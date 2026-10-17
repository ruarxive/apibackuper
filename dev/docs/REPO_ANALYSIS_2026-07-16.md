# apibackuper — Repository Analysis Report (2026-07-16)

**Scope**: full-codebase review of v1.0.13 (master @ 80ec1a1): core modules, CLI (`cmds/`), storage backends, tests, packaging, CI/CD, docs, repo hygiene. All findings verified against source; the three most severe were double-checked by hand.

---

## 1. Executive Summary

apibackuper is a useful, feature-rich CLI tool with a real user base, good security tooling on CI (CodeQL, dependency-review, bandit, OIDC trusted publishing), and no committed secrets. However, the codebase currently has **systemic correctness problems**:

- **The test suite is red**: 25 failed / 113 passed locally, and 2 tests hang for ~60s and ~3600s of real time — meaning CI is broken or burning >1h per job.
- **Total coverage is 29%**; the largest and most important module (`cmds/project.py`, 3,249 lines) has **13% coverage**.
- Several **schema-valid configurations crash at runtime**; retry logic is partially broken; the parallel fetch path can **corrupt the entire zip archive** on early stop; `--verbose` is silently a no-op.
- The project has outgrown its structure: one 3,249-line god-module, two parallel storage abstractions, three sources of dependency truth, and schema/code drift.

**Verdict**: functionally valuable, but needs a focused "correctness first" pass (fix P0 bugs, green the suite), then a structural refactor of `cmds/project.py`, then packaging/docs cleanup.

---

## 2. Repository Snapshot

| Area | State |
|---|---|
| Package | `apibackuper` 1.0.13, Python ≥3.8, typer CLI, MIT |
| Size | ~4,200 LOC of package code; `core.py` 805, `cmds/project.py` 3,249 |
| Tests | 138 collected: **25 failed, 113 passed**, 2 hang; coverage **29%** total |
| CI | GitHub Actions: ci.yml, codeql.yml, dependency-review.yml, publish.yml (OIDC ✅) |
| Docs | README (pandoc-corrupted), CHANGELOG + HISTORY (diverged), no API docs |
| Secrets scan | ✅ clean — no keys/tokens in tracked files |
| Committed junk | `pylint_report.txt` (82 KB), stray file literally named `flake8` |

---

## 3. Critical Bugs (P0 — fix first)

