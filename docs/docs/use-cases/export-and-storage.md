---
title: "Export and storage"
description: "Choose a backup backend, produce verified analysis files and derive a current view from retained history"
---
# Export and storage

Keep response pages as the recoverable collection, then export records for
analysis or exchange. Storage chooses how pages are retained; export chooses
the representation of extracted records. Changing export format does not
convert or replace the source backup.

The commands below run in a project that already has a successful backup. For
a reproducible input, complete the [local quick start](/getting-started/quick-start):
it produces five records with IDs 1–5 and fields `id`, `title`, `updated_at`.

## 1. Choose storage before the first collection

| Backend | Configuration | Result | Useful when |
|---------|---------------|--------|-------------|
| ZIP | `storage_type: zip`, `storage_path: storage` | `storage/storage.zip` | You want one published page archive with compression |
| Filesystem | `storage_type: filesystem`, `storage_path: pages` | `pages/page_N.json` and retained run subdirectories | You want to inspect individual payloads |
| SQLite | `storage_type: sqlite`, `storage_path: backup.sqlite` | One database holding JSON page BLOBs | You want a database container and Python storage access |

For example, the ZIP section in an otherwise complete project is:

```yaml
storage:
  storage_type: zip
  storage_path: storage
```

For SQLite, replace that section with:

```yaml
storage:
  storage_type: sqlite
  storage_path: backup.sqlite
```

