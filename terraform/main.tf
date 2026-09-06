provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Scope       = "poc"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# When no organizer_key is supplied, generate one so the stack is internally
# consistent for validation/plan without embedding a secret in source (NFR-007).
resource "random_password" "organizer_key" {
  count   = var.organizer_key == "" ? 1 : 0
  length  = 32
  special = false
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Effective organizer key: supplied value takes precedence, otherwise generated.
  organizer_key = var.organizer_key != "" ? var.organizer_key : one(random_password.organizer_key[*].result)

  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}
