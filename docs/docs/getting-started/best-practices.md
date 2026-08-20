---
title: "Best practices"
description: "Reliable long-running backups, credentials, and checkpoints"
---
# Best practices

## Estimate before a full run

Always run `apibackuper estimate full` first. It reports record counts, expected
size, and wall-clock time so you can set rate limits and storage accordingly.

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

## Respect API limits

Set both `rate_limit` and `request.parallelism`. Concurrency still waits on
the rate limiter. Start conservative (`parallelism: 1`) and raise it only
after a successful estimate.

## Identify records uniquely

Set `data.item_key` (comma-separated for composite keys) so incremental and
update modes can skip duplicates. Set `data.change_key` for update mode.

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
