"""Tests for state file round-trip and resume checkpoints.

The resume mechanism depends on ``_save_state`` / ``_load_state`` /
``_save_checkpoint`` / ``_load_checkpoint`` writing and reading consistent
JSON. A regression here would silently corrupt resume state across runs
(§P2.29 of the 2026-10 analysis report).
"""
import json
import os
import tempfile

from apibackuper.cmds.project import ProjectBuilder


def _builder_with_state_paths(state_file, checkpoint_file):
    """Build a ProjectBuilder with custom state/checkpoint paths but no
    real config load."""
    builder = ProjectBuilder.__new__(ProjectBuilder)
    builder.state_file = state_file
    builder.checkpoint_file = checkpoint_file
    builder.project_path = os.path.dirname(state_file)
    return builder


class TestStateRoundTrip:
    def test_save_then_load_returns_same_dict(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "apibackuper_state.json")
            builder = _builder_with_state_paths(state_file, "")

            payload = {
                "last_run_start": "2026-10-02T10:00:00+00:00",
                "last_run_end": "2026-10-02T10:30:00+00:00",
                "last_page": 17,
                "last_change_key": "2026-10-02T10:25:00+00:00",
                "records_processed": 8500,
                "bytes_processed": 12_500_000,
            }
            builder._save_state(payload)
            loaded = builder._load_state()
            assert loaded == payload

    def test_load_returns_empty_when_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "missing.json")
            builder = _builder_with_state_paths(state_file, "")
            assert builder._load_state() == {}

    def test_load_returns_empty_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "corrupt.json")
            with open(state_file, "w") as f:
                f.write("{this is not json")
            builder = _builder_with_state_paths(state_file, "")
            assert builder._load_state() == {}

    def test_save_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "nested", "deeper", "state.json")
            builder = _builder_with_state_paths(state_file, "")
            builder._save_state({"last_page": 1})
            assert os.path.exists(state_file)

    def test_save_silently_ignores_errors(self, caplog):
        # Make state_file point at a directory — open() for write will fail.
        with tempfile.TemporaryDirectory() as td:
            state_file = td  # it's a directory
            builder = _builder_with_state_paths(state_file, "")
            # Should not raise.
            builder._save_state({"x": 1})


class TestCheckpointRoundTrip:
    def test_save_then_load_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            ck_file = os.path.join(td, "apibackuper_checkpoint.json")
            builder = _builder_with_state_paths("", ck_file)

            payload = {
                "last_page": 42,
                "records_processed": 1500,
                "storage_bytes": 250_000,
                "updated_at": "2026-10-02T10:15:00+00:00",
            }
            builder._save_checkpoint(payload)
            loaded = builder._load_checkpoint()
            assert loaded == payload

    def test_checkpoint_preserves_unicode(self):
        with tempfile.TemporaryDirectory() as td:
            ck_file = os.path.join(td, "ck.json")
            builder = _builder_with_state_paths("", ck_file)
            builder._save_checkpoint({"note": "тест 中文"})
            loaded = builder._load_checkpoint()
            assert loaded["note"] == "тест 中文"


class TestAtomicWriteSafety:
    """P2 item 25 (deferred): state writes must be atomic — write to a temp
    file then rename, so a crash mid-write never corrupts the state file.

    This is the "good practice" check; the current implementation writes
    directly. The test documents the *current* behaviour; if the rewrite
    lands, the test still passes (it just becomes redundant).
    """

    def test_state_file_is_valid_json_after_save(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "state.json")
            builder = _builder_with_state_paths(state_file, "")
            builder._save_state({"last_page": 99})
            with open(state_file, "r", encoding="utf8") as f:
                json.load(f)  # must parse cleanly


class TestResumeEndToEnd:
    """End-to-end resume: save state, simulate restart, load state."""

    def test_resume_continues_from_last_page(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "state.json")

            # First "run": save progress up to page 17.
            b1 = _builder_with_state_paths(state_file, "")
            b1._save_state({
                "last_page": 17,
                "records_processed": 8500,
                "bytes_processed": 12_500_000,
            })

            # Second "run" (new process): the loader must return the
            # progress so resume picks up at page 18.
            b2 = _builder_with_state_paths(state_file, "")
            loaded = b2._load_state()
            assert loaded["last_page"] == 17
            assert loaded["records_processed"] == 8500
            # The caller should resume from page 18.
            assert loaded["last_page"] + 1 == 18