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
| `state_file` | Persistent run state |
| `checkpoint_file` | Resume checkpoint path |
| `checkpoint_interval_pages` | Pages between checkpoint writes |

## project

| Field | Purpose |
|-------|---------|
| `description` | Human-readable purpose |
| `url` | API endpoint |
| `http_mode` | `GET` or `POST` |
| `work_modes` | Comma-separated `full`, `incremental`, `update` |
| `iterate_by` | `page`, `skip`, or `range` |
| `resp_type` | `json` (default), `xml`, or `html` |
| `update_mode` | `by_change_key`, `by_timestamp`, or `custom_script` |
| `detect` | Auto-detect keys during run |
| `default_delay` / `retry_delay` / `retry_count` | Simple delay and retry |
| `force_retry` | Retry on errors |

## data

| Field | Purpose |
|-------|---------|
| `data_key` | Path to the array of records |
| `total_number_key` | Path to the total record count |
| `pages_number_key` | Path to the total page count |
| `item_key` | Unique id (comma-separated for composites) |
| `change_key` | Field that indicates a record changed |

Nested keys use `settings.splitter` (default `.`), for example
`result.results` or `СтатусАккредитации.ДействуетС`.
