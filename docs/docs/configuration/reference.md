---
title: "Configuration reference"
description: "Required fields, effective defaults, supported combinations and compatibility limits for every YAML section"
---
# Configuration reference

Use this page to look up a field's type, effective default and runtime role.
For a complete starting file and loading/path rules, see the
[configuration overview](/configuration/). Detailed pages explain the decisions
behind each section.

The canonical schema is `apibackuper/schemas/config_schema.json`. Required
sections are `settings`, `project`, `params`, `data` and `storage`. Each must be
an object; `data: {}` is valid for a root array/object. Unknown keys are rejected
in normal top-level sections. Follow rule objects have more permissive schema
validation, so passing validation there does not prove execution support.

## Reading the defaults

Defaults below are the loader's effective fallbacks, not values inserted into
your file. Omitted optional values differ from explicit YAML `null`: most string
and numeric fields do not accept null. Use YAML numbers/booleans for typed fields,
and quote string values such as credentials and dates.

`${VAR}` expansion happens before validation and produces strings. It is useful
for secrets; a numeric field such as `page_size_limit: "${PAGE_SIZE}"` still
becomes a string and does not satisfy an integer schema. JSON request files do
not expand these placeholders. `${VAR:-default}` handles unset/empty variables;
there is no automatic `.env` loading.

Validate the complete file with:

```bash
apibackuper validate-config --strict -p /srv/catalog
apibackuper run full --dry-run -p /srv/catalog
```

Both are offline checks. The API's credentials, actual response keys, page-size
cap and server-side filter semantics still need verification against the service.

## settings

| Field | Type / default | Requirement and behavior |
|-------|----------------|--------------------------|
| `name` | string; no default | **Required** project name |
| `initialized` | boolean; omitted | Legacy scaffold metadata; not a substitute for complete config |
| `id` | string; omitted | Descriptive metadata identifier |
| `splitter` | string; `.` | Nested response/record path separator; not JSONPath |
| `logfile` | string; `apibackuper.log` | Relative to working directory unless absolute |
| `state_file` | string; project's `apibackuper_state.json` | Successful-run state/watermark; explicit override is used as written |
| `checkpoint_file` | string; project's `apibackuper_checkpoint.json` | Resume progress; explicit override is used as written |
| `checkpoint_interval_pages` | integer ≥ 0; `1` | Periodic saves every N pages; 0 leaves lifecycle saves enabled |

Do not share recovery files between projects. Keep config and data files
consistent with their checkpoint during resume. See [project and data](/configuration/project-and-data).

## project

| Field | Type / default | Requirement and behavior |
|-------|----------------|--------------------------|
| `url` | HTTP(S) URI string | **Required** list/search endpoint |
| `http_mode` | `GET` or `POST` | **Required**; POST is JSON, not form data |
| `description` | string; omitted | Dataset purpose/source description |
| `work_modes` | string; omitted | Legacy declaration such as `full,incremental,update`; does not enforce an allowlist |
| `iterate_by` | `page`, `skip`, `range`, `cursor`, `next_url`, `link_header`; `page` | Main backup pagination; cursor modes are sequential |
| `resp_type` | `json`, `xml`, `html`; `json` | Main response decoding; HTML requires extraction code |
| `detect` | boolean; `false` | Infer selected keys from the first JSON response |
| `update_mode` | `by_change_key`, `by_timestamp`, `custom_script` | Conditional fallback described below; custom script is reserved/rejected |
| `default_delay` | number ≥ 0; `0.5` | Seconds slept after successful requests |
| `retry_delay` | integer ≥ 0; `5` | Fallback retry delay in seconds |
| `retry_count` | integer ≥ 0; `5` | Fallback retries after the initial attempt |
| `force_retry` | boolean; `false` | Legacy accepted field; configure active policy under `request.retry` |

If `update_mode` is omitted, a configured `data.change_key` selects change-key
mode; otherwise timestamp mode is selected. The matching request parameter and
a successful saved watermark are needed to send a selective filter. Work-mode
metadata alone does not make an endpoint incremental.

