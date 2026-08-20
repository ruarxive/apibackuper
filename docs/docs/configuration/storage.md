---
title: "Storage"
description: "ZIP, filesystem, and SQLite storage backends"
---
# Storage

```yaml
storage:
  storage_type: zip          # zip | filesystem | sqlite
  storage_path: storage
  compression: true
  compression_level: 6
```

| Field | Purpose |
|-------|---------|
| `storage_type` | `zip` (default), `filesystem`, or `sqlite` |
| `storage_path` | Directory, or `.sqlite` file for SQLite |
| `compression` | Compress ZIP storage |
| `compression_level` | 0–9 |
| `max_file_size` | Split threshold in bytes |
| `split_files` | Split when the size limit is reached |

See [export and storage](/use-cases/export-and-storage).
