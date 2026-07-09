## ADDED Requirements
### Requirement: Dry-run execution mode
The system SHALL support a `--dry-run` flag on run, update, and follow
commands that validates configuration and prints an execution plan without
making any HTTP requests.

#### Scenario: Dry-run with valid config
- **WHEN** a user runs `apibackuper run --dry-run`
- **THEN** the system loads and validates the config
- **AND** it prints the number of pages, estimated records, and storage path
- **AND** no HTTP requests are made
- **AND** the exit code is 0

#### Scenario: Dry-run with invalid config
- **WHEN** a user runs `apibackuper run --dry-run` with a malformed config
- **THEN** the system reports the specific validation error
- **AND** no HTTP requests are made
- **AND** the exit code is non-zero

#### Scenario: Dry-run with detect
- **WHEN** a user runs `apibackuper run --dry-run` with `detect: true` in config
- **THEN** the system makes a single HTTP request to inspect the API
- **AND** prints suggested pagination and data key configuration
- **AND** does not proceed to full download
