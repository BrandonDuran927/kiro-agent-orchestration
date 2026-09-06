# ---------------------------------------------------------------------------
# API Gateway HTTP API (v2) — backend HTTP entry at the default execute-api URL
# (docs/architecture.md, docs/api-contract.md). No custom domain (NFR-004).
# ---------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"

  # CORS allows the CloudFront distribution origin for the required methods.
  cors_configuration {
    allow_origins = ["https://${aws_cloudfront_distribution.frontend.domain_name}"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "x-organizer-key"]
    max_age       = 300
  }

  tags = {
    Component = "api"
  }
}

# Lambda proxy integration (single path-routed function).
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# Routes defined by the API contract.
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "post_feedback" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /feedback"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "get_feedback" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /feedback"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Access logging to CloudWatch (NFR-013).
resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name_prefix}-http-api"
  retention_in_days = var.log_retention_days

  tags = {
    Component = "observability"
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      sourceIp       = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      integrationErr = "$context.integrationErrorMessage"
    })
  }

  tags = {
    Component = "api"
  }
}

# Allow API Gateway to invoke the Lambda.
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowInvokeFromHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
