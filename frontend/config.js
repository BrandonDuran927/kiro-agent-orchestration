/*
 * Runtime configuration for the Workshop Feedback Portal frontend.
 *
 * This file holds ONLY non-secret configuration. The single value here is the
 * API Gateway default (execute-api) base URL, which is a Terraform *output*
 * (see docs/architecture.md section 7). It is safe to serve publicly.
 *
 * DO NOT place AWS credentials, secrets, or the organizer access key in this
 * file or anywhere in the frontend assets (NFR-007, AC-013). The organizer key
 * is entered at runtime by the organizer and lives only in memory for the
 * duration of a review request.
 *
 * DevOps replaces the placeholder below at deploy time with the real API base
 * URL (Terraform output). A trailing slash is tolerated by the app.
 */
window.APP_CONFIG = {
  // Example: "https://abc123.execute-api.us-east-1.amazonaws.com"
  apiBaseUrl: "__API_BASE_URL__"
};
