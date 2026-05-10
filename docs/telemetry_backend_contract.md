# Telemetry Backend Contract

This document defines the minimal backend contract for Depsly telemetry
ingestion once remote collection is enabled.

## Goal

Accept small batches of anonymous command-level telemetry events over HTTPS,
validate them, store them briefly, and make aggregate reporting possible.

## Endpoint

`POST /v1/telemetry/events`

## Request Headers

- `Content-Type: application/json`
- `User-Agent: depsly/<version>`

Optional later:

- `X-Telemetry-Schema-Version: 1`

## Request Body

```json
{
  "schema_version": "1",
  "sent_at": "2026-05-10T20:00:00Z",
  "events": [
    {
      "event": "cli.command.completed",
      "schema_version": "1",
      "install_id": "b6d8d8ff9e26415ab5ac8ad8b5d8933e",
      "session_id": "3d09939eaabd412dbda5c7c993cba1b8",
      "timestamp": "2026-05-10T19:59:58Z",
      "depsly_version": "0.1.9",
      "platform": "macos",
      "python_version": "3.11",
      "command": "recommend",
      "first_use_on_install": false,
      "options": {
        "include_dev": true,
        "json": false
      },
      "result": {
        "success": true,
        "duration_bucket": "1-5s",
        "graph_size_bucket": "201-1000"
      }
    }
  ]
}
```

## Validation Rules

The ingestion service should:

- require top-level `schema_version`
- require `events` to be a non-empty array
- validate each event against the telemetry schema
- reject unknown schema major versions
- ignore unknown minor-compatible fields only if you explicitly choose to
- cap batch size

Suggested caps:

- max 100 events per request
- max request body 256 KB

## Response

Success:

```json
{
  "accepted": 12,
  "rejected": 0
}
```

Validation failure:

```json
{
  "accepted": 0,
  "rejected": 3,
  "errors": [
    "schema_version must be '1'",
    "command is required"
  ]
}
```

## HTTP Status Codes

- `202 Accepted`
  Accepted for processing.
- `400 Bad Request`
  Invalid payload shape.
- `413 Payload Too Large`
  Batch too large.
- `429 Too Many Requests`
  Client should back off.
- `500 Internal Server Error`
  Server-side failure.

## Privacy Requirements

The server should not enrich telemetry with:

- repository identity
- package names
- raw command arguments
- source file paths

If load balancers or edge systems log client IPs, retain them separately only
according to infrastructure policy, not as part of telemetry event payloads.

## Idempotency

The first version may accept duplicate events.

If deduplication becomes necessary later, add an event fingerprint based on:

- `install_id`
- `session_id`
- `timestamp`
- `command`

Do not require account-backed identity.

## Storage Strategy

Recommended flow:

1. Validate request.
2. Write raw accepted events to a staging table.
3. Run scheduled aggregation jobs.
4. Delete raw events after the retention window.

## Aggregates To Produce

- daily command counts
- daily success/failure counts by command
- daily duration bucket counts by command
- daily graph-size bucket counts by command
- daily option usage counts by command
- daily first-use counts by command

## Out Of Scope For V1

- user accounts
- authenticated telemetry identity
- per-project analytics
- cross-repo analysis
- real-time dashboards
