## ADDED Requirements
### Requirement: Detection command
The system SHALL provide an `apibackuper detect` command that samples a project
endpoint and suggests pagination mode, data key, and total count key, and can
optionally write a starter YAML file.

#### Scenario: Detection output
- **WHEN** a user runs `apibackuper detect` for a project
- **THEN** the command prints suggested `iterate_by`, `data_key`, and
  `total_number_key` values

### Requirement: Detection flag in config
The system SHALL support a `project.detect: true` setting to run detection and
apply suggestions during a backup run.

#### Scenario: Detect flag applies suggestions
- **WHEN** `project.detect` is enabled for a run
- **THEN** detected pagination and data keys are applied for that run
