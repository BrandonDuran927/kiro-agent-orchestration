# ---------------------------------------------------------------------------
# Lambda packaging
# ---------------------------------------------------------------------------
# The backend workstream owns the function code and produces a build output
# directory (see docs/infrastructure-implementation-summary.md for the artifact
# contract). This config packages that directory into a deterministic zip via
# archive_file so application changes are detected by content hash.
#
# If the backend build output is not yet present (parallel workstreams), a
# bundled placeholder under terraform/lambda_bootstrap/ is packaged instead so
# the configuration remains internally consistent for fmt/validate/plan. The
# real backend build output MUST be present before deployment.
locals {
  lambda_build_present = fileexists("${var.lambda_source_dir}/${split(".", var.lambda_handler)[0]}.py")
  lambda_source_dir    = local.lambda_build_present ? var.lambda_source_dir : "${path.module}/lambda_bootstrap"
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = local.lambda_source_dir
  output_path = "${path.module}/${var.lambda_zip_output_path}"
}

# ---------------------------------------------------------------------------
# CloudWatch log group for the Lambda (NFR-013)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days

  tags = {
    Component = "observability"
  }
}

# ---------------------------------------------------------------------------
# Lambda execution role (least privilege, NFR-006)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = {
    Component = "iam"
  }
}

# Scoped logging permissions to this function's log group only.
data "aws_iam_policy_document" "lambda_permissions" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  # DynamoDB access scoped to the Feedback table ARN and only the required
  # actions (PutItem for create, GetItem/Scan for the reserved/list patterns).
  statement {
    sid    = "FeedbackTableAccess"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.feedback.arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name_prefix}-lambda-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# ---------------------------------------------------------------------------
# Lambda function (Python, single path-routed handler)
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.lambda.arn
  runtime       = var.lambda_runtime
  handler       = var.lambda_handler

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  timeout     = 10
  memory_size = 128

  environment {
    variables = {
      FEEDBACK_TABLE_NAME = aws_dynamodb_table.feedback.name
      ORGANIZER_KEY       = local.organizer_key
      LOG_LEVEL           = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda,
    aws_cloudwatch_log_group.lambda,
  ]

  tags = {
    Component = "compute"
  }
}
