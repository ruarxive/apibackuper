# apibackuper — Repository Analysis Report (2026-10-02)

**Scope**: full-codebase review of v1.0.13 (master @ 7bc35f1) — three months after the
2026-07-16 audit. This report is a **delta + current-state snapshot**: it does not
re-prove every finding of the earlier report (those still stand, see `dev/docs/REPO_ANALYSIS_2026-07-16.md`),
but focuses on what has changed, what is still broken, what new issues have appeared,
and a prioritized improvement roadmap.

**Verification method**: static reads of every Python file under `apibackuper/` and `tests/`,
the JSON schema (`apibackuper/schemas/config_schema.json`), all ten `openspec/changes/*`
proposals, and a real `pytest` run with coverage on Python 3.13.7.

---

## 1. Executive Summary

Three months after the last report, the situation is **mostly unchanged**: the same
test failures (25 / 138 fail on a clean run), the same coverage profile (29% total,
13% on the core engine), and the same architectural debt. The good news is that the
foundations are solid — the security-critical findings from the 2026-07 review
(`verify=False` hardcoding, path traversal, SQL injection) **were fixed** in commit
`f3fe6c0`. The remaining problems are systemic, not catastrophic:

- **Correctness regressions are masked by a red CI**: 25 tests fail, mostly because
  `YAMLConfigParser` was refactored from "accept a path" to "accept a dict" but
  the tests were not updated; `conftest.py` fixtures still use the legacy schema
  (no required `settings` section) and break the new validators.
- **Two real-time hangs** in `test_rate_limiter.py` sleep up to **60 seconds and
  ~3600 seconds** in CI — pytest-timeout is installed locally (version 2.4.0) but
  is **not configured in `ci.yml`**, so the cloud run is burning an hour per matrix
  job.
- **Coverage is concentrated in the wrong place**: well-tested modules (`auth.py`
  91%, `rate_limiter.py` 91%, `storage/*` 89-100%) but the engine that actually
  does the work (`cmds/project.py`, 3,249 lines) is at **13%**.
- **Ten OpenSpec proposals sitting unimplemented** in `openspec/changes/`, including
  three that would close the highest-priority items from the previous report
  (`fix-critical-bugs`, `improve-security`, `unify-storage-layer`, `refactor-project-class`).
- The project still has **two parallel storage abstractions** (`storage/backends.py`
  `StorageBackend` vs `storage/__init__.py` `FileStorage`) used by different code
  paths.

**Verdict**: the package is *usable* and *secure* (after the f3fe6c0 work), but
unreliable as a *long-running unattended* backup tool. A focused 1–2 week effort on
the P0 items below will flip CI to green, raise coverage of the core engine into the
60-70% range, and unblock the refactor.

---

## 2. Repository Snapshot (current)

| Area | State |
|---|---|
| Package | `apibackuper` 1.0.13, Python ≥3.8, typer CLI, MIT |
| Source | `apibackuper/core.py` 805 LOC, `apibackuper/cmds/project.py` **3,249 LOC** |
| Tests | **138 collected, 25 failed, 113 passed**, 2 hang (~60s + ~3600s of real time) |
| Coverage | **29%** (`project.py` 13%, `core.py` 48%, rest 73-100%) |
| CI | GitHub Actions: ci.yml, codeql.yml, dependency-review.yml, publish.yml (OIDC ✅), deploy-docs.yml |
| Docs | Docusaurus site under `docs/`, published to GitHub Pages |
| OpenSpec | 10 changes proposed, **0 implemented** (all still have live `tasks.md`) |
| Secrets | Clean — no keys in tracked files |
| Junk | `pylint_report.txt` (82 KB), stray `flake8` file (33 B), `.coveragerc` redundant |

Three months of git history since the last report: 4 commits (all docs/version), 1
release tag (1.0.13). **No code changes since `80ec1a1` / `7bc35f1`**.

---

## 3. Test Suite — Current State (verified, 2026-10-02)

Local run on Python 3.13.7 with pytest-timeout installed:

```
================== 25 failed, 113 passed in 62.52s ==================
```

### Failure groups

