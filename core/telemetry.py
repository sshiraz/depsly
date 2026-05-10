"""Privacy-first local telemetry helpers for the Depsly CLI."""

from __future__ import annotations

import json
import os
import platform
import sys
import uuid
from pathlib import Path
from time import perf_counter
from urllib import error as urllib_error
from urllib import request as urllib_request

from core.export import TOOL_VERSION, scan_timestamp
from core.storage import depsly_home

DEFAULT_TELEMETRY_URL = "https://telemetry.depsly.com/v1/telemetry/events"


def telemetry_dir() -> Path:
    """Return the local directory used for telemetry config and queued events."""
    return depsly_home() / "telemetry"


def telemetry_config_path() -> Path:
    """Return the local telemetry config path."""
    return telemetry_dir() / "config.json"


def telemetry_queue_path() -> Path:
    """Return the local telemetry queue path."""
    return telemetry_dir() / "queue.jsonl"


def default_telemetry_config() -> dict:
    """Return the default telemetry config."""
    return {
        "enabled": False,
        "install_id": None,
        "created_at": None,
        "updated_at": None,
        "prompt_shown": False,
        "seen_commands": [],
    }


def load_telemetry_config() -> dict:
    """Load telemetry config from disk, merging with defaults."""
    config = default_telemetry_config()
    path = telemetry_config_path()
    if not path.exists():
        return config
    loaded = json.loads(path.read_text(encoding="utf-8"))
    config.update(loaded)
    config["seen_commands"] = list(config.get("seen_commands", []))
    return config


def save_telemetry_config(config: dict) -> Path:
    """Persist telemetry config to disk."""
    path = telemetry_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def telemetry_enabled() -> bool:
    """Return whether telemetry is enabled, respecting environment override."""
    if os.environ.get("DEPSLY_TELEMETRY") == "0":
        return False
    return bool(load_telemetry_config()["enabled"])


def enable_telemetry() -> dict:
    """Enable telemetry and return the updated config."""
    config = load_telemetry_config()
    now = scan_timestamp()
    config["enabled"] = True
    config["prompt_shown"] = True
    config["updated_at"] = now
    if config.get("created_at") is None:
        config["created_at"] = now
    if not config.get("install_id"):
        config["install_id"] = uuid.uuid4().hex
    save_telemetry_config(config)
    return config


def disable_telemetry() -> dict:
    """Disable telemetry and return the updated config."""
    config = load_telemetry_config()
    config["enabled"] = False
    config["updated_at"] = scan_timestamp()
    save_telemetry_config(config)
    return config


def delete_local_telemetry_data() -> bool:
    """Delete queued unsent telemetry data stored locally."""
    queue_path = telemetry_queue_path()
    if not queue_path.exists():
        return False
    queue_path.unlink()
    return True


def duration_bucket(duration_seconds: float) -> str:
    """Bucket a command runtime into one coarse telemetry range."""
    if duration_seconds < 1:
        return "<1s"
    if duration_seconds < 5:
        return "1-5s"
    if duration_seconds < 30:
        return "5-30s"
    return "30s+"


def graph_size_bucket(total_nodes: int | None) -> str:
    """Bucket a graph size into one coarse telemetry range."""
    if total_nodes is None:
        return "unknown"
    if total_nodes <= 50:
        return "0-50"
    if total_nodes <= 200:
        return "51-200"
    if total_nodes <= 1000:
        return "201-1000"
    return "1000+"


def platform_family() -> str:
    """Return a coarse OS family label."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return "unknown"


def python_version() -> str:
    """Return the current major.minor Python version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _coarse_options(options: dict | None) -> dict:
    """Keep only coarse boolean option fields approved for telemetry."""
    if not options:
        return {}
    approved = ("include_dev", "json", "open_browser")
    return {
        key: bool(options[key])
        for key in approved
        if key in options
    }


def _mark_first_use(command: str) -> bool:
    """Mark a command as seen and return whether this is its first local use."""
    config = load_telemetry_config()
    seen_commands = set(config.get("seen_commands", []))
    first_use = command not in seen_commands
    if first_use:
        seen_commands.add(command)
        config["seen_commands"] = sorted(seen_commands)
        config["updated_at"] = scan_timestamp()
        save_telemetry_config(config)
    return first_use


def failure_category_for_exception(exc: Exception) -> str:
    """Map an exception into a small fixed telemetry failure taxonomy."""
    message = str(exc).lower()
    if "unsupported lockfileversion" in message:
        return "unsupported_lockfile"
    if "file not found" in message:
        return "missing_file"
    if "cannot parse" in message or "jsondecodeerror" in type(exc).__name__.lower():
        return "parse_error"
    return "internal_error"


