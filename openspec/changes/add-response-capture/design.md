## Context
Pages are stored as `page_N.json` or `runs/<id>/page_N.json`. Backends
classify a member as a page when its basename starts with `page_`
(`apibackuper/storage/backends.py`). Export, follow, `info` and the integrity
summary read only pages. For `resp_type: xml` and `html`, `backup.store`
saves `json.dumps(decoded)`, not the response bytes.

## Goals / Non-Goals
- Goals: record exactly what was fetched and when; keep the original bytes for
  non-JSON responses; produce standard WARC files; leave record export unchanged.
- Non-Goals: byte-exact replay of the wire exchange (requests decodes transfer
  and content encodings); WACZ packaging; capturing follow and file downloads
  (follow-up change once page capture is proven).

## Decisions
- **Member names avoid the `page_` prefix.** `exchange_N.json` and
  `raw_N.<ext>` sit in the same prefix as their page, so existing page
  listings, export and the resume logic ignore them without code changes.
  The `storage-backend` delta reserves these names.
- **Write order.** The raw body and the exchange record are saved before
  `page_N.json`. A crash between the two writes leaves an orphan exchange,
  which is harmless; a page never exists without its exchange while capture is on.
- **Redaction.** Request headers and parameters go through
  `redact_headers`/`redact_params`; the URL goes through `redact_url`;
  response `Set-Cookie` and `Authorization` values are replaced. The
  record notes `"redacted": true` when anything was replaced, so WARC
  consumers know the request record is not the exact wire request.
- **`raw_body: auto`.** Store raw bytes when `resp_type` is not `json`, or
  when a postfetch hook changes the content. With `always`, also store JSON
  bodies (useful when hooks rewrite pages); with `never`, store none.
- **WARC export.** Use warcio's `WARCWriter` with gzip. Per page: a `request`
  record (method, target URI, redacted headers, body for POST) and a
  `response` record whose HTTP header block is rebuilt from the status,
  reason and captured headers. `Content-Encoding` and `Transfer-Encoding`
  are dropped and `Content-Length` is set, because the stored payload is
  decoded. `WARC-Date` is the fetch time. The payload is the raw body when
  present, otherwise the page bytes. `WARC-Payload-Digest` is SHA-1 per WARC
  convention; the SHA-256 stays in the exchange record.
- **Defaults.** `metadata: true` and `raw_body: auto`, so new harvests carry
  provenance by default; the cost is one small JSON member per page.

## Risks / Trade-offs
- Larger archives and more members → measured cost is a few hundred bytes per
  page; `metadata: false` opts out.
- Redacted URLs in WARC target URIs reduce replay fidelity for APIs with
  credentials in the query → documented; prefer header authentication.
- A new optional dependency (`warcio`, Apache-2.0) → imported only by WARC export.

## Migration Plan
No migration. Older versions ignore the new members. Rollback by reverting;
captured members remain inert in archives.

## Open Questions
- Should `metadata` default to `true` for existing projects on upgrade, or only
  for projects created after the release? The proposal assumes `true`.
