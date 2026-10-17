---
title: "Troubleshooting"
description: "SSL errors, missing config, rate limits, and common failures"
---
# Troubleshooting

Logs are written to `apibackuper.log` in the current working directory. Use
`--verbose` to also print them to the console.

## Configuration file not found

`apibackuper` looks for `apibackuper.yaml`, `apibackuper.yml`, then
`apibackuper.cfg` in the project directory.

- Run `apibackuper create <name>` to scaffold a project
- Pass `--projectpath` if you are not in the project directory
- Confirm the file name matches one of the expected names

Validate after editing:

```bash
apibackuper validate-config -p myproject
```

## SSL certificate verification failed

SSL verification is enabled by default for `run`, `follow`, `estimate`, and
`getfiles`. If a certificate is untrusted:

```yaml
request:
  verify_ssl: false
```

A warning is logged when verification is disabled. Use this only for trusted
internal APIs or testing — disabling SSL makes the connection vulnerable to
man-in-the-middle attacks.

## Rate limiting / HTTP 429

Slow down requests and add retries:

```yaml
rate_limit:
  enabled: true
  requests_per_second: 2
  burst_size: 1

request:
  parallelism: 1
  retry:
    max_retries: 5
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 30
    retry_on_status: [429, 500, 502, 503, 504]
```

## Pagination never finishes

- Confirm `params.page_size_limit` matches the API's maximum page size
- Check `data.data_key` and `data.total_number_key` against a sample response
- Try `apibackuper detect` to suggest keys
- For skip/offset APIs, set `project.iterate_by: skip` and
  `params.count_skip_param`

## Empty export

- Run `apibackuper info` and confirm records were stored
- Run `apibackuper run full` before exporting
- Check that `data.data_key` points at the array of items

## Parquet export fails

Install optional dependencies:

```bash
pip install pandas pyarrow
# or
pip install "apibackuper[recommended]"
```

## Resume did not continue

- Use the same project, mode and storage path as the interrupted run:
  `apibackuper run full --resume` or `apibackuper update --resume`.
- Keep the checkpoint with the referenced storage and any `.journal` sidecar.
  For a full backup, that storage is normally the `.partial` path.
- Confirm the checkpoint path is readable and writable. Relative custom
  state/checkpoint paths resolve from the current working directory.
- Set `settings.checkpoint_interval_pages` for periodic progress saves.
  Lifecycle checkpoints are written even with the default interval of 0.

`No valid checkpoint is available to resume` means no readable checkpoint was
loaded. `run continue` scans the published archive for missing pages; it does
not recover a staged full backup. A completed checkpoint prints
`Backup is already complete`; omit `--resume` to start a new run.

If downloading finished but publication was interrupted, resume can recover
the archive and state without another HTTP request. See [`run`](/commands/run)
for the recovery-file layout.

## A command saved pages but exited unsuccessfully

An exhausted retry budget or missing page makes the backup incomplete.
`continue_on_error: true` permits further collection but does not turn an
incomplete backup into success. The last successful state stays unchanged;
use the matching resume command to retry from the first unresolved page.

## Export contains repeated IDs

Export includes the original pages and all retained update generations.
`data.item_key` does not deduplicate the history. Use downstream processing
to select the latest version of each object when needed.

## Related docs

- [Best practices](/getting-started/best-practices)
- [Rate limiting and requests](/configuration/rate-limiting-and-requests)
- [`detect`](/commands/detect)
