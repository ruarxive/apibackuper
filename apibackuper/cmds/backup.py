"""Backup workflow shared by the public run/update commands."""

import hashlib
import itertools
import json
import os
import shutil
import time
from copy import deepcopy
from datetime import datetime, timezone
from runpy import run_path
from urllib.parse import urljoin, urlsplit

import xmltodict
from tqdm import tqdm

from .. import __version__
from ..common import get_dict_value, update_dict_values
from ..storage.session import BackupSession
from .capture import is_capture_member, save_capture
from .config_loader import load_json_file
from .export import process_record
from .fetch import CURSOR_MODES, build_page_request
from .fixity import (
    MANIFEST_NAME,
    config_digest,
    digest,
    generation_pages,
    generation_prefix,
    write_generation_record,
)
from .runner import PageOutcome, fetch_all_pages, parse_total_pages
from .utils import flat_param_value, redact_text


def _decode(project, content, process):
    if not content.strip():
        return None
    if project.resp_type == "json":
        return json.loads(content)
    if project.resp_type == "xml":
        return xmltodict.parse(content)
    if project.resp_type == "html" and process:
        return process(content)
    raise ValueError("HTML responses require a postfetch process function")


def _records(project, data):
    if project.data_key and data is not None:
        if get_dict_value(data, project.data_key, splitter=project.field_splitter) is None:
            raise ValueError(f"Response is missing configured data_key: {project.data_key}")
    return process_record(data, data_key=project.data_key, field_splitter=project.field_splitter)


def _next_position(project, response, data):
    """Return the cursor or absolute URL of the page after ``response``, or None."""
    if project.iterate_by == "link_header":
        links = getattr(response, "links", None) or {}
        value = (links.get("next") or {}).get("url")
    else:
        key = project.next_url_key if project.iterate_by == "next_url" else project.next_cursor_key
        # A literal key such as ``@odata.nextLink`` wins over a dotted path.
        if isinstance(data, dict) and key in data:
            value = data[key]
        else:
            value = get_dict_value(data, key, splitter=project.field_splitter)
    if value is None or value == "" or value is False:
        return None
    if project.iterate_by == "cursor":
        return value
    base = getattr(response, "url", None) or project.start_url
    target = urljoin(base, str(value))
    host = urlsplit(target).netloc
    if host != urlsplit(project.start_url).netloc and not project.allow_cross_host_next:
        raise RuntimeError(
            f"Backup is incomplete: the next-page URL points to another host ({host}); "
            "set params.allow_cross_host_next to follow it"
        )
    return target


def _summary(project, session, baseline):
    """Read retained run pages so legacy resume and replay have exact totals.

    Returns the summary and the SHA-256 of every page of the generation.
    """
    pages = records = size = 0
    digests = {}
    last_page = project.start_page - 1
    change = baseline.get("last_change_key")
    for name in session.backend.list_objects("page"):
        if not name.startswith(session.prefix):
            continue
        if not session.prefix and "/" in name:
            continue
        content = session.backend.get_object(name)
        digests[name] = digest(content)
        items = _records(project, json.loads(content))
        pages += 1
        records += len(items)
        size += len(content)
        last_page = max(last_page, int(name.rsplit("page_", 1)[-1].split(".")[0]))
        if project.change_key:
            for item in items:
                value = get_dict_value(item, project.change_key, splitter=project.field_splitter)
                if value is not None and (change is None or value > change):
                    change = value
    for name in session.backend.list_objects("object"):
        if is_capture_member(name) and generation_prefix(name) == session.prefix:
            digests[name] = digest(session.backend.get_object(name, "object"))
    summary = {
        "pages_processed": pages,
        "records_processed": records,
        "bytes_processed": size,
        "last_page": last_page,
        "last_change_key": change,
    }
    return summary, digests


