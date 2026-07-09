## MODIFIED Requirements
### Requirement: CLI command test assertions
Each CLI test SHALL assert specific expected outcomes rather than accepting
any possible exit code.

#### Scenario: Successful create command
- **WHEN** the `create` command is invoked with valid arguments
- **THEN** the test asserts `exit_code == 0`
- **AND** it verifies expected output or side effects

#### Scenario: Failed command with missing config
- **WHEN** a command is invoked with a nonexistent project path
- **THEN** the test asserts `exit_code == 1`
- **AND** it verifies the error message contains relevant information

### Requirement: Core business logic coverage
The test suite SHALL cover the main execution paths of `ProjectBuilder`
methods that constitute the tool's primary value.

#### Scenario: Run with paginated API
- **WHEN** `ProjectBuilder.run()` is called against a paginated endpoint
- **THEN** test mocks HTTP responses for each page
- **AND** verifies all pages are fetched and stored correctly

#### Scenario: Follow mode item extraction
- **WHEN** `ProjectBuilder.follow()` is called with `follow_mode: item`
- **THEN** test mocks the index response and follow-up responses
- **AND** verifies each item URL is constructed and fetched

#### Scenario: Export to JSONL
- **WHEN** `ProjectBuilder.export()` is called with JSONL format
- **THEN** test verifies the output file contains one JSON object per line
- **AND** all records are present and valid JSON

### Requirement: Edge case coverage
The test suite SHALL cover edge cases that have historically been sources
of bugs.

#### Scenario: Non-divisible pagination totals
- **WHEN** total records are not evenly divisible by page size
- **THEN** tests verify the correct number of pages is fetched
- **AND** no float-to-integer errors occur

#### Scenario: Rate limiter with all limits active
- **WHEN** requests-per-second, per-minute, and per-hour limits are all set
- **THEN** tests verify the limiter enforces the most restrictive limit
- **AND** no deadlock or starvation occurs

#### Scenario: Storage path traversal attempt
- **WHEN** a path containing `../` is passed to `FilesystemStorage`
- **THEN** the test verifies the path is sanitized or rejected
