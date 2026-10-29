# archive-fixity Specification

## Purpose
Document the per-generation SHA-256 manifests, run records and `verify` command maintained by apibackuper.

## Requirements
### Requirement: Generation manifests
Every successful `run` or `update` SHALL write `manifest-sha256.txt` into the
prefix of the generation it publishes. The manifest SHALL list the SHA-256
digest and member name of every page and captured member of that generation,
one `<digest>  <member>` line each, sorted by member name.

#### Scenario: Full backup manifest
- **WHEN** a full run saves `page_1.json` and `page_2.json`
- **THEN** the published archive contains `manifest-sha256.txt` with two lines whose digests match those members

#### Scenario: Update manifest
- **WHEN** an update publishes generation `runs/<id>/`
- **THEN** `runs/<id>/manifest-sha256.txt` lists only that generation's members

### Requirement: Run metadata
Every successful run SHALL write `run.json` beside its manifest, containing the
apibackuper version, run ID, mode, start and end time in UTC, page and record
counts, the API-reported total when known, and the SHA-256 of the resolved
configuration with credentials redacted.

#### Scenario: Configuration hash excludes secrets
- **WHEN** two runs differ only in the value of `auth.token`
- **THEN** their `run.json` configuration hashes are equal

### Requirement: Verify command
`apibackuper verify` SHALL recompute the digest of every member listed in each
generation manifest and report changed, missing and unlisted members. It SHALL
exit with status 1 when any listed member is changed or missing. With
`--strict` it SHALL also exit with status 1 for unlisted members and for
generations without a manifest. `--json` SHALL print a machine-readable report.

#### Scenario: Intact archive
- **WHEN** no member has changed since the run
- **THEN** `verify` exits with status 0 and reports every generation as verified

#### Scenario: Tampered page
- **WHEN** the bytes of `page_2.json` are changed after publication
- **THEN** `verify` reports `page_2.json` as changed and exits with status 1

#### Scenario: Legacy archive
- **WHEN** an archive written before manifests existed is verified
- **THEN** `verify` warns that the generation has no manifest and exits with status 0
- **AND** with `--strict` it exits with status 1

### Requirement: Verification record
`verify` SHALL record the time and result of the last verification in the
project state file, and `info` SHALL show it.

#### Scenario: Info after verification
- **WHEN** `verify` succeeds and `info` is run
- **THEN** `info` shows the verification time and a passing result

