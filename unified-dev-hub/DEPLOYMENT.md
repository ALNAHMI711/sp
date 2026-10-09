# Deployment guide

## Docker Compose
1. Copy `.env.example` to `.env`.
2. Set `ADMIN_PASSWORD` to a unique long password and `SECRET_KEY` to a random value of at least 32 characters.
3. Run `docker compose up --build -d`.
4. Verify `http://localhost:8000/health` returns `{"status":"ok","database":"ok",...}`.

## Render
A starter `render.yaml` is included. Review the plan and persistent-disk pricing in your Render account before creating the service. Configure the required environment values in the Render dashboard. Persistent disks and always-on services may incur charges; do not assume this is a free deployment.

## Production checklist
- Use HTTPS and `COOKIE_SECURE=true`.
- Use a persistent disk/volume for SQLite. Do not use ephemeral storage for project records.
- Set unique administrator credentials and rotate them if exposed.
- Confirm `/health` is healthy after deployment.
- Keep the service private until login and authorization tests pass.
- Do not claim build/deploy status is real unless an actual provider integration verifies it.
- Back up the database before upgrades and test restoring a copy.
