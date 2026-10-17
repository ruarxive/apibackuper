---
title: "Contributing"
description: "Development setup, code style, tests, and documentation"
---
# Contributing

Contributions are welcome. This page covers local setup, style, tests, and
docs.

## Development setup

### Prerequisites

- Python 3.10 or higher
- Git
- pip

### Installation

```bash
git clone https://github.com/datacoon/apibackuper.git
cd apibackuper
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## Code style

- **black** — version 25.1.0, line length 100
- **isort** — Black profile, line length 100
- **flake8** — shared `.flake8` configuration
- **mypy** — `mypy apibackuper`
- **bandit** — `bandit -r apibackuper -ll`

```bash
black apibackuper
isort --profile=black apibackuper
flake8 apibackuper
```

## Tests

```bash
pytest
pytest --cov=apibackuper --cov-report=html
tox                 # multiple Python versions
python -m scripts.validate_examples
```

See `tests/README.md` for markers, fixtures, and file layout.

The suite enforces at least 70% overall coverage. Backup lifecycle regressions
cover interruption, resume, update generations and export on ZIP, SQLite and
filesystem storage. Example validation checks configuration syntax and schema
without contacting external APIs.

## Documentation

The site is Docusaurus in `docs/`:

```bash
make docs-serve     # or: cd docs && npm start
make docs           # production build
```

Edit markdown in `docs/docs/`. Keep frontmatter (`title`, `description`).
`npm run build` fails on broken links (`onBrokenLinks: 'throw'`).

## Pull requests

- Follow existing CLI and YAML conventions
- Add or update tests for behavior changes
- Update the docs site when commands or config fields change
- Add a [CHANGELOG.md](https://github.com/datacoon/apibackuper/blob/master/CHANGELOG.md) note under Unreleased
