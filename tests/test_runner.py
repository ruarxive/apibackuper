"""Tests for the extracted ``cmds.runner`` module.

These cover the orchestration logic in isolation: sequential vs parallel
loops, retry exhaustion, consecutive-error abort, storage close on
every exit path, and the page-count parser.
"""

from unittest.mock import MagicMock

import pytest

from apibackuper.cmds.runner import FetchResult, PageOutcome, fetch_all_pages, parse_total_pages
from apibackuper.constants import DEFAULT_NUMBER_OF_PAGES


@pytest.fixture
def run_pages():
    """Run pages with successful defaults; override only the behavior under test."""

    def run(**overrides):
        options = {
            "pages": [1, 2, 3],
            "parallelism": 1,
            "fetch_one": lambda p: {"page": p, "status": 200, "content": b"{}"},
            "on_page": lambda p, c: True,
            "should_retry": lambda s: False,
            "retry_max_retries": 0,
            "max_consecutive_errors": 10,
            "continue_on_error": True,
            "storage_backend": None,
            "progress_bar": None,
            "start_timer": 0.0,
            "total_pages": 3,
            "checkpoint_interval": 0,
            "save_checkpoint": lambda c: None,
        }
        options.update(overrides)
        return fetch_all_pages(**options)

    return run


@pytest.mark.parametrize("parallelism", [1, 2])
def test_nonretryable_http_failure_is_not_saved(run_pages, parallelism):
    saved = []
    result = run_pages(
        parallelism=parallelism,
        fetch_one=lambda p: {"page": p, "status": 403, "content": b"denied"},
        on_page=lambda p, c: saved.append(p) or True,
    )
    assert result == {"403": 3}
    assert saved == []
    assert not result.completed
    assert result.next_page == 1
    assert result.failed_pages == [1, 2, 3]


def test_parallel_terminal_page_prevents_later_batches(run_pages):
    fetched = []
    saved = []

    def fetch(page):
        fetched.append(page)
        return {"page": page, "status": 200, "content": b"{}"}

    def consume(page, content):
        if page == 2:
            return False
        saved.append(page)
        return True

    result = run_pages(pages=list(range(1, 7)), parallelism=3, fetch_one=fetch, on_page=consume)
    assert sorted(fetched) == [1, 2, 3]
    assert saved == [1]
    assert result.completed
    assert result.last_page == 1
    assert result.next_page == 2


@pytest.mark.parametrize("parallelism", [1, 3])
def test_checkpoint_never_passes_failed_page(run_pages, parallelism):
    checkpoints = []
    saved = []
    result = run_pages(
        parallelism=parallelism,
        fetch_one=lambda p: {
            "page": p,
            "status": 503 if p == 2 else 200,
            "content": b"{}",
        },
        on_page=lambda p, c: saved.append(p) or True,
        checkpoint_interval=1,
        save_checkpoint=checkpoints.append,
    )
    assert saved == [1, 3]
    assert [c["last_page"] for c in checkpoints] == [1]
    assert checkpoints[0]["next_page"] == 2
    assert checkpoints[0]["storage_bytes"] == 2
    assert result.last_page == 1
    assert result.next_page == 2
    assert result.failed_pages == [2]
    assert result.pages_processed == 1
    assert result.bytes_processed == 2
    assert not result.completed


@pytest.mark.parametrize("parallelism", [1, 3])
def test_saved_terminal_page_counts_records_and_bytes_once(run_pages, parallelism):
    consumed = []
    checkpoints = []
    progress = MagicMock()

    def consume(page, content):
        consumed.append(page)
        return PageOutcome(stop=page == 3, records=2, bytes_written=7)

    result = run_pages(
        pages=[2, 3, 4, 5],
        parallelism=parallelism,
        on_page=consume,
        progress_bar=progress,
        initial_pages_processed=1,
        initial_records_processed=5,
        initial_bytes_processed=9,
        checkpoint_interval=1,
        save_checkpoint=checkpoints.append,
    )
    assert isinstance(result, FetchResult)
    assert result == {}
    assert result.completed
    assert consumed == [2, 3]
    assert result.last_page == 3
    assert result.next_page == 4
    assert result.failed_pages == []
    assert result.pages_processed == 3
    assert result.records_processed == 9
    assert result.bytes_processed == 23
    assert checkpoints[-1]["last_page"] == 3
    assert checkpoints[-1]["records_processed"] == 9
    assert checkpoints[-1]["storage_bytes"] == 23
    assert progress.update.call_count == 2