## params

| Field | Type / default | Requirement and behavior |
|-------|----------------|--------------------------|
| `page_size_limit` | integer ≥ 1 | **Required** expected records per full page |
| `start_page` | integer ≥ 1; `1` | Internal start page; sent unchanged in page mode |
| `page_number_param` | string; omitted | Page-mode request parameter; e.g. `page` or `paging.page` |
| `page_size_param` | string; omitted | Request parameter receiving page size |
| `cursor_param` | string; omitted | Cursor-mode request parameter receiving the token from the previous response |
| `allow_cross_host_next` | boolean; `false` | Follow next-page URLs on another host |
| `count_skip_param` | string; omitted | Skip-mode offset `(page-1)*size` |
| `count_from_param` | string; omitted | Range lower bound `(page-1)*size` |
| `count_to_param` | string; omitted | Range upper bound `page*size`; no automatic inclusive adjustment |
| `query_mode` | `query`, `params`, `mixed`; `query` | Put changing values in query/body, semicolon URL params, or URL query respectively |
| `force_flat_params` | boolean; `false` | Legacy GET top-level value serialization in default query mode |
| `change_key_param` | string; omitted | API request field receiving the previous successful change key |
| `update_since_param` | string; omitted | API request field receiving the successful timestamp watermark |

This section holds parameter names. Fixed request values belong in
`params.json`; changing values overwrite matching fields during page construction.
Request-body nested fields use dot notation. See [pagination](/configuration/pagination)
and [HTTP request files](/configuration/http-requests).

## data

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `data_key` | string; omitted | Path from response root to records; omit for root list/object |
| `total_number_key` | string; omitted | Path from response root to total **record** count |
| `pages_number_key` | string; omitted | Path from response root to total **page** count; fallback after record total |
| `next_cursor_key` | string; omitted | `cursor` mode: path to the next token; missing or empty ends collection |
| `next_url_key` | string; omitted | `next_url` mode: path or literal key of the next URL; missing ends collection |
| `item_key` | string; omitted | Identifier metadata; does not build an index or deduplicate archives |
| `change_key` | string; omitted | Path from each extracted record to a comparable change value |

`settings.splitter` separates these paths. A configured `data_key` must exist.
Follow requires its own `follow_item_key`; comma-separated `item_key` metadata
does not construct a composite follow identifier. Counts bound collection,
while short/empty pages can end it earlier. See [extraction and updates](/configuration/project-and-data).

## storage

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `storage_type` | `zip`, `filesystem`, `sqlite` | **Required** main backend |
| `storage_path` | string; `storage` | Directory for ZIP/filesystem; database filename for SQLite |
| `compression` | boolean; optional | Accepted; CLI ZIP always uses Deflate |
| `compression_level` | integer 0–9; optional | Reserved, not applied to CLI writes |
| `max_file_size` | integer ≥ 0; optional | Reserved bytes value; no splitting/size cap |
| `split_files` | boolean; optional | Reserved; no automatic archive splitting |
| `capture.metadata` | boolean; `true` | Write `exchange_N.json` provenance beside each page |
| `capture.raw_body` | `auto`, `always`, `never`; `auto` | Write the original body as `raw_N.<ext>`; `auto` only for non-JSON responses |

Relative paths resolve from the project. Full backups stage at a sibling
`.partial` path; ZIP can also have a `.journal` directory. Changing the backend
setting does not convert old data. See [storage and recovery](/configuration/storage).

## auth

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `type` | `basic`, `bearer`, `apikey`, `oauth2` | Required when configuring usable authentication; omit the whole section for a public API |
| `username` | string; omitted | Basic auth username |
| `password` | string; omitted | Basic secret; precedes `password_file` |
| `password_file` | string; omitted | File containing only the password, whitespace stripped |
| `token` | string; omitted | Access token without `Bearer ` prefix; precedes `token_file` |
| `token_file` | string; omitted | Bearer/OAuth2 access-token file, whitespace stripped |
| `api_key` | string; omitted | Header API key; no dedicated API-key-file field |
| `api_key_header` | string; `X-API-Key` | Header name for `apikey` |
| `auth_url` | URI string; omitted | OAuth2 form-POST refresh endpoint |
| `refresh_token` | string; omitted | OAuth refresh token; no dedicated refresh-token-file field |

