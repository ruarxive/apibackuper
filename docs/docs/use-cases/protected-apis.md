---
title: "Protected APIs"
description: "Authentication, rate limits, retries, and SSL for authenticated endpoints"
---
# Protected APIs

## Bearer token

```yaml
auth:
  type: bearer
  token_file: /path/to/token.txt
```

Template: `examples/templates/bearer-auth.yaml`.

Other `auth.type` values: `basic`, `apikey`, `oauth2`. See
[Authentication](/configuration/auth).

## Rate limits and concurrency

```yaml
rate_limit:
  enabled: true
  requests_per_second: 5
  burst_size: 5

request:
  parallelism: 10
  timeout: 120
  retry:
    max_retries: 5
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 30
    retry_on_status: [429, 500, 502, 503, 504]
```

Concurrency respects the rate limiter. Feature example:
`examples/features/concurrency-retry/`.

## SSL

Leave verification on unless the API certificate is known-bad:

```yaml
request:
  verify_ssl: false
```

A warning is logged when SSL is disabled. See
[Troubleshooting](/getting-started/troubleshooting).