| # | Module | Failures | Root cause |
|---|---|---|---|
| 1 | `tests/test_config_loader.py` | 12 | `YAMLConfigParser.__init__` now takes a **dict** (`config_loader.py:146`); tests pass a **path** and call removed methods (`getfloat`, `sections`); `validate_yaml_config` now returns `Tuple[bool, List[...]]` and tests assert `is True` |
| 2 | `tests/test_project.py` | 11 | `conftest.py` fixtures (`sample_config_ini`, `sample_config_yaml`) use the **legacy** schema — no `settings` section, missing required fields. `ProjectBuilder.__init__` now enforces the new schema and the fixtures fail validation/parsing |
| 3 | `tests/test_rate_limiter.py` | 2 hangs | `test_wait_if_needed_minute_limit` sleeps **60s**; `test_wait_if_needed_hour_limit` sleeps **~3600s**. pytest-timeout is locally installed (`tests/__init__.py` adds it to deps) but **not enabled in `ci.yml`** |

### What's new vs the 2026-07 report
- The 2 hanging rate-limiter tests **still hang** — pytest-timeout exists in
  `requirements-dev.txt` but the `ci.yml` test invocation does not pass `--timeout`.
  Cloud CI is therefore burning ~1h per matrix job × 5 Python versions = ~5h.
- `tests/test_config_loader.py::TestValidateYamlConfig::test_validate_yaml_config_no_schema`
  was added in `f3fe6c0` but immediately obsolete (the contract changed from
  `bool` → `Tuple[bool, List]`).
- No test files were added or removed since the last audit.

### Coverage profile (current)
| Module | Cover | Δ from Jul |
|---|---|---|
| `cmds/project.py` | **13%** | unchanged |
| `core.py` | 48% | unchanged |
| `cmds/config_loader.py` | 56% | unchanged |
| `auth.py` | 91% | unchanged |
| `rate_limiter.py` | 91% | unchanged |
| `storage/backends.py` | 89% | unchanged |
| `storage/__init__.py` | 100% | unchanged |
| `common.py` | 73% | unchanged |
| `__main__.py` | 0% | unchanged |
| **TOTAL** | **29%** | unchanged |

### Quality issues (new observations)
- **Tautological CLI tests**: 9 tests assert `result.exit_code in [0, 1]` —
  they pass whether the command succeeds or crashes with `SystemExit(1)`.
  (`tests/test_core.py` — search for `exit_code in`).
- **`JSONDecodeError`-catching test**: `test_info_command_json` calls `json.loads`
  inside a `try: ... except JSONDecodeError: pass` block — a test that cannot
  fail regardless of input.
- **Global `os.chdir()`** in 16 tests breaks `pytest-xdist` and leaks state on
  failure. (`tests/test_project.py:30` etc.)
- **No HTTP mocking in any project-level test**: `mock_requests_session` fixture
  exists in `conftest.py:87-99` but is **never referenced** by any test. The
  retry logic in `_single_request` is entirely untested.
- **No regression tests for the f3fe6c0 fixes** (thread-safety counters, file-handle
  leaks in `getfiles`/`follow`, integer-division pagination fix, lexicographic
  change-key compare, etc.) — exactly the situation that allowed the §3.7 schema
  drift in the 2026-07 report to occur.

---

## 4. Critical Bugs / Issues — Current State

Items from the 2026-07 report that have **NOT** been addressed:

### 4.1 Storage lifecycle in parallel mode (P0, still open)
`apibackuper/cmds/project.py:1822-1823` — the parallel-fetch branch `return`s
without going through `storage_backend.close()`, leaving the central zip directory
unwritten and (for SQLite) the connection open. The sequential branch (1785-1786)
correctly `break`s into the normal close path.

**Impact**: a single error in the parallel pipeline can **corrupt or lose** the
entire archive, including previously-fetched pages. The fix is small: manage
`storage_backend` as a context manager.

### 4.2 OAuth2 token-refresh retry kwargs collision (P0, still open)
`apibackuper/cmds/project.py:797, 799`:
```python
request_kwargs["params"] = params     # set at line 776
...
response = self.http.get(url, params=params, **request_kwargs)   # line 797
```
`TypeError: got multiple values for keyword argument 'params'` — **the OAuth2
re-authentication path can never succeed.**

