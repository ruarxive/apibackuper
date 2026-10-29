# Change: Add fixity manifests and a `verify` command

## Why
Fixity checking is a core preservation function, but apibackuper writes no
checksums. `docs/docs/getting-started/data-integrity.md` asks users to hash
archives with a hand-written script, which is easy to skip and does not cover
individual members or update generations. WACZ (`datapackage.json` with
SHA-256) and `warcio check` provide this for web archives; BagIt (RFC 8493)
uses the same `manifest-sha256.txt` form.

## What Changes
- Every successful run writes a BagIt-style `manifest-sha256.txt`
  (`<sha256>  <member>` per line) for the generation it publishes: the base
  pages for `full`/`continue`, `runs/<id>/manifest-sha256.txt` for `update`.
  When response capture is enabled, captured members are included.
- Each generation also gets `run.json`: apibackuper version, run ID, mode,
  start and end time, page and record counts, the API total when known, and the
  SHA-256 of the resolved configuration with credentials redacted.
- New command `apibackuper verify [--strict] [--json]`:
  - recomputes the digests of every member listed in each manifest;
  - reports changed, missing and unlisted members;
  - exits 1 on any mismatch or missing member; with `--strict`, unlisted
    members and generations without a manifest are errors too.
- `info` shows whether the latest generation has a manifest and when it was
  last verified (from the state file).
- Archives created before this change verify as "no manifest" (a warning, or
  an error with `--strict`).

## Impact
- Affected specs: new `archive-fixity` capability; `backup-resume`
  (publication writes the manifest)
- Affected code: `apibackuper/cmds/backup.py` (publication),
  new `apibackuper/cmds/verify.py`, `apibackuper/core.py` (command),
  `apibackuper/storage/backends.py` (member listing helpers), docs for data
  integrity and commands
- Not breaking: manifest and run members do not start with `page_` and are
  ignored by export and resume.
