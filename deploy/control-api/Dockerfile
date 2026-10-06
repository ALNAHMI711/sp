FROM python:3.12-slim
WORKDIR /app
COPY deploy/control-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY worker /app/worker
COPY app /app/app
COPY deploy/migrate_postgres.py /app/deploy/migrate_postgres.py
COPY .gitignore /app/.gitignore
RUN useradd --create-home --uid 10002 api && mkdir -p /app/data && chown -R api:api /app
USER api
EXPOSE 8080
CMD ["uvicorn", "app.control_api:app", "--host", "0.0.0.0", "--port", "8080"]
