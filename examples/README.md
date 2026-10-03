# Examples

The `examples/` directory contains ready-to-run YAML configs and Python
hook scripts that demonstrate how to use apibackuper against real APIs.
Every project has an `apibackuper.cfg` or `apibackuper.yaml` and (where
needed) a `scripts/` folder with `prefetch` / `postfetch` / `follow` hooks.

## Layout

| Directory | What |
|---|---|
| `templates/` | **Start here** — minimal YAML configs covering the common patterns: page-based, bearer-auth, skip-offset, follow-multihop |
| `features/` | Focused examples for individual capabilities: hooks, detect, export-filters, sqlite-storage, update-resume, concurrency-retry |
| `sozd/`, `budgetreg/`, `budgetrgz/`, … | Real working projects against Russian government and other APIs. Each is a complete, runnable example. |

## Templates

Drop one of these into a new project directory, edit the URL/keys, and
you're up and running:

* **`templates/page-based.yaml`** — minimal page-number pagination (page=1, page=2, …).
* **`templates/skip-offset.yaml`** — offset/skip pagination for APIs without a count (e.g. Elasticsearch-style).
* **`templates/bearer-auth.yaml`** — page-based with a static `Authorization: Bearer …` header.
* **`templates/follow-multihop.yaml`** — fetch a list endpoint, follow each item to its details page.

## Features

Each subdirectory under `features/` is a complete, single-capability
example. The `README.md` in that directory explains what it demonstrates.

* **`concurrency-retry/`** — parallel fetching (`parallelism > 1`) with the retry budget.
* **`detect/`** — let apibackuper infer the data key, page size, and iteration strategy from the first response.
* **`export-filters/`** — `--fields` projection and `--where` filtering on the export command.
* **`hooks/`** — pre/postfetch and follow scripts via the `[code]` section.
* **`sqlite-storage/`** — use the SQLite storage backend instead of zip for live querying.
* **`update-resume/`** — incremental / update mode with checkpoint resume.

## Real-world projects

The unprefixed directories (`sozd`, `budgetreg`, etc.) are end-to-end
examples for specific APIs. They demonstrate:

- **`sozd/`** — Russian State Duma bills. Uses a custom Python `postfetch` script to parse HTML and extract the bill IDs from a list page. Run with `python -m apibackuper run full -p examples/sozd`.
- **`budgetreg/`**, **`budgetrgz/`**, **`budgettofk/`**, **`budgetsclassif/`** — budget.gov.ru registries; mix of page-based and detect-mode.
- **`etrust/`** — e-trust.gosuslugi.ru certificate authorities; uses Bearer auth.
- **`fpreceivers/`** — spending.gov.ru; large dataset, demonstrates parallel fetching.
- **`hhemployers/`** — hh.ru employer listings; demonstrates skip-offset.
- **`hubofdata/`** — hubofdata.com; demonstrates SQLite storage.
- **`subsidies/`** — government subsidies; demonstrates the follow-link pattern.
- **`esklp/`** — esklp; demonstrates the export filters.

## Running an example

```bash
# (1) Pick an example directory
cd examples/sozd

# (2) Validate the config without making any requests
python -m apibackuper validate-config

# (3) Run a profile to see the resolved configuration
python -m apibackuper run full --profile

# (4) Run the actual backup
python -m apibackuper run full
```

> ⚠️ **Be careful running third-party examples against production APIs.**
> Examples exist to illustrate the configuration grammar, not to certify
> the upstream service's stability. Always start with `--profile` and review
> the URLs and rate-limit settings before fetching live data.

## Writing your own

The simplest starting point is to copy `templates/page-based.yaml`,
edit the `project.url`, set `params.page_size_limit` to the upstream
API's max, and run. See `docs/docs/configuration/` on the documentation
site for the full schema reference.