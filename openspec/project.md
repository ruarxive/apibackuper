# Project Context

## Purpose
`apibackuper` is a CLI tool and Python library for backing up REST API data to
local storage. It focuses on iterating API endpoints, collecting full or
incremental datasets, and exporting archived data in multiple formats.

## Tech Stack
- Python 3.6+ CLI/library
- Typer for CLI commands
- Requests/urllib3 for HTTP
- JSON/YAML handling (jsonschema, PyYAML)
- XML parsing (lxml, xmltodict)
- Storage/export: zip, JSONL, gzip, zstd; optional parquet (pandas, pyarrow)

## Project Conventions

### Code Style
- Black formatting with 100-character line length
- isort using Black profile (line length 100)
- flake8 with E203/E501 ignored, max line length 100
- EditorConfig: 4-space indent, LF, trim trailing whitespace

### Architecture Patterns
- CLI entrypoint in `apibackuper.__main__` with command modules under `apibackuper/cmds/`
- Core logic split into modules (`core`, `auth`, `rate_limiter`, `storage`)
- Project configuration in YAML or INI with JSON schema validation
- Local archive storage (zip) with export helpers for multiple formats

### Testing Strategy
- pytest with coverage enabled (`tests/`), doctest modules on
- tox runs tests across Python 3.6–3.12 and separate lint/format/typecheck envs
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
- Must remain compatible with Python 3.6+
- Tool is designed to be simple and reliable for long-running backups
- SSL verification is configurable for APIs with certificate issues

## External Dependencies
- External APIs are user-configured REST endpoints
- Optional integrations: aria2p (download acceleration), pandas/pyarrow (parquet)
- Local filesystem storage is required for archives and exports
