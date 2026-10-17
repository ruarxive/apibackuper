---
title: "Hooks"
description: "Implement lifecycle callbacks and extraction scripts with exact contexts, return contracts and recovery behavior"
---
# Hooks

Use lifecycle hooks to customize a backup's page requests or record operational
information. Use extraction scripts when a response body must be transformed
before records can be selected. These extension points have different function
signatures and execution models.

## Choose the extension point

| Need | Configure | Function | Execution |
|------|-----------|----------|-----------|
| Add a header or fixed parameter before a run | `hooks.before_run` | `hook(context)` or `run(context)` | Separate Python process |
| Adjust each page's URL, headers or body parameters | `hooks.before_request` | Same | Separate process per callback |
| Observe a returned page or saved-page progress | `hooks.after_response`, `after_page` | Same | Separate process per callback |
| Observe a successfully published backup | `hooks.after_run` | Same | Separate process |
| Parse HTML or custom non-JSON content | `code.postfetch` | `process(content)` | Main Python process |
| Parse HTML detail responses | `code.follow` | `process(content)` | Main Python process |

Hooks run with the user's filesystem/network permissions. Python's `-I` option
isolates interpreter settings; it does not sandbox a script. Only configure
trusted code. `run full --dry-run` does not execute these scripts.

## Register lifecycle scripts

```yaml
hooks:
  before_run: hooks/before_run.py
  before_request: hooks/before_request.py
  after_response: hooks/after_response.py
  after_page: hooks/after_page.py
  after_run: hooks/after_run.py
```

Each path resolves from the project directory unless absolute. Configure only
the callbacks you need; missing optional entries do nothing. Each configured
file defines `hook(context)` or the fallback name `run(context)`, returns a
JSON-serializable value, and must finish within 30 seconds.

These callbacks belong to `run`/`update`. They are not global middleware for
`estimate`, `detect`, `follow` or `getfiles`.

## Request lifecycle and concurrency

For a normal page-collection run, the sequence is:

```text
before_run
  before_request(page)
  HTTP attempt(s), retries and any OAuth refresh
  after_response(page)
  decode, extract records and save the page
  after_page(page)
  ... remaining pages ...
publish archive and successful state
after_run
```

`before_request` and `after_response` wrap the page fetch, not every transport
attempt inside its retry budget. A failed HTTP fetch has no successful
`after_response` callback. A response can reach `after_response` and still fail
later JSON parsing or record extraction.

With parallel pages, request callbacks can run concurrently and finish out of
order. Saved pages are consumed in order by the collector. Every callback starts
a fresh subprocess: Python globals in a hook file do not persist across calls.
Use concurrency-safe external storage if callbacks need shared state.

## Context and return contract

| Hook | Context keys | Applied return keys |
|------|--------------|---------------------|
| `before_run` | `mode`, `project_path`, `headers`, `params` | `headers`, `params` |
| `before_request` | `mode`, `page`, `url`, `headers`, `params` | `url`, `headers`, `params` |
| `after_response` | Same page request context plus `response` | None |
| `after_page` | `mode`, `page`, `records_processed`, `bytes_written` | None |
| `after_run` | `mode`, `pages_processed`, `records_processed`, `bytes_processed`, `last_page`, `last_change_key`, `errors` | None |

`mode` is `full`, `continue` or `update`. Before-request contexts contain
page-specific parameters after pagination construction. The HTTP executor merges
`auth` headers afterward, so overriding `Authorization` in a hook can still be
superseded by the configured auth handler. Contexts can contain credentials
supplied through JSON files or earlier hooks.

### Modify request headers without losing existing values

Save as `hooks/before_request.py`:

```python
def hook(context):
    headers = dict(context.get("headers", {}))
    headers["X-Archive-Client"] = "nightly"
    return {"headers": headers}
```

