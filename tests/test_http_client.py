"""Tests for the extracted ``cmds.http_client`` module.

The module owns request-building, retry-kwargs filtering, and actionable
error wrapping for ``ProjectBuilder._single_request``. These tests cover
each helper in isolation so changes there don't have to round-trip
through the full ProjectBuilder.
"""
import logging
from unittest.mock import MagicMock

import pytest
import requests as requests_lib

from apibackuper.cmds.http_client import (
    build_request_kwargs,
    build_retry_kwargs,
    wrap_request_exception,
)


class TestBuildRequestKwargs:
    def test_get_no_flat_params(self):
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="GET",
            url="https://api.example.com/items",
            params={"page": 1},
            flatten=None,
            headers={"X-Custom": "v"},
            verify_ssl=True,
            connect_timeout=5,
            read_timeout=60,
            allow_redirects=True,
        )
        assert method == "get"
        assert kwargs["headers"] == {"X-Custom": "v"}
        assert kwargs["params"] == {"page": 1}
        assert kwargs["verify"] is True
        assert kwargs["timeout"] == (5, 60)
        assert kwargs["allow_redirects"] is True
        assert query is None

    def test_get_redacts_token_in_log_safe(self):
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="GET",
            url="https://api.example.com/items",
            params={"page": 1, "token": "abc123"},
            flatten=None,
            headers=None,
            verify_ssl=True,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=True,
        )
        assert "token" in log_safe
        assert "abc123" not in log_safe
        assert "***REDACTED***" in log_safe
        # Real params retain the token.
        assert kwargs["params"]["token"] == "abc123"

    def test_get_with_flat_params_url_encodes(self):
        flatten = {"q": "a&b=c", "page": 1}
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="GET",
            url="https://api.example.com/items",
            params={"q": "a&b=c", "page": 1},
            flatten=flatten,
            headers=None,
            verify_ssl=True,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=True,
        )
        # urlencoded escapes & as %26 and = as %3D in the query string.
        assert query.startswith("q=")
        assert "a%26b%3Dc" in query
        assert "page=1" in query

    def test_get_with_flat_params_redacts_token(self):
        flatten = {"token": "secret", "page": 1}
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="GET",
            url="https://api.example.com/items",
            params={"token": "secret", "page": 1},
            flatten=flatten,
            headers=None,
            verify_ssl=True,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=True,
        )
        assert "secret" not in log_safe
        # Real query keeps the token (we redact only the log-safe URL).
        assert "secret" in query

    def test_get_with_flat_params_stringifies_non_string_values(self):
        # Real configs often have ints/floats as page numbers. The helper
        # must not crash on ``int.replace``.
        flatten = {"page": 1, "size": 25}
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="GET",
            url="https://api.example.com/items",
            params={"page": 1, "size": 25},
            flatten=flatten,
            headers=None,
            verify_ssl=True,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=True,
        )
        assert "page=" in query
        assert "size=" in query

    def test_post_redacts_params_and_headers(self):
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="POST",
            url="https://api.example.com/items",
            params={"Authorization": "Bearer ey", "data": "ok"},
            flatten=None,
            headers={"Authorization": "Bearer secret"},
            verify_ssl=True,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=True,
        )
        assert method == "post"
        assert kwargs["json"] == {"Authorization": "Bearer ey", "data": "ok"}
        assert "Bearer secret" not in log_safe
        assert "Bearer ey" not in log_safe

    def test_no_headers_attr_does_not_crash(self):
        (method, kwargs, log_safe), query = build_request_kwargs(
            http_mode="POST",
            url="https://api.example.com/items",
            params={"x": 1},
            flatten=None,
            headers=None,
            verify_ssl=False,
            connect_timeout=30,
            read_timeout=120,
            allow_redirects=False,
        )
        assert "headers" not in kwargs
        assert kwargs["verify"] is False
        assert kwargs["allow_redirects"] is False


