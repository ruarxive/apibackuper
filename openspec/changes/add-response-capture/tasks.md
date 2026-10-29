## 1. Configuration
- [ ] 1.1 Add `storage.capture.metadata` and `storage.capture.raw_body` to the
      schema and `ProjectBuilder`, with defaults `true` and `auto`

## 2. Capture
- [ ] 2.1 Build the exchange record from the final response (status, reason,
      headers, URL, fetch time, elapsed, SHA-256, version, run ID) with redaction
- [ ] 2.2 Save `raw_N.<ext>` and `exchange_N.json` before `page_N.json` in
      the page's prefix for full, continue and update runs
- [ ] 2.3 Pass the response, not only its content, from `fetch` to `store`

## 3. Export and reporting
- [ ] 3.1 Add `--format warc` (and `.warc.gz` extension detection) that writes
      request and response records with warcio; skip pages without exchanges
      and report the count
- [ ] 3.2 Add `warcio` to the `recommended` extra with a clear error when missing
- [ ] 3.3 Report captured exchanges in `info --stats`

## 4. Tests and docs
- [ ] 4.1 Tests: exchange content and redaction, XML raw bytes kept, resume
      with capture, WARC round-trip read back with warcio, legacy archive export
- [ ] 4.2 Document capture, the archive layout and WARC export; update `CHANGELOG.md`
