---
title: "Follow and files"
description: "Collect a list, fetch complete detail objects, archive attachments and verify each stage"
---
# Follow and files

Use this workflow when a list contains only summary fields and each record has
a separate detail endpoint. Download attachments after collecting those details.
The three commands are separate stages: `run` saves the list, `follow` saves
details, and `getfiles` downloads the referenced bytes.

This walkthrough describes an illustrative notices API, not the local demo
server. Replace `api.example.com` and `files.example.com` with your service's
endpoints. It assumes JSON detail responses, stable scalar IDs and attachment
URLs that the project is authorized to fetch.

## 1. Map the list, detail and file contracts

A list response at `GET /notices?page=1&per_page=100` might be:

```json
{
  "total": 2,
  "items": [
    {"id": 42, "title": "Road repair"},
    {"id": 43, "title": "Bridge inspection"}
  ]
}
```

For ID 42, `GET /notices/42` returns:

```json
{
  "notice": {
    "id": 42,
    "title": "Road repair",
    "description": "Full notice text",
    "document_url": "https://files.example.com/reports/42.pdf"
  }
}
```

There are three different extraction paths:

| Purpose | Setting | Value here |
|---------|---------|------------|
| Records in a list response | `data.data_key` | `items` |
| Identifier used to fetch a detail | `follow.follow_item_key` | `id`, relative to a list record |
| Object in the detail response | `follow.follow_data_key` | `notice` |
| Attachment reference in that object | `files.keys` | `document_url` |

## 2. Configure the complete pipeline

Save this as `apibackuper.yaml` in a dedicated project directory:

```yaml config
settings:
  name: notices-with-documents
project:
  url: https://api.example.com/notices
  http_mode: GET
  iterate_by: page
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
data:
  data_key: items
  total_number_key: total
  item_key: id
storage:
  storage_type: zip
follow:
  follow_mode: item
  follow_item_key: id
  follow_pattern: "https://api.example.com/notices/{id}"
  follow_http_mode: GET
  follow_data_key: notice
files:
  fetch_mode: prefix
  root_url: ""
  keys: document_url
  storage_mode: filepath
  file_storage_type: filesystem
  use_aria2: false
```

The unnamed follow rule writes `details.zip`. In item mode, `{id}` is filled
from the list record. There is no need for `follow_param` in this example: adding
it would also send an ID query/body parameter. `data.item_key` alone does not
configure follow; every record needs the separate `follow_item_key` value.

An empty file prefix preserves the complete `document_url`. Filesystem file
output makes each PDF easy to inspect; main storage remains ZIP because
`getfiles` currently requires it. Attachment output can instead use its own ZIP.

## 3. Collect and verify each stage

```bash
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper run full
apibackuper export list.jsonl
apibackuper follow full --dry-run
apibackuper follow full
apibackuper export details.jsonl
apibackuper getfiles
```

Run this sequence in a fresh project. Saving `list.jsonl` before the first follow
preserves a convenient list-level inventory. Once an unnamed `details.zip`
exists, normal export selects it and extracts `notice`; it no longer exports
the list records. A new main backup does not automatically refresh old details.

For the two-record example, the expected artifacts include:

```text
storage/
  storage.zip           # list pages, e.g. page_1.json
  details.zip           # 42.json and 43.json, with full detail responses
  allfiles.csv          # discovered attachment references, one per line
  files.list            # URLs recorded by the built-in downloader
  files/
    reports/
      42.pdf
      43.pdf
list.jsonl
details.jsonl
```

A single unnamed rule fetches one detail per distinct ID. Repeated IDs in
retained list history do not cause one detail fetch for every historical
version. Details represent the response at follow time, which may be later
than the list snapshot.

Save this as `check.py` and run it after the example pipeline:

