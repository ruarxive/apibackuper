## ADDED Requirements
### Requirement: Reserved capture member names
Storage backends SHALL treat only members whose basename starts with `page_`
as pages. Members named `exchange_N.json` and `raw_N.<ext>` SHALL be stored and
listed as objects, and SHALL NOT be counted, exported as records or used to
compute resume positions.

#### Scenario: Capture members ignored by page listing
- **WHEN** an archive contains `page_1.json`, `exchange_1.json` and `raw_1.xml`
- **THEN** listing pages returns only `page_1.json`
