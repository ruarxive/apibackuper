## 1. Configuration
- [x] 1.1 Add `request.response_rules`, `request.retry.wait_headers` and
      `request.retry.max_wait` to the schema; validate rule shape

## 2. Evaluation
- [x] 2.1 Evaluate rules in `_request` for every response, before the status check
- [x] 2.2 Map actions for pages (`retry`, `fail`, `accept`; `missing` fails),
      follow and files (`missing` records the key or file)
- [x] 2.3 Replace the hard-coded 404/410 handling with equivalent default rules
- [x] 2.4 Wait from the configured headers (seconds, HTTP date, Unix time) with
      `max_wait`

## 3. Reporting, tests and docs
- [x] 3.1 Count rule actions in the run summary
- [x] 3.2 Tests: 200 error body retried and failed, `4xx` accepted, follow
      `missing`, `X-RateLimit-Reset` epoch wait, `max_wait` exceeded
- [x] 3.3 Document rules in the request policy guide; update `CHANGELOG.md`
