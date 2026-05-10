# Depsly Telemetry

Depsly telemetry is designed to help improve the product without collecting
project contents or sensitive dependency data.

## Principles

- opt-in, not opt-out
- anonymous by default
- minimal data collection
- no lockfile or package data
- easy disable and deletion
- documented schema and fields

## Purpose

Depsly telemetry exists to help improve the product while preserving trust in a
local-first CLI.

We use telemetry to understand:

- which CLI commands are used most
- which features are rarely used
- where commands fail
- rough performance by project-size bucket
- whether new features are being adopted

We do not use telemetry to inspect your codebase, dependency graph, lockfile
contents, package names, file paths, or package-level decisions.

## Default Behavior

Telemetry should be disabled by default until the user explicitly enables it.

Recommended user controls:

- `depsly telemetry status`
- `depsly telemetry enable`
- `depsly telemetry disable`
- `depsly telemetry show-sample`
- `depsly telemetry flush`
- `depsly telemetry delete-data`

Recommended environment override:

- `DEPSLY_TELEMETRY=0` disables telemetry regardless of saved local settings

Optional transport configuration:

- `DEPSLY_TELEMETRY_URL` overrides the built-in HTTPS ingestion endpoint
- `DEPSLY_TELEMETRY_BATCH_SIZE` sets the maximum events per flush batch
- `DEPSLY_TELEMETRY_TIMEOUT_SECONDS` sets the upload timeout
- `DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD` sets the queued-event threshold for best-effort automatic flush

## What We Collect

Depsly should collect only coarse command-level product analytics.

- anonymous install id
- ephemeral session id
- event timestamp
- Depsly version
- OS family
- Python version
- command name
- coarse option flags
- runtime bucket
- graph-size bucket
- success or failure
- coarse failure category
- whether the command is a first-time use on this installation

Example coarse option flags:

- `include_dev`
- `json`
- `open_browser`

Example runtime buckets:

- `<1s`
- `1-5s`
- `5-30s`
- `30s+`

Example graph-size buckets:

- `unknown`
- `0-50`
- `51-200`
- `201-1000`
- `1000+`

Example failure categories:

- `parse_error`
- `unsupported_lockfile`
- `missing_file`
- `internal_error`

## What We Never Collect

Depsly should never upload:

- lockfile contents
- dependency graph structure
- package names
- package keys
- file paths
- project names
- repository URLs
- recommendation output
- trace paths
- HTML report contents
- raw command arguments beyond coarse option booleans
- raw exception messages unless separately scrubbed and approved

## Anonymization Model

Telemetry should use a random local install id generated on the user machine and
stored in a local settings file under the Depsly home directory.

Recommended behavior:

- generate a random install id on first telemetry enable
- use a short-lived session id per CLI session or per process
- avoid deriving identity from machine name, repo state, or file paths
- optionally rotate install ids on a long interval if needed later

This provides enough continuity for product analytics without turning telemetry
into account-level tracking.

## Local Queue and Delivery

Telemetry should not block CLI execution.

Recommended approach:

- record events locally first
- queue them on disk under the Depsly home directory
- send them in small batches when explicitly flushed
- retry quietly
- cap queue size and discard oldest pending events if necessary

The CLI should continue to work normally if telemetry delivery fails.

Current transport behavior:

- events are always queued locally first
- Depsly includes a built-in telemetry endpoint for normal opt-in usage
- `DEPSLY_TELEMETRY_URL` exists for development or override scenarios
- best-effort remote delivery happens automatically once the queue reaches a threshold
- `depsly telemetry flush` attempts to send one batch
- failed sends leave the queue intact

## Retention

Recommended retention rules:

- keep local unsent telemetry for a short bounded period
- retain server-side raw events only as long as needed for aggregation
- prefer aggregated reporting over long-lived event storage

If exact retention windows change later, document them explicitly here.

## User Trust Requirements

Before telemetry is enabled, Depsly should clearly state:

- this is optional
- this helps improve the product
- what is collected
- what is never collected
- how to disable it

Recommended product framing:

> Help improve Depsly by sharing anonymous CLI usage data.

That purpose statement is narrow, honest, and easy to evaluate.

## Scope Guardrails

If future telemetry expansion is considered, do not add:

- repo identity
- package-level data
- lockfile excerpts
- recommendation bodies
- trace output
- cross-product identity joins

without a deliberate policy update and explicit user consent model review.
