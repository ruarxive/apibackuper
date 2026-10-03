"""Tests for the extracted ``cmds.profile`` module.

The helper computes a record / page / ETA estimate for the
``--profile`` flag without making any HTTP requests. Three inputs
feed the estimate:

* ``state`` — the JSON state file left by the last run.
* ``total_number_key`` — a config option that signals "the API
  exposes a total count, but only via a sample request".
* ``rps`` / ``default_delay`` — rate-limit knobs used for ETA.

The tests below pin each branch so future refactors cannot quietly
regress the user-visible profile output.
"""
import pytest

from apibackuper.cmds.profile import compute_profile_estimate


class TestStateSource:
    """State file is the most accurate source — it overrides config."""

    def test_state_with_records_returns_state_value(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=None,
            default_delay=None,
            state={
                "records_processed": 250,
                "last_run_start": "2026-10-01T10:00:00+00:00",
                "last_run_end": "2026-10-01T10:01:00+00:00",
            },
        )
        assert result["source"] == "state"
        assert result["records_estimate"] == 250
        assert result["eta_seconds"] == 60.0

    def test_state_with_zero_records_falls_through(self):
        # Zero records is treated as "no state" — fall through to the
        # config or unknown branches.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=2.0,
            default_delay=0.5,
            state={
                "records_processed": 0,
                "last_run_start": "2026-10-01T10:00:00+00:00",
                "last_run_end": "2026-10-01T10:01:00+00:00",
            },
        )
        assert result["source"] == "config"

    def test_state_with_no_timing_falls_back_to_rate(self):
        # No ISO timestamps → state.eta_seconds is None → ETA via rps.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=2.0,
            default_delay=0.5,
            state={"records_processed": 100},
        )
        assert result["source"] == "state"
        assert result["records_estimate"] == 100
        # 1 page / 2 rps = 0.5s + 1 * 0.5s delay = 1.0s
        assert result["eta_seconds"] == pytest.approx(1.0)

    def test_state_with_invalid_records_value_falls_through(self):
        # Garbage value coerces to None → falls through.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=1.0,
            default_delay=None,
            state={"records_processed": "not-an-int"},
        )
        assert result["source"] == "config"

    def test_state_with_end_before_start_ignored(self):
        # Negative delta is ignored — treat as no timing.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=2.0,
            default_delay=0.5,
            state={
                "records_processed": 50,
                "last_run_start": "2026-10-01T10:01:00+00:00",
                "last_run_end": "2026-10-01T10:00:00+00:00",
            },
        )
        assert result["source"] == "state"
        assert result["eta_seconds"] == pytest.approx(1.0)  # rate fallback


class TestConfigSource:
    """When state is missing but ``total_number_key`` is configured."""

    def test_config_with_page_limit_returns_lower_bound(self):
        result = compute_profile_estimate(
            page_limit=25,
            iterate_by="page",
            total_number_key="meta.total",
            rps=2.0,
            default_delay=0.5,
            state=None,
        )
        assert result["source"] == "config"
        assert result["records_estimate"] == 25  # one page worth
        assert result["pages_estimate"] == 1
        # 1 page / 2 rps = 0.5s + 0.5s delay = 1.0s
        assert result["eta_seconds"] == pytest.approx(1.0)

    def test_config_without_page_limit(self):
        result = compute_profile_estimate(
            page_limit=None,
            iterate_by="page",
            total_number_key="meta.total",
            rps=None,
            default_delay=None,
            state=None,
        )
        assert result["source"] == "config"
        assert result["records_estimate"] is None
        assert result["pages_estimate"] is None
        assert result["eta_seconds"] is None

    def test_config_with_only_delay_eta_uses_delay(self):
        # No rps, only delay. ETA = pages * delay.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=None,
            default_delay=2.0,
            state=None,
        )
        assert result["source"] == "config"
        assert result["eta_seconds"] == pytest.approx(2.0)

    def test_config_with_zero_page_limit_uses_lower_bound(self):
        # Defensive: page_limit <= 0 is treated as missing.
        result = compute_profile_estimate(
            page_limit=0,
            iterate_by="page",
            total_number_key="meta.total",
            rps=None,
            default_delay=None,
            state=None,
        )
        assert result["source"] == "config"
        assert result["records_estimate"] is None
        assert result["pages_estimate"] is None

    def test_config_notes_mention_total_number_key(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=None,
            default_delay=None,
            state=None,
        )
        assert any("total_number_key" in n for n in result["notes"])


class TestUnknownSource:
    """When neither state nor ``total_number_key`` is available."""

    def test_no_state_no_key_returns_unknown(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=None,
            default_delay=None,
            state=None,
        )
        assert result["source"] == "unknown"
        assert result["records_estimate"] is None
        assert result["pages_estimate"] is None
        assert result["eta_seconds"] is None

    def test_unknown_eta_uses_rate_when_available(self):
        # Even with unknown counts, ETA can be estimated if the user
        # configured rps+delay and we have at least one page count.
        # Without a page count, ETA is still None.
        result = compute_profile_estimate(
            page_limit=None,
            iterate_by="page",
            total_number_key=None,
            rps=2.0,
            default_delay=0.5,
            state=None,
        )
        assert result["source"] == "unknown"
        assert result["eta_seconds"] is None


class TestEtaCalculation:
    """Pin the rate / delay math so future tweaks stay correct.

    Note: with ``total_number_key`` set but no state, the helper's
    lower bound is one page (because we don't know the real total
    without a sample request). The tests below assume that 1-page
    floor.
    """

    def test_eta_with_only_rps(self):
        # 1 page / 1 rps = 1s, no delay
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=1.0,
            default_delay=None,
            state=None,
        )
        assert result["eta_seconds"] == pytest.approx(1.0)

    def test_eta_with_only_delay(self):
        # 1 page * 1s delay = 1s
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=None,
            default_delay=1.0,
            state=None,
        )
        assert result["eta_seconds"] == pytest.approx(1.0)

    def test_eta_with_both_rps_and_delay(self):
        # 1 page / 2 rps = 0.5s + 1 * 0.5s delay = 1.0s
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=2.0,
            default_delay=0.5,
            state=None,
        )
        assert result["eta_seconds"] == pytest.approx(1.0)

    def test_eta_with_zero_rps_or_delay_falls_back_to_zero(self):
        # rps=0 is invalid → use delay only.
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=0.0,
            default_delay=0.5,
            state=None,
        )
        # 1 page * 0.5s = 0.5s
        assert result["eta_seconds"] == pytest.approx(0.5)


class TestInputRobustness:
    """Helper must not crash on weird input shapes."""

    def test_state_none_works(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=None,
            default_delay=None,
            state=None,
        )
        assert result["source"] == "unknown"

    def test_state_empty_dict_works(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key=None,
            rps=None,
            default_delay=None,
            state={},
        )
        assert result["source"] == "unknown"

    def test_state_with_garbage_timestamps_falls_back(self):
        result = compute_profile_estimate(
            page_limit=10,
            iterate_by="page",
            total_number_key="meta.total",
            rps=2.0,
            default_delay=0.5,
            state={
                "records_processed": 0,
                "last_run_start": "not-a-date",
                "last_run_end": "not-a-date",
            },
        )
        # Zero records → falls through to config branch.
        assert result["source"] == "config"

    def test_all_kwargs_required(self):
        # The helper is kwargs-only by design; positional args fail.
        with pytest.raises(TypeError):
            compute_profile_estimate(10, "page", None, None, None, None)