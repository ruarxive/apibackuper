"""Page-fetch loop orchestration.

The public entry point is :func:`fetch_all_pages`:

- Sequential when ``parallelism <= 1``
- ThreadPoolExecutor when ``parallelism > 1``; results are consumed in page order
- The supplied fetch worker owns the retry budget
- Updates a tqdm progress bar when one is supplied
- Saves checkpoints at the configured interval for contiguous saved pages
- Closes a supplied storage backend on every exit path for compatibility;
  callers owning durable publication pass None and close storage themselves

The caller resolves configuration and supplies a fetch worker and a storage
callback. Both sequential and parallel modes consume pages in logical order.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain, islice
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from ..common import get_dict_value
from ..constants import DEFAULT_NUMBER_OF_PAGES


@dataclass(frozen=True)
class PageOutcome:
    """Describe a page after its storage callback has completed."""

    saved: bool = True
    stop: bool = False
    records: int = 0
    bytes_written: Optional[int] = None


class FetchResult(dict):
    """Legacy error mapping with the contiguous, saved resume boundary.

    Pages saved after an error remain in storage, but are excluded from these
    counters so replaying the failed prefix cannot inflate checkpoint totals.
    """

    def __init__(self, last_page: int, pages: int, records: int, size: int):
        super().__init__()
        self.completed = True
        self.last_page = last_page
        self.next_page = last_page + 1
        self.failed_pages: List[int] = []
        self.pages_processed = pages
        self.records_processed = records
        self.bytes_processed = size


def fetch_all_pages(
    *,
    pages: Iterable[int],
    parallelism: int,
    fetch_one: Callable[[int], Dict[str, Any]],
    on_page: Callable[[int, bytes], bool | PageOutcome],
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
) -> FetchResult:
    """Run the per-page fetch loop and return errors and resume progress.

    Parameters
    ----------
    pages
        Ordered page numbers to fetch; an unbounded iterator runs until a
        page outcome or error stops the loop.
    parallelism
        Number of worker threads. ``<= 1`` means sequential.
    fetch_one
        Per-page worker. Takes a page number, returns a dict with
        ``{page, status, content, error, accepted}``. ``status`` is None on
        transport failure; ``error`` is a string when the request raised;
        ``accepted`` marks a non-2xx response that a response rule accepted.
    on_page
        Per-page success handler. Takes ``(page, content)`` and returns
        a PageOutcome, or a legacy boolean (False stops without saving).
    should_retry
        Compatibility parameter; the supplied worker owns retry decisions.
    retry_max_retries
        Compatibility parameter; the supplied worker owns the retry budget.
    max_consecutive_errors
        Aborts the loop after this many consecutive failures.
    continue_on_error
        When False, the loop aborts on the first HTTP or transport failure.
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
    FetchResult
        Mapping of status code (or ``"transport"``) to failure count, with
        completion status and counters for the contiguous saved prefix.
    """
    # ``pages`` may be an unbounded iterator when the API reports no counts.
    iterator: Iterator[int] = iter(pages)
    first = next(iterator, None)
    if first is not None:
        iterator = chain([first], iterator)
    result = FetchResult(
        first - 1 if first is not None else initial_pages_processed,
        initial_pages_processed,
        initial_records_processed,
        initial_bytes_processed,
    )
    consecutive_errors = 0
    contiguous = True
    saved_pages = initial_pages_processed

    run_close = getattr(storage_backend, "close", None)

    def safe_close_backend() -> None:
        if run_close is None:
            return
        try:
            run_close()
        except (IOError, OSError, ValueError) as e:
            logging.error("Error closing storage backend: %s", e)

    def close_progress() -> None:
        if progress_bar is not None:
            try:
                progress_bar.close()
            except Exception:
                pass

    def inc_error(page: int, key: str) -> None:
        nonlocal consecutive_errors, contiguous
        consecutive_errors += 1
        contiguous = False
        result.completed = False
        result.failed_pages.append(page)
        result[key] = result.get(key, 0) + 1

    def finalize_progress(current: int) -> None:
        if progress_bar is not None:
            elapsed = max(1e-6, time.time() - start_timer)
            speed = current / elapsed
            eta_seconds = int(max(0, total_pages - current) / speed) if speed else 0
            progress_bar.set_postfix(
                {
                    "speed_p/s": f"{speed:.2f}",
                    "eta_s": eta_seconds,
                }
            )

    def progress() -> Dict[str, Any]:
        return {
            "last_page": result.last_page,
            "next_page": result.next_page,
            "failed_pages": list(result.failed_pages),
            "pages_processed": result.pages_processed,
            "records_processed": result.records_processed,
            "storage_bytes": result.bytes_processed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def save_checkpoint_if_due() -> None:
        if not checkpoint_interval or not result.pages_processed:
            return
        if result.pages_processed % checkpoint_interval == 0:
            save_checkpoint(progress())

    def consume(page: int, response: Dict[str, Any]) -> bool:
        """Process ordered results; return True to end the entire run."""
        nonlocal consecutive_errors, saved_pages
        status = response.get("status")
        accepted = response.get("accepted") or (status is not None and 200 <= status < 300)
        if response.get("error") or status is None or not accepted:
            inc_error(page, str(status) if status is not None else "transport")
            if progress_bar is not None:
                progress_bar.update(1)
            return not continue_on_error or consecutive_errors >= max_consecutive_errors

        content = response["content"]
        outcome = on_page(page, content)
        if not isinstance(outcome, PageOutcome):
            outcome = PageOutcome(saved=bool(outcome), stop=not bool(outcome))
        if outcome.saved:
            consecutive_errors = 0
            saved_pages += 1
            if contiguous:
                result.last_page = page
                result.next_page = page + 1
                result.pages_processed += 1
                result.records_processed += outcome.records
                result.bytes_processed += (
                    len(content) if outcome.bytes_written is None else outcome.bytes_written
                )
                save_checkpoint_if_due()
            if progress_bar is not None:
                progress_bar.update(1)
            finalize_progress(saved_pages)
        elif not outcome.stop:
            inc_error(page, "unsaved")
            return not continue_on_error or consecutive_errors >= max_consecutive_errors
        return outcome.stop

    def _run_sequential() -> None:
        for page in iterator:
            if consume(page, fetch_one(page)):
                return

    def _run_parallel() -> None:
        while True:
            batch = list(islice(iterator, parallelism))
            if not batch:
                return
            results: Dict[int, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                future_map = {executor.submit(fetch_one, page): page for page in batch}
                for future in as_completed(future_map):
                    results[future_map[future]] = future.result()
            for page in batch:
                if consume(page, results[page]):
                    return

    try:
        if parallelism <= 1:
            _run_sequential()
        else:
            _run_parallel()
    except BaseException:
        # Record the durable prefix so an interrupted run (Ctrl+C, a decode
        # error) resumes after it instead of at the last periodic checkpoint.
        if result.pages_processed > initial_pages_processed:
            try:
                save_checkpoint(progress())
            except Exception as error:
                logging.error("Could not save checkpoint after interruption: %s", error)
        raise
    finally:
        close_progress()
        safe_close_backend()

    return result


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
    if page_size_limit <= 0:
        raise ValueError("page_size_limit must be greater than zero")

    total = None
    num_pages: Optional[int] = None

    if total_number_key:
        try:
            raw = get_dict_value(response_data, total_number_key, splitter=field_splitter)
            if raw is None:
                logging.warning("total_number_key not found in response")
            else:
                total = int(raw)
                if total < 0:
                    raise ValueError("record total cannot be negative")
                num_pages = (total + page_size_limit - 1) // page_size_limit
        except (ValueError, TypeError, KeyError) as e:
            logging.warning("Error extracting total_number_key: %s, using default", e)
            total = None

    if num_pages is None and pages_number_key:
        try:
            raw = get_dict_value(response_data, pages_number_key, splitter=field_splitter)
            if raw is None:
                logging.warning("pages_number_key not found in response")
                num_pages = DEFAULT_NUMBER_OF_PAGES
            else:
                num_pages = int(raw)
                if num_pages < 0:
                    raise ValueError("page total cannot be negative")
                total = num_pages * page_size_limit
        except (ValueError, TypeError, KeyError) as e:
            logging.warning("Error extracting pages_number_key: %s, using default", e)
            num_pages = DEFAULT_NUMBER_OF_PAGES
            total = None

    if num_pages is None:
        num_pages = DEFAULT_NUMBER_OF_PAGES

    return num_pages, total


__all__ = ["FetchResult", "PageOutcome", "fetch_all_pages", "parse_total_pages"]
