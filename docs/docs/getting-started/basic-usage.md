---
title: "Basic usage"
description: "Project layout, common flags, and everyday commands"
---
# Basic usage

Every backup lives in a **project directory** that contains a configuration
file (`apibackuper.yaml` or the legacy `apibackuper.cfg`) plus optional
`params.json` for POST bodies.

## Create and run

```bash
apibackuper create budgettofk
apibackuper estimate full -p budgettofk
apibackuper run full -p budgettofk
```

If you are already inside the project directory, omit `-p` / `--projectpath`.

## Inspect a project

```bash
apibackuper info -p hhemployers
apibackuper info --json -p hhemployers
apibackuper validate-config -p hhemployers
```

## Export

```bash
apibackuper export hhemployers.jsonl -p hhemployers
apibackuper export data.parquet -p hhemployers
apibackuper export --format zstd output.zst -p hhemployers
```

## Follow-up work

```bash
apibackuper follow continue
apibackuper getfiles
```

## Common flags

Most commands accept:

| Flag | Purpose |
|------|---------|
| `-p` / `--projectpath` | Project directory (defaults to the current directory) |
| `-v` / `--verbose` | Extra logging to the console as well as `apibackuper.log` |

Use `apibackuper <command> --help` for the live flag list.

## Configuration formats

YAML is recommended. The loader looks for `apibackuper.yaml` or
`apibackuper.yml` first, then falls back to `apibackuper.cfg`. INI is
deprecated; `run` and `update` print a warning when they load it.

See [Configuration](/configuration/) for the full field list.