def build_telemetry_event(
    *,
    command: str,
    started_at: float,
    success: bool,
    options: dict | None = None,
    total_nodes: int | None = None,
    failure_category: str | None = None,
) -> dict:
    """Build one coarse command-level telemetry event."""
    config = load_telemetry_config()
    event = {
        "event": "cli.command.completed",
        "schema_version": "1",
        "install_id": config.get("install_id"),
        "session_id": uuid.uuid4().hex,
        "timestamp": scan_timestamp(),
        "depsly_version": TOOL_VERSION,
        "platform": platform_family(),
        "python_version": python_version(),
        "command": command,
        "first_use_on_install": _mark_first_use(command),
        "options": _coarse_options(options),
        "result": {
            "success": success,
            "duration_bucket": duration_bucket(perf_counter() - started_at),
            "graph_size_bucket": graph_size_bucket(total_nodes),
        },
    }
    if not success and failure_category is not None:
        event["result"]["failure_category"] = failure_category
    return event


def queue_telemetry_event(event: dict) -> Path:
    """Append a telemetry event to the local queue."""
    path = telemetry_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def load_queued_telemetry_events() -> list[dict]:
    """Load all queued telemetry events from disk."""
    path = telemetry_queue_path()
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sample_telemetry_event() -> dict:
    """Return a representative sample event for user inspection."""
    return {
        "event": "cli.command.completed",
        "schema_version": "1",
        "command": "recommend",
        "result": {
            "success": True,
            "duration_bucket": "1-5s",
            "graph_size_bucket": "201-1000",
        },
    }


def telemetry_endpoint() -> str | None:
    """Return the resolved telemetry ingestion endpoint."""
    value = os.environ.get("DEPSLY_TELEMETRY_URL", "").strip()
    return value or DEFAULT_TELEMETRY_URL


def telemetry_batch_size() -> int:
    """Return the maximum number of events to send in one batch."""
    raw = os.environ.get("DEPSLY_TELEMETRY_BATCH_SIZE", "50").strip()
    try:
        value = int(raw)
    except ValueError:
        return 50
    return max(1, min(value, 100))


def telemetry_timeout_seconds() -> float:
    """Return the telemetry upload timeout in seconds."""
    raw = os.environ.get("DEPSLY_TELEMETRY_TIMEOUT_SECONDS", "2.0").strip()
    try:
        value = float(raw)
    except ValueError:
        return 2.0
    return max(0.1, min(value, 10.0))


def telemetry_auto_flush_threshold() -> int:
    """Return the queue size that triggers best-effort automatic flush."""
    raw = os.environ.get("DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD", "20").strip()
    try:
        value = int(raw)
    except ValueError:
        return 20
    return max(1, min(value, 1000))


def build_telemetry_batch_payload(events: list[dict]) -> dict:
    """Wrap queued telemetry events in the batch envelope sent to the server."""
    return {
        "schema_version": "1",
        "sent_at": scan_timestamp(),
        "events": events,
    }


def queued_telemetry_event_count() -> int:
    """Return the number of queued local telemetry events."""
    return len(load_queued_telemetry_events())


def should_auto_flush_telemetry() -> bool:
    """Return whether the current queue size should trigger automatic flush."""
    return queued_telemetry_event_count() >= telemetry_auto_flush_threshold()


def _write_queued_telemetry_events(events: list[dict]) -> Path:
    """Rewrite the queue file with the provided remaining events."""
    path = telemetry_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        if path.exists():
            path.unlink()
        return path
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def _post_telemetry_batch(*, url: str, payload: dict, timeout_seconds: float) -> dict:
    """Send one telemetry batch via HTTPS and return the decoded JSON response."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"depsly/{TOOL_VERSION}",
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8").strip()
    if not body:
        return {}
    return json.loads(body)


def flush_queued_telemetry_events() -> dict:
    """Send one batch of queued telemetry events if transport is configured."""
    endpoint = telemetry_endpoint()
    if endpoint is None:
        return {
            "attempted": False,
            "sent": 0,
            "remaining": queued_telemetry_event_count(),
            "reason": "not_configured",
        }

    queued = load_queued_telemetry_events()
    if not queued:
        return {
            "attempted": False,
            "sent": 0,
            "remaining": 0,
            "reason": "empty_queue",
        }

    batch_size = telemetry_batch_size()
    batch = queued[:batch_size]
    payload = build_telemetry_batch_payload(batch)
    try:
        _post_telemetry_batch(
            url=endpoint,
            payload=payload,
            timeout_seconds=telemetry_timeout_seconds(),
        )
    except (urllib_error.URLError, TimeoutError, json.JSONDecodeError):
        return {
            "attempted": True,
            "sent": 0,
            "remaining": len(queued),
            "reason": "send_failed",
        }

    remaining_events = queued[len(batch):]
    _write_queued_telemetry_events(remaining_events)
    return {
        "attempted": True,
        "sent": len(batch),
        "remaining": len(remaining_events),
        "reason": "sent",
    }


def maybe_auto_flush_telemetry() -> dict:
    """Best-effort automatic flush when the queue reaches the configured threshold."""
    if not should_auto_flush_telemetry():
        return {
            "attempted": False,
            "sent": 0,
            "remaining": queued_telemetry_event_count(),
            "reason": "below_threshold",
        }
    return flush_queued_telemetry_events()
