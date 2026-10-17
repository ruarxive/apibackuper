# Test Suite for apibackuper

This directory contains unit and backup lifecycle tests for apibackuper.
Use Python 3.10+ and install the development extra from the repository root:

```bash
python -m pip install -e ".[dev]"
```

## Running Tests

### Run all tests
```bash
python -m pytest
```

### Run with coverage
```bash
python -m pytest --cov=apibackuper --cov-report=html
```

The shared `pyproject.toml` configuration already enables coverage reports and
enforces a 70% overall coverage floor. For focused test selections, use
`--no-cov` to avoid applying the whole-project coverage gate to a small subset.

### Run specific test file
```bash
python -m pytest --no-cov tests/test_common.py
```

### Run specific test class
```bash
python -m pytest --no-cov tests/test_common.py::TestEtreeToDict
```

### Run specific test
```bash
python -m pytest --no-cov tests/test_common.py::TestEtreeToDict::test_simple_xml
```

### Run with verbose output
```bash
pytest -v
```

### Run with markers

`unit`, `integration` and `slow` are registered in `pyproject.toml`, but the
current tests do not assign these markers. Select tests by file, class or
function as shown above. Marker filters such as `-m unit` only select tests
that carry that marker and exit with status 5 when nothing matches.

## Test Structure

- `conftest.py` - Shared fixtures and test utilities
- `test_common.py` - Tests for common utility functions (XML parsing, dict operations)
- `test_rate_limiter.py` - Tests for rate limiting functionality
- `test_auth.py` - Tests for authentication handlers
- `test_storage.py` - ZIP, SQLite and filesystem backend operations and legacy API deprecation
- `test_config_loader.py` - Tests for configuration loading and parsing
- `test_utils.py` - Tests for utility functions (file loading, CSV parsing, URL replacement)
- `test_http_client.py` - Tests for HTTP client with authentication and rate limiting
- `test_core.py` - Tests for CLI commands
- `test_project.py` - Tests for ProjectBuilder class
- `test_backup_workflow.py` - Full backup, interrupted resume, update generations, follow, export and failure recovery with real temporary storage
- `test_runner.py`, `test_fetch.py`, `test_single_request.py` - Ordered page collection, request construction and shared HTTP execution
- `test_export.py`, `test_where_filter.py` - Record extraction, field projection and export filters
- `test_profile.py`, `test_state_resume.py` - Offline estimates and state/checkpoint round trips
- `test_substitute_env_vars.py`, `test_validate_config.py` - Environment substitution and configuration validation
- `test_documented_cli.py` - Real project logging initialization, verbose output and safe failure on invalid export filters
- `test_docs_examples.py` - Execute marked Quick Start/Python API snippets with real localhost HTTP, temporary storage and exact output checks
- `test_docs_validation.py` - Check that the documentation gate rejects unknown keys, invalid types/JSON and incomplete full configurations

## Test Coverage

The test suite aims to cover:
- Unit tests for individual functions and classes
- Integration tests for component interactions
- Error handling and edge cases
- Configuration parsing (INI and YAML)
- Authentication methods (Basic, Bearer, API Key, OAuth2)
- Rate limiting functionality
- Storage operations
- HTTP client functionality
- CLI command execution

## Fixtures

Common fixtures available in `conftest.py`:
- `temp_dir` - Temporary directory for test files
- `sample_config_ini` - Sample INI configuration file
- `sample_config_yaml` - Sample YAML configuration file
- `mock_requests_session` - Mock requests session
- `sample_json_data` - Sample JSON data
- `sample_xml_data` - Sample XML data
- `sample_csv_data` - Sample CSV file

## Running Tests in CI

CI runs pytest directly on Python 3.10–3.13 on Ubuntu and macOS. Local tox
environments cover the same Python versions and share the pytest configuration.
Only environments with installed interpreters can run locally; see `tox.ini`.

```bash
# Run tests on all Python versions
tox

# Run tests on specific Python version
tox -e py313

# Run linting
tox -e lint

# Run type checking
tox -e typecheck

# Check Black and isort formatting
tox -e format
```

Validate the shipped configuration examples without external HTTP requests:

```bash
python -m scripts.validate_examples
```

This also checks shipped JSON files and Markdown YAML/JSON blocks. Run the
documentation walkthrough on its own with
`python -m pytest --no-cov tests/test_docs_examples.py`; it starts and closes
an ephemeral localhost server automatically and never fetches public APIs.

`test_backup_workflow.py` exercises real temporary ZIP, SQLite and filesystem
storage through backup, interrupted resume, update, follow and export. It also
checks abrupt process termination, publication recovery, installed-record
preservation, credential diagnostics and nonzero command failures. The shared
pytest configuration enforces a 70% overall coverage floor.
