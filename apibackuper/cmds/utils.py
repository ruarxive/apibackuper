# -*- coding: utf-8 -*-
"""Utility functions for project operations"""
import csv
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from ..constants import PARAM_SPLITTER

# Names commonly used to carry credentials that must never be written to logs.
# Matched case-insensitively against keys in headers and query params.
_SENSITIVE_KEY_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "x-auth",
        "x-auth-token",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "passwd",
        "secret",
        "cookie",
        "credential",
    }
)

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
    return redact_params(headers) if headers else {}


def redact_params(params: Any) -> Any:
    """Copy nested parameter containers, replacing sensitive dictionary values.

    Preserve container types and leave scalar values untouched. Actual request
    parameters are never modified while preparing their log representation.
    """
    if isinstance(params, dict):
        return {
            key: _REDACTED if _is_sensitive_key(key) else redact_params(value)
            for key, value in params.items()
        }
    if isinstance(params, list):
        return [redact_params(value) for value in params]
    if isinstance(params, tuple):
        return tuple(redact_params(value) for value in params)
    return params


def redact_url(url: str) -> str:
    """Remove URL credentials from diagnostics without altering real requests."""
    try:
        parsed = urlsplit(url)
        netloc = parsed.netloc
        if "@" in netloc:
            netloc = _REDACTED + "@" + netloc.rsplit("@", 1)[1]
        query = urlencode(
            [
                (key, _REDACTED if _is_sensitive_key(key) else value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            ],
            doseq=True,
        )
        return urlunsplit(parsed._replace(netloc=netloc, query=query))
    except ValueError:
        # Malformed URLs can still contain credentials; fail closed in logs.
        return "[REDACTED URL]"


_URL_IN_TEXT = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>\"']+", re.IGNORECASE)
_CREDENTIAL_IN_TEXT = re.compile(
    r"(?P<key>[\"']?[\w.-]*(?:"
    + "|".join(re.escape(key) for key in sorted(_SENSITIVE_KEY_NAMES))
    + r")[\w.-]*[\"']?\s*[:=]\s*)"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"(?:(?:Bearer|Basic|Token|Digest)\s+)?[^\s&;,\)\]}]+)",
    re.IGNORECASE,
)


def redact_text(value: Any) -> str:
    """Sanitize URLs and credential assignments in arbitrary exception text."""
    text = _URL_IN_TEXT.sub(lambda match: redact_url(match.group()), str(value))
    return _CREDENTIAL_IN_TEXT.sub(lambda match: match.group("key") + _REDACTED, text)


def append_query(url: str, params: Any) -> str:
    """Append query parameters, retaining existing pairs and URL fragments.

    ``params`` accepts a mapping, a sequence of pairs or an encoded query string,
    allowing flat and regular request construction to share URL handling.
    """
    if not params:
        return url
    parsed = urlsplit(url)
    extra = params if isinstance(params, str) else urlencode(params, doseq=True)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    pairs.extend(parse_qsl(extra, keep_blank_values=True))
    return urlunsplit(parsed._replace(query=urlencode(pairs, doseq=True)))


def load_file_list(filename: str, encoding: str = "utf8") -> List[str]:
    """Reads file and returns list of strings as list"""
    flist = []
    with open(filename, "r", encoding=encoding) as fobj:
        for line in fobj:
            flist.append(line.rstrip())
    return flist


def load_csv_data(
    filename: str, key: str, encoding: str = "utf8", delimiter: str = ";"
) -> Dict[str, Dict[str, str]]:
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

    In query mode, key/value pairs are URL-encoded via
    ``urllib.parse.urlencode`` so values containing
    ``&``, ``=``, ``#`` or whitespace no longer corrupt or extend the query.
    Non-query mode (path-param style with ``;``) keeps raw values because the
    delimiter is the API contract, not the URL grammar.
    """
    if query_mode:
        if not params and not urlsplit(url).query:
            # Preserve the historical empty-query result for this public helper.
            parsed = urlsplit(url)
            base = urlunsplit(parsed._replace(fragment="")) + "?"
            return base + ("#" + parsed.fragment if parsed.fragment else "")
        return append_query(url, params)
    parsed = urlparse(url)
    splitter = PARAM_SPLITTER
    finalparams = []
    for key, value in params.items():
        finalparams.append("%s=%s" % (str(key), str(value)))
    return parsed.geturl() + splitter + splitter.join(finalparams)
