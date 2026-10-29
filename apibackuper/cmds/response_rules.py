"""Declarative response rules and rate-limit header waits.

``request.response_rules`` is an ordered list. The first rule whose conditions
all match a response decides what happens to it:

- ``retry``: retry under the retry policy, even for a 2xx response;
- ``fail``: stop with an error, without retrying;
- ``missing``: the object is gone; follow and file downloads record it and go
  on, a page request fails;
- ``accept``: treat the response as successful, even with a non-2xx status.

Conditions are ``status`` (a code, a list of codes, or a class such as
``"4xx"``), ``body_key`` with an optional ``body_value`` (a dotted path in a
JSON body) and ``content_type`` (a case-insensitive substring of the
``Content-Type`` header). A rule needs at least one condition.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from ..common import get_dict_value

ACTIONS = ("retry", "fail", "missing", "accept")
CONDITIONS = ("status", "body_key", "content_type")
# Statuses treated as ``missing`` when no rule matches (follow and files).
DEFAULT_MISSING_STATUSES = (404, 410)
# Numeric header values at least this large are Unix timestamps, not seconds.
_UNIX_TIME_THRESHOLD = 1_000_000_000


def validate_rules(rules: Any) -> List[str]:
    """Return error messages for a ``request.response_rules`` value."""
    if rules is None:
        return []
    if not isinstance(rules, list):
        return ["request.response_rules must be a list"]
    errors = []
    for index, rule in enumerate(rules):
        where = f"request.response_rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{where} must be a mapping")
            continue
        if rule.get("action") not in ACTIONS:
            errors.append(f"{where}.action must be one of {', '.join(ACTIONS)}")
        if not any(name in rule for name in CONDITIONS):
            errors.append(f"{where} needs at least one of {', '.join(CONDITIONS)}")
        if "status" in rule and not _valid_status(rule["status"]):
            errors.append(f"{where}.status must be a code, a list of codes or a class like 4xx")
        if "body_value" in rule and "body_key" not in rule:
            errors.append(f"{where}.body_value requires body_key")
    return errors


def _valid_status(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 100 <= value <= 599
    if isinstance(value, str):
        return bool(re.fullmatch(r"[1-5](xx|[0-9]{2})", value.lower()))
    if isinstance(value, list):
        return bool(value) and all(_valid_status(item) for item in value)
    return False


def _status_matches(expected: Any, status: int) -> bool:
    if isinstance(expected, list):
        return any(_status_matches(item, status) for item in expected)
    if isinstance(expected, str):
        expected = expected.lower()
        if expected.endswith("xx"):
            return str(status)[0] == expected[0]
        return status == int(expected)
    return status == expected


def matches(rule: Dict[str, Any], response, splitter: str = ".") -> bool:
    """Return True when every condition of ``rule`` holds for ``response``."""
    if "status" in rule and not _status_matches(rule["status"], response.status_code):
        return False
    if "content_type" in rule:
        content_type = (response.headers or {}).get("Content-Type") or ""
        if str(rule["content_type"]).lower() not in content_type.lower():
            return False
    if "body_key" in rule:
        try:
            body = response.json()
        except ValueError:
            return False
        value = get_dict_value(body, rule["body_key"], splitter=splitter)
        if "body_value" in rule:
            return value == rule["body_value"]
        return value is not None
    return True


def action_for(rules: List[Dict[str, Any]], response, splitter: str = ".") -> Optional[str]:
    """Return the action of the first matching rule, or None."""
    for rule in rules:
        if matches(rule, response, splitter=splitter):
            return rule["action"]
    return None


def header_wait(response, headers: List[str]) -> Optional[int]:
    """Seconds to wait from the first configured header present, or None.

    Values may be seconds, a Unix timestamp (``X-RateLimit-Reset``) or an
    HTTP date (``Retry-After``).
    """
    if response is None:
        return None
    for name in headers:
        value = (response.headers or {}).get(name)
        if not value:
            continue
        try:
            number = float(value)
        except ValueError:
            number = None
        now = datetime.now(timezone.utc)
        if number is not None:
            if number >= _UNIX_TIME_THRESHOLD:
                return max(0, math.ceil(number - now.timestamp()))
            return max(0, math.ceil(number))
        try:
            moment = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return max(0, math.ceil((moment - now).total_seconds()))
    return None


__all__ = [
    "ACTIONS",
    "DEFAULT_MISSING_STATUSES",
    "action_for",
    "header_wait",
    "matches",
    "validate_rules",
]
