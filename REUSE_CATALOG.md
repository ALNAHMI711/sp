# Reuse Catalog

This project intentionally reuses existing, tested components instead of rebuilding them.

## Existing components found in ALNAHMI711 repositories

### autonomous-business-manager
- `app/persistent_queue.py` — durable SQLite FIFO queue, idempotent task IDs, retries and stale-claim recovery.
- `app/persistent_worker.py` — restart-safe worker loop with task-manager integration and recovery.
- `app/approval.py` — approval/pause/resume/stop lifecycle with audit records.
- `app/queue_runtime.py` — kill switch, network execution gate, authenticated control endpoints, queue startup and recovery.

These are strong candidates for the future control-plane runtime of `sp`; they should be extracted or reused through a shared package rather than rewritten.

### -
- `app/job_queue.py` — framework-neutral queue lifecycle with idempotency keys, worker leases, retries, cancellation and expired-lease reclamation.
- `app/worker_agent.py` — worker enrollment/heartbeat/draining state model.
- `app/worker_command_handler.py` — authenticated worker command routing and ownership checks.

These are useful for the eventual multi-node worker layer.

## Upstream components

### OpenHands
Use the maintained OpenHands stack for agent execution instead of implementing an AI coding runtime inside `sp`:
- Agent Canvas: control center.
- Software Agent SDK / Agent Server: conversations, workspaces and agent execution.
- Automation: schedules, webhooks, dispatch and run history.
- Extensions PR Review: ready-made automated PR review.

## GitHub
Use GitHub Actions and the official `actions/create-github-app-token` action for temporary scoped credentials.

## Target architecture

`sp` owns:
policy -> approvals -> repository allowlist -> job orchestration -> audit -> completion gates

Existing ABM/- components can provide:
durable queue -> worker leases -> retries -> worker health -> kill switch

OpenHands owns:
AI coding execution -> workspace -> agent tools -> agent conversation

GitHub owns:
branches -> commits -> PRs -> CI -> review status

Do not duplicate these responsibilities.
