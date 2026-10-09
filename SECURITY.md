# Security Policy

## Production rules

1. Never commit passwords, API keys, tokens, private keys, `.env` files, or other credentials.
2. Integration credentials (GitHub App, webhook, Telegram, and AI provider keys) should be entered through the authenticated control-panel Integrations page. Values are encrypted before storage, never returned by the API, and the encryption key is kept in the persistent data volume with restrictive file permissions. Environment variables are fallback/bootstrap only; do not require integration keys in the deployment environment for the panel to operate.
3. The admin dashboard and all sensitive API/WebSocket routes require server-side authentication and authorization.
4. Production deployments require successful security checks, automated tests, staging health checks, and post-deployment verification.
5. GitHub webhooks must be authenticated with a signature before any deployment action is queued.
6. Repository code is untrusted input and must not receive production secrets during build or test execution.
7. AI automation is policy-constrained and cannot bypass approvals, security controls, or audit logging.
8. Kill switch and maintenance mode must remain explicit administrative actions.

## Control-panel integration secrets\n\nThe control panel supports encrypted storage for `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS`, and `AI_API_KEY`. Only SUPER_ADMIN and ADMIN roles may manage them. Deleting a panel value may expose an environment fallback if one is configured, so remove obsolete fallback values from the host after migration. Back up the persistent data volume securely; losing `control-secrets.key` makes stored values unrecoverable.\n\n## Reporting

Do not publish credentials or exploit details in repository issues. Rotate compromised credentials immediately and document the incident through the private operational audit process.
