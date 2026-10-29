"""Per-record export pipeline.

Extracted from ``ProjectBuilder.export`` so the filtering / projection /
serialisation logic can be unit-tested in isolation. The orchestrator in
``ProjectBuilder.export`` opens the storage backend, iterates over its
files, and calls :func:`process_record` for each parsed JSON payload.

The function returns a list of records that match ``--where`` and have
been projected via ``--fields``. The caller is responsible for writing
them to its destination (jsonl, gzip, zstd, parquet).
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import tempfile
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from ..common import get_dict_value
from ..storage import ZipStorageBackend, build_storage_backend
from .where_filter import match_where, select_fields


def process_record(
    data: Any,
    *,
    data_key: Optional[str],
    field_splitter: str = ".",
    fields: Optional[Iterable[str]] = None,
    where: Optional[Callable[[Any], bool]] = None,
    record_filter: Optional[Callable[[Any], bool]] = None,
) -> List[Any]:
    """Filter and project one parsed JSON payload from storage.

    The pipeline mirrors what ``ProjectBuilder.export`` did inline for each
    storage backend (zip details, sqlite, zip storage): extract items via
    ``data_key`` if set, otherwise treat the payload itself as a list; apply
    ``--where``; project to ``--fields``; accumulate matched records.

    Parameters
    ----------
    data
        Parsed JSON payload from a single page or detail file.
    data_key
        Dotted path to the records array inside the payload, e.g.
        ``"results.items"``. When ``None`` or the key is not present, the
        payload itself is iterated (works for top-level lists and bare dicts).
    fields
        Iterable of dotted paths to project the matched records to. When
        ``None`` or empty, returns the matched records unchanged.
    where
        Predicate over a single record that returns ``True`` when the record
        should be included. ``None`` accepts everything.
    record_filter
        Optional alternative predicate (used by the ``follow``-mode path,
        which checks a different field before the where-filter).

    Returns
    -------
    list of records that survived the pipeline.
    """
    if data is None:
        return []

    if record_filter and not record_filter(data):
        return []

    # Resolve the list of candidate items.
    if data_key:
        items = get_dict_value(data, data_key, splitter=field_splitter)
        if items is None:
            return []
        # A single dict value is treated as a one-item list.
        if isinstance(items, dict):
            items = [items]
    else:
        items = data

    if not isinstance(items, list):
        # Single scalar / dict — wrap as one record so the user gets it.
        items = [items]

    result: List[Any] = []
    for item in items:
        if where is not None and not where(item):
            continue
        projected = select_fields(item, list(fields) if fields else None, splitter=field_splitter)
        result.append(projected)
    return result


def natural_order(name: str) -> List[Any]:
    """Sort key that orders ``page_2.json`` before ``page_10.json``.

    Storage backends list members lexicographically; exports follow the
    collection order instead, with base pages before ``runs/<id>/`` updates.
    """
    return [int(part) if index % 2 else part for index, part in enumerate(re.split(r"(\d+)", name))]


def serialize_record(record: Any) -> str:
    """Render one record as a JSON string with the trailing newline.

    Mirrors the historical inline format so a jsonl file diff is unchanged.
    """
    return json.dumps(record, ensure_ascii=False) + "\n"


def export_project(project, format, filename, fields=None, where=None):
    """Export all retained generations through the same record pipeline."""
    if project.config is None:
        project._raise_config_not_found()
    if format not in ("jsonl", "gzip", "zstd", "parquet", "warc"):
        raise ValueError("Supported formats: jsonl, gzip, zstd, parquet, warc")
    if not filename:
        raise ValueError("Output filename is required")
    if os.path.realpath(filename) == os.path.realpath(project.storage_file):
        raise ValueError("Export destination must differ from the backup storage")
    if format == "warc" and (fields or where):
        raise ValueError(
            "WARC export writes whole HTTP exchanges; --fields and --where do not apply"
        )
    condition = project._parse_where(where)
    details = project.details_storage_file
    # WARC records come from the main backup's captured exchanges.
    use_details = (
        format != "warc" and project.config.has_section("follow") and os.path.exists(details)
    )
    output_path = os.path.realpath(filename)
    if use_details and output_path == os.path.realpath(details):
        raise ValueError("Export destination must differ from the source details archive")
    if project.storage_type == "filesystem":
        storage_root = os.path.realpath(project.storage_file)
        if os.path.commonpath((storage_root, output_path)) == storage_root:
            raise ValueError("Export destination must be outside the filesystem backup")
    backend = (
        ZipStorageBackend(details, mode="r")
        if use_details
        else build_storage_backend(project.storage_type, project.storage_file, "read")
    )
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(filename)))
    os.close(fd)
    output = None
    parquet_writer = None
    try:
        if format == "warc":
            written, skipped = _write_warc(backend, temporary, os.path.basename(filename))
            os.replace(temporary, filename)
            print(
                f"Exported {written} exchanges to WARC; skipped {skipped} pages without exchanges"
            )
            return
        if format == "parquet":
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                raise RuntimeError(
                    "Parquet export requires pyarrow; install apibackuper[recommended]"
                ) from None
        elif format == "gzip":
            output = gzip.open(temporary, "wt", encoding="utf8")
        elif format == "zstd":
            import zstandard

            output = io.TextIOWrapper(
                zstandard.ZstdCompressor().stream_writer(open(temporary, "wb")), encoding="utf8"
            )
        else:
            output = open(temporary, "w", encoding="utf8")
        data_key = project.follow_data_key if use_details else project.data_key
        kind = "object" if use_details else "page"
        names = sorted(backend.list_objects(kind), key=natural_order)

        def exported_records():
            for name in names:
                content = backend.get_object(name, kind)
                if content is None:
                    continue
                yield from process_record(
                    json.loads(content),
                    data_key=data_key,
                    field_splitter=project.field_splitter,
                    fields=fields,
                    where=lambda item: project._match_where(item, condition),
                )

        if output is not None:
            for record in exported_records():
                output.write(serialize_record(record))
        else:
            # Pass 1 settles one schema for every batch; pass 2 writes it.
            schema, json_columns = _parquet_schema(pa, _batches(exported_records()))
            parquet_writer = pq.ParquetWriter(temporary, schema)
            for batch in _batches(exported_records()):
                parquet_writer.write_table(_parquet_table(pa, batch, schema, json_columns))
            parquet_writer.close()
            parquet_writer = None
        if output is not None:
            output.close()
            output = None
        os.replace(temporary, filename)
    finally:
        backend.close()
        if output is not None:
            output.close()
        if parquet_writer is not None:
            parquet_writer.close()
        if os.path.exists(temporary):
            os.unlink(temporary)


PARQUET_BATCH_SIZE = 5000


def _warc_date(value: Optional[str]) -> Optional[str]:
    """Render an ISO 8601 UTC time as a WARC date (``...Z``)."""
    if not value:
        return None
    return value.replace("+00:00", "Z")


def _write_warc(backend, path: str, name: str) -> Tuple[int, int]:
    """Write request and response records for every page with an exchange record."""
    try:
        from warcio.statusandheaders import StatusAndHeaders
        from warcio.warcwriter import WARCWriter
    except ImportError:
        raise RuntimeError(
            "WARC export requires warcio; install apibackuper[recommended]"
        ) from None
    from urllib.parse import urlsplit

    from .. import __version__
    from .capture import exchange_name
    from .fixity import generation_prefix

    written = skipped = 0
    with open(path, "wb") as handle:
        writer = WARCWriter(handle, gzip=True, warc_version="1.1")
        writer.write_record(
            writer.create_warcinfo_record(
                name, {"software": f"apibackuper/{__version__}", "format": "WARC File Format 1.1"}
            )
        )
        for page_name in sorted(backend.list_objects("page"), key=natural_order):
            page = int(page_name.rsplit("page_", 1)[-1].split(".")[0])
            content = backend.get_object(
                exchange_name(generation_prefix(page_name), page), "object"
            )
            if content is None:
                skipped += 1
                continue
            exchange = json.loads(content)
            request, response = exchange["request"], exchange["response"]
            payload = None
            if exchange.get("raw_member"):
                payload = backend.get_object(exchange["raw_member"], "object")
            if payload is None:
                payload = backend.get_object(page_name, "page")
            # The stored payload is decoded, so transfer and content encodings
            # no longer apply and the length is the stored length.
            headers = [
                (key, str(value))
                for key, value in response["headers"].items()
                if key.lower() not in ("content-encoding", "transfer-encoding", "content-length")
            ]
            headers.append(("Content-Length", str(len(payload))))
            status = f"{response['status']} {response.get('reason') or ''}".strip()
            uri = response.get("url") or request.get("url")
            date = (
                {"WARC-Date": _warc_date(exchange.get("fetched_at"))}
                if exchange.get("fetched_at")
                else {}
            )
            record = writer.create_warc_record(
                uri,
                "response",
                payload=io.BytesIO(payload),
                http_headers=StatusAndHeaders(status, headers, protocol="HTTP/1.1"),
                warc_headers_dict=date,
            )
            target = urlsplit(request.get("url") or uri)
            path_and_query = (target.path or "/") + (f"?{target.query}" if target.query else "")
            request_headers = [(key, str(value)) for key, value in request["headers"].items()]
            if not any(key.lower() == "host" for key, _ in request_headers):
                request_headers.insert(0, ("Host", target.netloc))
            body = request.get("body")
            if body is None:
                body_bytes = b""
            elif isinstance(body, str):
                body_bytes = body.encode("utf8")
            else:
                body_bytes = json.dumps(body, ensure_ascii=False).encode("utf8")
            linked = dict(
                date, **{"WARC-Concurrent-To": record.rec_headers.get_header("WARC-Record-ID")}
            )
            request_record = writer.create_warc_record(
                uri,
                "request",
                payload=io.BytesIO(body_bytes),
                http_headers=StatusAndHeaders(
                    f"{request.get('method') or 'GET'} {path_and_query} HTTP/1.1",
                    request_headers,
                    is_http_request=True,
                ),
                warc_headers_dict=linked,
            )
            writer.write_record(record)
            writer.write_record(request_record)
            written += 1
    return written, skipped


def _batches(records: Iterable[Any]) -> Iterable[List[Any]]:
    batch: List[Any] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Parquet export requires object records; use jsonl for other values")
        batch.append(record)
        if len(batch) >= PARQUET_BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def _parquet_schema(pa: Any, batches: Iterable[List[Dict[str, Any]]]) -> Tuple[Any, Set[str]]:
    """Infer one schema for all records.

    API records often change a field's type between pages, which made a schema
    taken from the first batch reject later ones. Types are inferred per column
    and promoted (for example int to double); a column whose types cannot be
    reconciled, such as numbers and strings, is exported as JSON text.
    """
    types: Dict[str, Any] = {}
    json_columns: Set[str] = set()
    for batch in batches:
        names = dict.fromkeys(key for record in batch for key in record)
        for name in names:
            if name in json_columns:
                continue
            try:
                kind = pa.array([record.get(name) for record in batch]).type
                types[name] = _promote(pa, types[name], kind) if name in types else kind
            except (pa.ArrowInvalid, pa.ArrowTypeError, OverflowError):
                types.setdefault(name, None)
                json_columns.add(name)
    fields = [
        pa.field(name, pa.string() if name in json_columns else kind)
        for name, kind in types.items()
    ]
    return pa.schema(fields), json_columns


def _promote(pa: Any, left: Any, right: Any) -> Any:
    schemas = [pa.schema([("value", left)]), pa.schema([("value", right)])]
    try:
        merged = pa.unify_schemas(schemas, promote_options="permissive")
    except TypeError:  # pyarrow < 14 has no promote_options
        merged = pa.unify_schemas(schemas)
    return merged.field("value").type


def _parquet_table(
    pa: Any, batch: List[Dict[str, Any]], schema: Any, json_columns: Set[str]
) -> Any:
    columns = []
    for field in schema:
        values = [record.get(field.name) for record in batch]
        if field.name in json_columns:
            values = [
                None if value is None else json.dumps(value, ensure_ascii=False, default=str)
                for value in values
            ]
        columns.append(pa.array(values, type=field.type))
    return pa.Table.from_arrays(columns, schema=schema)


__all__ = ["process_record", "serialize_record", "match_where"]
