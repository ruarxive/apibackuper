## 1. Component Extraction
- [ ] 1.1 Create `apibackuper/cmds/config_processor.py` with `ConfigProcessor` class
- [ ] 1.2 Create `apibackuper/cmds/request_engine.py` with `RequestEngine` class
- [ ] 1.3 Create `apibackuper/cmds/storage_manager.py` with `StorageManager` class
- [ ] 1.4 Create `apibackuper/cmds/export_pipeline.py` with `ExportPipeline` class
- [ ] 1.5 Create `apibackuper/cmds/hook_runner.py` with `HookRunner` class

## 2. Orchestrator Refactoring
- [ ] 2.1 Refactor `ProjectBuilder.__init__` to use `ConfigProcessor`
- [ ] 2.2 Refactor `_single_request` to delegate to `RequestEngine`
- [ ] 2.3 Refactor storage operations to delegate to `StorageManager`
- [ ] 2.4 Refactor `export()` to delegate to `ExportPipeline`
- [ ] 2.5 Refactor `_run_hook` to delegate to `HookRunner`
- [ ] 2.6 Ensure `ProjectBuilder` remains the public API for backward compatibility

## 3. Type Hints and Interfaces
- [ ] 3.1 Add type hints to all public methods in extracted components
- [ ] 3.2 Define clear `__init__` signatures with dependency injection
- [ ] 3.3 Add type hints to remaining `ProjectBuilder` methods

## 4. Tests
- [ ] 4.1 Write unit tests for `ConfigProcessor` (YAML, INI, defaults, validation)
- [ ] 4.2 Write unit tests for `RequestEngine` (auth, retry, rate limiting)
- [ ] 4.3 Write unit tests for `StorageManager` (save, list, retrieve)
- [ ] 4.4 Write unit tests for `ExportPipeline` (JSONL, parquet, zstd)
- [ ] 4.5 Write unit tests for `HookRunner` (load, execute, error handling)

## 5. Verification
- [ ] 5.1 Confirm all existing tests pass without modification
- [ ] 5.2 Confirm no public API changes for CLI commands
