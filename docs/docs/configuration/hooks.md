---
title: "Hooks"
description: "Python hooks and custom scripts for the backup pipeline"
---
# Hooks

Hook scripts are Python files referenced from the config. Feature example:
`examples/features/hooks/`.

```yaml
hooks:
  before_run: hooks/before_run.py
  before_request: hooks/before_request.py
  after_response: hooks/after_response.py
  after_page: hooks/after_page.py
  after_run: hooks/after_run.py
```

| Hook | When it runs |
|------|----------------|
| `before_run` | Once before the backup starts |
| `before_request` | Before each HTTP request |
| `after_response` | After each HTTP response |
| `after_page` | After a page of records is stored |
| `after_run` | Once after the backup finishes |

Each script defines `hook(context)` or `run(context)` and returns a
JSON-serializable value. Hooks run in a separate Python process with the
user's permissions and a 30-second timeout. `before_run` may return modified
`headers` and `params`; `before_request` may also return a modified `url`.
Other hook results are ignored. Hook failures log a warning and return no override.

Contexts can include live request credentials. Use trusted scripts and avoid
printing secrets. The subprocess isolation option does not sandbox filesystem
or network access.

## Custom extraction scripts

Some HTML / non-JSON APIs need Python to parse the body (`examples/sozd/`):

```yaml
code:
  postfetch: scripts/pagetodata.py
  follow: scripts/listtodata.py
```

Extraction scripts define `process(content)` and run inside the main process.