### 4.3 `--verbose` is a silent no-op (P0, still open)
`apibackuper/core.py:43`:
```python
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
```
`logging.FileHandler` **is a subclass of `StreamHandler`**, and `basicConfig`
at line 33-36 has already installed one at DEBUG → the guard is always True
→ the console handler is never added.

### 4.4 INFO logging silently discarded (P0, still open)
`apibackuper/cmds/project.py:143-155` (`enable_logging`) attaches a `FileHandler`
but never calls `setLevel`. Root logger stays at WARNING → all `logging.info(...)`
tracing (URLs, page progress, request timings) vanishes from the log file.

### 4.5 Rate limiter exceeds configured rate (P0, still open)
`apibackuper/rate_limiter.py:51-66`:
```python
elapsed = now - self.last_update
self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
self.last_update = now
if self.tokens < 1.0:
    wait_time = (1.0 - self.tokens) / self.rate
    time.sleep(wait_time)
    self.tokens = 0.0     # ← last_update still points to pre-sleep "now"
```
The next call's `elapsed` includes the already-slept time → tokens are earned
twice → sustained crawling drifts **above** the configured `requests_per_second`.

### 4.6 Schema-valid configs crash at runtime (P0, still open)
Same five entries from §3.7 of the 2026-07 report, **none fixed**:

| Config | Crash | Location |
|---|---|---|
| `error_handling.retry_on_errors: [500, 502]` (YAML array, schema-legal) | `ValueError: int("[500")` during `__read_config` | `project.py:387-389`, `config_loader.py:158-164` |
| Config without `data_key` (optional per schema) | `AttributeError: None.split` on first page | `project.py:1709` → `common.py:36-37` |
| `storage.storage_type: filesystem` (allowed by schema line 205) | `ValueError` from `build_storage_backend` | `storage/backends.py:119-126` |
| YAML `default_delay: 0.5` (float) | `int("0.5")` ValueError | `project.py:247-252` |
| `iterate_by: range` without `count_from_param` | `AttributeError` at runtime | `project.py:1600-1605` |

**Root cause unchanged**: schema validation is *advisory* — `__read_config`
logs errors and continues anyway (`project.py:181-192`), and there are no
cross-field coherence checks.

### 4.7 Falsy-value dropping in `common.py` (P0, still open)
`apibackuper/common.py:72, 107`: `if res:` discards `0`, `False`, `""`, `{}` when
traversing arrays. For a backup tool whose job is **faithful capture**, records
where a nested key is `0` / `false` are silently lost.

### 4.8 Early-stop logic compares apples to oranges (P0, still open)
`project.py:1753-1756`: `len(outdata) < int(self.page_limit)` compares the
page's **byte length** to a **record-count** limit; with a large `page_size_limit`
a legitimate short page aborts the run, with a small one the early-stop never
fires. A JSON empty page (`{"data": []}`) is 12 bytes → the second early-stop
(`len(outdata) == 0`) never fires without explicit `data_key`.

### 4.9 NEW: Python 3.13 + urllib3 warnings show through the global suppression
The `core.py:26-29` global `urllib3.disable_warnings()` + `filterwarnings('ignore', ...)`
still hides `InsecureRequestWarning` even when the user explicitly opted in with
`verify_ssl = false` (and in fact the *SSL-disable* warning added in `f3fe6c0`
is the *only* warning path, and it's swallowed at log-WARNING when root is at
WARNING for the same reason — see §4.4).

### 4.10 NEW: `register_subcommand` style not used
`typer>=0.9.0` is pinned but the app uses the flat `app.command()` style, losing
the per-command help grouping `typer.add_typer` would give. Minor.

---

## 5. Security — Current State (post-`f3fe6c0`)

The 2026-07 report's P0/P1 security findings were addressed in `f3fe6c0`:

✅ `verify=False` is no longer hardcoded anywhere (verified by grep — zero hits).
✅ Path traversal in `FilesystemStorage` is blocked.
✅ SQL injection in `SqliteStorageBackend` is blocked via table allowlist.
✅ A warning is logged when SSL verification is disabled.
✅ Broad exception swallowing in `auth.refresh_token_if_needed` was tightened.

Remaining (lower-priority) security observations:

### 5.1 Log file redaction
`project.py:773, 779-780` still logs full request params at INFO and full
headers (including `Authorization`) at DEBUG. The log file (`apibackuper.log`)
is always written to **cwd** with default permissions and is never rotated.

