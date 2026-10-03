# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.12] - 2025-11-14

### Added
- **Zstandard (zstd) compression format support** for export functionality
  - Export data as zstd-compressed files with maximum compression level
  - Auto-detection of `.zst` file extension
  - Requires `zstandard` library (included in dependencies)
- Fixed setup.py build issue to avoid importing module during build

### Changed
- Updated export format documentation to include zstd alongside jsonl, gzip, and parquet
- Improved SSL certificate verification handling at session level

### Fixed
- Fixed logfile initialization to ensure it's always available
- Improved error handling for missing logfile attribute

## [1.0.13] - 2026-10-03

### Added (this release)
- **Docs**: Docusaurus documentation site in `docs/`, organized like undatum (getting started, CLI reference, configuration, examples) and ready for GitHub Pages at `https://ruarxive.org/apibackuper/`
- **Docs**: `SECURITY.md` documenting the "config = executable code" model, hook context shapes, credential redaction, and reporting vulnerabilities
- **Security**: SSL certificate verification is now configurable in `follow`, `estimate`, and `getfiles` modes (previously hardcoded to disabled)
- **Security**: Path traversal prevention in filesystem storage
- **Security**: SQL injection prevention in SQLite storage backend via table name allowlist
- **Security**: Warning logged when SSL verification is disabled
- **Security**: Authorization headers and token query params are redacted in the log file via `apibackuper.cmds.utils.{redact_headers,redact_params}` (P2.21)
- **Security**: Zip member names sanitized via `safe_member_name` so server-controlled filenames cannot escape the archive (P2.22)
- **Security**: Query-string building uses `urllib.parse.urlencode` so ``&``/``=``/``#``/whitespace in values cannot extend or replace query parameters (P2.23)
- **Security**: OAuth2 refresh now honours `verify_ssl`, defaults to a 30 s timeout, logs non-200 responses with the body, and captures rotated refresh tokens (P2.24)
- **Security**: Bearer header suppression when oauth2 token is missing or empty (P2.25)
- **Security**: Logging setup moved out of import time into `cli()` so importing the package does not create `apibackuper.log` in cwd (P2.26)
- **Schema**: `error_handling.retry_on_errors` now accepts YAML lists, INI strings, and single integers; crashes on `[500, 502]` schema-legal input are fixed
- **Schema**: `params.default_delay: 0.5` (float) no longer crashes the loader via `getint`; new `YAMLConfigParser.getfloat()` accepts both int and float strings
- **Schema**: `storage.storage_type: "filesystem"` is now a real backend (`FilesystemStorageBackend`) instead of raising `ValueError`
- **Bug fix**: parallel-mode early stop now closes the storage backend on every exit path (zip central directory is no longer skipped on early error)
- **Bug fix**: OAuth2 retry no longer crashes with `TypeError: got multiple values for keyword argument 'params'`
- **Bug fix**: `--verbose` flag is no longer a silent no-op (the previous guard mistook `FileHandler` for a console handler)
- **Bug fix**: `enable_logging` now sets the root logger to DEBUG so `logging.info(...)` traces actually land in the log file
- **Bug fix**: rate limiter no longer drifts above the configured `requests_per_second` after a sleep (was double-counting the post-sleep time)
- **Bug fix**: falsy values (`0`, `False`, `""`, `{}`) are no longer silently dropped by `get_dict_value` / `set_dict_value`
- **Bug fix**: early-stop detection compares records to `page_size_limit` instead of bytes; empty JSON pages (`{"data": []}`) trigger early-stop instead of fetching 20 000 pages of nothing
- **Build**: Minimum Python raised from 3.6 to 3.8; 3.13 added to the CI matrix
- **Build**: CI now runs on macOS in addition to Ubuntu
- **Build**: pytest-timeout enforced in CI so hanging tests can't burn hours
- **Build**: `--cov-fail-under=29` coverage gate active in `pyproject.toml`
- **Build**: `setup.py` deleted (PEP 621 `pyproject.toml` is authoritative); `pyproject.toml` license uses PEP 639 `license = "MIT"`
- **Tests**: 56 new regression tests lock in every P0/P1/P2 fix
- **Tests**: 14 mocked-Session tests for `_single_request` (timeouts, 4xx/5xx, 401-refresh)
- **Tests**: 9 state/resume round-trip tests

### Removed
- `init()` and `to_package()` methods (unfinished / unused)
- Stray `flake8` file (accidental redirect)
- `pylint_report.txt` (82 KB committed junk)
- `.coveragerc` (silently overrode `pyproject.toml`)
- `[tool.flake8]` section in `pyproject.toml` (flake8 reads `setup.cfg`, not pyproject)
- `[tool.flake8]`-style duplicate configuration

## [1.0.12] - 2025-11-14

### Added
- **Zstandard (zstd) compression format support** for export functionality
  - Export data as zstd-compressed files with maximum compression level
  - Auto-detection of `.zst` file extension
  - Requires `zstandard` library (included in dependencies)
- Fixed setup.py build issue to avoid importing module during build

