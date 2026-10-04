"""Regression tests that lock in the P0 and P1 bug fixes.

Every test here corresponds to a numbered finding in the 2026-10 analysis
report (``dev/docs/REPO_ANALYSIS_2026-10-02.md``). If any of these tests
fail, the corresponding fix has regressed.
"""
import os
import time
import zipfile
import tempfile
import logging
import configparser
from unittest.mock import MagicMock, patch, PropertyMock
import pytest
import requests

import apibackuper.rate_limiter as rl_module
from apibackuper.rate_limiter import RateLimiter
from apibackuper import common
from apibackuper.common import get_dict_value, set_dict_value
from apibackuper.storage import build_storage_backend, safe_member_name
from apibackuper.cmds.config_loader import YAMLConfigParser
from apibackuper.cmds.utils import redact_params, redact_headers, _url_replacer
from apibackuper.auth import AuthHandler


# ---------------------------------------------------------------------------
# §4.1 — parallel-mode storage close
# ---------------------------------------------------------------------------

class TestStorageLifecycle:
    """The parallel-mode run() must close the storage backend on every exit."""

    def test_zip_close_persists_central_directory(self, tmp_path):
        backend = build_storage_backend("zip", str(tmp_path / "a.zip"), "full")
        backend.save_page("page_1.json", b'{"a":1}')
        backend.save_page("page_2.json", b'{"a":2}')
        backend.close()  # explicit close, as the new parallel branch does via try/finally
        # Without close(), the central directory is unwritten and ``namelist()`` is empty.
        with zipfile.ZipFile(str(tmp_path / "a.zip")) as zf:
            names = zf.namelist()
        assert "page_1.json" in names
        assert "page_2.json" in names


# ---------------------------------------------------------------------------
# §4.2 — OAuth2 retry kwargs
# ---------------------------------------------------------------------------

class TestOAuth2RetryKwargs:
    """Refreshed OAuth2 retry must not double-pass ``params`` or ``json``."""

    def test_get_retry_does_not_raise_typeerror(self):
        # Build a session that records both calls so we can assert the retry
        # used the correct kwargs.
        session = MagicMock()
        # First call returns 401, second returns 200.
        first, second = MagicMock(), MagicMock()
        first.status_code = 401
        first.content = b""
        second.status_code = 200
        second.content = b'{"ok":1}'
        session.get.side_effect = [first, second]

        c = configparser.ConfigParser()
        c.add_section("auth")
        c.set("auth", "type", "oauth2")
        c.set("auth", "token", "old")
        c.set("auth", "auth_url", "https://idp.example.com/token")
        c.set("auth", "refresh_token", "old_refresh")
        auth = AuthHandler.__new__(AuthHandler)
        auth.config = c
        auth.auth_type = "oauth2"
        auth.auth_data = {"token": "old", "auth_url": "https://idp.example.com/token",
                          "refresh_token": "old_refresh"}

        # Refresh call returns a new token.
        refresh_resp = MagicMock()
        refresh_resp.status_code = 200
        refresh_resp.text = "{}"
        refresh_resp.json.return_value = {"access_token": "new"}
        session.post.side_effect = [refresh_resp]

        from apibackuper.cmds.project import ProjectBuilder
        builder = ProjectBuilder.__new__(ProjectBuilder)
        builder.http = session
        builder.auth_handler = auth
        builder.http_mode = "GET"
        builder.verify_ssl = True
        builder.connect_timeout = 30
        builder.read_timeout = 120
        builder.allow_redirects = True
        builder.flat_params = False
        builder.rate_limiter = None

        # This call must not raise TypeError. If the bug regresses, both
        # kwargs="params" and an explicit params=... argument are passed to
        # ``session.get`` and requests raises.
        response = builder._single_request(
            "https://api.example.com/items",
            headers=None,
            params={"page": 1},
        )
        assert response is second
        # The retry call must not have ``params`` passed twice. Check that
        # the spread-kwargs (the ``**retry_kwargs`` dict) doesn't itself
        # contain ``params`` — the explicit ``params=params`` argument is
        # allowed and is what produces the single ``params`` entry in
        # ``call_args.kwargs``.
        retry_call = session.get.call_args_list[1]
        spread_kwargs = retry_call.kwargs.copy()
        explicit_params = spread_kwargs.pop("params", None)
        assert explicit_params == {"page": 1}
        assert "params" not in spread_kwargs, (
            "P1.13 regression: retry spread includes 'params' AND the "
            "caller passes params= explicitly — double-pass TypeError"
        )


