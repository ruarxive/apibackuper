## 1. Configuration
- [x] 1.1 Add `cursor`, `next_url`, `link_header` to `project.iterate_by` and
      add `data.next_cursor_key`, `data.next_url_key`, `params.cursor_param`,
      `params.allow_cross_host_next` to the schema
- [x] 1.2 Load the new keys in `ProjectBuilder` and validate required
      combinations and `parallelism == 1` in `validate-config`

## 2. Collection
- [x] 2.1 Build cursor, next-URL and Link-header requests in `cmds/fetch.py`
- [x] 2.2 Drive `run_backup` from a response-fed page generator; end on a
      missing token/URL or an empty page; fail on a repeated token/URL
- [x] 2.3 Store and restore the cursor in checkpoints; restart the chain for
      legacy checkpoints
- [x] 2.4 Reject cross-host next URLs unless explicitly allowed
- [x] 2.5 Send update watermarks only on the first request for next-URL and
      Link-header runs; reject `run continue` for cursor modes

## 3. Detection and planning
- [x] 3.1 Suggest cursor modes in `detect` from common fields and `Link` headers
- [x] 3.2 Show the cursor mode in the `run --dry-run` plan

## 4. Tests and docs
- [x] 4.1 Workflow tests per mode: full run, end of data, loop detection,
      interrupt + resume from the stored cursor, update watermark
- [x] 4.2 Update `docs/docs/configuration/pagination.md`, reference tables and
      `CHANGELOG.md`
