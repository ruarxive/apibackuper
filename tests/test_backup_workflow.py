"""Exercise commands against real storage, including interrupted backups."""

import json
from unittest.mock import Mock

import pytest
import requests
import yaml
from typer.testing import CliRunner

from apibackuper.cmds.project import ProjectBuilder
from apibackuper.core import app
from apibackuper.storage import build_storage_backend


def reply(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    response.headers = {}
    return response


@pytest.fixture
def make_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectBuilder, "enable_logging", lambda self: None)
    monkeypatch.setattr("apibackuper.cmds.project.time.sleep", lambda _: None)

    def make(storage="zip", **sections):
        path = tmp_path / storage
        path.mkdir(exist_ok=True)
        config = {
            "settings": {"name": "workflow", "checkpoint_interval_pages": 1},
            "project": {
                "url": "https://api.example.test/items",
                "http_mode": "GET",
                "default_delay": 0,
                "retry_count": 0,
                "retry_delay": 0,
            },
            "params": {"page_size_limit": 2, "page_number_param": "page"},
            "data": {"data_key": "items", "total_number_key": "total"},
            "storage": {
                "storage_type": storage,
                "storage_path": "storage.db" if storage == "sqlite" else "storage",
            },
        }
        for name, values in sections.items():
            config[name].update(values) if name in config else config.update({name: values})
        (path / "apibackuper.yaml").write_text(yaml.safe_dump(config))
        builder = ProjectBuilder(str(path))
        builder.http = Mock(spec=requests.Session)
        return builder

    return make


def serve(builder, records, fail_page=None, status=200):
    def get(url, **kwargs):
        page = int(kwargs.get("params", {}).get("page", 1))
        if page == fail_page:
            raise requests.Timeout("interrupted request")
        return reply({"items": records[(page - 1) * 2 : page * 2], "total": len(records)}, status)

    builder.http.get.side_effect = get


def stored(builder):
    backend = build_storage_backend(builder.storage_type, builder.storage_file, "continue")
    try:
        return [
            item
            for name in backend.list_objects("page")
            for item in json.loads(backend.get_object(name))["items"]
        ]
    finally:
        backend.close()


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_full_failure_preserves_old_backup_then_resume_publishes_all_pages(make_project, storage):
    builder = make_project(storage)
    old = [{"id": 1}, {"id": 2}, {"id": 3}]
    new = [{"id": 10}, {"id": 11}, {"id": 12}]
    serve(builder, old)
    builder.run("full")
    state_before = builder._load_state()
    serve(builder, new, fail_page=2)
    with pytest.raises(RuntimeError):
        builder.run("full")
    assert stored(builder) == old
    assert builder._load_state() == state_before
    checkpoint = builder._load_checkpoint()
    assert checkpoint["next_page"] == 2
    assert checkpoint["records_processed"] == 2
    serve(builder, new)
    builder.run("full", resume=True)
    assert stored(builder) == new
    assert builder._load_state()["records_processed"] == 3


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_update_retains_previous_generation_and_exports_all_records(
    make_project, storage, tmp_path
):
    builder = make_project(
        storage,
        project={"update_mode": "by_change_key"},
        params={"change_key_param": "since"},
        data={"change_key": "id"},
    )
    old = [{"id": 1}, {"id": 2}, {"id": 3}]
    new = [{"id": 101}, {"id": 102}]
    serve(builder, old)
    builder.run("full")
    serve(builder, new)
    builder.update()
    assert sorted(item["id"] for item in stored(builder)) == [1, 2, 3, 101, 102]
    assert all(call.kwargs["params"]["since"] == 3 for call in builder.http.get.call_args_list[2:])
    output = tmp_path / "export.jsonl"
    builder.export("jsonl", str(output))
    assert sorted(json.loads(line)["id"] for line in output.read_text().splitlines()) == [
        1,
        2,
        3,
        101,
        102,
    ]


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_gap_keeps_state_and_resume_reuses_update_generation(make_project, storage):
    builder = make_project(storage, error_handling={"continue_on_error": True})
    serve(builder, [{"id": 0}])
    builder.run("full")
    baseline = builder._load_state()
    records = [{"id": n} for n in range(10, 16)]
    serve(builder, records, fail_page=2)
    with pytest.raises(RuntimeError):
        builder.update()
    assert builder._load_state() == baseline
    checkpoint = builder._load_checkpoint()
    assert checkpoint["last_page"] == 1
    assert checkpoint["next_page"] == 2
    generation = checkpoint["run_id"]
    serve(builder, records)
    builder.update(resume=True)
    assert builder._load_checkpoint()["run_id"] == generation
    assert sorted(item["id"] for item in stored(builder)) == [0, 10, 11, 12, 13, 14, 15]


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_legacy_checkpoint_does_not_reset_existing_pages(make_project, storage):
    builder = make_project(storage)
    from pathlib import Path

    Path(builder.storage_file).parent.mkdir(parents=True, exist_ok=True)
    backend = build_storage_backend(storage, builder.storage_file, "full")
    backend.save_page("page_1.json", b'{"items":[{"id":1},{"id":2}],"total":3}')
    backend.close()
    builder._save_checkpoint({"last_page": 2})
    serve(builder, [{"id": 1}, {"id": 2}, {"id": 3}])
    builder.run("full", resume=True)
    assert sorted(item["id"] for item in stored(builder)) == [1, 2, 3]


