# Frontend — Workshop Feedback Portal

Framework-less static frontend (HTML/CSS/JavaScript, no build step) for the
Workshop Feedback Portal POC. It is served as static assets from S3 via
CloudFront (see `docs/architecture.md`).

## Files

| File | Purpose |
|------|---------|
| `index.html` | Attendee submission view + organizer review view (tabbed). |
| `styles.css` | Responsive, accessible styling. |
| `api.js` | API access layer — implements `POST /feedback` and `GET /feedback` per `docs/api-contract.md`. |
| `app.js` | DOM/event logic, client-side convenience validation, UI state handling, safe rendering. |
| `config.js` | **Non-secret** runtime config: the API base URL (a Terraform output). |

## Configuration

The API base URL is **not** hardcoded. It is read at runtime from
`window.APP_CONFIG.apiBaseUrl` in `config.js`, which contains the placeholder
`__API_BASE_URL__`.

At deploy time, DevOps replaces the placeholder with the real API Gateway
default (`execute-api`) URL — a Terraform output. For example:

```js
window.APP_CONFIG = {
  apiBaseUrl: "https://abc123.execute-api.us-east-1.amazonaws.com"
};
```

No secret is involved: the API base URL is public. See NFR-007 / AC-013.

## Secrets policy

- **No AWS credentials, secrets, or the organizer key are embedded anywhere.**
- The organizer access key is entered at runtime in the review form and sent
  only as the `X-Organizer-Key` request header for that single request. It is
  never persisted to storage or written into any asset.

## Local preview

Open `index.html` through any static file server and set a valid `apiBaseUrl`
in `config.js`. No build tooling is required.
