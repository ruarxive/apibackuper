"""Tests for ``ProjectBuilder._single_request`` HTTP error paths.

These exercise the request lifecycle with mocked ``requests.Session`` so the
behaviour around timeouts, 4xx/5xx, retry exhaustion and 401-refresh can be
verified without a real network (§5 of the 2026-10 analysis report).
"""

import logging
import traceback
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

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
    builder.retry_max_retries = 2
    builder.retry_on_status = {500, 502, 503, 504}
    builder.error_retry_codes = {500, 502, 503, 504}
    builder.retry_backoff_strategy = "exponential"
    builder.retry_initial_delay = 0
    builder.retry_max_delay = 0
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
        builder.auth_handler.get_headers.return_value = {"Authorization": "Bearer test-token"}
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
        builder.auth_handler.get_headers.return_value = {"Authorization": "Bearer new_token"}
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


@pytest.mark.parametrize("existing_query", ["", "?existing=keep&empty="])
def test_flat_request_preserves_query_and_fragment_without_logging_secrets(caplog, existing_query):
    builder = _make_builder()
    builder.flat_params = True
    builder.http.get.return_value = MagicMock(status_code=200)
    url = f"https://user-secret:pass-secret@api.example.com/items{existing_query}#data"
    flattened = {
        "page": 2,
        "api_key": "flat-key-secret",
        "filter": {"token": "nested-filter-secret", "active": True},
    }
    with caplog.at_level(logging.INFO):
        builder._single_request(url, {"Authorization": "Bearer header-secret"}, {}, flattened)

    sent_url = builder.http.get.call_args.args[0]
    assert "?" in sent_url
    query = parse_qs(urlsplit(sent_url).query, keep_blank_values=True)
    assert query["page"] == ["2"]
    assert query["api_key"] == ["flat-key-secret"]
    assert "nested-filter-secret" in query["filter"][0]
    assert urlsplit(sent_url).fragment == "data"
    if existing_query:
        assert query["existing"] == ["keep"]
        assert query["empty"] == [""]
    assert urlsplit(sent_url).username == "user-secret"
    assert urlsplit(sent_url).password == "pass-secret"
    assert "params" not in builder.http.get.call_args.kwargs
    assert builder.http.get.call_args.kwargs["headers"]["Authorization"] == "Bearer header-secret"
    for secret in (
        "user-secret",
        "pass-secret",
        "flat-key-secret",
        "nested-filter-secret",
        "header-secret",
    ):
        assert secret not in caplog.text
    assert flattened["filter"]["token"] == "nested-filter-secret"


def test_oauth_flat_refresh_reuses_identical_encoded_url():
    builder = _make_builder()
    builder.flat_params = True
    builder.auth_handler = MagicMock(auth_type="oauth2")
    builder.auth_handler.get_headers.side_effect = [
        {"Authorization": "Bearer old-token"},
        {"Authorization": "Bearer refreshed-token"},
    ]
    builder.auth_handler.refresh_token_if_needed.return_value = True
    first = MagicMock(status_code=401)
    second = MagicMock(status_code=200)
    builder.http.get.side_effect = [first, second]

    response = builder._single_request(
        "https://api.example.com/items?existing=keep#data",
        None,
        {"ordinary": "unused"},
        {"page": 3, "filter": "a&b"},
    )
    assert response is second
    calls = builder.http.get.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == calls[1].args[0]
    parsed = urlsplit(calls[1].args[0])
    assert parse_qs(parsed.query) == {"existing": ["keep"], "page": ["3"], "filter": ["a&b"]}
    assert parsed.fragment == "data"
    assert "params" not in calls[1].kwargs
    assert calls[1].kwargs["headers"]["Authorization"] == "Bearer refreshed-token"
    builder.auth_handler.refresh_token_if_needed.assert_called_once_with(
        builder.http, verify=True, timeout=(30, 120)
    )


