---
title: "Best practices"
description: "Reliable long-running backups, credentials, and checkpoints"
---
# Best practices

## Estimate before a full run

Preview the resolved configuration without HTTP requests:

```bash
apibackuper run full --dry-run
```

Then run `apibackuper estimate full` to sample the live API and estimate record
counts, size and time. The dry-run estimate uses saved state and configuration.

## Prefer YAML and keep secrets out of git

Use `apibackuper.yaml`. Put tokens and passwords in files referenced by
`token_file` / `password_file`, not in the committed config:

```yaml
auth:
  type: bearer
  token_file: /run/secrets/api_token
```

## Checkpoint long jobs

```yaml
settings:
  checkpoint_file: apibackuper_checkpoint.json
  checkpoint_interval_pages: 5
  state_file: apibackuper_state.json
```

Resume with:

```bash
apibackuper run full --resume
```

Use `apibackuper update --resume` for an interrupted update. Keep the state,
checkpoint, staging `.partial` storage and ZIP `.journal` sidecars together.
Starting `run full` without `--resume` starts a fresh staged backup.

The interval enables periodic saves; lifecycle checkpoints are still written
when it is 0. State/checkpoint overrides are used as written: use absolute
paths when invoking a project from different working directories.

## Respect API limits

Set both `rate_limit` and `request.parallelism`. Concurrency still waits on
the rate limiter. Start conservative (`parallelism: 1`) and raise it only
after a successful estimate.

## Identify records uniquely

Set `data.item_key` to identify objects used by follow/file operations.
For change-key updates, set `data.change_key` and the API's
`params.change_key_param`. For timestamp updates, set `params.update_since_param`.

Updates retain earlier generations, and exports include all retained versions.
Repeated object IDs are expected; deduplicate downstream when you need a
current-object snapshot.

## Validate configuration

```bash
apibackuper validate-config
```

Do this after every config edit, especially pagination and auth changes.

## Keep SSL enabled

Leave `request.verify_ssl: true` unless the API has a known certificate
problem. The tool logs a warning when verification is off.

## Related docs

- [Troubleshooting](/getting-started/troubleshooting)
- [Incremental and update](/use-cases/incremental-and-update)
- [Protected APIs](/use-cases/protected-apis)
