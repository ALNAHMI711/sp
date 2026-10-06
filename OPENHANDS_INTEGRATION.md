# OpenHands Integration

## Role split

- `sp`: control plane, repository allowlist, policy guard, approvals, audit, completion state.
- OpenHands Agent Canvas: coding-agent runtime and automation engine.
- GitHub: source control, pull requests and CI.
- Phone: monitoring/control only.

## Approved execution model

1. A task enters `sp`.
2. Policy checks repository and task sensitivity.
3. OpenHands receives only an approved task.
4. OpenHands works in an isolated workspace.
5. Tests and CI are required before completion.
6. Changes are committed to a branch and proposed as a PR.
7. `sp` records the result and notifies the operator.
8. Sensitive production/trading actions remain outside autonomous authority.

## Deployment

For the eventual 24/7 deployment, run OpenHands Agent Canvas on a secured VM with Docker or another isolated backend. Use TLS, a strong backend API key, firewall restrictions, and separate credentials for GitHub. OpenHands documents VM self-hosting and scheduled/webhook automations.

## Important boundary

Do not expose an OpenHands agent directly to the public internet without authentication and network hardening. The agent can execute commands and access files/network resources.

## Current phase

The repository currently contains a GitHub Actions bootstrap worker. This is an interim control-plane implementation. The next migration step is to replace its custom coding loop with OpenHands as the execution backend rather than duplicating an agent implementation inside `sp`.
