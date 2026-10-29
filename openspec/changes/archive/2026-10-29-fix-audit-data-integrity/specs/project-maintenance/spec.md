## ADDED Requirements
### Requirement: Consistent support and tool policy
Metadata, CI, tox, pre-commit and documentation SHALL consistently declare Python
3.10+ and use the same formatter and linter configuration.

#### Scenario: Developer and CI formatting
- **WHEN** formatting runs through pre-commit or CI
- **THEN** the same pinned formatter and shared configuration apply

### Requirement: Current examples and specifications
All shipped YAML examples/templates SHALL validate, documented versions SHALL
match package metadata, and completed OpenSpec changes SHALL have current base specs.

#### Scenario: Repository validation
- **WHEN** repository checks run
- **THEN** every example validates and strict OpenSpec validation succeeds
