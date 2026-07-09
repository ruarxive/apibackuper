# Change: Refactor ProjectBuilder God class into focused components

## Why
`apibackuper/cmds/project.py` is a 3,369-line monolith that handles config
loading, HTTP requests, storage, export, estimation, hooks, detection, and
follow-mode. It has 17 test methods that cover only superficial initialization.
This God class makes it impossible to test individual behaviors, extend
features, or understand the codebase without reading thousands of lines.

## What Changes
- Extract `ConfigProcessor` — config loading, validation, normalization (from `__read_config`)
- Extract `RequestEngine` — HTTP session, `_single_request`, retry, auth integration
- Extract `StorageManager` — wrapper over storage backends, page/object save logic
- Extract `ExportPipeline` — all export format logic from `export()`
- Extract `HookRunner` — `_run_hook` and hook lifecycle management
- Refactor `ProjectBuilder` into a thin orchestrator that composes these components
- Add type hints to all extracted classes and their public methods
- Ensure extracted classes are independently testable with clear interfaces

## Impact
- Affected specs: architecture, request-execution, export-filtering, hook-execution
- Affected code: `apibackuper/cmds/project.py`, new files under `apibackuper/cmds/`
