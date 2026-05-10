"""Minimal telemetry ingestion service primitives."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path


MAX_BATCH_SIZE = 100
MAX_REQUEST_BYTES = 256 * 1024

ALLOWED_COMMANDS = {
    "analyze",
    "recommend",
    "trace",
    "simulate-remove",
    "save-scan",
    "list-scans",
    "compare-scans",
    "graph-html",
}
ALLOWED_PLATFORMS = {"macos", "linux", "windows", "unknown"}
ALLOWED_DURATION_BUCKETS = {"<1s", "1-5s", "5-30s", "30s+"}
ALLOWED_GRAPH_SIZE_BUCKETS = {"unknown", "0-50", "51-200", "201-1000", "1000+"}
ALLOWED_FAILURE_CATEGORIES = {
    "parse_error",
    "unsupported_lockfile",
    "missing_file",
    "internal_error",
}
ALLOWED_OPTION_KEYS = {"include_dev", "json", "open_browser"}


@dataclass
class ValidationResult:
    """Validation result for a telemetry request payload."""

    accepted: int
    rejected: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return self.rejected == 0


def _is_iso_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_telemetry_event(event: object, *, index: int = 0) -> list[str]:
    """Validate one telemetry event against the documented schema."""
    prefix = f"events[{index}]"
    errors: list[str] = []
    if not isinstance(event, dict):
        return [f"{prefix} must be an object"]

    required = {
        "event",
        "schema_version",
        "install_id",
        "session_id",
        "timestamp",
        "depsly_version",
        "platform",
        "python_version",
        "command",
        "options",
        "result",
    }
    missing = sorted(required - set(event))
    for key in missing:
        errors.append(f"{prefix}.{key} is required")

    extra = sorted(set(event) - (required | {"first_use_on_install"}))
    for key in extra:
        errors.append(f"{prefix}.{key} is not allowed")

    if event.get("event") != "cli.command.completed":
        errors.append(f"{prefix}.event must be 'cli.command.completed'")
    if event.get("schema_version") != "1":
        errors.append(f"{prefix}.schema_version must be '1'")
    if not isinstance(event.get("install_id"), str) or not event.get("install_id"):
        errors.append(f"{prefix}.install_id must be a non-empty string")
    if not isinstance(event.get("session_id"), str) or not event.get("session_id"):
        errors.append(f"{prefix}.session_id must be a non-empty string")
    if not _is_iso_datetime(event.get("timestamp")):
        errors.append(f"{prefix}.timestamp must be an ISO-8601 datetime string")
    if not isinstance(event.get("depsly_version"), str) or not event.get("depsly_version"):
        errors.append(f"{prefix}.depsly_version must be a non-empty string")
    if event.get("platform") not in ALLOWED_PLATFORMS:
        errors.append(f"{prefix}.platform is invalid")
    if not isinstance(event.get("python_version"), str) or not event.get("python_version"):
        errors.append(f"{prefix}.python_version must be a non-empty string")
    if event.get("command") not in ALLOWED_COMMANDS:
        errors.append(f"{prefix}.command is invalid")
    if "first_use_on_install" in event and not isinstance(event.get("first_use_on_install"), bool):
        errors.append(f"{prefix}.first_use_on_install must be a boolean")

    options = event.get("options")
    if not isinstance(options, dict):
        errors.append(f"{prefix}.options must be an object")
    else:
        extra_options = sorted(set(options) - ALLOWED_OPTION_KEYS)
        for key in extra_options:
            errors.append(f"{prefix}.options.{key} is not allowed")
        for key, value in options.items():
            if not isinstance(value, bool):
                errors.append(f"{prefix}.options.{key} must be a boolean")

    result = event.get("result")
    if not isinstance(result, dict):
        errors.append(f"{prefix}.result must be an object")
    else:
        result_required = {"success", "duration_bucket", "graph_size_bucket"}
        missing_result = sorted(result_required - set(result))
        for key in missing_result:
            errors.append(f"{prefix}.result.{key} is required")
        extra_result = sorted(set(result) - (result_required | {"failure_category"}))
        for key in extra_result:
            errors.append(f"{prefix}.result.{key} is not allowed")
        if not isinstance(result.get("success"), bool):
            errors.append(f"{prefix}.result.success must be a boolean")
        if result.get("duration_bucket") not in ALLOWED_DURATION_BUCKETS:
            errors.append(f"{prefix}.result.duration_bucket is invalid")
        if result.get("graph_size_bucket") not in ALLOWED_GRAPH_SIZE_BUCKETS:
            errors.append(f"{prefix}.result.graph_size_bucket is invalid")
        if "failure_category" in result and result.get("failure_category") not in ALLOWED_FAILURE_CATEGORIES:
            errors.append(f"{prefix}.result.failure_category is invalid")

    return errors


def validate_telemetry_batch(payload: object) -> ValidationResult:
    """Validate a telemetry batch request body."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ValidationResult(accepted=0, rejected=1, errors=["payload must be an object"])

    if payload.get("schema_version") != "1":
        errors.append("schema_version must be '1'")
    if not _is_iso_datetime(payload.get("sent_at")):
        errors.append("sent_at must be an ISO-8601 datetime string")

    events = payload.get("events")
    if not isinstance(events, list):
        errors.append("events must be an array")
        return ValidationResult(accepted=0, rejected=1, errors=errors)
    if not events:
        errors.append("events must not be empty")
    if len(events) > MAX_BATCH_SIZE:
        errors.append(f"events must contain at most {MAX_BATCH_SIZE} items")

    event_errors = [err for i, event in enumerate(events) for err in validate_telemetry_event(event, index=i)]
    errors.extend(event_errors)
    rejected = len(events) if errors else 0
    accepted = 0 if errors else len(events)
    return ValidationResult(accepted=accepted, rejected=rejected, errors=errors)


