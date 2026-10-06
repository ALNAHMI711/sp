# Durable Control Plane

The control queue is the persistence boundary between the phone/control UI and the autonomous worker runtime. Every newly submitted job starts in `pending_approval`; only an authenticated user with `jobs:approve` can move it to `queued`, which is the only state the worker may claim.

## Lifecycle

`pending_approval -> queued -> running -> succeeded`

Cancellation has two phases for active work: `running -> cancel_requested -> cancelled`. Queued work can move directly to `cancelled`. Failure or expired worker leases return a job to `queued` until `max_attempts` is exhausted, then the job becomes `failed`.

Finalization is compare-and-set style: a worker can only finish a job that is still `running`, so a concurrent cancellation cannot be overwritten by a later success.

## Guarantees

- SQLite WAL for crash-safe single-node persistence.
- Idempotency keys prevent duplicate submissions.
- Worker leases allow recovery after process/node failure.
- Attempt limits prevent infinite retry loops.
- Secrets are not stored in queue rows.
- The queue does not execute shell commands itself; execution remains behind the existing policy/OpenHands boundary.
- Pending approvals cannot be claimed by workers.
- Kill switch cancels pending approvals as well as queued work.

## Migration path

SQLite is supported for single-node deployments. PostgreSQL is the multi-worker adapter and uses `FOR UPDATE SKIP LOCKED` for safe concurrent claiming. The deployment migration service creates the PostgreSQL schema before the API/worker starts.

## Safety

A queue entry does not imply authorization. The existing repository allowlist, task policy, approval rules and completion gate remain authoritative. Sensitive operations must still be rejected or explicitly approved.
