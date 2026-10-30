# -*- coding: utf-8 -*-
"""Find pagination parameters of a live endpoint by sending a few requests."""
import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

PAGE_PARAMS = ("page", "p", "pageNumber", "page_number", "pageNo", "pageIndex")
OFFSET_PARAMS = ("offset", "skip", "start", "from")
SIZE_PARAMS = ("per_page", "limit", "page_size", "pageSize", "size", "perPage", "count", "rows")
# Page size requested to find out whether the API caps it.
LARGE_PAGE = 100

# ``fetch(extra)`` repeats the first request with ``extra`` parameters added
# and returns the records it got, or ``None`` when the request failed.
Fetch = Callable[[Dict[str, Any]], Optional[List[Any]]]


def _fingerprint(records: Any) -> str:
    return json.dumps(records, sort_keys=True, ensure_ascii=False, default=str)


def _ordered(candidates: Sequence[str], preferred: Iterable[str]) -> List[str]:
    """Try names the request already uses before the common ones."""
    preferred = [name for name in preferred if name in candidates]
    return preferred + [name for name in candidates if name not in preferred]


def record_fields(records: List[Any], limit: int = 20) -> List[str]:
    """Return the sorted top-level field names of the first records."""
    fields: Set[str] = set()
    for record in records[:limit]:
        if isinstance(record, dict):
            fields.update(str(key) for key in record)
    return sorted(fields)


def probe_pagination(
    fetch: Fetch,
    first: List[Any],
    total: Optional[int] = None,
    preferred: Iterable[str] = (),
    modes: Sequence[str] = ("page", "skip"),
) -> Dict[str, Any]:
    """Suggest ``iterate_by``, parameter names and ``page_size_limit``.

    A page parameter is accepted when page 2 returns other records than the
    first request and page 1 returns the same ones; an offset parameter when
    an offset equal to the first page's size returns other records. A size
    parameter is accepted when the API returns exactly the requested number.
    """
    preferred = list(preferred)
    result: Dict[str, Any] = {"warnings": []}
    size = len(first)
    if not size:
        result["warnings"].append("The first response has no records; pagination was not probed")
        return result
    if total is not None and total <= size:
        result["page_size_limit"] = size
        result["warnings"].append(
            f"All {total} records fit on the first page; pagination was not probed"
        )
        return result

    original = _fingerprint(first)
    position: Dict[str, Any] = {}
    if "page" in modes:
        for name in _ordered(PAGE_PARAMS, preferred):
            second = fetch({name: 2})
            if second and _fingerprint(second) != original:
                if _fingerprint(fetch({name: 1})) == original:
                    result.update(iterate_by="page", page_number_param=name)
                    position = {name: 1}
                    break
    if not position and "skip" in modes:
        for name in _ordered(OFFSET_PARAMS, preferred):
            second = fetch({name: size})
            if second and _fingerprint(second) != original:
                result.update(iterate_by="skip", count_skip_param=name)
                position = {name: 0}
                break
    if not position:
        result["page_size_limit"] = size
        result["warnings"].append(
            "No page or offset parameter changed the records; set "
            "params.page_number_param or params.count_skip_param by hand"
        )
        return result

    trial = 3 if size == 2 else 2
    for name in _ordered(SIZE_PARAMS, preferred):
        records = fetch({**position, name: trial})
        if records is not None and len(records) == trial:
            result["page_size_param"] = name
            break
    if "page_size_param" not in result:
        result["page_size_limit"] = size
        return result

    records = fetch({**position, result["page_size_param"]: LARGE_PAGE})
    returned = len(records or [])
    if not returned:
        result["page_size_limit"] = size
        result["warnings"].append(
            f"A request for {LARGE_PAGE} records failed; page_size_limit is the default {size}"
        )
    elif returned >= LARGE_PAGE or (total is not None and returned >= total):
        result["page_size_limit"] = LARGE_PAGE
    else:
        result["page_size_limit"] = returned
        if total is None:
            result["warnings"].append(
                f"A request for {LARGE_PAGE} records returned {returned}; check whether "
                "the API caps the page size or the dataset is that small"
            )
    return result
