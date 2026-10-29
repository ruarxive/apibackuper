## Context
`run_backup` (`apibackuper/cmds/backup.py`) computes the page list up front
from count metadata, or iterates `itertools.count()` until a short page. It
builds each request from the page number via `build_page_request`
(`apibackuper/cmds/fetch.py`). In cursor-style APIs, request N+1 depends on
response N, so a page number alone cannot rebuild a request.

## Goals / Non-Goals
- Goals: sequential cursor, next-URL and Link-header traversal; exact resume;
  loop detection; the same storage layout (`page_N.json`) and export behaviour.
- Non-Goals: parallel cursor traversal, date-window slicing, and cursors that
  must be sent in headers or in POST bodies at nested paths (follow-up if needed).

## Decisions
- **Page numbering stays sequential.** The Nth response is saved as
  `page_N.json`, so export, `info`, follow and the integrity checks are unchanged.
- **The cursor lives in the checkpoint.** After each contiguous saved page the
  checkpoint records `{"next_page": N+1, "cursor": <token or URL>}`. Resume
  sends that cursor and does not replay the chain from page 1. A legacy
  checkpoint without a cursor restarts the chain, and the replayed pages
  overwrite identical names.
- **Request building.**
  - `cursor`: `params[cursor_param] = token`, using the same query, params or
    body placement as the existing pagination parameters. Base parameters and
    update watermarks are repeated, as cursor APIs expect the same filters.
  - `next_url`: the request URL is `urljoin(current_url, value)`. Base
    `params.json` values are sent only on the first request, because next URLs
    already carry their query.
  - `link_header`: parse `response.links["next"]["url"]` from requests.
- **End of data.** The token or URL is missing, `null` or empty, or an empty
  page arrives. A short page does not end a cursor run, because cursor APIs
  often return variable page sizes.
- **Loop guard.** Keep the set of seen tokens and URLs for the run; a repeat
  raises an incomplete-run error. The existing repeated-records check still applies.
- **Runner.** The page source becomes a generator fed by the previous
  `PageOutcome`; `fetch_all_pages` already accepts an unbounded iterable. Cursor
  modes force `parallelism=1`, and validation rejects a higher setting.

## Risks / Trade-offs
- Some cursors expire. A resume after expiry gets HTTP 400 or 410 → the run
  fails with a hint to start a new full backup.
- Next URLs may point to another host → existing redirect-safe credential
  handling does not apply to explicit URLs, so a next URL on a different host
  is rejected unless `params.allow_cross_host_next: true` is set.

## Migration Plan
Additive configuration; no data migration. Rollback by reverting the code.
Archives created with cursor modes stay readable by older versions, because
the page layout is unchanged.

## Open Questions
- Should the `cursor` mode also support sending the token in a header (for
  example GitHub GraphQL-style APIs)? Proposed as a follow-up.