@pytest.mark.parametrize(
    "error_type", [requests.exceptions.Timeout, requests.exceptions.ConnectionError]
)
def test_request_transport_retries_are_bounded_and_diagnostics_redacted(caplog, error_type):
    builder = _make_builder()
    builder.rate_limiter = MagicMock()
    url = (
        "https://request-user-secret:request-pass-secret@api.example.com/items"
        "?token=request-token-secret"
    )
    builder.http.get.side_effect = error_type(
        f"Network failed for {url}; Authorization: Bearer exception-header-secret"
    )
    params = {"filter": {"api_key": "nested-param-secret"}}
    with patch("apibackuper.cmds.project.time.sleep"), caplog.at_level(logging.INFO):
        with pytest.raises(RuntimeError) as error:
            builder._request(url, params=params)

    assert builder.http.get.call_count == builder.retry_max_retries + 1
    assert builder.rate_limiter.wait_if_needed.call_count == builder.retry_max_retries + 1
    assert builder.http.get.call_args.args[0] == url
    assert builder.http.get.call_args.kwargs["params"]["filter"]["api_key"] == "nested-param-secret"
    diagnostics = caplog.text + str(error.value) + "".join(traceback.format_exception(error.value))
    for secret in (
        "request-user-secret",
        "request-pass-secret",
        "request-token-secret",
        "exception-header-secret",
        "nested-param-secret",
    ):
        assert secret not in diagnostics
    assert error.value.__suppress_context__


def test_request_recovers_after_transport_failure():
    builder = _make_builder()
    response = MagicMock(status_code=200)
    builder.http.get.side_effect = [requests.exceptions.Timeout("temporary timeout"), response]
    with patch("apibackuper.cmds.project.time.sleep"):
        assert builder._request("https://api.example.com/items") is response
    assert builder.http.get.call_count == 2


def test_request_retries_transient_status_until_success():
    builder = _make_builder()
    builder.rate_limiter = MagicMock()
    responses = [
        MagicMock(status_code=503, headers={}),
        MagicMock(status_code=502, headers={}),
        MagicMock(status_code=200, content=b"saved data"),
    ]
    builder.http.get.side_effect = responses
    with patch("apibackuper.cmds.project.time.sleep"):
        response = builder._request("https://api.example.com/items")
    assert response is responses[-1]
    assert builder.http.get.call_count == 3
    assert builder.rate_limiter.wait_if_needed.call_count == 3


@pytest.mark.parametrize("status, expected_attempts", [(403, 1), (503, 3)])
def test_request_failed_status_raises_instead_of_returning_data(status, expected_attempts, caplog):
    builder = _make_builder()
    builder.http.get.return_value = MagicMock(status_code=status, headers={}, content=b"error body")
    url = "https://api.example.com/items?api_key=status-key-secret"
    with patch("apibackuper.cmds.project.time.sleep"), caplog.at_level(logging.INFO):
        with pytest.raises(RuntimeError, match=f"HTTP {status}") as error:
            builder._request(url)
    assert error.value.status_code == status
    assert builder.http.get.call_count == expected_attempts
    assert builder.http.get.call_args.args[0] == url
    assert "status-key-secret" not in str(error.value) + caplog.text


@pytest.mark.parametrize("method", ["HEAD", "POST"])
def test_request_method_override_keeps_transport_controls(method):
    builder = _make_builder()
    builder.rate_limiter = MagicMock()
    response = MagicMock(status_code=200)
    session_method = getattr(builder.http, method.lower())
    session_method.return_value = response
    with patch("apibackuper.cmds.project.time.sleep"):
        actual = builder._request(
            "https://api.example.com/items", params={"page": 1}, http_mode=method
        )
    assert actual is response
    assert session_method.call_args.kwargs["timeout"] == (30, 120)
    assert session_method.call_args.kwargs["verify"] is True
    assert builder.rate_limiter.wait_if_needed.call_count == 1
