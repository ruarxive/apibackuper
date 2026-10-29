# backup-integrity Specification

## Purpose
Document the implemented full-backup staging, generation retention and checkpoint integrity maintained by apibackuper.

## Requirements
### Requirement: Safe full backup and resume
The system SHALL stage fresh full backups and publish them only after successful
completion. Resume SHALL preserve previously stored pages and accept legacy checkpoints.

#### Scenario: Interrupted full run resumes
- **WHEN** a full run fails after saving a page and is resumed
- **THEN** the earlier complete backup remains intact until successful publication
- **AND** all pages saved before interruption remain in the completed backup

### Requirement: Lossless incremental generations
Updates SHALL retain previous pages and use a stable generation identifier across resume.

#### Scenario: Update starts at page one
- **WHEN** an update fetches page one after a prior full backup
- **THEN** both the old page and the new generation are available for export

### Requirement: Durable contiguous checkpoints
Checkpoint positions SHALL never pass an unsaved page. Failed or partial runs
SHALL leave the last successful incremental state unchanged and exit unsuccessfully.

#### Scenario: Middle page fails
- **WHEN** page two fails and page three succeeds
- **THEN** resume retries page two and state does not advance beyond the failed run

### Requirement: Unified page outcome accounting
One runner SHALL own progress and checkpoint counters and stop sequential and
parallel processing at the same logical end of data.

#### Scenario: Parallel short page
- **WHEN** a parallel batch contains the final short page
- **THEN** no later batch is fetched and that saved page is counted exactly once

