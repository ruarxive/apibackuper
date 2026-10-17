---
title: "Rate limiting and requests"
description: "Rate limits, timeouts, retries, proxies, and SSL"
---
# Rate limiting and requests

## rate_limit

Token-bucket (per second) plus sliding windows (per minute / hour).

```yaml
rate_limit:
  enabled: true
  requests_per_second: 10
  requests_per_minute: 600
  requests_per_hour: 36000
  burst_size: 5
```

## request

```yaml
request:
  timeout: 120
  connect_timeout: 30
  read_timeout: 120
  verify_ssl: true
  user_agent: apibackuper/2.0.0
  max_redirects: 5
  allow_redirects: true
  parallelism: 1
  proxies:
    http: http://proxy:8080
    https: https://proxy:8080
  retry:
    max_retries: 5
    backoff_strategy: exponential   # or fixed
    initial_delay: 1
    max_delay: 30
    retry_on_status: [429, 500, 502, 503, 504]
```

`parallelism` is the number of concurrent page requests. It still waits on
the rate limiter.

Built-in backup, update, follow, file download, detection and estimation requests share
authentication, status checks, bounded retries, SSL verification and rate limits.
`connect_timeout` and `read_timeout` control HTTP connection/read timeouts;
set them explicitly rather than relying on the legacy `timeout` field.

The optional aria2 integration queues transfers to a separate RPC service;
see [files configuration](/configuration/files) for its requirements.

`max_retries` is the number of retries after the initial attempt. Transport
failures and statuses in `retry_on_status` use this budget. Other unsuccessful
statuses fail immediately after any supported OAuth2 refresh attempt. A numeric
`Retry-After` header takes precedence over the configured backoff delay.

Legacy `project.retry_count` and `project.retry_delay` supply defaults when
`request.retry` is omitted. Flat `request.retry_*` options are also accepted
for INI compatibility and override corresponding nested YAML values.

## error_handling

```yaml
error_handling:
  retry_on_errors: [429, 500, 502, 503]
  max_consecutive_errors: 10
  continue_on_error: true
```

`retry_on_errors` supplies the fallback retry status list. `continue_on_error`
allows collection to proceed after a failed page until the consecutive-error
limit is reached; an incomplete backup still exits unsuccessfully and preserves
the previous successful state. Resume restarts at the first unresolved page.

Feature example: `examples/features/concurrency-retry/`.