def test_root_array_without_data_key(make_project, tmp_path):
    builder = make_project(data={"data_key": "", "total_number_key": ""})
    builder.data_key = None
    builder.http.get.side_effect = [reply([{"id": 1}, {"id": 2}]), reply([{"id": 3}])]
    builder.run("full")
    output = tmp_path / "root.jsonl"
    builder.export("jsonl", str(output))
    assert [json.loads(line)["id"] for line in output.read_text().splitlines()] == [1, 2, 3]
    assert builder._load_state()["records_processed"] == 3


def test_forbidden_response_is_failed_cli_exit(make_project, monkeypatch):
    builder = make_project()
    serve(builder, [], status=403)
    monkeypatch.setattr("apibackuper.core.ProjectBuilder", lambda _: builder)
    result = CliRunner().invoke(app, ["run", "full"])
    assert result.exit_code == 1
    assert "403" in result.output
    assert builder._load_state() == {}


def test_flat_params_reach_valid_url_with_existing_query(make_project):
    builder = make_project(
        project={"url": "https://api.example.test/items?lang=ru"},
        params={"force_flat_params": True},
    )
    serve(builder, [{"id": 1}])
    builder.run("full")
    from urllib.parse import parse_qs, urlsplit

    url = builder.http.get.call_args.args[0]
    assert urlsplit(url).path == "/items"
    assert parse_qs(urlsplit(url).query) == {"lang": ["ru"], "page": ["1"]}


def test_yaml_retry_list_loads_and_fractional_delay_validates(make_project):
    builder = make_project(
        project={"default_delay": 0.5}, error_handling={"retry_on_errors": [429, 500, 503]}
    )
    assert builder.error_retry_codes == [429, 500, 503]
    assert builder.validate_config()[0]


def test_transport_error_is_retried_on_initial_page(make_project):
    builder = make_project(project={"retry_count": 1})
    builder.http.get.side_effect = [
        requests.Timeout("temporary"),
        reply({"items": [{"id": 1}], "total": 1}),
    ]
    builder.run("full")
    assert builder.http.get.call_count == 2
    assert stored(builder) == [{"id": 1}]


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_interrupted_state_commit_recovers_without_http(make_project, monkeypatch, storage):
    builder = make_project(storage)
    serve(builder, [{"id": 1}, {"id": 2}, {"id": 3}])
    save = builder._save_state
    monkeypatch.setattr(builder, "_save_state", Mock(side_effect=OSError("state disk unavailable")))
    with pytest.raises(OSError):
        builder.run("full")
    assert builder._load_checkpoint()["status"] == "publishing"
    before = builder.http.get.call_count
    monkeypatch.setattr(builder, "_save_state", save)
    builder.run("full", resume=True)
    assert builder.http.get.call_count == before
    assert stored(builder) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert builder._load_state()["records_processed"] == 3
    assert builder._load_checkpoint()["status"] == "complete"


