# Change: Add response rules and rate-limit header waits

## Why
A response is judged only by its HTTP status. APIs that answer `200` with an
error body (`{"error": "quota exceeded"}`, an HTML maintenance page) have it
archived as data or crash the decoder. Rate-limit headers other than
`Retry-After` (`X-RateLimit-Reset`, `RateLimit-Reset`) are ignored, so a 429 is
retried on the fixed backoff and often fails again. The only exception to
"non-2xx fails" is hard-coded: 404/410 for follow and file downloads.
dlt (`response_actions`), Airbyte (error handlers with response filters) and
Redpanda Connect (`successful_on`, `drop_on`) all make this declarative.

## What Changes
- New `request.response_rules`: an ordered list evaluated on every response
  for pages, follow requests and file downloads. A rule matches on any of:
  - `status`: a code, a list, or a class such as `4xx`;
  - `body_key`, with an optional `body_value`: a dotted path in a JSON body;
  - `content_type`: a substring of the response `Content-Type`.
- Actions: `retry` (use the retry policy and budget), `fail` (stop as an
  incomplete run), `missing` (record as gone for follow/files; fail for pages),
  `accept` (treat as success). The first matching rule wins; built-in defaults
  reproduce today's behaviour when no rule matches.
- New `request.retry.wait_headers` (default `["Retry-After"]`): headers read in
  order to wait before a retry. Seconds, HTTP dates and Unix timestamps
  (`X-RateLimit-Reset`) are supported. `request.retry.max_wait` caps the wait
  and fails the run when exceeded.
- Run summaries count responses per rule action.

## Impact
- Affected specs: `request-execution`
- Affected code: `apibackuper/cmds/project.py` (`_request`, retry delay),
  `apibackuper/cmds/backup.py`, `apibackuper/cmds/follow.py`, `getfiles`,
  `apibackuper/schemas/config_schema.json`, request policy docs
- Not breaking: without rules the behaviour is unchanged.
