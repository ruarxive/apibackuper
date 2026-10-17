# Project Context

## Purpose
`apibackuper` is a CLI tool and Python library for backing up REST API data to
local storage. It focuses on iterating API endpoints, collecting full or
incremental datasets, and exporting archived data in multiple formats. Backups
must preserve previously collected data during failures, resume and updates.

## Tech Stack
- Python 3.10+ CLI/library
- Typer for CLI commands
- Requests/urllib3 for HTTP
- JSON/YAML handling (jsonschema, PyYAML)
- XML parsing (lxml, xmltodict)
- Storage: ZIP, SQLite and filesystem backends
- Export: JSONL, gzip, zstd; optional Parquet (pandas, pyarrow)

## Project Conventions

### Code Style
- Black 25.1.0 formatting with 100-character line length
- isort using Black profile (line length 100)
- Shared flake8 rules in `.flake8`, used by CI, tox and pre-commit; retained
  legacy style exemptions do not disable core Pyflakes correctness checks
- EditorConfig: 4-space indent, LF, trim trailing whitespace

### Architecture Patterns
- CLI entrypoint in `apibackuper.__main__` with command modules under `apibackuper/cmds/`
- `ProjectBuilder` owns project configuration and public command facades;
  `cmds/backup.py` orchestrates full backups, resume and incremental updates
- `cmds/runner.py` owns page outcomes, progress counters and checkpoints of the
  contiguous, durably saved page prefix
- Request construction and execution share authentication, retries, timeouts,
  rate limiting and credential-safe diagnostics across backup, follow and file commands
- Project configuration in YAML or INI with JSON schema validation
- Storage backends share a protocol. Full backups stage beside the destination
  in `.partial` and publish on completion; updates retain namespaced generations
  under `runs/<id>/`. Export reads legacy flat pages and retained generations
- Failed runs leave the last successful state unchanged. Legacy archives and
  checkpoints remain readable; export preserves history rather than producing
  a deduplicated object snapshot

### Testing Strategy
- pytest with coverage enabled (`tests/`), doctest modules on
- Command lifecycle regressions exercise download, interruption, resume, update
  and export against mocked HTTP and temporary storage
- CI tests Python 3.10–3.13 on Ubuntu and macOS; tox uses the same Python range
  with separate lint/format/typecheck environments
- Build, metadata and installed-wheel smoke checks run on pull requests;
  distributable wheels include schemas and exclude tests
- Pre-commit hooks enforce formatting, linting, and basic checks

### Git Workflow
- Default branch: `master`
- Changelog follows Keep a Changelog and SemVer for releases
- Pre-commit hooks are expected before commits

## Domain Context
- Primary use case: backing up data from public or protected REST APIs
- Supports pagination by page or skip, incremental/update modes, and follow-up
  requests to related resources
- Can download associated files and archive them locally
- Authentication methods: Basic, Bearer, API Key, OAuth2
- Rate limiting to respect API quotas and prevent throttling

## Important Constraints
- Must remain compatible with Python 3.10+; the raised minimum is an explicit
  breaking compatibility change in package metadata and migration documentation
- Tool is designed to be simple and reliable for long-running backups
- A failed or incomplete backup must return a nonzero exit status and must not
  advance incremental state past missing pages
- SSL verification is configurable for APIs with certificate issues

## External Dependencies
- External APIs are user-configured REST endpoints
- Optional integrations: aria2p (download acceleration), pandas/pyarrow (parquet)
- Local filesystem storage is required for archives and exports
