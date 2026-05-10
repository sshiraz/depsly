# Telemetry Deployment

This runbook describes how to operate the Depsly telemetry backend that the CLI
targets after users opt in.

## Scope

The repository now contains:

- `scripts/telemetry_ingest_server.py` for the HTTPS-adjacent ingest process
- `scripts/telemetry_maintenance.py` for report publishing and retention cleanup
- `ops/telemetry/Dockerfile` for a simple containerized deployment
- `ops/telemetry/systemd/` for a basic VM-style deployment

This is intentionally small-footprint. It is suitable for low-volume telemetry
collection before a more managed backend is needed.

## Required Components

- one long-running ingest process
- one persistent data directory for the SQLite database and report artifacts
- one TLS-terminating reverse proxy in front of the ingest process
- one scheduled maintenance job

## Recommended Directory Layout

```text
/opt/depsly
  scripts/
  core/
  pyproject.toml

/var/lib/depsly-telemetry
  telemetry.sqlite3
  reports/
```

## Environment

Use the template in `ops/telemetry/env.example`.

Important variables:

- `DEPSLY_TELEMETRY_INGEST_HOST`
- `DEPSLY_TELEMETRY_INGEST_PORT`
- `DEPSLY_TELEMETRY_INGEST_DB_PATH`
- `DEPSLY_TELEMETRY_REPORT_DIR`
- `DEPSLY_TELEMETRY_RAW_RETAIN_DAYS`
- `DEPSLY_TELEMETRY_REPORT_RETAIN_DAYS`

## Deployment Modes

### Container

Build:

```bash
docker build -f ops/telemetry/Dockerfile -t depsly-telemetry .
```

Run:

```bash
docker run \
  --name depsly-telemetry \
  -p 127.0.0.1:8787:8787 \
  -v /var/lib/depsly-telemetry:/var/lib/depsly-telemetry \
  -e DEPSLY_TELEMETRY_INGEST_HOST=0.0.0.0 \
  -e DEPSLY_TELEMETRY_INGEST_PORT=8787 \
  -e DEPSLY_TELEMETRY_INGEST_DB_PATH=/var/lib/depsly-telemetry/telemetry.sqlite3 \
  depsly-telemetry
```

Run maintenance separately on the host or in a short-lived container:

```bash
python scripts/telemetry_maintenance.py \
  --db-path /var/lib/depsly-telemetry/telemetry.sqlite3 \
  --output-dir /var/lib/depsly-telemetry/reports
```

### VM / systemd

1. Copy the repo to `/opt/depsly`
2. Create `/etc/depsly-telemetry.env` from `ops/telemetry/env.example`
3. Install the unit files from `ops/telemetry/systemd/`
4. Enable and start:

```bash
sudo systemctl enable --now depsly-telemetry-ingest.service
sudo systemctl enable --now depsly-telemetry-maintenance.timer
```

## Reverse Proxy

The Python ingest server is intentionally minimal and should sit behind a
reverse proxy that terminates TLS and optionally enforces request limits.

Requirements:

- route `POST /v1/telemetry/events`
- route `GET /health`
- limit request body size to match or exceed the server cap of `256 KB`
- expose the public hostname used by the CLI endpoint

## Smoke Test

After deployment:

1. `curl http://127.0.0.1:8787/health`
2. run a local Depsly CLI with telemetry enabled against the deployment
3. verify rows appear in the SQLite DB
4. run maintenance once
5. verify:
   - dated JSON report exists
   - dated text report exists
   - latest JSON report exists
   - latest text report exists

## Monitoring

Minimum monitoring:

- HTTP health check against `/health`
- alert if the ingest service stops responding
- alert if `latest-telemetry-report.txt` stops updating

## Scaling Boundary

This SQLite-backed deployment is appropriate for low traffic and simple ops.

Move to Postgres when you need:

- stronger concurrency guarantees
- easier backup/restore workflows
- higher ingest volume
- multiple application instances
