# -*- coding: utf-8 -*-
"""Create a project from one probed endpoint (``apibackuper init``)."""
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import yaml

from .config_loader import validate_yaml_config
from .project import DETECTED_OPTIONS, ProjectBuilder, apply_detected_options
from .utils import slugify_name

# Default environment variable holding the secret for each auth type.
AUTH_VARIABLES = {"bearer": "API_TOKEN", "apikey": "API_KEY", "basic": "API_PASSWORD"}
CONFIG_NAMES = ("apibackuper.yaml", "apibackuper.yml", "apibackuper.cfg")


def parse_headers(values: Optional[List[str]]) -> Dict[str, str]:
    """Turn ``Name: value`` strings into a header mapping."""
    headers = {}
    for value in values or []:
        name, sep, content = value.partition(":")
        if not sep or not name.strip():
            raise ValueError(f"Header must look like 'Name: value': {value!r}")
        headers[name.strip()] = content.strip()
    return headers


def auth_section(
    auth: str, variable: Optional[str], header: Optional[str], username: Optional[str]
):
    """Return the YAML ``auth`` section with the secret as a ``${VAR}`` placeholder."""
    if auth not in AUTH_VARIABLES:
        raise ValueError(f"--auth must be one of {', '.join(AUTH_VARIABLES)}")
    variable = variable or AUTH_VARIABLES[auth]
    placeholder = "${" + variable + "}"
    if auth == "bearer":
        return variable, {"type": "bearer", "token": placeholder}
    if auth == "apikey":
        return variable, {
            "type": "apikey",
            "api_key": placeholder,
            "api_key_header": header or "X-API-Key",
        }
    if not username:
        raise ValueError("--username is required for --auth basic")
    return variable, {"type": "basic", "username": username, "password": placeholder}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf8") as fobj:
        json.dump(payload, fobj, ensure_ascii=False, indent=2)
        fobj.write("\n")


def _write_yaml(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf8") as fobj:
        yaml.safe_dump(payload, fobj, sort_keys=False, allow_unicode=True)


def init_project(
    path: str,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    auth: Optional[str] = None,
    auth_env: Optional[str] = None,
    api_key_header: Optional[str] = None,
    username: Optional[str] = None,
    data_key: Optional[str] = None,
    probe: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """Write a project for ``url`` into ``path`` and return a report.

    GET query parameters move from the URL into ``params.json`` and a POST
    body is written there, so that pagination values can be added on each
    page. With ``probe``, one request plus a few pagination probes fill in
    the records path, count field and pagination settings.
    """
    method = method.upper()
    if method not in ("GET", "POST"):
        raise ValueError("--method must be GET or POST")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://: {url}")
    existing = [name for name in CONFIG_NAMES if os.path.exists(os.path.join(path, name))]
    if existing and not force:
        raise FileExistsError(
            f"{os.path.join(path, existing[0])} already exists; pass --force to replace it"
        )
    os.makedirs(path, exist_ok=True)

    parts = urlsplit(url)
    params: Dict[str, Any] = dict(body or {})
    if method == "GET" and parts.query:
        params.update(parse_qsl(parts.query, keep_blank_values=True))
        url = urlunsplit(parts._replace(query=""))
    config: Dict[str, Any] = {
        "settings": {"name": slugify_name(os.path.basename(os.path.abspath(path)))},
        "project": {"url": url, "http_mode": method, "resp_type": "json"},
        "params": {"page_size_limit": 100},
        "data": {"data_key": data_key} if data_key else {},
        "storage": {"storage_type": "zip", "storage_path": "storage"},
    }
    variable = None
    if auth:
        variable, config["auth"] = auth_section(auth, auth_env, api_key_header, username)

    files = ["apibackuper.yaml"]
    if headers:
        _write_json(os.path.join(path, "headers.json"), headers)
        files.append("headers.json")
    config_path = os.path.join(path, "apibackuper.yaml")
    _write_yaml(config_path, config)

    report: Dict[str, Any] = {"project_path": os.path.abspath(path), "warnings": []}
    suggestions: Dict[str, Any] = {}
    if probe and variable and not os.environ.get(variable):
        report["warnings"].append(f"{variable} is not set; the endpoint was not probed")
        probe = False
    if probe:
        if params:
            _write_json(os.path.join(path, "params.json"), params)
        builder = ProjectBuilder(path)
        try:
            suggestions = builder.detect(write_config=False)
        finally:
            builder.http.close()
        # Detected values replace the placeholder size, never the user's options.
        config["params"].pop("page_size_limit")
        apply_detected_options(config, suggestions)
        config["params"].setdefault("page_size_limit", 100)
        for option in ("page_number_param", "count_skip_param", "page_size_param"):
            params.pop(suggestions.get(option), None)
        report["warnings"].extend(suggestions.get("warnings", []))
    else:
        report["warnings"].append(
            "Pagination was not detected; set project.iterate_by and the params names by hand"
        )
    params_path = os.path.join(path, "params.json")
    if params:
        _write_json(params_path, params)
        files.append("params.json")
    elif os.path.exists(params_path):
        os.remove(params_path)
    _write_yaml(config_path, config)

    if variable and not os.environ.get(variable):
        # The project cannot load without its secret; check the schema only.
        valid, schema_errors = validate_yaml_config(config)
        validation: Dict[str, Any] = {
            "valid": valid,
            "errors": [{"path": e.get("path"), "message": e.get("message")} for e in schema_errors],
            "warnings": [],
        }
    else:
        builder = ProjectBuilder(path)
        try:
            validation = builder.validation_report()
        finally:
            builder.http.close()
    report["warnings"].extend(issue["message"] for issue in validation["warnings"])
    project_dir = os.path.relpath(path)
    report.update(
        files=files,
        detected={name: suggestions[name] for name in DETECTED_OPTIONS if name in suggestions},
        records_on_first_page=suggestions.get("records_on_first_page"),
        fields=suggestions.get("fields", []),
        sample_record=suggestions.get("sample_record"),
        valid=validation["valid"],
        errors=validation["errors"],
        next_steps=[
            *([f"export {variable}=..."] if variable else []),
            f"cd {project_dir}",
            "apibackuper run full --max-pages 2",
            "apibackuper run full",
            f"apibackuper export {config['settings']['name']}.jsonl",
        ],
    )
    return report
