## ADDED Requirements
### Requirement: Checkpoint persistence
The system SHALL write a checkpoint file at a configured interval containing
the last page or skip position, records processed, and storage offset.

#### Scenario: Checkpoint written during run
- **WHEN** a backup run reaches the checkpoint interval
- **THEN** the checkpoint file is updated with the latest position and counts

### Requirement: Resume from checkpoint
The system SHALL resume a run from the latest checkpoint when
`apibackuper run --resume` is specified.

#### Scenario: Resume continues from last checkpoint
- **WHEN** `--resume` is provided and a checkpoint exists
- **THEN** processing continues from the checkpoint position without re-fetching
  earlier pages
