---
title: "CLI Reference"
description: "Index of apibackuper CLI commands"
slug: /commands
---

# CLI Reference

All commands are available as `apibackuper <command>`. Use
`apibackuper <command> --help` for the live flag list.

Project commands accept `--projectpath` / `-p` (project directory); `create`
takes the destination directory as its positional argument.
`--verbose` / `-v` is available on `create`, `detect`, `run`, `update`,
`export` and `validate-config`. Check individual command pages for other flags.

## Global options

Put these before the command name:

```bash
apibackuper --json run full --max-pages 2
apibackuper --no-progress run full
```

- `--json` — write exactly one JSON object to stdout and everything else to
  stderr. A success looks like `{"ok": true, "command": "run", "result": {...}}`.
  A failure looks like `{"ok": false, "command": "run", "error": {"code":
  "config_not_found", "type": "FileNotFoundError", "message": "...", "hints":
  [...]}, "exit_code": 1}`. Error codes include `config_not_found`,
  `invalid_config`, `unset_env_var`, `backup_incomplete`, `pagination_ignored`,
  `already_exists`, `usage_error`, `invalid_value` and `operation_failed`.
- `--no-progress` — do not draw progress bars. Bars are also hidden whenever
  stderr is not a terminal, for example in pipes, CI logs and coding agents.

## Project lifecycle

| Command | Page |
|---------|------|
| `init` | [`/commands/init`](/commands/init) |
| `create` | [`/commands/create`](/commands/create) |
| `detect` | [`/commands/detect`](/commands/detect) |
| `validate-config` | [`/commands/validate-config`](/commands/validate-config) |
| `schema` | [`/commands/schema`](/commands/schema) |
| `info` | [`/commands/info`](/commands/info) |

## Backup

| Command | Page |
|---------|------|
| `estimate` | [`/commands/estimate`](/commands/estimate) |
| `run` | [`/commands/run`](/commands/run) |
| `update` | [`/commands/update`](/commands/update) |
| `verify` | [`/commands/verify`](/commands/verify) |

## Follow-up

| Command | Page |
|---------|------|
| `follow` | [`/commands/follow`](/commands/follow) |
| `getfiles` | [`/commands/getfiles`](/commands/getfiles) |

## Export

| Command | Page |
|---------|------|
| `export` | [`/commands/export`](/commands/export) |
