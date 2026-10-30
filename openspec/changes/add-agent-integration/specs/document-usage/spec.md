## ADDED Requirements

### Requirement: LLM-oriented documentation
The documentation site SHALL publish `llms.txt` with a link to the agent skill
and `llms-full.txt` containing the configuration reference, pagination, HTTP
request files and hooks pages as plain Markdown in one file. CI SHALL fail when
`llms-full.txt` is older than its source pages.

#### Scenario: Agent fetches full documentation
- **WHEN** an agent fetches `https://ruarxive.org/apibackuper/llms-full.txt`
- **THEN** it receives the configuration reference and pagination rules in one response

### Requirement: Supported pagination is described consistently
Every documentation page that lists pagination modes SHALL describe `cursor`,
`next_url` and `link_header` as supported.

#### Scenario: When-to-use page
- **WHEN** a user reads the API contract table on the when-to-use page
- **THEN** cursor tokens and next-link traversal are listed as supported starting points
