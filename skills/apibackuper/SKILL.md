---
name: apibackuper
description: Collect every record from a paginated HTTP API (JSON, XML or server-rendered HTML) into a resumable local archive and export it to JSONL or Parquet, using a YAML project instead of a hand-written requests/httpx loop. Use when asked to write a parser, scraper, crawler, harvester, downloader or ETL extract step for an API or registry; to download, collect, mirror, archive or back up all records or a whole dataset from an endpoint; or to build a repeatable or incremental API data collection. Russian triggers - написать парсер, парсер API, выгрузить данные из API, скачать все записи, собрать датасет, сборщик данных, архивировать API, резервная копия API. Not for JavaScript-rendered sites, browser logins, CAPTCHAs or a single one-off request.
---

# apibackuper

`apibackuper` is a CLI that pages through an HTTP API, saves every response,
resumes after failures, records provenance and exports records. A project is a
directory with `apibackuper.yaml` and optional request files. Pagination,
retries, rate limits, authentication, resume, incremental updates and export
are configuration, not code.

Prefer it over writing a collector. The only code you should write is a small
hook or extraction function for what the configuration cannot express, or a
post-processing step over the exported JSONL.

## Decide first

| The source | Use apibackuper? |
|------------|------------------|
| List/search endpoint returning records page by page (page number, offset, numeric range, cursor token, next URL, `Link` header) | Yes |
| GET with query parameters, or POST with a JSON body | Yes |
| JSON or XML responses | Yes |
| Server-rendered HTML listing paged through the URL | Yes, with `resp_type: html` and a `code.postfetch` extractor |
| Basic, Bearer, API key header, OAuth2 (refresh token or client credentials) | Yes |
| Detail endpoint per record, or attached files to download | Yes, `follow` rules and `getfiles` |
| Pages rendered by JavaScript, browser login, CAPTCHA | No: use a browser tool |
| One request or a few fixed URLs | No: use `curl` |
| Iteration only by date windows, no page/offset/cursor | Not natively: one project per window, or a `before_request` hook |
| Form-encoded POST bodies | No: POST bodies are JSON only |

Install if `apibackuper --help` fails: `pipx install apibackuper` or
`pip install apibackuper` (Python 3.10+). If `apibackuper init --help` fails,
the installed version is older than 3.1: `pipx upgrade apibackuper` or
`pip install --upgrade apibackuper`. Add `apibackuper[recommended]` for
Parquet and WARC export.

## Workflow

Put `--json` before any command to get exactly one JSON object on stdout
(`{"ok": true, "result": ...}` or `{"ok": false, "error": {"code", "message",
"hints"}}`); other output goes to stderr and progress bars are off.

1. **Create the project from the endpoint.**

   ```bash
   apibackuper --json init myproject --url "https://api.example.com/items"
   ```

   `init` sends one request plus a few probes (`page=2`, `per_page=100`, ...)
   and writes a complete `apibackuper.yaml`. Its report lists the detected
   settings, the record `fields`, a `sample_record`, `warnings` and
   `next_steps`. Options: `--method POST --body '{"q": "*"}'`,
   `-H "Accept: application/json"` (repeatable), `--auth bearer|apikey|basic`
   with `--auth-env VAR` (secrets stay `${VAR}` placeholders; export the
   variable first so the endpoint can be probed), `--data-key` to override the
   records path. Query parameters in the URL move into `params.json`.

   Read the `warnings`. If pagination was not detected, open the API docs or
   request page 2 with `curl`, then set the names by hand from
   [references/config-patterns.md](references/config-patterns.md). Do not use
   `apibackuper create`: it writes a legacy INI file and ignores its `--url`
   and `--datakey` options.
2. **Validate offline.**

   ```bash
   cd myproject
   apibackuper validate-config --strict --json
   ```

   Each error and warning has a `path`, `message` and `hint`. A warning about a
   missing pagination parameter means a run would save only the first page.
   `apibackuper schema` prints every allowed field.
