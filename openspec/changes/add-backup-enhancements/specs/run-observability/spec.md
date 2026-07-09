## ADDED Requirements
### Requirement: Progress reporting
The system SHALL display pages processed, estimated total pages, current speed,
and ETA during a run.

#### Scenario: Progress output during run
- **WHEN** a backup run is in progress
- **THEN** progress output includes pages processed, total estimate, speed, and ETA

### Requirement: End-of-run summary
The system SHALL display a summary with total records, total bytes, and errors
grouped by HTTP status after completion.

#### Scenario: Summary after completion
- **WHEN** a run completes
- **THEN** the summary output includes counts and grouped errors

### Requirement: Machine-readable run info
The system SHALL extend `apibackuper info --json` to include last run status,
start and end timestamps, record count, and total size.

#### Scenario: Info JSON includes run metadata
- **WHEN** a user runs `apibackuper info --json`
- **THEN** the output includes run status, timestamps, and counts