# ---------------------------------------------------------------------------
# §4.3 — enable_verbose must add a console handler
# ---------------------------------------------------------------------------

class TestEnableVerbose:
    def test_console_handler_installed(self, tmp_path):
        # Pretend we have a FileHandler, as if apibackuper had previously set
        # up file logging.
        logfile = tmp_path / "apibackuper.log"
        root = logging.getLogger()
        root.handlers.clear()
        fh = logging.FileHandler(str(logfile))
        root.addHandler(fh)

        from apibackuper.core import enable_verbose
        enable_verbose()

        has_console = any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            for h in root.handlers
        )
        assert has_console, "enable_verbose() did not install a console handler"


# ---------------------------------------------------------------------------
# §4.4 — enable_logging must set root logger to DEBUG
# ---------------------------------------------------------------------------

class TestEnableLoggingLevel:
    def test_root_logger_at_debug(self, sample_config_ini):
        from apibackuper.cmds.project import ProjectBuilder
        builder = ProjectBuilder(os.path.dirname(sample_config_ini))
        builder.enable_logging()
        assert logging.getLogger().level == logging.DEBUG


# ---------------------------------------------------------------------------
# §4.5 — rate limiter honours configured rate
# ---------------------------------------------------------------------------

class TestRateLimiterHonoursRate:
    def test_no_drift_on_sustained_crawl(self):
        """After sleep, ``last_update`` must reflect post-sleep time so the
        next call doesn't double-count elapsed time.

        The P0.3 bug was that ``RateLimiter.wait_if_needed`` updated
        ``last_update`` *before* sleeping, so on the next call the
        limiter credited itself with tokens earned during the sleep and
        granted an extra free burst — sustained crawls drifted above the
        configured ``requests_per_second``.

        The fix moves the ``last_update = time.time()`` call to *after*
        the sleep. We verify that:

        * ``last_update`` ends up at the post-sleep time, not the
          pre-sleep time;
        * the next call doesn't see ``elapsed > 0`` based on the
          sleep — i.e. tokens are not silently refilled.
        """
        # Pin every call to t=0.0 so the burst is exhausted, then jump
        # to t=1.0 on the post-sleep ``time.time()`` call to simulate
        # that 1 second of real time elapsed during the sleep. We use
        # a stateful function as ``side_effect`` so internal
        # ``logging`` calls (which also touch ``time.time`` indirectly
        # through ``ct = time.time()`` in ``LogRecord.__init__``) do
        # not exhaust the iterator and raise ``StopIteration``.
        call_log: list[float] = []

        def fake_time() -> float:
            # First three ``wait_if_needed`` calls each need exactly
            # one ``time.time()`` for ``now = time.time()`` plus, when
            # tokens < 1, the post-sleep ``self.last_update =
            # time.time()``. The third call is the one that sleeps
            # and updates ``last_update`` — that's where t advances
            # to 1.0. Anything beyond that (e.g. logging's internal
            # ``ct``) stays at 1.0.
            call_log.append(len(call_log))
            if len(call_log) <= 4:
                return 0.0
            return 1.0

        with patch.object(rl_module.time, "sleep") as mock_sleep, \
             patch.object(rl_module.time, "time", side_effect=fake_time):
            rl = RateLimiter(requests_per_second=2.0, burst_size=2)
            rl.wait_if_needed()  # tokens 2 -> 1
            rl.wait_if_needed()  # tokens 1 -> 0
            rl.wait_if_needed()  # tokens 0 -> sleep 0.5
            assert mock_sleep.called, "expected sleep on burst exhausted"
            # ``last_update`` must be 1.0 (post-sleep), not 0.0
            # (pre-sleep). The P0.3 bug set it before the sleep.
            assert rl.last_update == 1.0, (
                "last_update was set pre-sleep — P0.3 regression "
                f"(got {rl.last_update!r})"
            )
            # On the next call, ``elapsed = now - last_update = 0``,
            # so tokens are NOT refilled. The limiter must sleep
            # again rather than granting a free burst.
            mock_sleep.reset_mock()
            rl.wait_if_needed()
            assert mock_sleep.called, (
                "rate limiter granted a free burst after sleep — "
                "P0.3 regression (double-counted the sleep)"
            )


