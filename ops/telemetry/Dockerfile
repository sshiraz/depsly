FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md cli.py /app/
COPY core /app/core
COPY scripts /app/scripts

RUN pip install --no-cache-dir .

ENV DEPSLY_TELEMETRY_INGEST_HOST=0.0.0.0
ENV DEPSLY_TELEMETRY_INGEST_PORT=8787
ENV DEPSLY_TELEMETRY_INGEST_DB_PATH=/var/lib/depsly-telemetry/telemetry.sqlite3

VOLUME ["/var/lib/depsly-telemetry"]

EXPOSE 8787

CMD ["python", "scripts/telemetry_ingest_server.py"]
