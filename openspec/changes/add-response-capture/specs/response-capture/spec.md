## ADDED Requirements
### Requirement: Exchange records
While `storage.capture.metadata` is enabled, the system SHALL store
`exchange_N.json` beside every saved `page_N.json`, in the same generation
prefix. The record SHALL contain the request method, final URL, request
parameters or body, response status and reason, response headers, fetch time
in UTC, elapsed time, SHA-256 of the response body, content type,
apibackuper version and run ID.

#### Scenario: Page saved with its exchange
- **WHEN** a full run saves `page_1.json`
- **THEN** `exchange_1.json` exists with the status, headers and fetch time of that response

#### Scenario: Update generation
- **WHEN** an update saves `runs/<id>/page_1.json`
- **THEN** `runs/<id>/exchange_1.json` is saved

### Requirement: Credential redaction in exchanges
Exchange records SHALL NOT contain credentials. Sensitive request headers,
parameters and URL query values, and the response `Set-Cookie` and
`Authorization` headers, SHALL be replaced with a redaction marker, and the
record SHALL indicate that redaction occurred.

#### Scenario: Bearer token not stored
- **WHEN** a request is sent with `Authorization: Bearer secret`
- **THEN** `exchange_N.json` does not contain `secret`
- **AND** the record is marked as redacted

### Requirement: Original response bytes
With `storage.capture.raw_body: auto`, the system SHALL store the original
response body as `raw_N.<ext>` whenever the saved page differs from it, for
example for XML or HTML responses. With `always` it SHALL store every body;
with `never` it SHALL store none.

#### Scenario: XML response kept verbatim
- **WHEN** an XML API page is saved
- **THEN** `raw_1.xml` contains the exact bytes received
- **AND** `page_1.json` still contains the normalized records used by export

### Requirement: WARC export
`apibackuper export --format warc <file>` SHALL write WARC/1.1 `request` and
`response` records for every page with an exchange record. It SHALL use the raw
body as the response payload when present, set `WARC-Date` to the fetch time,
and report how many pages were skipped for lack of an exchange record.

#### Scenario: WARC round trip
- **WHEN** a captured backup is exported with `--format warc`
- **THEN** reading the file yields one response record per page with the original status and payload

#### Scenario: Legacy archive
- **WHEN** an archive without exchange records is exported to WARC
- **THEN** the command reports that all pages were skipped and does not write records for them

### Requirement: Capture can be disabled
Setting `storage.capture.metadata: false` SHALL stop writing exchange records
without changing the pages that are saved.

#### Scenario: Capture disabled
- **WHEN** metadata capture is disabled
- **THEN** only `page_N.json` members are written