def test_zip_journal_survives_abrupt_process_exit(tmp_path):
    import subprocess
    import sys
    from zipfile import ZipFile

    archive = str(tmp_path / "backup.zip")
    script = "\n".join(
        [
            "import os, sys",
            "from apibackuper.storage import ZipStorageBackend",
            "backend = ZipStorageBackend(sys.argv[1], mode='w')",
            "backend.save_page('page_1.json', b'first')",
            "backend.flush()",
            "backend.save_page('page_2.json', b'second')",
            "os._exit(17)",
        ]
    )
    result = subprocess.run([sys.executable, "-c", script, archive])
    assert result.returncode == 17
    with ZipFile(archive) as raw:
        assert raw.testzip() is None
    backend = build_storage_backend("zip", archive, "continue")
    assert backend.get_object("page_1.json") == b"first"
    assert backend.get_object("page_2.json") == b"second"
    backend.save_page("page_2.json", b"replayed")
    backend.close()
    with ZipFile(archive) as raw:
        assert raw.namelist() == ["page_1.json", "page_2.json"]
        assert raw.read("page_2.json") == b"replayed"


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_follow_uses_auth_retry_timeout_and_exports_details(make_project, storage, tmp_path):
    builder = make_project(
        storage,
        auth={"type": "bearer", "token": "test-bearer"},
        follow={
            "follow_mode": "item",
            "follow_item_key": "id",
            "follow_param": "id",
            "follow_pattern": "https://api.example.test/detail",
        },
    )
    serve(builder, [{"id": 1}])
    builder.run("full")
    builder.retry_max_retries = 1
    builder.rate_limiter = Mock()
    builder.http.get.reset_mock()
    builder.http.get.side_effect = [reply({}, 503), reply({"id": 1, "detail": "captured"})]
    builder.follow("full")
    assert builder.http.get.call_count == 2
    assert builder.rate_limiter.wait_if_needed.call_count == 2
    for call in builder.http.get.call_args_list:
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-bearer"
        assert call.kwargs["timeout"] == (builder.connect_timeout, builder.read_timeout)
    output = tmp_path / "follow.jsonl"
    builder.export("jsonl", str(output))
    assert json.loads(output.read_text()) == {"id": 1, "detail": "captured"}
    with pytest.raises(ValueError):
        builder.export("jsonl", builder.details_storage_file)


def test_failed_follow_preserves_previous_details(make_project):
    from zipfile import ZipFile

    builder = make_project(
        follow={
            "follow_mode": "item",
            "follow_item_key": "id",
            "follow_param": "id",
            "follow_pattern": "https://api.example.test/detail",
        }
    )
    serve(builder, [{"id": 1}])
    builder.run("full")
    builder.http.get.side_effect = [reply({"id": 1, "detail": "old"})]
    builder.follow("full")
    builder.http.get.side_effect = [reply({}, 403)]
    with pytest.raises(RuntimeError):
        builder.follow("full")
    with ZipFile(builder.details_storage_file) as archive:
        assert json.loads(archive.read("1.json"))["detail"] == "old"


def test_filesystem_export_cannot_replace_source_page(make_project):
    from pathlib import Path

    builder = make_project("filesystem")
    serve(builder, [{"id": 1}])
    builder.run("full")
    page = Path(builder.storage_file) / "page_1.json"
    before = page.read_bytes()
    with pytest.raises(ValueError):
        builder.export("jsonl", str(page))
    assert page.read_bytes() == before


def test_nonpaginated_object_endpoint(make_project):
    builder = make_project()
    builder.page_number_param = None
    builder.data_key = None
    builder.total_number_key = ""
    builder.http.get.return_value = reply({"id": 1, "name": "single"})
    builder.run("full")
    assert builder.http.get.call_count == 1
    assert builder._load_state()["records_processed"] == 1


