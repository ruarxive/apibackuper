---
title: "REST API backup"
description: "Build, verify and recover a complete paginated GET backup, then adapt it to a real API"
---
# REST API backup

Use this workflow when an endpoint returns a collection in numbered pages or
offset/limit batches. The result is a local archive of response pages and a
JSON Lines export that can be checked independently of the API.

The worked example uses the repository's local server: **five records, two
records per page, three saved pages**. After trying it, replace the URL and
field names with those of your service. For POST request bodies, use the
[POST walkthrough](/use-cases/post-api-backup).

## 1. Identify the API contract

Before configuring a real endpoint, inspect a successful response and its
request parameters. Write down:

| Question | Example | Configuration |
|----------|---------|---------------|
| Where is the collection? | `{"items": [...]}` | `data.data_key: items` |
| Where is the total record count? | `{"total": 5}` | `data.total_number_key: total` |
| Which parameter selects the page? | `page=1` | `params.page_number_param: page` |
| Which parameter sets the page size? | `per_page=2` | `params.page_size_param: per_page` |
| How many records does the server actually return? | Two on a full page | `params.page_size_limit: 2` |
| Which field identifies a record? | `id` | `data.item_key: id` |

The record ID is useful for verification; configuring `item_key` does not
deduplicate pages. Also confirm the service supports a stable ordering and
whether the total covers the filtered collection or the entire database.

## 2. Start the local API and create a project

Install apibackuper from a repository checkout as described in
[installation](/getting-started/installation). From the repository root, keep
this server running in one terminal:

```bash
python examples/local-demo/server.py
```

In a second terminal with the same Python environment active:

```bash
apibackuper create rest-demo
cd rest-demo
```

`create` writes a minimal legacy INI scaffold. Save the following as
`apibackuper.yaml` in `rest-demo`; YAML takes precedence over that scaffold:

```yaml config
settings:
  name: rest-demo
project:
  url: http://127.0.0.1:8765/items
  http_mode: GET
  iterate_by: page
  default_delay: 0
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 2
data:
  data_key: items
  total_number_key: total
  item_key: id
storage:
  storage_type: zip
```

The first request is `GET /items?page=1&per_page=2`. Its response is:

```json
{
  "total": 5,
  "items": [
    {"id": 1, "title": "Item 1", "updated_at": "2026-01-01"},
    {"id": 2, "title": "Item 2", "updated_at": "2026-01-02"}
  ]
}
```

`data_key` is relative to the response root. For a root array, omit it. For
`{"result":{"items":[...]}}`, use `result.items`. See
[project and data](/configuration/project-and-data) for extraction rules.

## 3. Validate, preview and collect

Run inside `rest-demo`:

```bash doc-test
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full
apibackuper info --json
apibackuper export items.jsonl
```

Validation and dry-run are offline. Estimate makes a live sample request and
should report 5 records and 3 requests for this fixture; timings and byte sizes
vary. `run full` performs the backup, and export reads saved data locally.

After successful publication, the relevant files are:

```text
rest-demo/
  apibackuper.yaml
  apibackuper_state.json
  apibackuper_checkpoint.json
  storage/
    storage.zip
  items.jsonl
```

The ZIP contains raw JSON page payloads, including their `total` and `items`
wrappers. The export extracts the records, one JSON object per line.

## 4. Check the result

Save this as `check.py` in the project directory and run `python check.py`:

```python doc-test
import json
from pathlib import Path
from zipfile import ZipFile

records = [json.loads(line) for line in Path("items.jsonl").read_text().splitlines()]
assert len(records) == 5
assert sorted(record["id"] for record in records) == [1, 2, 3, 4, 5]
with ZipFile("storage/storage.zip") as archive:
    assert set(archive.namelist()) == {"page_1.json", "page_2.json", "page_3.json"}
    last_page = json.loads(archive.read("page_3.json"))
    assert [record["id"] for record in last_page["items"]] == [5]
print("Verified: 5 records, 5 distinct IDs, 3 pages")
```

For a real collection, compare exported record and distinct-ID counts with a
known source count, and inspect boundary IDs and representative nested fields.
A successful command confirms collection under the configured rules; a changing
API can still move objects between pages. See
[backup completeness](/getting-started/data-integrity).

## 5. Adapt the request to a real service

Change the URL, extraction paths and pagination names together. Add a
`params.json` beside the YAML for fixed API-specific query parameters, such as:

```json
{"status": "active", "sort": "id", "direction": "asc"}
```

These names are illustrative; use only parameters supported by your API. The
same fixed filter and ordering are copied into every request, while configured
pagination values change per page. Headers belong in `headers.json`, and
credentials belong in [auth](/configuration/auth).

For an offset/limit API, replace the `project` and `params` sections with:

```yaml
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: skip
params:
  count_skip_param: offset
  page_size_param: limit
  page_size_limit: 100
```

This sends offsets 0, 100, 200 and so on. Set the page size to the size the
server actually returns: requesting 100 while the service caps responses at
50 can trigger an early stop. Without a usable total, a short/empty page ends
collection, subject to the fallback page boundary. Native zero-based page
numbers, cursor tokens and next-link traversal require a different collection
approach. See [pagination](/configuration/pagination).

## Recover and repeat

If a full run fails or is interrupted, preserve the checkpoint,
`storage/storage.zip.partial` and any matching `.journal` directory, then use:

```bash
apibackuper run full --resume
```

Resume needs a valid checkpoint for the same mode and storage path. Keep the
endpoint, filters and sorting fixed while recovering. A failed full run keeps
the previous published archive; `info` may therefore describe an earlier
successful run. Check the latest command's exit status and logs as well.

A fresh `run full` replaces the published backup only after success. Preserve a
verified copy before replacing a snapshot you need to retain. To keep changed
records over time, configure [updates](/use-cases/incremental-and-update).

| Unexpected result | First check |
|-------------------|-------------|
| Only one page saved | Pagination parameter name and actual returned page size |
| Missing records or repeated IDs | Stable sorting, changing source data, and filtered total semantics |
| Response extraction fails | `data_key` path and whether an API error was returned inside HTTP 200 |
| Resume reports no checkpoint | Correct project directory, mode, checkpoint and storage location |
| Export shows different fields | An existing unnamed follow details archive can be selected for export |

Repository projects such as `hhemployers`, `budgettofk`, `budgetreg` and
`subsidies` provide additional request shapes. Their external endpoints depend
on the upstream service; see [Examples](/examples/).
