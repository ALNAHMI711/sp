# Integrations

Open `/static/integrations.html` while the application is running and signed in.

## GitHub (read-only status)
Set `GITHUB_READ_TOKEN` on the server to a fine-grained token with only the minimum account-read permission needed for `GET /user`. This endpoint only validates token identity; repository inspection and write operations are not implemented by this starter.

## Vercel (read-only status)
Set `VERCEL_READ_TOKEN` on the server with minimum user-read scope needed for `GET /v2/user`. This endpoint only validates token identity; project deployment operations are not implemented by this starter.

## Important
- Never add real tokens to GitHub files, browser storage, frontend code, or issue comments.
- The integration health endpoint returns status only, not token values or provider response bodies.
- Missing credentials are reported as `missing_token`; invalid/insufficient credentials are reported separately.
- A connected status does not mean the platform can build, deploy, or modify a project.
