# Test Suite for apibackuper

This directory contains the comprehensive test suite for the apibackuper project.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=apibackuper --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_common.py
```

### Run specific test class
```bash
pytest tests/test_common.py::TestEtreeToDict
```

### Run specific test
```bash
pytest tests/test_common.py::TestEtreeToDict::test_simple_xml
```

### Run with verbose output
```bash
pytest -v
```

### Run with markers
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Structure

- `conftest.py` - Shared fixtures and test utilities
- `test_common.py` - Tests for common utility functions (XML parsing, dict operations)
- `test_rate_limiter.py` - Tests for rate limiting functionality
- `test_auth.py` - Tests for authentication handlers
- `test_storage.py` - Tests for storage classes (ZipFileStorage, FilesystemStorage)
- `test_config_loader.py` - Tests for configuration loading and parsing
- `test_utils.py` - Tests for utility functions (file loading, CSV parsing, URL replacement)
- `test_http_client.py` - Tests for HTTP client with authentication and rate limiting
- `test_core.py` - Tests for CLI commands
- `test_project.py` - Tests for ProjectBuilder class

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

Tests are configured to run in CI environments using tox. See `tox.ini` for configuration.

```bash
# Run tests on all Python versions
tox

# Run tests on specific Python version
tox -e py39

# Run linting
tox -e lint

# Run type checking
tox -e typecheck
```

