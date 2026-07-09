# Change: Add dry-run mode for config validation

## Why
apibackuper makes real API requests on every `run` command. Users who want to
test a new config or verify pagination settings must actually hit the API,
consuming rate limits and producing side effects. A dry-run mode would let
users validate config, detect pagination parameters, and estimate request
count without making any network calls.

## What Changes
- Add `--dry-run` flag to `run`, `update`, and `follow` commands
- In dry-run mode: load config, validate schema, detect API structure, print
  plan (pages, estimated requests, storage path), then exit without HTTP calls
- Reuse existing `detect` logic to suggest pagination and data keys
- Print a human-readable execution plan before exiting

## Impact
- Affected specs: run-execution
- Affected code: `apibackuper/core.py`, `apibackuper/cmds/project.py`
