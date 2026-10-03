"""HTTP request building and error wrapping for apibackuper.

Extracted from ``cmds/project.py`` (``ProjectBuilder._single_request``) so
the request-construction logic and the error-message templates can be
unit-tested in isolation, and so future changes (e.g. async via httpx)
touch one file instead of a 3,000-line god module.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

import requests

from .utils import _is_sensitive_key, _REDACTED, redact_headers, redact_params


def build_request_kwargs(
    *,
    http_mode: str,
    url: str,
    params: Dict[str, Any],
    flatten: Optional[Dict[str, str]],
    headers: Optional[Dict[str, str]],
    verify_ssl: bool,
    connect_timeout: float,
    read_timeout: float,
    allow_redirects: bool,
) -> tuple:
    """Build ``(method, kwargs_for_session_method, log_safe_url)``.

    The caller is responsible for invoking the returned method on its
    session. ``log_safe_url`` is the URL string we want to write to the
    log file — redaction of ``token=``, ``api_key=``, etc. is applied
    here so the actual HTTP request never carries the redacted token.

    Returns ``(method, kwargs, log_safe_url)`` where ``method`` is the
    attribute name on a ``requests.Session`` (``"get"`` or ``"post"``).
    """
    request_kwargs: Dict[str, Any] = {
        "verify": verify_ssl,
        "timeout": (connect_timeout, read_timeout),
        "allow_redirects": allow_redirects,
    }

    log_safe_url = url

    if http_mode == "GET":
        if flatten:
            # P2.21: redact sensitive keys before logging.
            redacted_flatten = {
                k: (_REDACTED if _is_sensitive_key(k)
                     else value.replace("'", '"').replace("True", "true"))
                for k, value in flatten.items()
            }
            # P2.23: URL-encode the query so values with ``&``, ``=``, ``#``
            # or whitespace do not corrupt or extend the query.
            query_string = urlencode(redacted_flatten, doseq=True)
            actual_query_string = urlencode(
                {k: v.replace("'", '"').replace("True", "true")
                 for k, v in flatten.items()},
                doseq=True,
            )
            log_safe_url = url + "?" + query_string
            if headers:
                request_kwargs["headers"] = headers
            return ("get", request_kwargs, log_safe_url), actual_query_string
        # Branch without flat_params
        log_safe_url = f"{url} params={redact_params(params)}"
        if headers:
            request_kwargs["headers"] = headers
        request_kwargs["params"] = params
        return ("get", request_kwargs, log_safe_url), None

    # POST
    log_safe_url = (
        f"{url} params={redact_params(params)} "
        f"headers={redact_headers(headers)}"
    )
    if headers:
        request_kwargs["headers"] = headers
    request_kwargs["json"] = params
    return ("post", request_kwargs, log_safe_url), None


def build_retry_kwargs(
    request_kwargs: Dict[str, Any],
    headers: Dict[str, str],
) -> Dict[str, Any]:
    """Build retry kwargs without the body-bearing keys.

    ``requests`` raises ``TypeError: got multiple values for keyword
    argument 'params'`` when ``params`` appears both as a spread kwarg
    AND as a separate ``params=...`` argument. This helper produces a
    kwargs dict that is safe to spread alongside an explicit
    ``params=...`` (P1.13).
    """
    retry_kwargs = {
        k: v for k, v in request_kwargs.items()
        if k not in ("params", "json")
    }
    retry_kwargs["headers"] = headers
    return retry_kwargs


def wrap_request_exception(
    exc: Exception,
    *,
    url: str,
    connect_timeout: float,
    read_timeout: float,
    default_delay: float,
    logfile: Optional[str],
) -> RuntimeError:
    """Turn a low-level ``requests`` exception into an actionable ``RuntimeError``.

    The user sees a multi-line, suggestion-rich message in the log file;
    the original exception is chained via ``raise ... from exc``.
    """
    log_file_hint = logfile or "apibackuper.log"

    if isinstance(exc, requests.exceptions.Timeout):
        timeout_info = (
            f"Connect timeout: {connect_timeout}s, "
            f"Read timeout: {read_timeout}s"
        )
        error_msg = (
            f"Request timeout while connecting to {url}\n"
            f"  Current timeout settings: {timeout_info}\n"
            f"  Error details: {str(exc)}\n"
            "  Suggestions:\n"
            f"    - Increase timeout values in [request] section:\n"
            f"      connect_timeout = {connect_timeout * 2}\n"
            f"      read_timeout = {read_timeout * 2}\n"
            "    - Check network connectivity and API server status\n"
            "    - Verify the URL is correct and accessible"
        )
        logging.error("Request timeout for URL %s: %s", url, exc)
        return RuntimeError(error_msg)

    if isinstance(exc, requests.exceptions.SSLError):
        error_msg = (
            f"SSL certificate verification failed for {url}\n"
            f"  Error details: {str(exc)}\n"
            "  Suggestions:\n"
            "    - If this is a trusted server, disable SSL verification in [request] section:\n"
            "      verify_ssl = False\n"
            "    - Or provide a path to a trusted certificate bundle:\n"
            "      verify_ssl = /path/to/certificate.pem\n"
            "    - Update your system's certificate store\n"
            "    - Check if the server's certificate has expired"
        )
        logging.error("SSL error for URL %s: %s", url, exc)
        return RuntimeError(error_msg)

    if isinstance(exc, requests.exceptions.ConnectionError):
        error_msg = (
            f"Failed to connect to {url}\n"
            f"  Error details: {str(exc)}\n"
            "  Suggestions:\n"
            "    - Check your internet connection\n"
            f"    - Verify the URL is correct: {url}\n"
            "    - Check if the API server is running and accessible\n"
            "    - If using a proxy, verify proxy settings in [request] section\n"
            "    - Check firewall settings"
        )
        logging.error("Connection error for URL %s: %s", url, exc)
        return RuntimeError(error_msg)

    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = (
            exc.response.status_code
            if hasattr(exc, "response") and exc.response
            else "unknown"
        )
        error_msg = (
            f"HTTP error {status_code} for {url}\n"
            f"  Error details: {str(exc)}\n"
        )
        if hasattr(exc, "response") and exc.response:
            error_msg += f"  Response status: {exc.response.status_code}\n"
            if exc.response.status_code == 401:
                error_msg += (
                    "  Suggestions:\n"
                    "    - Check authentication credentials in [auth] section\n"
                    "    - Verify API key or token is valid and not expired\n"
                    "    - Check if authentication type matches API requirements"
                )
            elif exc.response.status_code == 403:
                error_msg += (
                    "  Suggestions:\n"
                    "    - Check if your account has permission to access this resource\n"
                    "    - Verify API key has required permissions\n"
                    "    - Check rate limiting or quota restrictions"
                )
            elif exc.response.status_code == 404:
                error_msg += (
                    "  Suggestions:\n"
                    f"    - Verify the URL is correct: {url}\n"
                    "    - Check if the API endpoint exists\n"
                    "    - Review API documentation for correct endpoint path"
                )
            elif exc.response.status_code == 429:
                error_msg += (
                    "  Suggestions:\n"
                    "    - You are being rate limited. Wait before retrying\n"
                    "    - Configure rate limiting in [rate_limit] section\n"
                    "    - Increase delays between requests in [project] section:\n"
                    f"      default_delay = {default_delay * 2}"
                )
            elif exc.response.status_code >= 500:
                error_msg += (
                    "  Suggestions:\n"
                    "    - This is a server error. The API may be temporarily unavailable\n"
                    "    - Wait a few minutes and try again\n"
                    "    - Check API status page if available\n"
                    "    - Increase retry settings in [project] section"
                )
        logging.error("HTTP error for URL %s: %s", url, exc)
        return RuntimeError(error_msg)

    if isinstance(exc, requests.exceptions.RequestException):
        error_msg = (
            f"Request failed for {url}\n"
            f"  Error details: {str(exc)}\n"
            "  Suggestions:\n"
            "    - Check network connectivity\n"
            "    - Verify URL and request parameters\n"
            "    - Review configuration settings\n"
            f"    - Check logs for more details: {log_file_hint}"
        )
        logging.error("Request error for URL %s: %s", url, exc)
        return RuntimeError(error_msg)

    # ValueError / RuntimeError / IOError
    error_msg = (
        f"Unexpected error while requesting {url}\n"
        f"  Error details: {str(exc)}\n"
        f"  Error type: {type(exc).__name__}\n"
        "  Suggestions:\n"
        f"    - Check logs for more details: {log_file_hint}\n"
        "    - Verify configuration is correct\n"
        "    - Try running with --verbose flag for more information"
    )
    logging.error(
        "Unexpected error in request to %s: %s", url, exc,
        exc_info=True,
    )
    return RuntimeError(error_msg)


__all__ = [
    "build_request_kwargs",
    "build_retry_kwargs",
    "wrap_request_exception",
]