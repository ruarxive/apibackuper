---
title: "export"
description: "apibackuper export command reference"
---
# `export`

Exports stored records to JSON Lines, gzip, zstd, or Parquet.

```bash
apibackuper export etrust.jsonl
apibackuper export etrust.jsonl.gz
apibackuper export etrust.jsonl.zst
apibackuper export etrust.parquet
apibackuper export --format jsonl output.jsonl -p hhemployers
apibackuper export out.jsonl --fields id,title --where "updated_at >= 2024-01-01"
```

**Arguments:**

- `filename` — output path

**Key options:**

- `--format` / `-f` — `jsonl`, `gzip`, `zstd`, or `parquet`. If omitted, guessed
  from the extension (`.jsonl`, `.gz`, `.zst`, `.parquet`)
- `--fields` — comma-separated field list
- `--where` — simple filter, for example `updated_at >= 2024-01-01`
- `--projectpath` / `-p`
- `--verbose` / `-v`

Parquet requires `pandas` and `pyarrow` (`pip install "apibackuper[recommended]"`).
