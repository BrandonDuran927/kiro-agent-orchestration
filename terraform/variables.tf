variable "aws_region" {
  description = "AWS region into which the POC is deployed."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project identifier used as a prefix for resource names and tags."
  type        = string
  default     = "workshop-feedback"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,32}$", var.project_name))
    error_message = "project_name must be 3-32 chars of lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment/stage label (POC lifecycle)."
  type        = string
  default     = "poc"
}

variable "organizer_key" {
  description = <<-EOT
    Shared organizer access key (A-005). Injected into the Lambda environment so the
    function can gate GET /feedback. Never embed this in source or frontend assets
    (NFR-007). Supply via TF_VAR_organizer_key, a *.auto.tfvars file excluded from
    version control, or -var at plan/apply time. If left empty, a random key is
    generated so the stack remains internally consistent for validation.
  EOT
  type        = string
  default     = ""
  sensitive   = true
}

variable "lambda_runtime" {
  description = "Python runtime for the backend Lambda function."
  type        = string
  default     = "python3.12"
}

variable "lambda_handler" {
  description = "Lambda handler entrypoint (module.function) exposed by the backend build output."
  type        = string
  default     = "handler.lambda_handler"
}

variable "lambda_source_dir" {
  description = <<-EOT
    Path (relative to the terraform/ directory) to the backend build output that will be
    packaged into the Lambda deployment zip via archive_file. See the infrastructure
    implementation summary for the artifact contract. Defaults to the backend build
    output directory produced by the backend workstream.
  EOT
  type        = string
  default     = "../backend/build"
}

variable "lambda_zip_output_path" {
  description = "Path (relative to terraform/) where the packaged Lambda zip is written."
  type        = string
  default     = "build/lambda.zip"
}

variable "frontend_source_dir" {
  description = <<-EOT
    Path (relative to the terraform/ directory) to the built static frontend assets that
    are uploaded to the private S3 bucket. Produced by the frontend workstream.
  EOT
  type        = string
  default     = "../frontend/dist"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days for Lambda and API Gateway log groups."
  type        = number
  default     = 14
}

variable "cloudfront_price_class" {
  description = "CloudFront price class. PriceClass_100 is cheapest and sufficient for a POC."
  type        = string
  default     = "PriceClass_100"
}
