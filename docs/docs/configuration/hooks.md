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

## Custom extraction scripts

Some HTML / non-JSON APIs need Python to parse the body (`examples/sozd/`):

```yaml
code:
  postfetch: scripts/pagetodata.py
  follow: scripts/listtodata.py
```
