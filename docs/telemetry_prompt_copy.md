# Telemetry Prompt Copy

## First-Run Prompt

```text
Help improve Depsly

Depsly can share anonymous CLI usage data to help improve the product.
This includes things like which commands are used, whether they succeed,
and coarse performance and project-size buckets.

Depsly does not upload your lockfile, dependency graph, package names,
file paths, or command output.

Telemetry is optional and can be changed at any time.

Commands:
  depsly telemetry enable
  depsly telemetry disable
  depsly telemetry status
```

## Enable Confirmation

```text
Telemetry enabled.

Depsly will send anonymous command-level usage data to help improve the
product. It will not upload your lockfile, dependency graph, package names,
file paths, or command output.
```

## Disable Confirmation

```text
Telemetry disabled.

Depsly will stop sending telemetry. You can re-enable it later with:
  depsly telemetry enable
```

## Status Output

### Enabled

```text
Telemetry: enabled

Depsly is sending anonymous command-level usage data to help improve the
product.

Never collected: lockfile contents, dependency graph, package names,
file paths, and command output.
```

### Disabled

```text
Telemetry: disabled

Depsly is not sending telemetry.

Enable at any time with:
  depsly telemetry enable
```

## Show-Sample Output

```text
Sample telemetry event:

{
  "event": "cli.command.completed",
  "schema_version": "1",
  "command": "recommend",
  "result": {
    "success": true,
    "duration_bucket": "1-5s",
    "graph_size_bucket": "201-1000"
  }
}
```

## Delete-Data Confirmation

```text
Local telemetry data deleted.

Any queued unsent telemetry events stored by Depsly on this machine have been
removed.
```
