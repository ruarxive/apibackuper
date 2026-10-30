# apibackuper

> A command-line tool to archive and backup REST APIs

**Version:** 3.0.0

This README describes version 3.0.0. See the
[changelog](CHANGELOG.md#300---2026-10-29) for release details and the
[3.0 migration notes](#upgrading-to-30) before upgrading from 2.x.

**apibackuper** downloads paginated REST APIs into local storage and exports
the archive as JSON Lines, gzip, zstd, Parquet or WARC. It is designed for
repeatable, long-running backups rather than one-off HTTP requests.

## Features

- GET and POST iterative APIs: page, skip/offset, range, cursor, next-URL and
  `Link` header pagination, with checks that fail incomplete collections
- Full, incremental, and update work modes, with resume from checkpoints
- ZIP, filesystem, or SQLite storage; each update in ZIP storage gets its own archive
- Provenance for every page (`exchange_N.json`: request, status, headers, fetch
  time, SHA-256) and the original bytes of XML/HTML responses
- Fixity manifests for every run and downloaded file, checked by `apibackuper verify`
- Export to JSON Lines, gzip, Zstandard, Parquet or WARC
- YAML configuration (INI still loaded, but deprecated)
- Authentication: Basic, Bearer, API Key, OAuth2 (refresh token or client credentials)
- Rate limiting, retries with `Retry-After`/`X-RateLimit-Reset` waits, response
  rules for error bodies, concurrency, and SSL controls
- Follow-up requests for related objects and streamed downloads of associated files
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

Parquet export, WARC export and aria2 downloads:

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

## Using with AI coding agents

The [`skills/apibackuper`](skills/apibackuper/SKILL.md) Agent Skill teaches
Claude Code, Codex, Cursor and Kimi Code to configure an apibackuper project
instead of writing a custom scraper for each API. In Claude Code:

```text
/plugin marketplace add ruarxive/apibackuper
/plugin install apibackuper@apibackuper-marketplace
```

For other agents, and for an `AGENTS.md` rule without skill support, see the
[AI coding agents guide](docs/docs/getting-started/ai-agents.md).

## Commands

```bash
apibackuper init <dir> --url URL [--method POST --body JSON] [-H "Name: value"] [--auth bearer]
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
apibackuper validate-config [--strict] [--json]
apibackuper schema
apibackuper --json <command>
```

`init` probes an endpoint and writes a complete project; `run full --max-pages 2`
checks two real pages in a temporary archive without touching the project.
`--json` before any command prints one JSON object with the result or an error
code; progress bars are hidden when output is not a terminal.

`run full --dry-run` (alias `--profile`), `update --dry-run`, and
`follow full --dry-run` print a JSON plan without making HTTP requests.
`estimate full` contacts the API to measure a sample response.

See [HTTP request files](docs/docs/configuration/http-requests.md) for custom
headers, query filters and POST bodies, and [export filters](docs/docs/configuration/export-filters.md)
for the `--where`/`--fields` contract. Malformed filters fail instead of
silently producing unfiltered output.

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

### Upgrading to 3.0

Version 3.0 changes the archive layout and several defaults. Backups made by
2.x remain readable; read these points before upgrading scheduled jobs.

- **ZIP update generations live in their own archives.** Each `update` now
  writes `storage/storage.zip.runs/<id>.zip` instead of adding `runs/<id>/`
  members to `storage.zip`. All commands read both layouts. Tools that open
  `storage.zip` directly no longer see new update generations; use `export`
  or the [storage API](docs/docs/development/python-api.md). Version 2.x does
  not read `storage.zip.runs/`, so after rolling back, run a new full backup.
- **Provenance records are written by default.** Every saved page gets an
  `exchange_N.json` member, and XML/HTML responses keep `raw_N.<ext>`. Set
  `storage.capture.metadata: false` (and `raw_body: never`) for pages-only
  archives. Each run also writes `manifest-sha256.txt` and `run.json`, and
  `getfiles` writes `files-manifest-sha256.txt`. Scripts that expect only
  `page_N.json` members must ignore these names.
- **Incomplete collections fail instead of "succeeding".** A short or empty
  page before the end implied by `total_number_key`/`pages_number_key` (for
  example, an API that caps the page size) now fails the run, and the previous
  backup stays published. Set `page_size_limit` to the size the API returns, or
  remove an inexact count key. Without count metadata there is no 20,000-page
  cap any more; a page that repeats the previous one fails the run.
- **Missing credential files are errors.** An absent or empty `token_file`,
  `password_file` or `client_secret_file` fails `validate-config` and stops
  requests, instead of sending them without credentials.
- **New defaults.** `settings.checkpoint_interval_pages` defaults to 1
  (checkpoint after every page; set 0 for the previous behaviour). Without an
  explicit list, HTTP 429 and 504 are retried along with 500, 502 and 503.
- **Follow and file downloads continue past missing objects.** HTTP 404/410
  responses are recorded in `details.missing.json` or `files_skipped.list`
  instead of stopping the command.
- **Deprecated:** `ProjectBuilder.getfiles(be_careful=...)` is ignored with a
  warning; use `files.max_file_size`.

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