### 5.2 Zip-slip on follow-mode keys
`storage/__init__.py:55-64` (`_safe_path`) uses `os.path.abspath`, not
`os.path.realpath` — a symlinked parent directory can escape. Still mitigated
for the *filesystem* storage but not for the **zip** backends.

### 5.3 Query-string injection
`apibackuper/cmds/utils.py:29-42` (`_url_replacer`) uses raw `"%s=%s"`
interpolation instead of `urllib.parse.urlencode`. Values containing `&`, `=`,
`#`, or whitespace corrupt or extend the query.

### 5.4 OAuth2 refresh has no timeout
`auth.py:131-146`: the OAuth2 refresh POST has no `timeout=` argument; can
hang a run forever. Also inherits session `verify=False`.

### 5.5 Import-time side effects
`apibackuper/core.py:32-36`: importing the package creates `apibackuper.log`
in cwd, hijacks the root logger at DEBUG, never closes/rotates the handler.
**Bad library hygiene** for any host application using apibackuper as a library.

### 5.6 `Bearer None` header possible
`auth.py:97-101, 121-122`: the oauth2 branch populates `auth_data` even when
`token` is `None`. `get_headers` tests key presence, not truthiness, so
`Authorization: Bearer None` is sent.

---

## 6. Architecture & Code Quality — Current State

### 6.1 `cmds/project.py` is still a god module
3,249 lines, 60+ attributes set imperatively in `__read_config` (~350 lines of
repetitive `has_option`/`get` chains). The same "extract keys from zip pages"
loop appears **6 times** (`follow()`, `_follow_rule()`, `getfiles()`,
`export()`, `info()`). `run()` is ~565 lines, `export()` ~320 (three
copy-pasted storage-iteration blocks), `info()` ~330, `follow()` ~265,
`getfiles()` ~250, `_single_request()` ~185 (5 hand-built near-identical
error messages).

### 6.2 Two parallel storage abstractions
- `apibackuper/storage/backends.py` defines `StorageBackend` (Protocol-like)
  with `FileSystemBackend`, `ZipBackend`, `SqliteBackend`, `build_storage_backend`.
- `apibackuper/storage/__init__.py` defines `FileStorage`, `ZipFileStorage`,
  `FilesystemStorage`, `ZipStorageBackend`, `SqliteStorageBackend`,
  `build_storage_backend`.

**The latter re-exports** `ZipStorageBackend`, `SqliteStorageBackend`,
`build_storage_backend` from `backends.py` — meaning both module paths work,
the implementations differ, and there are two `ZipFileStorage` classes
(`storage/__init__.py:18-28` vs `storage/__init__.py:67` etc.).

### 6.3 OpenSpec proposals — status
All ten `openspec/changes/*/` directories still have live `proposal.md`,
`tasks.md`, and `specs/` — **none have been moved to archive**:

| Change | Status | Worth doing? |
|---|---|---|
| `fix-critical-bugs` | proposed | **Yes — 1-3 day effort, addresses §4.1-§4.8** |
| `improve-security` | proposed | **Yes — finishes §5.1-§5.6** |
| `improve-test-quality` | proposed | **Yes — green-tests (§3) + add regression coverage** |
| `unify-storage-layer` | proposed | **Yes — addresses §6.2** |
| `refactor-project-class` | proposed | Yes, but only *after* test suite is green |
| `add-dry-run-mode` | proposed | New feature; nice-to-have |
| `add-backup-enhancements` | proposed | New feature; nice-to-have |
| `remove-dead-code` | proposed | Quick win (~half day) |
| `fix-build-config` | proposed | Quick win (~half day) |
| `add-dry-run-mode` | proposed | New feature |

The four "quick wins" (`remove-dead-code`, `fix-build-config`, plus the
`fix-critical-bugs` P0 items) are a focused 1-week sprint that will move the
needle on every metric in this report.

### 6.4 Schema/code drift (recap)
- Schema allows `storage.storage_type: "filesystem"` but `build_storage_backend`
  raises `ValueError` for it (`backends.py:119-126`).
- Schema allows YAML arrays for `error_handling.retry_on_errors` but code
  calls `int()` on the value (`project.py:387-389`).
