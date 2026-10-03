# -*- coding: utf-8 -*-
"""Utility functions for project operations"""
import csv
from typing import Dict, List, Any, Optional, Iterable
from urllib.parse import urlparse, urlencode

from ..constants import PARAM_SPLITTER


# Names commonly used to carry credentials that must never be written to logs.
# Matched case-insensitively against keys in headers and query params.
_SENSITIVE_KEY_NAMES = frozenset({
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
})

_REDACTED = "***REDACTED***"


def _is_sensitive_key(key: Any) -> bool:
    """True when ``key`` looks like it carries credentials."""
    try:
        name = str(key).lower()
    except Exception:
        return False
    for sensitive in _SENSITIVE_KEY_NAMES:
        if sensitive in name:
            return True
    return False


def redact_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a copy of ``headers`` with sensitive values replaced.

    Used before logging request/response headers so Authorization and friends
    never land in the log file (§5.1 of the 2026-10 analysis report).
    """
    if not headers:
        return {}
    redacted = {}
    for k, v in headers.items():
        if _is_sensitive_key(k):
            redacted[k] = _REDACTED
        else:
            redacted[k] = v
    return redacted


def redact_params(params: Any) -> Any:
    """Return a copy of ``params`` (dict) with sensitive keys redacted.

    Strings and other types are returned unchanged so the helper is safe to
    call on whatever the caller has.
    """
    if not isinstance(params, dict):
        return params
    redacted = {}
    for k, v in params.items():
        if _is_sensitive_key(k):
            redacted[k] = _REDACTED
        else:
            redacted[k] = v
    return redacted


def load_file_list(filename: str, encoding: str = "utf8") -> List[str]:
    """Reads file and returns list of strings as list"""
    flist = []
    with open(filename, "r", encoding=encoding) as fobj:
        for line in fobj:
            flist.append(line.rstrip())
    return flist


def load_csv_data(filename: str, key: str, encoding: str = "utf8", delimiter: str = ";") -> Dict[str, Dict[str, str]]:
    """Reads CSV file and returns list records as array of dicts"""
    flist = {}
    with open(filename, "r", encoding=encoding) as fobj:
        reader = csv.DictReader(fobj, delimiter=delimiter)
        for row in reader:
            flist[row[key]] = row
    return flist


def _url_replacer(url: str, params: Dict[str, Any], query_mode: bool = False) -> str:
    """Replaces URL params.

    In query mode, uses '?' as the query initiator and '&' as the separator.
    In params (non-query) mode, uses PARAM_SPLITTER (';') for both initiator
    and separator, producing URLs like ``url;key=val;key2=val2``.

    P2.23: in query mode, key/value pairs are now URL-encoded via
    ``urllib.parse.urlencode`` (with ``quote_via=quote``) so values containing
    ``&``, ``=``, ``#`` or whitespace no longer corrupt or extend the query.
    Non-query mode (path-param style with ``;``) keeps raw values because the
    delimiter is the API contract, not the URL grammar.
    """
    parsed = urlparse(url)
    if query_mode:
        # ``urlencode`` percent-encodes both keys and values.
        query_string = urlencode(params, doseq=True)
        return parsed.geturl() + "?" + query_string
    splitter = PARAM_SPLITTER
    finalparams = []
    for key, value in params.items():
        finalparams.append("%s=%s" % (str(key), str(value)))
    return parsed.geturl() + splitter + splitter.join(finalparams)

