## ADDED Requirements
### Requirement: Manifest before publication
The system SHALL write a generation's `manifest-sha256.txt` and `run.json`
into staged storage before publishing it. Resuming an interrupted publication
SHALL write any manifest that is still missing before the backup is reported
complete.

#### Scenario: Interrupted publication
- **WHEN** a run is interrupted after collection but before its manifest is written
- **THEN** `run full --resume` writes the manifest and publishes the backup without new HTTP requests
