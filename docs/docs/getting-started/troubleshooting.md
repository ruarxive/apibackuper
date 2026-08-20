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

- Enable checkpoints: `settings.checkpoint_interval_pages`
- Pass `--resume` to `run` or `update`
- Confirm `settings.checkpoint_file` is writable

## Related docs

- [Best practices](/getting-started/best-practices)
- [Rate limiting and requests](/configuration/rate-limiting-and-requests)
- [`detect`](/commands/detect)
