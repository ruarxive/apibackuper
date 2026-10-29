"""Fixity manifests for backup generations and their verification.

Every successful run writes two members into the prefix of the generation it
publishes (``""`` for the base pages, ``runs/<id>/`` for an update):

- ``manifest-sha256.txt``: BagIt-style ``<sha256>  <member>`` lines, sorted by
  member name, for every page of that generation;
- ``run.json``: version, run ID, mode, times, counts and a configuration hash.

Neither name starts with ``page_``, so page listings, export and resume ignore
them. :func:`verify_storage` recomputes the digests through the storage backend.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from ..storage import build_storage_backend
from ..storage.backends import _is_page
from .utils import redact_params

MANIFEST_NAME = "manifest-sha256.txt"
RUN_RECORD_NAME = "run.json"
# Downloaded files: one BagIt-style line per stored file, beside file storage.
FILES_MANIFEST_NAME = "files-manifest-sha256.txt"


def generation_prefix(name: str) -> str:
    """Return the generation prefix of a member: ``""`` or ``runs/<id>/``."""
    return name.rsplit("/", 1)[0] + "/" if "/" in name else ""


def generation_pages(names: Iterable[str], prefix: str) -> List[str]:
    return [name for name in names if _is_page(name) and generation_prefix(name) == prefix]


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stream_digest(handle, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 of a readable binary stream, read in chunks and closed."""
    value = hashlib.sha256()
    with handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            value.update(block)
    return value.hexdigest()


def files_manifest_path(project) -> str:
    return os.path.join(project.storagedir, FILES_MANIFEST_NAME)


def open_files_storage(project, mode: str):
    """Open the configured file storage, or return None when it does not exist."""
    from ..storage import FilesystemStorageBackend, ZipStorageBackend

    if project.file_storage_type == "zip":
        path = os.path.join(project.storagedir, "files.zip")
        if mode == "r" and not os.path.exists(path):
            return None
        return ZipStorageBackend(path, mode=mode)
    root = os.path.join(project.storagedir, "files")
    if mode == "r" and not os.path.isdir(root):
        return None
    return FilesystemStorageBackend(root, mode="read" if mode == "r" else "a")


def append_manifest_line(path: str, name: str, value: str) -> None:
    """Durably append one ``<sha256>  <member>`` line."""
    with open(path, "a", encoding="utf8") as handle:
        handle.write(f"{value}  {name}\n")
        handle.flush()
        os.fsync(handle.fileno())


def verify_files(project) -> Dict[str, Any]:
    """Check downloaded files against ``files-manifest-sha256.txt``."""
    entry: Dict[str, Any] = {
        "generation": "(files)",
        "manifest": False,
        "verified": 0,
        "changed": [],
        "missing": [],
        "unlisted": [],
    }
    backend = open_files_storage(project, "r")
    if backend is None:
        return entry
    try:
        stored = set(backend.list_objects("object"))
        path = files_manifest_path(project)
        if not os.path.exists(path):
            entry["unlisted"] = sorted(stored)
            return entry
        entry["manifest"] = True
        with open(path, "rb") as handle:
            listed = parse_manifest(handle.read())
        for name, expected in sorted(listed.items()):
            stream = backend.open_object(name)
            if stream is None:
                entry["missing"].append(name)
            elif stream_digest(stream) != expected:
                entry["changed"].append(name)
            else:
                entry["verified"] += 1
        entry["unlisted"] = sorted(stored - set(listed))
    finally:
        backend.close()
    return entry


def render_manifest(digests: Dict[str, str]) -> bytes:
    return "".join(f"{digests[name]}  {name}\n" for name in sorted(digests)).encode("utf8")


def parse_manifest(content: bytes) -> Dict[str, str]:
    listed = {}
    for line in content.decode("utf8").splitlines():
        if line.strip():
            value, name = line.split(None, 1)
            listed[name.strip()] = value.lower()
    return listed


def config_digest(project) -> str:
    """Hash the resolved configuration with credentials redacted.

    Two runs whose configurations differ only in secret values hash equally.
    """
    config = project.config
    if hasattr(config, "_data"):
        data = config._data
    else:
        data = {section: dict(config.items(section)) for section in config.sections()}
    text = json.dumps(redact_params(data), sort_keys=True, ensure_ascii=False, default=str)
    return digest(text.encode("utf8"))


def write_generation_record(backend, prefix: str, digests: Dict[str, str], run: Dict[str, Any]):
    """Store the manifest and run record of one generation in ``backend``."""
    backend.save_object(prefix + MANIFEST_NAME, render_manifest(digests))
    record = json.dumps(run, ensure_ascii=False, indent=2, default=str).encode("utf8")
    backend.save_object(prefix + RUN_RECORD_NAME, record)


def verify_storage(project, strict: bool = False) -> Dict[str, Any]:
    """Check every generation's members against its manifest.

    Changed or missing listed members make the result fail. With ``strict``,
    unlisted pages and generations without a manifest fail it too.
    """
    if not os.path.exists(project.storage_file):
        raise FileNotFoundError(f"Backup storage not found: {project.storage_file}")
    backend = build_storage_backend(project.storage_type, project.storage_file, "read")
    generations = []
    try:
        pages = backend.list_objects("page")
        prefixes = {generation_prefix(name) for name in pages}
        prefixes.update(
            generation_prefix(name)
            for name in backend.list_objects("object")
            if name.rsplit("/", 1)[-1] == MANIFEST_NAME
        )
        for prefix in sorted(prefixes):
            content = backend.get_object(prefix + MANIFEST_NAME, "object")
            members = generation_pages(pages, prefix)
            entry: Dict[str, Any] = {
                "generation": prefix or "(base)",
                "manifest": content is not None,
                "verified": 0,
                "changed": [],
                "missing": [],
                "unlisted": [],
            }
            if content is None:
                entry["unlisted"] = members
            else:
                listed = parse_manifest(content)
                for name, expected in sorted(listed.items()):
                    data = backend.get_object(name, "page" if _is_page(name) else "object")
                    if data is None:
                        entry["missing"].append(name)
                    elif digest(data) != expected:
                        entry["changed"].append(name)
                    else:
                        entry["verified"] += 1
                entry["unlisted"] = sorted(set(members) - set(listed))
            generations.append(entry)
    finally:
        backend.close()
    if project.config.has_section("files"):
        files = verify_files(project)
        if files["manifest"] or files["unlisted"]:
            generations.append(files)
    damaged = any(entry["changed"] or entry["missing"] for entry in generations)
    incomplete = any(entry["unlisted"] or not entry["manifest"] for entry in generations)
    return {
        "ok": not damaged and not (strict and incomplete),
        "strict": strict,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "generations": generations,
    }


__all__ = [
    "FILES_MANIFEST_NAME",
    "MANIFEST_NAME",
    "RUN_RECORD_NAME",
    "config_digest",
    "generation_pages",
    "generation_prefix",
    "parse_manifest",
    "render_manifest",
    "verify_storage",
    "write_generation_record",
]