### Changed
- Updated export format documentation to include zstd alongside jsonl, gzip, and parquet
- Improved SSL certificate verification handling at session level

### Fixed
- Fixed logfile initialization to ensure it's always available
- Improved error handling for missing logfile attribute

### Fixed
- **Bug**: Integer division crash in pagination page count calculation (`/` → `//`) for non-divisible totals
- **Bug**: Dead no-op branch in `run()` start_page assignment
- **Bug**: Lexicographic string comparison for change-key values (removed erroneous `str()` cast)
- **Bug**: URL `_url_replacer` non-query mode producing `?` instead of `;` as query initiator
- **Bug**: Thread-unsafe shared counters in parallel page fetching (added `threading.Lock`)
- **Bug**: File handle leaks in `getfiles()` download loop (added `try/finally` cleanup)
- **Bug**: File handle leak in `follow()` headers.json loading (switched to `with` statement)

### Removed
- **Dead code**: Deleted `apibackuper/cmds/http_client.py` (227 lines, never imported)
- **Dead code**: Deleted `tests/test_http_client.py` (tested dead code)
- **Cleanup**: Removed commented-out code blocks and unused imports

## [1.0.11] - 2025-11-14

### Added
- **YAML configuration format support** alongside existing INI format
  - Automatic detection of `apibackuper.yaml` or `apibackuper.yml` files
  - Falls back to `apibackuper.cfg` if no YAML file is found
  - JSON schema validation for YAML configurations
- **Authentication support** for protected APIs:
  - Basic authentication (username/password)
  - Bearer token authentication
  - API Key authentication (custom header support)
  - OAuth2 authentication with token refresh
  - Support for reading credentials from files for security
- **Rate limiting functionality** to prevent API throttling:
  - Configurable requests per second, minute, and hour
  - Token bucket algorithm for per-second limits
  - Sliding window for per-minute and per-hour limits
  - Burst size configuration
- **Request configuration section**:
  - Configurable timeouts (total, connect, read)
  - SSL certificate verification control
  - Custom user agent
  - Proxy support
  - Redirect handling configuration
- **Enhanced export functionality**:
  - Parquet format support (requires pandas and pyarrow)
  - Auto-detection of export format from file extension
  - Explicit format specification option
- **Improved error handling**:
  - Better SSL error messages with actionable suggestions
  - Enhanced retry mechanisms
  - More descriptive error messages

### Changed
- Improved error messages for SSL certificate verification failures
- Enhanced retry logic for better reliability

### Fixed
- Better handling of SSL certificate verification errors
- Improved error recovery mechanisms

## [1.0.10] - 2024-XX-XX

### Changed
- Minor improvements and bug fixes

## [1.0.9] - 2024-XX-XX

### Changed
- Code improvements and dependency updates

## [1.0.8] - 2023-03-13

### Added
- Python scripts support to extract data from HTML web pages
- 'sozd' example demonstrating scripts usage
- Custom data extraction capabilities

## [1.0.7] - 2021-11-04

### Fixed
- "continue" mode now supports both "run" and "follow" commands
- Users can resume interrupted backups with `apibackuper run continue`
- Improved resume capability for follow operations

## [1.0.6] - 2021-11-01

### Added
- `default_delay` configuration option for request delays
- `retry_delay` configuration option for retry timing
- `retry_count` configuration option for error handling
- Automatic retry on HTTP status 500 or 503 errors
- Retry mechanism continues until HTTP 200 or retry_count is reached

### Changed
- Improved error handling with configurable retry behavior

## [1.0.5] - 2021-05-31

### Fixed
- Minor bug fixes

## [1.0.4] - 2021-05-31

### Added
- `start_page` configuration option for APIs that don't start at page 1
- Support for data returned as JSON array (when data_key is not provided)
- Initial code for Frictionless Data packaging implementation

## [1.0.3] - 2020-10-28

### Added
- aria2 download support for faster file downloads
- Several new configuration options

## [1.0.2] - 2020-09-20

### Added
- `follow` command to make additional requests for downloaded data
- `getfiles` command to retrieve files linked with API objects
- Permanent storage directory "storage" instead of temporary "temp" directory

### Changed
- Storage location changed from temporary "temp" to permanent "storage" directory

## [1.0.1] - 2020-08-14

### Added
- First public release on PyPI
- Initial GitHub repository setup

---

## Release Notes Format

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

[Unreleased]: https://github.com/datacoon/apibackuper/compare/v1.0.12...HEAD
[1.0.12]: https://github.com/datacoon/apibackuper/compare/v1.0.11...v1.0.12
[1.0.11]: https://github.com/datacoon/apibackuper/compare/v1.0.10...v1.0.11
[1.0.10]: https://github.com/datacoon/apibackuper/compare/v1.0.9...v1.0.10
[1.0.9]: https://github.com/datacoon/apibackuper/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/datacoon/apibackuper/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/datacoon/apibackuper/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/datacoon/apibackuper/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/datacoon/apibackuper/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/datacoon/apibackuper/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/datacoon/apibackuper/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/datacoon/apibackuper/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/datacoon/apibackuper/releases/tag/v1.0.1

