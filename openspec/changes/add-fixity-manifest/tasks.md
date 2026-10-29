## 1. Manifest generation
- [x] 1.1 Compute SHA-256 for every member of the published generation in
      `run_backup` before publication, from the staged backend content
- [x] 1.2 Write `manifest-sha256.txt` and `run.json` into the generation
      prefix for zip, sqlite and filesystem storage
- [x] 1.3 Hash the resolved configuration with credentials redacted
- [x] 1.4 Make the publication-recovery path rewrite missing manifests

## 2. Verify command
- [x] 2.1 Add `apibackuper verify` with `--strict` and `--json`, reading all
      generation manifests through the storage backend (including the ZIP journal)
- [x] 2.2 Report changed, missing and unlisted members, and generations
      without a manifest; set the exit status
- [x] 2.3 Record the last verification time and result in the state file and
      show it in `info`

## 3. Tests and docs
- [x] 3.1 Tests: manifests after full and update runs on every backend,
      tampered member, deleted member, unlisted member, legacy archive with and
      without `--strict`, recovery after interrupted publication
- [x] 3.2 Replace the hand-written hashing recipe in the data-integrity guide;
      add a `verify` command page; update `CHANGELOG.md`
