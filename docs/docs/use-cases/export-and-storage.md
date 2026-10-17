---
title: "Export and storage"
description: "Choose ZIP, filesystem, or SQLite storage and export JSONL, gzip, zstd, or Parquet"
---
# Export and storage

## Storage backends

```yaml
storage:
  storage_type: zip          # zip | filesystem | sqlite
  storage_path: storage
```

| Type | When to use |
|------|-------------|
| `zip` | Default. Compact single-file archive |
| `filesystem` | Inspect individual JSON files on disk |
| `sqlite` | JSON page BLOBs in a local database (`storage_path` is the `.sqlite` file) |

SQLite example: `examples/features/sqlite-storage/`.

For ZIP, `storage_path: storage` creates `storage/storage.zip`. For filesystem
storage it is the directory containing pages. For SQLite, set a database path
such as `storage_path: storage.sqlite`.

Full backups use `.partial` staging, and ZIP writes may have a `.journal`
sidecar. Keep recovery files together until the run completes; see
[storage configuration](/configuration/storage).

## Export formats

```bash
apibackuper export data.jsonl
apibackuper export data.jsonl.gz
apibackuper export data.jsonl.zst
apibackuper export data.parquet
apibackuper export --format jsonl output.jsonl
```

| Extension | Format |
|-----------|--------|
| `.jsonl` / `.json` | JSON Lines |
| `.gz` / `.gzip` | gzip-compressed JSON Lines |
| `.zst` | Zstandard |
| `.parquet` | Parquet (needs `pandas` and `pyarrow`) |

## Field filters

```bash
apibackuper export out.jsonl --fields id,title,updated_at
apibackuper export out.jsonl --where "updated_at >= 2024-01-01"
```

Feature example: `examples/features/export-filters/`.

See [export filter syntax](/configuration/export-filters) for supported operators,
types and dates. See [Python storage access](/development/python-api#direct-storage-access)
to inspect page payloads; SQLite does not create a relational row per API object.

## Historical records and safe output paths

After updates, export reads both the original pages and every retained
`runs/<id>/` generation. It preserves repeated IDs. Apply deduplication
downstream if you need one current record per object.

When a follow details archive exists, export uses its records instead of the
list pages. Choose an output path outside the backup and its detail archives.
Export writes a temporary file and replaces existing output only after success;
see [`export`](/commands/export).
