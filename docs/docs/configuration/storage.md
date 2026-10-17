---
title: "Storage"
description: "ZIP, filesystem, and SQLite storage backends"
---
# Storage

```yaml
storage:
  storage_type: zip          # zip | filesystem | sqlite
  storage_path: storage
```

| Field | Purpose |
|-------|---------|
| `storage_type` | `zip` (default), `filesystem`, or `sqlite` |
| `storage_path` | Directory for ZIP/filesystem, or a database file path for SQLite; default `storage` |
| `compression` | Accepted by the schema; CLI ZIP storage currently always uses Deflate |
| `compression_level` | Reserved; 0–9 accepted but not applied |
| `max_file_size` | Reserved; automatic splitting is not implemented |
| `split_files` | Reserved; automatic splitting is not implemented |

Relative `storage_path` values are resolved from the project directory:

| Backend | Example configuration | Published storage |
|---------|-----------------------|-------------------|
| `zip` | `storage_path: storage` | `storage/storage.zip` |
| `filesystem` | `storage_path: storage` | `storage/` with individual JSON pages |
| `sqlite` | `storage_path: storage.sqlite` | `storage.sqlite` |

For SQLite, an existing directory or a path ending in a directory separator
uses `storage.db` inside that directory.

See [export and storage](/use-cases/export-and-storage).

Full backups are built beside the destination as `.partial` storage and replace
the previous complete backup after success. ZIP writes use a `.journal` directory
of durable pages and compact it into an archive at close. Keep that directory
with its archive when recovering an interrupted process.

Updates retain `runs/<chronological-id>/page_N.json` generations. Legacy flat
`page_N.json` members remain readable. Filesystem storage supports the same
run, resume, update and export workflow as ZIP and SQLite.

ZIP currently uses Deflate compression. `compression_level`, `max_file_size`
and `split_files` are reserved settings; automatic splitting and configurable
compression levels are not implemented.

Export includes every retained update generation. It does not create a
deduplicated snapshot; see [`export`](/commands/export). Recovery steps and
checkpoint requirements are documented under [`run`](/commands/run).
