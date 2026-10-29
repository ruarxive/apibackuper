---
title: "Follow"
description: "Fetch detail records by ID or URL, paginate independent rules and manage detail archive recovery"
---
# Follow

Many list endpoints return summaries, with another endpoint for each object's
full record. `follow` reads the completed main backup, builds one target per
identifier and writes the detail responses to ZIP archives. Run the main backup
before collecting details.

## Start with one detail endpoint

For list records such as:

```json
{"id": 42, "title": "Item 42", "detail_url": "https://api.example.com/items/42"}
```

merge this section into the project:

```yaml
follow:
  follow_mode: item
  follow_http_mode: GET
  follow_item_key: id
  follow_pattern: "https://api.example.com/items/{id}"
```

Then run:

```bash
apibackuper run full
apibackuper follow full --dry-run
apibackuper follow full
apibackuper export details.jsonl
```

The example requests `/items/42`, saves its JSON response as `42.json` in
`details.zip`, and exports the detail records when that archive exists. The
ID comes from `follow_item_key`; it is not inferred from `data.item_key`.
Dry-run prints a plan but does not prove each source record contains that field.

## Field reference

| Field | Default / requirement | Meaning |
|-------|-----------------------|---------|
| `follow_mode` | Required for execution | `item`, `prefix` or `url`; `drilldown` is not implemented |
| `follow_http_mode` | `GET` | GET query parameters or POST JSON body |
| `follow_item_key` | Required record path | Scalar identifier used to name/store the response and deduplicate targets |
| `follow_pattern` | Required for `item`/`prefix` | URL format string or literal prefix |
| `follow_param` | Optional | Alias for the ID in formatting, also sent as a request parameter |
| `follow_url_key` | Required for `url` | Record path containing the complete detail URL |
| `follow_data_key` | Omitted | Path to records inside the detail response, used in pagination/export |
| `rules` | Optional YAML list | Independent detail-fetch rules, each based on the original main records |

Record paths use `settings.splitter`. Missing `follow_item_key` fails collection;
use a scalar string or number, not a list/object or a comma-separated composite.
Repeated IDs in main backup history produce one target per key in a rule, not
one detail response per historical version.

