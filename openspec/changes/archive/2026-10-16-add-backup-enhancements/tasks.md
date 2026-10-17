## 1. Implementation (Phase 1)
- [x] 1.1 Add update mode state file and CLI command
- [x] 1.2 Add checkpointing and resume flow for run commands
- [x] 1.3 Enforce YAML-first config validation with verbose errors
- [x] 1.4 Add richer progress output and end-of-run summary
- [x] 1.5 Expand `apibackuper info --json` with run metadata
- [x] 1.6 Add tests for update, resume, validation, and info outputs

## 2. Implementation (Phase 2)
- [x] 2.1 Add storage backend interface and keep ZIP backend
- [x] 2.2 Implement SQLite backend and config wiring
- [x] 2.3 Extend follow rules for multi-level and pagination
- [x] 2.4 Add hook execution points and sandboxed invocation
- [x] 2.5 Add tests for storage, follow, and hooks

## 3. Implementation (Phase 3)
- [x] 3.1 Implement API detection command and config flag
- [x] 3.2 Add concurrency support with rate limit enforcement
- [x] 3.3 Add flexible retry policy configuration
- [x] 3.4 Enhance export CLI with fields and filters
- [x] 3.5 Add tests for detect, concurrency, retry, and export

## 4. Documentation
- [x] 4.1 Add quickstart guides for common API patterns
- [x] 4.2 Add YAML templates to `examples/`
- [x] 4.3 Add FAQ entries for common issues
