# VPS Worker Runtime

This deployment is the first always-on runtime for the control-plane worker.

## Architecture

Phone/control client -> future Control API -> SQLite/PostgreSQL control queue -> worker container -> policy -> inspection -> OpenHands -> tests -> completion.

The phone is not part of the execution path.

## Deployment

On the VPS:

1. Install Docker Engine and Docker Compose.
2. Clone this repository.
3. Copy `deploy/worker.env.example` to `deploy/worker.env`.
4. Fill only runtime secrets on the VPS; never commit `worker.env`.
5. Start:

```bash
docker compose -f deploy/compose.worker.yml up -d --build
```

6. Verify:

```bash
docker compose -f deploy/compose.worker.yml ps
docker compose -f deploy/compose.worker.yml logs --tail=100 worker
```

Compose uses `restart: unless-stopped` and a healthcheck so the worker can recover from process/container failures. Docker documents `unless-stopped` as a restart policy that continues across daemon restarts unless the service was manually stopped. The healthcheck provides an explicit container health signal.

## Security posture

- Root filesystem is read-only.
- `no-new-privileges` is enabled.
- All Linux capabilities are dropped.
- Queue data is stored in a named volume.
- Temporary files use tmpfs.
- Secrets come from the VPS environment file, outside Git.
- The worker does not expose a network port.
- Sensitive tasks remain blocked by the queue/policy boundary.

## Important limitation

This is a single-node worker runtime. PostgreSQL, multi-worker coordination, API authentication, audit events, and production failover are still separate implementation steps.

Do not treat a healthy container as proof that OpenHands is configured or that a deployment is production-ready.
