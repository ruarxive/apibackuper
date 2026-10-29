# testing Specification

## Purpose
Document the regression coverage that the apibackuper test suite maintains.

## Requirements
### Requirement: Workflow regression coverage
The suite SHALL execute actual backup, resume, update, follow and export workflows
with mocked HTTP and real temporary storage, including destructive-failure regressions.

#### Scenario: Resume preservation regression
- **WHEN** the test suite runs
- **THEN** it verifies actual stored records before and after interruption and resume

### Requirement: Installable artifact verification
Pull requests SHALL build and install the wheel, verify CLI execution and bundled
schema access, and reject test packages in wheel contents.

#### Scenario: Wheel smoke check
- **WHEN** CI builds a wheel
- **THEN** the installed CLI and schema load work outside the source checkout

