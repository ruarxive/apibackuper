---
title: "update"
description: "apibackuper update command reference"
---
# `update`

Fetches changed records using the last successful state and the configured update mode.

```bash
apibackuper update
apibackuper update --resume -p myproject
apibackuper update --dry-run -p myproject
```

**Key options:**

- `--resume` — continue the interrupted update within its existing generation
- `--dry-run` — print the update plan and local estimate without HTTP requests
- `--projectpath` / `-p`
- `--verbose` / `-v`

## Selecting changed records

`project.update_mode` selects `by_change_key` or `by_timestamp`. If omitted, it
defaults to `by_change_key` when `data.change_key` is configured, and otherwise
to `by_timestamp`. In change-key mode, configure `data.change_key` and
`params.change_key_param`; the last successful change key is sent with the next
update request.

For `by_timestamp`, configure `params.update_since_param`. The next request uses
the stored `update_watermark`, captured at the start of the last successful run.
Legacy state without this field falls back to `last_run_end`. Using the run's
start time allows a later update to collect changes that occurred while the
previous backup was downloading.

`custom_script` is a reserved configuration value; running an update with it
raises an error. Use an API-supported change-key or timestamp filter.

## Retained generations and export

Each update writes a new generation under
`runs/<chronological-id>/page_N.json`, preserving earlier pages even when the API
returns new data for the same page number. `update --resume` keeps the same
generation and reuses pages already saved for that run.

Export emits all retained historical records from the original flat pages and
every update generation. It does not deduplicate records by object identifier
or produce a latest-object snapshot. The same object can appear more than once
when it was returned by multiple updates. Legacy archives with flat
`page_N.json` names remain readable alongside the generation layout.

## Failure and recovery

Failed or incomplete updates return a nonzero exit status and leave the last
successful state and update watermark unchanged. Pages already saved remain
available for `update --resume`; the checkpoint never advances beyond an
unresolved gap. Legacy checkpoints without `next_page` safely replay their last
recorded page.

For ZIP storage, a `.journal` sidecar directory holds durable pages until close
compacts them into the archive. Resume reads it automatically. Keep it beside
its corresponding ZIP or `.partial` archive, together with the checkpoint,
when recovering or moving an interrupted backup. A pending publication intent
can be completed from saved data without issuing new HTTP requests.

Fresh full backups use a sibling `.partial` staging path and keep the previous
complete archive until successful publication; see [`run`](/commands/run).
See [incremental and update](/use-cases/incremental-and-update) for configuration examples.
