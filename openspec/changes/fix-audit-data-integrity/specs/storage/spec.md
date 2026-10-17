## ADDED Requirements
### Requirement: Backend lifecycle parity
ZIP, SQLite and filesystem backends SHALL support full, resume, update and export
through the same page/object interface and preserve legacy flat pages.

#### Scenario: Filesystem lifecycle
- **WHEN** a filesystem backup is interrupted, resumed, updated and exported
- **THEN** all retained generations are readable and no saved records are lost

### Requirement: Idempotent logical members
Saving an existing logical member SHALL replace that member without duplicate exports.

#### Scenario: Replayed checkpoint page
- **WHEN** a legacy checkpoint causes a saved ZIP member to be fetched again
- **THEN** export includes its latest content once
