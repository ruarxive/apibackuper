---
title: "Rate limiting and requests"
description: "Set request quotas, concurrency, timeout and retry budgets, proxies and error stopping rules"
---
# Rate limiting and requests

These settings control different parts of a request: `rate_limit` controls when
an attempt may start, `request` controls the exchange and retry budget, and
`error_handling` controls what the page collector does after a request fails.
Configure them together for a predictable long-running backup.

## A conservative starting policy

```yaml
project:
  default_delay: 0
rate_limit:
  enabled: true
  requests_per_second: 2
  requests_per_minute: 100
  burst_size: 1
request:
  connect_timeout: 10
  read_timeout: 60
  verify_ssl: true
  parallelism: 1
  retry:
    max_retries: 3
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 10
    retry_on_status: [429, 500, 502, 503, 504]
error_handling:
  max_consecutive_errors: 3
  continue_on_error: false
```

Merge these sections into a complete project. This example allows a small
request rate, retries transient responses, and stops collection after a page
cannot be fetched. Increase concurrency only after confirming the API's quota
and stable pagination behavior.

## Rate limits and bursts

| Field | Effective default | Behavior |
|-------|-------------------|----------|
| `enabled` | true when the section exists | false disables this project's limiter |
| `requests_per_second` | No per-second cap | Positive number; token refill rate, fractions allowed |
| `requests_per_minute` | No minute cap | Integer rolling 60-second window; 0 disables this window |
| `requests_per_hour` | No hour cap | Integer rolling 3,600-second window; 0 disables this window |
| `burst_size` | 5 | Positive token-bucket capacity and initial allowance |

Without a `rate_limit` section there is no configured limiter. Merely adding
`enabled: true` without any quota does not create a rate cap. Omit a per-second
limit to disable it; validation rejects an explicitly non-positive value.

All configured windows apply. For example, 10 requests/second with a limit of
100/minute can still stop for the minute window after 100 requests. A token
bucket with `burst_size: 5` can start with five tokens; it does not enforce evenly
spaced requests. Use `burst_size: 1` when a service tolerates little burst traffic.

Limits are shared by the project's ordinary request attempts in this process,
including retries. They are not coordinated across separate CLI processes or
other applications using the same account. Redirects, OAuth token refresh and
its immediate replay can add HTTP exchanges inside an attempt; reserve quota
headroom when the provider counts every exchange. aria2 transfers use their own
service policy.

## Concurrency and default delay

`request.parallelism` defaults to 1 and controls concurrent **backup page**
requests. It is not a global worker count for follow or file downloads. Pages
are consumed in order for durable checkpoints; extra requests can already be
in flight when an end page or failure is discovered.

`project.default_delay` defaults to 0.5 seconds and sleeps after a successful
request. It adds to response time and any rate-limit waits. With multiple
workers, each successful request waits independently, so this setting alone
does not impose an account-wide requests/second cap. Use `rate_limit` for quotas.

## Connection and read timeouts

```yaml
request:
  connect_timeout: 10
  read_timeout: 60
```

`connect_timeout` defaults to 30 seconds; `read_timeout` defaults to 120 seconds.
Both are positive integer seconds. The first bounds connection establishment;
the second bounds waiting for data during reads, not total job duration. A slow
stream can take longer than `read_timeout` overall while continuing to deliver data.

The legacy `request.timeout` defaults to 120 but does not replace the active
connection/read pair. Set those fields explicitly. Total wall time also includes
retries, backoff, rate-limit waits, redirects and successful-request delays.

## Retry budget and delay calculation

```yaml
request:
  retry:
    max_retries: 3
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 4
    retry_on_status: [429, 500, 502, 503, 504]
```

`max_retries` counts retries **after** the initial attempt: 3 permits up to four
ordinary attempts. Retryable transport failures and configured unsuccessful
statuses consume this budget. Other unsuccessful statuses fail without exhausting
it, after any supported OAuth refresh attempt. HTTP 2xx is considered successful;
an application error encoded inside a 200 JSON body requires correct extraction
or application-specific handling.