Credential-file paths are relative to the working directory. Files are read at
load time. OAuth refresh is 401-triggered and updates tokens in memory only.
See [authentication](/configuration/auth) for required combinations and provider limits.

## rate_limit

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `enabled` | boolean; `true` with section | false disables the configured limiter |
| `requests_per_second` | positive number; omitted | Token refill rate; fractional rates allowed |
| `requests_per_minute` | integer ≥ 0; omitted | Rolling minute cap; 0 means no minute cap |
| `requests_per_hour` | integer ≥ 0; omitted | Rolling hour cap; 0 means no hour cap |
| `burst_size` | integer ≥ 1; `5` | Initial/capacity tokens for the per-second bucket |

No section, or no active quota, means no effective rate cap. Quotas apply in
one process rather than across all account consumers.

## request

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `timeout` | integer ≥ 1; `120` | Legacy value; does not replace active connect/read pair |
| `connect_timeout` | integer ≥ 1; `30` | Connection timeout seconds |
| `read_timeout` | integer ≥ 1; `120` | Read inactivity timeout seconds, not whole-job duration |
| `verify_ssl` | boolean; `true` | No CA-bundle path in this field |
| `user_agent` | string; `apibackuper/<version>` | Session User-Agent |
| `max_redirects` | integer ≥ 0; `5` | Maximum followed redirects |
| `allow_redirects` | boolean; `true` | Allow redirect handling |
| `parallelism` | integer ≥ 1; `1` | Concurrent main backup page workers |
| `proxies` | string or schema-accepted object | Use implemented `http=URL,https=URL` string form; ordinary YAML mapping is not applied correctly |
| `retry.max_retries` | integer ≥ 0; `project.retry_count` | Retries after the initial attempt |
| `retry.backoff_strategy` | `fixed` or `exponential`; `fixed` | Retry delay calculation |
| `retry.initial_delay` | integer ≥ 0; `project.retry_delay` | Delay base in seconds |
| `retry.max_delay` | integer ≥ 0; `max(retry_delay,retry_delay*4)` | Cap on configured backoff, not server Retry-After |
| `retry.retry_on_status` | integer array, HTTP 100–599 | Explicit retry statuses; fallback described below |

Flat compatibility keys `retry_max_retries`, `retry_backoff_strategy`,
`retry_initial_delay`, `retry_max_delay`, `retry_on_status` override the
corresponding nested values. Flat status values also accept comma-separated
strings. Missing retry status configuration falls back to
`error_handling.retry_on_errors`, then `[429,500,502,503,504]`. An empty nested status
list can still use the fallback; set `max_retries: 0` to disable ordinary retries.
OAuth refresh is a separate 401-handling step.

See [request policy](/configuration/rate-limiting-and-requests) for delay examples,
proxy syntax, quota scope and total request budgets.

