---
title: "Basic usage"
description: "Understand project files, path resolution, command order, recovery modes and safe exports"
---
# Basic usage

A backup project is a directory containing an API definition and the local
state needed to collect it repeatedly. Run commands inside that directory, or
select it with `-p` / `--projectpath`. The CLI command prefix can also be written
as `python -m apibackuper` when you need to select a specific Python environment.

For a first successful collection, use the
[Quick Start](/getting-started/quick-start). This page explains the same workflow
for a project you will maintain.

## Create a project and supply the configuration

From a parent directory:

```bash
apibackuper create catalog
cd catalog
```

`create` writes a minimal legacy `apibackuper.cfg`. It is a scaffold, not a
complete API definition. Add `apibackuper.yaml` using a
[template](/examples/templates) or the
[REST walkthrough](/use-cases/rest-api-backup), and set the actual endpoint,
request method, pagination and response keys.

Configuration search order is:

1. `apibackuper.yaml`
2. `apibackuper.yml`
3. `apibackuper.cfg`

The first format found takes precedence; files are not merged. Editing an INI
file while YAML exists therefore does not change the active project definition.
YAML is recommended; INI is deprecated and produces a validation warning.

## Know which files serve which purpose

A project using defaults can contain:

```text
catalog/
  apibackuper.yaml
  params.json                  # optional fixed parameters / POST JSON body
  headers.json                 # optional request headers
  url_params.json              # optional URL parameters for supported query modes
  follow_params.json           # optional fixed detail-request parameters
  apibackuper_state.json        # last successful run and update watermark
  apibackuper_checkpoint.json   # interrupted/completed run recovery information
  storage/
    storage.zip                # default published main backup
    details.zip                # only after unnamed follow collection
    files.zip                  # only after ZIP-output attachment downloads
```

Do not create empty state or checkpoint files manually. Commands maintain them.
`.partial` storage and matching ZIP `.journal` directories can also exist while
a collection is unfinished. Keep them for recovery rather than deleting them as
scratch data. Main archive, details, attachment bytes and exports are separate
artifacts; one successful stage does not run the others automatically.

## Use a project path without changing directories

These commands run from the **parent** of `catalog`:

```bash
apibackuper validate-config --strict -p catalog
apibackuper run full --dry-run -p catalog
apibackuper estimate full -p catalog
apibackuper run full -p catalog
apibackuper info --json -p catalog
apibackuper export catalog.jsonl -p catalog
```

The export is `catalog.jsonl` in the current directory, beside the project.
`-p` selects a configuration directory; it does not change the process working
directory. Put command-specific options after the command, and quote paths with
spaces, for example `-p "API backups/catalog"`.

| Path | Resolution rule |
|------|-----------------|
| Config and JSON request files | Inside the selected project |
| Relative `storage.storage_path` | Inside the selected project |
| Default state/checkpoint paths | Inside the selected project |
| Explicit state/checkpoint overrides | As written, relative to process working directory |
| Relative token/password files and `settings.logfile` | Process working directory |
| Export filename | Process working directory |

For scheduled jobs, use a known working directory and absolute secret/state
paths where needed. See [configuration paths](/configuration/#path-resolution).

## Follow the collection lifecycle

| Step | Command | Network and purpose |
|------|---------|---------------------|
| Check configuration | `validate-config --strict` | Offline schema/project checks; warnings fail too |
| Preview execution | `run full --dry-run` | Offline plan from configuration and saved state |
| Sample the API | `estimate full` | Live request; requires usable record-count metadata |
| Collect pages | `run full` | Live backup with staged full publication |
| Inspect saved state | `info --json` | Local project/storage report |
| Export records | `export catalog.jsonl` | Local extraction from retained pages/details |

An API without a usable total may still be collectable with page-count or
short-page stopping, even when `estimate` cannot compute its total. A dry-run
also does not test credentials or response keys against the live service.

`detect` can suggest response/pagination keys for an existing project:

```bash
apibackuper detect
```

It makes a live request. Review suggestions before using `--write-config`; it
cannot establish stable ordering, meaningful modification fields or deletion
semantics. See [detect](/commands/detect).

## Choose the right recovery or refresh command

| Your intent | Command | Required context |
|-------------|---------|------------------|
| New complete replacement | `run full` | Valid project; preserve an old snapshot if needed |
| Finish an interrupted full run | `run full --resume` | Same mode/path and valid checkpoint/staging |
| Fill missing pages in published storage | `run continue` | Published flat-page sequence; no record-level freshness check |
| Legacy name for the previous operation | `run incremental` | Same behavior as `continue` |
| Collect changed records | `update` | Successful baseline and API-supported watermark filter |
| Finish an interrupted update | `update --resume` | Its original generation and checkpoint |

A fresh full backup replaces the published main archive only after success.
Updates retain generations and repeated IDs; they do not produce a deduplicated
current table. A completed checkpoint makes `--resume` report that the run is
already complete. See [incremental and update](/use-cases/incremental-and-update).

After a failure, use the latest command's exit status and logs. `info` may still
show the earlier successful run because failure does not advance successful
state. Do not start another fresh run merely because saved state says `success`.

## Export locally and preserve the source

```bash
apibackuper export catalog.jsonl
apibackuper export catalog.jsonl.gz
apibackuper export selected.jsonl --fields id,title --where "id >= 3"
```

Choose fields and types from your records; the numeric-ID filter is illustrative.
Export defaults from the suffix (`.jsonl`, `.gz`, `.zst`, `.parquet`) or an
explicit `--format`. `.json` also means JSON Lines, not a single array. Parquet
requires optional dependencies.

Keep output outside source storage; filesystem backups reject exports inside
their own root. Export replaces existing output only after successful writing.
Filtering accepts one comparison, not SQL/logical expressions. See
[export and storage](/use-cases/export-and-storage).

## Add details or attachments only when configured

For a project with an unnamed follow rule:

```bash
apibackuper follow full --dry-run
apibackuper follow full
apibackuper getfiles
```

`follow` requires its own identifier/URL settings. `getfiles` requires a `files`
section and ZIP main storage. With follow configured, it reads unnamed details
rather than falling back to list pages. An existing unnamed `details.zip` is
also selected by export, so refresh details deliberately after new list backups.
See [follow and files](/use-cases/follow-and-files).

## Get help and diagnostics

```bash
apibackuper --help
apibackuper run --help
apibackuper export --help
```

| Flag | Available on |
|------|--------------|
| `-p` / `--projectpath` | Project commands; `create` uses a positional destination |
| `-v` / `--verbose` | `create`, `detect`, `run`, `update`, `export`, `validate-config` |
| `--dry-run` | `run`, `update`, `follow`; `run` also has the alias `--profile` |
| `--resume` | `run`, `update`; follow recovery uses `follow continue` |
| `--strict` | `validate-config` |

The default log is `apibackuper.log` in the process working directory; the
project can set `settings.logfile`. Verbose output adds console diagnostics on
supported commands. Check [troubleshooting](/getting-started/troubleshooting)
when a command fails, and [best practices](/getting-started/best-practices)
before turning the project into a recurring job.