def test_xml_pages_are_normalized_and_exportable(make_project, tmp_path):
    builder = make_project(
        project={"resp_type": "xml"},
        data={"data_key": "root.item", "total_number_key": "root.total"},
    )
    first = reply({})
    first._content = b"<root><total>3</total><item><id>1</id></item><item><id>2</id></item></root>"
    second = reply({})
    second._content = b"<root><total>3</total><item><id>3</id></item></root>"
    builder.http.get.side_effect = [first, second]
    builder.run("full")
    output = tmp_path / "xml.jsonl"
    builder.export("jsonl", str(output))
    assert [json.loads(line)["id"] for line in output.read_text().splitlines()] == ["1", "2", "3"]


def test_files_download_uses_shared_auth_and_controls(make_project):
    from pathlib import Path
    from zipfile import ZipFile

    builder = make_project(
        auth={"type": "bearer", "token": "file-secret"},
        files={
            "fetch_mode": "prefix",
            "keys": "file",
            "root_url": "https://files.example.test/",
            "storage_mode": "id",
            "file_storage_type": "zip",
        },
    )
    serve(builder, [{"id": 1, "file": "document"}])
    builder.run("full")
    builder.http.get.reset_mock()
    downloaded = reply({"file": "content"})
    builder.http.get.side_effect = [downloaded]
    builder.getfiles()
    request = builder.http.get.call_args
    assert request.kwargs["headers"]["Authorization"] == "Bearer file-secret"
    assert request.kwargs["timeout"] == (builder.connect_timeout, builder.read_timeout)
    with ZipFile(Path(builder.storagedir) / "files.zip") as archive:
        assert archive.read("document") == downloaded.content


@pytest.mark.parametrize("format", ["gzip", "zstd", "parquet"])
def test_export_formats_filter_and_project_actual_records(make_project, tmp_path, format):
    builder = make_project()
    serve(builder, [{"id": 1, "name": "one"}, {"id": 2, "name": "two"}, {"id": 3, "name": "three"}])
    builder.run("full")
    output = tmp_path / ("records." + format)
    if format == "parquet":
        parquet = pytest.importorskip("pyarrow.parquet")
        builder.export(format, str(output), fields=["id"], where="id >= 2")
        records = parquet.read_table(output).to_pylist()
    else:
        builder.export(format, str(output), fields=["id"], where="id >= 2")
        if format == "gzip":
            import gzip

            with gzip.open(output, "rt") as reader:
                text = reader.read()
        else:
            import zstandard

            with open(output, "rb") as reader:
                text = zstandard.ZstdDecompressor().stream_reader(reader).read().decode()
        records = [json.loads(line) for line in text.splitlines()]
    assert records == [{"id": 2}, {"id": 3}]


def test_missing_environment_variable_cli_names_variable(make_project, monkeypatch):
    from pathlib import Path

    builder = make_project()
    path = Path(builder.config_filename)
    config = yaml.safe_load(path.read_text())
    config["auth"] = {"type": "bearer", "token": "${AUDIT_MISSING_TOKEN}"}
    path.write_text(yaml.safe_dump(config))
    monkeypatch.delenv("AUDIT_MISSING_TOKEN", raising=False)
    result = CliRunner().invoke(app, ["run", "full", "-p", builder.project_path])
    assert result.exit_code == 2
    assert "AUDIT_MISSING_TOKEN" in result.output


def test_invalid_execution_configuration_leaves_backup_untouched(make_project):
    from pathlib import Path

    builder = make_project()
    serve(builder, [{"id": 1}])
    builder.run("full")
    before = Path(builder.storage_file).read_bytes()
    config = yaml.safe_load(Path(builder.config_filename).read_text())
    config["project"].pop("url")
    Path(builder.config_filename).write_text(yaml.safe_dump(config))
    invalid = ProjectBuilder(builder.project_path)
    with pytest.raises(ValueError, match="Invalid project configuration"):
        invalid.run("full")
    assert Path(builder.storage_file).read_bytes() == before


