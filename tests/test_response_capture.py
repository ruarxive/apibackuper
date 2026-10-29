"""Exchange records, original bodies and WARC export (openspec add-response-capture)."""

import hashlib
import json
from pathlib import Path

import pytest
import requests

from apibackuper.storage import build_storage_backend
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
stored = workflow.stored

RECORDS = [{"id": n} for n in range(5)]


def exchange_reply(url, kwargs, payload, content=None, headers=None):
    """A response whose ``request`` is the prepared request apibackuper sent."""
    response = requests.Response()
    response.status_code = 200
    response.reason = "OK"
    response._content = content if content is not None else json.dumps(payload).encode()
    response.headers = requests.structures.CaseInsensitiveDict(headers or {})
    response.request = requests.Request(
        "GET", url, params=kwargs.get("params"), headers=kwargs.get("headers")
    ).prepare()
    response.url = response.request.url
    return response


def serve_exchanges(builder, records=RECORDS, headers=None):
    def get(url, **kwargs):
        page = int(kwargs["params"]["page"])
        payload = {"items": records[(page - 1) * 2 : page * 2], "total": len(records)}
        return exchange_reply(url, kwargs, payload, headers=headers)

    builder.http.get.side_effect = get


def members(builder):
    backend = build_storage_backend(builder.storage_type, builder.storage_file, "read")
    try:
        return {name: backend.get_object(name, "object") for name in backend.list_objects("object")}
    finally:
        backend.close()


@pytest.mark.parametrize("storage", ["zip", "sqlite", "filesystem"])
def test_every_page_gets_an_exchange_record(make_project, storage):
    builder = make_project(storage)
    serve_exchanges(builder, headers={"Content-Type": "application/json", "ETag": '"v1"'})
    builder.run("full")
    saved = members(builder)
    for page in (1, 2, 3):
        record = json.loads(saved[f"exchange_{page}.json"])
        assert record["page"] == page and record["response"]["status"] == 200
        assert record["request"]["method"] == "GET"
        assert f"page={page}" in record["request"]["url"]
        assert record["response"]["headers"]["ETag"] == '"v1"'
        assert record["fetched_at"].endswith("+00:00")
        page_bytes = _page(builder, page)
        assert record["response"]["sha256"] == hashlib.sha256(page_bytes).hexdigest()
        assert record["raw_member"] is None and record["redacted"] is False
    assert builder.info(stats=True)["statistics"]["storage"]["captured_exchanges"] == 3


def _page(builder, page):
    backend = build_storage_backend(builder.storage_type, builder.storage_file, "read")
    try:
        return backend.get_object(f"page_{page}.json", "page")
    finally:
        backend.close()


def test_credentials_are_redacted_in_exchanges(make_project):
    builder = make_project(auth={"type": "bearer", "token": "secret-token-value"})
    serve_exchanges(builder, RECORDS[:1], headers={"Set-Cookie": "session=secret-cookie"})
    builder.run("full")
    text = members(builder)["exchange_1.json"].decode()
    assert "secret-token-value" not in text and "secret-cookie" not in text
    assert json.loads(text)["redacted"] is True


def test_xml_response_bytes_are_kept_verbatim(make_project):
    builder = make_project(
        project={"resp_type": "xml"},
        data={"data_key": "root.items.item", "total_number_key": "root.total"},
    )
    body = b"<root><total>1</total><items><item><id>1</id></item></items></root>"
    builder.http.get.side_effect = lambda url, **kwargs: exchange_reply(url, kwargs, None, body)
    builder.run("full")
    saved = members(builder)
    assert saved["raw_1.xml"] == body
    assert json.loads(saved["exchange_1.json"])["raw_member"] == "raw_1.xml"
    assert json.loads(_page(builder, 1))["root"]["total"] == "1"


def test_capture_settings_are_loaded(tmp_path, monkeypatch):
    from apibackuper.cmds.project import ProjectBuilder

    monkeypatch.setattr(ProjectBuilder, "enable_logging", lambda self: None)
    capture = {"metadata": False, "raw_body": "always"}
    path = workflow.write_project(tmp_path, storage={"storage_type": "zip", "capture": capture})
    builder = ProjectBuilder(path)
    assert builder.validate_config()[0]
    assert builder.capture_metadata is False and builder.capture_raw_body == "always"


def test_capture_settings(make_project):
    off = make_project("zip")
    off.capture_metadata = False
    serve_exchanges(off)
    off.run("full")
    assert not any(name.startswith(("exchange_", "raw_")) for name in members(off))
    always = make_project("sqlite")
    always.capture_raw_body = "always"
    serve_exchanges(always, RECORDS[:1])
    always.run("full")
    saved = members(always)
    assert saved["raw_1.json"] == _page(always, 1)


def test_update_generation_has_its_own_exchanges(make_project):
    builder = make_project(
        project={"update_mode": "by_change_key"},
        params={"change_key_param": "since"},
        data={"change_key": "id"},
    )
    serve_exchanges(builder)
    builder.run("full")
    serve_exchanges(builder, [{"id": 10}])
    builder.update()
    names = members(builder)
    assert any(name.startswith("runs/") and name.endswith("/exchange_1.json") for name in names)


def test_new_full_backup_drops_previous_exchanges_on_filesystem(make_project):
    builder = make_project("filesystem")
    serve_exchanges(builder)
    builder.run("full")
    serve_exchanges(builder, RECORDS[:1])
    builder.run("full")
    root = Path(builder.storage_file)
    assert sorted(path.name for path in root.glob("exchange_*")) == ["exchange_1.json"]


def test_warc_export_round_trip(make_project, tmp_path, capsys):
    archive_iterator = pytest.importorskip("warcio.archiveiterator")
    builder = make_project()
    serve_exchanges(builder)
    builder.run("full")
    output = tmp_path / "backup.warc.gz"
    builder.export("warc", str(output))
    with open(output, "rb") as handle:
        records = [
            (record.rec_type, record.http_headers, record.content_stream().read())
            for record in archive_iterator.ArchiveIterator(handle)
        ]
    responses = [(headers, body) for kind, headers, body in records if kind == "response"]
    assert [kind for kind, _, _ in records].count("request") == 3
    assert [headers.get_statuscode() for headers, _ in responses] == ["200", "200", "200"]
    assert [json.loads(body)["items"][0]["id"] for _, body in responses] == [0, 2, 4]
    assert "Exported 3 exchanges" in capsys.readouterr().out
    with pytest.raises(ValueError, match="--fields"):
        builder.export("warc", str(tmp_path / "x.warc.gz"), fields=["id"])


def test_warc_export_skips_pages_without_exchanges(make_project, tmp_path, capsys):
    pytest.importorskip("warcio")
    builder = make_project()
    builder.capture_metadata = False
    serve_exchanges(builder)
    builder.run("full")
    builder.export("warc", str(tmp_path / "legacy.warc.gz"))
    assert "skipped 3 pages" in capsys.readouterr().out
    assert [item["id"] for item in stored(builder)] == [0, 1, 2, 3, 4]