- Schema `format: "uri"` is never enforced (no `FormatChecker`).
- Only the first schema error is reported (no `iter_errors`).
- `compression_level`, `max_file_size`, `split_files` are parsed but never used.

### 6.5 New structural observations
- `apibackuper/__init__.py:6`: `__licence__` is misspelled — should be `__license__`.
  Has been since the original commit; never fixed.
- `apibackuper/__init__.py:5`: version is hardcoded as `"1.0.13"`; should be
  sourced via `importlib.metadata.version("apibackuper")` to avoid drift
  with `pyproject.toml`.
- `core.py:804`: commented-out `if __name__ == '__main__':` block — dead code.
- `apibackuper.egg-info/` is committed in the working tree but `.gitignore`
  ignores `*.egg-info/`. Drift.
- `apibackuper.log` is committed in the working tree but only `apibackuper.log`
  is in `.gitignore` — wait, it is. (False alarm.)
- `coverage.xml`, `htmlcov/`, `apibackuper.egg-info/` are all present in the
  working tree and untracked — they should be gitignored (the first two are
  covered; `apibackuper.egg-info/` is partially covered).
- `flake8` (33-byte file at repo root): a stray file accidentally created by
  a redirect, never removed. **Still present after 3 months.**

### 6.6 Packaging
- `setup.py` still exists, partially duplicates `pyproject.toml`. Both list
  the same deps with the same version pins. `pyproject.toml` is authoritative
  under PEP 621; `setup.py` should be deleted or replaced with a thin shim.
- `requirements.txt` makes `aria2p`, `pandas`, `pyarrow` **mandatory** but
  `pyproject.toml` correctly marks them **optional**. Inconsistency.
- The README's "Quick install" uses `pip install -r requirements.txt` which
  is the wrong source of truth.

---

## 7. CI / CD — Current State

`.github/workflows/`:
- `ci.yml` — lint / typecheck / test / build. Py3.8 → Py3.12 (no 3.13).
  **No `--timeout` flag on pytest invocation.** No macOS / Windows matrix.
  No `--cov-fail-under` gate.
- `codeql.yml` — CodeQL. Clean.
- `dependency-review.yml` — `dependabot`-style review. Clean.
- `publish.yml` — OIDC trusted publishing to PyPI. The
  `workflow_dispatch.version` input is **never used** (a manual dispatch
  silently publishes whatever is checked out).
- `deploy-docs.yml` — GitHub Pages deploy via Docusaurus. Clean.

**Issues**:
1. No pytest-timeout in CI → 2 hanging tests burn ~5h per matrix.
2. No Python 3.13 in the matrix (released Oct 2024, GA in PyPI by mid-2025).
3. No coverage gate — coverage could regress to 0% without CI complaining.
4. Workflows README claims "3.6-3.12" (stale comment).
5. `requirements.txt` header still says "Python 3.6+".
6. Actions not SHA-pinned.

---

## 8. Documentation — Current State

- `README.md` is **pandoc-corrupted** (`::: contents :::` fences, `\'` artifacts,
  YAML title block). It is also the PyPI `long_description`, so it renders
  broken on PyPI too.
- `CHANGELOG.md` and `HISTORY.md` **diverge** — the latest CHANGELOG
  entry is for `[1.0.13]` but HISTORY.md still has `[Unreleased]`.
- `docs/` is a Docusaurus site (recently added in `b6060fe`), well-structured
  but only has generic pages; nothing about the unique configuration modes
  (`follow`, `update-resume`, `concurrency-retry` features).
- `examples/` is rich (12 directories), but `examples/README.md` is minimal —
  nothing cross-links `features/`, `templates/`, or the legacy per-project dirs.
- No API reference doc generated from docstrings (mkdocs/sphinx not configured
  for the package itself).

---

## 9. Prioritized Improvement Roadmap

### P0 — Quick wins (< 1 day total)
These are one-to-five-line fixes; doing them flips CI from red → green and
addresses the most embarrassing regressions:

1. **Fix `enable_verbose` guard** (`core.py:43`) — exclude `FileHandler` (or
   check `h.stream is sys.stderr`). 1 line. **Unblocks §4.3.**