The return dictionary overrides named objects; it does not recursively merge
their contents. Returning `{"headers":{"X-Archive-Client":"nightly"}}` alone
would replace the previous header object. Copy existing `params` in the same
way before adding a filter or request field. Return `None` to leave everything
unchanged. Returning a value from the observer hooks does not modify stored data.

`before_run` changes the base parameters, after which pagination/update fields
are applied. `before_request` can alter the page request that is about to be
sent. A hook cannot bypass later URL/body serialization merely by returning an
arbitrary Requests keyword; only the keys in the table are applied.

### Observe response metadata

The `response` object is a JSON snapshot, not a live Requests response:

```json
{
  "status_code": 200,
  "headers": {"Content-Type": "application/json"},
  "url": "https://api.example.com/items?page=2",
  "text": "{\"items\":[{\"id\":42}]}",
  "text_truncated": false
}
```

Text is limited to 2,000 characters and can be absent. Do not parse this preview
as if it were the complete response body. To transform records, use extraction
scripts instead. Response headers, URLs and previews can contain sensitive data.

### Interpret saved-page counters

An `after_page` context can look like:

```json
{"mode":"full","page":2,"records_processed":200,"bytes_written":17640}
```

`records_processed` is **cumulative stored-record progress** for the current
collection, initialized from recovery progress when resuming. `bytes_written`
is the serialized size of this one page, not total bytes. A hook observing a
saved page does not mean the full backup has been published. Recovery checkpoints
only advance through the durable contiguous prefix; telemetry is not a transaction
commit signal for the whole dataset.

`after_run` reports final successful-run counters and an empty `errors` object
on that success path. It is not a failure/finally callback and is not guaranteed
to run during publication-only recovery.

## Failures, stdout and retries

The subprocess wrapper writes the return value as JSON on stdout. Do not print
other text there; that makes the result invalid JSON. stderr is captured and
included in warnings when a subprocess fails; stderr from a successful hook is
not automatically forwarded as normal run logging.

A script exception, nonzero exit, timeout or invalid JSON output logs a warning
and supplies no override. Hook failure does not by itself abort the backup.
If a transformation must be mandatory for correct extraction, an in-process
`code.postfetch` script can fail the command instead.

Callbacks do not have exactly-once delivery. Resume/replay can invoke them again,
and publication recovery can skip normal collection callbacks. Make external
side effects idempotent and do not use `after_run` as the sole audit of whether
archive publication occurred.

## Extraction scripts for HTML

```yaml
project:
  resp_type: html
code:
  postfetch: /srv/catalog/scripts/pagetodata.py
  follow: /srv/catalog/scripts/listtodata.py
```

Each extraction file exposes `process(content)`. `content` is raw response bytes.
The function returns a JSON-serializable list or wrapper matching the configured
`data.data_key` / `follow_data_key`. For example, a response containing one JSON
object per text line could be converted by:

```python
import json


def process(content):
    return [json.loads(line) for line in content.decode("utf8").splitlines() if line.strip()]
```

Set `data: {}` when returning a root list, or return `{"items":[...]}` and set
`data_key: items`. The parser above is an example for that specific line format;
real HTML needs a parser matching its structure. Unlike observer hooks, extraction
exceptions can fail the command. Extractors run inside the main process without
the hook subprocess's 30-second timeout.

Use absolute extraction script paths when the same project runs from different
working directories: legacy call sites can resolve relative paths differently.
Main JSON/XML backup decoding uses built-in parsers; selecting `code.postfetch`
without the relevant response mode does not make it a universal response filter.

## Debug a script

1. Check the function name and script path before a live run.
2. Exercise `hook(context)` with a small representative dictionary, including
   a page number and any fields your code reads.
3. Verify that the returned value can be serialized as JSON and contains only
   supported override keys.
4. Inspect `apibackuper.log` for subprocess errors or invalid JSON warnings.
5. Test a resumed run if the hook has any durable external side effects.

Examples of all lifecycle script names live in `examples/features/hooks/`.
