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
cd budgettofk
# save apibackuper.yaml with the endpoint, pagination and response keys
apibackuper validate-config
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full
```

`create` writes a minimal legacy `apibackuper.cfg`. Add a complete YAML file
using the [quick start](/getting-started/quick-start) or a
[template](/examples/templates). YAML takes precedence over the INI scaffold.

From the parent directory, select the project explicitly:

```bash
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

Project commands accept `-p` / `--projectpath`; `create` takes the destination
as its positional argument. Additional flags apply to specific commands:

| Flag | Purpose |
|------|---------|
| `-p` / `--projectpath` | Project directory (defaults to the current directory) |
| `-v` / `--verbose` | Extra diagnostics on `create`, `detect`, `run`, `update`, `export` and `validate-config` |
| `--dry-run` | Offline JSON plan on `run`, `update` and `follow`; `run` also accepts `--profile` |
| `--resume` | Recover an interrupted `run` or `update` from its checkpoint |
| `--strict` | Treat configuration warnings as errors with `validate-config` |

Use `apibackuper <command> --help` for the live flag list.

## Configuration formats

YAML is recommended. The loader looks for `apibackuper.yaml` or
`apibackuper.yml` first, then falls back to `apibackuper.cfg`. INI is
deprecated; `run` and `update` print a warning when they load it.

See [Configuration](/configuration/) for the full field list.
