# apibackuper configuration patterns

Every complete project needs the sections `settings`, `project`, `params`,
`data` and `storage`. The fragments below replace or add sections of the
minimal project in `SKILL.md`. Unknown keys fail validation, so copy names
exactly. Full field reference:
<https://ruarxive.org/apibackuper/configuration/reference>.

## Pagination

### Page number

```yaml
project:
  iterate_by: page
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
  start_page: 1
```

Requests `page=1`, `page=2`, ... `start_page` must be 1 or more; APIs whose
first page is 0 need `iterate_by: skip` or a `before_request` hook.

### Offset and limit

```yaml
project:
  iterate_by: skip
params:
  count_skip_param: offset
  page_size_param: limit
  page_size_limit: 100
```

Sends `offset=0`, `offset=100`, ... Put a stable sort (for example
`{"sort": "id"}`) into `params.json` when the API supports one.

### Numeric range

```yaml
project:
  iterate_by: range
params:
  count_from_param: from
  count_to_param: to
  page_size_limit: 100
```

Sends `from=0&to=100`, `from=100&to=200`. The API must treat `to` as exclusive.

### Cursor token

```yaml
project:
  iterate_by: cursor
params:
  cursor_param: cursor
  page_size_param: limit
  page_size_limit: 100
data:
  data_key: items
  next_cursor_key: meta.next_cursor
```

### Next URL in the body

```yaml
project:
  iterate_by: next_url
params:
  page_size_limit: 100
data:
  data_key: results
  next_url_key: next
```

A literal key such as `@odata.nextLink` is read as written. Next URLs on
another host fail unless `params.allow_cross_host_next: true`.

### Link header

```yaml
project:
  iterate_by: link_header
params:
  page_size_limit: 100
data:
  data_key: items
```

Cursor, next-URL and Link-header modes are sequential: keep
`request.parallelism` at 1.

### Stopping

With `data.total_number_key` (records) or `data.pages_number_key` (pages) the
run knows how many pages to fetch and fails on a short page before the end.
Without them it stops at the first short or empty page.

## Request shape

### Fixed query parameters (GET)

`params.json` beside `apibackuper.yaml`:

```json
{"status": "active", "sort": "id"}
```

Pagination values override matching keys on each page.

### POST with a JSON body

```yaml
project:
  url: https://api.example.com/search
  http_mode: POST
params:
  page_number_param: paging.page
  page_size_param: paging.limit
  page_size_limit: 100
```

`params.json` holds the fixed body, for example `{"filter": {"active": true}}`.
Page 2 then sends
`{"filter": {"active": true}, "paging": {"limit": 100, "page": 2}}`.
Dotted names create nested fields. Bodies are JSON, never form data.

### Headers

`headers.json`:

```json
{"Accept": "application/json"}
```

JSON request files do not expand `${VAR}`; keep secrets in `auth`.

## Authentication

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

```yaml
auth:
  type: apikey
  api_key: "${API_KEY}"
  api_key_header: X-API-Key
```

```yaml
auth:
  type: basic
  username: reader
  password: "${API_PASSWORD}"
```

```yaml
auth:
  type: oauth2
  grant_type: client_credentials
  auth_url: https://auth.example.com/oauth/token
  client_id: backup-client
  client_secret: "${OAUTH_CLIENT_SECRET}"
  scope: "catalog.read"
```

Bearer tokens go without the `Bearer ` prefix. A missing variable stops the
command with exit status 2. For an API key in the query string, add it in a
`before_run` hook from `os.environ` (see Hooks), not in `params.json`.

## Response formats

### XML

```yaml
project:
  resp_type: xml
data:
  data_key: response.items.item
  total_number_key: response.total
```

XML is parsed with `xmltodict`: the root element is the first path segment,
attributes become `@name` keys and text becomes `#text`. A single child
element is returned as an object, not a list.

### Server-rendered HTML

```yaml
project:
  resp_type: html
code:
  postfetch: /abs/path/to/project/extract.py
data:
  data_key: items
```

`extract.py`:

```python
from lxml import html


def process(content):
    tree = html.fromstring(content)
    rows = tree.xpath("//table[@id='results']//tr[td]")
    return {"items": [{"id": row.xpath("string(td[1])"), "name": row.xpath("string(td[2])")} for row in rows]}
```

`content` is the raw body as bytes. Return a list (and omit `data_key`) or a
wrapper matching `data_key`. Use absolute paths for `code.postfetch`.

## Request policy

```yaml
project:
  default_delay: 0.5
rate_limit:
  enabled: true
  requests_per_second: 2
  burst_size: 1
request:
  connect_timeout: 10
  read_timeout: 60
  parallelism: 1
  retry:
    max_retries: 5
    backoff_strategy: exponential
    initial_delay: 2
  response_rules:
    - body_key: error
      action: retry
    - content_type: text/html
      action: fail
    - status: [403, 451]
      action: missing
```

Without a status list, 429, 500, 502, 503 and 504 are retried, and
`Retry-After` is honoured. `request.verify_ssl: false` disables certificate
checks for broken government endpoints; say so to the user when you set it.

## Hooks

```yaml
hooks:
  before_run: hooks/before_run.py
  before_request: hooks/before_request.py
```

`hooks/before_run.py`, adding a query-string API key from the environment:

```python
import os


def hook(context):
    params = dict(context.get("params") or {})
    params["api_key"] = os.environ["CATALOG_API_KEY"]
    return {"params": params}
```

`before_request` receives `page`, `url`, `headers` and `params` for each page
and may return new `url`, `headers` or `params`. Returned objects replace the
old ones, so copy them first. Each call runs in a fresh process with a
30-second limit; globals do not persist.

## Incremental updates

```yaml
project:
  update_mode: by_timestamp
params:
  update_since_param: changed_after
```

`apibackuper update` sends the start time of the last successful run as
`changed_after`. For a change field in each record use
`update_mode: by_change_key`, `params.change_key_param` and `data.change_key`.
The API must support the filter. Each update keeps its own generation; export
returns all generations, so deduplicate by `item_key` for a current snapshot.

## Detail endpoints

```yaml
data:
  data_key: items
  item_key: id
follow:
  follow_mode: item
  follow_pattern: "https://api.example.com/items/{id}"
  follow_item_key: id
  follow_param: id
```

Run `apibackuper follow full` after `run full`. Export then reads the details
archive. Several named rules under `follow.rules` are independent branches,
not a chain.

## Attached files

```yaml
files:
  fetch_mode: prefix
  root_url: ""
  keys: document_url
  storage_mode: filepath
  file_storage_type: filesystem
```

Run `apibackuper getfiles` after `run full`. The main storage must be ZIP.
`files.max_file_size` skips large downloads.

## Storage

```yaml
storage:
  storage_type: zip
  storage_path: storage
```

`zip` is the default choice; `filesystem` and `sqlite` also work for pages.
Keep `storage.capture.metadata: true` (default) for provenance.
