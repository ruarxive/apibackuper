# build-system Specification

## Purpose
Document the implemented build-system behavior maintained by apibackuper.

## Requirements

### Requirement: Package license declaration
The system SHALL declare the MIT license consistently across all build
artifacts.

#### Scenario: License metadata consistency
- **WHEN** building the package through the PEP 517 backend in `pyproject.toml`
- **THEN** the resulting metadata reports the MIT license
- **AND** the license expression is `MIT`

### Requirement: Package dependencies
The package SHALL declare all runtime dependencies required by features
shipped in the release.

#### Scenario: Zstandard export feature
- **WHEN** a user installs the package from PyPI
- **THEN** the `zstandard` package is automatically installed
- **AND** the `apibackuper export` command with zstd format works without
  manual dependency installation

### Requirement: CI test matrix
The CI pipeline SHALL test only against Python versions that are officially
supported and compatible with the declared dependencies.

#### Scenario: CI runs on supported versions
- **WHEN** a pull request is opened
- **THEN** the test matrix runs on Python 3.10 through 3.13
- **AND** unsupported Python 3.8 and 3.9 are excluded

### Requirement: Pre-commit validation hooks
All configured pre-commit hooks SHALL execute successfully on valid files.

#### Scenario: JSON file validation
- **WHEN** a developer commits a valid `.json` file
- **THEN** the JSON validation pre-commit hook passes
- **AND** no false-positive failure blocks the commit

### Requirement: Shared formatting and lint configuration
Black SHALL use a 100-character target line length and flake8 SHALL use the
shared repository configuration, including documented legacy stylistic ignores.

#### Scenario: Consistent developer checks
- **WHEN** developer tools or CI check source files
- **THEN** the same Black version and shared flake8 configuration apply
