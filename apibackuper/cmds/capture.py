"""Exchange records and original bodies saved beside each page.

With response capture enabled, a run stores in the page's generation prefix:

- ``exchange_N.json``: request method, URL, headers and body; response status,
  reason, final URL, headers, content type, SHA-256 and length; fetch time,
  elapsed time, apibackuper version and run ID. Credentials are redacted.
- ``raw_N.<ext>``: the response body as received, when it differs from the
  saved page (XML or HTML responses) or when ``raw_body: always`` is set.

Neither name starts with ``page_``, so page listings, export and resume ignore
them; the fixity manifest lists them with the pages.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from .. import __version__
from .utils import _REDACTED, redact_headers, redact_params, redact_text, redact_url

CAPTURE_PREFIXES = ("exchange_", "raw_")
RAW_EXTENSIONS = {"json": "json", "xml": "xml", "html": "html"}


def is_capture_member(name: str) -> bool:
    return name.rsplit("/", 1)[-1].startswith(CAPTURE_PREFIXES)


def exchange_name(prefix: str, page: int) -> str:
    return f"{prefix}exchange_{page}.json"


def raw_name(prefix: str, page: int, resp_type: str) -> str:
    return f"{prefix}raw_{page}.{RAW_EXTENSIONS.get(resp_type, 'bin')}"


def _safe_url(url: Optional[str]) -> Optional[str]:
    return redact_url(url) if url else url


def _request_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, bytes):
        body = body.decode("utf8", "replace")
    try:
        return redact_params(json.loads(body))
    except (TypeError, ValueError):
        return redact_text(body)


def build_exchange(
    response,
    *,
    page: int,
    run_id: Optional[str],
    fetched_at: Optional[str],
    raw_member: Optional[str],
) -> Dict[str, Any]:
    """Describe one HTTP exchange without credentials."""
    request = getattr(response, "request", None)
    content = response.content or b""
    elapsed = getattr(response, "elapsed", None)
    record = {
        "page": page,
        "run_id": run_id,
        "apibackuper_version": __version__,
        "fetched_at": fetched_at,
        "elapsed_seconds": elapsed.total_seconds() if elapsed is not None else None,
        "request": {
            "method": getattr(request, "method", None),
            "url": _safe_url(getattr(request, "url", None) or response.url),
            "headers": redact_headers(dict(getattr(request, "headers", None) or {})),
            "body": _request_body(getattr(request, "body", None)),
        },
        "response": {
            "status": response.status_code,
            "reason": response.reason,
            "url": _safe_url(response.url),
            "headers": redact_headers(dict(response.headers or {})),
            "content_type": (response.headers or {}).get("Content-Type"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "length": len(content),
        },
        "raw_member": raw_member,
    }
    record["redacted"] = _REDACTED in json.dumps(record, default=str)
    return record


def save_capture(project, session, page: int, response, fetched_at: Optional[str]) -> None:
    """Store the raw body and exchange record of a page before the page itself."""
    raw_member = None
    mode = project.capture_raw_body
    if mode == "always" or (mode == "auto" and project.resp_type != "json"):
        raw_member = raw_name(session.prefix, page, project.resp_type)
        session.backend.save_object(raw_member, response.content or b"")
    if project.capture_metadata:
        record = build_exchange(
            response,
            page=page,
            run_id=session.run_id or None,
            fetched_at=fetched_at,
            raw_member=raw_member,
        )
        encoded = json.dumps(record, ensure_ascii=False, indent=2, default=str).encode("utf8")
        session.backend.save_object(exchange_name(session.prefix, page), encoded)


__all__ = [
    "CAPTURE_PREFIXES",
    "build_exchange",
    "exchange_name",
    "is_capture_member",
    "raw_name",
    "save_capture",
]
