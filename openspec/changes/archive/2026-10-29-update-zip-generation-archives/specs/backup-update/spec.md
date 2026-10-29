## ADDED Requirements
### Requirement: Update cost independent of archive size
An update SHALL compact only the archive of its own generation, so its disk
writes and temporary space are proportional to the pages it collected rather
than to the size of the existing backup.

#### Scenario: Large existing archive
- **WHEN** an update adds one page to a backup whose `storage.zip` is 10 GB
- **THEN** no copy of `storage.zip` is written

### Requirement: Full backup retires generation archives
Publishing a full backup SHALL retire the previous backup's generation
archives, deleting them only after the new state is committed. Resuming an
interrupted publication SHALL finish the retirement, after which only the new
backup's members are visible.

#### Scenario: Interrupted full publication
- **WHEN** a full run is interrupted after moving the generation archives aside but before committing state
- **THEN** `run full --resume` commits the state, deletes the retired archives and sends no HTTP requests
