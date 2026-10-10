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


## VPS with HTTPS (Caddy example)
The Compose port is bound to `127.0.0.1:8000`, not the public network. Put a reverse proxy in front of it:
1. Point your domain's DNS A/AAAA record to the VPS.
2. Install Caddy using its official instructions.
3. Copy `Caddyfile.example` to your Caddy configuration and replace `your-domain.example` with your domain.
4. Keep `COOKIE_SECURE=true` in the app's `.env` when serving over HTTPS.
5. Start/reload Caddy, then verify the HTTPS URL and `/health`.
6. Keep port 8000 blocked from public inbound traffic; expose only SSH and the proxy ports as needed.

Generate a secret key with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Backup reminder
The SQLite database is stored in the persistent `/data` volume. Back it up regularly before upgrades and keep backups outside the running container. Restore a backup to a separate test copy first; never overwrite the only production copy during a test.
