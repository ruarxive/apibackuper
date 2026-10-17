## ADDED Requirements
### Requirement: Follow rules list
The system SHALL support a list of follow rules, each defining follow mode,
pattern, data key, and optional pagination settings.

#### Scenario: Multiple follow rules
- **WHEN** multiple follow rules are configured
- **THEN** each rule is executed for its matching items

### Requirement: Multi-level followed pagination
The system SHALL support pagination settings for followed endpoints, including
multi-level follow chains.

#### Scenario: Paginated followed endpoint
- **WHEN** a followed endpoint includes pagination settings
- **THEN** the follow requests iterate using the configured pagination mode
