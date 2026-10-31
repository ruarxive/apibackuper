# -* coding: utf-8 -*-
import configparser
import csv
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import zipfile
from contextlib import suppress
from runpy import run_path
from timeit import default_timer as timer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import requests

# Marks root-logger handlers apibackuper installed, so they can be replaced
# without touching handlers that belong to an embedding application.
LOG_HANDLER_MARK = "_apibackuper_handler"


try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

with suppress(ImportError):
    import aria2p

from tqdm import tqdm

from .. import __version__
from ..auth import AuthHandler
from ..common import get_dict_value
from ..constants import (
    DEFAULT_DELAY,
    DEFAULT_ERROR_STATUS_CODES,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT,
    FIELD_SPLITTER,
    RETRY_DELAY,
)
from ..rate_limiter import RateLimiter
from ..storage import FilesystemStorageBackend, ZipStorageBackend, build_storage_backend

# Import from refactored modules
from .config_loader import (
    JSONSCHEMA_AVAILABLE,
    UnresolvedEnvVarError,
    YAMLConfigParser,
    load_json_file,
    parse_status_codes,
    substitute_env_vars,
    validate_yaml_config,
)
from .fetch import CURSOR_MODES
from .utils import (
    _is_sensitive_key,
    _url_replacer,
    append_query,
    flat_param_value,
    load_file_list,
    progress_disable,
    redact_headers,
    redact_params,
    redact_text,
    redact_url,
    remove_query_keys,
)
from .where_filter import match_where


def _safe_int(value: Any, option: str, default: int = 0) -> int:
    """Coerce ``value`` to int, logging a warning and falling back on failure.

    Used by ``ProjectBuilder.__init__`` so a non-integer value in a config
    field does not crash the constructor with ``ValueError: invalid literal
    for int()``. The schema validator will still surface the underlying
    problem as a proper error.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        logging.warning(
            "%s must be an integer; falling back to %s",
            option,
            default,
        )
        return default


# Request parameters each pagination mode needs; without them only page 1 is fetched.
PAGINATION_PARAMS = {
    "page": ("page_number_param",),
    "skip": ("count_skip_param",),
    "range": ("count_from_param", "count_to_param"),
}


def _issue(path: Optional[str], message: str, hint: Optional[str] = None) -> Dict[str, Any]:
    """Build one validation error or warning entry."""
    entry: Dict[str, Any] = {"path": path, "message": message}
    if hint:
        entry["hint"] = hint
    return entry


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` atomically.

    Writes to a sibling ``.tmp`` file, flushes + fsyncs, then ``os.replace()``
    swaps it onto the target path. On POSIX, ``os.replace`` is atomic, so a
    crash mid-write leaves either the previous content or the new content
    intact — never a half-written file (§P3 of the 2026-10 analysis report).
    """
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf8") as fobj:
        json.dump(payload, fobj, ensure_ascii=False, indent=2)
        fobj.flush()
        try:
            os.fsync(fobj.fileno())
        except (OSError, AttributeError):
            # Some filesystems (e.g. tmpfs on some Linux configs) don't
            # support fsync; skip it rather than fail the write.
            pass
    os.replace(tmp_path, path)


# Common response fields that point to the next page, most specific first.
NEXT_URL_KEYS = (
    "@odata.nextLink",
    "next",
    "next_url",
    "nextUrl",
    "links.next",
    "_links.next.href",
    "paging.next",
    "pagination.next",
    "meta.next",
)
# Cursor fields and the request parameter that usually carries them back.
NEXT_CURSOR_KEYS = (
    ("next_cursor", "cursor"),
    ("nextCursor", "cursor"),
    ("cursor.next", "cursor"),
    ("response_metadata.next_cursor", "cursor"),
    ("meta.next_cursor", "cursor"),
    ("cursor", "cursor"),
    ("next_page_token", "page_token"),
    ("nextPageToken", "pageToken"),
)
# Detected suggestion -> (config section, option); suggestions never replace
# an option the configuration already sets.
DETECTED_OPTIONS = {
    "data_key": ("data", "data_key"),
    "total_number_key": ("data", "total_number_key"),
    "pages_number_key": ("data", "pages_number_key"),
    "next_url_key": ("data", "next_url_key"),
    "next_cursor_key": ("data", "next_cursor_key"),
    "cursor_param": ("params", "cursor_param"),
    "iterate_by": ("project", "iterate_by"),
    "page_number_param": ("params", "page_number_param"),
    "count_skip_param": ("params", "count_skip_param"),
    "page_size_param": ("params", "page_size_param"),
    "page_size_limit": ("params", "page_size_limit"),
}


def apply_detected_options(config_data: Dict[str, Any], suggestions: Dict[str, Any]) -> None:
    """Write detected options into a YAML config mapping without overriding it."""
    for name, (section, option) in DETECTED_OPTIONS.items():
        if suggestions.get(name):
            config_data.setdefault(section, {}).setdefault(option, suggestions[name])


# Bytes read per chunk while streaming file downloads.
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class RedirectSafeSession(requests.Session):
    """Session that drops credential headers when a redirect leaves the host.

    ``requests`` strips only ``Authorization`` on a cross-host redirect, so an
    API key in ``X-API-Key`` or a custom header from ``headers.json`` would be
    sent to the redirect target. ``protected_headers`` adds names such as a
    configured ``auth.api_key_header`` that do not look sensitive.
    """

    def __init__(self) -> None:
        super().__init__()
        self.protected_headers: set = set()

    def rebuild_auth(self, prepared_request, response):
        super().rebuild_auth(prepared_request, response)
        if self.should_strip_auth(response.request.url, prepared_request.url):
            protected = {name.lower() for name in self.protected_headers}
            for name in list(prepared_request.headers):
                if name.lower() in protected or _is_sensitive_key(name):
                    del prepared_request.headers[name]


