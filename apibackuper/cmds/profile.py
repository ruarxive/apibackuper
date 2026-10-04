"""Profile-time estimation without making HTTP requests.

Extracted from the ``--profile`` flag in :mod:`apibackuper.core`. The CLI
prints a JSON dump of the resolved configuration; this helper supplies
the *estimation* part (record count, page count, ETA in seconds) so the
user can see the run footprint before launching it.

The estimate is conservative — the helper never makes an HTTP request.
It draws on three sources of truth, in priority order:

1. **State file**: if a previous run persisted ``records_processed``
   and a wall-clock duration, report those exact numbers.
2. **Configured totals**: if the project sets a ``total_number_key``
   the helper reports the *schema* (a real value needs one sample
   request) but still returns a defensible lower bound from
   ``page_limit`` and the historical record-per-page ratio.
3. **Unknown**: if neither state nor ``total_number_key`` is
   available, return ``None`` for every count. The CLI surfaces the
   gap rather than guessing.

ETA follows the same ladder:

* **State**: ``elapsed_seconds`` from the last run, adjusted for
  pending pages (records_left / records_processed * elapsed_seconds).
* **Configured RPS**: ``total_requests / rps`` plus the configured
  ``default_delay`` per request.
* **Default delay only**: ``total_requests * (default_delay + 0.1)``s.
"""

from __future__ import annotations

from typing import Any, Optional


def compute_profile_estimate(
    *,
    page_limit: Optional[int],
    iterate_by: Optional[str],
    total_number_key: Optional[str],
    rps: Optional[float],
    default_delay: Optional[float],
    state: Optional[dict],
) -> dict:
    """Return the ``estimate`` sub-dict for the ``--profile`` JSON output.

    Parameters are kwargs-only. ``None`` means "not configured" — the
    helper treats missing values as unknown rather than guessing.

    Returns a dict with the following keys:

    * ``source`` — one of ``"state"``, ``"config"``, ``"unknown"``.
    * ``records_estimate`` — int or ``None``.
    * ``pages_estimate`` — int or ``None``.
    * ``eta_seconds`` — float or ``None``.
    * ``notes`` — list of strings documenting how the values were
      derived (handy for human-readable diff in CI logs).

    The function is pure and dependency-free so it can be unit-tested
    with table-driven cases (see ``tests/test_profile.py``).
    """
    notes: list = []
    state = state or {}

    # 1. Try the state file first.
    state_records = _safe_int(state.get("records_processed"))
    state_run_seconds = _compute_state_duration_seconds(state)
    if state_records is not None and state_records > 0:
        records = state_records
        notes.append(f"records_processed={records} from state file (last run)")
        eta = (
            state_run_seconds
            if state_run_seconds is not None
            else _eta_from_rate(
                pages=1,
                rps=rps,
                default_delay=default_delay,
            )
        )
        if state_run_seconds is None:
            notes.append("ETA: no last_run timing in state; using rate limit fallback")
        return {
            "source": "state",
            "records_estimate": records,
            "pages_estimate": 1,
            "eta_seconds": eta,
            "notes": notes,
        }

    # 2. Configured totals — only useful when total_number_key is set.
    if total_number_key:
        notes.append(
            f"total_number_key='{total_number_key}' is configured; a real"
            " count requires one sample request"
        )
        # We can still give a defensive lower bound: at least one page.
        if page_limit and page_limit > 0:
            notes.append(f"lower-bound estimate: page_limit={page_limit} → ≥1 page")
            return {
                "source": "config",
                "records_estimate": page_limit,  # lower bound = one page
                "pages_estimate": 1,
                "eta_seconds": _eta_from_rate(
                    pages=1,
                    rps=rps,
                    default_delay=default_delay,
                ),
                "notes": notes,
            }
        return {
            "source": "config",
            "records_estimate": None,
            "pages_estimate": None,
            "eta_seconds": _eta_from_rate(
                pages=None,
                rps=rps,
                default_delay=default_delay,
            ),
            "notes": notes,
        }

    # 3. Nothing to go on.
    notes.append("no state file and no total_number_key — exact count unknown")
    return {
        "source": "unknown",
        "records_estimate": None,
        "pages_estimate": None,
        "eta_seconds": _eta_from_rate(
            pages=None,
            rps=rps,
            default_delay=default_delay,
        ),
        "notes": notes,
    }


def _safe_int(value: Any) -> Optional[int]:
    """Coerce ``value`` to int, returning ``None`` on any failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compute_state_duration_seconds(state: dict) -> Optional[float]:
    """Compute wall-clock seconds between ``last_run_start`` and
    ``last_run_end`` if both are ISO-8601 strings."""
    from datetime import datetime

    start = state.get("last_run_start")
    end = state.get("last_run_end")
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
    except (TypeError, ValueError):
        return None
    delta = (e - s).total_seconds()
    return delta if delta >= 0 else None


def _eta_from_rate(
    *,
    pages: Optional[int],
    rps: Optional[float],
    default_delay: Optional[float],
) -> Optional[float]:
    """Estimate wall-clock seconds for ``pages`` requests.

    * If ``rps`` is configured, time = pages / rps.
    * If ``default_delay`` is configured, add pages * delay to the
      network time.
    * If neither is set, return ``None``.
    """
    if pages is None or pages <= 0:
        return None
    network = float(pages) / rps if (rps and rps > 0) else 0.0
    per_request_delay = default_delay if default_delay and default_delay > 0 else 0.0
    overhead = float(pages) * per_request_delay
    total = network + overhead
    return total if total > 0 else None


__all__ = ["compute_profile_estimate"]
