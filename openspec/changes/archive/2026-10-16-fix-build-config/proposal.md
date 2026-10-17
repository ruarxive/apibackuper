# Change: Fix build, dependency, and CI configuration

## Why
Multiple configuration files contradict each other: the wrong license is
declared in `setup.py`, required dependencies are missing from the build
artifacts, flake8 is configured to ignore the very line-length rule it
enforces, and the pre-commit hook uses an invalid `json.tool --check` flag.
These inconsistencies cause the pip-installed package to be missing features,
CI to give false confidence, and commits to fail on JSON files.

## What Changes
- Fix license classifier in `setup.py` from BSD to MIT
- Add `zstandard` and `tqdm` to `setup.py` `install_requires`
- Remove `--extend-ignore=E501` from flake8 invocations in tox/CI
- Fix or replace the broken `validate-json-schema` pre-commit hook
- Remove EOL Python 3.6/3.7 from CI matrix and classifiers
- Remove `setup.cfg` `universal = 1` (project is Python 3-only)
- Remove redundant `mock` dependency from dev requirements
- Remove `pylint` from dev requirements (no config, unused in CI)
- Update `codecov-action` from v4 to v5
- Remove `setup.py` in favor of `pyproject.toml`-only build (or reduce to shim)

## Impact
- Affected specs: build-system
- Affected code: `setup.py`, `setup.cfg`, `pyproject.toml`, `tox.ini`,
  `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `requirements.txt`,
  `requirements-dev.txt`