def test_unsaved_nonterminal_page_freezes_checkpoint(run_pages):
    result = run_pages(
        on_page=lambda p, c: PageOutcome(saved=p != 2, records=3),
    )
    assert result == {"unsaved": 1}
    assert result.failed_pages == [2]
    assert result.next_page == 2
    assert result.records_processed == 3
    assert not result.completed


@pytest.mark.parametrize("raw_total", [None, "invalid", -1])
def test_invalid_record_metadata_falls_back_to_page_metadata(raw_total):
    assert parse_total_pages(
        {"total": raw_total, "pages": 4},
        resp_type="json",
        total_number_key="total",
        pages_number_key="pages",
        page_size_limit=10,
    ) == (4, 40)


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_page_size_is_rejected(limit):
    with pytest.raises(ValueError, match="page_size_limit"):
        parse_total_pages(
            {"total": 2},
            resp_type="json",
            total_number_key="total",
            pages_number_key="",
            page_size_limit=limit,
        )


class TestFetchAllPagesSequential:
    def test_runs_all_pages_sequentially(self):
        calls = []

        def fetch_one(page):
            calls.append(page)
            return {"page": page, "status": 200, "content": b"{}"}

        def on_page(page, content):
            return True

        errors = fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=1,
            fetch_one=fetch_one,
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=None,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert calls == [1, 2, 3]
        assert errors == {}

    def test_storage_backend_closed_after_success(self):
        backend = MagicMock()
        fetch_all_pages(
            pages=[1],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=lambda p, c: True,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=1,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert backend.close.called

    def test_storage_backend_closed_when_on_page_returns_false(self):
        backend = MagicMock()
        fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=lambda p, c: False,  # early-stop after first page
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert backend.close.called

    def test_storage_backend_closed_when_fetch_raises(self):
        backend = MagicMock()

        def fetch_one(page):
            raise RuntimeError("network down")

        with pytest.raises(RuntimeError):
            fetch_all_pages(
                pages=[1],
                parallelism=1,
                fetch_one=fetch_one,
                on_page=lambda p, c: True,
                should_retry=lambda s: False,
                retry_max_retries=0,
                max_consecutive_errors=10,
                continue_on_error=True,
                storage_backend=backend,
                progress_bar=None,
                start_timer=0.0,
                total_pages=1,
                checkpoint_interval=0,
                save_checkpoint=lambda c: None,
            )
        # Even on exception, the finally clause must close the backend.
        assert backend.close.called


class TestFetchAllPagesErrors:
    def test_consecutive_errors_trigger_abort(self):
        backend = MagicMock()
        errors = fetch_all_pages(
            pages=[1, 2, 3, 4, 5],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 503, "content": b""},
            on_page=lambda p, c: True,
            should_retry=lambda s: s == 503,
            retry_max_retries=0,
            max_consecutive_errors=2,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=5,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        # 503 errors accumulate; abort after 2 consecutive.
        assert errors == {"503": 2}

    def test_continue_on_error_false_aborts_on_first_failure(self):
        backend = MagicMock()
        errors = fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 503, "content": b""},
            on_page=lambda p, c: True,
            should_retry=lambda s: s == 503,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=False,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert errors == {"503": 1}

    def test_transport_error_counted_separately(self):
        backend = MagicMock()
        errors = fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "error": "Timeout", "status": None},
            on_page=lambda p, c: True,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert errors == {"transport": 3}


