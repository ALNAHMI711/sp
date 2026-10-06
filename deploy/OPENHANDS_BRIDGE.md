# OpenHands bridge configuration

The control hub connects to the OpenHands Agent Server over its authenticated API.

## Required runtime secrets

- `OPENHANDS_AGENT_SERVER_URL`
- `OPENHANDS_SESSION_API_KEY`
- `OPENHANDS_SECRET_KEY`

These values must exist only in the deployment secret store.

## API security

The Agent Server expects the session key in `X-Session-API-Key`. Keep the server private when possible. If it must be reachable across hosts, use TLS/private networking and firewall restrictions.

## Health checks

Use:
- `GET /health`
- `GET /ready`
- `GET /server_info`

Do not mark the backend online merely because the URL is configured. A health request must succeed.

## Smoke test

The first automated smoke test must use a non-sensitive repository/task and an isolated workspace. It must verify:
1. authentication;
2. server readiness;
3. conversation creation;
4. task execution;
5. result retrieval;
6. clean termination.

No Binance LIVE, withdrawals, production deployment, secret rotation, destructive database/repository operations, or force pushes are allowed in the smoke test.