@pytest.mark.parametrize("storage", ["zip", "sqlite"])
def test_export_rejects_source_through_parent_symlink(make_project, tmp_path, storage):
    from pathlib import Path

    builder = make_project(storage)
    serve(builder, [{"id": 1}])
    builder.run("full")
    source = Path(builder.storage_file)
    alias = tmp_path / "alias"
    alias.symlink_to(source.parent, target_is_directory=True)
    before = source.read_bytes()
    with pytest.raises(ValueError):
        builder.export("jsonl", str(alias / source.name))
    assert source.read_bytes() == before


def test_new_full_backup_does_not_inherit_old_interrupted_zip_journal(make_project):
    from apibackuper.storage import ZipStorageBackend

    builder = make_project()
    serve(builder, [{"id": 1}])
    builder.run("full")
    interrupted = ZipStorageBackend(builder.storage_file)
    interrupted.save_page("page_1.json", b'{"items":[{"id":99}],"total":1}')
    interrupted._zip.close()  # Simulate an exited process: keep the durable sidecar.
    serve(builder, [{"id": 2}])
    builder.run("full")
    assert stored(builder) == [{"id": 2}]


def test_zip_compaction_failure_can_be_retried(tmp_path, monkeypatch):
    import os
    from apibackuper.storage import ZipStorageBackend

    path = str(tmp_path / "archive.zip")
    backend = ZipStorageBackend(path, mode="w")
    backend.save_page("page_1.json", b"one")
    backend.close()
    backend = ZipStorageBackend(path)
    backend.save_page("page_2.json", b"two")
    replace = os.replace
    monkeypatch.setattr(os, "replace", Mock(side_effect=OSError("publication interrupted")))
    with pytest.raises(OSError):
        backend.close()
    monkeypatch.setattr(os, "replace", replace)
    backend.close()
    reader = ZipStorageBackend(path, mode="r")
    assert reader.get_object("page_1.json") == b"one"
    assert reader.get_object("page_2.json") == b"two"
    reader.close()


def test_oauth_refresh_diagnostics_do_not_echo_credentials(make_project, caplog):
    builder = make_project(
        auth={
            "type": "oauth2",
            "token": "private-access-token",
            "refresh_token": "private-refresh-token",
            "auth_url": "https://auth.example.test/token",
        }
    )
    builder.http.get.return_value = reply({}, 401)
    builder.http.post.return_value = reply({"diagnostic": "private-refresh-token"}, 400)
    with pytest.raises(RuntimeError):
        builder._request(builder.start_url)
    assert "private-access-token" not in caplog.text
    assert "private-refresh-token" not in caplog.text
    assert builder.http.post.call_args.kwargs["data"]["refresh_token"] == "private-refresh-token"


DETAIL_RULE = {
    "follow_mode": "item",
    "follow_item_key": "id",
    "follow_param": "id",
    "follow_pattern": "https://api.example.test/detail",
}


def test_filesystem_full_backup_keeps_follow_details(make_project):
    from zipfile import ZipFile

    builder = make_project("filesystem", follow=DETAIL_RULE)
    serve(builder, [{"id": 1}])
    builder.run("full")
    builder.http.get.side_effect = [reply({"id": 1, "detail": "kept"})]
    builder.follow("full")
    serve(builder, [{"id": 1}])
    builder.run("full")
    with ZipFile(builder.details_storage_file) as archive:
        assert json.loads(archive.read("1.json"))["detail"] == "kept"


def test_capped_page_size_fails_instead_of_publishing_partial_backup(make_project):
    builder = make_project(params={"page_size_limit": 5})
    serve(builder, [{"id": n} for n in range(6)])
    with pytest.raises(RuntimeError, match="page_size_limit"):
        builder.run("full")
    assert not builder._load_state()
    assert builder._load_checkpoint()["status"] == "running"


def test_without_count_metadata_collects_until_short_page(make_project, monkeypatch):
    monkeypatch.setattr("apibackuper.cmds.runner.DEFAULT_NUMBER_OF_PAGES", 2)
    builder = make_project()
    builder.total_number_key = ""
    records = [{"id": n} for n in range(7)]
    serve(builder, records)
    builder.run("full")
    assert stored(builder) == records


