# Security policy

## Before exposing the service to the internet
1. Set a unique `ADMIN_USERNAME`, a long unique `ADMIN_PASSWORD`, and a cryptographically random `SECRET_KEY` of at least 32 characters.
2. Keep `.env` out of version control. Never commit API tokens, database credentials, or session secrets.
3. Put the service behind HTTPS and set `COOKIE_SECURE=true`.
4. Restrict network access where possible and keep dependencies updated.
5. Back up the persistent `/data` volume securely and test restore procedures.
6. Do not treat project stage values as proof of a successful build or deployment.

## Reporting
Do not publish secrets or personal data in issues. For a suspected vulnerability, report it privately to the repository maintainer.

## Current scope
This starter app is a single-admin project tracker. It does not execute repository code, run arbitrary shell commands, or deploy projects remotely. Provider integrations must be implemented and reviewed separately before production use.