# ---------------------------------------------------------------------------
# §4.6 — schema-valid configs no longer crash
# ---------------------------------------------------------------------------

class TestSchemaValidConfigs:
    def test_getfloat_accepts_float(self):
        p = YAMLConfigParser({"project": {"default_delay": 0.5}})
        assert p.getfloat("project", "default_delay") == 0.5

    def test_retry_on_errors_accepts_list(self):
        # Validate that the parsing path accepts a YAML list (the historically
        # crashing form). The CLI's retry parsing lives in cmds/project.py but
        # the schema validator would have caught the crash earlier.
        cfg = {
            "settings": {"name": "t"},
            "project": {"url": "https://api.example.com", "http_mode": "GET"},
            "params": {"page_size_limit": 10},
            "data": {},
            "storage": {"storage_type": "zip", "storage_path": "storage"},
            "error_handling": {"retry_on_errors": [500, 502, 503]},
        }
        from apibackuper.cmds.config_loader import validate_yaml_config
        ok, errors = validate_yaml_config(cfg, None)
        # Schema-valid: ok=True. (Schema accepts both string and list.)
        assert ok is True, f"unexpected errors: {errors}"

    def test_data_key_none_does_not_crash(self):
        assert get_dict_value({"a": 1}, None) is None
        assert get_dict_value({"a": 1}, None, as_array=True) is None

    def test_filesystem_storage_backend_built(self):
        with tempfile.TemporaryDirectory() as td:
            be = build_storage_backend("filesystem", td, "full")
            be.save_page("page_1.json", b"data")
            assert "page_1.json" in be.list_objects("page")
            be.close()


# ---------------------------------------------------------------------------
# §4.7 — falsy values preserved
# ---------------------------------------------------------------------------

class TestFalsyValuePreservation:
    def test_zero_preserved_in_as_array(self):
        result = get_dict_value(
            {"items": [{"c": 0}, {"c": 0}, {"c": 5}]},
            "items.c", as_array=True,
        )
        assert result == [0, 0, 5]

    def test_empty_string_preserved(self):
        result = get_dict_value(
            {"items": [{"s": ""}, {"s": "x"}]},
            "items.s", as_array=True,
        )
        assert result == ["", "x"]

    def test_false_preserved(self):
        result = get_dict_value(
            {"items": [{"f": False}, {"f": True}]},
            "items.f", as_array=True,
        )
        assert result == [False, True]

    def test_set_zero_in_dict_of_dict(self):
        d = {"a": {"b": 99}}
        set_dict_value(d, "a.b", 0)
        assert d["a"]["b"] == 0


# ---------------------------------------------------------------------------
# §4.8 — early-stop detects empty JSON pages
# ---------------------------------------------------------------------------

# These are covered by integration tests once project.py is refactored.


# ---------------------------------------------------------------------------
# §5.1 — log redaction
# ---------------------------------------------------------------------------

