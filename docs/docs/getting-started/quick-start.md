---
title: "Quick Start"
description: "Back up five known records from a local API and verify the export"
---
# Quick Start

This walkthrough backs up **five fixed records in three pages** from a local
API. It needs Python 3.10+ and a repository checkout. After installation, all
API traffic stays on `127.0.0.1`; no API account or token is needed.

## 1. Install and start the API

From a terminal:

```bash
git clone https://github.com/ruarxive/apibackuper.git
cd apibackuper
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/local-demo/server.py
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
Leave this terminal running. The server prints
`Demo API: http://127.0.0.1:8765/items`.
If the port is occupied, use `--port 8766` and change the copied YAML URL.

## 2. Prepare the project

Open a second terminal in the repository root, activate the same environment,
then copy the example:

```bash
cp -R examples/local-demo demo
cd demo
```

In PowerShell, use `Copy-Item -Recurse examples/local-demo demo` for the copy.
The copied `apibackuper.yaml` contains:

```yaml config
settings:
  name: local-demo
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

The first request is `GET /items?page=1&per_page=2`. It returns:

```json
{"total": 5, "items": [
  {"id": 1, "title": "Item 1", "updated_at": "2026-01-01"},
  {"id": 2, "title": "Item 2", "updated_at": "2026-01-02"}
]}
```

## 3. Validate, preview and estimate

Run these commands inside `demo`:

```bash doc-test
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
```

Validation and dry-run work offline. Estimate contacts the local server and
reports 5 records, 2 records per request and 3 requests. Size and time depend
on the machine. Dry-run can report an unknown count before the first backup.

## 4. Back up and export

```bash doc-test
apibackuper run full --verbose
apibackuper info --json
apibackuper export items.jsonl
apibackuper export selected.jsonl --fields id,title --where "id >= 3"
```

A successful run publishes `storage/storage.zip`. Its members are
`page_1.json`, `page_2.json` and `page_3.json`; the last page has only ID 5.
The export contains one JSON object per line. Check the result in Python
(save this as `check.py` and run `python check.py`):

```python doc-test
import json
from pathlib import Path
from zipfile import ZipFile

records = [json.loads(line) for line in Path("items.jsonl").read_text().splitlines()]
assert sorted(row["id"] for row in records) == [1, 2, 3, 4, 5]
assert len(records) == 5
selected = [json.loads(line) for line in Path("selected.jsonl").read_text().splitlines()]
assert sorted(row["id"] for row in selected) == [3, 4, 5]
assert all(set(row) == {"id", "title"} for row in selected)
with ZipFile("storage/storage.zip") as archive:
    assert sorted(archive.namelist()) == ["page_1.json", "page_2.json", "page_3.json"]
print("Verified: 5 records, 3 pages, 3 filtered records")
```

Stop the API server with Ctrl-C when finished. Recover an interrupted backup
with `apibackuper run full --resume` while the server is running.

## Next steps

- [Real POST API example](/use-cases/post-api-backup) — the E-Trust walkthrough
- [HTTP request files](/configuration/http-requests) — headers, filters and POST bodies
- [Pagination](/configuration/pagination) — page, skip and range boundaries
- [Backup completeness](/getting-started/data-integrity) — what a successful run guarantees
- [Python API](/development/python-api) — use this project from a script
- [Cookbook](/getting-started/cookbook) — choose another task

The marked walkthrough commands and Python checks are executed in CI against
this server. External API examples are configuration samples; their availability
depends on the upstream service.