def test_ignored_page_parameter_is_reported(make_project):
    builder = make_project()
    builder.total_number_key = ""
    builder.http.get.side_effect = lambda url, **kwargs: reply({"items": [{"id": 1}, {"id": 2}]})
    with pytest.raises(ValueError, match="ignore the pagination parameter"):
        builder.run("full")


def test_rate_limited_page_is_retried_by_default(make_project):
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    builder = make_project(project={"retry_count": 1})
    assert 429 in builder.retry_on_status and 504 in builder.retry_on_status
    limited = reply({}, 429)
    limited.headers = {"Retry-After": format_datetime(datetime.now(timezone.utc) + timedelta(60))}
    assert 59 * 86400 < builder._get_retry_delay(1, limited) <= 60 * 86400
    builder.http.get.side_effect = [limited, reply({"items": [{"id": 1}], "total": 1})]
    builder.run("full")
    assert stored(builder) == [{"id": 1}]


def test_follow_records_missing_objects_and_publishes_the_rest(make_project):
    from zipfile import ZipFile

    builder = make_project(follow=DETAIL_RULE)
    serve(builder, [{"id": 1}, {"id": 2}])
    builder.run("full")

    def detail(url, **kwargs):
        key = kwargs["params"]["id"]
        return reply({}, 404) if key == 2 else reply({"id": key, "detail": True})

    builder.http.get.side_effect = detail
    builder.follow("full")
    with ZipFile(builder.details_storage_file) as archive:
        assert archive.namelist() == ["1.json"]
    missing = builder.details_storage_file[: -len(".zip")] + ".missing.json"
    with open(missing, encoding="utf8") as handle:
        assert json.load(handle) == [{"key": 2, "page": 1, "status": 404}]
    builder.http.get.reset_mock()
    builder.follow("continue")
    assert [call.kwargs["params"]["id"] for call in builder.http.get.call_args_list] == [2]


def test_interrupted_run_resumes_after_last_saved_page(make_project):
    builder = make_project(settings={"checkpoint_interval_pages": 0})
    records = [{"id": n} for n in range(6)]

    def get(url, **kwargs):
        page = int(kwargs["params"]["page"])
        if page == 3:
            raise KeyboardInterrupt
        return reply({"items": records[(page - 1) * 2 : page * 2], "total": len(records)})

    builder.http.get.side_effect = get
    with pytest.raises(KeyboardInterrupt):
        builder.run("full")
    assert builder._load_checkpoint()["next_page"] == 3
    serve(builder, records)
    builder.http.get.reset_mock()
    builder.run("full", resume=True)
    assert [call.kwargs["params"]["page"] for call in builder.http.get.call_args_list] == [3]
    assert stored(builder) == records


def test_checkpoint_interval_defaults_to_every_page(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectBuilder, "enable_logging", lambda self: None)
    config = {
        "settings": {"name": "defaults"},
        "project": {"url": "https://api.example.test/items", "http_mode": "GET"},
        "params": {"page_size_limit": 2},
        "data": {},
        "storage": {"storage_type": "zip"},
    }
    (tmp_path / "apibackuper.yaml").write_text(yaml.safe_dump(config))
    assert ProjectBuilder(str(tmp_path)).checkpoint_interval_pages == 1


def write_project(path, **sections):
    config = {
        "settings": {"name": "real-session"},
        "project": {"url": "https://api.example.test/items", "http_mode": "GET"},
        "params": {"page_size_limit": 2},
        "data": {},
        "storage": {"storage_type": "zip"},
    }
    for name, values in sections.items():
        config.setdefault(name, {}).update(values)
    (path / "apibackuper.yaml").write_text(yaml.safe_dump(config))
    return str(path)


def test_export_follows_page_order(make_project, tmp_path):
    builder = make_project()
    records = [{"id": n} for n in range(25)]
    serve(builder, records)
    builder.run("full")
    output = tmp_path / "ordered.jsonl"
    builder.export("jsonl", str(output))
    assert [json.loads(line) for line in output.read_text().splitlines()] == records


