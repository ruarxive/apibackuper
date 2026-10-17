---
title: "Project and data"
description: "Identify the dataset, extract nested records, configure update watermarks and locate state files"
---
# Project and data

These sections answer three questions: which dataset is this, what endpoint
returns it, and which parts of the response are records and metadata? Configure
these before adding follow or file downloads.

## Project identity and recovery files

```yaml
settings:
  name: catalog
  splitter: "."
  logfile: apibackuper.log
  checkpoint_interval_pages: 5
```

| Field | Required / default | Meaning |
|-------|--------------------|---------|
| `name` | Required string | Human-readable project identifier |
| `id` | Optional string | Metadata identifier; does not select the endpoint or storage |
| `initialized` | Optional boolean | Legacy scaffold metadata; setting it true does not fill in other sections |
| `splitter` | `.` | Separator for nested response/record field paths |
| `logfile` | `apibackuper.log` | Log path, relative to the working directory unless absolute |
| `state_file` | Project's `apibackuper_state.json` | Last successful run and update watermark |
| `checkpoint_file` | Project's `apibackuper_checkpoint.json` | Recovery mode, storage path and saved-page progress |
| `checkpoint_interval_pages` | `0` | Non-negative periodic checkpoint interval; 0 disables periodic saves |

Lifecycle checkpoints are written even when the interval is 0. State is
advanced only after a successful backup/update; incomplete collection keeps
the previous successful state. A checkpoint is recovery progress, not a
substitute for the archive or its ZIP journal.

Explicit state/checkpoint paths are used as written. For example,
`state_file: run-state.json` resolves from the process working directory even
when `-p /srv/catalog` points elsewhere. Use absolute overrides for scheduled
jobs, and keep one writer per project. See [recovery](/commands/run).

## Endpoint and response format

```yaml
project:
  description: Public item catalogue
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
  resp_type: json
  default_delay: 0.5
```

| Field | Required / default | How to choose |
|-------|--------------------|---------------|
| `url` | Required HTTP(S) endpoint | Use the list endpoint, with fixed filters in `params.json` |
| `http_mode` | Required `GET` or `POST` | POST sends JSON, not form data |
| `description` | Optional | Explain the source, scope and collection purpose |
| `iterate_by` | `page` | `page`, `skip` or `range`; match the API's pagination contract |
| `resp_type` | `json` | `json`, `xml` or `html`; HTML requires `code.postfetch` |
| `detect` | `false` | Infer selected keys from the initial JSON response; review suggestions first |
| `update_mode` | Conditional | Change-key mode when `data.change_key` exists, otherwise timestamp mode |
| `default_delay` | `0.5` seconds | Pause after a successful request; fractional seconds are supported |
| `retry_count` / `retry_delay` | `5` / `5` seconds | Fallbacks for the active request retry policy |
| `work_modes` | Optional string | Legacy descriptive declaration, not a command allowlist or update filter |
| `force_retry` | Legacy boolean | Use `request.retry` to configure retries |

`detect` cannot infer business semantics such as deletion handling, stable sort
order or the correct update filter. Use `apibackuper detect` to inspect
suggestions and then set explicit fields for repeatable production collection.

## Extract records from a wrapped response

For this response:

```json
{
  "result": {
    "count": 3,
    "pages": 2,
    "items": [
      {"id": 41, "metadata": {"modified": "2026-01-01"}},
      {"id": 42, "metadata": {"modified": "2026-01-02"}}
    ]
  }
}
```

use:

```yaml
data:
  data_key: result.items
  total_number_key: result.count
  pages_number_key: result.pages
  item_key: id
  change_key: metadata.modified
```

`data_key` starts from the response root. `change_key` starts from **each extracted
record**. `total_number_key` and `pages_number_key` start from the response root
and describe counts, not record IDs. If both counts are configured, a usable
record total takes precedence over page count.

`item_key` documents the record identifier in configuration. Current backup and
export paths do not build an index or deduplicate by it. Follow operations need
an explicit `follow.follow_item_key`; a comma-separated `data.item_key` string
does not construct a composite identifier automatically.

### Root arrays and single objects

Omit `data_key` for a root array:

```json
[{"id": 41}, {"id": 42}]
```

The required section can be empty: `data: {}`. A bare object such as `{"id":41}`
is treated as one record. If you configure a `data_key`, it must exist; the
backup fails on a missing configured path instead of treating the response as
an empty dataset. `estimate` still needs `total_number_key` even when a backup
can run without total metadata.

### Field names containing dots

When dots are literal field-name characters, choose a different response-path
separator. For `{"@odata.count":3,"value":[{"id":41}]}`:

```yaml
settings:
  splitter: "/"
data:
  data_key: value
  total_number_key: "@odata.count"
  item_key: id
```

A nested record path would then be `metadata/modified`. This separator also
controls export field lookup. Request-body pagination paths use their own dot
notation; changing `splitter` does not change JSON request construction.

These are object paths, not JSONPath: expressions such as `items[*].id` or
`items[0]` are not supported path syntax.

## XML and HTML responses

XML is parsed into a dictionary using `xmltodict`, then extracted with the same
`data_key` rules. Inspect the parsed shape, especially attributes, namespaces
and elements that appear once versus multiple times. For example, repeated
`<item>` elements under `<response><items>` can be selected by
`response.items.item`. XML text values are strings; a numeric-looking change
key does not automatically become an integer.

HTML needs a trusted extraction script with `process(content)` returning a
JSON-serializable list or wrapped object. Configure `code.postfetch` and a
`data_key` matching that return value. Non-JSON backups save the decoded result
as JSON pages, so exports use the resulting JSON shape. See [hooks and extraction](/configuration/hooks).

## Configure updates

For an API accepting `modified_after`, configure all three parts:

```yaml
project:
  update_mode: by_change_key
params:
  change_key_param: modified_after
data:
  change_key: metadata.modified
```

After a successful run, the largest observed record change key becomes the
next update's filter value. Values must be consistently typed and comparable.
Normalize timestamp strings and timezones; mixed numbers and strings can fail
comparison, and inconsistent date strings need not sort chronologically.

For an API accepting a time boundary independently of record fields:

```yaml
project:
  update_mode: by_timestamp
params:
  update_since_param: updated_since
```

The stored `update_watermark` is the prior successful run's start time in ISO
UTC form; legacy state can fall back to `last_run_end`. The API must accept
that representation and define whether boundary values are included. Without
a saved watermark or the matching request parameter, no update filter is sent.
Run and verify a full backup before relying on selective updates.

`custom_script` is reserved and rejected by update execution. Updates retain
historical generations, including repeated IDs; deletions are not inferred.
See [incremental and update](/use-cases/incremental-and-update) and
[backup completeness](/getting-started/data-integrity).

## Diagnose extraction problems

| Symptom | Check |
|---------|-------|
| Missing `data_key` error | Response wrapper, spelling, separator, and whether the API returned an error object |
| First page only | Pagination parameter configured for the chosen mode; actual returned page size |
| Wrong request estimate | `total_number_key` means records, `pages_number_key` means pages |
| Updates fetch the full dataset | Saved state, `update_mode`, matching request parameter, and API-side filter support |
| Repeated IDs after export | Expected retained history; `item_key` does not deduplicate |