class TestFetchAllPagesParallel:
    def test_parallelism_two_processes_in_batches(self):
        pages_processed = []

        def on_page(p, content):
            pages_processed.append(p)
            return True

        backend = MagicMock()
        errors = fetch_all_pages(
            pages=[1, 2, 3, 4, 5],
            parallelism=2,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=5,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert sorted(pages_processed) == [1, 2, 3, 4, 5]
        assert errors == {}
        assert backend.close.called

    def test_parallel_storage_close_on_on_page_returns_false(self):
        pages_processed = []

        def on_page(p, content):
            pages_processed.append(p)
            return p < 3  # early-stop after page 3

        backend = MagicMock()
        fetch_all_pages(
            pages=[1, 2, 3, 4, 5],
            parallelism=3,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=backend,
            progress_bar=None,
            start_timer=0.0,
            total_pages=5,
            checkpoint_interval=0,
            save_checkpoint=lambda c: None,
        )
        assert backend.close.called


class TestFetchAllPagesCheckpoint:
    def test_checkpoint_saved_every_n_pages(self):
        saved = []
        fetch_all_pages(
            pages=[1, 2, 3, 4, 5],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=lambda p, c: True,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=None,
            progress_bar=None,
            start_timer=0.0,
            total_pages=5,
            checkpoint_interval=2,
            save_checkpoint=lambda c: saved.append(c),
        )
        # Checkpoints saved at pages 2 and 4 (every 2 pages).
        assert len(saved) == 2
        assert saved[0]["last_page"] == 2
        assert saved[1]["last_page"] == 4

    def test_checkpoint_disabled_when_interval_zero(self):
        saved = []
        fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=1,
            fetch_one=lambda p: {"page": p, "status": 200, "content": b""},
            on_page=lambda p, c: True,
            should_retry=lambda s: False,
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=None,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=0,
            save_checkpoint=lambda c: saved.append(c),
        )
        assert saved == []