def test_max_redirects_is_applied_to_session(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectBuilder, "enable_logging", lambda self: None)
    builder = ProjectBuilder(write_project(tmp_path, request={"max_redirects": 0}))
    assert builder.http.max_redirects == 0


def test_flat_params_keep_string_values_and_send_objects_as_json(make_project):
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    builder = make_project(params={"force_flat_params": True})
    Path(builder.project_path, "params.json").write_text(
        json.dumps({"q": "TrueNorth O'Reilly", "filter": {"active": True}})
    )
    serve(builder, [{"id": 1}])
    builder.run("full")
    query = parse_qs(urlsplit(builder.http.get.call_args.args[0]).query)
    assert query["q"] == ["TrueNorth O'Reilly"]
    assert json.loads(query["filter"][0]) == {"active": True}


def test_parquet_export_reconciles_types_across_batches(make_project, tmp_path, monkeypatch):
    pq = pytest.importorskip("pyarrow.parquet")
    import pyarrow as pa

    monkeypatch.setattr("apibackuper.cmds.export.PARQUET_BATCH_SIZE", 2)
    builder = make_project()
    records = [
        {"id": 1, "v": 1, "n": 1},
        {"id": 2, "v": 2, "n": 2},
        {"id": 3, "v": "x", "n": 1.5},
        {"id": 4, "v": {"k": 1}, "n": 2},
    ]
    serve(builder, records)
    builder.run("full")
    output = tmp_path / "drift.parquet"
    builder.export("parquet", str(output))
    table = pq.read_table(output)
    assert table.schema.field("n").type == pa.float64()
    assert table.column("n").to_pylist() == [1.0, 2.0, 1.5, 2.0]
    assert [json.loads(value) for value in table.column("v").to_pylist()] == [1, 2, "x", {"k": 1}]


def test_project_logging_keeps_host_handlers(tmp_path, monkeypatch):
    import logging

    from apibackuper.cmds.project import LOG_HANDLER_MARK

    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    saved, level = root.handlers[:], root.level
    host = logging.NullHandler()
    root.addHandler(host)
    try:
        path = write_project(tmp_path)
        ProjectBuilder(path)
        ProjectBuilder(path)
        assert host in root.handlers
        assert sum(getattr(h, LOG_HANDLER_MARK, False) for h in root.handlers) == 1
    finally:
        for handler in root.handlers:
            if handler not in saved:
                handler.close()
        root.handlers[:] = saved
        root.setLevel(level)


def test_getfiles_reads_journal_pages_and_skips_missing_files(make_project):
    from pathlib import Path
    from zipfile import ZipFile

    from apibackuper.storage import ZipStorageBackend

    builder = make_project(
        files={
            "fetch_mode": "prefix",
            "keys": "file",
            "root_url": "https://files.example.test/",
            "storage_mode": "id",
            "file_storage_type": "zip",
        },
    )
    serve(builder, [{"id": 1, "file": "gone"}])
    builder.run("full")
    # A page left in the journal by an interrupted run, not yet compacted.
    journal = ZipStorageBackend(builder.storage_file)
    journal.save_page("page_2.json", json.dumps({"items": [{"id": 2, "file": 7}]}).encode())
    journal.flush()

    def download(url, **kwargs):
        return reply({}, 404) if url.endswith("/gone") else reply({"file": url})

    builder.http.get.reset_mock()
    builder.http.get.side_effect = download
    builder.getfiles()
    with ZipFile(Path(builder.storagedir) / "files.zip") as archive:
        assert archive.namelist() == ["7"]
    skipped = (Path(builder.storagedir) / "files_skipped.list").read_text()
    assert "gone;;HTTP 404" in skipped


def test_getfiles_rejects_unknown_fetch_mode(make_project):
    builder = make_project(
        files={"fetch_mode": "prefix", "keys": "file", "root_url": "https://files.example.test/"}
    )
    serve(builder, [{"id": 1, "file": "a"}])
    builder.run("full")
    builder.fetch_mode = "magic"  # e.g. from a deprecated INI file without schema checks
    with pytest.raises(ValueError, match="fetch_mode"):
        builder.getfiles()