class ProjectBuilder:
    """Project builder"""

    def __init__(self, project_path: Optional[str] = None) -> None:
        self.http = RedirectSafeSession()
        self.project_path = os.path.abspath(project_path or os.getcwd())
        # Initialize logfile with default value early to ensure it's always available
        self.logfile = "apibackuper.log"
        # Store YAML_AVAILABLE for later use
        self._yaml_available = YAML_AVAILABLE
        # Check for YAML config files first (priority), then fall back to INI
        yaml_config_yml = os.path.join(self.project_path, "apibackuper.yml")
        yaml_config_yaml = os.path.join(self.project_path, "apibackuper.yaml")
        ini_config = os.path.join(self.project_path, "apibackuper.cfg")

        if self._yaml_available and os.path.exists(yaml_config_yaml):
            self.config_filename = yaml_config_yaml
            self.config_format = "yaml"
        elif self._yaml_available and os.path.exists(yaml_config_yml):
            self.config_filename = yaml_config_yml
            self.config_format = "yaml"
        elif os.path.exists(ini_config):
            self.config_filename = ini_config
            self.config_format = "ini"
        else:
            # Default to INI format for backward compatibility
            self.config_filename = ini_config
            self.config_format = "ini"

        self.__read_config(self.config_filename)
        self.enable_logging()

    def enable_logging(self) -> None:
        """Enable logging to file (no stdout/stderr output by default)"""
        logFormatter = logging.Formatter(
            "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
        )
        rootLogger = logging.getLogger()

        # Replace only apibackuper's own file handlers to avoid duplicates.
        for handler in list(rootLogger.handlers):
            if getattr(handler, LOG_HANDLER_MARK, False):
                rootLogger.removeHandler(handler)
                handler.close()

        fileHandler = logging.FileHandler("{0}".format(self.logfile))
        fileHandler.setFormatter(logFormatter)
        setattr(fileHandler, LOG_HANDLER_MARK, True)
        rootLogger.addHandler(fileHandler)

        # Preserve the historical DEBUG default while respecting an explicit
        # logging section. CLI --verbose can override it after construction.
        log_level = "DEBUG"
        config = getattr(self, "config", None)
        if config is not None and config.has_section("logging"):
            log_level = config.get("logging", "level", fallback="INFO").upper()
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        rootLogger.setLevel(levels.get(log_level, logging.INFO))

    def __read_config(self, filename: str) -> None:
        self.config = None
        if not os.path.exists(filename):
            return

        # ``conf`` is one of ``YAMLConfigParser`` (yaml branch) or
        # ``configparser.ConfigParser`` (ini branch); declare the union
        # up front so mypy doesn't narrow to ``YAMLConfigParser`` in the
        # ini branch (which has its own ``.read`` method).
        conf: Any

        if self.config_format == "yaml":
            if not self._yaml_available:
                logging.warning(
                    "YAML config file found but PyYAML is not installed. Falling back to INI."
                )
                # Try to fall back to INI
                ini_config = os.path.join(self.project_path, "apibackuper.cfg")
                if os.path.exists(ini_config):
                    self.config_filename = ini_config
                    self.config_format = "ini"
                    self.__read_config(ini_config)
                    return
                else:
                    return

            try:
                with open(filename, "r", encoding="utf8") as fobj:
                    yaml_data = yaml.safe_load(fobj)

                # Substitute ${VAR} placeholders (improve-security 4.1-4.3).
                if yaml_data:
                    try:
                        yaml_data = substitute_env_vars(yaml_data, source=filename)
                    except UnresolvedEnvVarError as exc:
                        self._config_error = exc
                        return

                # Validate YAML config against schema
                if yaml_data:
                    is_valid, validation_errors = validate_yaml_config(yaml_data)
                    if not is_valid:
                        error_messages = []
                        for error in validation_errors:
                            path = error.get("path", "root")
                            msg = error.get("message", "Unknown error")
                            error_messages.append(f"  {path}: {msg}")
                        error_text = "YAML config validation failed:\n" + "\n".join(error_messages)
                        logging.error(error_text)
                        # Don't fail completely, but log the errors
                        # This allows the app to continue with potentially invalid config
                        # The validate_config command can be used to check configs explicitly

                conf = YAMLConfigParser(yaml_data)
                self.config = conf
            except (IOError, OSError, ValueError, yaml.YAMLError) as e:
                logging.error("Error reading YAML config file: %s", str(e))
                return
        else:
            # INI format
            conf = configparser.ConfigParser()
            conf.read(filename, encoding="utf8")
            self.config = conf
            logging.warning("INI configuration is deprecated; use YAML instead.")

        if self.config is not None:
            required = (
                ("settings", "name"),
                ("project", "url"),
                ("project", "http_mode"),
                ("storage", "storage_type"),
            )
            if any(not self.config.has_option(section, key) for section, key in required):
                # Preserve the parsed configuration for validate-config while
                # avoiding accidental execution with incomplete attributes.
                return
            self.storage_path = (
                self.config.get("storage", "storage_path")
                if self.config.has_option("storage", "storage_path")
                else "storage"
            )
            self.storagedir = os.path.join(self.project_path, self.storage_path)
            self.field_splitter = (
                self.config.get("settings", "splitter")
                if self.config.has_option("settings", "splitter")
                else FIELD_SPLITTER
            )
            self.id = (
                self.config.get("settings", "id")
                if self.config.has_option("settings", "id")
                else None
            )
            self.name = self.config.get("settings", "name")
            self.logfile = (
                self.config.get("settings", "logfile")
                if self.config.has_option("settings", "logfile")
                else "apibackuper.log"
            )
            self.state_file = (
                self.config.get("settings", "state_file")
                if self.config.has_option("settings", "state_file")
                else os.path.join(self.project_path, "apibackuper_state.json")
            )
            self.checkpoint_file = (
                self.config.get("settings", "checkpoint_file")
                if self.config.has_option("settings", "checkpoint_file")
                else os.path.join(self.project_path, "apibackuper_checkpoint.json")
            )
            # Checkpoint after every saved page by default so a crash resumes
            # where it stopped; 0 keeps only the lifecycle checkpoints.
            self.checkpoint_interval_pages = _safe_int(
                (
                    self.config.get("settings", "checkpoint_interval_pages")
                    if self.config.has_option("settings", "checkpoint_interval_pages")
                    else 1
                ),
                "settings.checkpoint_interval_pages",
                1,
            )
            self.data_key = (
                self.config.get("data", "data_key")
                if self.config.has_option("data", "data_key")
                else None
            )
            self.change_key = (
                self.config.get("data", "change_key")
                if self.config.has_option("data", "change_key")
                else None
            )
            self.storage_type = self.config.get("storage", "storage_type")
            self.http_mode = self.config.get("project", "http_mode")
            self.description = (
                self.config.get("project", "description")
                if self.config.has_option("project", "description")
                else None
            )
            self.start_url = self.config.get("project", "url")
            self.page_limit = _safe_int(
                (
                    self.config.get("params", "page_size_limit")
                    if self.config.has_option("params", "page_size_limit")
                    else 0
                ),
                "params.page_size_limit",
                0,
            )
            self.resp_type = (
                self.config.get("project", "resp_type")
                if self.config.has_option("project", "resp_type")
                else "json"
            )
            self.iterate_by = (
                self.config.get("project", "iterate_by")
                if self.config.has_option("project", "iterate_by")
                else "page"
            )
            self.detect_enabled = (
                self.config.getboolean("project", "detect")
                if self.config.has_option("project", "detect")
                else False
            )
            self.update_mode = (
                self.config.get("project", "update_mode")
                if self.config.has_option("project", "update_mode")
                else None
            )
            # ``default_delay`` is documented as a float (e.g. ``0.5``). Earlier
            # versions called ``getint`` and crashed on any non-integer delay. The
            # config-loader now has a dedicated ``getfloat`` (see §4.6 of the
            # 2026-10 analysis report) — use it.
            self.default_delay = (
                self.config.getfloat("project", "default_delay")
                if self.config.has_option("project", "default_delay")
                else DEFAULT_DELAY
            )
            self.retry_delay = _safe_int(
                (
                    self.config.get("project", "retry_delay")
                    if self.config.has_option("project", "retry_delay")
                    else RETRY_DELAY
                ),
                "project.retry_delay",
                RETRY_DELAY,
            )
            self.force_retry = (
                self.config.getboolean("project", "force_retry")
                if self.config.has_option("project", "force_retry")
                else False
            )
            self.retry_count = _safe_int(
                (
                    self.config.get("project", "retry_count")
                    if self.config.has_option("project", "retry_count")
                    else DEFAULT_RETRY_COUNT
                ),
                "project.retry_count",
                DEFAULT_RETRY_COUNT,
            )

            self.start_page = _safe_int(
                (
                    self.config.get("params", "start_page")
                    if self.config.has_option("params", "start_page")
                    else 1
                ),
                "params.start_page",
                1,
            )
            self.query_mode = (
                self.config.get("params", "query_mode")
                if self.config.has_option("params", "query_mode")
                else "query"
            )
            self.flat_params = (
                self.config.getboolean("params", "force_flat_params")
                if self.config.has_option("params", "force_flat_params")
                else False
            )
            self.change_key_param = (
                self.config.get("params", "change_key_param")
                if self.config.has_option("params", "change_key_param")
                else None
            )
            self.update_since_param = (
                self.config.get("params", "update_since_param")
                if self.config.has_option("params", "update_since_param")
                else None
            )
            self.total_number_key = (
                self.config.get("data", "total_number_key")
                if self.config.has_option("data", "total_number_key")
                else ""
            )
            self.pages_number_key = (
                self.config.get("data", "pages_number_key")
                if self.config.has_option("data", "pages_number_key")
                else ""
            )
            self.page_number_param = (
                self.config.get("params", "page_number_param")
                if self.config.has_option("params", "page_number_param")
                else None
            )
            self.count_skip_param = (
                self.config.get("params", "count_skip_param")
                if self.config.has_option("params", "count_skip_param")
                else None
            )
            self.count_from_param = (
                self.config.get("params", "count_from_param")
                if self.config.has_option("params", "count_from_param")
                else None
            )
            self.count_to_param = (
                self.config.get("params", "count_to_param")
                if self.config.has_option("params", "count_to_param")
                else None
            )
            self.page_size_param = (
                self.config.get("params", "page_size_param")
                if self.config.has_option("params", "page_size_param")
                else None
            )
            # Cursor-style pagination (iterate_by: cursor, next_url, link_header).
            self.cursor_param = (
                self.config.get("params", "cursor_param")
                if self.config.has_option("params", "cursor_param")
                else None
            )
            self.allow_cross_host_next = (
                self.config.getboolean("params", "allow_cross_host_next")
                if self.config.has_option("params", "allow_cross_host_next")
                else False
            )
            self.next_cursor_key = (
                self.config.get("data", "next_cursor_key")
                if self.config.has_option("data", "next_cursor_key")
                else None
            )
            self.next_url_key = (
                self.config.get("data", "next_url_key")
                if self.config.has_option("data", "next_url_key")
                else None
            )
            self.storage_file = self._resolve_storage_file()
            self.details_storage_file = os.path.join(
                (
                    os.path.dirname(self.storage_file)
                    if self.storage_type == "sqlite"
                    else self.storagedir
                ),
                "details.zip",
            )

            self.code_postfetch = (
                self.config.get("code", "postfetch")
                if self.config.has_option("code", "postfetch")
                else None
            )
            self.code_follow = (
                self.config.get("code", "follow")
                if self.config.has_option("code", "follow")
                else None
            )
            self.hooks = {}
            if self.config.has_section("hooks"):
                for hook_name in [
                    "before_run",
                    "before_request",
                    "after_response",
                    "after_page",
                    "after_run",
                ]:
                    if self.config.has_option("hooks", hook_name):
                        self.hooks[hook_name] = self.config.get("hooks", hook_name)

            self.follow_enabled = False
            if self.config.has_section("follow"):
                self.follow_enabled = True
                self.follow_rules = []
                if self.config_format == "yaml" and hasattr(self.config, "_data"):
                    follow_data = self.config._data.get("follow")
                    if isinstance(follow_data, list):
                        self.follow_rules = follow_data
                    elif isinstance(follow_data, dict) and isinstance(
                        follow_data.get("rules"), list
                    ):
                        self.follow_rules = follow_data.get("rules")
                self.follow_data_key = (
                    self.config.get("follow", "follow_data_key")
                    if self.config.has_option("follow", "follow_data_key")
                    else None
                )
                self.follow_item_key = (
                    self.config.get("follow", "follow_item_key")
                    if self.config.has_option("follow", "follow_item_key")
                    else None
                )
                self.follow_mode = (
                    self.config.get("follow", "follow_mode")
                    if self.config.has_option("follow", "follow_mode")
                    else None
                )
                self.follow_http_mode = (
                    self.config.get("follow", "follow_http_mode")
                    if self.config.has_option("follow", "follow_http_mode")
                    else "GET"
                )
                self.follow_param = (
                    self.config.get("follow", "follow_param")
                    if self.config.has_option("follow", "follow_param")
                    else None
                )
                self.follow_pattern = (
                    self.config.get("follow", "follow_pattern")
                    if self.config.has_option("follow", "follow_pattern")
                    else None
                )
                self.follow_url_key = (
                    self.config.get("follow", "follow_url_key")
                    if self.config.has_option("follow", "follow_url_key")
                    else None
                )
            if self.config.has_section("files"):
                self.fetch_mode = self.config.get("files", "fetch_mode")
                self.default_ext = (
                    self.config.get("files", "default_ext")
                    if self.config.has_option("files", "default_ext")
                    else None
                )
                self.files_keys = self.config.get("files", "keys").split(",")
                self.root_url = self.config.get("files", "root_url")
                self.storage_mode = (
                    self.config.get("files", "storage_mode")
                    if self.config.has_option("files", "storage_mode")
                    else "filepath"
                )
                self.file_storage_type = (
                    self.config.get("files", "file_storage_type")
                    if self.config.has_option("files", "file_storage_type")
                    else "zip"
                )
                self.use_aria2 = (
                    self.config.get("files", "use_aria2")
                    if self.config.has_option("files", "use_aria2")
                    else "False"
                )
                self.files_max_file_size = (
                    _safe_int(self.config.get("files", "max_file_size"), "files.max_file_size", 0)
                    if self.config.has_option("files", "max_file_size")
                    else None
                )

            # Parse new config sections
            # Authentication
            self.auth_handler = None
            if self.config.has_section("auth"):
                self.auth_handler = AuthHandler(self.config)
                if self.auth_handler.auth_type == "apikey":
                    self.http.protected_headers.add(
                        self.auth_handler.auth_data.get("header", "X-API-Key")
                    )

            # Rate limiting
            self.rate_limiter = None
            if self.config.has_section("rate_limit"):
                enabled = (
                    self.config.getboolean("rate_limit", "enabled")
                    if self.config.has_option("rate_limit", "enabled")
                    else True
                )
                if enabled:
                    rps = None
                    rpm = None
                    rph = None
                    burst = 5
                    if self.config.has_option("rate_limit", "requests_per_second"):
                        try:
                            rps = float(self.config.get("rate_limit", "requests_per_second"))
                        except (TypeError, ValueError):
                            logging.warning("rate_limit.rps must be a number; ignored")
                    if self.config.has_option("rate_limit", "requests_per_minute"):
                        rpm = _safe_int(
                            self.config.get("rate_limit", "requests_per_minute"),
                            "rate_limit.requests_per_minute",
                            0,
                        )
                    if self.config.has_option("rate_limit", "requests_per_hour"):
                        rph = _safe_int(
                            self.config.get("rate_limit", "requests_per_hour"),
                            "rate_limit.requests_per_hour",
                            0,
                        )
                    if self.config.has_option("rate_limit", "burst_size"):
                        burst = _safe_int(
                            self.config.get("rate_limit", "burst_size"),
                            "rate_limit.burst_size",
                            5,
                        )
                    self.rate_limiter = RateLimiter(rps, rpm, rph, burst)
            self._rate_lock = threading.Lock()

            # Enhanced error handling
            self.error_retry_codes = DEFAULT_ERROR_STATUS_CODES
            self.max_consecutive_errors = 10
            self.continue_on_error = True

            if self.config.has_section("error_handling"):
                if self.config.has_option("error_handling", "retry_on_errors"):
                    # Schema-legal values:
                    #   YAML list  -> ``retry_on_errors: [500, 502]``
                    #   INI string -> ``retry_on_errors = 500, 502``
                    # Earlier code called ``int()`` on the raw string, which
                    # raised ``ValueError: int("[500")`` on the YAML list form
                    # and crashed the CLI before any command ran (§4.6 of the
                    # 2026-10 analysis report).
                    getter = getattr(self.config, "getvalue", self.config.get)
                    self.error_retry_codes = parse_status_codes(
                        getter("error_handling", "retry_on_errors")
                    )
                if self.config.has_option("error_handling", "max_consecutive_errors"):
                    self.max_consecutive_errors = _safe_int(
                        self.config.get("error_handling", "max_consecutive_errors"),
                        "error_handling.max_consecutive_errors",
                        10,
                    )
                if self.config.has_option("error_handling", "continue_on_error"):
                    self.continue_on_error = self.config.getboolean(
                        "error_handling", "continue_on_error"
                    )

            # Request configuration
            self.request_timeout = DEFAULT_TIMEOUT
            self.connect_timeout = 30
            self.read_timeout = DEFAULT_TIMEOUT
            self.verify_ssl = True
            self.user_agent = f"apibackuper/{__version__}"
            self.max_redirects = 5
            self.allow_redirects = True
            self.proxies = None
            self.parallelism = 1
            self.retry_policy: Dict[int, int] = {}
            self.retry_backoff_strategy = "fixed"
            self.retry_max_retries = self.retry_count
            self.retry_initial_delay = self.retry_delay
            self.retry_max_delay = max(self.retry_delay, self.retry_delay * 4)
            self.retry_on_status = self.error_retry_codes
            # Response rules and rate-limit header waits (YAML only).
            self.response_rules: List[Dict[str, Any]] = []
            self.retry_wait_headers: List[str] = ["Retry-After"]
            self.retry_max_wait = None
            self._rule_counts: Dict[str, int] = {}
            self._rule_lock = threading.Lock()

            if self.config.has_section("request"):
                if self.config.has_option("request", "timeout"):
                    self.request_timeout = _safe_int(
                        self.config.get("request", "timeout"),
                        "request.timeout",
                        DEFAULT_TIMEOUT,
                    )
                if self.config.has_option("request", "connect_timeout"):
                    self.connect_timeout = _safe_int(
                        self.config.get("request", "connect_timeout"),
                        "request.connect_timeout",
                        30,
                    )
                if self.config.has_option("request", "read_timeout"):
                    self.read_timeout = _safe_int(
                        self.config.get("request", "read_timeout"),
                        "request.read_timeout",
                        DEFAULT_TIMEOUT,
                    )
                if self.config.has_option("request", "verify_ssl"):
                    self.verify_ssl = self.config.getboolean("request", "verify_ssl")
                if self.config.has_option("request", "user_agent"):
                    self.user_agent = self.config.get("request", "user_agent")
                if self.config.has_option("request", "max_redirects"):
                    self.max_redirects = _safe_int(
                        self.config.get("request", "max_redirects"),
                        "request.max_redirects",
                        5,
                    )
                if self.config.has_option("request", "allow_redirects"):
                    self.allow_redirects = self.config.getboolean("request", "allow_redirects")
                # Proxies - for YAML, this would be a dict, for INI it's a string
                if self.config.has_option("request", "proxies"):
                    # Simple proxy string format: "http=http://proxy:8080,https=https://proxy:8080"
                    proxy_str = self.config.get("request", "proxies")
                    if proxy_str:
                        self.proxies = {}
                        for p in proxy_str.split(","):
                            if "=" in p:
                                k, v = p.split("=", 1)
                                self.proxies[k.strip()] = v.strip()
                if self.config_format == "yaml" and hasattr(self.config, "_data"):
                    request_data = self.config._data.get("request", {})
                    if isinstance(request_data, dict):
                        if isinstance(request_data.get("parallelism"), int):
                            self.parallelism = max(1, request_data.get("parallelism"))
                        rules = request_data.get("response_rules")
                        if isinstance(rules, list):
                            self.response_rules = [rule for rule in rules if isinstance(rule, dict)]
                        retry_data = request_data.get("retry")
                        if isinstance(retry_data, dict):
                            if isinstance(retry_data.get("wait_headers"), list):
                                self.retry_wait_headers = [
                                    str(name) for name in retry_data["wait_headers"]
                                ]
                            if retry_data.get("max_wait") is not None:
                                self.retry_max_wait = retry_data["max_wait"]
                            self.retry_max_retries = retry_data.get(
                                "max_retries", self.retry_max_retries
                            )
                            self.retry_backoff_strategy = retry_data.get(
                                "backoff_strategy", self.retry_backoff_strategy
                            )
                            self.retry_initial_delay = retry_data.get(
                                "initial_delay", self.retry_initial_delay
                            )
                            self.retry_max_delay = retry_data.get("max_delay", self.retry_max_delay)
                            retry_on = retry_data.get("retry_on_status")
                            if isinstance(retry_on, list):
                                self.retry_on_status = retry_on

                if self.config.has_option("request", "retry_max_retries"):
                    self.retry_max_retries = _safe_int(
                        self.config.get("request", "retry_max_retries"),
                        "request.retry_max_retries",
                        0,
                    )
                if self.config.has_option("request", "retry_backoff_strategy"):
                    self.retry_backoff_strategy = self.config.get(
                        "request", "retry_backoff_strategy"
                    )
                if self.config.has_option("request", "retry_initial_delay"):
                    self.retry_initial_delay = _safe_int(
                        self.config.get("request", "retry_initial_delay"),
                        "request.retry_initial_delay",
                        0,
                    )
                if self.config.has_option("request", "retry_max_delay"):
                    self.retry_max_delay = _safe_int(
                        self.config.get("request", "retry_max_delay"),
                        "request.retry_max_delay",
                        0,
                    )
                if self.config.has_option("request", "retry_on_status"):
                    getter = getattr(self.config, "getvalue", self.config.get)
                    self.retry_on_status = parse_status_codes(getter("request", "retry_on_status"))
                if self.config.has_option("request", "parallelism"):
                    self.parallelism = max(
                        1,
                        _safe_int(
                            self.config.get("request", "parallelism"),
                            "request.parallelism",
                            1,
                        ),
                    )

            # Storage enhancements
            self.compression_level = 6
            self.max_file_size = None
            self.split_files = False

            if self.config.has_section("storage"):
                if self.config.has_option("storage", "compression_level"):
                    self.compression_level = self.config.getint("storage", "compression_level")
                if self.config.has_option("storage", "max_file_size"):
                    self.max_file_size = self.config.getint("storage", "max_file_size")
                if self.config.has_option("storage", "split_files"):
                    self.split_files = self.config.getboolean("storage", "split_files")

            # Response capture: YAML ``storage.capture``; INI flat
            # ``capture_metadata`` / ``capture_raw_body`` keys.
            self.capture_metadata = True
            self.capture_raw_body = "auto"
            capture = (
                self.config._data.get("storage", {}).get("capture")
                if self.config_format == "yaml" and hasattr(self.config, "_data")
                else None
            )
            if isinstance(capture, dict):
                self.capture_metadata = bool(capture.get("metadata", True))
                self.capture_raw_body = capture.get("raw_body", "auto")
            elif self.config.has_section("storage"):
                if self.config.has_option("storage", "capture_metadata"):
                    self.capture_metadata = self.config.getboolean("storage", "capture_metadata")
                if self.config.has_option("storage", "capture_raw_body"):
                    self.capture_raw_body = self.config.get("storage", "capture_raw_body")

            # Initialize HTTP session with new settings
            self.http.headers.update({"User-Agent": self.user_agent})
            self.http.verify = self.verify_ssl  # Set verify at session level for all requests
            self.http.max_redirects = self.max_redirects
            if not self.verify_ssl:
                logging.warning(
                    "SSL certificate verification is disabled. "
                    "This makes connections vulnerable to man-in-the-middle attacks. "
                    "Set 'request.verify_ssl = true' in config to enable verification."
                )
            if self.proxies:
                self.http.proxies.update(self.proxies)

            if not self.update_mode:
                self.update_mode = "by_change_key" if self.change_key else "by_timestamp"

    def _raise_config_not_found(self) -> None:
        """Raise a consistent error when the config file is missing or unreadable."""
        if getattr(self, "_config_error", None) is not None:
            raise self._config_error
        raise FileNotFoundError(
            f"Configuration file not found in: {self.project_path} "
            "(expected apibackuper.yaml, apibackuper.yml or apibackuper.cfg)"
        )

    def _resolve_storage_file(self) -> str:
        storage_path = self.storage_path if hasattr(self, "storage_path") else "storage"
        if self.storage_type == "sqlite":
            candidate = storage_path
            if not os.path.isabs(candidate):
                candidate = os.path.join(self.project_path, candidate)
            if candidate.endswith(os.sep) or os.path.isdir(candidate):
                candidate = os.path.join(candidate, "storage.db")
            return candidate
        if self.storage_type == "filesystem":
            return self.storagedir
        return os.path.join(self.storagedir, "storage.zip")

    def _load_state(self) -> Dict[str, Any]:
        """Load persistent run state."""
        if not self.state_file or not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf8") as fobj:
                return json.load(fobj)
        except (IOError, OSError, ValueError) as e:
            logging.warning("Failed to load state file %s: %s", self.state_file, e)
            return {}

    def _save_state(self, state: Dict[str, Any], strict: bool = False) -> None:
        """Persist run state to disk atomically.

        Writes to ``state_file + ".tmp"`` first, fsync, then ``os.replace()``
        onto the final path so a crash mid-write cannot corrupt the live
        state file (§P3 atomic writes of the 2026-10 analysis report).
        """
        if not self.state_file:
            return
        try:
            state_dir = os.path.dirname(self.state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir)
            _atomic_write_json(self.state_file, state)
        except (IOError, OSError, ValueError) as e:
            if strict:
                raise
            logging.warning("Failed to write state file %s: %s", self.state_file, e)

    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint for resume."""
        if not self.checkpoint_file or not os.path.exists(self.checkpoint_file):
            return {}
        try:
            with open(self.checkpoint_file, "r", encoding="utf8") as fobj:
                return json.load(fobj)
        except (IOError, OSError, ValueError) as e:
            logging.warning("Failed to load checkpoint file %s: %s", self.checkpoint_file, e)
            return {}

    def _save_checkpoint(self, checkpoint: Dict[str, Any], strict: bool = False) -> None:
        """Persist checkpoint to disk atomically.

        Same atomic-write pattern as :meth:`_save_state` so a crashed run
        does not leave a half-written checkpoint file that subsequent
        resumes cannot parse.
        """
        if not self.checkpoint_file:
            return
        try:
            checkpoint_dir = os.path.dirname(self.checkpoint_file)
            if checkpoint_dir and not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir)
            _atomic_write_json(self.checkpoint_file, checkpoint)
        except (IOError, OSError, ValueError) as e:
            if strict:
                raise
            logging.warning("Failed to write checkpoint file %s: %s", self.checkpoint_file, e)

    def _run_hook(self, hook_name: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        hook_path = self.hooks.get(hook_name) if hasattr(self, "hooks") else None
        if not hook_path:
            return None
        try:
            resolved_path = hook_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self.project_path, resolved_path)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", delete=False) as temp_file:
                json.dump(context, temp_file, ensure_ascii=False)
                context_path = temp_file.name
            try:
                cmd = [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import json,runpy,sys;"
                        "ctx=json.load(open(sys.argv[1]));"
                        "mod=runpy.run_path(sys.argv[2]);"
                        "fn=mod.get('hook') or mod.get('run');"
                        "out=fn(ctx) if callable(fn) else None;"
                        "json.dump(out, sys.stdout) if out is not None else sys.stdout.write('null')"
                    ),
                    context_path,
                    resolved_path,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30, check=False
                )
                if result.returncode != 0:
                    logging.warning(
                        "Hook %s failed: %s", hook_name, redact_text(result.stderr.strip())
                    )
                    return None
                try:
                    return json.loads(result.stdout) if result.stdout else None
                except json.JSONDecodeError:
                    logging.warning("Hook %s returned non-JSON output", hook_name)
                    return None
            finally:
                os.unlink(context_path)
        except (IOError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
            logging.warning("Error running hook %s: %s", hook_name, redact_text(e))
            return None

    def _serialize_response(self, response: requests.Response) -> Dict[str, Any]:
        text = None
        try:
            text = response.text
        except (ValueError, RuntimeError):
            text = None
        truncated = False
        if text and len(text) > 2000:
            text = text[:2000]
            truncated = True
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "url": response.url,
            "text": text,
            "text_truncated": truncated,
        }

    def _should_retry(self, status_code: int) -> bool:
        retry_codes = self.retry_on_status or self.error_retry_codes
        return status_code in retry_codes

    def _get_retry_delay(self, attempt: int, response: Optional[requests.Response]) -> int:
        from .response_rules import header_wait

        # Server-provided waits (``Retry-After`` by default; seconds, HTTP
        # dates or Unix timestamps) override the configured backoff.
        wait = header_wait(response, getattr(self, "retry_wait_headers", ["Retry-After"]))
        if wait is not None:
            return wait
        if self.retry_backoff_strategy == "exponential":
            delay = self.retry_initial_delay * (2 ** (attempt - 1))
        else:
            delay = self.retry_initial_delay
        return int(min(max(delay, 0), self.retry_max_delay))

    def _parse_where(self, where: Optional[str]) -> Optional[Dict[str, Any]]:
        # P3.31: logic lifted to ``cmds.where_filter`` so it can be tested
        # in isolation. The wrapper preserves the existing call signature.
        from .where_filter import parse_where

        return parse_where(where, splitter=self.field_splitter)

    def _match_where(self, item: Dict[str, Any], condition: Optional[Dict[str, Any]]) -> bool:
        return match_where(item, condition)

    def _select_fields(self, item: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
        # P3.31: logic lifted to ``cmds.where_filter`` so it can be tested
        # in isolation. The wrapper preserves the existing call signature.
        from .where_filter import select_fields

        return select_fields(item, fields, splitter=self.field_splitter)

    def _single_request(
        self,
        url: str,
        headers: Optional[Dict[str, str]],
        params: Dict[str, Any],
        flatten: Optional[Dict[str, str]] = None,
        http_mode: Optional[str] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Single http/https request with authentication and rate limiting.

        Thin wrapper around ``apibackuper.cmds.http_client`` — that module
        owns the request-building, the retry-kwargs filtering, and the
        actionable error wrapping; this method owns the OAuth2 refresh
        trigger and the rate-limiter ordering.
        """
        from .http_client import build_request_kwargs, build_retry_kwargs, wrap_request_exception
        from .utils import append_query

        http_mode = http_mode or self.http_mode
        headers = dict(headers or {})

        try:
            # Apply rate limiting first — no point making the request if
            # we'd be violating the configured limit.
            if self.rate_limiter:
                with self._rate_lock:
                    self.rate_limiter.wait_if_needed()

            # Merge auth headers (the auth handler is the source of truth
            # for whatever the upstream service expects).
            used_token = None
            if self.auth_handler:
                # OAuth2: fetch or renew the token before it is needed.
                self.auth_handler.ensure_token(
                    self.http,
                    verify=self.verify_ssl,
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                used_token = self.auth_handler.auth_data.get("token")
                auth_headers = self.auth_handler.get_headers()
                if headers:
                    headers.update(auth_headers)
                else:
                    headers = auth_headers

            (method, request_kwargs, log_safe_url), actual_query_string = build_request_kwargs(
                http_mode="GET" if http_mode == "HEAD" else http_mode,
                url=url,
                params=params,
                flatten=flatten if self.flat_params else None,
                headers=headers,
                verify_ssl=self.verify_ssl,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
                allow_redirects=self.allow_redirects,
            )
            if stream:
                # File downloads read the body in chunks instead of at once.
                request_kwargs["stream"] = True
            # The flat-params branch returns an extra actual_query_string;
            # the regular branches return None and we use ``url`` directly.
            logging.info("url: %s", log_safe_url)

            session_method = getattr(self.http, method)
            if http_mode == "HEAD":
                session_method = self.http.head
            if actual_query_string is not None:
                response = session_method(append_query(url, actual_query_string), **request_kwargs)
            else:
                response = session_method(url, **request_kwargs)

            # Handle OAuth2 token refresh if needed.
            if (
                response.status_code == 401
                and self.auth_handler
                and self.auth_handler.auth_type == "oauth2"
            ):
                # P2.24: propagate the session's TLS verification flag and
                # timeout to the refresh POST.
                if self.auth_handler.refresh_token_if_needed(
                    self.http,
                    verify=self.verify_ssl,
                    timeout=(self.connect_timeout, self.read_timeout),
                    failed_token=used_token,
                ):
                    # Retry request with new token. The build_retry_kwargs
                    # helper produces a kwargs dict that is safe to spread
                    # alongside an explicit params=... argument (P1.13).
                    auth_headers = self.auth_handler.get_headers()
                    if headers:
                        headers.update(auth_headers)
                    else:
                        headers = auth_headers
                    retry_kwargs = build_retry_kwargs(request_kwargs, headers)
                    if http_mode in ("GET", "HEAD"):
                        method = self.http.head if http_mode == "HEAD" else self.http.get
                        if actual_query_string is not None:
                            response = method(
                                append_query(url, actual_query_string), **retry_kwargs
                            )
                        else:
                            response = method(url, params=params, **retry_kwargs)
                    else:
                        response = self.http.post(url, json=params, **retry_kwargs)

            return response
        except (requests.exceptions.RequestException, ValueError, RuntimeError, IOError) as e:
            wrapped = wrap_request_exception(
                e,
                url=url,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
                default_delay=self.default_delay,
                logfile=getattr(self, "logfile", None),
            )
            raise wrapped from None

    def _request(self, url, headers=None, params=None, flatten=None, http_mode=None, stream=False):
        """Execute every command's requests with bounded retries and status checks."""
        from .http_client import RequestFailed
        from .utils import redact_text, redact_url

        auth_handler = getattr(self, "auth_handler", None)
        if auth_handler and auth_handler.error:
            # Never fall back to unauthenticated requests.
            raise ValueError(auth_handler.error)
        from .response_rules import DEFAULT_MISSING_STATUSES, action_for

        rules = getattr(self, "response_rules", None) or []
        response = None
        budget = max(0, self.retry_max_retries)
        for attempt in range(budget + 1):
            try:
                response = self._single_request(
                    url, headers, params or {}, flatten, http_mode=http_mode, stream=stream
                )
            except RuntimeError as exc:
                if attempt == budget:
                    raise RuntimeError(redact_text(exc)) from None
            else:
                status = response.status_code
                action = (
                    action_for(rules, response, self.field_splitter, stream=stream)
                    if rules
                    else None
                )
                if action is not None:
                    self._count_rule(action)
                if action == "accept" or (action is None and 200 <= status < 300):
                    if self.default_delay:
                        time.sleep(self.default_delay)
                    return response
                if action == "missing":
                    raise RequestFailed(
                        f"HTTP {status} for {redact_url(url)}: object is missing",
                        status,
                        missing=True,
                    )
                if action == "fail":
                    raise RequestFailed(
                        f"HTTP {status} for {redact_url(url)} matched a fail response rule", status
                    )
                retryable = action == "retry" or (action is None and self._should_retry(status))
                if attempt == budget or not retryable:
                    reason = " (response rule: retry)" if action == "retry" else ""
                    raise RequestFailed(
                        f"HTTP {status} for {redact_url(url)}{reason}",
                        status,
                        # Without a rule, 404/410 still mean the object is gone.
                        missing=action is None and status in DEFAULT_MISSING_STATUSES,
                    )
            delay = self._get_retry_delay(attempt + 1, response)
            max_wait = getattr(self, "retry_max_wait", None)
            if max_wait is not None and delay > max_wait:
                raise RequestFailed(
                    f"HTTP {response.status_code} for {redact_url(url)} asks to wait {delay} s, "
                    f"more than request.retry.max_wait ({max_wait} s)",
                    response.status_code,
                )
            time.sleep(delay)
        raise RuntimeError("Request retry budget exhausted")

    def _count_rule(self, action: str) -> None:
        lock = getattr(self, "_rule_lock", None)
        if lock is None:
            return
        with lock:
            self._rule_counts[action] = self._rule_counts.get(action, 0) + 1

    @staticmethod
    def create(name: str) -> None:
        """Create new project"""
        try:
            if not os.path.exists(name):
                os.mkdir(name)
            config_filename = "apibackuper.cfg"
            config_path = os.path.join(name, config_filename)
            if os.path.exists(config_path):
                print("Project already exists")
            else:
                config = configparser.ConfigParser()
                config["settings"] = {"initialized": False, "name": name}
                try:
                    with open(config_path, "w", encoding="utf8") as f:
                        config.write(f)
                    print("Projects %s created" % (name))
                except (IOError, OSError) as e:
                    error_msg = (
                        f"Failed to write configuration file: {config_path}\n"
                        f"  Error: {str(e)}\n"
                        f"  Suggestions:\n"
                        f"    - Check if you have write permissions in the current directory\n"
                        f"    - Verify disk space is available\n"
                        f"    - Check if the file is locked by another process"
                    )
                    logging.error("Error writing config file %s: %s", config_path, e)
                    raise RuntimeError(error_msg) from e
        except PermissionError as e:
            error_msg = (
                f"Permission denied creating project directory: {name}\n"
                f"  Error: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check if you have write permissions in the current directory\n"
                f"    - Try running with appropriate permissions\n"
                f"    - Choose a different location for the project"
            )
            logging.error("Permission denied creating project directory %s: %s", name, e)
            raise RuntimeError(error_msg) from e
        except OSError as e:
            error_msg = (
                f"Failed to create project directory: {name}\n"
                f"  Error: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Suggestions:\n"
                f"    - Check if the directory already exists\n"
                f"    - Verify disk space is available\n"
                f"    - Check filesystem permissions"
            )
            logging.error("OS error creating project %s: %s", name, e)
            raise RuntimeError(error_msg) from e

    def export(self, format: str, filename: str, fields=None, where=None) -> None:
        """Export retained pages or followed objects through a shared pipeline."""
        from .export import export_project

        export_project(self, format, filename, fields=fields, where=where)

    def run(self, mode: str, resume: bool = False) -> None:
        """Collect data with durable storage and checkpoint publication."""
        from .backup import run_backup

        run_backup(self, mode, resume=resume)

    def sample(self, max_pages: int, preview: int = 3) -> Dict[str, Any]:
        """Collect at most ``max_pages`` pages into a temporary archive and preview them.

        The project's archive, state and checkpoint stay untouched, and the
        ``after_run`` hook does not run. Returns page and record counts, the
        record fields, the first records and the configuration warnings.
        """
        from .backup import run_backup
        from .probe import record_fields

        if max_pages < 1:
            raise ValueError("--max-pages must be at least 1")
        names = (
            "storage_path",
            "storagedir",
            "storage_file",
            "details_storage_file",
            "state_file",
            "checkpoint_file",
        )
        saved = {name: getattr(self, name, None) for name in names}
        with tempfile.TemporaryDirectory(prefix="apibackuper-sample-") as tmp:
            self.storagedir = os.path.join(tmp, "storage")
            self.storage_path = (
                os.path.join(tmp, "storage.db")
                if self.storage_type == "sqlite"
                else self.storagedir
            )
            self.storage_file = self._resolve_storage_file()
            self.details_storage_file = os.path.join(tmp, "details.zip")
            self.state_file = os.path.join(tmp, "state.json")
            self.checkpoint_file = os.path.join(tmp, "checkpoint.json")
            self.sample_max_pages = max_pages
            try:
                summary = run_backup(self, "full")
                exported = os.path.join(tmp, "sample.jsonl")
                self.export("jsonl", exported)
                with open(exported, "r", encoding="utf8") as fobj:
                    records = [json.loads(line) for line in fobj if line.strip()]
            finally:
                for name, value in saved.items():
                    setattr(self, name, value)
                self.sample_max_pages = None
        return {
            "pages": summary["pages_processed"],
            "records": len(records),
            "total_reported": summary["total"],
            "more_pages": summary["more_pages"],
            "fields": record_fields(records),
            "preview": records[:preview],
            "warnings": [issue["message"] for issue in self.validation_report()["warnings"]],
        }

    def update(self, resume: bool = False) -> None:
        """Run update mode with state tracking."""
        self.run("update", resume=resume)

    def _detect_suggestions(self, data: Any, headers: Any = None) -> Dict[str, Any]:
        suggestions: Dict[str, Any] = {}
        link = (headers or {}).get("Link") or (headers or {}).get("link")
        if link and any(
            "next" in str(entry.get("rel", "")).split()
            for entry in requests.utils.parse_header_links(link)
        ):
            suggestions["iterate_by"] = "link_header"
        if isinstance(data, dict):
            from .probe import PAGES_KEYS, TOTAL_KEYS, find_count_key, find_records_key

            splitter = self.field_splitter
            for name, key in (
                ("data_key", find_records_key(data, splitter)),
                ("total_number_key", find_count_key(data, TOTAL_KEYS, splitter)),
                ("pages_number_key", find_count_key(data, PAGES_KEYS, splitter)),
            ):
                if key:
                    suggestions[name] = key
            if "iterate_by" not in suggestions:
                suggestions.update(self._detect_cursor(data))
            if "iterate_by" not in suggestions:
                if "page" in data or "pages" in data:
                    suggestions["iterate_by"] = "page"
                elif "offset" in data or "skip" in data:
                    suggestions["iterate_by"] = "skip"
        return suggestions

    def _detect_cursor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest a next-URL or cursor mode from common response fields."""
        splitter = self.field_splitter
        for path in NEXT_URL_KEYS:
            key = path if path in data else splitter.join(path.split("."))
            value = data.get(key) if key in data else get_dict_value(data, key, splitter=splitter)
            if isinstance(value, str) and value.startswith(("http://", "https://", "/", "?")):
                return {"iterate_by": "next_url", "next_url_key": key}
        for path, param in NEXT_CURSOR_KEYS:
            key = splitter.join(path.split("."))
            # Only a scalar token counts; ``cursor`` may also name a wrapper object.
            value = get_dict_value(data, key, splitter=splitter)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and value != "":
                return {"iterate_by": "cursor", "next_cursor_key": key, "cursor_param": param}
        return {}

    def _apply_detection(self, suggestions: Dict[str, Any]) -> None:
        if not suggestions:
            return
        for name, (section, option) in DETECTED_OPTIONS.items():
            if suggestions.get(name) and not self.config.has_option(section, option):
                setattr(self, name, suggestions[name])

    def detect(self, write_config: bool = False, probe: bool = True) -> Dict[str, Any]:
        """Detect pagination and data keys from a sample request.

        With ``probe``, also report the record fields and a sample record, and
        send a few more requests to find the page, offset and size parameters.
        """
        headers = load_json_file(os.path.join(self.project_path, "headers.json"), default={})
        params = load_json_file(os.path.join(self.project_path, "params.json"), default={})
        url_params = load_json_file(
            os.path.join(self.project_path, "url_params.json"), default=None
        )
        if self.query_mode == "params":
            url = _url_replacer(self.start_url, url_params or {})
        elif self.query_mode == "mixed":
            url = _url_replacer(self.start_url, url_params or {}, query_mode=True)
        else:
            url = self.start_url
        response = self._request(url, headers, params, None)
        if self.resp_type != "json":
            print("Detection only supports JSON responses.")
            return {}
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            print("Detection failed: response is not valid JSON.")
            return {}
        suggestions = self._detect_suggestions(data, response.headers)
        if probe:
            suggestions.update(self._probe(url, headers, params, data, suggestions))
        if write_config and self.config_format == "yaml" and hasattr(self.config, "_data"):
            yaml_data = self.config._data
            apply_detected_options(yaml_data, suggestions)
            if YAML_AVAILABLE:
                with open(self.config_filename, "w", encoding="utf8") as fobj:
                    yaml.safe_dump(yaml_data, fobj, sort_keys=False, allow_unicode=True)
        return suggestions

    def _probe(
        self,
        url: str,
        headers: Dict[str, Any],
        params: Dict[str, Any],
        data: Any,
        suggestions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Describe the first page's records and probe for pagination parameters."""
        from .export import process_record
        from .probe import probe_pagination, record_fields

        data_key = self.data_key or suggestions.get("data_key")

        def records_of(payload: Any) -> List[Any]:
            if data_key and get_dict_value(payload, data_key, splitter=self.field_splitter) is None:
                return []
            return process_record(payload, data_key=data_key, field_splitter=self.field_splitter)

        records = records_of(data)
        info: Dict[str, Any] = {"records_on_first_page": len(records)}
        if records:
            info["fields"] = record_fields(records)
            info["sample_record"] = records[0]
        configured = self.config.has_option("project", "iterate_by")
        mode = self.iterate_by if configured else suggestions.get("iterate_by", "page")
        if mode not in PAGINATION_PARAMS or mode == "range":
            return info
        if all(self.config.has_option("params", name) for name in PAGINATION_PARAMS[mode]):
            return info
        total = None
        total_key = self.total_number_key or suggestions.get("total_number_key")
        if total_key:
            value = get_dict_value(data, total_key, splitter=self.field_splitter)
            if isinstance(value, (int, str)) and str(value).isdigit():
                total = int(value)

        def fetch(extra: Dict[str, Any]) -> Optional[List[Any]]:
            target = remove_query_keys(url, extra) if self.http_mode == "GET" else url
            try:
                response = self._request(target, headers, dict(params, **extra), None)
                return records_of(response.json())
            except (RuntimeError, ValueError, OSError):
                return None

        query = [key for key, _ in parse_qsl(urlsplit(url).query)]
        probed = probe_pagination(
            fetch,
            records,
            total,
            preferred=query + list(params),
            modes=(mode,) if configured else ("page", "skip"),
        )
        if probed.pop("count_is_page_length", False) and not self.total_number_key:
            # ``None`` overrides the suggestion, and apply_detected_options skips it.
            probed["total_number_key"] = None
            probed["warnings"].append(
                f"{total_key} equals the number of records on one page, not the total; "
                "it was not used as data.total_number_key"
            )
        info.update(probed)
        return info

    def verify(self, strict: bool = False) -> Dict[str, Any]:
        """Check archive members against their fixity manifests.

        The result is recorded in the state file as ``last_verification``.
        """
        if self.config is None:
            self._raise_config_not_found()
        from .fixity import verify_storage

        report = verify_storage(self, strict=strict)
        state = self._load_state()
        if state:
            state["last_verification"] = {
                "checked_at": report["checked_at"],
                "ok": report["ok"],
                "strict": strict,
            }
            self._save_state(state)
        return report

    def follow(self, mode: str = "full") -> None:
        """Collect related objects using the shared HTTP execution policy."""
        from .follow import follow_project

        follow_project(self, mode)

    def getfiles(self, be_careful: bool = False) -> None:
        """Downloads all files associated with this API data"""
        if be_careful:
            warnings.warn(
                "getfiles(be_careful=...) is deprecated and ignored; set files.max_file_size",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.config is None:
            self._raise_config_not_found()
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != "zip":
            print("Only zip storage supported right now")
            return
        storage_file = os.path.join(self.storagedir, "storage.zip")
        if not os.path.exists(storage_file):
            print("Storage file not found")
            return

        headers = load_json_file(os.path.join(self.project_path, "headers.json"), default={})

        if not self.config.has_section("files"):
            raise ValueError("getfiles requires a files section in the configuration")
        if self.fetch_mode not in ("prefix", "pattern"):
            raise ValueError(f"Unsupported files.fetch_mode: {self.fetch_mode}")
        if self.file_storage_type not in ("zip", "filesystem"):
            raise ValueError(f"Unsupported files.file_storage_type: {self.file_storage_type}")

        from .export import process_record
        from .http_client import RequestFailed

        uniq_ids: set = set()

        allfiles_name = os.path.join(self.storagedir, "allfiles.csv")
        if not os.path.exists(allfiles_name):
            # Read through the storage backend so pages still in the ZIP
            # journal after an interrupted run are included.
            if self.config.has_section("follow"):
                source, kind, data_key = self.details_storage_file, "object", self.follow_data_key
            else:
                source, kind, data_key = storage_file, "page", self.data_key
            logging.info("Extract file urls from downloaded data")
            backend = ZipStorageBackend(source, mode="r")
            try:
                names = backend.list_objects(kind)
                for fname in tqdm(
                    names,
                    desc="Extracting file URLs",
                    unit="file",
                    disable=progress_disable(not names),
                ):
                    data = json.loads(backend.get_object(fname, kind))
                    records = process_record(
                        data, data_key=data_key, field_splitter=self.field_splitter
                    )
                    for item in records:
                        for key in self.files_keys:
                            values = get_dict_value(
                                item, key, as_array=True, splitter=self.field_splitter
                            )
                            for value in values or []:
                                for uniq_id in value if isinstance(value, list) else [value]:
                                    if uniq_id is not None and str(uniq_id).strip():
                                        uniq_ids.add(str(uniq_id))
            finally:
                backend.close()

            logging.info("Storing all filenames")
            with open(allfiles_name, "w", encoding="utf8") as f:
                for u in uniq_ids:
                    f.write(str(u) + "\n")
        else:
            logging.info("Load all filenames")
            uniq_ids = load_file_list(allfiles_name)
        # Start download
        files_storage_file = os.path.join(self.storagedir, "files.zip")
        files_list_storage = os.path.join(self.storagedir, "files.list")
        files_skipped = os.path.join(self.storagedir, "files_skipped.list")
        if os.path.exists(files_list_storage):
            list_file = open(files_list_storage, "a", encoding="utf8")
        else:
            list_file = open(files_list_storage, "w", encoding="utf8")
        if os.path.exists(files_skipped):
            skipped_file = open(files_skipped, "a", encoding="utf8")
            skipped = csv.DictWriter(
                skipped_file,
                delimiter=";",
                fieldnames=["filename", "filesize", "reason"],
            )
        else:
            skipped_file = open(files_skipped, "w", encoding="utf8")
            skipped = csv.DictWriter(
                skipped_file,
                delimiter=";",
                fieldnames=["filename", "filesize", "reason"],
            )
            skipped.writeheader()
        # Ensure files are closed even if an exception occurs during downloads
        files_to_close = [list_file, skipped_file]

        use_aria2 = True if self.use_aria2 == "True" else False
        if use_aria2:
            aria2 = aria2p.API(aria2p.Client(host="http://localhost", port=6800, secret=""))
        else:
            aria2 = None
        if self.file_storage_type == "zip":
            fstorage = ZipStorageBackend(files_storage_file, mode="a", compression=ZIP_DEFLATED)
        elif self.file_storage_type == "filesystem":
            fstorage = FilesystemStorageBackend(
                os.path.join(self.storagedir, "files"),
                mode="a",
            )
        from .fixity import append_manifest_line, files_manifest_path, parse_manifest, stream_digest

        manifest_path = files_manifest_path(self)
        listed: set = set()
        if os.path.exists(manifest_path):
            with open(manifest_path, "rb") as handle:
                listed = set(parse_manifest(handle.read()))
        stored_names = set(fstorage.list_objects("object"))
        # Files stored by an interrupted run or an older version get their line now.
        for name in sorted(stored_names - listed):
            stream = fstorage.open_object(name)
            if stream is not None:
                append_manifest_line(manifest_path, name, stream_digest(stream))

        n = 0
        missing_files = 0
        total_files = len(uniq_ids)
        download_progress = None
        if total_files > 0:
            download_progress = tqdm(
                total=total_files,
                desc="Downloading files",
                unit="file",
                disable=progress_disable(),
            )
        try:
            for uniq_id in uniq_ids:
                if self.fetch_mode == "prefix":
                    url = self.root_url + str(uniq_id)
                elif self.fetch_mode == "pattern":
                    url = self.root_url.format(uniq_id)
                n += 1
                if n % 50 == 0:
                    logging.info("Downloaded %d files", n)
                if self.default_ext is not None:
                    filename = str(uniq_id) + "." + self.default_ext
                else:
                    filename = str(uniq_id)
                if self.storage_mode == "filepath":
                    filename = urlparse(url).path
                logging.info("Processing %s as %s", redact_url(url), filename)
                from ..storage import safe_member_name

                filename = safe_member_name(filename)
                if filename in stored_names:
                    logging.info("File %s already stored", filename)
                    if download_progress:
                        download_progress.update(1)
                    continue
                if not use_aria2:
                    try:
                        outcome, size, detail = self._download_file(
                            url, headers, fstorage, filename
                        )
                    except RequestFailed as error:
                        # A removed attachment must not stop the other downloads.
                        if not error.missing:
                            raise
                        skipped.writerow(
                            {
                                "filename": filename,
                                "filesize": "",
                                "reason": f"HTTP {error.status_code}",
                            }
                        )
                        missing_files += 1
                        if download_progress:
                            download_progress.update(1)
                        continue
                    if outcome == "skipped":
                        logging.info("File %s skipped: %s", filename, detail)
                        skipped.writerow(
                            {"filename": filename, "filesize": str(size), "reason": detail}
                        )
                    else:
                        # The member is durable before its manifest line is written.
                        fstorage.flush()
                        append_manifest_line(manifest_path, filename, detail)
                        stored_names.add(filename)
                        list_file.write(url + "\n")
                else:
                    aria2.add_uris(
                        uris=[
                            url,
                        ],
                        options={
                            "out": filename,
                            "dir": os.path.abspath(os.path.join(self.storagedir, "files")),
                        },
                    )
                if download_progress:
                    download_progress.update(1)
        finally:
            if download_progress:
                download_progress.close()
            fstorage.close()
            for fobj in files_to_close:
                try:
                    fobj.close()
                except (IOError, OSError):
                    pass
        if missing_files:
            print(f"Warning: {missing_files} files are missing upstream; " f"see {files_skipped}")

    def _download_file(self, url, headers, fstorage, filename) -> Tuple[str, int, str]:
        """Stream one file into ``fstorage``.

        Returns ``("stored", size, sha256)``, or ``("skipped", size, reason)``
        when it exceeds ``files.max_file_size``. The body is written in chunks
        to a temporary file beside the storage, so memory use does not grow with
        the file, and a failed or interrupted download leaves no stored member.
        """
        limit = getattr(self, "files_max_file_size", None)
        response = self._request(url, headers=headers, http_mode="GET", stream=True)
        temporary = None
        try:
            declared = response.headers.get("Content-Length")
            if limit and declared and declared.isdigit() and int(declared) > limit:
                return "skipped", int(declared), self._too_large(limit)
            digest = hashlib.sha256()
            size = 0
            fd, temporary = tempfile.mkstemp(dir=self.storagedir, prefix=".download-")
            with os.fdopen(fd, "wb") as handle:
                for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if limit and size > limit:
                        return "skipped", size, self._too_large(limit)
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            fstorage.save_object_from_path(filename, temporary)
            return "stored", size, digest.hexdigest()
        finally:
            response.close()
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _too_large(limit: int) -> str:
        return f"File larger than files.max_file_size ({limit} bytes)"

    def estimate(self, mode: str) -> Optional[Dict[str, Any]]:  # noqa: ARG002
        """Measures time, size and count of records and returns the figures"""
        if self.config is None:
            self._raise_config_not_found()
            return None
        from .backup import _decode
        from .export import process_record

        if not self.total_number_key:
            print("Can't estimate without total_number_key field in config file")
            return None
        if self.page_limit <= 0:
            raise ValueError("params.page_size_limit must be greater than zero")

        process_func = None
        if self.code_postfetch is not None:
            path = self.code_postfetch
            # Resolve like ``run`` does, relative to the project directory.
            script = run_path(
                path if os.path.isabs(path) else os.path.join(self.project_path, path)
            )
            process_func = script["process"]

        headers = load_json_file(os.path.join(self.project_path, "headers.json"), default={})
        params = load_json_file(os.path.join(self.project_path, "params.json"), default={})
        if self.flat_params:
            params = {k: flat_param_value(v) for k, v in params.items()}
        url_params = load_json_file(
            os.path.join(self.project_path, "url_params.json"), default=None
        )

        start = timer()
        if self.query_mode == "params":
            url = _url_replacer(self.start_url, url_params)
        elif self.query_mode == "mixed":
            url = _url_replacer(self.start_url, url_params, query_mode=True)
        else:
            url = self.start_url
        http_mode = "GET" if self.http_mode == "GET" else "POST"
        if http_mode == "GET" and self.flat_params and params:
            response = self._request(append_query(url, params), headers=headers or None)
        else:
            logging.debug(
                "Start request %s params: %s headers: %s",
                redact_url(url),
                redact_params(params),
                redact_headers(headers),
            )
            response = self._request(
                url, headers=headers or None, params=params or None, http_mode=http_mode
            )
        start_page_data = _decode(self, response.content, process_func)
        end = timer()

        raw_total = get_dict_value(
            start_page_data, self.total_number_key, splitter=self.field_splitter
        )
        try:
            total = int(raw_total)
        except (TypeError, ValueError):
            print(
                f"Can't estimate: total_number_key {self.total_number_key!r} is missing or "
                "not a number in the response"
            )
            return None
        request_time = end - start
        req_number = -(-total // self.page_limit)
        data = process_record(
            start_page_data, data_key=self.data_key, field_splitter=self.field_splitter
        )
        data_size = sum(len(json.dumps(r, ensure_ascii=False)) for r in data)
        avg_size = float(data_size) / len(data) if len(data) > 0 else 0.0

        print("Total records: %d" % (total))
        print("Records per request: %d" % (self.page_limit))
        print("Total requests: %d" % (req_number))
        print("Average record size %.2f bytes" % (avg_size))
        print("Estimated size (json lines) %.2f MB" % ((avg_size * total) / 1000000))
        print("Avg request time, seconds %.4f " % (request_time))
        print("Estimated all requests time, seconds %.4f " % (request_time * req_number))
        return {
            "total_records": total,
            "records_per_request": self.page_limit,
            "total_requests": req_number,
            "average_record_bytes": round(avg_size, 2),
            "estimated_jsonl_bytes": int(avg_size * total),
            "request_seconds": round(request_time, 4),
            "estimated_seconds": round(request_time * req_number, 4),
        }

    def info(self, stats: bool = False) -> Optional[Dict[str, Any]]:
        """Get project information and statistics"""
        if self.config is None:
            self._raise_config_not_found()
            return None

        report = {
            "project": {
                "name": self.name,
                "description": self.description,
                "url": self.start_url,
                "http_mode": self.http_mode,
                "response_type": self.resp_type,
                "storage_type": self.storage_type,
                "storage_path": self.storagedir,
                "log_file": self.logfile if hasattr(self, "logfile") else "apibackuper.log",
            },
            "configuration": {
                "page_limit": self.page_limit,
                "start_page": self.start_page,
                "iterate_by": self.iterate_by,
                "query_mode": self.query_mode,
                "default_delay": self.default_delay,
                "retry_count": self.retry_count,
                "retry_delay": self.retry_delay,
                "force_retry": self.force_retry,
            },
            "data": {
                "data_key": self.data_key,
                "total_number_key": self.total_number_key if self.total_number_key else None,
                "pages_number_key": self.pages_number_key if self.pages_number_key else None,
            },
            "params": {
                "page_number_param": self.page_number_param,
                "page_size_param": self.page_size_param,
                "count_skip_param": self.count_skip_param,
                "count_from_param": self.count_from_param,
                "count_to_param": self.count_to_param,
                "flat_params": self.flat_params,
            },
        }

        # Add request configuration
        report["request"] = {
            "timeout": self.request_timeout,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "verify_ssl": self.verify_ssl,
            "user_agent": self.user_agent,
            "max_redirects": self.max_redirects,
            "allow_redirects": self.allow_redirects,
            "proxies_configured": self.proxies is not None and len(self.proxies) > 0,
        }

        # Add error handling configuration
        report["error_handling"] = {
            "retry_on_codes": self.error_retry_codes,
            "max_consecutive_errors": self.max_consecutive_errors,
            "continue_on_error": self.continue_on_error,
        }

        # Add storage configuration
        report["storage_config"] = {
            "compression_level": self.compression_level,
            "max_file_size": self.max_file_size,
            "split_files": self.split_files,
        }

        # Add authentication info if configured
        if self.auth_handler:
            report["authentication"] = {"type": self.auth_handler.auth_type}

        # Add rate limiting info if configured
        if self.rate_limiter:
            report["rate_limiting"] = {
                "enabled": True,
                "requests_per_second": self.rate_limiter.requests_per_second,
                "requests_per_minute": self.rate_limiter.requests_per_minute,
                "requests_per_hour": self.rate_limiter.requests_per_hour,
            }
        else:
            report["rate_limiting"] = {"enabled": False}

        # Add follow configuration if enabled
        if self.follow_enabled:
            report["follow"] = {
                "enabled": True,
                "mode": self.follow_mode,
                "http_mode": self.follow_http_mode,
                "data_key": self.follow_data_key,
                "item_key": self.follow_item_key,
                "param": self.follow_param,
                "pattern": self.follow_pattern,
                "url_key": self.follow_url_key,
            }
        else:
            report["follow"] = {"enabled": False}

        # Add files configuration if enabled
        if self.config.has_section("files"):
            report["files"] = {
                "enabled": True,
                "fetch_mode": self.fetch_mode,
                "root_url": self.root_url,
                "keys": self.files_keys,
                "storage_mode": self.storage_mode,
                "file_storage_type": self.file_storage_type,
                "default_ext": self.default_ext,
                "use_aria2": self.use_aria2 == "True",
            }
        else:
            report["files"] = {"enabled": False}

        # Add code configuration if present
        if self.code_postfetch or self.code_follow:
            report["code"] = {}
            if self.code_postfetch:
                report["code"]["postfetch"] = self.code_postfetch
            if self.code_follow:
                report["code"]["follow"] = self.code_follow

        # Add statistics if requested and storage exists
        if stats:
            stats_data = {}

            # Storage statistics, read through the backend so filesystem
            # storage and pages still in a ZIP journal are counted too.
            if os.path.exists(self.storage_file):
                try:
                    storage_backend = build_storage_backend(
                        self.storage_type, self.storage_file, "read"
                    )
                    try:
                        file_list = storage_backend.list_objects("page")
                        total_size = 0
                        total_records = 0
                        for fname in tqdm(
                            file_list,
                            desc="Counting records",
                            unit="file",
                            leave=False,
                            disable=progress_disable(len(file_list) <= 100),
                        ):
                            try:
                                content = storage_backend.get_object(fname, "page")
                                if content is None:
                                    continue
                                total_size += len(content)
                                data = json.loads(content)
                                if self.data_key:
                                    items = get_dict_value(
                                        data, self.data_key, splitter=self.field_splitter
                                    )
                                    if isinstance(items, list):
                                        total_records += len(items)
                                    elif items is not None:
                                        total_records += 1
                                else:
                                    if isinstance(data, list):
                                        total_records += len(data)
                                    elif data is not None:
                                        total_records += 1
                            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                                logging.debug("Error counting records in %s: %s", fname, e)
                        captured = sum(
                            1
                            for name in storage_backend.list_objects("object")
                            if name.rsplit("/", 1)[-1].startswith("exchange_")
                        )
                    finally:
                        storage_backend.close()
                    stats_data["storage"] = {
                        "file_exists": True,
                        "total_files": len(file_list),
                        "captured_exchanges": captured,
                        "generation_archives": len(
                            getattr(storage_backend, "generation_archives", list)()
                        ),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                        "total_records": total_records,
                        "avg_records_per_file": (
                            round(total_records / len(file_list), 2) if len(file_list) > 0 else 0
                        ),
                    }
                except (IOError, OSError, ValueError, zipfile.BadZipFile) as e:
                    logging.error("Error reading storage: %s", e)
                    stats_data["storage"] = {"file_exists": True, "error": str(e)}
            else:
                stats_data["storage"] = {"file_exists": False}

            # Details storage statistics
            details_file = self.details_storage_file
            if os.path.exists(details_file):
                try:
                    mzip = ZipFile(details_file, mode="r", compression=ZIP_DEFLATED)
                    file_list = mzip.namelist()
                    total_size = sum(mzip.getinfo(f).file_size for f in file_list)

                    stats_data["details"] = {
                        "file_exists": True,
                        "total_files": len(file_list),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                    }

                    mzip.close()
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error("Error reading details file: %s", e)
                    stats_data["details"] = {"file_exists": True, "error": str(e)}
            else:
                stats_data["details"] = {"file_exists": False}

            # Files storage statistics
            files_storage_file = os.path.join(self.storagedir, "files.zip")
            if os.path.exists(files_storage_file):
                try:
                    mzip = ZipFile(files_storage_file, mode="r", compression=ZIP_DEFLATED)
                    file_list = mzip.namelist()
                    total_size = sum(mzip.getinfo(f).file_size for f in file_list)

                    stats_data["files"] = {
                        "file_exists": True,
                        "total_files": len(file_list),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                    }

                    mzip.close()
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error("Error reading files storage: %s", e)
                    stats_data["files"] = {"file_exists": True, "error": str(e)}
            else:
                stats_data["files"] = {"file_exists": False}

            report["statistics"] = stats_data

        state = self._load_state()
        if state:
            report["run"] = {
                "last_run_start": state.get("last_run_start"),
                "last_run_end": state.get("last_run_end"),
                "status": "success" if state.get("last_run_end") else "unknown",
                "records_processed": state.get("records_processed"),
                "bytes_processed": state.get("bytes_processed"),
                "last_page": state.get("last_page"),
                "last_change_key": state.get("last_change_key"),
            }
            if state.get("last_verification"):
                report["verification"] = state["last_verification"]

        return report

    def validate_config(
        self,
        verbose: bool = False,
    ) -> Tuple[bool, int, int]:
        """Validate project configuration.

        Returns a tuple ``(is_valid, error_count, warning_count)`` so callers
        can distinguish "valid with warnings" from "valid clean" without
        re-reading the printed output. ``is_valid`` is ``True`` iff there are
        no errors (warnings do not invalidate).
        """
        report = self.validation_report(verbose=verbose)
        errors, warnings = report["errors"], report["warnings"]

        # Print results
        if verbose or errors or warnings:
            if errors:
                print("Errors found:")
                for error in errors:
                    print(f"  ERROR: {error['message']}")
            if warnings:
                print("Warnings:")
                for warning in warnings:
                    print(f"  WARNING: {warning['message']}")

        return report["valid"], len(errors), len(warnings)

    def validation_report(self, verbose: bool = False) -> Dict[str, Any]:
        """Return ``{"valid", "errors", "warnings"}`` without printing.

        Each issue is a dictionary with the configuration ``path`` (``None``
        for the whole file), a ``message`` and, when known, a ``hint``.
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        def error(path: Optional[str], message: str, hint: Optional[str] = None) -> None:
            errors.append(_issue(path, message, hint))

        def warn(path: Optional[str], message: str, hint: Optional[str] = None) -> None:
            warnings.append(_issue(path, message, hint))

        def report() -> Dict[str, Any]:
            return {"valid": not errors, "errors": errors, "warnings": warnings}

        if self.config is None:
            error(
                None,
                "Configuration file not found",
                "Create apibackuper.yaml in the project directory or pass --projectpath",
            )
            return report()

        if self.config_format == "ini":
            warn(None, "INI configuration is deprecated; use YAML instead")

        # For YAML configs, use schema validation first
        if self.config_format == "yaml" and JSONSCHEMA_AVAILABLE:
            try:
                # Reload the YAML file to get raw data for schema validation
                if os.path.exists(self.config_filename):
                    with open(self.config_filename, "r", encoding="utf8") as fobj:
                        yaml_data = yaml.safe_load(fobj)
                    if yaml_data:
                        try:
                            yaml_data = substitute_env_vars(
                                yaml_data,
                                source=self.config_filename,
                            )
                        except UnresolvedEnvVarError as e:
                            error(None, str(e), f"Export {e.name} before running the command")
                            return report()

                    if yaml_data:
                        is_valid, validation_errors = validate_yaml_config(yaml_data)
                        if not is_valid:
                            for schema_error in validation_errors:
                                path = schema_error.get("path", "root")
                                msg = schema_error.get("message", "Unknown error")
                                error(
                                    path,
                                    f"Schema validation error at {path}: {msg}",
                                    "Run 'apibackuper schema' to see allowed fields and types",
                                )
            except (IOError, OSError, ValueError) as e:
                if verbose:
                    warn(None, f"Could not perform schema validation: {e}")

        # Check required sections
        required_sections = ["settings", "project", "params", "data", "storage"]
        for section in required_sections:
            if not self.config.has_section(section):
                error(section, f"Missing required section: {section}")

        # Validate settings section
        if self.config.has_section("settings"):
            if not self.config.has_option("settings", "name"):
                error("settings.name", "Missing required option: settings.name")

        # Validate project section
        if self.config.has_section("project"):
            if not self.config.has_option("project", "url"):
                error("project.url", "Missing required option: project.url")
            else:
                try:
                    url = self.config.get("project", "url")
                    if not url.startswith(("http://", "https://")):
                        error("project.url", f"Invalid URL format: {url}")
                except (configparser.NoOptionError, configparser.NoSectionError):
                    error("project.url", "Invalid or missing project.url")

            if not self.config.has_option("project", "http_mode"):
                error("project.http_mode", "Missing required option: project.http_mode")
            else:
                try:
                    http_mode = self.config.get("project", "http_mode")
                    if http_mode not in ["GET", "POST"]:
                        error(
                            "project.http_mode",
                            f"Invalid http_mode: {http_mode} (must be GET or POST)",
                        )
                except (configparser.NoOptionError, configparser.NoSectionError):
                    error("project.http_mode", "Invalid or missing project.http_mode")

        # Validate params section
        if self.config.has_section("params"):
            if not self.config.has_option("params", "page_size_limit"):
                error("params.page_size_limit", "Missing required option: params.page_size_limit")
            else:
                try:
                    limit = self.config.getint("params", "page_size_limit")
                    if limit <= 0:
                        error("params.page_size_limit", "page_size_limit must be greater than 0")
                except (ValueError, configparser.NoOptionError, configparser.NoSectionError):
                    error("params.page_size_limit", "page_size_limit must be an integer")

        # Validate response rules (YAML request.response_rules)
        if hasattr(self.config, "_data"):
            from .response_rules import validate_rules

            request_data = self.config._data.get("request") or {}
            if isinstance(request_data, dict):
                for message in validate_rules(request_data.get("response_rules")):
                    error("request.response_rules", message)

        # Validate cursor-style pagination
        iterate_by = (
            self.config.get("project", "iterate_by")
            if self.config.has_option("project", "iterate_by")
            else "page"
        )
        if iterate_by == "cursor":
            if not self.config.has_option("data", "next_cursor_key"):
                error(
                    "data.next_cursor_key",
                    "data.next_cursor_key is required for iterate_by: cursor",
                    "Set it to the response path of the next-page token",
                )
            if not self.config.has_option("params", "cursor_param"):
                error(
                    "params.cursor_param",
                    "params.cursor_param is required for iterate_by: cursor",
                    "Set it to the request parameter that receives the token",
                )
        elif iterate_by == "next_url" and not self.config.has_option("data", "next_url_key"):
            error(
                "data.next_url_key",
                "data.next_url_key is required for iterate_by: next_url",
                "Set it to the response path of the next-page URL",
            )
        if iterate_by in CURSOR_MODES and getattr(self, "parallelism", 1) > 1:
            error(
                "request.parallelism",
                f"request.parallelism must be 1 for iterate_by: {iterate_by}, "
                "because each request depends on the previous response",
            )

        # Without the parameter its mode needs, a run requests only page 1.
        missing = [
            name
            for name in PAGINATION_PARAMS.get(iterate_by, ())
            if not self.config.has_option("params", name)
        ]
        if missing and self.config.has_section("params"):
            names = " and ".join(f"params.{name}" for name in missing)
            warn(
                f"params.{missing[0]}",
                f"{names} not set for iterate_by: {iterate_by}; "
                "only the first page will be collected",
                "Set it to the API's pagination parameter name, or run "
                "'apibackuper detect' to probe it",
            )

        # Validate storage section
        if self.config.has_section("storage"):
            if not self.config.has_option("storage", "storage_type"):
                error("storage.storage_type", "Missing required option: storage.storage_type")
            else:
                storage_type = self.config.get("storage", "storage_type")
                if storage_type not in ["zip", "filesystem", "sqlite"]:
                    warn(
                        "storage.storage_type",
                        f"Storage type '{storage_type}' may not be fully supported",
                    )

        # Validate authentication if configured
        if self.config.has_section("auth"):
            auth_type = (
                self.config.get("auth", "type") if self.config.has_option("auth", "type") else None
            )
            if not auth_type:
                error("auth.type", "auth.type is required when auth section is present")
            elif auth_type == "basic":
                if not self.config.has_option("auth", "username"):
                    error("auth.username", "auth.username is required for basic authentication")
                if not self.config.has_option("auth", "password") and not self.config.has_option(
                    "auth", "password_file"
                ):
                    error(
                        "auth.password",
                        "auth.password or auth.password_file is required for basic authentication",
                    )
            elif auth_type == "bearer":
                if not self.config.has_option("auth", "token") and not self.config.has_option(
                    "auth", "token_file"
                ):
                    error(
                        "auth.token",
                        "auth.token or auth.token_file is required for bearer authentication",
                    )
            elif auth_type == "apikey":
                if not self.config.has_option("auth", "api_key"):
                    error("auth.api_key", "auth.api_key is required for apikey authentication")
            elif auth_type == "oauth2" and (
                self.config.get("auth", "grant_type", fallback="refresh_token")
                == "client_credentials"
            ):
                for option in ("auth_url", "client_id"):
                    if not self.config.has_option("auth", option):
                        error(f"auth.{option}", f"auth.{option} is required for client_credentials")
                if not (
                    self.config.has_option("auth", "client_secret")
                    or self.config.has_option("auth", "client_secret_file")
                ):
                    error(
                        "auth.client_secret",
                        "auth.client_secret or auth.client_secret_file is required "
                        "for client_credentials",
                    )
            elif auth_type == "oauth2":
                has_token = self.config.has_option("auth", "token") or self.config.has_option(
                    "auth", "token_file"
                )
                can_refresh = self.config.has_option(
                    "auth", "refresh_token"
                ) and self.config.has_option("auth", "auth_url")
                if not (has_token or can_refresh):
                    error(
                        "auth.token",
                        "auth.token, auth.token_file, or auth.refresh_token with auth.auth_url "
                        "is required for oauth2 authentication",
                    )
            auth_handler = getattr(self, "auth_handler", None)
            if auth_handler is not None and auth_handler.error:
                error("auth", auth_handler.error)

        # Validate rate limiting if configured
        if self.config.has_section("rate_limit"):
            if self.config.has_option("rate_limit", "requests_per_second"):
                try:
                    rps = float(self.config.get("rate_limit", "requests_per_second"))
                    if rps <= 0:
                        error(
                            "rate_limit.requests_per_second",
                            "rate_limit.requests_per_second must be greater than 0",
                        )
                except ValueError:
                    error(
                        "rate_limit.requests_per_second",
                        "rate_limit.requests_per_second must be a number",
                    )

        return report()
