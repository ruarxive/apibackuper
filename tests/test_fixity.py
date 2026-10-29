"""Fixity manifests and `verify` (openspec add-fixity-manifest)."""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apibackuper.cmds.fixity import MANIFEST_NAME, RUN_RECORD_NAME, config_digest, parse_manifest
from apibackuper.core import app
from apibackuper.storage import build_storage_backend
from apibackuper.storage.session import BackupSession
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
serve = workflow.serve

RECORDS = [{"id": n} for n in range(5)]


def member(builder, name, kind="object"):
    backend = build_storage_backend(builder.storage_type, builder.storage_file, "read")
    try:
        return backend.get_object(name, kind)
    finally:
        backend.close()


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_full_and_update_runs_write_verifiable_manifests(make_project, storage):
    builder = make_project(
        storage,
        project={"update_mode": "by_change_key"},
        params={"change_key_param": "since"},
        data={"change_key": "id"},
    )
    serve(builder, RECORDS)
    builder.run("full")
    listed = parse_manifest(member(builder, MANIFEST_NAME))
    assert sorted(listed) == ["page_1.json", "page_2.json", "page_3.json"]
    for name, value in listed.items():
        assert hashlib.sha256(member(builder, name, "page")).hexdigest() == value
    run = json.loads(member(builder, RUN_RECORD_NAME))
    assert run["mode"] == "full" and run["pages"] == 3 and run["records"] == 5
    assert run["api_total"] == 5 and len(run["config_sha256"]) == 64

    serve(builder, [{"id": 10}])
    builder.update()
    report = builder.verify()
    assert report["ok"]
    generations = {entry["generation"]: entry for entry in report["generations"]}
    update = next(entry for name, entry in generations.items() if name.startswith("runs/"))
    assert generations["(base)"]["verified"] == 3 and update["verified"] == 1


def test_verify_reports_changed_missing_and_unlisted_pages(make_project):
    builder = make_project("filesystem")
    serve(builder, RECORDS)
    builder.run("full")
    root = Path(builder.storage_file)
    (root / "page_2.json").write_text('{"items": [{"id": "tampered"}]}')
    (root / "page_3.json").unlink()
    (root / "page_9.json").write_text('{"items": []}')
    report = builder.verify()
    base = report["generations"][0]
    assert not report["ok"]
    assert base["changed"] == ["page_2.json"]
    assert base["missing"] == ["page_3.json"]
    assert base["unlisted"] == ["page_9.json"]


def test_unlisted_and_unmanifested_pages_fail_only_in_strict_mode(make_project):
    builder = make_project("filesystem")
    serve(builder, RECORDS)
    builder.run("full")
    (Path(builder.storage_file) / MANIFEST_NAME).unlink()
    report = builder.verify()
    assert report["ok"] and not report["generations"][0]["manifest"]
    assert not builder.verify(strict=True)["ok"]


def test_config_hash_ignores_secret_values(make_project):
    first = make_project("zip", auth={"type": "bearer", "token": "one"})
    second = make_project("sqlite", auth={"type": "bearer", "token": "two"})
    second.config._data["storage"] = first.config._data["storage"]
    assert config_digest(first) == config_digest(second)
    second.config._data["settings"]["name"] = "renamed"
    assert config_digest(first) != config_digest(second)


def test_interrupted_publication_writes_missing_manifest(make_project, monkeypatch):
    builder = make_project("filesystem")
    serve(builder, RECORDS)
    publish = BackupSession.publish
    attempts = []

    def interrupted(self):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("publication interrupted")
        return publish(self)

    monkeypatch.setattr(BackupSession, "publish", interrupted)
    with pytest.raises(OSError):
        builder.run("full")
    assert builder._load_checkpoint()["status"] == "publishing"
    # A publication intent written before manifests existed.
    (Path(builder.storage_file + ".partial") / MANIFEST_NAME).unlink()
    builder.http.get.reset_mock()
    builder.run("full", resume=True)
    builder.http.get.assert_not_called()
    assert builder.verify(strict=True)["ok"]


def test_verify_cli_exit_status_and_info(make_project):
    builder = make_project("filesystem")
    serve(builder, RECORDS)
    builder.run("full")
    runner = CliRunner()
    passed = runner.invoke(app, ["verify", "-p", builder.project_path, "--json"])
    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output)["ok"]
    assert builder.info()["verification"]["ok"]
    (Path(builder.storage_file) / "page_1.json").write_text("{}")
    failed = runner.invoke(app, ["verify", "-p", builder.project_path])
    assert failed.exit_code == 1
    assert "changed: page_1.json" in failed.output
    assert not builder.info()["verification"]["ok"]
