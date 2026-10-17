---
title: "HTTP request files"
description: "How headers.json, params.json and url_params.json become GET and POST requests"
---
# HTTP request files

Use these files to describe the request independently of how records are extracted.
The YAML `params` section names pagination parameters. Additional request values
live in JSON files beside `apibackuper.yaml`:

| File | Content | If absent |
|------|---------|-----------|
| `headers.json` | Object of HTTP header names and string values | No per-project headers |
| `params.json` | Object of fixed query parameters (GET) or JSON body fields (POST) | Empty object |
| `url_params.json` | Object of URL parameters for `params` and `mixed` modes | Empty object |
| `follow_params.json` | Object of fixed detail-request values, independent of main `params.json` | Empty object |

These paths resolve from the project directory, including with `-p`. JSON files
do **not** expand `${VAR}`. Set credentials through YAML [authentication](/configuration/auth)
or a trusted hook instead. `auth` headers override conflicting `headers.json`
values; the session supplies the configured User-Agent unless overridden.

## GET query parameters

With `project.url: https://api.example.com/items`, `http_mode: GET` and:

```yaml
params:
  query_mode: query
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 2
```

save `params.json`:

```json
{"status": "active", "sort": "id"}
```

and, optionally, `headers.json`:

```json
{"Accept": "application/json", "X-Client": "archive-job"}
```

Page 2 requests `GET https://api.example.com/items?status=active&sort=id&per_page=2&page=2`
with those headers. Query parameter order is not significant. Pagination values
override matching fields from `params.json` on each page. Existing URL queries
are retained, so avoid defining the same key in both the URL and JSON file.

## POST JSON bodies

With the same configuration and `http_mode: POST`, the URL stays
`https://api.example.com/items` and page 2 sends:

```json
{"status": "active", "sort": "id", "per_page": 2, "page": 2}
```

The body is JSON, not form data. For a nested pagination body use parameter
names such as `paging.page` and `paging.limit`; these create or replace nested
dictionary fields using `.`. For example:

```yaml
params:
  page_number_param: paging.page
  page_size_param: paging.limit
  page_size_limit: 2
```

Page 2 with `params.json` containing `{"filter":{"active":true}}` sends:

```json
{"filter": {"active": true}, "paging": {"limit": 2, "page": 2}}
```

See the [local demo](/getting-started/quick-start) or [E-Trust POST example](/use-cases/post-api-backup).

## URL parameter modes

For an endpoint `https://api.example.com/items`, page 2, page size 2 and
`url_params.json` containing `{"lang":"en"}`:

| `query_mode` | URL | Where `params.json` goes |
|--------------|-----|--------------------------|
| `query` (default) | `/items` | GET query or POST JSON; pagination is merged here |
| `params` | `/items;lang=en;per_page=2;page=2` | GET query or POST JSON, separately from URL pagination |
| `mixed` | `/items?lang=en&per_page=2&page=2` | GET query or POST JSON, separately from URL pagination |

In `query` mode, `url_params.json` is unused by backup page construction.
`params` means semicolon path parameters, not a replacement for POST bodies.
It appends raw values; reserve it for APIs requiring that syntax and avoid
URLs already containing a query or fragment. `mixed` URL-encodes query values.
These modes do not substitute `{name}` placeholders into path segments.

## Legacy flat serialization

In the default `query` mode, `params.force_flat_params: true` stringifies each top-level GET parameter,
including nested objects, before URL encoding. It does not expand nested
objects into dotted query keys and is not a general JSON serializer. Use a
plain scalar `params.json` when possible; check the target API's expected
encoding before enabling this compatibility option. It does not change POST
JSON body serialization.

`run full --dry-run` validates configuration and prints a summary; it does not
show every resolved header/body field or prove the API accepts them. Use a
small local or staging API run to inspect actual requests. Diagnostics redact
recognized credentials; avoid writing secrets from custom hooks to logs.


## Precedence and scope

For a normal backup page in `query` mode, request construction follows this order:

1. Load `headers.json` and `params.json` from the project.
2. Apply any `before_run` hook replacements to the base objects.
3. Add the update watermark parameter, if applicable, and current pagination values.
4. Apply `before_request` overrides to that page's URL, headers and parameters.
5. Merge configured `auth` headers, then serialize the GET query or POST JSON body.

A page-number setting therefore replaces an old `page` value in `params.json`;
it is not necessary to maintain that value manually. In `mixed`/`params` modes,
pagination goes into URL parameters, leaving the JSON body as the fixed request
body unless a hook changes it.

The JSON files are loaded for a command's workflow; editing them while a run is
in progress is not a way to update each subsequent request. Keep source filters
fixed while resuming so retained pages describe the same dataset.

`follow` loads `follow_params.json` and ordinary headers, then applies its own
ID/page fields. Attachment downloads use the extracted URL and ordinary headers;
they do not reuse the main POST body. See [follow](/configuration/follow) and
[files](/configuration/files) for those command-specific rules.

## Complete POST example

For a search API accepting this body on page 2:

```json
{"filter":{"status":"active"},"paging":{"page":2,"limit":50}}
```

save the fixed part as `params.json`:

```json
{"filter":{"status":"active"}}
```

and configure the changing fields:

```yaml
project:
  url: https://api.example.com/search
  http_mode: POST
  iterate_by: page
params:
  query_mode: query
  page_number_param: paging.page
  page_size_param: paging.limit
  page_size_limit: 50
data:
  data_key: result.items
  total_number_key: result.total
```

Merge this fragment with required `settings` and `storage` sections from the
[configuration overview](/configuration/). A response such as
`{"result":{"total":75,"items":[...]}}` supplies extraction metadata;
those response paths do not belong in `params.json`.

## Validate request files and diagnose errors

`validate-config` validates YAML, not the semantic contents of every JSON request
file or the remote service's contract. A JSON file must contain a JSON object:
use double-quoted keys/strings, without comments or trailing commas. A local
syntax check is `python -m json.tool params.json`; it does not prove the payload
is accepted by the API.

| Symptom | What to inspect |
|---------|-----------------|
| HTTP 400 or validation error | Parameter names, required fixed filters, JSON body versus query location |
| Every request returns the same page | Actual changing parameter; correct `query_mode` and nested name |
| `${API_TOKEN}` is sent literally | JSON files do not expand environment placeholders; use YAML `auth` |
| Server rejects the content type | POST is serialized as JSON; form encoding is not a supported mode |
| Fixed body field unexpectedly changes | Pagination/watermark override or `before_request` hook |
| Nested GET filter is encoded unexpectedly | The API's required encoding versus ordinary/legacy flat serialization |

The JSON examples illustrate the application payload. Actual header values,
query ordering, and low-level serialization are supplied by the HTTP client.
