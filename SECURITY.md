# Security Policy

## Production rules

1. Never commit passwords, API keys, tokens, private keys, `.env` files, or other credentials.
2. Production secrets are injected at runtime through environment variables or a dedicated secret manager.
3. The admin dashboard and all sensitive API/WebSocket routes require server-side authentication and authorization.
4. Production deployments require successful security checks, automated tests, staging health checks, and post-deployment verification.
5. GitHub webhooks must be authenticated with a signature before any deployment action is queued.
6. Repository code is untrusted input and must not receive production secrets during build or test execution.
7. AI automation is policy-constrained and cannot bypass approvals, security controls, or audit logging.
8. Kill switch and maintenance mode must remain explicit administrative actions.

## Reporting

Do not publish credentials or exploit details in repository issues. Rotate compromised credentials immediately and document the incident through the private operational audit process.