```python
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

lists = [json.loads(line) for line in Path("list.jsonl").read_text().splitlines()]
details = [json.loads(line) for line in Path("details.jsonl").read_text().splitlines()]
assert {row["id"] for row in details} == {row["id"] for row in lists}
with ZipFile("storage/details.zip") as archive:
    assert {f"{row['id']}.json" for row in lists} == set(archive.namelist())
    assert json.loads(archive.read("42.json"))["notice"]["id"] == 42
pdf = Path("storage/files/reports/42.pdf").read_bytes()
assert pdf.startswith(b"%PDF-"), "Expected a PDF, not a login/error page"
print("Details:", len(details), "PDF 42 SHA-256:", hashlib.sha256(pdf).hexdigest())
```

The ID check detects missing details; a PDF signature is only a basic format
check. For a production collection, compare all expected attachment paths,
inspect representative documents and retain a checksum manifest. A URL inventory
or HTTP 200 alone does not prove that every document is valid.

## Detail URLs and fixed parameters

If list records already contain absolute detail URLs, replace the follow section:

```yaml
follow:
  follow_mode: url
  follow_item_key: id
  follow_url_key: links.detail
  follow_data_key: notice
```

For example, `links.detail` can contain
`https://api.example.com/notices/42`. URL mode uses that value directly; it does
not join a relative path to the main URL. Prefix mode can concatenate a literal
URL prefix with the extracted ID. Item-format substitutions are not automatically
URL-encoded, so choose IDs/paths compatible with the service's URL contract.

Put fixed detail parameters in `follow_params.json`, for example:

```json
{"includeDocuments": true}
```

That file is separate from main-list `params.json`. It is copied into each
detail request; the example parameter is useful only if the API supports it.
See [follow configuration](/configuration/follow) for paginated detail endpoints
and [files configuration](/configuration/files) for relative paths/document IDs.

## Recovery and later refreshes

| Interrupted stage | Recovery |
|-------------------|----------|
| List full backup | `apibackuper run full --resume` with its main checkpoint |
| Detail collection | `apibackuper follow continue` with saved details/staging |
| Built-in file downloads | Run `apibackuper getfiles` again; existing filenames are skipped |

Full detail runs stage `details.zip.partial` and publish after success. Keep any
matching `.journal` sidecar during recovery. `follow continue` reuses saved
objects, including full-run staging when present; it does not use the main
`--resume` checkpoint or refetch already saved detail names.

After the list is updated, use `follow full` to refresh existing IDs as well as
new ones. Verify details first, then remove **only the attachment discovery
cache** before rescanning for new links:

```python
from pathlib import Path

Path("storage/allfiles.csv").unlink(missing_ok=True)
```

Run `getfiles` again. Existing files remain, and existing filenames are skipped.
A changed document at the same path will not be refreshed by clearing the cache;
retain the previous output and arrange a fresh file collection when new bytes
must be archived. `filepath` ignores URL host/query when naming files, so different
URLs with the same path can collide. Signed URLs can also expire before download.

## Several detail endpoints or large downloads

`follow.rules` can collect independent endpoints such as profile and events
into `details_profile.zip` and `details_events.zip`. Every rule reads the
original list; there is no automatic multi-hop traversal. Named results are not
automatically combined or selected by `export`/`getfiles`. Prefer the single
unnamed rule above for this pipeline, or process named outputs explicitly via
[Python storage access](/development/python-api#direct-storage-access).

Built-in file downloads use the project's credentials and HTTP policy, and read
a response into memory before storing it. They do not resume partial file bytes.
Keep follow/file hosts within the credential scope. For external aria2 transfers,
installing `aria2p` is only one prerequisite: a running RPC service is required,
its policy is separate, and queueing URLs does not mean transfers have completed.
See [files configuration](/configuration/files#aria2-integration).

| Symptom | First check |
|---------|-------------|
| Missing-ID error | `follow_item_key` is present on every extracted list record |
| Details export is empty | `follow_data_key` matches the wrapper in detail responses |
| Missing `details.zip` during getfiles | Follow is configured; complete an unnamed detail collection first |
| No attachments after an update | Stale `allfiles.csv`, wrong field path, or expiring URLs |
| Old file skipped | Existing filename or URL-path collision; no content revalidation |
