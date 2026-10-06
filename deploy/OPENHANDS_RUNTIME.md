# OpenHands deployment plan

This directory contains deployment guidance only. It does not contain production secrets.

## Runtime

- OpenHands Agent Canvas on an always-on VM.
- Docker isolation preferred for project workspaces.
- nginx or equivalent TLS reverse proxy.
- Firewall: SSH restricted; HTTPS exposed only as required.
- Strong LOCAL_BACKEND_API_KEY stored outside Git.
- GitHub credentials stored as runtime secrets.
- Separate workspace per repository/task.

## Control flow

GitHub issue/webhook/approved task
-> sp policy
-> OpenHands automation
-> isolated workspace
-> tests
-> PR
-> CI
-> completion event
-> notification

## Current limitation

The GitHub Actions worker in sp is an interim bootstrap. It should not be treated as the final 24/7 runtime because scheduled Actions are bounded CI jobs, not a permanent server.

## Security

Never expose the Agent Server without authentication and network hardening. OpenHands can execute shell commands and access filesystem/network resources on its host.
