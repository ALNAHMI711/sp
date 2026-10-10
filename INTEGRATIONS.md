# Integration credentials and deployment configuration

The Arabic dashboard section **إعدادات التكامل والمفاتيح** is the entry point for application integration credentials. Never put real values in Git, source files, issue comments, screenshots, or logs.

## Integration catalog

All items below are optional until the corresponding integration is implemented and explicitly enabled. Saving a value only stores it; it does not by itself activate a connector or prove that the credential works.

| Integration | Dashboard field | When it is needed | Current scope / note |
| --- | --- | --- | --- |
| GitHub webhook | `GITHUB_WEBHOOK_SECRET` | When receiving GitHub webhook events | Verifies `X-Hub-Signature-256`; the repository must also be allowlisted. |
| GitHub App | `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY` | When GitHub App authentication is implemented/enabled | Credentials are stored, but these fields alone do not implement App token generation or grant repository access. Prefer a least-privilege GitHub App over a personal token. |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS` | When the Telegram controller is implemented/enabled | The allowlist is a security requirement; saving a token alone does not activate bot commands. |
| OpenAI | `OPENAI_API_KEY` | When an OpenAI-backed feature is implemented/enabled | Optional; saving does not activate AI execution. |
| Other AI provider | `AI_API_KEY` | Only for a specifically supported provider | Generic slot; do not assume any provider works until an adapter and connection test exist. |

The dashboard reports whether a value is present, not whether an external provider has accepted it. A real connection test must be implemented per provider before showing a credential as valid.

## Deployment-only settings

These configure the application itself and are not ordinary provider credentials. Supply them through the hosting platform's protected secret/configuration mechanism; never commit their values:

- `CONTROL_JWT_SECRET`: required to sign and validate admin sessions.
- `CONTROL_ADMIN_USERNAME` and `CONTROL_ADMIN_PASSWORD`: initial admin bootstrap credentials; use a unique strong password.
- `CONTROL_QUEUE_DB`: persistent database path/configuration.
- `CONTROL_QUEUE_BACKEND` and `CONTROL_POSTGRES_DSN`: required when using PostgreSQL.
- `CONTROL_KILL_SWITCH_FILE` and `CONTROL_WORKER_REGISTRY_DB`: deployment paths if customized.

Use `.env.example` for names and safe explanations only, never real values.

## Storage and operational safety

- The API accepts only allowlisted credential names and requires the authenticated user's `secrets:write` scope to save or delete them.
- Credential values are encrypted before being stored in the SQLite `integration_secrets` table and are never returned by the status endpoint.
- The Fernet encryption key is generated locally as `control-secrets.key` next to the configured database file. Keep the data directory on persistent storage, restrict access to the file, and include the key in an access-controlled encrypted backup. Losing this key makes saved credentials unrecoverable; exposing it compromises their confidentiality.
- Rotate credentials if they may have been exposed. Delete unused credentials from the dashboard and revoke them at the provider.
- The dashboard status means **configured**, not **connected/valid**. Do not use a configured status as a readiness or production go-live signal.
- Live or sensitive operations still require their separate approval and safety gates.
