# Telemetry Implementation Plan

This plan is intentionally privacy-first. The goal is to learn which Depsly
commands are used, how often they succeed, and where performance pain shows up,
without collecting project contents.

## Goals

- measure command usage share
- measure success and failure rates
- measure rough runtime distribution
- measure rough graph-size distribution
- keep telemetry optional, anonymous, and easy to disable

## Non-Goals

- collecting lockfile contents
- collecting package names or package keys
- collecting dependency graph data
- collecting file paths or repository identity
- building user-level behavioral profiles

## CLI Surface

Add a `telemetry` command group:

- `depsly telemetry status`
- `depsly telemetry enable`
- `depsly telemetry disable`
- `depsly telemetry show-sample`
- `depsly telemetry delete-data`

Optional later:

- `depsly telemetry export-local`

## Local Storage

Store local telemetry state under the Depsly home directory, for example:

- `~/.depsly/telemetry/config.json`
- `~/.depsly/telemetry/queue.jsonl`

Suggested config fields:

- `enabled`
- `install_id`
- `created_at`
- `updated_at`
- `prompt_shown`

## Event Lifecycle

1. Command starts.
2. Record start time in memory only.
3. Command finishes.
4. Build one coarse event.
5. If telemetry is enabled, append it to the local queue.
6. Attempt asynchronous or deferred batch delivery.
7. On success, delete delivered events from the queue.
8. On failure, keep queued events until queue limits are reached.

## Instrumentation Scope

Instrument these commands first:

- `analyze`
- `recommend`
- `trace`
- `simulate-remove`
- `save-scan`
- `list-scans`
- `compare-scans`
- `graph-html`

Do not instrument internals at package level.

## Bucketing

Convert sensitive or high-cardinality values into buckets before writing the
event to disk.

### Duration

- `<1s`
- `1-5s`
- `5-30s`
- `30s+`

### Graph Size

- `unknown`
- `0-50`
- `51-200`
- `201-1000`
- `1000+`

### Failures

Map exceptions into a small fixed taxonomy:

- `parse_error`
- `unsupported_lockfile`
- `missing_file`
- `internal_error`

## Networking

Requirements:

- never block the main CLI flow on telemetry delivery
- use short timeouts
- batch multiple events
- tolerate offline environments
- silently no-op when disabled

If telemetry transport is not available yet, phase 1 can stop at local queueing
and sample inspection.

## Phased Rollout

### Phase 1

- add config file support
- add telemetry CLI commands
- generate sample events
- queue events locally only

### Phase 2

- instrument core commands
- add batch upload transport
- add queue pruning and retry logic

### Phase 3

- add basic aggregate reporting on the server side
- publish exact retention windows
- review whether any field should be removed or tightened

## Trust Safeguards

- telemetry remains off until explicitly enabled
- environment variable override can force disable
- all fields are documented in `TELEMETRY.md`
- sample event view is built into the CLI
- local queued events can be deleted by the user

## Suggested Acceptance Criteria

- user can enable and disable telemetry without editing config files
- telemetry adds negligible latency to normal CLI usage
- no event contains package names, file paths, or lockfile contents
- queue survives process restarts
- failed delivery does not break command execution
- a sample event is easy to inspect locally
