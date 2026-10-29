# pagination Specification

## Purpose
Document the implemented pagination behavior maintained by apibackuper.
## Requirements
### Requirement: Pagination page count calculation
The system SHALL compute the number of pages using integer division so that
the result is always a whole number suitable for use as a range bound.

#### Scenario: Page count for non-divisible totals
- **WHEN** the total record count is not evenly divisible by the page limit
- **THEN** the page count is rounded up to the nearest integer
- **AND** no `TypeError` is raised when iterating pages

### Requirement: Change-key value comparison
The system SHALL compare change-key values using their natural type
(numeric or temporal) rather than lexicographic string ordering.

#### Scenario: Numeric change keys
- **WHEN** a change-key value is a numeric ID such as `10`
- **AND** the previous value was `9`
- **THEN** the new value is correctly recognized as greater

### Requirement: URL query construction
The system SHALL use `?` as the query-string initiator and `&` as the
parameter separator when constructing URLs in query mode, and `;` only as
a parameter separator in params mode.

#### Scenario: Params mode URL construction
- **WHEN** constructing a URL in params mode
- **THEN** the query-string initiator is `;` and the separator is `;`
- **AND** no `?` character appears in the constructed URL

### Requirement: Cursor-based pagination
The system SHALL support `project.iterate_by: cursor`. It SHALL read the next
token from `data.next_cursor_key` in each response and send it as
`params.cursor_param` in the following request. Collection SHALL end when the
token is missing, null or empty, or when a page has no records.

#### Scenario: Cursor chain to the end
- **WHEN** three responses return tokens `a`, `b` and no token
- **THEN** three pages are saved as `page_1.json` to `page_3.json`
- **AND** the second and third requests send the tokens `a` and `b`

#### Scenario: Variable page sizes
- **WHEN** a cursor response contains fewer records than `page_size_limit` and still has a token
- **THEN** collection continues with the next token

### Requirement: Next-URL pagination
The system SHALL support `project.iterate_by: next_url`. It SHALL request the
URL at `data.next_url_key`, resolved against the current request URL, until no
next URL is present. Base request parameters SHALL be sent only with the first
request. A next URL on a different host SHALL fail the run unless
`params.allow_cross_host_next` is true.

#### Scenario: Relative next URL
- **WHEN** a response from `https://api.example/items` contains `"next": "/items?page=2"`
- **THEN** the next request is sent to `https://api.example/items?page=2`

#### Scenario: Cross-host next URL rejected
- **WHEN** a next URL points to another host and cross-host next URLs are not allowed
- **THEN** the run fails as incomplete before sending that request

### Requirement: Link-header pagination
The system SHALL support `project.iterate_by: link_header`. It SHALL follow the
RFC 8288 `Link` header target with `rel="next"` until the header has no next link.

#### Scenario: Link header ends the run
- **WHEN** the second response has no `rel="next"` link
- **THEN** collection stops after saving two pages

### Requirement: Cursor loop detection
The system SHALL fail a cursor, next-URL or Link-header run as incomplete when
a token or URL repeats within the run, without publishing the backup.

#### Scenario: Repeated token
- **WHEN** the API returns token `a` on two consecutive responses
- **THEN** the run exits unsuccessfully and the previous backup remains published

### Requirement: Cursor resume
Checkpoints for cursor, next-URL and Link-header runs SHALL store the next
token or URL together with the contiguous saved prefix. `--resume` SHALL
continue from that stored cursor without requesting saved pages again.

#### Scenario: Resume after interruption
- **WHEN** a cursor run is interrupted after saving page 2
- **THEN** `run full --resume` sends the cursor returned by page 2
- **AND** pages 1 and 2 are not requested again

### Requirement: Sequential cursor collection
The configuration validator SHALL reject `request.parallelism` greater than 1
together with a cursor, next-URL or Link-header iteration mode.

#### Scenario: Parallel cursor configuration
- **WHEN** `iterate_by` is `cursor` and `request.parallelism` is 4
- **THEN** `validate-config` reports an error and `run` does not start