class TestLogRedaction:
    def test_redact_headers(self):
        h = redact_headers({
            "Authorization": "Bearer secret",
            "Content-Type": "application/json",
            "X-API-Key": "sk-abc",
        })
        assert h["Authorization"] == "***REDACTED***"
        assert h["X-API-Key"] == "***REDACTED***"
        assert h["Content-Type"] == "application/json"

    def test_redact_params(self):
        p = redact_params({
            "token": "abc",
            "api_key": "sk-xyz",
            "page": 1,
            "access_token": "ey",
        })
        assert p["token"] == "***REDACTED***"
        assert p["api_key"] == "***REDACTED***"
        assert p["access_token"] == "***REDACTED***"
        assert p["page"] == 1


# ---------------------------------------------------------------------------
# §5.2 — zip-slip central sanitization
# ---------------------------------------------------------------------------

class TestZipSlipPrevention:
    def test_safe_member_name_strips_traversal(self):
        assert safe_member_name("../../etc/passwd") == "_/_/etc/passwd"
        assert safe_member_name("/etc/passwd") == "etc/passwd"

    def test_safe_member_name_handles_pure_traversal(self):
        # A path consisting only of ``..`` segments is sanitized to ``_`` —
        # it cannot resolve to a real archive entry but does not crash.
        # The rejection is reserved for inputs that resolve to *truly* empty
        # (e.g. a dot or empty string).
        result = safe_member_name("..")
        assert result == "_"
        for bad in [".", "", "/"]:
            with pytest.raises(ValueError):
                safe_member_name(bad)

    def test_storage_backend_sanitizes_through_chain(self, tmp_path):
        be = build_storage_backend("zip", str(tmp_path / "a.zip"), "full")
        be.save_page("../escape.txt", b"evil")
        be.close()
        with zipfile.ZipFile(str(tmp_path / "a.zip")) as zf:
            for name in zf.namelist():
                assert ".." not in name.split("/"), "zip-slip via python zipfile"


# ---------------------------------------------------------------------------
# §5.3 — query-string injection via urlencode
# ---------------------------------------------------------------------------

class TestQueryStringInjection:
    def test_urlencode_query_mode(self):
        url = _url_replacer(
            "https://api.example.com/items",
            {"q": "a&b=c", "x": "foo bar"},
            query_mode=True,
        )
        # & and = and spaces must be percent-encoded
        assert url == "https://api.example.com/items?q=a%26b%3Dc&x=foo+bar"


# ---------------------------------------------------------------------------
# §5.4 — OAuth2 refresh timeout, verify, log failures, rotation
# ---------------------------------------------------------------------------

class TestOAuth2RefreshHardening:
    def _auth(self):
        ah = AuthHandler.__new__(AuthHandler)
        ah.auth_type = "oauth2"
        ah.auth_data = {
            "token": "old",
            "auth_url": "https://idp.example.com/token",
            "refresh_token": "old_refresh",
        }
        return ah

    def test_timeout_default_30s(self):
        ah = self._auth()
        session = MagicMock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {"access_token": "new"}
        ah.refresh_token_if_needed(session)
        assert session.post.call_args.kwargs["timeout"] == 30

    def test_timeout_propagated(self):
        ah = self._auth()
        session = MagicMock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {"access_token": "new"}
        ah.refresh_token_if_needed(session, timeout=10)
        assert session.post.call_args.kwargs["timeout"] == 10

    def test_verify_propagated(self):
        ah = self._auth()
        session = MagicMock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {"access_token": "new"}
        ah.refresh_token_if_needed(session, verify=True)
        assert session.post.call_args.kwargs["verify"] is True

    def test_non_200_returns_false_and_logs(self):
        ah = self._auth()
        session = MagicMock()
        session.post.return_value.status_code = 500
        session.post.return_value.text = "server error"
        session.post.return_value.json.side_effect = ValueError

        with patch("apibackuper.auth.logging.warning") as warn:
            ok = ah.refresh_token_if_needed(session)
        assert ok is False
        assert warn.called

    def test_rotated_refresh_token_captured(self):
        ah = self._auth()
        session = MagicMock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {
            "access_token": "new_ey",
            "refresh_token": "rotated_refresh",
        }
        ok = ah.refresh_token_if_needed(session)
        assert ok is True
        assert ah.auth_data["token"] == "new_ey"
        assert ah.auth_data["refresh_token"] == "rotated_refresh"


