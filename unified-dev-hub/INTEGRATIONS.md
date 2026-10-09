# Integrations

Open `/static/integrations.html` while the application is running and signed in.

## GitHub (read-only)
Set `GITHUB_READ_TOKEN` on the server to a fine-grained token with only the minimum permissions required for account identity and repository metadata.
- `GET /api/integrations`: validates token identity.
- `GET /api/github/repos`: returns up to 25 accessible repositories with names, visibility, default branch, URL, and update timestamp.

## Vercel (read-only)
Set `VERCEL_READ_TOKEN` on the server with minimum user/project-read scope.
- `GET /api/integrations`: validates token identity.
- `GET /api/vercel/projects`: returns up to 25 projects with name, framework, and update timestamp.

## Important
- Never add real tokens to GitHub files, browser storage, frontend code, or issue comments.
- Tokens remain on the server; API responses do not include token values or raw provider response bodies.
- Missing credentials are reported as `missing_token`; invalid/insufficient credentials are reported separately.
- Provider browsing is read-only. It does not trigger workflow runs, edit repositories, build apps, or deploy to Vercel.
- A connected status does not mean all platform operations are available.
