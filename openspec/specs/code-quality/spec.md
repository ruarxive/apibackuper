# code-quality Specification

## Purpose
Document the implemented code-quality behavior maintained by apibackuper.

## Requirements

### Requirement: Error handling for missing config files
The system SHALL report missing config files through a single code path
rather than copy-pasting the same error message block across multiple
command methods.

#### Scenario: Config file not found
- **WHEN** a user runs any command and the config file does not exist
- **THEN** a consistent error message is displayed
- **AND** the system exits with a non-zero status code

### Requirement: CLI command error handling
The system SHALL handle common exceptions (file not found, permission errors,
runtime errors) through a shared mechanism rather than per-command
copy-pasted try/except blocks.

#### Scenario: Permission error on config file
- **WHEN** a user runs a command without read permission on the config file
- **THEN** the error is caught and reported consistently across all commands
