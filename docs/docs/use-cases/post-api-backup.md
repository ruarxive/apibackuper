---
title: "POST API: E-Trust"
description: "Verify a paginated POST backup locally, then map the workflow to the E-Trust request body"
---
# POST API: E-Trust

Some read-only APIs accept a JSON search body instead of URL query parameters.
Use `http_mode: POST`, put the fixed request body in `params.json`, and configure
which body fields apibackuper changes for pagination.

First verify that workflow against the local demo, then adapt it to the E-Trust
certificate-authority list. E-Trust is an external, undocumented API example;
its endpoint, response shape and access requirements can change.

## 1. Reproduce the POST workflow locally

With an installed repository checkout, start the server from the repository
root in one terminal:

```bash
python examples/local-demo/server.py
```

Keep it running. In a second terminal with the same environment active:

```bash
apibackuper create post-demo
cd post-demo
```

Save this as `apibackuper.yaml`, which takes precedence over the generated INI:

```yaml config
settings:
  name: post-demo
project:
  url: http://127.0.0.1:8765/items
  http_mode: POST
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

Save the request body in `params.json` in the same directory:

```json request-body
{"page": 1, "per_page": 2}
```

The server accepts this JSON body at `POST /items` and returns the same five
records as the GET demo. The first two records are returned on page 1, the next
two on page 2, and ID 5 on page 3.

```bash doc-test
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full
apibackuper info --json
apibackuper export post-items.jsonl
```

Validation/dry-run are offline; estimate and run contact the local server.
After the commands succeed, save this as `check.py` and run `python check.py`:

```python doc-test
import json
from pathlib import Path
from zipfile import ZipFile

records = [json.loads(line) for line in Path("post-items.jsonl").read_text().splitlines()]
assert len(records) == 5
assert sorted(record["id"] for record in records) == [1, 2, 3, 4, 5]
with ZipFile("storage/storage.zip") as archive:
    assert len(archive.namelist()) == 3
    assert json.loads(archive.read("page_1.json"))["total"] == 5
print("Verified POST backup: 5 records in 3 pages")
```

This local example tests POST collection without depending on an external
service. It does not implement E-Trust's filters or response fields.

## 2. Understand how the body is built

`params.json` holds **values**, while the YAML `params` section identifies the
**names of pagination fields**. Before each request, apibackuper copies the
base body and overwrites the configured page and page-size fields:

| Request | Body for the local example |
|---------|----------------------------|
| Page 1 | `{"page":1,"per_page":2}` |
| Page 2 | `{"page":2,"per_page":2}` |
| Page 3 | `{"page":3,"per_page":2}` |

An initial `page` value in the file does not fix every request to that page.
Other body fields stay in the copied request. JSON `null`, booleans, arrays and
nested objects retain their JSON types in the normal POST path. Use valid JSON,
not YAML, comments or a form-encoded string.

Nested page fields can use dotted names, for example
`page_number_param: paging.page`, with the matching nested object in the body.
For POST APIs that put some values in the URL, see
[HTTP requests](/configuration/http-requests) for `query_mode` and
`url_params.json`; the normal POST mode sends `params.json` as JSON.

Use POST collection only for read/search operations where replaying a request
is acceptable. Retries and resume can issue a request again.

## 3. Create a separate E-Trust project

From a parent directory, create another project rather than changing the
source of an interrupted local backup:

```bash
apibackuper create etrust
cd etrust
```

Save the following as `apibackuper.yaml`:

```yaml config
settings:
  name: etrust
project:
  description: E-Trust certificate-authority list
  url: https://e-trust.gosuslugi.ru/app/scc/portal/api/v1/portal/ca/list
  http_mode: POST
  iterate_by: page
params:
  page_size_param: recordsOnPage
  page_size_limit: 100
  page_number_param: page
data:
  total_number_key: total
  data_key: data
  item_key: РеестровыйНомер
storage:
  storage_type: zip
request:
  connect_timeout: 30
  read_timeout: 120
  parallelism: 1
  verify_ssl: true
```

The corresponding `params.json` is:

```json
{
  "page": 1,
  "orderBy": "id",
  "ascending": false,
  "recordsOnPage": 100,
  "searchString": null,
  "cities": null,
  "software": null,
  "cryptToolClasses": null,
  "statuses": null
}
```

Check these fields against a currently successful request from the service
before collecting. Here `data` is the response collection, `total` is its
reported record count, and `РеестровыйНомер` is a record identifier. They are
not request-body fields. The configured page size must match a full response
page; the local demo's `items` and `per_page` names do not apply here.

If the service requires ordinary headers, add `headers.json`. If it requires
credentials, use [authentication](/configuration/auth) and obtain authorized
access separately. This example does not establish that the live endpoint is
currently public or available.

## 4. Validate the live contract and collect

```bash
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full --verbose
apibackuper info --json
apibackuper export etrust.jsonl
```

Check the live estimate's record count and full-page size before the full run.
For a count `N` with 100 records per page, the count-based request plan is
`ceil(N / 100)`. Reported times and byte estimates are samples, not guarantees;
there is no fixed expected E-Trust count in this walkthrough.

A successful full run publishes `storage/storage.zip`. Verify the exported row
count, distinct registry numbers and a sample of nested fields against the
source. If a full run is interrupted, preserve the checkpoint and `.partial`
archive, including any `.journal` sidecar, and recover with:

```bash
apibackuper run full --resume
```

Keep request filters, sorting and page size fixed during recovery. A failed
full run leaves the previously published archive available.

## 5. Export and decide how to refresh

```bash
apibackuper export etrust.jsonl.gz
apibackuper export etrust.jsonl.zst
apibackuper export etrust.parquet
```

gzip and zstd are available in the base installation. Parquet needs the
`recommended` extra; see [installation](/getting-started/installation). Export
runs locally and does not make another POST request.

A date-looking response field alone does not provide selective updates. For
example, `СтатусАккредитации.ДействуетС` may describe accreditation rather than
all record modifications. Configure `update` only after establishing a suitable
change field and an API-supported request filter. Otherwise, use verified full
snapshots and retain the ones you need. See
[incremental and update](/use-cases/incremental-and-update).

| Failure | Check |
|---------|-------|
| HTTP 400 or an application error body | Body types, accepted filter names, current endpoint contract |
| Every page repeats the same IDs | Correct page field, including its nested path, and server-side ordering |
| Only the first batch is saved | Actual full-page size and response `data_key`/total fields |
| HTTP 401/403 | Current credentials and permissions; offline validation cannot test access |
| Timeout or HTTP 429 | Active read/connect timeouts and the service's request quota |

See [export and storage](/use-cases/export-and-storage) for output checks and
[protected APIs](/use-cases/protected-apis) for a complete HTTP policy.
