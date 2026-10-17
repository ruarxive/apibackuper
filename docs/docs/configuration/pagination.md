---
title: "Pagination"
description: "Choose page, offset or range pagination, calculate request values and diagnose stopping behavior"
---
# Pagination

`project.iterate_by` describes how to obtain the next portion of records.
Configure the API's parameter names under `params`; apibackuper supplies their
values on each request. The same pagination construction is used for GET query
parameters and POST JSON bodies in the default `query_mode: query`.

## Choose a mode

| API contract | `iterate_by` | Required parameter names | First two requests, size 100 |
|--------------|--------------|--------------------------|--------------------------------|
| Page number and size | `page` | `page_number_param`; usually `page_size_param` | `page=1`, then `page=2` |
| Offset and limit | `skip` | `count_skip_param`; usually `page_size_param` | `offset=0`, then `offset=100` |
| Numeric start/end interval | `range` | `count_from_param`, `count_to_param` | `from=0&to=100`, then `from=100&to=200` |

The page size must equal the number of records the API actually returns on a
full page. If the server caps `per_page=100` at 50, set `page_size_limit: 50`.
A short first page can otherwise be mistaken for the end of the dataset.

## Page-number APIs

```yaml
project:
  iterate_by: page
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
  start_page: 1
```

For `GET https://api.example.com/items` the requests include:

```text
/items?per_page=100&page=1
/items?per_page=100&page=2
/items?per_page=100&page=3
```

`start_page` defaults to 1 and must be a positive integer. Page mode sends it
unchanged. Native page numbering starting at 0 is not supported by this setting.
An absent `page_size_param` sends no size parameter; the API's fixed page size
must still match `page_size_limit` for counting and stopping.

## Skip/offset APIs

```yaml
project:
  iterate_by: skip
params:
  count_skip_param: offset
  page_size_param: limit
  page_size_limit: 100
  start_page: 1
```

For internal page `p` and size `n`, the offset is `(p - 1) * n`. Thus the first
three requests use offsets 0, 100 and 200, with `limit=100`. `start_page: 3`
starts at offset 200; it is not an offset of 3 records.

Put a stable sort parameter, if the API supports one, in `params.json`:

```json
{"sort": "id", "direction": "asc"}
```

Parameter names and sort syntax belong to the API. Offset pagination can skip
or repeat objects if inserts/deletes shift positions while the backup runs.

## Numeric ranges

```yaml
project:
  iterate_by: range
params:
  count_from_param: from
  count_to_param: to
  page_size_limit: 100
```

The bounds are `from=(p-1)*n` and `to=p*n`. For the first pages:

| Internal page | `from` | `to` |
|---------------|--------|------|
| 1 | 0 | 100 |
| 2 | 100 | 200 |
| 3 | 200 | 300 |

The API must interpret the upper bound as **exclusive** for these intervals to
be disjoint. Inclusive endpoints repeat boundary records. There is no setting
for subtracting 1 from the upper bound. Range mode calculates record-position
bounds; it is not a date-range iterator or a cursor-based traversal.

## How many pages are fetched?

The first response is used to derive the collection bound:

1. A usable `data.total_number_key` gives `ceil(total / page_size_limit)`.
2. Otherwise, `data.pages_number_key` supplies the page count.
3. Without usable count metadata, the fallback is 20,000 internal pages.

For 250 records and a size of 100, the count is 3 pages. Without count metadata,
responses of 100, 100 and 50 records stop after the short page. If all pages
are exactly full, an additional empty page can be needed to discover the end.

An empty page ends collection without adding an empty data page to the archive.
A bare single-object response ends after that object. When the chosen iteration
mode has no configured pagination parameter, backup collection is limited to
one page even if a total count is available.

`start_page` shifts the start of the internal range; it does not create metadata
for pages skipped deliberately. Use a full run from page 1 for a complete dataset.
For interruption recovery, prefer `run full --resume` rather than editing
`start_page`. See [run](/commands/run) for checkpoint semantics.

## Request location and nested parameters

The `params` section holds parameter **names**, not arbitrary filter values.
Store fixed values in `params.json`. With a POST body:

```yaml
project:
  http_mode: POST
params:
  page_number_param: paging.page
  page_size_param: paging.limit
  page_size_limit: 100
```

page 2 receives `{"paging":{"limit":100,"page":2}}` merged into that body.
Use [HTTP request files](/configuration/http-requests) to choose GET/POST and
`query_mode: query`, `params` or `mixed`. The last two put pagination in the URL
rather than merging it into the body.

## Follow pagination is separate

A paginated `follow.rules` entry uses its own `params` object and a short-page
stopping rule. The top-level list pagination settings do not automatically
paginate each detail endpoint. See [paginated follow rules](/configuration/follow#paginate-a-detail-endpoint).

## Common failures

| Symptom | Likely cause / action |
|---------|-----------------------|
| Only one page saved | Missing parameter name for the chosen mode, short page, or wrong `data_key` |
| Every page contains the same records | Wrong parameter name/location; the API ignores the changing value |
| Collection stops after the first 50 records | Server page-size cap differs from `page_size_limit` |
| Unexpected page count | Record total confused with page total, or metadata path does not exist |
| Repeated/missing IDs | Unstable sorting, changing source, or inclusive range bounds |
| Cursor/next-link API cannot be expressed | Cursor tokens and next-link traversal are not implemented |

`detect` can suggest field names, but verify request values and stopping behavior
with a sample collection. Read [backup completeness](/getting-started/data-integrity)
before relying on a successful exit as evidence that every source record exists
in the archive.