For this example, delays before retries are 1, 2 and 4 seconds. `fixed` uses
`initial_delay` each time, capped by `max_delay`; exponential uses
`min(initial_delay * 2^(retry_number - 1), max_delay)`.
A server `Retry-After: 15` overrides the configured backoff delay, even when it
exceeds `max_delay`. An HTTP-date Retry-After waits until that time; otherwise the configured
delay is used instead.

POST requests can also be retried. Use this tool for read/query endpoints where
replaying a request is acceptable to the API; it does not provide an idempotency-key
or write-transaction protocol.

### Retry configuration precedence

For each corresponding setting, flat compatibility keys override nested keys:

1. Explicit `request.retry_max_retries`, `retry_backoff_strategy`,
   `retry_initial_delay`, `retry_max_delay`, `retry_on_status`.
2. Nested values under `request.retry`.
3. Fallbacks: `project.retry_count` (5), `project.retry_delay` (5 seconds),
   fixed backoff and maximum delay `max(retry_delay, retry_delay * 4)`.

The fallback retry status list is `error_handling.retry_on_errors`, or
`[429, 500, 502, 503, 504]` when omitted. Configure a non-empty explicit list to
remove ambiguity. Prefer the nested YAML form and
remove leftover flat overrides when migrating a configuration.

## Failed pages and continued collection

```yaml
error_handling:
  retry_on_errors: [429, 500, 502, 503]
  max_consecutive_errors: 10
  continue_on_error: true
```

After a page exhausts its HTTP retry budget, `continue_on_error: true` lets the
collector try later pages until the consecutive-error limit is reached. A
successfully saved page resets the consecutive-error count. `false` stops at
the first unresolved failure; parallel requests may already have completed.

Continued collection is still an **incomplete run**: it returns a nonzero exit,
does not publish a failed full backup or advance successful update state, and
keeps recovery progress. The checkpoint only advances through the contiguous
saved prefix. Use the matching `run full --resume` or `update --resume` to retry
from the first unresolved page.

## SSL and redirects

| Field | Default | Notes |
|-------|---------|-------|
| `verify_ssl` | true | Boolean only; a CA-bundle path is not accepted in this option |
| `allow_redirects` | true | Follow redirects using the HTTP client |
| `max_redirects` | 5 | Maximum followed redirects; 0 permits none |
| `user_agent` | `apibackuper/<version>` | Session User-Agent; per-request headers may override it |

Leave SSL verification enabled for normal collection. A self-signed or broken
certificate may require an explicitly trusted test/internal configuration with
`verify_ssl: false`; this logs a warning. Use the final API endpoint rather
than relying on unnecessary redirects, and inspect failures in the log.

## Proxies

Use the currently implemented comma-separated string form, including in YAML:

```yaml
request:
  proxies: "http=http://proxy.example.com:8080,https=http://proxy.example.com:8080"
```

Each entry is `scheme=proxy_url`. An HTTPS target can use an HTTP CONNECT proxy,
so the proxy URL does not need `https://` merely because the target does.
The schema also accepts a YAML mapping, but the current loader does not apply
ordinary mapping entries correctly. Use the string form for an effective
project-level setting. This parser is not a JSON-object-string parser.

The underlying Requests session also uses its normal process environment.
Account for `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` in scheduled environments;
remove unintended inherited proxy settings when diagnosing routing problems.

## Diagnose slow or failing runs

| Symptom | Check |
|---------|-------|
| Long wait with no requests | Minute/hour quota window, Retry-After and backoff logs |
| Too many requests despite a delay | Multiple workers/processes, token-bucket burst and other account consumers |
| All retries fail on 401/403 | Authentication/permissions; extra retries do not fix an invalid credential |
| Timeout persists after increasing `timeout` | Set active `connect_timeout` and `read_timeout` |
| Proxy configuration has no effect | Use the supported string form and inspect process proxy environment |
| Pages were saved but command failed | An unresolved gap keeps the run incomplete; resume with matching mode/storage |

Feature example: `examples/features/concurrency-retry/`. See
[authentication](/configuration/auth) for OAuth refresh and
[backup completeness](/getting-started/data-integrity) for consistency limits.
