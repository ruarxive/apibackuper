## Context
The MAJOR_UPDATE report calls for multiple cross-cutting changes across CLI,
core processing, storage, and configuration. These features introduce new state
management, storage backends, extensibility hooks, and richer observability.

## Goals / Non-Goals
- Goals:
  - Reliable incremental backups and resumable runs
  - Clear and strict configuration validation with YAML-first UX
  - Extensible pipeline with custom hooks
  - Storage backend abstraction with SQLite option
  - Faster and safer runs via concurrency and retries
  - Better user guidance, progress, and documentation
- Non-Goals:
  - Distributed execution or orchestration
  - UI or web dashboard
  - Full ETL transforms beyond export filters

## Decisions
- Decision: Introduce a storage backend interface and keep ZIP as default
- Decision: Use a per-project state file for update and checkpointing
- Decision: Add a detection command that only samples once by default
- Decision: Provide hook execution via file paths with explicit allow-list
- Alternatives considered:
  - Global state database vs per-project state file
  - Removing INI immediately vs deprecation warning first
  - Multi-process concurrency vs thread pool

## Risks / Trade-offs
- Increased complexity in core run loop -> mitigate with tests and phased rollout
- Hook execution can be unsafe -> mitigate with clear docs and opt-in usage
- SQLite backend may diverge from ZIP semantics -> keep common interface and
  parity tests

## Migration Plan
1. Add deprecation warnings for INI config usage
2. Keep existing ZIP storage as default while adding SQLite option
3. Ship update/resume as opt-in commands and flags
4. Expand documentation and examples in the same release

## Open Questions
- Should update mode support custom change detection scripts in v1?
- Should detection be purely advisory or able to write YAML by default?
- What is the minimal checkpoint data for resuming downloads safely?
