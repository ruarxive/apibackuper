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
  user_agent: apibackuper/1.0.13
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

## error_handling

```yaml
error_handling:
  retry_on_errors: [429, 500, 502, 503]
  max_consecutive_errors: 10
  continue_on_error: true
```

Feature example: `examples/features/concurrency-retry/`.
