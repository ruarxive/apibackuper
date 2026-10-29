# Change: Capture raw HTTP exchanges and export them as WARC

## Why
A saved page is only the response body (`apibackuper/cmds/backup.py`). XML and
HTML responses are stored as converted JSON, so the original bytes are lost.
Status, response headers, the final URL, request parameters and fetch time are
not kept at all. For a preservation archive this weakens the evidential value
of the data and blocks handing the harvest to web-archive tooling. warcio and
warcprox capture the full exchange, and WARC/WACZ is the ingest and replay
format used by web archives (pywb, national libraries).

## What Changes
- For every saved page, store an exchange record `exchange_N.json` next to
  `page_N.json`: method, final URL, request parameters or body, status,
  reason, response headers, fetch time (UTC), elapsed time, body SHA-256,
  content type, apibackuper version and run ID. Credentials are redacted with
  the existing diagnostics helpers; `Set-Cookie` is redacted as well.
- Store the original body as `raw_N.<ext>` when it differs from the saved page
  (XML, HTML and decoded-then-normalized responses). JSON pages are already the
  raw body and are not duplicated.
- New `storage.capture` settings: `metadata` (default `true`) and `raw_body`
  (`auto` by default; also `always` or `never`).
- New export format `apibackuper export --format warc out.warc.gz`, which
  writes WARC/1.1 `request` and `response` records from captured exchanges
  using the optional `warcio` dependency (`recommended` extra).
- `info --stats` reports how many pages have captured exchanges.
- Archives without exchange records stay readable; WARC export skips those
  pages and reports how many it skipped.

## Impact
- Affected specs: new `response-capture` capability; `storage-backend`
  (reserved member names)
- Affected code: `apibackuper/cmds/backup.py`, `apibackuper/cmds/export.py`,
  `apibackuper/cmds/project.py` (config, info),
  `apibackuper/schemas/config_schema.json`, `pyproject.toml` (optional
  `warcio`), docs for storage, export and data integrity
- Not breaking: page members and export of records are unchanged. Archives
  grow by one small JSON member per page while capture is enabled.