SQLite stores pages, not one relational row per API record. Querying arbitrary
API fields with SQL requires a separate transformation; use normal export or
[Python storage access](/development/python-api#direct-storage-access) to read
the payloads. `getfiles` requires a ZIP main source even when downloaded files
use filesystem output. Follow detail results remain ZIP for every main backend.

Changing the type/path does not migrate existing data or its checkpoint. To
switch backends, use a separate project/destination, perform a fresh collection
and verify its export before retiring the original. Filesystem full publication
replaces its dedicated storage directory, so keep unrelated files elsewhere.

## 2. Verify the source and create exports

From the project directory:

```bash doc-test
apibackuper info --json
apibackuper export all-records.jsonl
apibackuper export all-records.jsonl.gz
apibackuper export all-records.jsonl.zst
```

Export is local: it does not call the source API. A normal page export extracts
`data.data_key` from each saved response, removing its response wrapper.
Records follow page order (`page_2` before `page_10`), with the original pages
first and retained update generations after them, oldest first.

| Output extension | Meaning | Dependencies |
|------------------|---------|--------------|
| `.jsonl` or `.json` | One JSON value per line, not a JSON array | Base installation |
| `.gz` or `.gzip` | gzip-compressed JSON Lines | Base installation |
| `.zst` | Zstandard-compressed JSON Lines | Base installation |
| `.parquet` | Columnar records | `recommended` extra, including pyarrow |

For a downstream system that does not use a recognized suffix, choose explicitly:

```bash
apibackuper export --format gzip delivery.bin
```

To create Parquet after installing the extra:

```bash
python -m pip install 'apibackuper[recommended]'
apibackuper export all-records.parquet
```

Parquet export reads the records twice: first to settle one schema, then to
write it. Compatible types are promoted (integers and decimals become doubles,
new nested fields are merged). A top-level field whose values cannot share one
type, such as numbers in some records and strings in others, is written as a
JSON text column. Records must be objects. JSONL preserves flexible record
shapes more directly.

Create the output parent directory first and keep exports outside source backup
paths. In particular, filesystem backups reject output anywhere inside their
storage root. Export writes a temporary file beside the destination and replaces
the destination after success. A failed filter or serialization does not replace
a previous complete output, but adequate free space is still required.

## 3. Produce a focused analysis file

With the local five-record backup:

```bash doc-test
apibackuper export selected.jsonl --fields id,title --where "id >= 3"
```

The expected output is:

```jsonl
{"id": 3, "title": "Item 3"}
{"id": 4, "title": "Item 4"}
{"id": 5, "title": "Item 5"}
```

Filtering happens before field selection, so a filter can use a field omitted
from the final output. For nested fields, `--fields id,metadata.score` produces
a literal `metadata.score` output key rather than a nested object. Missing/null
selected fields are omitted.

`--where` accepts **one comparison** with `==`, `!=`, `<`, `<=`, `>` or `>=`.
Quote the whole expression for the shell. There is no AND/OR, SQL, regular
expression or date parser; dates compare as strings. Missing/null values never
match, and numeric-looking values are parsed as numbers. See the exact
[export filter grammar](/configuration/export-filters) before using filters for
reporting.

## 4. Check records and compressed output

For the local fixture, save as `check_exports.py` and run it in the project:

```python doc-test
import gzip
import json
from pathlib import Path

rows = [json.loads(line) for line in Path("all-records.jsonl").read_text().splitlines()]
with gzip.open("all-records.jsonl.gz", "rt", encoding="utf8") as stream:
    compressed_rows = [json.loads(line) for line in stream]
selected = [json.loads(line) for line in Path("selected.jsonl").read_text().splitlines()]
assert rows == compressed_rows
assert sorted(row["id"] for row in rows) == [1, 2, 3, 4, 5]
assert sorted(row["id"] for row in selected) == [3, 4, 5]
assert all(set(row) == {"id", "title"} for row in selected)
print("Verified: 5 source records and 3 projected records; gzip matches JSONL")
```

For a large collection, count/validate records incrementally instead of loading
the entire export into memory. Compare row counts and distinct IDs separately:
retained update history can legitimately contain more rows than current objects.
Check representative nested fields and boundary dates as well as counts.

## 5. Build a current-object view from history

After `update`, export reads the original pages and all retained
`runs/<id>/` generations. Repeated IDs and inclusive-boundary records remain.
Export ordering alone is not a version-selection rule.

Suppose each historical record has a non-null `id` and a string
`metadata_modified` normalized to the **same UTC format and precision**. This
small-dataset script keeps the largest timestamp for each ID and rejects
conflicting records tied at that largest timestamp, regardless of input order:

```python history-view
import json
from pathlib import Path

latest = {}
conflicts = set()
with Path("history.jsonl").open(encoding="utf8") as stream:
    for line in stream:
        record = json.loads(line)
        key = record["id"]
        version = record["metadata_modified"]
        if key is None or not isinstance(version, str) or not version:
            raise ValueError("Expected a non-null ID and normalized timestamp string")
        previous = latest.get(key)
        if previous is None or version > previous["metadata_modified"]:
            latest[key] = record
            conflicts.discard(key)
        elif version == previous["metadata_modified"] and record != previous:
            conflicts.add(key)

if conflicts:
    raise ValueError(f"Conflicting latest versions for IDs: {conflicts}")

with Path("current.jsonl").open("w", encoding="utf8") as stream:
    for record in latest.values():
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
print("Current objects:", len(latest))
```

First create the input with `apibackuper export history.jsonl`. This script is
for a service with an appropriate modification field; the local fixture's
`updated_at` field is a different example. It stores one record per distinct
ID in memory and does not normalize timestamps itself. Choose a provider-defined
revision/tie-breaker if timestamp precision is insufficient, and use a database
or external processing for larger histories.

The script retains deletion/tombstone records as versions. If the API supplies
them, apply its documented deletion semantics afterward. An object absent from
a later update is not automatically deleted from history or this current view.
See [incremental and update](/use-cases/incremental-and-update).

## Follow sources and retained backups

When the configuration has a `follow` section and an unnamed `details.zip`
exists, export reads details using `follow_data_key` instead of list pages.
Named `details_<name>.zip` archives are not selected automatically. Export a
list inventory before the first follow when you need both representations,
and refresh old details deliberately after changing the main collection.

A new full backup replaces its previous published main storage after success;
updates grow history inside it. For retention, stop writers, preserve the old
archive together with configuration and successful state, then create and verify
the next snapshot. There is no built-in history pruning or restore-to-API command.
Keep `.partial`, checkpoint and matching ZIP `.journal` files together until
interrupted work is recovered. See [storage](/configuration/storage).

Updates append their pages to main storage while collecting. An export during
or after an incomplete update can therefore include unfinished history. Recover
the update successfully before producing a verified downstream dataset.

| Unexpected result | Check |
|-------------------|-------|
| `.json` is not a JSON array | That suffix selects JSON Lines; parse one line at a time |
| Export contains repeated IDs | All retained versions are exported; derive a current view explicitly |
| Fields differ from the list endpoint | Existing unnamed details archive is selected |
| No records match a visible ID | Source ID type versus filter numeric conversion, or a missing/null field |
| Parquet export fails | Optional dependencies; records that are not objects |
| Export path is rejected | Destination overlaps the source archive or filesystem backup root |
