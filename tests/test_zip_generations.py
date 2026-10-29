"""Per-generation ZIP archives (openspec update-zip-generation-archives)."""

import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from apibackuper.storage import ZipStorageBackend
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
serve = workflow.serve

UPDATE = {
    "project": {"update_mode": "by_change_key"},
    "params": {"change_key_param": "since"},
    "data": {"change_key": "id"},
}
BASE = [{"id": n} for n in range(5)]


def exported(builder, path):
    builder.export("jsonl", str(path))
    return sorted(json.loads(line)["id"] for line in path.read_text().splitlines())


def fingerprint(path):
    status = os.stat(path)
    return status.st_ino, status.st_size, status.st_mtime_ns


def test_update_writes_its_own_archive_and_leaves_base_untouched(make_project, tmp_path):
    builder = make_project(**UPDATE)
    serve(builder, BASE)
    builder.run("full")
    before = fingerprint(builder.storage_file)
    serve(builder, [{"id": 10}, {"id": 11}])
    builder.update()
    assert fingerprint(builder.storage_file) == before
    runs = Path(builder.storage_file + ".runs")
    archives = sorted(runs.glob("*.zip"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        run_id = archives[0].stem
        assert f"runs/{run_id}/page_1.json" in archive.namelist()
        assert f"runs/{run_id}/manifest-sha256.txt" in archive.namelist()
    assert exported(builder, tmp_path / "all.jsonl") == [0, 1, 2, 3, 4, 10, 11]
    assert builder.verify(strict=True)["ok"]
    assert builder.info(stats=True)["statistics"]["storage"]["generation_archives"] == 1


def test_legacy_generations_inside_the_base_archive_stay_readable(make_project, tmp_path):
    builder = make_project(**UPDATE)
    serve(builder, BASE)
    builder.run("full")
    legacy = ZipStorageBackend(builder.storage_file)
    legacy._base.save_page("runs/old/page_1.json", json.dumps({"items": [{"id": 7}]}).encode())
    legacy.close()
    with ZipFile(builder.storage_file) as archive:
        assert "runs/old/page_1.json" in archive.namelist()
    serve(builder, [{"id": 10}])
    builder.update()
    assert exported(builder, tmp_path / "mixed.jsonl") == [0, 1, 2, 3, 4, 7, 10]


def test_full_backup_retires_previous_generations(make_project, tmp_path):
    builder = make_project(**UPDATE)
    serve(builder, BASE)
    builder.run("full")
    serve(builder, [{"id": 10}])
    builder.update()
    serve(builder, [{"id": 20}, {"id": 21}])
    builder.run("full")
    assert not os.path.exists(builder.storage_file + ".runs")
    assert exported(builder, tmp_path / "fresh.jsonl") == [20, 21]


def test_interrupted_full_publication_completes_on_resume(make_project, monkeypatch):
    builder = make_project(**UPDATE)
    serve(builder, BASE)
    builder.run("full")
    serve(builder, [{"id": 10}])
    builder.update()
    serve(builder, [{"id": 20}])
    save_state = builder._save_state
    attempts = []

    def interrupted(state, strict=False):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("state commit interrupted")
        return save_state(state, strict=strict)

    monkeypatch.setattr(builder, "_save_state", interrupted)
    with pytest.raises(OSError):
        builder.run("full")
    assert os.path.isdir(builder.storage_file + ".runs.previous")
    builder.http.get.reset_mock()
    builder.run("full", resume=True)
    builder.http.get.assert_not_called()
    assert not os.path.exists(builder.storage_file + ".runs")
    assert not os.path.exists(builder.storage_file + ".runs.previous")
    assert builder._load_state()["records_processed"] == 1
