# apibackuper troubleshooting

Run with `--verbose` to see requests in the console and in `apibackuper.log`.
Validate after every configuration edit: `apibackuper validate-config --strict --json`.
With `apibackuper --json <command>`, failures carry `error.code` (shown in
brackets below), `error.message` and `error.hints`.

| Message or symptom | Cause | Fix |
|--------------------|-------|-----|
| Warning `params.page_number_param not set for iterate_by: page; only the first page will be collected`, or `Warning: collected N of M records reported by the API` after a run | No pagination parameter for the chosen `iterate_by` | Add `page_number_param` (or `count_skip_param`, `count_from_param`/`count_to_param`, `cursor_param`); `apibackuper detect` probes it. Check with `apibackuper run full --max-pages 2` |
| `Backup is incomplete: page P returned N records (page_size_limit is L) before page M ...` [`backup_incomplete`] | The API caps the page size below `page_size_limit` | Set `params.page_size_limit` to the size the API returns; run a new `apibackuper run full` |
| `Page P returned the same records as page P-1; the API appears to ignore the pagination parameter ...` [`pagination_ignored`] | Wrong parameter name, or the parameter belongs in the body/URL instead | Check the API docs; for POST use dotted names such as `paging.page`; check `params.query_mode` |
| `Response is missing configured data_key: ...` | Wrong records path, or an error body | Inspect one response with `curl`; fix `data.data_key`; add a `request.response_rules` entry for error bodies |
| `Backup is incomplete: the next-page URL points to another host ...` | Next links use a different host | Set `params.allow_cross_host_next: true` if that host is trusted |
| `Backup is incomplete: page P returned a next position that was already followed ...` | The cursor or next URL loops | Check `data.next_cursor_key` / `data.next_url_key`; the API may need a sort parameter |
| `Backup is incomplete; resume from checkpoint. Errors: ...` | Pages failed after retries | Fix the cause (auth, rate limit, network), then `apibackuper run full --resume` |
| `configuration references unset environment variable` (exit status 2) [`unset_env_var`] | A `${VAR}` placeholder has no value | `export VAR=...` before the command, or use `${VAR:-default}` |
| `Configuration validation failed`, `Invalid project configuration` [`invalid_config`] | Schema or rule error | `apibackuper validate-config --json` names the `path` and a `hint`; `apibackuper schema` lists allowed keys |
| `HTTP 403 for ...`, `HTTP 401 for ...` [`http_error`, with `status`] | Missing credentials, a required header such as a custom User-Agent, or a regional block | Add `-H "Name: value"` or `--auth` to `init` (or `headers.json` / `auth`); check the API's access rules |
| `Configuration file not found in: ...` [`config_not_found`] | Wrong directory | `cd` into the project or pass `-p PATH` |
| `... already exists; pass --force to replace it` [`already_exists`] | `init` target has a configuration | Choose another directory or add `--force` |
| `HTML responses require a postfetch process function` | `resp_type: html` without `code.postfetch` | Add `code.postfetch` with an absolute path to a script defining `process(content)` |
| `No valid checkpoint is available to resume` | `--resume` without an interrupted run | Run `apibackuper run full` without `--resume` |
| SSL certificate errors | Broken or self-signed certificate chain | Prefer fixing the CA bundle; otherwise `request.verify_ssl: false` and tell the user |
| HTTP 429 or slow responses | Rate limit | Add a `rate_limit` section and raise `project.default_delay`; `Retry-After` is honoured |
| Only first page saved, no warning | No count metadata and the first page was short | Check `page_size_limit` against the real page size |
| Export has duplicate IDs | Several `update` generations or offset drift | Deduplicate the JSONL by `item_key`; prefer a stable sort |
| `Invalid --where ...` | Unsupported filter syntax | One comparison only, for example `--where "id >= 3"`; no `=` or `AND` |

Useful checks:

```bash
apibackuper run full --dry-run
apibackuper --json run full --max-pages 2
apibackuper estimate full
apibackuper --json info
apibackuper --json verify
```

`run full --dry-run` prints the resolved plan and configuration warnings
without HTTP requests. `run full --max-pages 2` checks two real pages in a
temporary archive. `info` shows the last successful run and stored record count.
