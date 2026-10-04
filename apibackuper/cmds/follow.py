"""Follow-mode key / URL extraction.

Extracted from the four ``follow_mode`` branches inside
``ProjectBuilder.follow``. The original code mixed three concerns:

1. Open the source archive and extract either primary keys
   (``item`` mode), detail URLs (``url`` mode), or computed URLs
   (``prefix`` mode).
2. Open the destination archive (full = ``w``, continue = ``a``).
3. Loop through the keys and fetch each item.

This module owns step 1 — the pure, file-format-driven extraction.
The orchestrator (``ProjectBuilder.follow``) handles the HTTP loop
and destination archive lifecycle.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zipfile import ZipFile

from ..common import get_dict_value


def extract_keys_from_pages(
    source_zip: ZipFile,
    file_list: List[str],
    *,
    data_key: Optional[str],
    field_splitter: str,
    item_key: str,
) -> List[Any]:
    """Extract a flat list of ``item[item_key]`` values from every page.

    Used by the ``item`` and ``prefix`` follow modes, which only need
    the primary key — the URL is constructed either from the configured
    ``follow_pattern`` or from a different field.

    A page with the wrong shape is logged and skipped (matching the
    historical behaviour).
    """
    keys: List[Any] = []
    for fname in file_list:
        with source_zip.open(fname, "r") as tf:
            data = json.load(tf)
        try:
            repeatable_data = (
                get_dict_value(data, data_key, splitter=field_splitter) if data_key else data
            )
            if isinstance(repeatable_data, dict):
                # Page exists but has no list — skip silently.
                continue
            for item in repeatable_data:
                keys.append(item[item_key])
        except (KeyError, TypeError):
            logging.info("Data key: %s not found", data_key)
    return keys


def extract_url_map_from_pages(
    source_zip: ZipFile,
    file_list: List[str],
    *,
    data_key: Optional[str],
    field_splitter: str,
    item_key: str,
    url_key: str,
) -> Dict[Any, str]:
    """Extract ``{item_key: detail_url}`` pairs from every page.

    Used by the ``url`` follow mode, which navigates to a per-item URL
    rather than constructing it from a pattern.
    """
    urls: Dict[Any, str] = {}
    for fname in file_list:
        with source_zip.open(fname, "r") as tf:
            data = json.load(tf)
        try:
            for item in get_dict_value(
                data,
                data_key,
                splitter=field_splitter,
            ):
                item_id = item[item_key]
                urls[item_id] = get_dict_value(
                    item,
                    url_key,
                    splitter=field_splitter,
                )
        except KeyError:
            logging.info("Data key: %s not found", data_key)
    return urls


def compute_pending_targets(
    all_targets: Iterable[Any],
    *,
    dest_zip: Optional[ZipFile],
    full: bool,
) -> Tuple[List[Any], int]:
    """Compute the pending set and the count of already-done items.

    In ``full`` mode, every target is pending (count = 0).
    In ``continue`` mode, the items already in ``dest_zip`` are
    subtracted from ``all_targets`` (returns the diff + the count
    of already-done items).

    The orchestrator uses ``count_done`` to seed its progress-bar
    ``initial`` value so the user sees accurate counts when resuming.
    """
    if full or dest_zip is None:
        return list(all_targets), 0
    existing = set(dest_zip.namelist())
    return [t for t in all_targets if _archive_name(t) not in existing], len(existing)


def _archive_name(target: Any) -> str:
    """How the orchestrator names an entry in the destination zip."""
    return f"{target}.json"


__all__ = [
    "extract_keys_from_pages",
    "extract_url_map_from_pages",
    "compute_pending_targets",
]
