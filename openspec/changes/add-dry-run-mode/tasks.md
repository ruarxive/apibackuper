## 1. CLI Integration
- [ ] 1.1 Add `--dry-run` option to `run` command in `core.py`
- [ ] 1.2 Add `--dry-run` option to `update` command in `core.py`
- [ ] 1.3 Add `--dry-run` option to `follow` command in `core.py`

## 2. Implementation
- [ ] 2.1 Add `_dry_run_plan()` method to `ProjectBuilder` that computes execution plan without HTTP
- [ ] 2.2 Print plan: URL, iterate_by, page count, data key, storage path, estimated size
- [ ] 2.3 Integrate with existing `detect` for API structure suggestions
- [ ] 2.4 Ensure zero HTTP requests in pure dry-run (without detect)

## 3. Tests
- [ ] 3.1 Add test for dry-run with valid config (no HTTP calls made)
- [ ] 3.2 Add test for dry-run with invalid config (validation error, no HTTP)
- [ ] 3.3 Add test for dry-run with detect enabled (single HTTP call)
- [ ] 3.4 Add test verifying exit code 0 on success
