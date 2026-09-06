# Example variable values for the Workshop Feedback Portal POC.
# Copy to a real *.auto.tfvars file (git-ignored) OR export TF_VAR_* env vars.
# Do NOT commit real secret values (NFR-007).

aws_region   = "us-east-1"
project_name = "workshop-feedback"
environment  = "poc"

# Supply the organizer shared key at plan/apply time. Prefer:
#   $Env:TF_VAR_organizer_key = "your-strong-shared-key"   (PowerShell)
#   export TF_VAR_organizer_key="your-strong-shared-key"    (bash)
# If omitted, Terraform generates a random key (see `terraform output -raw organizer_key`).
# organizer_key = "REPLACE_ME_DO_NOT_COMMIT"

# Artifact paths (relative to the terraform/ directory).
# lambda_source_dir   = "../backend/build"
# frontend_source_dir = "../frontend/dist"
