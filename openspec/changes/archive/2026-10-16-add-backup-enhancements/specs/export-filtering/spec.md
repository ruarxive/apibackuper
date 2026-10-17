## ADDED Requirements
### Requirement: Export field selection and filters
The system SHALL allow export commands to select fields and apply simple filters
over records before writing the output.

#### Scenario: Export with fields and filter
- **WHEN** `apibackuper export` is called with `--fields` and `--where`
- **THEN** the output includes only selected fields and matching records

### Requirement: Export dependency validation
The system SHALL provide clear errors when an export format requires missing
dependencies.

#### Scenario: Parquet dependency missing
- **WHEN** a Parquet export is requested without required dependencies
- **THEN** the command fails with an error describing the missing packages
