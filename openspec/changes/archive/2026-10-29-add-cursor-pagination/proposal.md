# Change: Add cursor, next-URL and Link-header pagination

## Why
Collection supports only `page`, `skip` and `range` iteration
(`apibackuper/cmds/fetch.py`). Many APIs offer only an opaque cursor, a
next-page URL in the response body, or an RFC 8288 `Link: rel="next"` header,
and they cannot be archived today. Offset pagination also drifts when records
are inserted or deleted during a long harvest; cursor traversal does not.
dlt, the Singer SDK, Airbyte's low-code CDK and paginate-json all support these
modes.

## What Changes
- New `project.iterate_by` values:
  - `cursor`: read a token from `data.next_cursor_key` and send it in
    `params.cursor_param` on the next request.
  - `next_url`: request the URL found at `data.next_url_key`, relative to the
    current URL.
  - `link_header`: follow the `rel="next"` target of the `Link` response header.
- Collection ends when the response has no next token or URL. Without count
  metadata this is the only end signal, so no fixed page cap applies.
- A repeated token or URL (a pagination loop) fails the run as incomplete.
- Checkpoints store the next token or URL with the contiguous saved prefix, so
  `--resume` continues from the last saved page without replaying the chain.
- `request.parallelism` greater than 1 is rejected by `validate-config` for
  these modes, because each request depends on the previous response.
- `update` mode combines with these modes. `cursor` requests repeat the base
  parameters and the watermark with each cursor; for `next_url` and
  `link_header`, they are sent only with the first GET request, because the
  next URL carries the query.
- `run continue` is rejected for these modes, because it cannot start inside a
  chain; `run full --resume` and `update` are used instead.
- `detect` suggests these modes when it finds common next-link fields (`next`,
  `next_cursor`, `links.next`, `@odata.nextLink`) or a `Link` header.
- Schema, `validate-config`, `run --dry-run` plan and docs cover the new keys.

## Impact
- Affected specs: `pagination`, `api-detection`
- Affected code: `apibackuper/cmds/fetch.py`, `apibackuper/cmds/backup.py`,
  `apibackuper/cmds/project.py` (config, detect,
  validation), `apibackuper/schemas/config_schema.json`,
  `docs/docs/configuration/pagination.md`
- Not breaking: existing `page`/`skip`/`range` projects are unchanged.
