"""Filter expressions for ``export --where``.

Extracted from ``cmds/project.py`` so the parsing and matching logic can be
unit-tested in isolation. Each function is pure (no ``self``) and is the
authoritative implementation that ``ProjectBuilder._parse_where`` and
``ProjectBuilder._match_where`` delegate to.
"""
from typing import Any, Dict, List, Optional

from ..common import get_dict_value


_OPERATORS = ["<=", ">=", "!=", "==", ">", "<"]


def parse_where(
    where: Optional[str],
    splitter: str = ".",
) -> Optional[Dict[str, Any]]:
    """Parse a ``--where`` expression into a structured condition.

    Examples:

        ``"count > 10"``       -> ``{"field": "count", "op": ">", "value": 10}``
        ``"updated_at >= 2024-01-01"`` -> ``{"field": "updated_at", "op": ">=", "value": "2024-01-01"}``
        ``"foo.bar != 3.14"``  -> ``{"field": "foo.bar", "op": "!=", "value": 3.14}``

    Returns ``None`` for an empty string or an expression without a
    recognised operator.
    """
    if not where:
        return None
    for op in _OPERATORS:
        if op in where:
            left, right = where.split(op, 1)
            field = left.strip()
            value = right.strip().strip('"').strip("'")
            try:
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                # Leave the value as a string — useful for ISO dates etc.
                pass
            return {"field": field, "op": op, "value": value, "splitter": splitter}
    return None


def match_where(
    item: Dict[str, Any],
    condition: Optional[Dict[str, Any]],
) -> bool:
    """Return ``True`` iff ``item`` satisfies ``condition``.

    ``condition`` is the dict returned by :func:`parse_where`. ``field`` is
    resolved with the same dotted-path splitter used elsewhere in the
    codebase (default ``"."``).
    """
    if not condition:
        return True
    field = condition["field"]
    op = condition["op"]
    value = condition["value"]
    splitter = condition.get("splitter", ".")
    actual = get_dict_value(item, field, splitter=splitter)
    if actual is None:
        return False
    try:
        if op == "==":
            return actual == value
        if op == "!=":
            return actual != value
        if op == ">":
            return actual > value
        if op == "<":
            return actual < value
        if op == ">=":
            return actual >= value
        if op == "<=":
            return actual <= value
    except TypeError:
        # Comparison between incompatible types — treat as no match.
        return False
    return False


def select_fields(
    item: Dict[str, Any],
    fields: Optional[List[str]],
    splitter: str = ".",
) -> Dict[str, Any]:
    """Project ``item`` to the dotted paths in ``fields``.

    Returns the original ``item`` (not a copy) when ``fields`` is empty or
    ``None`` — callers may rely on the passthrough to skip the projection
    step entirely.
    """
    if not fields:
        return item
    selected: Dict[str, Any] = {}
    for field in fields:
        value = get_dict_value(item, field, splitter=splitter)
        # Falsy values (0, False, "") are valid exports — keep them.
        if value is not None:
            selected[field] = value
    return selected


__all__ = ["parse_where", "match_where", "select_fields"]