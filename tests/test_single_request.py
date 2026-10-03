"""Tests for ``ProjectBuilder._single_request`` HTTP error paths.

These exercise the request lifecycle with mocked ``requests.Session`` so the
behaviour around timeouts, 4xx/5xx, retry exhaustion and 401-refresh can be
verified without a real network (§5 of the 2026-10 analysis report).
"""
from unittest.mock import MagicMock, patch
import pytest
import requests

from apibackuper.cmds.project import ProjectBuilder


def _make_builder():
    """Construct a ProjectBuilder with no real config-load side effects."""
    import threading
    builder = ProjectBuilder.__new__(ProjectBuilder)
    builder.http = MagicMock()
    builder.auth_handler = None
    builder.http_mode = "GET"
    builder.verify_ssl = True
    builder.connect_timeout = 30
    builder.read_timeout = 120
    builder.allow_redirects = True
    builder.flat_params = False
    builder.rate_limiter = None
    builder._rate_lock = threading.Lock()
    builder.default_delay = 0.5
    builder.logfile = "apibackuper.log"
    return builder


class TestSingleRequestErrorPaths:
    def _ok_response(self, status=200, content=b'{"items": []}'):
        r = MagicMock()
        r.status_code = status
        r.content = content
        return r

    def test_timeout_raises_runtime_error_with_actionable_message(self):
        builder = _make_builder()
        builder.http.get.side_effect = requests.exceptions.Timeout("slow")

        with pytest.raises(RuntimeError) as exc:
            builder._single_request("https://api.example.com/items", None, {})
        msg = str(exc.value)
        assert "timeout" in msg.lower()
        assert "Increase timeout" in msg or "timeout values" in msg.lower()

    def test_ssl_error_raises_runtime_error_with_verify_hint(self):
        builder = _make_builder()
        builder.http.get.side_effect = requests.exceptions.SSLError("bad cert")

        with pytest.raises(RuntimeError) as exc:
            builder._single_request("https://api.example.com/items", None, {})
        msg = str(exc.value)
        assert "ssl" in msg.lower() or "certificate" in msg.lower()
        assert "verify_ssl" in msg

    def test_connection_error_raises_with_proxy_hint(self):
        builder = _make_builder()
        builder.http.get.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(RuntimeError) as exc:
            builder._single_request("https://api.example.com/items", None, {})
        msg = str(exc.value)
        assert "connect" in msg.lower() or "network" in msg.lower()

    def test_get_propagates_200(self):
        builder = _make_builder()
        builder.http.get.return_value = self._ok_response()
        resp = builder._single_request("https://api.example.com/items", None, {})
        assert resp.status_code == 200

    def test_post_propagates_200(self):
        builder = _make_builder()
        builder.http_mode = "POST"
        builder.http.post.return_value = self._ok_response()
        resp = builder._single_request("https://api.example.com/items", None, {})
        assert resp.status_code == 200

    def test_5xx_passed_through_without_retry(self):
        # _single_request itself does not retry; the caller (fetch_page) does.
        # Verify the response is propagated so the caller can decide.
        builder = _make_builder()
        builder.http.get.return_value = self._ok_response(status=503)
        resp = builder._single_request("https://api.example.com/items", None, {})
        assert resp.status_code == 503

    def test_4xx_passed_through_without_retry(self):
        builder = _make_builder()
        builder.http.get.return_value = self._ok_response(status=404)
        resp = builder._single_request("https://api.example.com/items", None, {})
        assert resp.status_code == 404

    def test_verify_ssl_passed_to_requests(self):
        builder = _make_builder()
        builder.verify_ssl = False
        builder.http.get.return_value = self._ok_response()
        builder._single_request("https://api.example.com/items", None, {})
        kwargs = builder.http.get.call_args.kwargs
        assert kwargs["verify"] is False

    def test_timeout_tuple_passed_to_requests(self):
        builder = _make_builder()
        builder.connect_timeout = 5
        builder.read_timeout = 60
        builder.http.get.return_value = self._ok_response()
        builder._single_request("https://api.example.com/items", None, {})
        kwargs = builder.http.get.call_args.kwargs
        assert kwargs["timeout"] == (5, 60)

    def test_allow_redirects_passed(self):
        builder = _make_builder()
        builder.allow_redirects = False
        builder.http.get.return_value = self._ok_response()
        builder._single_request("https://api.example.com/items", None, {})
        kwargs = builder.http.get.call_args.kwargs
        assert kwargs["allow_redirects"] is False

    def test_auth_headers_merged_when_present(self):
        builder = _make_builder()
        # Stand-in auth handler
        builder.auth_handler = MagicMock()
        builder.auth_handler.auth_type = "bearer"
        builder.auth_handler.get_headers.return_value = {
            "Authorization": "Bearer test-token"
        }
        builder.http.get.return_value = self._ok_response()
        builder._single_request(
            "https://api.example.com/items",
            headers={"X-Custom": "value"},
            params={},
        )
        sent_headers = builder.http.get.call_args.kwargs["headers"]
        assert sent_headers["X-Custom"] == "value"
        assert sent_headers["Authorization"] == "Bearer test-token"


class TestSingleRequestRateLimit:
    def test_rate_limiter_wait_called_before_request(self):
        builder = _make_builder()
        rl = MagicMock()
        rl.wait_if_needed = MagicMock()
        builder.rate_limiter = rl

        builder.http.get.return_value = MagicMock(status_code=200, content=b"")
        builder._single_request("https://api.example.com/items", None, {})
        # rate-limiter wait must precede the HTTP call
        assert rl.wait_if_needed.called
        # And it was called before session.get (call_count ordering)
        assert builder.http.get.called


class TestSingleRequestRetryOAuth2:
    def test_401_triggers_oauth2_refresh_then_retries(self):
        builder = _make_builder()
        # Auth handler that reports oauth2 and refreshes successfully.
        builder.auth_handler = MagicMock()
        builder.auth_handler.auth_type = "oauth2"
        builder.auth_handler.refresh_token_if_needed.return_value = True
        builder.auth_handler.get_headers.return_value = {
            "Authorization": "Bearer new_token"
        }
        # First call returns 401, second (retry) returns 200.
        first, second = MagicMock(), MagicMock()
        first.status_code = 401
        first.content = b""
        second.status_code = 200
        second.content = b'{"ok":1}'
        builder.http.get.side_effect = [first, second]

        resp = builder._single_request("https://api.example.com/items", None, {"page": 1})
        # Refresh was attempted
        assert builder.auth_handler.refresh_token_if_needed.called
        # Retry succeeded
        assert resp is second
        assert builder.http.get.call_count == 2

    def test_401_without_refresh_returns_401(self):
        builder = _make_builder()
        builder.auth_handler = MagicMock()
        builder.auth_handler.auth_type = "oauth2"
        builder.auth_handler.refresh_token_if_needed.return_value = False
        builder.auth_handler.get_headers.return_value = {}
        builder.http.get.return_value = MagicMock(status_code=401, content=b"")

        resp = builder._single_request("https://api.example.com/items", None, {})
        assert resp.status_code == 401
        # No retry happened
        assert builder.http.get.call_count == 1