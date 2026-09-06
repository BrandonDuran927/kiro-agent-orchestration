# Feedback persistence store (docs/data-model.md).
# On-demand capacity (NFR-008); partition key feedbackId; no sort key, no GSIs
# (single Scan/PutItem access pattern, minimal footprint per NFR-009).
resource "aws_dynamodb_table" "feedback" {
  name         = "${local.name_prefix}-feedback"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feedbackId"

  attribute {
    name = "feedbackId"
    type = "S"
  }

  tags = {
    Name      = "${local.name_prefix}-feedback"
    Component = "persistence"
  }
}