def _run_record(project, session, mode, state, total=None):
    """Describe one published generation for its ``run.json``."""
    return {
        "apibackuper_version": __version__,
        "run_id": session.run_id or None,
        "mode": mode,
        "started": state["last_run_start"],
        "ended": state["last_run_end"],
        "pages": state["pages_processed"],
        "records": state["records_processed"],
        "api_total": total,
        "config_sha256": config_digest(project),
    }


def _finish_publication(project, session, checkpoint):
    """Replay a durable publication intent after any interrupted commit step."""
    if session.backend.get_object(session.prefix + MANIFEST_NAME, "object") is None:
        # Intents saved before manifests existed: hash the staged generation.
        names = generation_pages(session.backend.list_objects("page"), session.prefix)
        names += [
            name
            for name in session.backend.list_objects("object")
            if is_capture_member(name) and generation_prefix(name) == session.prefix
        ]
        digests = {name: digest(session.backend.get_object(name, "object")) for name in names}
        state = checkpoint["pending_state"]
        record = _run_record(project, session, checkpoint.get("mode"), state)
        write_generation_record(session.backend, session.prefix, digests, record)
        session.backend.flush()
    session.publish()
    # A full ZIP backup replaces history: move the previous backup's
    # generation archives aside, and delete them only after the new state is
    # committed. Every step is safe to repeat when resuming publication.
    generations = session.destination + ".runs"
    retired = generations + ".previous"
    if project.storage_type == "zip" and checkpoint.get("mode") == "full":
        if os.path.isdir(generations):
            if os.path.isdir(retired):
                shutil.rmtree(retired)
            os.replace(generations, retired)
    project._save_state(checkpoint["pending_state"], strict=True)
    project._save_checkpoint(
        dict(checkpoint, storage_file=session.destination, status="complete"), strict=True
    )
    previous = session.destination + ".previous"
    if project.storage_type == "filesystem" and os.path.isdir(previous):
        shutil.rmtree(previous)
    if os.path.isdir(retired):
        shutil.rmtree(retired)


