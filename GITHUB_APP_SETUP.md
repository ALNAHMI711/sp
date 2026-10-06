# GitHub App Setup for the Autonomous Worker

The worker's write mode uses a short-lived GitHub App installation token instead of a long-lived personal access token.

## Required App permissions

Install the App only on the repositories the worker is allowed to modify.

Required repository permissions:

- Contents: Read and write
- Pull requests: Read and write

Do not grant administration, secrets, deployments, or destructive repository permissions.

## Control-hub configuration

In `ALNAHMI711/sp`:

1. Create repository variable:
   `AUTONOMOUS_WORKER_APP_CLIENT_ID`
2. Create repository secret:
   `AUTONOMOUS_WORKER_APP_PRIVATE_KEY`
3. Install the App on the approved target repositories.
4. Run the workflow manually with:
   - `write_mode = propose_changes`
   - `run_openhands = true`

The workflow creates a temporary installation token, clones the target repository with it, and revokes the token after the job.

## OpenHands configuration

For actual coding execution, configure these secrets in `sp`:

- `OPENHANDS_AGENT_SERVER_URL`
- `OPENHANDS_SESSION_API_KEY`

The Agent Server must be reachable from the GitHub runner. Keep it behind TLS/private networking where possible.

## Safety

The worker only opens a **draft** PR after:

1. repository allowlist and task policy pass;
2. tests pass before the agent;
3. OpenHands reports `finished`;
4. tests pass after the agent;
5. completion gate passes.

Sensitive operations remain blocked by policy and are not delegated to the worker.
