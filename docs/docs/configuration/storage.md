---
title: "Storage"
description: "Choose ZIP, filesystem or SQLite, understand paths and generations, and preserve recovery files"
---
# Storage

Storage keeps API page payloads so they can be resumed and exported later.
Choose it independently of the export format: any supported main backend can
produce JSONL, gzip, zstd or Parquet. Follow details and downloaded attachments
have their own output rules.

## Choose a backend

| Backend | Useful when | Main trade-off |
|---------|-------------|----------------|
| `zip` | You want a portable page archive and ZIP-source attachment downloads | Durable writes also use journal sidecars during collection |
| `filesystem` | You want to inspect JSON pages directly with file tools | Many files and directories for large histories |
| `sqlite` | You want page payloads in one database and SQL-level inspection | API objects remain JSON BLOBs, not normalized relational rows |

All three support full backup, resume, update generations and export. `getfiles`
currently requires a ZIP main source. Follow reads all three source backends but
always writes ZIP detail archives.

## ZIP configuration and paths

```yaml
storage:
  storage_type: zip
  storage_path: storage
```

For a project `/srv/catalog`, the published archive is
`/srv/catalog/storage/storage.zip`. `storage_path` is a **directory** for ZIP;
setting it to `backup.zip` would create `backup.zip/storage.zip`, not rename
the archive file.

A completed archive can contain:

```text
storage.zip
  page_1.json
  page_2.json
  runs/<run-id>/page_1.json
  runs/<later-run-id>/page_1.json
```

The full backup uses flat page members. Every update receives a separate run
namespace, so page 1 of an update does not overwrite the original page 1.
The JSON pages retain the configured response shape; use `export` to extract
records from a response wrapper.

## Filesystem configuration

```yaml
storage:
  storage_type: filesystem
  storage_path: pages
```

This publishes `/srv/catalog/pages/` with the same relative page names:

```text
pages/
  page_1.json
  page_2.json
  runs/
    <run-id>/
      page_1.json
```

Use a dedicated directory for this backend: full publication replaces the
configured directory, including any unrelated files you placed inside it.
A full run is staged in the sibling `pages.partial/`. Publication can briefly
use `pages.previous/` to preserve the old directory during replacement. Keep a
leftover publication/recovery directory until the matching resume completes;
do not manually merge its pages into the published directory.

Export destinations must be outside this backend's directory. For example,
`/srv/catalog/items.jsonl` is suitable; `/srv/catalog/pages/items.jsonl` is rejected
to protect backup contents.

## SQLite configuration

```yaml
storage:
  storage_type: sqlite
  storage_path: storage/catalog.sqlite
```

A relative path resolves from the project. SQLite expects a **database file**,
not the ZIP-style directory setting. An existing directory, or a path ending
in the platform's directory separator, resolves to `storage.db` inside it.
Prefer an explicit filename to avoid ambiguity across machines.

Tables `pages` and `objects` store `name`, `content` (BLOB) and `created_at`.
A row represents a page/object payload, not one record from the API. Names such
as `runs/<run-id>/page_1.json` remain logical names in the database. You can
inspect page inventory with:

```sql
SELECT name, length(content) AS bytes, created_at
FROM pages
ORDER BY name;
```

A full run uses `catalog.sqlite.partial` before publication. Exporting to the
source database path or an alias of it is rejected. See [Python storage access](/development/python-api#direct-storage-access)
for reading decoded page bytes through the backend interface.

## Full backups and recovery files

`run full` stages data beside the destination and replaces the previous complete
backup only after successful collection/publication. An interrupted run retains
staging data, the checkpoint and the prior successful state. Starting another
full run without `--resume` starts a fresh staging run.

For default ZIP storage, relevant files can include:

```text
catalog/
  apibackuper.yaml
  apibackuper_state.json
  apibackuper_checkpoint.json
  storage/
    storage.zip                  # previous complete backup
    storage.zip.partial          # in-progress replacement
    storage.zip.partial.journal/ # durable pages not yet compacted
```

Inside a published archive, each generation (the root for full backups,
`runs/<id>/` for updates) holds its pages plus `manifest-sha256.txt` and
`run.json`, which [`verify`](/commands/verify) uses to check the stored bytes.

The ZIP journal saves member data durably before checkpoint progress advances.
It is compacted into the archive on close. A journal next to `storage.zip`
rather than `.partial` can also exist for continued collection or updates.

Keep the correct archive/staging path and its `.journal` together with state and
checkpoint. Do not treat a copied ZIP without its active journal as a complete
copy of an interrupted run. Resume can also complete an interrupted publication
from saved data without downloading again:

```bash
apibackuper run full --resume -p /srv/catalog
apibackuper update --resume -p /srv/catalog
```

Choose the command matching the interrupted operation; the examples are
alternatives. See [run](/commands/run) for checkpoint compatibility and
[update](/commands/update) for retained generation recovery.

## Compression and reserved settings

| Field | Accepted value | Current CLI behavior |
|-------|----------------|----------------------|
| `storage_type` | Required `zip`, `filesystem` or `sqlite` | Selects main backend |
| `storage_path` | String; default `storage` | Resolved as above, relative to project unless absolute |
| `compression` | Boolean | Schema-accepted; ZIP CLI storage always uses Deflate |
| `compression_level` | Integer 0–9 | Reserved; does not change CLI compression level |
| `max_file_size` | Non-negative integer bytes | Reserved; no automatic archive splitting |
| `split_files` | Boolean | Reserved; no automatic archive splitting |

Compression of exported `.gz` or `.zst` files is a separate operation. Choosing
a compressed export does not change how backup pages are stored.

## Changing backends or moving a project

Changing `storage_type` or `storage_path` selects a different destination; it
does not convert or move previous data. For a backend change, create a separate
project/destination, perform a fresh full backup and verify an export before
retiring the old archive. There is no built-in ZIP-to-SQLite migration command.

For a completed project move, keep config, scripts and successful state together,
and update absolute paths. For an interrupted run, checkpoint storage references
must still match the configured destination; moving the directory alone may
require restoring its original paths to resume. Explicit relative state,
credential and log overrides still resolve from the working directory.

## Retention and export history

Updates retain historical generations; export emits records from all of them,
including repeated IDs. There is no automatic pruning, deduplication or
restore-to-API command. A fresh successful full run replaces the published main
history, so preserve a verified older archive separately when retention requires it.

Stop writers before copying or rotating an archive. Do not use the same storage
path for simultaneous projects, and do not share checkpoints between them.
If a details archive exists, export may select that archive instead of main
pages; refresh follow results after a changed main backup when appropriate.
See [follow output selection](/configuration/follow#output-selection-and-export).
