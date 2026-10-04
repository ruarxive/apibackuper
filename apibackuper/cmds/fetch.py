"""Per-page request parameter building.

Extracted from the ``fetch_page`` closure inside
``ProjectBuilder.run``. The closure was tangled with several
``self.*`` attributes (auth handler, http session, hooks); this
module extracts the **pure** part: assembling the per-page request
URL, params, and flatten dict for the configured iteration mode
(``page`` / ``skip`` / ``range`` / ``query_mode`` in ``"params"`` /
``"mixed"``).

The caller (the orchestrator) performs the HTTP call and retry loop using
the per-page dict returned by :func:`build_page_request`. This is the
shape that ``requests.Session.get(url, params=..., ...)`` expects.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple


def build_page_request(
    *,
    target_page: int,
    start_url: str,
    query_mode: str,
    page_limit: int,
    page_size_param: str,
    page_number_param: str,
    count_skip_param: str,
    count_from_param: str,
    count_to_param: str,
    iterate_by: str,
    change_params: Dict[str, Any],
    base_params: Dict[str, Any],
    base_url_params: Optional[Dict[str, Any]],
    base_flatten: Optional[Dict[str, Any]],
    url_replacer: Callable[..., str],
    update_dict_values: Callable[..., Dict[str, Any]],
    flat_params: bool,
) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
    """Build the per-page URL, params, url_params, and flatten.

    Parameters
    ----------
    target_page
        1-indexed page number.
    start_url
        The configured ``project.url`` (untouched).
    query_mode
        One of ``"url"`` (default), ``"params"``, ``"mixed"``.
    page_limit
        ``page_size_limit`` — records per page.
    page_size_param, page_number_param, count_skip_param, count_from_param, count_to_param
        Dotted-path parameter names for the configured iteration mode.
    iterate_by
        ``"page"``, ``"skip"``, or ``"range"``.
    change_params
        Mutable params dict shared across the run; modified copy is
        returned so the caller does not pollute the shared state.
    base_params
        The initial params dict (``params.json`` plus project defaults).
    base_url_params
        The initial url-params dict (``url_params.json``) or None.
    base_flatten
        The initial flat-params dict, when ``flat_params=True`` is
        configured. None otherwise.
    url_replacer
        ``apibackuper.cmds.utils._url_replacer`` — invoked when
        ``query_mode`` is ``"params"`` or ``"mixed"``.
    update_dict_values
        ``apibackuper.common.update_dict_values`` — used for the
        ``"url"`` (default) query mode.
    flat_params
        Whether to serialise params as a flat query string.

    Returns
    -------
    ``(request_url, params, url_params, flatten)`` — the four values
    that ``ProjectBuilder._single_request`` accepts.
    """
    local_change_params = dict(change_params)
    local_params = dict(base_params)
    local_url_params = dict(base_url_params) if base_url_params else None
    local_flatten = dict(base_flatten) if base_flatten else None

    if page_size_param:
        local_change_params[page_size_param] = page_limit

    if iterate_by == "page":
        local_change_params[page_number_param] = target_page
    elif iterate_by == "skip":
        local_change_params[count_skip_param] = (target_page - 1) * page_limit
    elif iterate_by == "range":
        local_change_params[count_from_param] = (target_page - 1) * page_limit
        local_change_params[count_to_param] = target_page * page_limit
    else:
        logging.warning("Unknown iterate_by %r — using 'page' fallback", iterate_by)
        local_change_params[page_number_param] = target_page

    if query_mode in ("params", "mixed"):
        if local_url_params is None:
            local_url_params = {}
        local_url_params.update(local_change_params)
    else:
        local_params = update_dict_values(local_params, local_change_params)
        if flat_params and local_params:
            local_flatten = {k: str(v) for k, v in local_params.items()}

    if query_mode == "params":
        request_url = url_replacer(start_url, local_url_params or {})
    elif query_mode == "mixed":
        request_url = url_replacer(
            start_url,
            local_url_params or {},
            query_mode=True,
        )
    else:
        request_url = start_url

    return request_url, local_params, local_url_params, local_flatten


__all__ = ["build_page_request"]
