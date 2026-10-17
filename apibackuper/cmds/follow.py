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
import os
from copy import deepcopy
from runpy import run_path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zipfile import ZipFile

from ..common import get_dict_value, update_dict_values
from ..storage import ZipStorageBackend, build_storage_backend, safe_member_name
from ..storage.backends import publish_zip
from .config_loader import load_json_file
from .export import process_record


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


def follow_project(project, mode="full"):
    """Follow stored records with the same HTTP controls as backup requests."""
    if project.config is None:
        project._raise_config_not_found()
    if not project.follow_enabled:
        raise ValueError("Follow mode is not enabled")
    if mode not in ("full", "continue"):
        raise ValueError("Follow mode must be full or continue")
    directory = (
        os.path.dirname(project.storage_file)
        if project.storage_type == "sqlite"
        else project.storagedir
    )
    os.makedirs(directory, exist_ok=True)
    headers = load_json_file(os.path.join(project.project_path, "headers.json"), {})
    params = load_json_file(os.path.join(project.project_path, "follow_params.json"), {})
    process = None
    if project.code_follow:
        path = project.code_follow
        process = run_path(
            path if os.path.isabs(path) else os.path.join(project.project_path, path)
        ).get("process")
    rules = project.follow_rules or [{}]
    for rule in rules:

        def option(name, default=None, *, rule=rule):
            return rule.get(name, getattr(project, name, default))

        follow_mode = option("follow_mode") or rule.get("mode")
        if follow_mode not in ("item", "prefix", "url"):
            raise ValueError(f"Unsupported follow_mode: {follow_mode}")
        suffix = "_" + safe_member_name(rule["name"]).replace("/", "_") if rule.get("name") else ""
        destination = os.path.join(directory, f"details{suffix}.zip")
        working = (
            destination + ".partial"
            if mode == "full" or os.path.exists(destination + ".partial")
            else destination
        )
        source = build_storage_backend(project.storage_type, project.storage_file, "read")
        targets = {}
        try:
            for name in source.list_objects("page"):
                for item in process_record(
                    json.loads(source.get_object(name)),
                    data_key=project.data_key,
                    field_splitter=project.field_splitter,
                ):
                    key = get_dict_value(
                        item, option("follow_item_key"), splitter=project.field_splitter
                    )
                    if key is None:
                        raise ValueError("A followed record is missing follow_item_key")
                    targets[key] = item
        finally:
            source.close()
        target = ZipStorageBackend(working, mode="w" if mode == "full" else "a")
        try:
            for key, item in targets.items():
                pattern = option("follow_pattern")
                follow_param = option("follow_param")
                if follow_mode == "url":
                    url = get_dict_value(
                        item, option("follow_url_key"), splitter=project.field_splitter
                    )
                elif follow_mode == "prefix":
                    url = pattern + str(key)
                else:
                    substitutions = dict(item) if isinstance(item, dict) else {}
                    if follow_param:
                        substitutions[follow_param] = key
                    url = pattern.format(**substitutions)
                pagination = rule.get("params", {})
                paginated = bool(rule.get("iterate_by") and pagination.get("page_number_param"))
                limit = int(pagination.get("page_size_limit", project.page_limit))
                maximum = int(pagination.get("max_pages", 1000)) if paginated else 1
                for page in range(1, maximum + 1):
                    name = safe_member_name(
                        f"{key}_page_{page}.json" if paginated else f"{key}.json"
                    )
                    changes = {follow_param: key} if follow_param else {}
                    if paginated:
                        changes[pagination["page_number_param"]] = page
                        if pagination.get("page_size_param"):
                            changes[pagination["page_size_param"]] = limit
                    if mode == "continue" and name in target.list_objects("object"):
                        content = target.get_object(name, "object")
                    else:
                        response = project._request(
                            url,
                            headers,
                            update_dict_values(deepcopy(params), changes),
                            http_mode=option("follow_http_mode", "GET"),
                        )
                        content = response.content
                        if project.resp_type == "html":
                            if process is None:
                                raise ValueError(
                                    "HTML follow requires code.follow process function"
                                )
                            content = json.dumps(process(content), ensure_ascii=False).encode(
                                "utf8"
                            )
                        target.save_object(name, content)
                        target.flush()
                    if not paginated:
                        break
                    records = process_record(
                        json.loads(content),
                        data_key=option("follow_data_key"),
                        field_splitter=project.field_splitter,
                    )
                    if len(records) < limit:
                        break
                else:
                    raise RuntimeError("Follow pagination reached max_pages before end of data")
            target.close()
            if working != destination:
                publish_zip(working, destination)
        finally:
            target.close()


__all__ = [
    "extract_keys_from_pages",
    "extract_url_map_from_pages",
    "compute_pending_targets",
]