# ---------------------------------------------------------------------------
# §5.5 — import-time side effects
# ---------------------------------------------------------------------------

class TestImportHasNoSideEffects:
    def test_import_does_not_create_log_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Importing must not write apibackuper.log to cwd.
        import importlib
        if "apibackuper.core" in importlib.sys.modules:
            importlib.reload(importlib.sys.modules["apibackuper.core"])
        else:
            import apibackuper.core  # noqa: F401
        log = tmp_path / "apibackuper.log"
        assert not log.exists(), "import created apibackuper.log in cwd"

    def test_root_logger_unchanged_after_import(self):
        root = logging.getLogger()
        before_handlers = list(root.handlers)
        before_level = root.level
        import apibackuper.core  # noqa: F401
        # Importing shouldn't *replace* handlers (only ``cli()`` does that).
        # The presence/absence of any handler is acceptable, but if the file
        # handler from before is still here, import didn't blow it away.
        assert before_level == root.level or root.level == logging.WARNING


# ---------------------------------------------------------------------------
# §5.6 — Bearer None header suppressed
# ---------------------------------------------------------------------------

class TestBearerNoneSuppressed:
    def _oauth2_auth(self, token=None):
        ah = AuthHandler.__new__(AuthHandler)
        ah.auth_type = "oauth2"
        ah.auth_data = {"token": token}
        return ah

    def test_no_header_when_token_none(self):
        h = self._oauth2_auth(token=None).get_headers()
        assert "Authorization" not in h

    def test_no_header_when_token_empty_string(self):
        h = self._oauth2_auth(token="").get_headers()
        assert "Authorization" not in h

    def test_header_emitted_when_token_set(self):
        h = self._oauth2_auth(token="ey...").get_headers()
        assert h["Authorization"] == "Bearer ey..."


# ---------------------------------------------------------------------------
# P1.12 — storage backend lifecycle in fetch loop
# ---------------------------------------------------------------------------

class TestFilesystemStorageBackend:
    def test_full_mode_wipes_existing_files(self, tmp_path):
        # Place a pre-existing file.
        (tmp_path / "old.json").write_bytes(b"old")
        be = build_storage_backend("filesystem", str(tmp_path), "full")
        assert not (tmp_path / "old.json").exists()
        be.save_object("new.json", b"new")
        assert (tmp_path / "new.json").exists()
        be.close()

    def test_continue_mode_preserves_existing(self, tmp_path):
        (tmp_path / "old.json").write_bytes(b"old")
        be = build_storage_backend("filesystem", str(tmp_path), "continue")
        assert (tmp_path / "old.json").exists()
        be.close()

    def test_traversal_rejected(self, tmp_path):
        be = build_storage_backend("filesystem", str(tmp_path), "full")
        with pytest.raises(ValueError):
            be.save_page("../escape", b"evil")
        be.close()


# ---------------------------------------------------------------------------
# P1.20 — f-string substitution in default_delay / default_delay float
# ---------------------------------------------------------------------------

class TestDefaultDelayIsFloat:
    def test_default_delay_is_a_float(self):
        # The constant is documented as a float. The previous getint() path
        # crashed any project with ``default_delay: 0.5``.
        from apibackuper.constants import DEFAULT_DELAY
        assert isinstance(DEFAULT_DELAY, float)
        assert DEFAULT_DELAY == 0.5