## error_handling and logging

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `error_handling.retry_on_errors` | Integer array or comma-separated string; `[429,500,502,503,504]` | Fallback retry statuses |
| `error_handling.max_consecutive_errors` | integer ≥ 0; `10` | Stop after this many consecutive unresolved page failures; 0 stops on the first failure, not unlimited |
| `error_handling.continue_on_error` | boolean; `true` | Try later pages after failure; incomplete runs still exit unsuccessfully |
| `logging.level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | DEBUG without section, INFO for empty logging section |

`--verbose` enables DEBUG file/console output after project initialization,
overriding the configured threshold on commands that support that flag. The
log path comes from `settings.logfile` and resolves from the working directory.

## follow, files, hooks and code

### follow

`follow` accepts a single rule object, an object with `rules: [...]`, or a list
of independent rules. Rule values override corresponding top-level defaults.

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `follow_mode` | string | Executable values: `item`, `url`, `prefix`; schema also accepts unimplemented `drilldown` |
| `follow_http_mode` | `GET` or `POST`; `GET` | Detail request method |
| `follow_item_key` | string | Required scalar ID path in every main record |
| `follow_pattern` | string | URL format for item mode, literal prefix for prefix mode |
| `follow_param` | string; omitted | ID alias for formatting and additional request parameter |
| `follow_url_key` | string | Complete URL path in the record for URL mode |
| `follow_data_key` | string; omitted | Detail record wrapper path for pagination/export |
| `rules[].name` | string; omitted | Archive suffix, e.g. `details_events.zip` |
| `rules[].iterate_by` | string; omitted | Use `page` for implemented detail page-number pagination |
| `rules[].params.page_number_param` | string | Required to activate rule page iteration |
| `rules[].params.page_size_param` | string; omitted | Parameter receiving rule page size |
| `rules[].params.page_size_limit` | integer; main page size | Expected rule full-page record count |
| `rules[].params.max_pages` | positive integer; `1000` | Per-ID safety bound; reaching it before a short page fails |

`follow_params.json` supplies fixed detail-request values. Rules read the main
records independently; they do not chain their output. Only unnamed
`details.zip` is selected automatically by normal export/getfiles. See
[follow](/configuration/follow) for source/output rules and continuation.

### files

| Field | Type / default | Interpretation |
|-------|----------------|----------------|
| `fetch_mode` | `prefix` or `pattern` | **Required** URL construction mode |
| `root_url` | string | **Required** prefix/pattern; empty string preserves complete URLs |
| `keys` | string | **Required** comma-separated record paths, without spaces around commas |
| `default_ext` | string; omitted | Extension for ID-mode saved filenames |
| `storage_mode` | `filepath` or `id`; `filepath` | URL-path name or extracted-value name |
| `file_storage_type` | `zip` or `filesystem`; `zip` | Downloaded-byte output; main source must still be ZIP |
| `use_aria2` | boolean or compatibility string; false | Queue transfers through fixed local aria2 RPC endpoint |

The discovery cache is reused until removed; existing output filenames are
skipped. `default_ext` does not convert content and `filepath` does not include
host/query in the name. See [files](/configuration/files) for collision handling,
source selection and aria2 policy.

### hooks and code

| Field | Type | Contract |
|-------|------|----------|
| `hooks.before_run` | script path | Base headers/params overrides |
| `hooks.before_request` | script path | Per-page URL/headers/params overrides |
| `hooks.after_response` | script path | Observe successful fetch snapshot |
| `hooks.after_page` | script path | Observe cumulative record count and current page bytes |
| `hooks.after_run` | script path | Observe successful collection/publication summary |
| `code.postfetch` | script path | In-process `process(content)` for HTML main responses |
| `code.follow` | script path | In-process `process(content)` for HTML detail responses |

Hook paths resolve from the project; use absolute legacy extraction paths for
portable invocation. Lifecycle callbacks use a separate process and 30-second
timeout, return JSON, and run for backup/update rather than every command.
Extraction scripts have a different failure/timeout model. See the complete
[hook contract](/configuration/hooks).

## Supported configuration does not always mean active behavior

| Setting / combination | Current status |
|-----------------------|----------------|
| `storage.compression_level`, `max_file_size`, `split_files` | Accepted but reserved |
| `project.update_mode: custom_script` | Accepted by schema, rejected by execution |
| `follow_mode: drilldown` | Accepted by schema, rejected by execution |
| `request.proxies` as a YAML object | Accepted by schema; use string form for effective proxy setup |
| `data.item_key` / `project.work_modes` | Descriptive settings, not deduplication/filter implementation |
| Main SQLite/filesystem plus `getfiles` | Unsupported main source for file discovery |
| Several follow rules | Independent requests; no automatic multi-hop traversal or export merge |

These distinctions matter when copying a schema-valid template. Verify the
selected command's behavior and a small sample export before a large job.
