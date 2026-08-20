---
title: "Contributing"
description: "Development setup, code style, tests, and documentation"
---
# Contributing

Contributions are welcome. This page covers local setup, style, tests, and
docs.

## Development setup

### Prerequisites

- Python 3.8 or higher
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

- **black** — line length 100
- **isort** — Black profile, line length 100
- **flake8** — max line length 100, ignore E203
- **mypy** — `mypy apibackuper --ignore-missing-imports --no-strict-optional`
- **bandit** — `bandit -r apibackuper -ll`

```bash
black --line-length=100 apibackuper
isort --profile=black --line-length=100 apibackuper
flake8 apibackuper --max-line-length=100 --extend-ignore=E203
```

## Tests

```bash
pytest
pytest --cov=apibackuper --cov-report=html
tox                 # multiple Python versions
```

See `tests/README.md` for markers, fixtures, and file layout.

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
