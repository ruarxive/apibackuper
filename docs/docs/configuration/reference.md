---
title: "Configuration reference"
description: "Complete field list for apibackuper.yaml"
---
# Configuration reference

Canonical schema: `apibackuper/schemas/config_schema.json`. Required top-level
keys: `settings`, `project`, `params`, `data`, `storage`.

Validate with [`apibackuper validate-config`](/commands/validate-config).

## settings

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | **Required** |
| `initialized` | boolean | |
| `id` | string | |
| `splitter` | string | Default `.` |
| `logfile` | string | Default `apibackuper.log` |
| `state_file` | string | |
| `checkpoint_file` | string | |
| `checkpoint_interval_pages` | integer | ≥ 0 |

## project

| Field | Type | Notes |
|-------|------|-------|
| `url` | uri | **Required** |
| `http_mode` | `GET` \| `POST` | **Required** |
| `description` | string | |
| `work_modes` | string | `full,incremental,update` |
| `iterate_by` | `page` \| `skip` \| `range` | Default `page` |
| `resp_type` | `json` \| `xml` \| `html` | Default `json` |
| `update_mode` | `by_change_key` \| `by_timestamp` \| `custom_script` | |
| `detect` | boolean | |
| `default_delay` | integer | Seconds |
| `retry_delay` | integer | Seconds |
| `retry_count` | integer | |
| `force_retry` | boolean | |

## params

| Field | Type | Notes |
|-------|------|-------|
| `page_size_limit` | integer | **Required**, ≥ 1 |
| `start_page` | integer | Default 1 |
| `page_number_param` | string | |
| `page_size_param` | string | |
| `count_skip_param` | string | Skip/offset |
| `count_from_param` | string | Range start |
| `count_to_param` | string | Range end |
| `query_mode` | `query` \| `params` \| `mixed` | Default `query` |
| `force_flat_params` | boolean | |
| `change_key_param` | string | |
| `update_since_param` | string | |

## data

| Field | Type |
|-------|------|
| `data_key` | string |
| `total_number_key` | string |
| `pages_number_key` | string |
| `item_key` | string |
| `change_key` | string |

## storage

| Field | Type | Notes |
|-------|------|-------|
| `storage_type` | `zip` \| `filesystem` \| `sqlite` | **Required** |
| `storage_path` | string | Default `storage` |
| `compression` | boolean | |
| `compression_level` | integer | 0–9 |
| `max_file_size` | integer | Bytes |
| `split_files` | boolean | |

## Optional sections

Documented on their own pages: [auth](/configuration/auth),
[rate_limit / request](/configuration/rate-limiting-and-requests),
[follow](/configuration/follow), [files](/configuration/files),
[hooks](/configuration/hooks).

Also available: `error_handling`, `logging.level`
(`DEBUG` \| `INFO` \| `WARNING` \| `ERROR`).
