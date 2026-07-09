## MODIFIED Requirements
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
