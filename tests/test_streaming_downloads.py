"""Streamed file downloads (openspec update-streaming-file-downloads)."""

import hashlib
import warnings
from pathlib import Path

import pytest
import requests

from apibackuper.cmds.fixity import FILES_MANIFEST_NAME, parse_manifest
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
serve = workflow.serve

CHUNK = b"x" * 1000


class StreamedResponse(requests.Response):
    """A download that must be read through ``iter_content``."""

    def __init__(self, chunks, length=None, fail_after=None):
        super().__init__()
        self.status_code = 200
        self.headers = requests.structures.CaseInsensitiveDict(
            {"Content-Length": str(length)} if length is not None else {}
        )
        self._chunks, self._fail_after = chunks, fail_after
        self.closed = False

    @property
    def content(self):
        raise AssertionError("the download was read into memory")

    def iter_content(self, chunk_size=1, decode_unicode=False):
        for index, chunk in enumerate(self._chunks):
            if self._fail_after is not None and index == self._fail_after:
                raise requests.exceptions.ChunkedEncodingError("connection dropped")
            yield chunk

    def close(self):
        self.closed = True


def files_project(make_project, storage="filesystem", **files):
    builder = make_project(
        files=dict(
            {
                "fetch_mode": "prefix",
                "keys": "file",
                "root_url": "https://files.example.test/",
                "storage_mode": "id",
                "file_storage_type": storage,
            },
            **files,
        )
    )
    serve(builder, [{"id": 1, "file": "big"}, {"id": 2, "file": "small"}])
    builder.run("full")
    builder.http.get.reset_mock()
    return builder


def downloads(builder, responses):
    builder.http.get.side_effect = lambda url, **kwargs: responses[url.rsplit("/", 1)[-1]]()


def manifest(builder):
    path = Path(builder.storagedir) / FILES_MANIFEST_NAME
    return parse_manifest(path.read_bytes()) if path.exists() else {}


@pytest.mark.parametrize("storage", ["zip", "filesystem"])
def test_files_are_streamed_and_recorded_in_the_manifest(make_project, storage):
    builder = files_project(make_project, storage)
    downloads(
        builder,
        {
            "big": lambda: StreamedResponse([CHUNK] * 5),
            "small": lambda: StreamedResponse([b"abc"], length=3),
        },
    )
    builder.getfiles()
    assert all(call.kwargs.get("stream") for call in builder.http.get.call_args_list)
    listed = manifest(builder)
    assert listed == {
        "big": hashlib.sha256(CHUNK * 5).hexdigest(),
        "small": hashlib.sha256(b"abc").hexdigest(),
    }
    assert builder.verify(strict=True)["ok"]


def test_oversize_files_are_skipped(make_project):
    builder = files_project(make_project, max_file_size=2500)
    downloads(
        builder,
        {
            # Undeclared size: stopped while streaming.
            "big": lambda: StreamedResponse([CHUNK] * 5),
            # Declared size over the cap: not read at all.
            "small": lambda: StreamedResponse([], length=10_000),
        },
    )
    builder.getfiles()
    root = Path(builder.storagedir)
    assert not (root / "files" / "big").exists() and not (root / "files" / "small").exists()
    skipped = (root / "files_skipped.list").read_text()
    assert skipped.count("files.max_file_size (2500 bytes)") == 2
    assert manifest(builder) == {}
    assert not list(root.glob(".download-*"))


def test_interrupted_download_leaves_no_member(make_project):
    builder = files_project(make_project)
    downloads(
        builder,
        {
            "big": lambda: StreamedResponse([CHUNK] * 5, fail_after=2),
            "small": lambda: StreamedResponse([b"abc"]),
        },
    )
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        builder.getfiles()
    root = Path(builder.storagedir)
    assert not (root / "files" / "big").exists()
    assert "big" not in manifest(builder)
    assert not list(root.glob(".download-*"))


def test_verify_detects_changed_and_missing_files(make_project):
    builder = files_project(make_project)
    downloads(
        builder,
        {"big": lambda: StreamedResponse([CHUNK]), "small": lambda: StreamedResponse([b"abc"])},
    )
    builder.getfiles()
    files = Path(builder.storagedir) / "files"
    (files / "big").write_bytes(b"tampered")
    (files / "small").unlink()
    report = builder.verify()
    entry = next(item for item in report["generations"] if item["generation"] == "(files)")
    assert not report["ok"]
    assert entry["changed"] == ["big"] and entry["missing"] == ["small"]


def test_stored_files_missing_from_the_manifest_are_added(make_project):
    builder = files_project(make_project)
    files = Path(builder.storagedir) / "files"
    files.mkdir(parents=True, exist_ok=True)
    (files / "big").write_bytes(b"from an older version")
    downloads(builder, {"small": lambda: StreamedResponse([b"abc"])})
    builder.getfiles()
    assert manifest(builder)["big"] == hashlib.sha256(b"from an older version").hexdigest()
    assert [call.args[0].rsplit("/", 1)[-1] for call in builder.http.get.call_args_list] == [
        "small"
    ]


def test_be_careful_is_deprecated(make_project):
    builder = files_project(make_project)
    downloads(
        builder,
        {"big": lambda: StreamedResponse([CHUNK]), "small": lambda: StreamedResponse([b"abc"])},
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        builder.getfiles(be_careful=True)
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)
