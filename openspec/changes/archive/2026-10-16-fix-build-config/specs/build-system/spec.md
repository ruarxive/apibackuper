## MODIFIED Requirements
### Requirement: Package license declaration
The system SHALL declare the MIT license consistently across all build
artifacts.

#### Scenario: License metadata consistency
- **WHEN** building the package via `setup.py` or `pyproject.toml`
- **THEN** the resulting metadata reports the MIT license
- **AND** the PyPI classifier is `License :: OSI Approved :: MIT License`

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
- **THEN** the test matrix runs on Python 3.8 through 3.12
- **AND** no CI time is wasted on EOL Python 3.6 or 3.7

### Requirement: Pre-commit validation hooks
All configured pre-commit hooks SHALL execute successfully on valid files.

#### Scenario: JSON file validation
- **WHEN** a developer commits a valid `.json` file
- **THEN** the JSON validation pre-commit hook passes
- **AND** no false-positive failure blocks the commit

### Requirement: flake8 line-length enforcement
The linter SHALL enforce the configured maximum line length on all source
files.

#### Scenario: Long line detection
- **WHEN** a source file contains a line exceeding 100 characters
- **THEN** flake8 reports the violation
- **AND** CI fails until the line is corrected
