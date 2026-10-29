# backup-resume Specification

## Purpose
Document the implemented backup-resume behavior maintained by apibackuper.
## Requirements
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

### Requirement: Manifest before publication
The system SHALL write a generation's `manifest-sha256.txt` and `run.json`
into staged storage before publishing it. Resuming an interrupted publication
SHALL write any manifest that is still missing before the backup is reported
complete.

#### Scenario: Interrupted publication
- **WHEN** a run is interrupted after collection but before its manifest is written
- **THEN** `run full --resume` writes the manifest and publishes the backup without new HTTP requests