def init_telemetry_ingest_db(db_path: Path) -> Path:
    """Initialize the SQLite database used for raw telemetry event storage."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table if not exists telemetry_raw_events (
                id integer primary key autoincrement,
                received_at text not null,
                event_timestamp text not null,
                schema_version text not null,
                install_id text not null,
                session_id text not null,
                depsly_version text not null,
                platform text not null,
                python_version text not null,
                command text not null,
                first_use_on_install integer,
                options_json text not null,
                result_json text not null,
                event_json text not null
            )
            """
        )
        conn.commit()
    return db_path


def store_telemetry_events(db_path: Path, events: list[dict]) -> int:
    """Persist validated telemetry events and return the number stored."""
    init_telemetry_ingest_db(db_path)
    received_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            insert into telemetry_raw_events (
                received_at,
                event_timestamp,
                schema_version,
                install_id,
                session_id,
                depsly_version,
                platform,
                python_version,
                command,
                first_use_on_install,
                options_json,
                result_json,
                event_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    received_at,
                    event["timestamp"],
                    event["schema_version"],
                    event["install_id"],
                    event["session_id"],
                    event["depsly_version"],
                    event["platform"],
                    event["python_version"],
                    event["command"],
                    1 if event.get("first_use_on_install") else 0,
                    json.dumps(event["options"], sort_keys=True),
                    json.dumps(event["result"], sort_keys=True),
                    json.dumps(event, sort_keys=True),
                )
                for event in events
            ],
        )
        conn.commit()
    return len(events)


def count_stored_telemetry_events(db_path: Path) -> int:
    """Return the number of raw telemetry events stored in the SQLite database."""
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("select count(*) from telemetry_raw_events").fetchone()
    return int(row[0]) if row else 0


def prune_stored_telemetry_events(
    db_path: Path,
    *,
    retain_days: int,
    now: datetime | None = None,
) -> int:
    """Delete raw telemetry events older than the retention window."""
    if retain_days < 0:
        raise ValueError("retain_days must be non-negative")
    if not db_path.exists():
        return 0

    effective_now = now or datetime.now(UTC)
    cutoff = (effective_now - timedelta(days=retain_days)).replace(microsecond=0)
    cutoff_text = cutoff.isoformat().replace("+00:00", "Z")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            delete from telemetry_raw_events
            where received_at < ?
            """,
            (cutoff_text,),
        )
        conn.commit()
    return int(cursor.rowcount or 0)


def health_response(db_path: Path) -> tuple[int, dict]:
    """Build the health response payload for the ingestion service."""
    return (
        HTTPStatus.OK,
        {
            "status": "ok",
            "stored_events": count_stored_telemetry_events(db_path),
        },
    )


def handle_ingest_post(*, path: str, content_length_header: str, raw_body: bytes, db_path: Path) -> tuple[int, dict]:
    """Handle one logical telemetry ingest POST request."""
    if path != "/v1/telemetry/events":
        return HTTPStatus.NOT_FOUND, {"error": "not_found"}

    try:
        content_length = int(content_length_header)
    except ValueError:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"}

    if content_length <= 0:
        return HTTPStatus.BAD_REQUEST, {"error": "empty_request"}
    if content_length > MAX_REQUEST_BYTES:
        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "payload_too_large"}

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return (
            HTTPStatus.BAD_REQUEST,
            {"accepted": 0, "rejected": 1, "errors": ["request body must be valid JSON"]},
        )

    validation = validate_telemetry_batch(payload)
    if not validation.ok:
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "accepted": validation.accepted,
                "rejected": validation.rejected,
                "errors": validation.errors,
            },
        )

    stored = store_telemetry_events(db_path, payload["events"])
    return HTTPStatus.ACCEPTED, {"accepted": stored, "rejected": 0}
