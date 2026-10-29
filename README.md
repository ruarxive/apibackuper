# apibackuper

> A command-line tool to archive and backup REST APIs

**Version:** 2.0.0

This README describes version 2.0.0. See the
[changelog](CHANGELOG.md#200---2026-10-17) for release details and migration notes.

**apibackuper** downloads paginated REST APIs into local storage and exports
the archive as JSON Lines, gzip, zstd, or Parquet. It is designed for
repeatable, long-running backups rather than one-off HTTP requests.

## Features

- GET and POST iterative APIs (page, skip/offset, or range pagination)
- Full, incremental, and update work modes, with resume from checkpoints
- ZIP, filesystem, or SQLite storage
- Export to JSON Lines, gzip, Zstandard, or Parquet
- YAML configuration (INI still loaded, but deprecated)
- Authentication: Basic, Bearer, API Key, OAuth2
- Rate limiting, retries, concurrency, and SSL controls
- Follow-up requests for related objects and associated file downloads
- Optional Python hooks for custom pipeline steps

## Documentation

The full documentation site (Docusaurus) lives in [`docs/`](docs/) and is
published at **[ruarxive.org/apibackuper](https://ruarxive.org/apibackuper/)**.

| Section | What it covers |
|---------|----------------|
| [Getting started](https://ruarxive.org/apibackuper/getting-started/installation) | Install, quick start, positioning |
| [Cookbook](https://ruarxive.org/apibackuper/getting-started/cookbook) | Task index by goal |
| [CLI reference](https://ruarxive.org/apibackuper/commands/) | Every command |
| [Configuration](https://ruarxive.org/apibackuper/configuration/) | YAML sections and field reference |
| [Examples](https://ruarxive.org/apibackuper/examples/) | Working projects and templates |
| [Troubleshooting](https://ruarxive.org/apibackuper/getting-started/troubleshooting) | SSL, pagination, rate limits |

Source pages: [`docs/docs/`](docs/docs/). Changelog: [`CHANGELOG.md`](CHANGELOG.md).

## Installation

### Using pip

```bash
pip install --upgrade pip setuptools
pip install apibackuper
```

### Using pipx or uv

```bash
pipx install apibackuper
# or
uv tool install apibackuper
```

Parquet export and aria2 downloads:

```bash
pip install "apibackuper[recommended]"
```

### Requirements

- Python 3.10 or greater

### Install from source

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install .
```

## Quick start

For a first run with a known result, follow the
[local API walkthrough](docs/docs/getting-started/quick-start.md): it serves
five records on your machine, backs up three pages and checks the exported IDs.
The server and configuration are in [`examples/local-demo/`](examples/local-demo/).

For an external POST API:

```bash
apibackuper create etrust
cd etrust
# save apibackuper.yaml with your API settings (and params.json for POST APIs)
apibackuper validate-config
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full
apibackuper export etrust.jsonl
```

A worked POST API example is in the
[E-Trust walkthrough](docs/docs/use-cases/post-api-backup.md).
Starter YAML files are in [`examples/templates/`](examples/templates/).
`create` currently writes a minimal `apibackuper.cfg`; save your complete
configuration as `apibackuper.yaml`, which takes precedence over that INI file.
The API-related `create` flags are accepted for compatibility but do not populate
the configuration. Follow the [create reference](docs/docs/commands/create.md).

## Commands

```bash
apibackuper create <name>
apibackuper detect [--url URL] [--write-config]
apibackuper estimate full
apibackuper run full [--resume]
apibackuper run continue
apibackuper update [--resume]
apibackuper follow full|continue
apibackuper getfiles
apibackuper export output.jsonl
apibackuper info [--json]
apibackuper verify [--strict] [--json]
apibackuper validate-config
```

`run full --dry-run` (alias `--profile`), `update --dry-run`, and
`follow full --dry-run` print a JSON plan without making HTTP requests.
`estimate full` contacts the API to measure a sample response.

See [HTTP request files](docs/docs/configuration/http-requests.md) for custom
headers, query filters and POST bodies, and [export filters](docs/docs/configuration/export-filters.md)
for the `--where`/`--fields` contract. Malformed filters now fail instead of
silently producing unfiltered output; this fix is listed under `Unreleased`.

`getfiles` currently reads ZIP backups. Its downloaded files can be stored in
ZIP or filesystem storage; see [file configuration](docs/docs/configuration/files.md).

```bash
apibackuper --help
apibackuper run --help
```

## Backup safety and recovery

A fresh `apibackuper run full` writes to a staging path ending in `.partial`
(for example, `storage.zip.partial`). It replaces the previous complete archive
only after every required page has been saved successfully. A failed full backup
keeps the previous archive and retains its staging data and checkpoint for recovery:

```bash
apibackuper run full --resume
```

Resume reuses saved pages and starts at the first unresolved page. Checkpoints
advance only through pages that have been saved durably. Failed or incomplete
backup runs exit with a nonzero status and preserve the last successful backup state,
so an update cannot advance its timestamp or change key past missing data.

Each `apibackuper update` retains its pages under a unique
`runs/<id>/page_N.json` generation. Use `apibackuper update --resume` to continue an
interrupted update within the same generation. Export reads the original pages
and every retained generation: it represents the retained archive history, and
does not deduplicate objects into a current snapshot. An object returned in several
updates can therefore appear several times in the export.

Existing archives with flat `page_N.json` members remain readable. Legacy
checkpoints without `next_page` are also accepted; resume safely replays their
last recorded page.

For ZIP storage, saved pages may also live in a `.journal` sidecar directory
until they are compacted into the archive. Keep `storage.zip.partial.journal`
beside `storage.zip.partial`, or `storage.zip.journal` beside `storage.zip`,
along with the checkpoint and state files, until recovery is complete. Resume
can finish an interrupted publication from saved data without downloading again.

`run continue` (alias `run incremental`) fills pages from the first missing
page in the published archive. To recover a staged full backup, use
`run full --resume`. See the [recovery guide](docs/docs/use-cases/incremental-and-update.md).

## Contributing

See the [development docs](https://ruarxive.org/apibackuper/development/contributing).

For embedding, see the [Python API guide](docs/docs/development/python-api.md).
Before scheduling backups, read [backup completeness](docs/docs/getting-started/data-integrity.md)
for source consistency, deletion handling, verification and rotation.

## Migration notes

### Python support

The minimum supported Python version is now **3.10**, declared by
`requires-python` in the package metadata. This is a breaking compatibility
change for Python 3.8 and 3.9 users; upgrade Python before installing this version.
CI covers Python 3.10–3.13 on Ubuntu and macOS.

### Storage backends (since v1.0.15)

The legacy `FileStorage`, `ZipFileStorage`, and `FilesystemStorage` API
in `apibackuper.storage` is **deprecated**. New code should use the unified
`StorageBackend` implementations from `apibackuper.storage.backends`:

| Legacy class              | Replacement                       |
| ------------------------- | --------------------------------- |
| `FileStorage`             | `StorageBackend` (base class)      |
| `ZipFileStorage`          | `ZipStorageBackend`               |
| `FilesystemStorage`       | `FilesystemStorageBackend`        |

The legacy concrete classes still work but emit `DeprecationWarning` on
instantiation. Importing alone is silent. Mapping the legacy API to the new
backend API:

```python
# Before (deprecated)
from apibackuper.storage import ZipFileStorage

storage = ZipFileStorage("pages.zip", mode="w")
storage.exists("page_1.json")           # -> bool
storage.store("page_1.json", b'{"id": 1}')
storage.close()

# After (preferred)
from apibackuper.storage import ZipStorageBackend

storage = ZipStorageBackend("pages.zip", mode="w")
"page_1.json" in storage.list_objects("page")   # -> bool
storage.save_page("page_1.json", b'{"id": 1}')
storage.close()
```

### YAML configuration

The INI config format is deprecated; YAML is the canonical format. A
YAML config supports `${VAR}` and `${VAR:-default}` placeholders for
sensitive credentials (see [SECURITY.md](SECURITY.md)).

## License

MIT License — see [LICENSE](LICENSE).

## Links

- [Documentation](https://ruarxive.org/apibackuper/)
- [GitHub](https://github.com/datacoon/apibackuper)
- [PyPI](https://pypi.org/project/apibackuper/)
- [Changelog](CHANGELOG.md)
- [Issue tracker](https://github.com/datacoon/apibackuper/issues)