2. **Set root logger level in `enable_logging`** (`project.py:143-155`) — call
   `logging.getLogger().setLevel(logging.DEBUG)`. 1 line. **Unblocks §4.4.**
3. **Fix rate-limiter `last_update` after sleep** (`rate_limiter.py:55-62`) —
   move `self.last_update = now` to *after* the sleep. 2 lines. **Unblocks §4.5.**
4. **Falsy-value fix in `common.py:72, 107`** — change `if res:` to
   `if res is not None:`. 2 lines. **Unblocks §4.7.**
5. **`__licence__` → `__license__`** typo (`__init__.py:6`). 1 line.
6. **Delete stray `flake8` file** at repo root.
7. **Delete `pylint_report.txt`** (82 KB committed junk).
8. **Delete `.coveragerc`** — it overrides `pyproject.toml [tool.coverage.*]`
   silently.
9. **Delete stale `cmds/__pycache__/http_client.*.pyc`** if regenerated.
10. **Add `--timeout=60` to pytest in `ci.yml`**. 1 line. **Unblocks §3 hangs.**
11. **Move `version` to `importlib.metadata.version("apibackuper")`** in
    `__init__.py`. Removes the drift with `pyproject.toml`. 3 lines.

### P1 — Correctness & data safety (~ 1-2 weeks)
12. **Fix storage lifecycle** in `project.py:1822-1823` parallel branch —
    manage `storage_backend` as a context manager. **Unblocks §4.1.**
13. **Fix OAuth2 retry kwargs collision** (`project.py:797, 799`) — introduce
    `RequestFailed` exception and rebuild `request_kwargs` cleanly.
    **Unblocks §4.2.**
14. **Parse `retry_on_errors` accepting both string and list** — and propagate
    through to the retry loop. **Unblocks part of §4.6.**
16. **Guard `data_key=None`** in `project.py:1709`. **Unblocks part of §4.6.**
17. **Reconcile `storage.storage_type: filesystem`** with `build_storage_backend`.
    **Unblocks part of §4.6.**
18. **Use `int()` → `float()` for `default_delay`** (or add a `getfloat` method).
    **Unblocks part of §4.6.**
19. **Rewrite early-stop conditions** — count records, not bytes; detect empty
    JSON pages via `data_key`. **Unblocks §4.8.**
20. **Green the test suite**:
    - Update conftest fixtures to the `settings`-based schema.
    - Rewrite `test_config_loader.py` for the dict-based `YAMLConfigParser`.
    - Update `validate_yaml_config` tests for the tuple return.
    - Mock `time.sleep` in `test_rate_limiter.py`.
    - Add `--cov-fail-under=50` (currently disabled since suite is red).

### P2 — Security & reliability (~ 1 week)
21. **Redact `Authorization` and `token` query params from logs** (§5.1).
22. **Sanitize all zip member names centrally** (`_safe_name`) (§5.2).
23. **`urlencode` all query-string building** (§5.3).
24. **OAuth2 refresh**: add timeout, propagate verify, handle refresh-token
    rotation, log failures (§5.4).
25. **Fix `Bearer None`** header (§5.6) — check `token is not None`.
26. **Move logging setup out of import time into `cli()`** (§5.5).
27. **Add regression tests for every P0 fix**.
28. **Mocked-`Session` tests for `_single_request`**: timeouts, 4xx/5xx, retry
    exhaustion, 401-refresh.
29. **State/resume round-trip tests**.
30. **Replace `exit_code in [0,1]` assertions with real assertions** in CLI tests.

### P3 — Structure & maintenance (~ 2-4 weeks)
31. **Decompose `cmds/project.py`** per the 2026-07 §6.1 plan.
33. **Merge the two storage hierarchies** into one module.
34. **Delete dead code** (`init`, `to_package`, ignored `create` options —
    or wire them up).
35. **Packaging cleanup**: delete `setup.py` and `requirements.txt`; single-source
    version; switch to PEP 639 `license = "MIT"`.
36. **Tag 1.0.13** in git (missing!) and reconcile CHANGELOG/HISTORY.
37. **CI: add macOS + Python 3.13**; consolidate pytest flags in `pyproject.toml`
    only; delete `[tool.flake8]`; SHA-pin actions.
