"""Page-fetch loop orchestration.

Extracted from ``cmds/project.py`` so the sequential and parallel fetch
loops are unit-testable in isolation and so future changes (e.g. async
via asyncio + httpx) touch one file instead of a 3,000-line god module.

The public entry point is :func:`fetch_all_pages` which mirrors the
historical behaviour:

- Sequential when ``parallelism <= 1``
- ThreadPoolExecutor when ``parallelism > 1`` (the same executor handles
  each page; results are read back in completion order)
- Honors ``retry_max_retries`` per page
- Updates a tqdm progress bar when one is supplied
- Saves checkpoint every ``checkpoint_interval_pages`` (the orchestrator
  passes the ``checkpoint_callback``)
- Closes the storage backend on every exit path (try/finally) so a
  single error during parallel fetch does not corrupt the archive

The orchestrator expects the caller to have already:

1. Built the storage backend and stored ``page_1.json`` (or the first
   available page) so that ``detect_enabled`` and the page-count
   inference have a starting response to inspect.
2. Resolved headers, params, url_params, flatten, change_params, and
   start_page/end_page via the project's configuration.

Those responsibilities remain in ``ProjectBuilder.run`` because they
depend on config schema and hooks; only the per-page loop body lives
here.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

from ..common import get_dict_value
from ..constants import DEFAULT_NUMBER_OF_PAGES


def fetch_all_pages(
    *,
    pages: List[int],
    parallelism: int,
    fetch_one: Callable[[int], Dict[str, Any]],
    on_page: Callable[[int, bytes], bool],
    should_retry: Callable[[Optional[int]], bool],
    retry_max_retries: int,
    max_consecutive_errors: int,
    continue_on_error: bool,
    storage_backend: Any,
    progress_bar: Any,
    start_timer: float,
    total_pages: int,
    checkpoint_interval: int,
    save_checkpoint: Callable[[Dict[str, Any]], None],
    initial_pages_processed: int = 0,
    initial_records_processed: int = 0,
    initial_bytes_processed: int = 0,
) -> Dict[str, int]:
    """Run the per-page fetch loop and return error_counts.

    Parameters
    ----------
    pages
        Ordered list of page numbers to fetch.
    parallelism
        Number of worker threads. ``<= 1`` means sequential.
    fetch_one
        Per-page worker. Takes a page number, returns a dict with
        ``{page, status, content, error}``. ``status`` is None on transport
        failure; ``error`` is a string when the request raised.
    on_page
        Per-page success handler. Takes ``(page, content)`` and returns
        ``True`` to continue, ``False`` to early-stop.
    should_retry
        Predicate over a status code; the loop retries when it returns True.
    retry_max_retries
        Per-page retry budget for retryable status codes.
    max_consecutive_errors
        Aborts the loop after this many consecutive failures.
    continue_on_error
        When False, the loop aborts on the first retryable failure.
    storage_backend
        Object with a ``close()`` method, or None. Closed on every exit
        path via try/finally.
    progress_bar
        tqdm-compatible progress bar, or None.
    start_timer
        ``time.time()`` snapshot for speed calculation.
    total_pages
        Total pages in this run (for ETA display).
    checkpoint_interval
        Save a checkpoint every N pages; 0 disables.
    save_checkpoint
        Function called with a checkpoint dict.
    initial_pages_processed, initial_records_processed, initial_bytes_processed
        Initial values for the running totals (so checkpoint payloads
        include the full project progress, not just this loop's slice).

    Returns
    -------
    dict mapping status code (or ``"transport"``) → count of failures.
    """
    error_counts: Dict[str, int] = {}
    consecutive_errors = 0

    run_close = getattr(storage_backend, "close", None)

    def safe_close_backend() -> None:
        if run_close is None:
            return
        try:
            run_close()
        except (IOError, OSError, ValueError) as e:
            logging.error("Error closing storage backend: %s", e)

    def close_progress() -> None:
        if progress_bar:
            try:
                progress_bar.close()
            except Exception:
                pass

    def inc_error(status: Optional[int], transport_error: Optional[str]) -> None:
        nonlocal consecutive_errors
        consecutive_errors += 1
        if status is not None:
            error_counts[str(status)] = error_counts.get(str(status), 0) + 1
        elif transport_error:
            error_counts["transport"] = error_counts.get("transport", 0) + 1

    def finalize_progress(current: int) -> None:
        if progress_bar:
            elapsed = max(1e-6, time.time() - start_timer)
            speed = current / elapsed
            eta_seconds = int((total_pages - current) / speed) if speed else 0
            progress_bar.set_postfix({
                "speed_p/s": f"{speed:.2f}",
                "eta_s": eta_seconds,
            })

    pages_processed_local = [initial_pages_processed]  # mutable container
    total_records_local = [initial_records_processed]
    total_bytes_local = [initial_bytes_processed]
    _result_lock = threading.Lock()

    def record_success(content: bytes, current_page: int) -> None:
        """Increment running totals only when a page has been successfully
        consumed (i.e. ``on_page`` returned True)."""
        with _result_lock:
            total_bytes_local[0] += len(content)
            pages_processed_local[0] += 1

    def save_checkpoint_if_due(current_page: int) -> None:
        if not checkpoint_interval:
            return
        with _result_lock:
            current_processed = pages_processed_local[0]
        if current_processed > 0 and current_processed % checkpoint_interval == 0:
            save_checkpoint({
                "last_page": current_page,
                "records_processed": total_records_local[0],
                "storage_bytes": total_bytes_local[0],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

    def _run_sequential() -> bool:
        nonlocal consecutive_errors
        for page in pages:
            result = fetch_one(page)
            status = result.get("status")
            transport_error = result.get("error")
            if transport_error or should_retry(status):
                inc_error(status, transport_error)
                if consecutive_errors >= max_consecutive_errors:
                    return False
                if not continue_on_error:
                    return False
                if progress_bar:
                    progress_bar.update(1)
                continue
            consecutive_errors = 0
            content = result["content"]
            if not on_page(page, content):
                return False
            record_success(content, page)
            if progress_bar:
                progress_bar.update(1)
            finalize_progress(pages_processed_local[0])
            save_checkpoint_if_due(page)
        return True

    def _run_parallel() -> bool:
        nonlocal consecutive_errors
        for offset in range(0, len(pages), parallelism):
            batch = pages[offset:offset + parallelism]
            results: Dict[int, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                future_map = {executor.submit(fetch_one, page): page for page in batch}
                for future in as_completed(future_map):
                    result = future.result()
                    results[result["page"]] = result
            stop_now = False
            for page in batch:
                if stop_now:
                    break
                result = results.get(page)
                if result is None:
                    continue
                status = result.get("status")
                transport_error = result.get("error")
                if transport_error or should_retry(status):
                    inc_error(status, transport_error)
                    if consecutive_errors >= max_consecutive_errors:
                        return False
                    if not continue_on_error:
                        return False
                    if progress_bar:
                        progress_bar.update(1)
                    continue
                consecutive_errors = 0
                content = result["content"]
                if not on_page(page, content):
                    stop_now = True
                    continue
                record_success(content, page)
                if progress_bar:
                    progress_bar.update(1)
                finalize_progress(pages_processed_local[0])
                save_checkpoint_if_due(page)
        return True

    try:
        if parallelism <= 1:
            _run_sequential()
        else:
            _run_parallel()
    finally:
        close_progress()
        safe_close_backend()

    return error_counts


def parse_total_pages(
    response_data: Any,
    *,
    resp_type: str,
    total_number_key: str,
    pages_number_key: str,
    page_size_limit: int,
    field_splitter: str = ".",
) -> tuple:
    """Infer the total page count from the API's metadata.

    Returns ``(num_pages, total_records)``. Falls back to
    :data:`DEFAULT_NUMBER_OF_PAGES` if neither ``total_number_key`` nor
    ``pages_number_key`` matches anything in the response.

    This is the per-run page-count logic that lived inline in
    ``ProjectBuilder.run`` before the runner extraction.
    """
    total = None
    num_pages: Optional[int] = None

    if total_number_key:
        try:
            raw = get_dict_value(response_data, total_number_key, splitter=field_splitter)
            if raw is None:
                logging.warning("total_number_key not found in response")
            else:
                total = int(raw)
                nr = 1 if total % page_size_limit > 0 else 0
                num_pages = (total // page_size_limit) + nr
        except (ValueError, TypeError, KeyError) as e:
            logging.warning("Error extracting total_number_key: %s, using default", e)
            num_pages = DEFAULT_NUMBER_OF_PAGES
            total = None

    if num_pages is None and pages_number_key:
        try:
            raw = get_dict_value(response_data, pages_number_key, splitter=field_splitter)
            if raw is None:
                logging.warning("pages_number_key not found in response")
                num_pages = DEFAULT_NUMBER_OF_PAGES
            else:
                num_pages = int(raw)
                total = num_pages * page_size_limit
        except (ValueError, TypeError, KeyError) as e:
            logging.warning("Error extracting pages_number_key: %s, using default", e)
            num_pages = DEFAULT_NUMBER_OF_PAGES
            total = None

    if num_pages is None:
        num_pages = DEFAULT_NUMBER_OF_PAGES

    return num_pages, total


__all__ = ["fetch_all_pages", "parse_total_pages"]