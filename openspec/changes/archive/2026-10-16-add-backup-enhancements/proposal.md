# Change: Add backup enhancements and extensibility

## Why
The MAJOR_UPDATE report identifies gaps in incremental backups, resiliency, and
extensibility that limit apibackuper as a continuous sync tool and make complex
APIs harder to configure and operate at scale.

## What Changes
- Add update mode with persistent state and change-key support
- Add resume and checkpointing for long-running backups
- Strengthen YAML-first config validation and error reporting
- Add API detection to suggest pagination and data keys
- Add custom hook execution at key pipeline points
- Introduce storage backend abstraction with SQLite support
- Expand follow rules to multi-level and paginated links
- Add concurrency and flexible retry policies within rate limits
- Enhance export UX with field selection and filters
- Add richer progress, summaries, and info JSON outputs
- Expand documentation with quickstarts, templates, and FAQ

## Impact
- Affected specs: backup-update, backup-resume, config-validation, api-detection,
  hook-execution, storage-backend, follow-links, request-execution,
  export-filtering, run-observability, document-usage
- Affected code: apibackuper/core.py, apibackuper/cmds/, apibackuper/storage/,
  apibackuper/cmds/http_client.py, apibackuper/rate_limiter.py,
  apibackuper/cmds/config_loader.py, apibackuper/schemas/config_schema.json,
  docs and examples