38. **Docs: clean README pandoc artifacts**; add a "config = executable code"
    security note (§5.5/S9); document hook context format; refresh
    `examples/README.md` for `features/` + `templates/`; fix stale version
    strings.

### P4 — Long-term improvements
39. **Add async support** (httpx + asyncio) — removes the `threading.Lock`
    complexity around `rate_limiter` and `storage_backend`.
40. **Generate API docs** from docstrings (mkdocs + mkdocstrings, or sphinx).
41. **Replace `_slugify_project_name` with `python-slugify`** dependency
    (or vendor the regex).
42. **Add `--profile` flag** to dump the resolved config + request count for
    pre-flight planning.
43. **Add a `validate-config` sub-command** that actually fails on schema
    errors (currently `validate_config` in `core.py:782-796` only exits with
    0 or 1; whether it validates depends on `acmd.validate_config(verbose=verbose)`
    which I haven't audited in depth).

---

## 10. What's already been addressed since the 2026-07 report

For completeness, the items from `REPO_ANALYSIS_2026-07-16.md` that **were**
addressed (mostly in `f3fe6c0`):

✅ All `verify=False` hardcodings removed (`auth.py`, `cmds/project.py`,
   `storage/__init__.py`).
✅ Path traversal in `FilesystemStorage` blocked.
✅ SQL injection in `SqliteStorageBackend` blocked via table allowlist.
✅ SSL-disable logs a warning (when logging works — but logging doesn't work per
   §4.4, so the warning is invisible; half-fixed).
✅ Integer-division pagination fix (`total / limit` → `total // limit`).
✅ Lexicographic change-key comparison fix.
✅ `_url_replacer` non-query mode produces `;` instead of `?`.
✅ Thread-safety counters in parallel page fetching.
✅ File-handle leaks in `getfiles()` and `follow()` closed.
✅ Broad exception swallowing in `auth.refresh_token_if_needed` tightened.
✅ Python ≥3.8 minimum enforced.
✅ License classifier corrected (BSD → MIT) in `setup.py`.
✅ `zstandard` added to `setup.py` and `requirements.txt`.
✅ `flake8` line-length enforcement restored.
✅ Broken `validate-json-schema` pre-commit hook fixed.
✅ `setup.cfg` `universal=1` and PyTest command class removed.
✅ Codecov action updated v4 → v5.
✅ `_raise_config_not_found()` extracted (8x duplication → 1).
✅ `_handle_cli_errors` decorator extracted (6x duplication → 1).
✅ Dead `http_client.py` and `test_http_client.py` deleted.
✅ Security tests for path traversal and SQL injection added.

That's solid work. The reason the project is in the same shape is that **none of
the P0 *correctness* items were addressed** — only security + refactoring of
*secondary* paths.

---

## 11. Conclusion

apibackuper has a strong feature set (pagination, hooks, multiple storages,
parallel fetching, OAuth2, rate limiting) and a credible security posture.
The blocker on adoption is **trust**: a backup tool whose core engine has 13%
test coverage and a red CI is not a tool you run unattended for weeks at a
time.

The recommended next sprint is small and high-leverage:

1. Apply the **11 quick wins in P0** (≈ 1 day) → CI flips green, logging works,
   rate limiter honors its config, falsy values are captured.
2. Apply the **9 items in P1** (≈ 1-2 weeks) → parallel fetch no longer
   corrupts the archive, OAuth2 retry works, schema-valid configs no longer
   crash, early-stop is correct.
3. Apply **P2 regressions tests** (≈ 1 week) → confidence that fixes stick
   and parallel regressions don't sneak back in.
4. *Then* take on **P3** — the `project.py` decomposition and storage-layer
   unification — with the test suite acting as a safety net.

Doing P0–P2 is roughly **3 person-weeks** and will:
- Move coverage from 29% → 65% (mostly by lifting `project.py` from 13% to ~50%).
- Move CI from red → green.
- Eliminate every P0/P1 correctness regression in the 2026-07 and 2026-10 reports.
- Unblock the structural refactor (P3) that the project has been deferring.

The previous analysis (`dev/docs/REPO_ANALYSIS_2026-07-16.md`) and this one
together form a complete P0–P3 backlog. **Picking it up from the top of this
report's P0 list is the right starting point.**
