# backup-sample Specification

## Purpose
Document the `run full --max-pages` sample run that previews live records without changing the project, maintained by apibackuper.

## Requirements
### Requirement: Sample run
`apibackuper run full --max-pages N` SHALL fetch at most N pages from the live
API with the project configuration, store them in a temporary location, print
the page count, record count and the first records, and exit. A sample run
SHALL NOT modify the published archive, the successful-run state or the
checkpoint.

#### Scenario: Check configuration on two pages
- **WHEN** a user runs `apibackuper run full --max-pages 2` on a page-mode project
- **THEN** two pages are requested, their records are previewed, and the project
  archive, state file and checkpoint are unchanged

#### Scenario: Pagination parameter ignored by the API
- **WHEN** the second sampled page repeats the first page's records
- **THEN** the sample run fails with the same error a full run reports