def run_backup(project, mode, resume=False):
    """Run a durable backup, raising on every incomplete outcome."""
    if project.config is None:
        project._raise_config_not_found()
    if mode == "incremental":
        mode = "continue"
    if mode not in ("full", "continue", "update"):
        raise ValueError(f"Unsupported run mode: {mode}")
    if mode == "continue" and project.iterate_by in CURSOR_MODES:
        raise ValueError(
            "run continue cannot start inside a cursor chain; "
            "use run full --resume or update instead"
        )
    valid, _, _ = project.validate_config()
    if not valid:
        raise ValueError("Invalid project configuration; run validate-config for details")
    checkpoint = project._load_checkpoint() if resume else {}
    if resume and not checkpoint:
        raise ValueError("No valid checkpoint is available to resume")
    if checkpoint.get("mode", mode) != mode:
        raise ValueError("Checkpoint mode does not match the requested run mode")
    if checkpoint.get("status") == "complete":
        print("Backup is already complete")
        return

    baseline = project._load_state() if mode == "update" else {}
    if hasattr(project, "_rule_counts"):
        project._rule_counts = {}
    started = checkpoint.get("run_start") or datetime.now(timezone.utc).isoformat()
    process = None
    if project.code_postfetch:
        path = project.code_postfetch
        process = run_path(
            path if os.path.isabs(path) else os.path.join(project.project_path, path)
        ).get("process")

    headers = load_json_file(os.path.join(project.project_path, "headers.json"), {})
    params = load_json_file(os.path.join(project.project_path, "params.json"), {})
    url_params = load_json_file(os.path.join(project.project_path, "url_params.json"), {})
    hook = project._run_hook(
        "before_run",
        {"mode": mode, "project_path": project.project_path, "headers": headers, "params": params},
    )
    if isinstance(hook, dict):
        headers, params = hook.get("headers", headers), hook.get("params", params)
    changes = {}
    if mode == "update":
        if project.update_mode == "custom_script":
            raise ValueError("custom_script update mode is not implemented")
        if project.update_mode == "by_change_key" and project.change_key_param:
            value = baseline.get("last_change_key")
            if value is not None:
                changes[project.change_key_param] = value
        elif project.update_mode == "by_timestamp" and project.update_since_param:
            value = baseline.get("update_watermark") or baseline.get("last_run_end")
            if value:
                changes[project.update_since_param] = value

    session = BackupSession(project, mode, checkpoint)
    if checkpoint.get("status") == "publishing":
        try:
            _finish_publication(project, session, checkpoint)
            print("Recovered completed backup publication")
            return
        finally:
            session.backend.close()
    current = {
        "last_page": project.start_page - 1,
        "next_page": project.start_page,
        "pages_processed": 0,
        "records_processed": 0,
        "storage_bytes": 0,
        "failed_pages": [],
        # Cursor or URL of the page after the saved prefix (cursor modes).
        "cursor": None,
    }
    current.update({key: checkpoint[key] for key in current if key in checkpoint})
    if checkpoint and "next_page" not in checkpoint:
        current["next_page"] = max(
            project.start_page, int(checkpoint.get("last_page", project.start_page))
        )
    if (
        project.iterate_by in CURSOR_MODES
        and current["next_page"] > project.start_page
        and current["cursor"] is None
    ):
        # Without a stored cursor the chain cannot continue; replay it from
        # the start, overwriting the saved pages.
        current.update(
            last_page=project.start_page - 1,
            next_page=project.start_page,
            pages_processed=0,
            records_processed=0,
            storage_bytes=0,
            failed_pages=[],
        )
    if mode == "continue" and not checkpoint:
        names = set(session.backend.list_objects("page"))
        while session.name(current["next_page"]) in names:
            current["next_page"] += 1
        current["last_page"] = current["next_page"] - 1

    def save(payload):
        current.update(payload)
        session.checkpoint(dict(current, run_start=started))

    def request(page, cursor=None):
        url, page_params, _, flatten = build_page_request(
            target_page=page,
            start_url=project.start_url,
            query_mode=project.query_mode,
            page_limit=project.page_limit,
            page_size_param=project.page_size_param,
            page_number_param=project.page_number_param,
            count_skip_param=project.count_skip_param,
            count_from_param=project.count_from_param,
            count_to_param=project.count_to_param,
            iterate_by=project.iterate_by,
            change_params=changes,
            base_params=params,
            base_url_params=url_params,
            base_flatten=None,
            url_replacer=project_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=project.flat_params,
            cursor_param=project.cursor_param,
            cursor=cursor,
        )
        if cursor is not None and project.iterate_by in ("next_url", "link_header"):
            # The next URL carries the position and the original query.
            url = cursor
            if project.http_mode == "GET":
                page_params, flatten = {}, None
        local_headers = deepcopy(headers)
        hook = project._run_hook(
            "before_request",
            {
                "url": url,
                "headers": local_headers,
                "params": page_params,
                "mode": mode,
                "page": page,
            },
        )
        if isinstance(hook, dict):
            url, local_headers, page_params = (
                hook.get("url", url),
                hook.get("headers", local_headers),
                hook.get("params", page_params),
            )
            if project.flat_params:
                flatten = {key: flat_param_value(value) for key, value in page_params.items()}
        response = project._request(url, local_headers, page_params, flatten)
        project._run_hook(
            "after_response",
            {
                "url": url,
                "headers": local_headers,
                "params": page_params,
                "mode": mode,
                "page": page,
                "response": project._serialize_response(response),
            },
        )
        return response

    # Imported once here so ProjectBuilder remains the configuration/public API facade.
    from .utils import _url_replacer as project_url_replacer

    bar = None
    try:
        save(current)
        first_page = int(current["next_page"])
        response = request(first_page, current["cursor"])
        first_fetched = datetime.now(timezone.utc).isoformat()
        first_data = _decode(project, response.content, process)
        if project.detect_enabled and project.resp_type == "json":
            project._apply_detection(project._detect_suggestions(first_data, response.headers))
        num_pages, total = parse_total_pages(
            first_data,
            resp_type=project.resp_type,
            total_number_key=project.total_number_key,
            pages_number_key=project.pages_number_key,
            page_size_limit=project.page_limit,
            field_splitter=project.field_splitter,
        )
        cursor_mode = project.iterate_by in CURSOR_MODES
        if cursor_mode:
            pagination_parameter = project.cursor_param or "next link"
        else:
            pagination_parameter = {
                "page": project.page_number_param,
                "skip": project.count_skip_param,
                "range": project.count_from_param,
            }.get(project.iterate_by)
        # Count metadata bounds the run; without it, collect until the API
        # returns a short or empty page instead of stopping at a fixed cap.
        # Cursor chains end only when the API returns no next position.
        bounded = not cursor_mode and (total is not None or not pagination_parameter)
        if not pagination_parameter:
            num_pages = 1
        num_pages = max(1, num_pages)
        last_expected = project.start_page + num_pages - 1
        pages = range(first_page, last_expected + 1) if bounded else itertools.count(first_page)
        bar = tqdm(total=len(pages) if bounded else None, desc="Downloading pages", unit="page")

        # Cursor modes: the next position comes from the stored page's response.
        # Capture: the exchange record is built from that response as well.
        position = {"next": current["cursor"]}
        capturing = project.capture_metadata or project.capture_raw_body != "never"
        responses = {}
        seen = set()
        if current["cursor"] is not None:
            seen.add(json.dumps(current["cursor"], sort_keys=True, default=str))

        def fetch(page):
            try:
                if page == first_page:
                    result, fetched_at = response, first_fetched
                else:
                    result = request(page, position["next"])
                    fetched_at = datetime.now(timezone.utc).isoformat()
                if cursor_mode or capturing:
                    responses[page] = (result, fetched_at)
                # ``_request`` returns only responses its status policy and
                # response rules accepted, including accepted non-2xx ones.
                return {
                    "page": page,
                    "status": result.status_code,
                    "content": result.content,
                    "accepted": True,
                }
            except (RuntimeError, ValueError, OSError) as exc:
                return {
                    "page": page,
                    "status": getattr(exc, "status_code", None),
                    "error": redact_text(exc),
                }

        hook_records = current["records_processed"]
        previous_digest = None
        early_end = None

        def note_end(page, count):
            nonlocal early_end
            if bounded and pagination_parameter and page < last_expected:
                early_end = (page, count)

        def store(page, content):
            nonlocal hook_records, previous_digest
            exchange, fetched_at = responses.pop(page, (None, None))
            data = _decode(project, content, process)
            items = _records(project, data)
            if not items:
                note_end(page, 0)
                return PageOutcome(saved=False, stop=True)
            if pagination_parameter:
                digest = hashlib.sha256(
                    json.dumps(items, sort_keys=True, ensure_ascii=False, default=str).encode()
                ).hexdigest()
                if digest == previous_digest:
                    raise ValueError(
                        f"Page {page} returned the same records as page {page - 1}; the API "
                        f"appears to ignore the pagination parameter {pagination_parameter!r}"
                    )
                previous_digest = digest
            following = None
            if cursor_mode:
                following = _next_position(project, exchange, data)
                if following is not None:
                    marker = json.dumps(following, sort_keys=True, default=str)
                    if marker in seen:
                        raise RuntimeError(
                            f"Backup is incomplete: page {page} returned a next position that "
                            "was already followed; the API pagination loops"
                        )
                    seen.add(marker)
            serialized = (
                content
                if project.resp_type == "json"
                else json.dumps(data, ensure_ascii=False).encode("utf8")
            )
            if capturing and exchange is not None:
                # Saved first, so a page never exists without its exchange.
                save_capture(project, session, page, exchange, fetched_at)
            session.backend.save_page(session.name(page), serialized)
            hook_records += len(items)
            project._run_hook(
                "after_page",
                {
                    "page": page,
                    "mode": mode,
                    "records_processed": hook_records,
                    "bytes_written": len(serialized),
                },
            )
            if cursor_mode:
                current["cursor"] = position["next"] = following
                return PageOutcome(
                    records=len(items), bytes_written=len(serialized), stop=following is None
                )
            countable = isinstance(data, list) or bool(project.data_key)
            short = countable and len(items) < project.page_limit
            if short:
                note_end(page, len(items))
            return PageOutcome(
                records=len(items),
                bytes_written=len(serialized),
                stop=short or not countable,
            )

        result = fetch_all_pages(
            pages=pages,
            # Each cursor request depends on the previous response.
            parallelism=1 if cursor_mode else project.parallelism,
            fetch_one=fetch,
            on_page=store,
            should_retry=project._should_retry,
            retry_max_retries=project.retry_max_retries,
            max_consecutive_errors=project.max_consecutive_errors,
            continue_on_error=project.continue_on_error and not cursor_mode,
            storage_backend=None,
            progress_bar=bar,
            start_timer=time.time(),
            total_pages=len(pages) if bounded else 0,
            checkpoint_interval=project.checkpoint_interval_pages,
            save_checkpoint=save,
            initial_pages_processed=current["pages_processed"],
            initial_records_processed=current["records_processed"],
            initial_bytes_processed=current["storage_bytes"],
        )
        if pages:
            save(
                {
                    "last_page": result.last_page,
                    "next_page": result.next_page,
                    "pages_processed": result.pages_processed,
                    "records_processed": result.records_processed,
                    "storage_bytes": result.bytes_processed,
                    "failed_pages": result.failed_pages,
                }
            )
        if not result.completed:
            raise RuntimeError(
                "Backup is incomplete; resume from checkpoint. Errors: " + json.dumps(result)
            )
        if early_end is not None:
            page, count = early_end
            raise RuntimeError(
                f"Backup is incomplete: page {page} returned {count} records "
                f"(page_size_limit is {project.page_limit}) before page {last_expected}, the "
                f"last page implied by the API's count metadata. If the API caps the page "
                f"size, set params.page_size_limit to the size it returns and run a new full "
                f"backup; if its count is not exact, remove the count key from the data section."
            )
        summary, digests = _summary(project, session, baseline)
        if total is not None and summary["records_processed"] < total:
            print(
                f"Warning: collected {summary['records_processed']} of {total} records "
                "reported by the API"
            )
        ended = datetime.now(timezone.utc).isoformat()
        state = dict(summary, last_run_start=started, last_run_end=ended, update_watermark=started)
        write_generation_record(
            session.backend,
            session.prefix,
            digests,
            _run_record(project, session, mode, state, total),
        )
        session.backend.flush()
        publication = dict(
            current,
            mode=mode,
            run_id=session.run_id,
            storage_file=session.path,
            run_start=started,
            status="publishing",
            pending_state=state,
        )
        project._save_checkpoint(publication, strict=True)
        _finish_publication(project, session, publication)
        project._run_hook("after_run", dict(mode=mode, **summary, errors={}))
        print("Run summary:")
        print(f"  Pages processed: {summary['pages_processed']}")
        print(f"  Total records: {summary['records_processed']}")
        print(f"  Total bytes: {summary['bytes_processed']}")
        print("  Errors by status: none")
        counts = getattr(project, "_rule_counts", None)
        if counts:
            listed = ", ".join(f"{action}={count}" for action, count in sorted(counts.items()))
            print(f"  Response rules applied: {listed}")
    finally:
        if bar is not None:
            bar.close()
        session.backend.close()
