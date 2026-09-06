# Infra-owned placeholder ONLY.
#
# This file exists so `data.archive_file.lambda` always has a valid source_dir
# for `terraform fmt/validate/plan`, even before the backend workstream has
# produced its build output (parallel workstreams per SDLC_WORKFLOW.md).
#
# It is NOT the application. The real backend handler is owned by the
# backend-developer under backend/ and is packaged from var.lambda_source_dir
# (default ../backend/build) when present. See
# docs/infrastructure-implementation-summary.md for the artifact contract.
#
# Handler signature matches var.lambda_handler default: handler.lambda_handler
import json


def lambda_handler(event, context):
    return {
        "statusCode": 503,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Backend build output not deployed.",
                }
            }
        ),
    }
