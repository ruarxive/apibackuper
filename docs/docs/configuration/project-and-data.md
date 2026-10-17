---
title: "Project and data"
description: "settings, project, and data configuration sections"
---
# Project and data

## settings

| Field | Purpose |
|-------|---------|
| `name` | Short project name |
| `initialized` | Whether the project has been initialized |
| `splitter` | Nested-field splitter (default `.`). Change when `.` is part of a key, for example OData `@odata.count` |
| `logfile` | Log file name (default `apibackuper.log`) |
| `state_file` | Last successful run state; default `apibackuper_state.json` in the project directory |
| `checkpoint_file` | Resume checkpoint; default `apibackuper_checkpoint.json` in the project directory |
| `checkpoint_interval_pages` | Periodic save interval; 0 disables periodic saves, while lifecycle checkpoints are still written |

Explicit state/checkpoint paths are used as written. Relative overrides resolve
from the working directory; use absolute paths when invoking the project with `-p`.

## project

| Field | Purpose |
|-------|---------|
| `description` | Human-readable purpose |
| `url` | API endpoint |
| `http_mode` | `GET` or `POST` |
| `work_modes` | Comma-separated `full`, `incremental`, `update` |
| `iterate_by` | `page`, `skip`, or `range` |
| `resp_type` | `json` (default), `xml`, or `html` |
| `update_mode` | `by_change_key` or `by_timestamp`; `custom_script` is reserved and execution rejects it |
| `detect` | Auto-detect keys during run |
| `default_delay` / `retry_delay` / `retry_count` | Delay in seconds (fractional `default_delay` supported), plus fallback retry delay and budget |
| `force_retry` | Legacy option; configure the active policy with `request.retry` |

## data

| Field | Purpose |
|-------|---------|
| `data_key` | Path to the records; omit for a root array or single object |
| `total_number_key` | Path to the total record count |
| `pages_number_key` | Path to the total page count |
| `item_key` | Unique id (comma-separated for composites) |
| `change_key` | Field that indicates a record changed |

Nested keys use `settings.splitter` (default `.`), for example
`result.results` or `СтатусАккредитации.ДействуетС`.

`item_key` does not remove duplicate IDs during backup or export. Updates
retain historical generations; see [incremental and update](/use-cases/incremental-and-update).
