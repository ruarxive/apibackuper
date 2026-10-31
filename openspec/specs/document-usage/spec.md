# document-usage Specification

## Purpose
Document the implemented document-usage behavior maintained by apibackuper.
## Requirements
### Requirement: Quickstart guides
The system SHALL provide quickstart guides for common API scenarios including
page-based, skip-based, authenticated, and followed resources.

#### Scenario: Quickstart coverage
- **WHEN** a user opens the documentation
- **THEN** quickstarts are available for each common scenario

### Requirement: Templates and FAQ
The system SHALL provide YAML templates in `examples/` and an FAQ section for
common configuration issues.

#### Scenario: Templates and FAQ available
- **WHEN** a user browses `examples/` and README docs
- **THEN** templates and FAQs are present for common tasks

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