### 3.1 Parallel-mode early stop corrupts the zip archive — `cmds/project.py:1822-1823` ✅ verified
```python
consecutive_errors = 0
if not handle_success(page, result["content"]):
    return                      # ← storage_backend.close() never runs
```
The sequential branch (1785-1786) `break`s into the normal close path (1855-1861); the parallel branch `return`s directly. Zip central directory is never written → **the whole archive (including previously fetched pages) can be lost**; sqlite connection leaks too. Same class of bug: exceptions not in `except (ValueError, RuntimeError, IOError)` at 1862 (e.g. `xmltodict`'s `ExpatError` at 1687, anything from a postfetch script at 1693) crash the run with the backend open. **Fix**: manage the backend with a context manager / `try/finally`.

### 3.2 OAuth2 token-refresh retry always crashes — `cmds/project.py:797, 799` ✅ verified
`request_kwargs["params"]` (or `["json"]`) is set at line 776/783, then the retry calls `self.http.get(url, params=params, **request_kwargs)` → `TypeError: got multiple values for keyword argument 'params'`. **The OAuth2 re-auth path can never succeed.**

### 3.3 Retry loop broken by exception-type mismatch — `cmds/project.py:816-915` vs `1659-1662`
`_single_request` converts every network failure into `RuntimeError`, but `fetch_page`'s retry loop catches only `requests.exceptions.RequestException` → a transient timeout during retry **aborts the entire run** instead of retrying. The `except requests.exceptions.RequestException` at 1431/1647 is largely dead code. **Fix**: raise a dedicated `RequestFailed` exception and catch it precisely.

### 3.4 `--verbose` is silently broken — `core.py:43` ✅ verified
```python
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
```
`logging.FileHandler` **is a subclass of `StreamHandler`**, and `basicConfig` already installed one at import → the guard is always True → the console handler is never added. Every `-v/--verbose` flag on every command does nothing.

### 3.5 INFO logging silently discarded — `cmds/project.py:143-155`
`enable_logging` attaches a `FileHandler` but never calls `setLevel`; unless the config has a `[logging]` section, the root logger stays at WARNING and all `logging.info(...)` tracing (URLs, page progress) vanishes.

### 3.6 Rate limiter exceeds the configured rate — `rate_limiter.py:51-66` ✅ verified
After sleeping, `self.tokens = 0.0` but `self.last_update` was set to the *pre-sleep* timestamp (line 55). The next call's `elapsed` includes the already-slept time → tokens are earned twice → sustained crawling drifts **above** `requests_per_second`. Fix: update `last_update` after the sleep.

### 3.7 Schema-valid configs crash at runtime
| Config | Crash | Location |
|---|---|---|
| `error_handling.retry_on_errors: [500, 502]` (YAML array, schema-legal) | `ValueError: int("[500")` during `__read_config` — CLI dead before any command | `project.py:387-389`, `config_loader.py:158-164` |
| Config without `data_key` (optional per schema) | `AttributeError: None.split` on first page | `project.py:1709` → `common.py:36-37` |
| `storage.storage_type: filesystem` (allowed by schema line 205) | `ValueError` from `build_storage_backend` | `storage/backends.py:119-126` |
| YAML `default_delay: 0.5` | `int("0.5")` ValueError (schema says integer; built-in default is 0.5) | `project.py:247-252` |
| `iterate_by: range` without `count_from_param` | `AttributeError` at runtime | `project.py:1600-1605` |

Root cause: **schema validation is advisory** — `__read_config` logs errors and continues anyway (`project.py:181-192`), and no cross-field coherence checks exist.

### 3.8 Early-stop logic is wrong — `project.py:1753-1756`, `1699-1701`
- `len(outdata) < int(self.page_limit)` compares the page's **byte length** to a **record-count** limit: with a large `page_size_limit` a legitimate short page aborts the run; with a small one it never fires.
- `len(outdata) == 0` only catches zero-byte HTTP bodies; a JSON empty page (`{"data": []}`) is ≥2 bytes, so without total/pages keys the tool fetches all 20,000 `DEFAULT_NUMBER_OF_PAGES`.

### 3.9 Data-integrity: falsy values silently dropped — `common.py:72, 107`
`if res:` in `get_dict_value`/`set_dict_value` discards `0`, `False`, `""`, `{}` when traversing arrays. For a backup tool whose job is faithful capture, records where a nested key is `0`/`false` are silently lost. Fix: `if res is not None:`.

### 3.10 Smaller confirmed bugs
- **Zip append mode duplicates entries** (`storage/backends.py:121`): re-fetched pages on continue/update create duplicate `page_N.json` members; `export()`/`info()` iterate `namelist()` and double-count; resume off-by-one (`project.py:1228`) compounds it.
- **xml/html + sqlite crash** (`project.py:1680-1694`, `backends.py:80`): `handle_success` yields `bytes` for json but `str` for xml/html → `sqlite3.Binary(str)` TypeError.
- **`getfiles` without `[files]` section** → `AttributeError` (`project.py:2557`, `2577`, `2450`); unknown `fetch_mode` → `NameError` (2585).
- **`follow()` wrong-script guard** (`project.py:2153-2155`): checks `code_postfetch` but executes `run_path(self.code_follow)` → `run_path(None)`.
- **Continue-mode page scan uses wrong range** (`project.py:1566-1570`): `range(self.start_page, num_pages)` should be `end_page`; loop can complete without setting `start_page` → full re-download.
- **Content-disposition dead code** (`project.py:2586-2589` vs `2616-2617`): carefully derived server filename is unconditionally overwritten.
- **`create()` generates an unusable INI** (`project.py:918-933`): only `[settings]`; next command hits `NoSectionError: storage`.
- **`create` CLI accepts 9 options that are completely ignored** (`core.py:417-440`, all `# noqa: ARG001`) — users reasonably expect `--datakey` etc. to land in the config.
- **`YAMLConfigParser` defects** (`config_loader.py`): YAML `null` → literal string `"None"` (164); `getint`/`getboolean(fallback=None)` raise instead of returning None (166-171); dead `isinstance(value, bool)` (178).
- **`__init__.py`**: `__licence__` misspelled (should be `__license__`); version hardcoded (drift risk with pyproject).
- **`detect` missing `FileNotFoundError` handling** (`core.py:556-602`) → raw traceback on missing project.

---

## 4. Security Findings

| # | Severity | Issue | Location |
|---|---|---|---|
| S1 | **Medium** | **Secrets in logs**: full request params (API keys commonly ride in query params) logged at INFO; full headers **including `Authorization`** logged at DEBUG. Log file `apibackuper.log` is always written to cwd at DEBUG level with default permissions | `project.py:773`, `779-780`; `core.py:32-36` |
| S2 | **Medium** | **Zip-slip**: server-controlled data used as zip member names with no sanitization — `urlparse(url).path` (leading `/`, `../`), content-disposition filenames, follow-mode keys from API data (`'%s.json' % key`). Traversal entries are written into `files.zip`/`details.zip`; only `FilesystemStorage._safe_path` guards (and it uses `abspath`, not `realpath` — symlink escape) | `project.py:2617`, `2588-2589`, `2082`, `2253`, `2321`, `2387`; `storage/__init__.py:55-64` |
| S3 | **Medium** | **Query-string injection via unencoded URL building**: raw `"%s=%s"` interpolation, no `urlencode` — values with `&`/`=`/`#`/spaces corrupt or extend the query | `cmds/utils.py:29-42`; `project.py:764-765`, `2704-2706` |
| S4 | **Medium** | **Global warning suppression at import**: `urllib3.disable_warnings()` + filterwarnings at module scope hide `InsecureRequestWarning` process-wide — users running `verify_ssl = false` get **no warning at all**; host applications using apibackuper as a library lose these warnings too | `core.py:26-29` |
| S5 | **Medium** | **OAuth2 refresh**: no `timeout` on the refresh POST (can hang a run forever); inherits session `verify=False` (refresh token over unverified TLS); silently returns False on non-200 with no log; ignores rotated `refresh_token` in the response | `auth.py:131-146` |
| S6 | **Low-Med** | **Import-time side effects**: importing the package creates `apibackuper.log` in cwd, hijacks the root logger at DEBUG, never closes/rotates the handler — bad library hygiene, unbounded log growth | `core.py:32-36` |
| S7 | **Low** | **`Bearer None` header**: oauth2 branch populates `auth_data` even when token is None; `get_headers` tests key presence, not truthiness | `auth.py:97-101`, `121-122` |
| S8 | **Low** | Missing `token_file`/`password_file` silently disables auth with no warning | `auth.py:43-47`, `56-60`, `82-86` |
| S9 | Info | Config = code: hook scripts and `code_postfetch`/`code_follow` execute arbitrary Python via `runpy.run_path` — by design for a local CLI, but must be documented prominently | `project.py:594-637`, `1348`, `2154`, `2664` |
| S10 | Low | Path traversal via follow-rule `name` in `details_{name}.zip` (config-controlled) | `project.py:1974` |

Positive: no committed secrets; SSL-disable path logs a warning (when logging works); OIDC trusted publishing on PyPI; CodeQL/bandit/dependency-review active.

---

## 5. Test Suite Assessment

**Status: red.** Full run (Python 3.13): **25 failed, 113 passed, ~62s** (with timeouts forced).

### Failure groups — all traceable to commit f3fe6c0 changing APIs without updating tests
1. **`test_config_loader.py` — 12 failures**: `validate_yaml_config` now returns `Tuple[bool, List]` (tests assert `is True`); `YAMLConfigParser.__init__` now takes a dict (tests pass a path); `getfloat()`/`sections()` no longer exist.
2. **`test_project.py` — 11 failures**: conftest fixtures `sample_config_ini`/`sample_config_yaml` use the **legacy schema** (no required `settings` section) → `NoSectionError`.
3. **`test_rate_limiter.py` — 2 hangs**: `test_wait_if_needed_minute_limit` sleeps **60 real seconds**; `test_wait_if_needed_hour_limit` sleeps **~1 hour**. The committed repo-root `apibackuper.log` proves a past run actually waited. CI (py3.8–3.12, no pytest-timeout) is currently red + burns hours.

### Coverage (deselecting the 2 hanging tests)
| Module | Cover | Module | Cover |
|---|---|---|---|
| `cmds/project.py` | **13%** | `core.py` | 48% |
| `__main__.py` | 0% | `cmds/config_loader.py` | 56% |
| `auth.py` | 91% | `rate_limiter.py` | 76% |
| `storage/*` | 89-100% | `common.py` | 73% |
| **TOTAL** | **29%** | | |

### Quality issues
- **The core engine is untested**: `run()` fetch/pagination (1311-1874, incl. the parallel engine and recently-patched thread-safety counters), `export()`, `follow()`, `getfiles()`, `estimate()`, `_single_request` error paths — all effectively zero coverage.
- **Tautological CLI tests**: 9 tests assert `result.exit_code in [0, 1]` — they pass even when the command crashes. `test_info_command_json` catches `JSONDecodeError` and passes anyway — a test that cannot fail.
- **No HTTP mocking at all**: not one test of `_single_request` with a mocked `requests.Session` (the `mock_requests_session` fixture exists but is unused — 4 of 7 conftest fixtures are entirely unused).
- **Flaky risks**: global `os.chdir()` in 16 tests (breaks pytest-xdist, leaks on failure); global root-logger mutation; `time.sleep(0.2)` then assert `elapsed < 0.1` (fails on loaded CI); patching `time.time` globally.
- **Bug fixes without regression tests**: the f3fe6c0 fixes (thread-safety counters, file-handle leaks in `getfiles`/`follow`, pagination division) have no tests — exactly how §3 regressions crept in.

---

## 6. Architecture & Code Quality

### 6.1 `cmds/project.py` is a god module (3,249 lines)
`ProjectBuilder` (lines 111-3249) holds ~60 attributes set imperatively in `__read_config` (~350 lines of repetitive `has_option`/`get` chains) and every concern: config parsing, HTTP, retries, hooks, state, export, follow, file downloads, stats, validation. God-functions: `run()` ~565 lines, `export()` ~320 (three copy-pasted storage-iteration blocks), `info()` ~330, `follow()` ~265 + `_follow_rule()` ~180 (the same "extract keys from zip pages" loop appears **6 times**), `getfiles()` ~250, `_single_request()` ~185 (5 hand-built near-identical error messages). A stale `cmds/__pycache__/http_client.*.pyc` with no source file suggests a split was started and abandoned.

**Recommended decomposition** (target: thin facade + focused modules):
```
cmds/config.py      typed ProjectConfig dataclass, per-section parsers (parse once, not per-access)
cmds/http_client.py _single_request, retry policy, error formatting; dedicated RequestFailed exception
cmds/hooks.py       _run_hook, _serialize_response
cmds/state.py       state/checkpoint IO with atomic writes (temp file + rename)
cmds/runner.py      run/fetch_page/handle_success; backend as context manager; one dispatch for seq+parallel
cmds/export.py      export + where/fields; one page-iterator generator shared by all storages
cmds/follow.py      merge follow/_follow_rule into one extract-keys→download pipeline
cmds/files.py       getfiles
cmds/inspect.py     info, estimate, detect, validate_config
storage/            merge the two parallel hierarchies (backends.py vs __init__.py); add __enter__/__exit__
```

### 6.2 Other structural issues
- **Two parallel storage abstractions** (`storage/backends.py:StorageBackend` vs `storage/__init__.py:FileStorage`) — `ZipFileStorage` is used only by `getfiles`.
- **~200 lines of duplicated exception handling** in `core.py` — the `_handle_cli_errors` decorator vs 4 inline `try/except` blocks with drifting messages.
- **Parsed-but-ignored options**: `storage.compression`, `compression_level`, `max_file_size`, `split_files`; `request.retry_*` flat keys parsed but rejected by the schema (`additionalProperties: false`).
- **Schema/code drift** (see §3.7) + no `FormatChecker` (`"format": "uri"` never enforced) + only first error reported (no `iter_errors`).
- **State/checkpoint writes not atomic** (`project.py:555-592`) — a crash mid-write corrupts resume state.
- **`time.sleep(default_delay)` fires after the response**, not between requests — first burst goes undelayed (`project.py:1652`).
- **Dead code**: `init()`, empty `to_package()`, `skipped_files_dict` bookkeeping never consulted, `self.id`, `settings.initialized` never set True, commented-out `__main__` block in `core.py`.
- **Sqlite backend commits every page** (`backends.py:82,90`) — an fsync per page; no batching, no WAL.
- **Not thread-safe** rate limiter (no lock) despite parallel fetching being a headline feature.

---

## 7. Packaging, CI, Docs, Hygiene

1. **Release provenance broken for 1.0.13**: no CHANGELOG entry (changes sit under `[Unreleased]`), no HISTORY entry, **no git tag** — yet dist artifacts exist and it was pushed to PyPI.
2. **Three conflicting dependency sources**: `pyproject.toml` (authoritative, `aria2p/pandas/pyarrow` optional) vs `requirements.txt` (makes all three **mandatory**) vs `setup.py` (third, differently-pinned list, dead under PEP 621). Version hardcoded in both `pyproject.toml` and `__init__.py` — no single-sourcing.
3. **Coverage config silently broken**: `.coveragerc` takes precedence over pyproject `[tool.coverage.*]` → the pyproject `omit`/`exclude_lines` never apply. Pick one (delete `.coveragerc`).
4. **README.md is pandoc-corrupted**: `::: contents :::` fences, `\--`, `It\'s`, YAML title block — it is the PyPI `long_description` and renders broken; also cites stale `apibackuper/1.0.11` user-agent; "What's New" stops at 1.0.12.
5. **Dual changelogs diverging**: `HISTORY.md` (with `2024-XX-XX` placeholder dates) vs `CHANGELOG.md` — keep one.
6. **Committed junk**: `pylint_report.txt` (82 KB), a stray 33-byte file named `flake8` (accidental redirect). `.gitignore` lacks `apibackuper_state.json`, `*.sqlite`, `*.parquet` (artifacts this tool itself produces, already untracked under `examples/features/`), while over-broadly ignoring `*.zip`/`*.jsonl`.
7. **CI matrix**: ubuntu-only (a cross-platform CLI), tests EOL Python 3.8, **omits 3.13**; pytest flags triple-defined (ci.yml, tox.ini, pyproject addopts); workflows README claims "3.6-3.12"; `requirements.txt` header says "Python 3.6+".
8. **publish.yml**: OIDC trusted publishing ✅, but `workflow_dispatch.version` input is **never used** (manual dispatch silently publishes whatever is checked out); actions not SHA-pinned; no SLSA provenance attestation.
9. **Dead configs**: `[tool.flake8]` in pyproject (flake8 never reads pyproject); `.pyre_configuration` with machine-specific absolute paths; duplicated `check-json` + local JSON hook in pre-commit; stale tox comment about py3.6/3.7.
10. **Tag scheme inconsistent**: `1.0.4`, `1.0.6` vs `v1.0.11`, `v1.0.12`.

---

## 8. Prioritized Roadmap

### P0 — Correctness & data safety (do first; each is small)
1. Fix storage lifecycle: context manager / `try/finally` around backend in `run()` (fixes zip corruption §3.1) — and save state on all exit paths.
2. Fix OAuth2 retry kwargs collision (§3.2) and retry exception mismatch (§3.3) — introduce `RequestFailed`.
3. Fix `enable_verbose` guard (check `h.stream is sys.stderr` or exclude `FileHandler`) and set logger level in `enable_logging` (§3.4-3.5).
4. Fix rate-limiter `last_update` after sleep (§3.6); add a lock for thread safety.
5. Fix falsy-value dropping in `common.py` (§3.9): `if res is not None:`.
6. Parse `retry_on_errors` accepting both string and list; guard `data_key=None`; reconcile `filesystem` storage + fractional `default_delay` with the schema (§3.7).
7. Rewrite early-stop conditions: count records, detect empty JSON pages via `data_key` (§3.8).
8. Green the test suite: update conftest fixtures to the `settings`-based schema, rewrite `YAMLConfigParser` tests for the dict API, update `validate_yaml_config` tests, **mock `time.sleep`** in rate-limiter tests, add pytest-timeout to CI.

### P1 — Security & reliability
9. Redact `Authorization`/token params from logs; write log file into the project dir, not cwd; move logging setup out of import time into `cli()` (S1, S4, S6).
10. Sanitize all zip member names (central `_safe_name`) (S2); `urlencode` all query building (S3).
11. OAuth2 refresh: add timeout, propagate verify, handle refresh-token rotation, log failures (S5, S7).
12. Atomic state/checkpoint writes; dedupe-or-replace strategy for zip append (or switch default to sqlite); batch sqlite commits / enable WAL.
13. Make schema validation **fail-fast** with `iter_errors` + `FormatChecker` + cross-field checks; sync schema↔code (retry keys, compression, filesystem).
14. Add regression tests for every P0 fix; mocked-`Session` tests for `_single_request` (timeouts, 4xx/5xx, retry exhaustion, 401-refresh); state/resume tests; replace `exit_code in [0,1]` with real assertions.

### P2 — Structure & maintenance
15. Decompose `cmds/project.py` per §6.1; merge storage hierarchies; delete dead code (`init`, `to_package`, ignored `create` options — or wire them up).
16. Packaging: delete `setup.py` and `requirements.txt` (or regenerate from pyproject via `pip-compile`); single-source version (`importlib.metadata` or setuptools dynamic); fix PEP 639 license form.
17. Release hygiene: tag 1.0.13, move `[Unreleased]` → `[1.0.13]`, drop `HISTORY.md`, adopt one tag scheme; fix `publish.yml` version input, SHA-pin actions, add SLSA attestation.
18. CI: add macOS/Windows + Python 3.13, drop 3.8; consolidate pytest flags in pyproject only; delete `.coveragerc`, `.pyre_configuration`, `[tool.flake8]`; update `.gitignore`.
19. Docs: clean README pandoc artifacts; add a "config = executable code" security note (S9); document hook context format; refresh `examples/README.md` for `features/` + `templates/`; fix stale version strings.

### Quick wins (< 1 day total)
- Items 3, 4, 5, 6 (partial), `__license__` typo, `.gitignore` entries, delete `pylint_report.txt` + `flake8` file + `.coveragerc`, mock the two hanging tests, tag 1.0.13 + changelog entry.

---

## 9. Conclusion

The project's feature set (parallel fetching, resume/checkpoint, hooks, multiple storages, export filters) is genuinely strong, and the security tooling posture on CI is better than most projects of this size. The dominant risks are **untested core paths** (13% coverage on the main module), a **red test suite masking regressions**, and a cluster of **small, high-impact correctness bugs** in error/exit paths — exactly the paths that run when something is already going wrong. The P0 list is almost entirely one-to-five-line fixes; doing those + greening CI before any further feature work will change the project's reliability profile disproportionately. The `project.py` decomposition (P2) should follow once tests can act as a safety net.
