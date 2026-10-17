---
title: "Quick Start"
description: "Install from source, collect five local records in three pages and verify the archive and filtered export"
---
# Quick Start

This walkthrough backs up **five fixed records in three pages** from a local
API, then verifies the saved pages and two exports. It needs Python 3.10+ and
a repository checkout. After installation, API traffic stays on `127.0.0.1`;
no API account or token is needed.

Use two terminals: one keeps the demo API running, and the other runs the backup.
All project commands below run inside a copied `demo` directory. An installed
package alone does not include this checkout's example server.

## 1. Install the source and start the API

On Linux/macOS, in terminal A:

```bash
git clone https://github.com/ruarxive/apibackuper.git
cd apibackuper
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/local-demo/server.py
```

On Windows PowerShell, after cloning and entering the repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python examples/local-demo/server.py
```

If you already have this checkout and its environment, activate it and start
the server without cloning/installing again. See
[installation](/getting-started/installation) for interpreter and PATH checks.

Leave terminal A running. It prints:

```text
Demo API: http://127.0.0.1:8765/items
```

If port 8765 is occupied, start it with `--port 8766` and change `project.url`
in the copied configuration in the next step to use port 8766 as well.

## 2. Prepare a separate backup project

Open terminal B in the repository root. Activate the **same environment**, then
copy the fixture so the original example remains reusable:

```bash
source .venv/bin/activate
cp -R examples/local-demo demo
cd demo
```

On PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
Copy-Item -Recurse examples/local-demo demo
Set-Location demo
```

Use a fresh destination for the first attempt. If `demo` already contains a
previous collection, keep it and choose another destination name. The copied
`apibackuper.yaml` is a complete project configuration:

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

You do not need `create` here: copying the fixture already supplied the config.
`page_number_param` and `page_size_param` name API parameters; `page_size_limit`
supplies the number 2. `data_key` points at the record array, and
`total_number_key` points at the total count, both from the response root.
`item_key` documents the identifier; it does not deduplicate records.

## 3. Understand the requests and stopping point

The first request is `GET /items?page=1&per_page=2`. It returns:

```json
{"total": 5, "items": [
  {"id": 1, "title": "Item 1", "updated_at": "2026-01-01"},
  {"id": 2, "title": "Item 2", "updated_at": "2026-01-02"}
]}
```

| Page | Returned IDs | Saved object |
|------|--------------|--------------|
| 1 | 1, 2 | `page_1.json` |
| 2 | 3, 4 | `page_2.json` |
| 3 | 5 | `page_3.json` |

The total is 5 records, so `ceil(5 / 2)` gives three pages. The last page is
also shorter than the configured page size. Real APIs can use different names,
server-side caps and changing datasets; the local fixture keeps these fixed
so a wrong count is easy to spot.

## 4. Validate, preview and estimate

Run inside `demo` in terminal B:

```bash doc-test
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
```

| Command | Contacts the API? | What to check |
|---------|-------------------|---------------|
| `validate-config --strict` | No | Required sections, known fields/types, no warnings |
| `run full --dry-run` | No | Local plan points to the loopback URL, page pagination and ZIP storage |
| `estimate full` | Yes | 5 records, 2 records/request and 3 planned requests |

Before a saved run exists, dry-run can report an unknown count. A live estimate
uses a sample response; byte sizes and timing vary with your machine. Validation
alone cannot prove that the API server is running.

## 5. Back up, inspect and export

```bash doc-test
apibackuper run full --verbose
apibackuper info --json
apibackuper export items.jsonl
apibackuper export selected.jsonl --fields id,title --where "id >= 3"
```

A successful full run publishes `storage/storage.zip`. The ZIP retains the page
response wrappers; `items.jsonl` contains extracted objects, one per line.
`selected.jsonl` contains IDs 3, 4 and 5 with only `id` and `title`.

Selected fields from `info --json` should be:

```json
{
  "run": {"status": "success", "records_processed": 5, "last_page": 3},
  "statistics": {"storage": {"total_records": 5}}
}
```

The actual report has more fields. Relevant project artifacts are:

```text
demo/
  apibackuper.yaml
  apibackuper_state.json       # successful run and watermark information
  apibackuper_checkpoint.json  # recovery progress and completed status
  apibackuper.log
  storage/
    storage.zip
  items.jsonl
  selected.jsonl
```

The default log is in the process working directory, which is `demo` here.
Export does not make another API request. JSONL is not a single JSON array;
parse each non-empty line as an independent object.

## 6. Verify the actual output

Save this as `check.py` in `demo` and run `python check.py`:

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
    last_page = json.loads(archive.read("page_3.json"))
    assert [row["id"] for row in last_page["items"]] == [5]
print("Verified: 5 records, 3 pages, 3 filtered records")
```

This checks the collection, page boundary, filter and projection rather than
only trusting a success message. The marked CLI and Python blocks are executed
against this server in the documentation tests.

## Repeat or recover the walkthrough

Stop terminal A with Ctrl-C after a successful collection. You can still inspect
and export the saved data with the server stopped.

Running `run full` again with the server running creates a fresh staged backup
and replaces the published main archive after success. It does not append five
more records. If a full run fails or is interrupted, keep its checkpoint,
`.partial` archive and matching `.journal` sidecar, restart the API if needed,
and use:

```bash
apibackuper run full --resume
```

A completed checkpoint reports that the backup is already complete; omit
`--resume` for a new collection. `run continue` works on published pages and is
a different operation. See [basic usage](/getting-started/basic-usage).

| Problem | First check |
|---------|-------------|
| Connection refused | Terminal A is running; YAML port matches the server port |
| Command/module not found | Terminal B uses the same activated environment as installation |
| Configuration not found | Terminal B is inside the copied `demo` project |
| Wrong exported records | Fresh project, unchanged fixture keys/page size and correct output directory |
| Extra setup dependencies | No Parquet/aria2 dependency is needed for this walkthrough |

## Move from the fixture to your API

Use a new project for the real endpoint. Establish its request method,
pagination, extraction paths, scope and stable ordering before collecting.
The local server implements GET/POST pagination, but not authentication,
change filtering, detail endpoints or attachments.

- [REST API backup](/use-cases/rest-api-backup) maps an API response to configuration.
- [POST API walkthrough](/use-cases/post-api-backup) explains JSON request bodies.
- [Protected APIs](/use-cases/protected-apis) combines credentials and request quotas.
- [Backup completeness](/getting-started/data-integrity) explains verification limits.
- [Cookbook](/getting-started/cookbook) groups the next commands by task.
