# follow-links Specification

## Purpose
Document the implemented follow-links behavior maintained by apibackuper.

## Requirements

### Requirement: Follow rules list
The system SHALL support a list of follow rules, each defining follow mode,
pattern, data key, and optional pagination settings.

#### Scenario: Multiple follow rules
- **WHEN** multiple follow rules are configured
- **THEN** each rule is executed for its matching items