class TestParseTotalPages:
    def test_total_number_key_with_divide(self):
        # total=105, page_limit=10 -> 11 pages
        num_pages, total = parse_total_pages(
            {"meta": {"total_records": 105}},
            resp_type="json",
            total_number_key="meta.total_records",
            pages_number_key="",
            page_size_limit=10,
        )
        assert num_pages == 11
        assert total == 105

    def test_total_number_key_exact_multiple(self):
        # total=100, page_limit=10 -> 10 pages (no remainder page)
        num_pages, total = parse_total_pages(
            {"meta": {"total_records": 100}},
            resp_type="json",
            total_number_key="meta.total_records",
            pages_number_key="",
            page_size_limit=10,
        )
        assert num_pages == 10
        assert total == 100

    def test_pages_number_key_inference(self):
        # When ``pages_number_key`` is set, ``total`` is computed from pages * limit
        num_pages, total = parse_total_pages(
            {"pagination": {"pages": 7}},
            resp_type="json",
            total_number_key="",
            pages_number_key="pagination.pages",
            page_size_limit=10,
        )
        assert num_pages == 7
        assert total == 70

    def test_no_metadata_keys_falls_back_to_default(self):
        num_pages, total = parse_total_pages(
            {},
            resp_type="json",
            total_number_key="",
            pages_number_key="",
            page_size_limit=10,
        )
        assert num_pages == DEFAULT_NUMBER_OF_PAGES
        assert total is None

    def test_total_garbage_value_falls_back_to_default(self):
        # If total_number_key is set but the value is not numeric, fall back.
        num_pages, total = parse_total_pages(
            {"meta": {"total_records": "not-a-number"}},
            resp_type="json",
            total_number_key="meta.total_records",
            pages_number_key="",
            page_size_limit=10,
        )
        assert num_pages == DEFAULT_NUMBER_OF_PAGES

    def test_pages_number_key_not_found_falls_back(self):
        # ``pages_number_key`` is configured but absent from the response.
        num_pages, total = parse_total_pages(
            {"other": "value"},
            resp_type="json",
            total_number_key="",
            pages_number_key="pagination.pages",
            page_size_limit=10,
        )
        assert num_pages == DEFAULT_NUMBER_OF_PAGES
        assert total is None

    def test_pages_number_key_garbage_value_falls_back(self):
        # ``pages_number_key`` is configured but the value is not numeric.
        num_pages, total = parse_total_pages(
            {"pagination": {"pages": "not-a-number"}},
            resp_type="json",
            total_number_key="",
            pages_number_key="pagination.pages",
            page_size_limit=10,
        )
        assert num_pages == DEFAULT_NUMBER_OF_PAGES
        assert total is None

    def test_close_progress_handles_exceptions(self):
        """``close_progress`` swallows exceptions from the bar's close()
        so a malformed progress bar can't fail the run."""
        from apibackuper.cmds.runner import fetch_all_pages

        broken_bar = MagicMock()
        broken_bar.close.side_effect = Exception("tqdm broke")

        # Set up a single-page run with a broken progress bar.
        def fetch_one(page):
            return {"status": 200, "content": b"{}", "error": None}

        def on_page(page, content):
            return True

        storage = MagicMock()
        storage.save_page = MagicMock()

        # Should not raise despite broken_bar.close() raising.
        result = fetch_all_pages(
            pages=[1],
            parallelism=1,
            fetch_one=fetch_one,
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=1,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=storage,
            progress_bar=broken_bar,
            start_timer=0.0,
            total_pages=1,
            checkpoint_interval=None,
            save_checkpoint=lambda x: None,
        )
        # close() was attempted (and failed internally — swallowed).
        assert result == {}
        broken_bar.close.assert_called_once()

    def test_safe_close_backend_logs_and_swallows_ioerror(self):
        """``safe_close_backend`` swallows IOError / OSError /
        ValueError from the storage backend's ``close()`` so a
        malfunctioning close at end-of-run doesn't crash the CLI."""
        from apibackuper.cmds.runner import fetch_all_pages

        broken_storage = MagicMock()
        broken_storage.close.side_effect = OSError("disk full")
        broken_storage.save_page = MagicMock()

        def fetch_one(page):
            return {"status": 200, "content": b"{}", "error": None}

        def on_page(page, content):
            return True

        # Should not raise despite the storage close() failing.
        fetch_all_pages(
            pages=[1],
            parallelism=1,
            fetch_one=fetch_one,
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=1,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=broken_storage,
            progress_bar=None,
            start_timer=0.0,
            total_pages=1,
            checkpoint_interval=None,
            save_checkpoint=lambda x: None,
        )
        broken_storage.close.assert_called_once()

    def test_parallel_mode_handles_pages(self):
        """In parallel mode, the helper dispatches via a
        ThreadPoolExecutor. Verify it doesn't crash with
        parallelism > 1."""
        from apibackuper.cmds.runner import fetch_all_pages

        pages_processed = []

        def on_page(p, content):
            pages_processed.append(p)
            return True

        def fetch_one(page):
            return {
                "page": page,
                "status": 200,
                "content": b'{"x": 1}',
                "error": None,
            }

        storage = MagicMock()

        fetch_all_pages(
            pages=[1, 2, 3],
            parallelism=2,
            fetch_one=fetch_one,
            on_page=on_page,
            should_retry=lambda s: False,
            retry_max_retries=1,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=storage,
            progress_bar=None,
            start_timer=0.0,
            total_pages=3,
            checkpoint_interval=None,
            save_checkpoint=lambda x: None,
        )
        # All three pages processed by the parallel branch.
        assert sorted(pages_processed) == [1, 2, 3]

    def test_500_in_should_retry_set_is_counted(self):
        """When ``should_retry(500)`` is True, a 500 from
        ``fetch_one`` is counted in ``errors['500']`` and the page is
        not passed to ``on_page``. This is the contract that
        ``ProjectBuilder._should_retry`` relies on — see project.py
        line ~1681 where the retry loop lives INSIDE ``fetch_page``,
        but the runner still records the error count based on the
        final status."""
        from apibackuper.cmds.runner import fetch_all_pages

        pages_seen = []

        def fetch_one(page):
            # Page 1: 500 (transient). Page 2: 200 (success).
            if page == 1:
                return {"page": 1, "status": 500, "content": b"", "error": None}
            return {"page": 2, "status": 200, "content": b"{}", "error": None}

        def on_page(p, content):
            pages_seen.append(p)
            return True

        storage = MagicMock()

        errors = fetch_all_pages(
            pages=[1, 2],
            parallelism=1,
            fetch_one=fetch_one,
            on_page=on_page,
            # ``should_retry(500)`` is True — matches the default
            # DEFAULT_ERROR_STATUS_CODES = {500, 502, 503, 504}.
            should_retry=lambda s: s in (500, 502, 503, 504),
            retry_max_retries=0,
            max_consecutive_errors=10,
            continue_on_error=True,
            storage_backend=storage,
            progress_bar=None,
            start_timer=0.0,
            total_pages=2,
            checkpoint_interval=None,
            save_checkpoint=lambda x: None,
        )
        # ``on_page`` was called only for the successful page.
        assert pages_seen == [2]
        # ``should_retry(500)`` is True, so the 500 page was counted
        # in the errors dict.
        assert errors == {"500": 1}
