# Durable Control Plane

The control queue is the persistence boundary between the phone/control UI and the autonomous worker runtime.

## Lifecycle

`queued -> running -> succeeded`

Failure or expired worker leases return a job to `queued` until `max_attempts` is exhausted, then the job becomes `failed`. A queued or running job may be cancelled.

## Guarantees

- SQLite WAL for crash-safe single-node persistence.
- Idempotency keys prevent duplicate submissions.
- Worker leases allow recovery after process/node failure.
- Attempt limits prevent infinite retry loops.
- Secrets are not stored in queue rows.
- The queue does not execute shell commands itself; execution remains behind the existing policy/OpenHands boundary.

## Migration path

SQLite is intentionally the MVP storage adapter. The domain contract is small enough to move the same lifecycle to PostgreSQL when the VPS deployment needs multiple control-plane instances.

## Safety

A queue entry does not imply authorization. The existing repository allowlist, task policy, approval rules and completion gate remain authoritative. Sensitive operations must still be rejected or explicitly approved.
