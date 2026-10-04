"""Per-record export pipeline.

Extracted from ``ProjectBuilder.export`` so the filtering / projection /
serialisation logic can be unit-tested in isolation. The orchestrator in
``ProjectBuilder.export`` opens the storage backend, iterates over its
files, and calls :func:`process_record` for each parsed JSON payload.

The function returns a list of records that match ``--where`` and have
been projected via ``--fields``. The caller is responsible for writing
them to its destination (jsonl, gzip, zstd, parquet).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable, List, Optional

from ..common import get_dict_value
from .where_filter import match_where, select_fields


def process_record(
    data: Any,
    *,
    data_key: Optional[str],
    field_splitter: str = ".",
    fields: Optional[Iterable[str]] = None,
    where: Optional[Callable[[Any], bool]] = None,
    record_filter: Optional[Callable[[Any], bool]] = None,
) -> List[Any]:
    """Filter and project one parsed JSON payload from storage.

    The pipeline mirrors what ``ProjectBuilder.export`` did inline for each
    storage backend (zip details, sqlite, zip storage): extract items via
    ``data_key`` if set, otherwise treat the payload itself as a list; apply
    ``--where``; project to ``--fields``; accumulate matched records.

    Parameters
    ----------
    data
        Parsed JSON payload from a single page or detail file.
    data_key
        Dotted path to the records array inside the payload, e.g.
        ``"results.items"``. When ``None`` or the key is not present, the
        payload itself is iterated (works for top-level lists and bare dicts).
    fields
        Iterable of dotted paths to project the matched records to. When
        ``None`` or empty, returns the matched records unchanged.
    where
        Predicate over a single record that returns ``True`` when the record
        should be included. ``None`` accepts everything.
    record_filter
        Optional alternative predicate (used by the ``follow``-mode path,
        which checks a different field before the where-filter).

    Returns
    -------
    list of records that survived the pipeline.
    """
    if data is None:
        return []

    if record_filter and not record_filter(data):
        return []

    # Resolve the list of candidate items.
    if data_key:
        items = get_dict_value(data, data_key, splitter=field_splitter)
        if items is None:
            return []
        # A single dict value is treated as a one-item list.
        if isinstance(items, dict):
            items = [items]
    else:
        items = data

    if not isinstance(items, list):
        # Single scalar / dict — wrap as one record so the user gets it.
        items = [items]

    result: List[Any] = []
    for item in items:
        if where is not None and not where(item):
            continue
        projected = select_fields(item, list(fields) if fields else None, splitter=field_splitter)
        result.append(projected)
    return result


def serialize_record(record: Any) -> str:
    """Render one record as a JSON string with the trailing newline.

    Mirrors the historical inline format so a jsonl file diff is unchanged.
    """
    return json.dumps(record, ensure_ascii=False) + "\n"


__all__ = ["process_record", "serialize_record", "match_where"]
