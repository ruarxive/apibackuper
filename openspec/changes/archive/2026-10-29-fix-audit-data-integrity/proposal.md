# Change: Resolve the October 2026 project audit

## Why
The audit reproduced data loss during resume and incremental updates, unsafe
checkpoint advancement, successful CLI exits after failed backups, and broken
configuration/request paths. Existing tests exercise helpers but never run the
main backup workflow. All sixteen audit findings need implementation and proof.

## What Changes
- Preserve existing backups during full runs and resume; retain incremental generations.
- Commit state only after complete, durable runs and checkpoint the contiguous saved prefix.
- Make HTTP failures observable and share authentication, retry, timeout and rate controls.
- Repair optional data keys, parallel termination, flat query strings, typed YAML and filesystem storage.
- Redact credentials recursively and in URLs/errors.
- Exercise actual command workflows, consolidate extracted components and progress ownership.
- Align Python support/tooling, package contents, wheel checks, examples, docs and OpenSpec.
- **BREAKING**: declare Python 3.10+ support, matching the existing CI and formatter floor.

## Impact
- Affected specs: backup-integrity, request-execution, configuration, storage,
  testing, project-maintenance.
- Affected code: cmds/project.py, runner.py, fetch.py, http_client.py,
  config_loader.py, export.py, utils.py, storage, tests, CI, packaging and docs.
- Existing flat archives and state/checkpoint JSON remain readable. Incremental
  generations add namespaced members without deleting old members.
- Approved for creation and implementation by the user's explicit request on 2026-10-16.
