# Autonomous Cloud Execution & Control Hub

## Purpose
`sp` is the control hub for an autonomous coding worker. The phone is only a control/monitoring client; the worker runs independently in cloud infrastructure.

## Initial repositories
- ALNAHMI711/Ahmed-Alnahmi-711 — trading execution foundation
- ALNAHMI711/autonomous-business-manager — automation/orchestration
- ALNAHMI711/- — content automation
- ALNAHMI711/tte — trading/chart terminal

## Safe lifecycle
DISCOVERED -> INSPECTING -> TESTING -> RUNNING -> TESTING -> COMPLETION_GATE -> PROPOSED -> CI -> READY

Failures return to TESTING or PROPOSED; sensitive actions require explicit approval.

## Hard safety boundary
The worker must never autonomously:
- enable Binance LIVE trading;
- enable withdrawals;
- rotate or expose secrets;
- deploy destructive production changes;
- liquidate positions as a generic recovery action.

Risk controls cannot be bypassed by AI, strategy, Telegram, or automation.

## Current worker mode
The worker now supports two explicit modes:

- `read_only`: inspect, clone, test, run OpenHands when configured, and produce reports.
- `propose_changes`: after policy approval, use a GitHub App installation token scoped to the target repository, allow OpenHands to edit an isolated runner workspace, rerun tests, pass the completion gate, push an `agent/*` branch, and open a **draft PR**.

A failed test, policy denial, missing OpenHands credentials, or failed completion gate prevents PR publication.

## GitHub App boundary
Write mode requires these control-hub settings:

- Repository variable: `AUTONOMOUS_WORKER_APP_CLIENT_ID`
- Repository secret: `AUTONOMOUS_WORKER_APP_PRIVATE_KEY`

The GitHub App installation should be limited to the target repositories and granted only the permissions required for this worker: repository contents write and pull requests write. The workflow creates a short-lived installation token and scopes it to the selected target repository.

No personal access token is stored in source control.

## Ready-made components used
The worker deliberately reuses maintained upstream components instead of reimplementing an agent runtime:

- OpenHands Agent Server / Software Agent SDK for coding execution.
- `actions/create-github-app-token` for short-lived GitHub App installation credentials.
- GitHub Actions for CI, artifacts, scheduling, and execution.
- GitHub draft PRs as the human-review boundary.

This keeps `sp` focused on policy, repository allowlisting, approvals, audit/completion gates, and orchestration.

## Phone independence
Closing the phone or losing mobile connectivity must not stop cloud execution. The phone only sends commands and reads status.
