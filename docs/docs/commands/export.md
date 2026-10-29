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

- `--format` / `-f` — `jsonl`, `gzip`, `zstd`, `parquet` or `warc`. If omitted,
  guessed from the extension (`.jsonl`, `.gz`, `.zst`, `.parquet`, `.warc`, `.warc.gz`)
- `--fields` — comma-separated field list
- `--where` — simple filter, for example `updated_at >= 2024-01-01`
- `--projectpath` / `-p`
- `--verbose` / `-v`

See [export filters](/configuration/export-filters) for the exact operators,
type conversion, nested paths, date handling and missing values. `--where`
supports one comparison; SQL `=`, compound conditions and malformed expressions
fail with exit status 1 before replacing existing output.

Parquet requires `pyarrow`; the `recommended` extra includes it and `pandas`:
`pip install "apibackuper[recommended]"`.

## Source records and history

Export reads the configured backup backend, including legacy flat pages and
all `runs/<id>/` update generations. It emits historical records as stored;
repeated object IDs remain repeated even when `data.item_key` is set.
`--where` and `--fields` filter and project each record without deduplicating it.

If the project has a `follow` section and a details archive exists, export
reads that archive using `follow_data_key` instead of the list pages.

## Output safety

The output is written to a temporary file beside the destination and replaces
the destination only after a successful export. An export failure preserves
any previous output. The output directory must already exist.

Choose a path outside your backup: export rejects the backup file itself,
the selected details archive, aliases resolving to those sources, and every
path inside a filesystem backup directory.
