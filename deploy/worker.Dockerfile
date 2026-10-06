FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY worker /app/worker
COPY .gitignore /app/.gitignore
RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /app/data /app/workspaces \
    && chown -R worker:worker /app
USER worker

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python /app/worker/worker_health.py

CMD ["python", "/app/worker/control_worker.py", "--db", "/app/data/control-queue.sqlite3"]
