# Examples

The `examples/` directory contains a reproducible local tutorial, YAML configs
and Python scripts illustrating public API integrations.
Every project has an `apibackuper.cfg` or `apibackuper.yaml` and (where
needed) a `scripts/` or `hooks/` folder with extraction or lifecycle scripts.

## Layout

| Directory | What |
|---|---|
| `local-demo/` | **Start here** — local API, five fixed records, tested backup/export walkthrough |
| `templates/` | Minimal YAML configs covering page-based, bearer-auth, skip-offset and independent follow rules |
| `features/` | Focused examples for individual capabilities: hooks, detect, export-filters, sqlite-storage, update-resume, concurrency-retry |
| `sozd/`, `budgetreg/`, `budgetrgz/`, … | External API samples; review current endpoint/access requirements before use |

## Templates

Drop one of these into a new project directory, edit the URL/keys, and
you're up and running:

* **`templates/page-based.yaml`** — minimal page-number pagination (page=1, page=2, …).
* **`templates/skip-offset.yaml`** — offset/limit pagination with `results` and `count` response keys.
* **`templates/bearer-auth.yaml`** — page-based with a static `Authorization: Bearer …` header.
* **`templates/follow-multihop.yaml`** — illustrates `follow.rules` syntax. Rules read original backup records independently; automatic multi-hop chaining is not implemented. Adapt the endpoints and keys before use.

## Features

Each subdirectory under `features/` contains a focused configuration. See
`features/README.md` and the linked documentation pages for usage; only `detect/`
has a separate README. These examples use external APIs and may need adaptation.

* **`concurrency-retry/`** — parallel fetching (`parallelism > 1`) with the retry budget.
* **`detect/`** — let apibackuper infer the data key, page size, and iteration strategy from the first response.
* **`export-filters/`** — `--fields` projection and `--where` filtering on the export command.
* **`hooks/`** — five lifecycle scripts via the `hooks` section.
* **`sqlite-storage/`** — use the SQLite storage backend instead of zip for live querying.
* **`update-resume/`** — incremental / update mode with checkpoint resume.

## Real-world projects

The unprefixed directories (`sozd`, `budgetreg`, etc.) are end-to-end
examples for specific APIs. They demonstrate:

- **`sozd/`** — Russian State Duma bills. Uses a custom Python `postfetch` script to parse HTML and extract the bill IDs from a list page. Run with `python -m apibackuper run full -p examples/sozd`.
- **`budgetreg/`**, **`budgetrgz/`**, **`budgettofk/`**, **`budgetsclassif/`** — budget.gov.ru registries; mix of page-based and detect-mode.
- **`etrust/`** — e-trust.gosuslugi.ru certificate authorities; POST JSON body in `params.json`, no auth section in the shipped YAML.
- **`fpreceivers/`** — spending.gov.ru; page-number pagination and ZIP storage.
- **`hhemployers/`** — hh.ru employer listings; page-number pagination with `per_page` and `page`.
- **`hubofdata/`** — hubofdata.ru CKAN search; skip/offset pagination and ZIP storage in legacy INI.
- **`subsidies/`** — spending.gov.ru subsidies; page-number pagination and a change-key field.
- **`esklp/`** — ESKLP registry; page-number pagination with SSL verification disabled in the sample.

## Running an example

```bash
# First start this in a separate terminal from the repository root:
python examples/local-demo/server.py
```

In another terminal in the repository root:

```bash
cp -R examples/local-demo demo
cd demo

# (2) Validate the config without making any requests
python -m apibackuper validate-config

# (3) Run a profile to see the resolved configuration
python -m apibackuper run full --profile

# (4) Run the backup against the local server and export five records
python -m apibackuper run full
python -m apibackuper export items.jsonl
```

> ⚠️ **Be careful running third-party examples against production APIs.**
> Examples exist to illustrate the configuration grammar, not to certify
> the upstream service's stability. Always start with `--profile` and review
> the URLs and rate-limit settings before fetching live data.

## Writing your own

Validate shipped YAML projects, templates, JSON files and Markdown YAML/JSON blocks,
from the repository root:

```bash
python -m scripts.validate_examples
```

The simplest starting point is to copy `templates/page-based.yaml`,
edit the `project.url`, set `params.page_size_limit` to the upstream
API's actual returned page size, and run. See `docs/docs/configuration/` on the documentation
site for the full schema reference.