A detail request answered with HTTP 404 or 410, or matching a `missing`
[response rule](/configuration/rate-limiting-and-requests#response-rules), does not stop the run. The key,
page and status are written to `details.missing.json` (`details_<name>.missing.json`
for a named rule) beside the archive, a warning is printed, and the remaining keys
are fetched. `follow continue` requests missing keys again. Other failures still
stop the run and keep the partial archive for `follow continue`.

## Choose a URL mode

### Format a URL with record fields: item

`item` formats `follow_pattern` with top-level record fields. With the example
above, `{id}` becomes `42`. If the identifier is a nested field, supply an alias:

```yaml
follow:
  follow_mode: item
  follow_item_key: metadata.id
  follow_param: item_id
  follow_pattern: "https://api.example.com/items/{item_id}"
```

For `{"metadata":{"id":42}}`, this formats `/items/42` and also sends
`item_id=42` as a query parameter (or POST body field). Omit `follow_param` when
you only need existing top-level fields for URL formatting and the API should
not receive an extra identifier parameter. Substitution does not URL-encode
path values; use identifiers suitable for the endpoint's path syntax.

### Append an identifier: prefix

```yaml
follow:
  follow_mode: prefix
  follow_item_key: id
  follow_pattern: "https://api.example.com/items/"
```

This concatenates the prefix and ID to form `/items/42`. Include the slash or
other separator in the prefix; it is not inserted automatically.

### Use a URL from the record: url

```yaml
follow:
  follow_mode: url
  follow_item_key: id
  follow_url_key: detail_url
```

The URL is taken from the record and `follow_pattern` is unused. Supply a usable
absolute URL; relative links are not automatically resolved against the main
endpoint. The project's auth and ordinary headers apply to these requests, so
use URLs allowed to receive that authentication.

## Detail parameters and response wrappers

Additional detail-request values belong in `follow_params.json`, beside the
main configuration:

```json
{"language": "en", "include_history": false}
```

They are separate from the main `params.json`. Each request copies these base
values, then adds the ID parameter and rule pagination values when configured.
All rules share this base file; a rule's `params` object configures pagination,
not arbitrary fixed request values.

If a detail response is `{"record":{"id":42,"title":"Item 42"}}`, set
`follow_data_key: record`. For `{"items":[...]}`, use `items`. Omit the field
for a root object or array. This path is separate from the main `data.data_key`.
Detail payloads need to be JSON for built-in export/pagination. HTML detail
responses can be converted with `code.follow`; selecting XML for the main
backup does not automatically decode XML detail responses.

## Multiple independent rules

```yaml
follow:
  rules:
    - name: profile
      follow_mode: item
      follow_item_key: id
      follow_pattern: "https://api.example.com/items/{id}"
    - name: events
      follow_mode: item
      follow_item_key: id
      follow_pattern: "https://api.example.com/items/{id}/events"
      follow_data_key: events
```

Both rules read the original main backup records. The events rule receives the
same list ID as the profile rule; it does not consume the fetched profile.
Automatic org → department → employee traversal is not implemented.
`follow` can also be a YAML list containing these rule objects directly.

Use simple unique names, such as `profile` or `events`; names are sanitized for
archive filenames. Each named rule produces its own ZIP archive.

## Paginate a detail endpoint

Page-based detail pagination is configured inside a rule:

```yaml
follow:
  rules:
    - name: events
      follow_mode: item
      follow_item_key: id
      follow_pattern: "https://api.example.com/items/{id}/events"
      follow_data_key: events
      iterate_by: page
      params:
        page_number_param: page
        page_size_param: per_page
        page_size_limit: 50
        max_pages: 100
```

For each item ID, pages start at 1. Responses are stored as
`42_page_1.json`, `42_page_2.json`, and so on. A page with fewer than 50 extracted
events ends that item's traversal. This loop does not use main-list total-count
metadata. A missing page-size limit falls back to the main project page size;
`max_pages` defaults to 1,000.

Reaching `max_pages` without a short page raises an error rather than publishing
an assumed complete result. Set a positive limit large enough to include the
terminating short/empty page. Use `iterate_by: page` with a `page_number_param`;
this detail loop does not implement the top-level skip/range calculations.

## Output selection and export

| Source backend | Detail output directory |
|----------------|-------------------------|
| ZIP | Directory containing `storage.zip` |
| Filesystem | The configured main storage directory |
| SQLite | Directory containing the database file |

An unnamed rule writes `details.zip`. Named rules write `details_profile.zip`,
`details_events.zip`, etc. Output remains ZIP regardless of the main backend.

When a `follow` section exists and `details.zip` is present, `export` selects it
instead of the main pages and uses the top-level `follow_data_key`. Named archives
are not automatically combined or selected. For a pipeline requiring the normal
export/getfiles commands, use a project with a single unnamed detail rule and
the corresponding top-level extraction key. For separate named results, read
the archives explicitly through [Python storage access](/development/python-api#direct-storage-access).

Main backup changes do not automatically refresh an existing details archive.
Rerun follow when you need updated details. A reused details archive can otherwise
make a later export show older detail data despite a newer main backup.

## Continue after interruption

`follow full` stages a replacement in `details.zip.partial` (or the named
archive's `.partial`), then publishes it after success. `follow continue`
reuses that staging archive when it exists, or continues the published archive
otherwise, skipping saved response names. Keep ZIP `.journal` sidecars together
with their archive. Follow continuation uses saved objects rather than the
main backup's page checkpoint; there is no `follow --resume` flag.

Changing URL rules or response keys while continuing can mix incompatible
results. Preserve needed output, then use `follow full` for a fresh detail view.
Follow requests use the common authentication, retries and rate limits, but
`request.parallelism` does not parallelize this loop and `hooks.*` are not
invoked here.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Missing identifier error | `follow_item_key` against each extracted main record |
| URL formatting error | Placeholder names, top-level record fields, and any `follow_param` alias |
| Extra ID query parameter | `follow_param` also supplies a request/body field |
| Only one response page per ID | Rule-level `iterate_by` and `params.page_number_param` |
| `max_pages` failure | Actual page size, `follow_data_key`, ignored pagination parameters or a genuinely larger result |
| Export ignores named results | Automatic selection only uses unnamed `details.zip` |
| Continued run fetches nothing new | Saved names are skipped; use full to refresh changed objects |
| "followed objects are missing upstream" warning | Keys in `details.missing.json` returned 404/410 or matched a `missing` rule |