3. **Check two pages of real data.**

   ```bash
   apibackuper --json run full --max-pages 2
   ```

   This sample run uses a temporary archive and leaves the project untouched.
   Check `records`, `total_reported`, `more_pages`, `fields` and `preview`.
   It fails with error code `pagination_ignored` when page 2 repeats page 1 and
   with `backup_incomplete` when the API caps the page size below
   `page_size_limit`. Fix the YAML and repeat until it passes.
4. **Collect.**

   ```bash
   apibackuper --json run full
   ```

   A nonzero exit means the backup is incomplete and the previous archive is
   kept. Fix the cause, then continue with `apibackuper run full --resume`.
5. **Export and check.**

   ```bash
   apibackuper export items.jsonl
   apibackuper --json info
   apibackuper --json verify
   ```

   Compare `result.statistics.storage.total_records` from `info` with the API
   total. Use `--fields id,title` and `--where "id >= 3"` on `export` to select
   data, and `.jsonl.gz`, `.jsonl.zst` or `.parquet` file names for other formats.
6. **Hand over.** Give the user the project directory, the commands to rerun
   (`apibackuper update` for new or changed records, see the patterns file), and
   the export path.

Run commands inside the project directory, or pass `-p PATH` to each command.
`apibackuper detect --url URL` prints the same detection as YAML without
creating a directory.

## Minimal project

```yaml config
settings:
  name: items
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
data:
  data_key: items
  total_number_key: total
  item_key: id
storage:
  storage_type: zip
```

| API contract | Settings |
|--------------|----------|
| `?page=2&per_page=100` | `iterate_by: page`, `page_number_param`, `page_size_param` |
| `?offset=200&limit=100` | `iterate_by: skip`, `count_skip_param`, `page_size_param` |
| `?from=200&to=300` (exclusive end) | `iterate_by: range`, `count_from_param`, `count_to_param` |
| Token in response, sent back as a parameter | `iterate_by: cursor`, `params.cursor_param`, `data.next_cursor_key` |
| Next page URL in the body | `iterate_by: next_url`, `data.next_url_key` |
| `Link: <...>; rel="next"` header | `iterate_by: link_header` |
| Records at `result.items` | `data.data_key: result.items` (dot path) |
| Response is a bare list | omit `data_key` |
| Total record count at `meta.total` | `data.total_number_key: meta.total` |
| Total page count instead | `data.pages_number_key` |

## Extend, do not rewrite

- Fixed query parameters or a POST body: `params.json` beside the YAML.
  Headers: `headers.json`. These JSON files do **not** expand `${VAR}`.
- Secrets: an `auth` section with `"${VAR}"` placeholders in YAML. Never put a
  literal token in a file you hand back.
- Per-request changes (signatures, computed parameters, API key in the query
  string from an environment variable): a `hooks.before_request` script with
  `hook(context)` returning `{"params": ...}` or `{"headers": ...}`.
- HTML or another custom body: `project.resp_type: html` and
  `code.postfetch: /abs/path/extract.py` with `process(content)` returning a
  list of records.
- Detail objects per record: `follow` rules, then `apibackuper follow full`.
- Attachments: a `files` section, then `apibackuper getfiles`.
- Error bodies with status 200, quota pages: `request.response_rules`.
- Embedding in Python: `from apibackuper.cmds.project import ProjectBuilder`.

Exact YAML for each case: [references/config-patterns.md](references/config-patterns.md).
Errors and fixes: [references/troubleshooting.md](references/troubleshooting.md).

## Pitfalls

- `params.page_size_limit` must equal the number of records the API really
  returns on a full page. `init` and `detect` probe it; when you set it by
  hand, a larger value makes the run fail with "returned N records ... before
  page M".
- The `params` section holds parameter **names**; values go into `params.json`.
- `total_number_key` is a record count; `pages_number_key` is a page count.
- Unknown keys in a section fail validation. Check field names with
  `apibackuper schema` rather than guessing.
- Export output directories must exist and lie outside the storage directory.
- Export keeps history: after several `update` runs a record can appear more
  than once. Deduplicate downstream by `item_key` if the user needs a snapshot.
- `--verbose` writes debug logs to `apibackuper.log` in the working directory.
