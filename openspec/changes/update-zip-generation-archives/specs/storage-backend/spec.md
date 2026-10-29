## ADDED Requirements
### Requirement: Per-generation ZIP archives
With ZIP storage, the backend SHALL store members named `runs/<id>/...` in the
archive `storage.zip.runs/<id>.zip` beside `storage.zip`, and SHALL list and read members of
the base archive, of legacy generations inside it and of every generation
archive as one set of names.

#### Scenario: Update leaves the base archive untouched
- **WHEN** an update saves `runs/<id>/page_1.json`
- **THEN** the member is written to `storage.zip.runs/<id>.zip`
- **AND** `storage.zip` is not rewritten

#### Scenario: Mixed legacy layout
- **WHEN** `storage.zip` contains `runs/old/page_1.json` and `runs/new.zip` exists
- **THEN** listing pages returns the base pages, `runs/old/page_1.json` and the pages of `runs/new.zip`
