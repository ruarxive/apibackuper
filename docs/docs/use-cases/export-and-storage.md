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
  compression: true
```

| Type | When to use |
|------|-------------|
| `zip` | Default. Compact single-file archive |
| `filesystem` | Inspect individual JSON files on disk |
| `sqlite` | Queryable local database (`storage_path` is the `.sqlite` file) |

SQLite example: `examples/features/sqlite-storage/`.

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
