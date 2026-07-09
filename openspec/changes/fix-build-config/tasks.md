## 1. License and Dependencies
- [x] 1.1 Fix license classifier in `setup.py` from BSD to MIT
- [x] 1.2 Add `zstandard>=0.22.0` to `setup.py` `install_requires`
- [x] 1.3 Add `zstandard>=0.22.0` to `requirements.txt`
- [x] 1.4 Add `tqdm>=4.66.0` to `setup.py` `install_requires`

## 2. Linting Configuration
- [x] 2.1 Remove `--extend-ignore=E501` from tox.ini flake8 invocation
- [x] 2.2 Remove `--extend-ignore=E501` from ci.yml flake8 invocation
- [x] 2.3 Align `flake8`, `setup.cfg`, and `pyproject.toml` flake8 configs

## 3. CI Pipeline
- [x] 3.1 Remove Python 3.6 and 3.7 from CI test matrix
- [x] 3.2 Remove Python 3.6/3.7 classifiers from pyproject.toml and setup.py
- [x] 3.3 Update `codecov-action` from v4 to v5
- [x] 3.4 Remove `setup.cfg` `universal = 1` setting

## 4. Pre-commit Hooks
- [x] 4.1 Replace `json.tool --check` hook with `python -c "import sys, json; ..."`
- [x] 4.2 Test all hooks pass on clean files

## 5. Dependency Cleanup
- [x] 5.1 Remove `mock` from `requirements-dev.txt` (redundant with stdlib)
- [x] 5.2 Remove `pylint` from `requirements-dev.txt` (no config, unused)
- [x] 5.3 Update pre-commit tool versions (black, isort, bandit)

## 6. Build System Modernization
- [x] 6.1 Remove deprecated `PyTest` command class from `setup.py`
- [x] 6.2 Remove `sys` import and conditional `argparse` dependency

## 7. Verification
- [x] 7.1 Run `pytest` and confirm tests pass
- [x] 7.2 Confirm no new test failures introduced
