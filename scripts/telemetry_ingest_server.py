"""Run a minimal Depsly telemetry ingestion service."""

from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.telemetry_ingest import (
    handle_ingest_post,
    health_response,
    count_stored_telemetry_events,
    init_telemetry_ingest_db,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Depsly telemetry ingestion service.")
    parser.add_argument(
        "--host",
        default=os.environ.get("DEPSLY_TELEMETRY_INGEST_HOST", "127.0.0.1"),
        help="Host interface to bind.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DEPSLY_TELEMETRY_INGEST_PORT", "8787")),
        help="Port to listen on.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(
            os.environ.get(
                "DEPSLY_TELEMETRY_INGEST_DB_PATH",
                str(ROOT / "var" / "telemetry" / "telemetry.sqlite3"),
            )
        ),
        help="SQLite path for raw telemetry events.",
    )
    return parser.parse_args()


class TelemetryIngestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for telemetry event ingestion."""

    db_path: Path

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            status, payload = health_response(self.db_path)
            self._send_json(status, payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        raw_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_length)
        except ValueError:
            content_length = 0
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        status, payload = handle_ingest_post(
            path=self.path,
            content_length_header=raw_length,
            raw_body=raw_body,
            db_path=self.db_path,
        )
        self._send_json(status, payload)


def make_handler(db_path: Path):
    """Bind the ingest DB path into a handler class."""
    init_telemetry_ingest_db(db_path)

    class BoundTelemetryIngestHandler(TelemetryIngestHandler):
        pass

    BoundTelemetryIngestHandler.db_path = db_path
    return BoundTelemetryIngestHandler


def main() -> int:
    args = parse_args()
    handler = make_handler(args.db_path)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Listening on http://{args.host}:{args.port}")
    print(f"SQLite DB: {args.db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