class TestBuildRetryKwargs:
    def test_filters_params_and_json(self):
        original = {
            "verify": True,
            "params": {"page": 1},
            "json": {"data": "ok"},
            "timeout": (5, 60),
            "headers": {"X-Auth": "tok"},
        }
        out = build_retry_kwargs(original, headers={"X-Auth": "new"})
        assert "params" not in out
        assert "json" not in out
        assert out["verify"] is True
        assert out["timeout"] == (5, 60)
        assert out["headers"] == {"X-Auth": "new"}

    def test_replaces_headers(self):
        original = {"verify": True, "headers": {"X-Auth": "old"}}
        out = build_retry_kwargs(original, headers={"X-Auth": "new"})
        assert out["headers"] == {"X-Auth": "new"}

    def test_no_params_or_json_no_change(self):
        original = {"verify": True, "timeout": (5, 60)}
        out = build_retry_kwargs(original, headers={"X": "v"})
        assert out == {"verify": True, "timeout": (5, 60), "headers": {"X": "v"}}


class TestWrapRequestException:
    def _http_error(self, status_code):
        """Build a ``requests.HTTPError`` carrying a fake response."""
        response = MagicMock()
        response.status_code = status_code
        return requests_lib.exceptions.HTTPError("boom", response=response)

    def test_timeout_includes_actionable_suggestion(self):
        wrapped = wrap_request_exception(
            requests_lib.exceptions.Timeout("slow"),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        assert isinstance(wrapped, RuntimeError)
        msg = str(wrapped)
        assert "timeout" in msg.lower()
        assert "Increase timeout values" in msg
        assert "5" in msg and "60" in msg
        assert "10" in msg and "120" in msg

    def test_ssl_error_suggests_disabling_verification(self):
        wrapped = wrap_request_exception(
            requests_lib.exceptions.SSLError("bad cert"),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "SSL" in msg or "certificate" in msg.lower()
        assert "verify_ssl" in msg

    def test_connection_error_suggests_checking_network(self):
        wrapped = wrap_request_exception(
            requests_lib.exceptions.ConnectionError("refused"),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "connect" in msg.lower() or "Failed to connect" in msg
        assert "internet" in msg.lower() or "firewall" in msg.lower()

    def test_http_error_401_suggests_auth_check(self):
        wrapped = wrap_request_exception(
            self._http_error(401),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "401" in msg
        assert "auth" in msg.lower() or "credentials" in msg.lower()

    def test_http_error_403_suggests_permissions(self):
        wrapped = wrap_request_exception(
            self._http_error(403),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "403" in msg
        assert "permission" in msg.lower()

    def test_http_error_404_suggests_url_check(self):
        wrapped = wrap_request_exception(
            self._http_error(404),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "404" in msg
        assert "url" in msg.lower() or "endpoint" in msg.lower()

    def test_http_error_429_suggests_increasing_delay(self):
        wrapped = wrap_request_exception(
            self._http_error(429),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "429" in msg
        assert "rate" in msg.lower() or "delay" in msg.lower()

    def test_http_error_500_suggests_server_retry(self):
        wrapped = wrap_request_exception(
            self._http_error(500),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "500" in msg
        assert "server" in msg.lower() or "try again" in msg.lower()

    def test_unexpected_exception_still_raises_runtimeerror(self):
        wrapped = wrap_request_exception(
            ValueError("bad value"),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile=None,
        )
        assert isinstance(wrapped, RuntimeError)
        assert "Unexpected error" in str(wrapped)
        assert "ValueError" in str(wrapped)
        # logfile hint defaults to "apibackuper.log"
        assert "apibackuper.log" in str(wrapped)

    def test_request_exception_with_no_response(self):
        wrapped = wrap_request_exception(
            requests_lib.exceptions.RequestException("boom"),
            url="https://api.example.com/items",
            connect_timeout=5,
            read_timeout=60,
            default_delay=0.5,
            logfile="apibackuper.log",
        )
        msg = str(wrapped)
        assert "https://api.example.com/items" in msg