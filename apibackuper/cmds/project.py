# -* coding: utf-8 -*-
import configparser
import csv
import io
import json
import logging
import os
import time
import threading
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import zipfile
import warnings
from timeit import default_timer as timer
from zipfile import ZipFile, ZIP_DEFLATED
import gzip
from urllib.parse import urlparse
import requests
from contextlib import suppress
from runpy import run_path
from typing import Optional, Dict, Any, List

# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=PendingDeprecationWarning)

import xmltodict

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

with suppress(ImportError):
    import aria2p

from ..common import get_dict_value, update_dict_values
from ..constants import (
    DEFAULT_DELAY,
    FIELD_SPLITTER,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT,
    FILE_SIZE_DOWNLOAD_LIMIT,
    DEFAULT_ERROR_STATUS_CODES,
    RETRY_DELAY,
    DEFAULT_NUMBER_OF_PAGES
)
from ..storage import FilesystemStorage, ZipFileStorage, build_storage_backend
from ..auth import AuthHandler
from ..rate_limiter import RateLimiter

from tqdm import tqdm

try:
    import pandas as pd
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

# Helper class for Zstandard text file writing
if ZSTD_AVAILABLE:
    class ZstdTextWriter:
        """Wrapper for writing text to Zstandard-compressed files"""
        def __init__(self, filename, level=22, encoding="utf8"):
            self.f = open(filename, "wb")
            cctx = zstd.ZstdCompressor(level=level)
            self.compressor = cctx.stream_writer(self.f)
            self.text_wrapper = io.TextIOWrapper(self.compressor, encoding=encoding)

        def write(self, data):
            return self.text_wrapper.write(data)

        def close(self):
            if self.text_wrapper:
                self.text_wrapper.flush()
                self.text_wrapper.close()
            if self.compressor:
                self.compressor.close()
            if self.f:
                self.f.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
            return False

# Import from refactored modules
from .config_loader import (
    load_json_file,
    validate_yaml_config,
    YAMLConfigParser,
    JSONSCHEMA_AVAILABLE
)

from .utils import load_file_list, load_csv_data, _url_replacer



class ProjectBuilder:
    """Project builder"""

    def __init__(self, project_path: Optional[str] = None) -> None:
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
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
            self.config_format = 'yaml'
        elif self._yaml_available and os.path.exists(yaml_config_yml):
            self.config_filename = yaml_config_yml
            self.config_format = 'yaml'
        elif os.path.exists(ini_config):
            self.config_filename = ini_config
            self.config_format = 'ini'
        else:
            # Default to INI format for backward compatibility
            self.config_filename = ini_config
            self.config_format = 'ini'

        self.__read_config(self.config_filename)
        self.enable_logging()

    def enable_logging(self) -> None:
        """Enable logging to file (no stdout/stderr output by default)"""
        logFormatter = logging.Formatter(
            "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
        )
        rootLogger = logging.getLogger()

        # Remove existing handlers to avoid duplicates
        rootLogger.handlers.clear()

        fileHandler = logging.FileHandler("{0}".format(self.logfile))
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)

    def __read_config(self, filename: str) -> None:
        self.config = None
        if not os.path.exists(filename):
            return

        if self.config_format == 'yaml':
            if not self._yaml_available:
                logging.warning("YAML config file found but PyYAML is not installed. Falling back to INI.")
                # Try to fall back to INI
                ini_config = os.path.join(self.project_path, "apibackuper.cfg")
                if os.path.exists(ini_config):
                    self.config_filename = ini_config
                    self.config_format = 'ini'
                    self.__read_config(ini_config)
                    return
                else:
                    return

            try:
                with open(filename, "r", encoding="utf8") as fobj:
                    yaml_data = yaml.safe_load(fobj)

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
            self.storage_path = (self.config.get(
                "storage", "storage_path") if self.config.has_option(
                    "storage", "storage_path") else "storage")
            self.storagedir = os.path.join(self.project_path, self.storage_path)
            self.field_splitter = (self.config.get(
                "settings", "splitter") if self.config.has_option(
                    "settings", "splitter") else FIELD_SPLITTER)
            self.id = (self.config.get("settings", "id") if self.config.has_option(
                "settings", "id") else None)
            self.name = self.config.get("settings", "name")
            self.logfile = (self.config.get("settings", "logfile") if self.config.has_option(
                "settings", "logfile") else "apibackuper.log")
            self.state_file = (self.config.get("settings", "state_file") if self.config.has_option(
                "settings", "state_file") else os.path.join(self.project_path, "apibackuper_state.json"))
            self.checkpoint_file = (self.config.get("settings", "checkpoint_file") if self.config.has_option(
                "settings", "checkpoint_file") else os.path.join(self.project_path, "apibackuper_checkpoint.json"))
            self.checkpoint_interval_pages = (self.config.getint(
                "settings", "checkpoint_interval_pages") if self.config.has_option(
                    "settings", "checkpoint_interval_pages") else 0)
            self.data_key = self.config.get("data", "data_key") if self.config.has_option('data', 'data_key') else None
            self.change_key = self.config.get("data", "change_key") if self.config.has_option('data', 'change_key') else None
            self.storage_type = self.config.get("storage", "storage_type")
            self.http_mode = self.config.get("project", "http_mode")
            self.description = (self.config.get(
                "project", "description") if self.config.has_option(
                    "project", "description") else None)
            self.start_url = self.config.get("project", "url")
            self.page_limit = self.config.getint("params", "page_size_limit")
            self.resp_type = (self.config.get("project",
                                       "resp_type") if self.config.has_option(
                                           "project", "resp_type") else "json")
            self.iterate_by = (self.config.get(
                "project", "iterate_by") if self.config.has_option(
                    "project", "iterate_by") else "page")
            self.detect_enabled = (self.config.getboolean(
                "project", "detect") if self.config.has_option(
                    "project", "detect") else False)
            self.update_mode = (self.config.get(
                "project", "update_mode") if self.config.has_option(
                    "project", "update_mode") else None)
            self.default_delay = (self.config.getint(
                "project", "default_delay") if self.config.has_option(
                    "project", "default_delay") else DEFAULT_DELAY)
            self.retry_delay = (self.config.getint(
                "project", "retry_delay") if self.config.has_option(
                    "project", "retry_delay") else RETRY_DELAY)
            self.force_retry = (self.config.getboolean(
                "project", "force_retry") if self.config.has_option(
                    "project", "force_retry") else False)
            self.retry_count = (self.config.getint(
                "project", "retry_count") if self.config.has_option(
                    "project", "retry_count") else DEFAULT_RETRY_COUNT)

            self.start_page = (self.config.getint("params", "start_page") if
                               self.config.has_option("params", "start_page") else 1)
            self.query_mode = (self.config.get(
                "params", "query_mode") if self.config.has_option(
                    "params", "query_mode") else "query")
            self.flat_params = (self.config.getboolean(
                "params", "force_flat_params") if self.config.has_option(
                    "params", "force_flat_params") else False)
            self.change_key_param = (self.config.get(
                "params", "change_key_param") if self.config.has_option(
                    "params", "change_key_param") else None)
            self.update_since_param = (self.config.get(
                "params", "update_since_param") if self.config.has_option(
                    "params", "update_since_param") else None)
            self.total_number_key = (self.config.get("data", "total_number_key")
                                     if self.config.has_option(
                                         "data", "total_number_key") else "")
            self.pages_number_key = (self.config.get("data", "pages_number_key")
                                     if self.config.has_option(
                                         "data", "pages_number_key") else "")
            self.page_number_param = (self.config.get(
                "params", "page_number_param") if self.config.has_option(
                    "params", "page_number_param") else None)
            self.count_skip_param = (self.config.get(
                "params", "count_skip_param") if self.config.has_option(
                    "params", "count_skip_param") else None)
            self.count_from_param = (self.config.get(
                "params", "count_from_param") if self.config.has_option(
                    "params", "count_from_param") else None)
            self.count_to_param = (self.config.get(
                "params", "count_to_param") if self.config.has_option(
                    "params", "count_to_param") else None)
            self.page_size_param = (self.config.get(
                "params", "page_size_param") if self.config.has_option(
                    "params", "page_size_param") else None)
            self.storage_file = self._resolve_storage_file()
            self.details_storage_file = os.path.join(self.storagedir,
                                                     "details.zip")

            self.code_postfetch = self.config.get('code', 'postfetch') if self.config.has_option('code', 'postfetch') else None
            self.code_follow = self.config.get('code', 'follow') if self.config.has_option('code', 'follow') else None
            self.hooks = {}
            if self.config.has_section("hooks"):
                for hook_name in ["before_run", "before_request", "after_response", "after_page", "after_run"]:
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
                    elif isinstance(follow_data, dict) and isinstance(follow_data.get("rules"), list):
                        self.follow_rules = follow_data.get("rules")
                self.follow_data_key = (self.config.get(
                    "follow", "follow_data_key") if self.config.has_option(
                        "follow", "follow_data_key") else None)
                self.follow_item_key = (self.config.get(
                    "follow", "follow_item_key") if self.config.has_option(
                        "follow", "follow_item_key") else None)
                self.follow_mode = (self.config.get(
                    "follow", "follow_mode") if self.config.has_option(
                        "follow", "follow_mode") else None)
                self.follow_http_mode = (self.config.get(
                    "follow", "follow_http_mode") if self.config.has_option(
                        "follow", "follow_http_mode") else "GET")
                self.follow_param = (self.config.get("follow", "follow_param")
                                     if self.config.has_option(
                                         "follow", "follow_param") else None)
                self.follow_pattern = (self.config.get(
                    "follow", "follow_pattern") if self.config.has_option(
                        "follow", "follow_pattern") else None)
                self.follow_url_key = (self.config.get(
                    "follow", "follow_url_key") if self.config.has_option(
                        "follow", "follow_url_key") else None)
            if self.config.has_section("files"):
                self.fetch_mode = self.config.get("files", "fetch_mode")
                self.default_ext = (self.config.get(
                    "files", "default_ext") if self.config.has_option(
                        "files", "default_ext") else None)
                self.files_keys = self.config.get("files", "keys").split(",")
                self.root_url = self.config.get("files", "root_url")
                self.storage_mode = (self.config.get(
                    "files", "storage_mode") if self.config.has_option(
                        "files", "storage_mode") else "filepath")
                self.file_storage_type = (self.config.get(
                    "files", "file_storage_type") if self.config.has_option(
                        "files", "file_storage_type") else "zip")
                self.use_aria2 = (self.config.get(
                    "files", "use_aria2") if self.config.has_option(
                        "files", "use_aria2") else "False")

            # Parse new config sections
            # Authentication
            self.auth_handler = None
            if self.config.has_section("auth"):
                self.auth_handler = AuthHandler(self.config)

            # Rate limiting
            self.rate_limiter = None
            if self.config.has_section("rate_limit"):
                enabled = self.config.getboolean("rate_limit", "enabled") if self.config.has_option("rate_limit", "enabled") else True
                if enabled:
                    rps = None
                    rpm = None
                    rph = None
                    burst = 5
                    if self.config.has_option("rate_limit", "requests_per_second"):
                        rps = float(self.config.get("rate_limit", "requests_per_second"))
                    if self.config.has_option("rate_limit", "requests_per_minute"):
                        rpm = self.config.getint("rate_limit", "requests_per_minute")
                    if self.config.has_option("rate_limit", "requests_per_hour"):
                        rph = self.config.getint("rate_limit", "requests_per_hour")
                    if self.config.has_option("rate_limit", "burst_size"):
                        burst = self.config.getint("rate_limit", "burst_size")
                    self.rate_limiter = RateLimiter(rps, rpm, rph, burst)
            self._rate_lock = threading.Lock()

            # Enhanced error handling
            self.error_retry_codes = DEFAULT_ERROR_STATUS_CODES
            self.max_consecutive_errors = 10
            self.continue_on_error = True

            if self.config.has_section("error_handling"):
                if self.config.has_option("error_handling", "retry_on_errors"):
                    codes_str = self.config.get("error_handling", "retry_on_errors")
                    self.error_retry_codes = [int(c.strip()) for c in codes_str.split(",")]
                if self.config.has_option("error_handling", "max_consecutive_errors"):
                    self.max_consecutive_errors = self.config.getint("error_handling", "max_consecutive_errors")
                if self.config.has_option("error_handling", "continue_on_error"):
                    self.continue_on_error = self.config.getboolean("error_handling", "continue_on_error")

            # Request configuration
            self.request_timeout = DEFAULT_TIMEOUT
            self.connect_timeout = 30
            self.read_timeout = DEFAULT_TIMEOUT
            self.verify_ssl = True
            self.user_agent = "apibackuper/1.0.11"
            self.max_redirects = 5
            self.allow_redirects = True
            self.proxies = None
            self.parallelism = 1
            self.retry_policy = {}
            self.retry_backoff_strategy = "fixed"
            self.retry_max_retries = self.retry_count
            self.retry_initial_delay = self.retry_delay
            self.retry_max_delay = max(self.retry_delay, self.retry_delay * 4)
            self.retry_on_status = self.error_retry_codes

            if self.config.has_section("request"):
                if self.config.has_option("request", "timeout"):
                    self.request_timeout = self.config.getint("request", "timeout")
                if self.config.has_option("request", "connect_timeout"):
                    self.connect_timeout = self.config.getint("request", "connect_timeout")
                if self.config.has_option("request", "read_timeout"):
                    self.read_timeout = self.config.getint("request", "read_timeout")
                if self.config.has_option("request", "verify_ssl"):
                    self.verify_ssl = self.config.getboolean("request", "verify_ssl")
                if self.config.has_option("request", "user_agent"):
                    self.user_agent = self.config.get("request", "user_agent")
                if self.config.has_option("request", "max_redirects"):
                    self.max_redirects = self.config.getint("request", "max_redirects")
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
                        retry_data = request_data.get("retry")
                        if isinstance(retry_data, dict):
                            self.retry_max_retries = retry_data.get("max_retries", self.retry_max_retries)
                            self.retry_backoff_strategy = retry_data.get(
                                "backoff_strategy", self.retry_backoff_strategy
                            )
                            self.retry_initial_delay = retry_data.get(
                                "initial_delay", self.retry_initial_delay
                            )
                            self.retry_max_delay = retry_data.get(
                                "max_delay", self.retry_max_delay
                            )
                            retry_on = retry_data.get("retry_on_status")
                            if isinstance(retry_on, list):
                                self.retry_on_status = retry_on

                if self.config.has_option("request", "retry_max_retries"):
                    self.retry_max_retries = self.config.getint("request", "retry_max_retries")
                if self.config.has_option("request", "retry_backoff_strategy"):
                    self.retry_backoff_strategy = self.config.get("request", "retry_backoff_strategy")
                if self.config.has_option("request", "retry_initial_delay"):
                    self.retry_initial_delay = self.config.getint("request", "retry_initial_delay")
                if self.config.has_option("request", "retry_max_delay"):
                    self.retry_max_delay = self.config.getint("request", "retry_max_delay")
                if self.config.has_option("request", "retry_on_status"):
                    codes_str = self.config.get("request", "retry_on_status")
                    self.retry_on_status = [int(c.strip()) for c in codes_str.split(",")]
                if self.config.has_option("request", "parallelism"):
                    self.parallelism = max(1, self.config.getint("request", "parallelism"))

            # Logging configuration
            if self.config.has_section("logging"):
                log_level = self.config.get("logging", "level") if self.config.has_option("logging", "level") else "INFO"
                log_level_map = {
                    "DEBUG": logging.DEBUG,
                    "INFO": logging.INFO,
                    "WARNING": logging.WARNING,
                    "ERROR": logging.ERROR
                }
                logging.getLogger().setLevel(log_level_map.get(log_level.upper(), logging.INFO))

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

            # Initialize HTTP session with new settings
            self.http.headers.update({"User-Agent": self.user_agent})
            self.http.verify = self.verify_ssl  # Set verify at session level for all requests
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
        """Raise a consistent error when config file is missing."""
        config_files = [
            os.path.join(self.project_path, "apibackuper.yaml"),
            os.path.join(self.project_path, "apibackuper.yml"),
            os.path.join(self.project_path, "apibackuper.cfg")
        ]
        found_files = [f for f in config_files if os.path.exists(f)]
        error_msg = (
            f"Configuration file not found in: {self.project_path}\n"
            f"  Expected files: apibackuper.yaml, apibackuper.yml, or apibackuper.cfg\n"
        )
        if found_files:
            error_msg += f"  Found files: {', '.join(os.path.basename(f) for f in found_files)}\n"
        error_msg += (
            "  Suggestions:\n"
            "    - Run 'apibackuper create <name>' to create a new project\n"
            "    - Navigate to the project directory first\n"
            f"    - Use --projectpath option to specify project location"
        )
        print(f"Error: {error_msg}")

    def _resolve_storage_file(self) -> str:
        storage_path = self.storage_path if hasattr(self, "storage_path") else "storage"
        if self.storage_type == "sqlite":
            candidate = storage_path
            if not os.path.isabs(candidate):
                candidate = os.path.join(self.project_path, candidate)
            if candidate.endswith(os.sep) or os.path.isdir(candidate):
                candidate = os.path.join(candidate, "storage.db")
            return candidate
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

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Persist run state to disk."""
        if not self.state_file:
            return
        try:
            state_dir = os.path.dirname(self.state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir)
            with open(self.state_file, "w", encoding="utf8") as fobj:
                json.dump(state, fobj, ensure_ascii=False, indent=2)
        except (IOError, OSError, ValueError) as e:
            logging.warning("Failed to write state file %s: %s", self.state_file, e)

    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint for resume."""
        if not self.checkpoint_file or not os.path.exists(self.checkpoint_file):
            return {}
        try:
            with open(self.checkpoint_file, "r", encoding="utf8") as fobj:
                return json.load(fobj)
        except (IOError, OSError, ValueError) as e:
            logging.warning("Failed to load checkpoint file %s: %s",
                            self.checkpoint_file, e)
            return {}

    def _save_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """Persist checkpoint to disk."""
        if not self.checkpoint_file:
            return
        try:
            checkpoint_dir = os.path.dirname(self.checkpoint_file)
            if checkpoint_dir and not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir)
            with open(self.checkpoint_file, "w", encoding="utf8") as fobj:
                json.dump(checkpoint, fobj, ensure_ascii=False, indent=2)
        except (IOError, OSError, ValueError) as e:
            logging.warning("Failed to write checkpoint file %s: %s",
                            self.checkpoint_file, e)

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
                    resolved_path
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False
                )
                if result.returncode != 0:
                    logging.warning("Hook %s failed: %s", hook_name, result.stderr.strip())
                    return None
                try:
                    return json.loads(result.stdout) if result.stdout else None
                except json.JSONDecodeError:
                    logging.warning("Hook %s returned non-JSON output", hook_name)
                    return None
            finally:
                os.unlink(context_path)
        except (IOError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
            logging.warning("Error running hook %s: %s", hook_name, e)
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
            "text_truncated": truncated
        }

    def _should_retry(self, status_code: int) -> bool:
        retry_codes = self.retry_on_status or self.error_retry_codes
        return status_code in retry_codes

    def _get_retry_delay(self, attempt: int, response: Optional[requests.Response]) -> int:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
        if self.retry_backoff_strategy == "exponential":
            delay = self.retry_initial_delay * (2 ** (attempt - 1))
        else:
            delay = self.retry_initial_delay
        return int(min(max(delay, 0), self.retry_max_delay))

    def _parse_where(self, where: Optional[str]) -> Optional[Dict[str, Any]]:
        if not where:
            return None
        operators = ["<=", ">=", "!=", "==", ">", "<"]
        for op in operators:
            if op in where:
                left, right = where.split(op, 1)
                field = left.strip()
                value = right.strip().strip('"').strip("'")
                try:
                    if "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                return {"field": field, "op": op, "value": value}
        return None

    def _match_where(self, item: Dict[str, Any], condition: Optional[Dict[str, Any]]) -> bool:
        if not condition:
            return True
        field = condition["field"]
        op = condition["op"]
        value = condition["value"]
        actual = get_dict_value(item, field, splitter=self.field_splitter)
        if actual is None:
            return False
        try:
            if op == "==":
                return actual == value
            if op == "!=":
                return actual != value
            if op == ">":
                return actual > value
            if op == "<":
                return actual < value
            if op == ">=":
                return actual >= value
            if op == "<=":
                return actual <= value
        except TypeError:
            return False
        return False

    def _select_fields(self, item: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
        if not fields:
            return item
        selected = {}
        for field in fields:
            selected[field] = get_dict_value(item, field, splitter=self.field_splitter)
        return selected

    def _single_request(
        self,
        url: str,
        headers: Optional[Dict[str, str]],
        params: Dict[str, Any],
        flatten: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """Single http/https request with authentication and rate limiting"""
        try:
            # Apply rate limiting
            if self.rate_limiter:
                with self._rate_lock:
                    self.rate_limiter.wait_if_needed()

            # Merge auth headers
            if self.auth_handler:
                auth_headers = self.auth_handler.get_headers()
                if headers:
                    headers.update(auth_headers)
                else:
                    headers = auth_headers

            # Prepare request kwargs
            request_kwargs = {
                "verify": self.verify_ssl,
                "timeout": (self.connect_timeout, self.read_timeout),
                "allow_redirects": self.allow_redirects
            }

            if self.http_mode == "GET":
                if self.flat_params and len(params.keys()) > 0:
                    s = []
                    for key, value in flatten.items():
                        s.append("%s=%s" %
                                 (key, value.replace("'", '"').replace("True", "true")))
                    logging.info("url: %s", url + "?" + "&".join(s))
                    if headers:
                        request_kwargs["headers"] = headers
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                    else:
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                else:
                    logging.info("url: %s, params: %s", url, str(params))
                    if headers:
                        request_kwargs["headers"] = headers
                    request_kwargs["params"] = params
                    response = self.http.get(url, **request_kwargs)
            else:
                logging.debug("Request %s, params %s, headers %s",
                              url, str(params), str(headers))
                if headers:
                    request_kwargs["headers"] = headers
                request_kwargs["json"] = params
                response = self.http.post(url, **request_kwargs)

            # Handle OAuth2 token refresh if needed
            if response.status_code == 401 and self.auth_handler and self.auth_handler.auth_type == "oauth2":
                if self.auth_handler.refresh_token_if_needed(self.http):
                    # Retry request with new token
                    auth_headers = self.auth_handler.get_headers()
                    if headers:
                        headers.update(auth_headers)
                    else:
                        headers = auth_headers
                    request_kwargs["headers"] = headers
                    if self.http_mode == "GET":
                        response = self.http.get(url, params=params, **request_kwargs)
                    else:
                        response = self.http.post(url, json=params, **request_kwargs)

            return response
        except requests.exceptions.Timeout as e:
            timeout_info = f"Connect timeout: {self.connect_timeout}s, Read timeout: {self.read_timeout}s"
            error_msg = (
                f"Request timeout while connecting to {url}\n"
                f"  Current timeout settings: {timeout_info}\n"
                f"  Error details: {str(e)}\n"
                "  Suggestions:\n"
                f"    - Increase timeout values in [request] section:\n"
                f"      connect_timeout = {self.connect_timeout * 2}\n"
                f"      read_timeout = {self.read_timeout * 2}\n"
                "    - Check network connectivity and API server status\n"
                "    - Verify the URL is correct and accessible"
            )
            logging.error("Request timeout for URL %s: %s", url, e)
            raise RuntimeError(error_msg) from e
        except requests.exceptions.SSLError as e:
            error_msg = (
                f"SSL certificate verification failed for {url}\n"
                f"  Error details: {str(e)}\n"
                "  Suggestions:\n"
                "    - If this is a trusted server, disable SSL verification in [request] section:\n"
                "      verify_ssl = False\n"
                "    - Or provide a path to a trusted certificate bundle:\n"
                "      verify_ssl = /path/to/certificate.pem\n"
                "    - Update your system's certificate store\n"
                "    - Check if the server's certificate has expired"
            )
            logging.error("SSL error for URL %s: %s", url, e)
            raise RuntimeError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            error_msg = (
                f"Failed to connect to {url}\n"
                f"  Error details: {str(e)}\n"
                "  Suggestions:\n"
                "    - Check your internet connection\n"
                f"    - Verify the URL is correct: {url}\n"
                "    - Check if the API server is running and accessible\n"
                "    - If using a proxy, verify proxy settings in [request] section\n"
                "    - Check firewall settings"
            )
            logging.error("Connection error for URL %s: %s", url, e)
            raise RuntimeError(error_msg) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else "unknown"
            error_msg = (
                f"HTTP error {status_code} for {url}\n"
                f"  Error details: {str(e)}\n"
            )
            if hasattr(e, 'response') and e.response:
                error_msg += f"  Response status: {e.response.status_code}\n"
                if e.response.status_code == 401:
                    error_msg += (
                        "  Suggestions:\n"
                        "    - Check authentication credentials in [auth] section\n"
                        "    - Verify API key or token is valid and not expired\n"
                        "    - Check if authentication type matches API requirements"
                    )
                elif e.response.status_code == 403:
                    error_msg += (
                        "  Suggestions:\n"
                        "    - Check if your account has permission to access this resource\n"
                        "    - Verify API key has required permissions\n"
                        "    - Check rate limiting or quota restrictions"
                    )
                elif e.response.status_code == 404:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Verify the URL is correct: {url}\n"
                        "    - Check if the API endpoint exists\n"
                        "    - Review API documentation for correct endpoint path"
                    )
                elif e.response.status_code == 429:
                    error_msg += (
                        "  Suggestions:\n"
                        "    - You are being rate limited. Wait before retrying\n"
                        "    - Configure rate limiting in [rate_limit] section\n"
                        f"    - Increase delays between requests in [project] section:\n"
                        f"      default_delay = {self.default_delay * 2}"
                    )
                elif e.response.status_code >= 500:
                    error_msg += (
                        "  Suggestions:\n"
                        "    - This is a server error. The API may be temporarily unavailable\n"
                        "    - Wait a few minutes and try again\n"
                        "    - Check API status page if available\n"
                        "    - Increase retry settings in [project] section"
                    )
            logging.error("HTTP error for URL %s: %s", url, e)
            raise RuntimeError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = (
                f"Request failed for {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check network connectivity\n"
                f"    - Verify URL and request parameters\n"
                f"    - Review configuration settings\n"
                f"    - Check logs for more details: {self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'}"
            )
            logging.error("Request error for URL %s: %s", url, e)
            raise RuntimeError(error_msg) from e
        except (ValueError, RuntimeError, IOError) as e:
            error_msg = (
                f"Unexpected error while requesting {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Suggestions:\n"
                f"    - Check logs for more details: {self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'}\n"
                f"    - Verify configuration is correct\n"
                f"    - Try running with --verbose flag for more information"
            )
            logging.error("Unexpected error in request to %s: %s", url, e,
                          exc_info=True)
            raise RuntimeError(error_msg) from e

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
                    logging.error("Error writing config file %s: %s",
                                  config_path, e)
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
            logging.error("Permission denied creating project directory %s: %s",
                          name, e)
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

    def init(
        self,
        url: str,  # noqa: ARG002
        pagekey: str,  # noqa: ARG002
        pagesize: str,  # noqa: ARG002
        datakey: str,  # noqa: ARG002
        itemkey: str,  # noqa: ARG002
        changekey: str,  # noqa: ARG002
        iterateby: str,  # noqa: ARG002
        http_mode: str,  # noqa: ARG002
        work_modes: str,  # noqa: ARG002
    ) -> None:
        """[TBD] Unfinished method. Don't use it please"""
        self.__read_config(self.config_filename)
        if self.config is None:
            self._raise_config_not_found()
            return

    def export(
        self,
        format: str,
        filename: str,
        fields: Optional[List[str]] = None,
        where: Optional[str] = None
    ) -> None:  # noqa: A002, W0622
        """Exports data as JSON lines, gzip, zstd, or parquet formats"""
        if self.config is None:
            self._raise_config_not_found()
            return

        if not filename:
            print("Error: Output filename is required")
            return

        try:
            condition = self._parse_where(where)
            # Check if parquet format is requested
            if format == "parquet":
                if not PARQUET_AVAILABLE:
                    print("Parquet format requires pandas and pyarrow. Please install them: pip install pandas pyarrow")
                    return
                # Collect all records first for parquet export
                all_records = []
            elif format == "jsonl":
                try:
                    outfile = open(filename, "w", encoding="utf8")  # noqa: SIM117
                except (IOError, PermissionError) as e:
                    error_msg = (
                        f"Cannot write to output file: {filename}\n"
                        f"  Error: {str(e)}\n"
                        f"  Suggestions:\n"
                        f"    - Check if you have write permissions for the file/directory\n"
                        f"    - Verify the directory exists and is accessible\n"
                        f"    - Check if the file is locked by another process\n"
                        f"    - Ensure you have sufficient disk space"
                    )
                    logging.error("Error opening output file %s: %s",
                                  filename, e)
                    print(f"Error: {error_msg}")
                    return
            elif format == "gzip":
                try:
                    outfile = gzip.open(filename, mode="wt", encoding="utf8")  # noqa: SIM117
                except (IOError, PermissionError) as e:
                    error_msg = (
                        f"Cannot write to gzip file: {filename}\n"
                        f"  Error: {str(e)}\n"
                        f"  Suggestions:\n"
                        f"    - Check if you have write permissions for the file/directory\n"
                        f"    - Verify the directory exists and is accessible\n"
                        f"    - Check if the file is locked by another process\n"
                        f"    - Ensure you have sufficient disk space"
                    )
                    logging.error("Error opening gzip file %s: %s", filename, e)
                    print(f"Error: {error_msg}")
                    return
            elif format == "zstd":
                if not ZSTD_AVAILABLE:
                    print("Zstandard format requires zstandard library. "
                          "Please install it: pip install zstandard")
                    return
                try:
                    # Create Zstandard compressor with maximum compression level (22)
                    outfile = ZstdTextWriter(filename, level=22, encoding="utf8")  # noqa: SIM117
                except (IOError, PermissionError) as e:
                    error_msg = (
                        f"Cannot write to zstd file: {filename}\n"
                        f"  Error: {str(e)}\n"
                        f"  Suggestions:\n"
                        f"    - Check if you have write permissions for the file/directory\n"
                        f"    - Verify the directory exists and is accessible\n"
                        f"    - Check if the file is locked by another process\n"
                        f"    - Ensure you have sufficient disk space"
                    )
                    logging.error("Error opening zstd file %s: %s", filename, e)
                    print(f"Error: {error_msg}")
                    return
            else:
                print("Supported formats: 'jsonl', 'gzip', 'zstd', 'parquet'")
                return
        except (IOError, OSError, ValueError) as e:
            logging.error("Error setting up export: %s", e)
            print(f"Error: Failed to set up export: {e}")
            return

        progress_bar = None
        try:
            details_file = os.path.join(self.storagedir, "details.zip")
            if self.config.has_section("follow") and os.path.exists(details_file):
                try:
                    mzip = ZipFile(details_file, mode="r", compression=ZIP_DEFLATED)
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error("Error opening details zip file: %s", e)
                    print(f"Error: Cannot read details file: {e}")
                    if format != "parquet":
                        outfile.close()
                    return
                try:
                    file_list = mzip.namelist()
                    total_files = len(file_list)
                    if total_files > 0:
                        progress_bar = tqdm(total=total_files, desc="Exporting files", unit="file")

                    for fname in file_list:
                        try:
                            tf = mzip.open(fname, "r")
                            logging.info("Loading %s", fname)
                            try:
                                data = json.load(tf)
                            except (json.JSONDecodeError, ValueError) as e:
                                logging.warning(f"Error parsing JSON from {fname}: {e}")
                                continue
                            finally:
                                tf.close()
                            try:
                                if self.follow_data_key:
                                    follow_data = get_dict_value(
                                        data,
                                        self.follow_data_key,
                                        splitter=self.field_splitter)
                                    if isinstance(follow_data, dict):
                                        if self._match_where(follow_data, condition):
                                            follow_data = self._select_fields(follow_data, fields)
                                            if format == "parquet":
                                                all_records.append(follow_data)
                                            else:
                                                outfile.write(
                                                    json.dumps(follow_data, ensure_ascii=False) +
                                                    "\n")
                                    else:
                                        for item in follow_data:
                                            if not self._match_where(item, condition):
                                                continue
                                            item = self._select_fields(item, fields)
                                            if format == "parquet":
                                                all_records.append(item)
                                            else:
                                                outfile.write(
                                                    json.dumps(item, ensure_ascii=False) +
                                                    "\n")
                                else:
                                    if self._match_where(data, condition):
                                        data = self._select_fields(data, fields)
                                        if format == "parquet":
                                            all_records.append(data)
                                        else:
                                            outfile.write(
                                                json.dumps(data, ensure_ascii=False) + "\n")
                            except KeyError:
                                logging.info("Data key: %s not found", self.data_key)
                        except (IOError, OSError, ValueError) as e:
                            logging.warning("Error processing file %s: %s",
                                            fname, e)
                        finally:
                            if progress_bar:
                                progress_bar.update(1)
                finally:
                    if progress_bar:
                        progress_bar.close()
                    mzip.close()
            else:
                if not os.path.exists(self.storage_file):
                    print("Storage file not found %s" % (self.storage_file))
                    if format != "parquet":
                        outfile.close()
                    return
                if self.storage_type == "sqlite":
                    try:
                        storage_backend = build_storage_backend("sqlite", self.storage_file, "continue")
                    except (IOError, OSError, ValueError) as e:
                        print(f"Error: Cannot open storage backend: {e}")
                        if format != "parquet":
                            outfile.close()
                        return
                    try:
                        file_list = storage_backend.list_objects("page")
                        total_files = len(file_list)
                        if total_files > 0:
                            progress_bar = tqdm(total=total_files, desc="Exporting files", unit="file")
                        for fname in file_list:
                            try:
                                content = storage_backend.get_object(fname, "page")
                                if content is None:
                                    continue
                                data = json.loads(content)
                                if self.data_key:
                                    for item in get_dict_value(
                                            data, self.data_key,
                                            splitter=self.field_splitter):
                                        if not self._match_where(item, condition):
                                            continue
                                        item = self._select_fields(item, fields)
                                        if format == "parquet":
                                            all_records.append(item)
                                        else:
                                            outfile.write(
                                                json.dumps(item, ensure_ascii=False) + "\n")
                                else:
                                    for item in data:
                                        if not self._match_where(item, condition):
                                            continue
                                        item = self._select_fields(item, fields)
                                        if format == "parquet":
                                            all_records.append(item)
                                        else:
                                            outfile.write(
                                                json.dumps(item, ensure_ascii=False) + "\n")
                            except (json.JSONDecodeError, ValueError) as e:
                                logging.warning("Error parsing JSON from %s: %s", fname, e)
                            finally:
                                if progress_bar:
                                    progress_bar.update(1)
                    finally:
                        if progress_bar:
                            progress_bar.close()
                        storage_backend.close()
                else:
                    storage_file = self.storage_file
                    try:
                        mzip = ZipFile(storage_file, mode="r", compression=ZIP_DEFLATED)
                    except (IOError, OSError, zipfile.BadZipFile) as e:
                        error_msg = (
                            f"Cannot read storage file: {storage_file}\n"
                            f"  Error: {str(e)}\n"
                            f"  Suggestions:\n"
                            f"    - Check if the file exists and is accessible\n"
                            f"    - Verify file permissions\n"
                            f"    - The file may be corrupted - try running the backup again\n"
                            f"    - Check if the file is locked by another process"
                        )
                        logging.error("Error opening storage zip file %s: %s",
                                      storage_file, e)
                        print(f"Error: {error_msg}")
                        if format != "parquet":
                            outfile.close()
                        return
                    try:
                        file_list = mzip.namelist()
                        total_files = len(file_list)
                        if total_files > 0:
                            progress_bar = tqdm(total=total_files, desc="Exporting files", unit="file")

                        for fname in file_list:
                            try:
                                tf = mzip.open(fname, "r")
                                try:
                                    data = json.load(tf)
                                except (json.JSONDecodeError, ValueError) as e:
                                    logging.warning(f"Error parsing JSON from {fname}: {e}")
                                    continue
                                finally:
                                    tf.close()
                                try:
                                    if self.data_key:
                                        for item in get_dict_value(
                                                data, self.data_key,
                                                splitter=self.field_splitter):
                                            if not self._match_where(item, condition):
                                                continue
                                            item = self._select_fields(item, fields)
                                            if format == "parquet":
                                                all_records.append(item)
                                            else:
                                                outfile.write(
                                                    json.dumps(item, ensure_ascii=False) + "\n")
                                    else:
                                        for item in data:
                                            if not self._match_where(item, condition):
                                                continue
                                            item = self._select_fields(item, fields)
                                            if format == "parquet":
                                                all_records.append(item)
                                            else:
                                                outfile.write(
                                                    json.dumps(item, ensure_ascii=False) + "\n")
                                except KeyError:
                                    logging.info("Data key: %s not found", self.data_key)
                            except (IOError, OSError, ValueError) as e:
                                logging.warning("Error processing file %s: %s",
                                                fname, e)
                            finally:
                                if progress_bar:
                                    progress_bar.update(1)
                    finally:
                        if progress_bar:
                            progress_bar.close()
                        mzip.close()

            # Handle parquet export
            if format == "parquet":
                if len(all_records) == 0:
                    print("No records found to export")
                    return
                try:
                    df = pd.DataFrame(all_records)
                    df.to_parquet(filename, engine='pyarrow', index=False)
                    logging.info("Data exported to %s (%d records)", filename, len(all_records))
                except (IOError, OSError, ValueError, ImportError) as e:
                    logging.error("Error exporting to parquet: %s", str(e))
                    print("Error exporting to parquet: %s" % str(e))
            else:
                try:
                    outfile.close()
                    logging.info("Data exported to %s", filename)
                except (IOError, OSError) as e:
                    logging.error("Error closing output file: %s", e)
        except (IOError, OSError, ValueError) as e:
            logging.error("Error during export: %s", e)
            print(f"Error: Export failed: {e}")
            if progress_bar:
                try:
                    progress_bar.close()
                except Exception:
                    pass
            if format != "parquet" and 'outfile' in locals():
                try:
                    outfile.close()
                except Exception:
                    pass

    def run(self, mode: str, resume: bool = False) -> None:
        """Run data collection"""
        if self.config is None:
            self._raise_config_not_found()
            return

        storage_backend = None
        progress_bar = None
        run_start_time = datetime.now(timezone.utc)
        state = self._load_state() if mode == "update" else {}
        checkpoint = self._load_checkpoint() if resume else {}
        last_change_value = state.get("last_change_key")
        last_run_end = state.get("last_run_end")
        resume_page = checkpoint.get("last_page") if resume else None
        pages_processed = 0
        total_records = 0
        total_bytes = 0
        error_counts: Dict[str, int] = {}
        try:
            try:
                if self.storage_type == "zip":
                    os.makedirs(self.storagedir, exist_ok=True)
                elif self.storage_type == "sqlite":
                    storage_dir = os.path.dirname(self.storage_file)
                    if storage_dir:
                        os.makedirs(storage_dir, exist_ok=True)
                else:
                    print(f"Unsupported storage type: {self.storage_type}")
                    return
            except (OSError, PermissionError) as e:
                logging.error("Error creating storage directory: %s", e)
                print(f"Error: Cannot create storage directory: {e}")
                return

            process_func = None
            if self.code_postfetch is not None:
                try:
                    script = run_path(self.code_postfetch)
                    process_func = script.get('process')
                    if process_func is None:
                        logging.warning("No 'process' function found in postfetch script")
                except (IOError, OSError, ValueError) as e:
                    logging.error("Error loading postfetch script: %s", e)
                    print(f"Warning: Error loading postfetch script: {e}")

            try:
                storage_backend = build_storage_backend(self.storage_type, self.storage_file, mode)
            except (IOError, OSError, PermissionError, ValueError) as e:
                logging.error("Error opening storage backend: %s", e)
                print(f"Error: Cannot open storage backend: {e}")
                return

            start = timer()
            try:
                headers = load_json_file(os.path.join(self.project_path,
                                                      "headers.json"),
                                         default={})
            except (IOError, OSError, ValueError) as e:
                logging.warning("Error loading headers.json: %s", e)
                headers = {}

            try:
                params = load_json_file(os.path.join(self.project_path, "params.json"),
                                        default={})
            except (IOError, OSError, ValueError) as e:
                logging.warning("Error loading params.json: %s", e)
                params = {}

            if self.flat_params:
                flatten = {}
                for k, v in params.items():
                    flatten[k] = str(v)
            else:
                flatten = None

            try:
                url_params = load_json_file(os.path.join(self.project_path,
                                                         "url_params.json"),
                                            default=None)
            except (IOError, OSError, ValueError) as e:
                logging.warning("Error loading url_params.json: %s", e)
                url_params = None

            hook_result = self._run_hook("before_run", {
                "mode": mode,
                "project_path": self.project_path,
                "headers": headers,
                "params": params
            })
            if isinstance(hook_result, dict):
                headers = hook_result.get("headers", headers)
                params = hook_result.get("params", params)

            try:
                if self.query_mode == "params":
                    url = _url_replacer(self.start_url, url_params or {})
                elif self.query_mode == "mixed":
                    url = _url_replacer(self.start_url, url_params or {}, query_mode=True)
                else:
                    url = self.start_url
                hook_result = self._run_hook("before_request", {
                    "url": url,
                    "headers": headers,
                    "params": params,
                    "mode": mode,
                    "page": None
                })
                if isinstance(hook_result, dict):
                    url = hook_result.get("url", url)
                    headers = hook_result.get("headers", headers)
                    params = hook_result.get("params", params)
                response = self._single_request(url, headers, params, flatten)
                self._run_hook("after_response", {
                    "url": url,
                    "headers": headers,
                    "params": params,
                    "mode": mode,
                    "page": None,
                    "response": self._serialize_response(response)
                })
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response:
                    status_code = e.response.status_code
                    error_msg = (
                        f"Failed to connect to API: HTTP {status_code}\n"
                        f"  URL: {url}\n"
                        f"  Error: {str(e)}\n"
                        f"  Check your configuration and network connection"
                    )
                logging.error("Error making initial request to %s: %s", url, e)
                print(f"Error: {error_msg}")
                if storage_backend:
                    storage_backend.close()
                return
            except (ValueError, RuntimeError, IOError) as e:
                error_msg = (
                    f"Unexpected error during initial request\n"
                    f"  URL: {url}\n"
                    f"  Error: {str(e)}\n"
                    f"  Error type: {type(e).__name__}\n"
                    f"  Check logs for details: {self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'}"
                )
                logging.error("Unexpected error in initial request to %s: %s",
                              url, e, exc_info=True)
                print(f"Error: {error_msg}")
                if storage_backend:
                    storage_backend.close()
                return

            try:
                if self.resp_type == "json":
                    start_page_data = response.json()
                elif self.resp_type == 'xml':
                    start_page_data = xmltodict.parse(response.content)
                elif self.resp_type == 'html' and process_func is not None:
                    start_page_data = process_func(response.content)
                else:
                    error_msg = (
                        f"Unsupported response type: {self.resp_type}\n"
                        f"  Supported types: json, xml, html\n"
                        f"  For HTML responses, you must configure a postfetch script in [code] section\n"
                        f"  Update resp_type in [project] section of your config file"
                    )
                    logging.error("Unsupported response type: %s",
                                  self.resp_type)
                    print(f"Error: {error_msg}")
                    if storage_backend:
                        storage_backend.close()
                    return
            except (json.JSONDecodeError, ValueError) as e:
                error_msg = (
                    f"Failed to parse API response as {self.resp_type}\n"
                    f"  Error: {str(e)}\n"
                    f"  Response type configured: {self.resp_type}\n"
                    f"  Suggestions:\n"
                    f"    - Verify the API is returning {self.resp_type} format\n"
                    f"    - Check if response_type in [project] section matches actual API response\n"
                    f"    - Review response in logs (if verbose mode enabled)\n"
                    f"    - If using HTML response, ensure postfetch script is configured correctly"
                )
                logging.error("Error parsing response from %s: %s", url, e)
                print(f"Error: {error_msg}")
                if storage_backend:
                    storage_backend.close()
                return
            except (IOError, OSError, RuntimeError) as e:
                error_msg = (
                    f"Failed to process API response\n"
                    f"  Error: {str(e)}\n"
                    f"  Response type: {self.resp_type}\n"
                    f"  Error type: {type(e).__name__}\n"
                    f"  Check logs for more details: {self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'}"
                )
                logging.error("Error processing response from %s: %s", url, e,
                              exc_info=True)
                print(f"Error: {error_msg}")
                if storage_backend:
                    storage_backend.close()
                return

            if self.detect_enabled and self.resp_type == "json":
                suggestions = self._detect_suggestions(start_page_data)
                self._apply_detection(suggestions)

            #        print(json.dumps(start_page_data, ensure_ascii=False))
            end = timer()

            try:
                if len(self.total_number_key) > 0:
                    total = get_dict_value(start_page_data,
                                           self.total_number_key,
                                           splitter=self.field_splitter)
                    if total is None:
                        logging.warning("total_number_key not found in response")
                        total = 0
                    else:
                        total = int(total)
                    nr = 1 if total % self.page_limit > 0 else 0
                    num_pages = (total // self.page_limit) + nr
                elif len(self.pages_number_key) > 0:
                    num_pages = get_dict_value(start_page_data,
                                               self.pages_number_key,
                                               splitter=self.field_splitter)
                    if num_pages is None:
                        logging.warning("pages_number_key not found in response")
                        num_pages = DEFAULT_NUMBER_OF_PAGES
                    else:
                        num_pages = int(num_pages)
                    total = num_pages * self.page_limit
                else:
                    num_pages = None
                    total = None
                if total is not None and num_pages is not None:
                     logging.info("Total pages %d, records %d", num_pages, total)
                     num_pages = int(num_pages)
                else:
                     num_pages = DEFAULT_NUMBER_OF_PAGES
            except (ValueError, TypeError, KeyError) as e:
                logging.warning("Error extracting page count: %s, using default",
                                e)
                num_pages = DEFAULT_NUMBER_OF_PAGES
                total = None

            change_params = {}

            # By default it's "full" mode with start_page and end_page as full list of pages
            start_page = self.start_page
            end_page = num_pages + self.start_page

            # if "continue" mode is set, shift start_page to last page saved. Force
            # rewriting last page and continue
            if mode == "continue":
                logging.debug("Continue mode enabled, looking for last saved page")
                pagenames = storage_backend.list_objects("page") if storage_backend else []
                for page in range(self.start_page, num_pages):
                    if "page_%d.json" % (page) not in pagenames:
                        start_page = page
                        break
                logging.debug("Start page number %d", start_page)

            if resume_page:
                start_page = max(start_page, int(resume_page))
                logging.debug("Resume enabled, start page %d", start_page)

            if mode == "update":
                if self.update_mode == "by_change_key" and self.change_key_param and last_change_value:
                    change_params[self.change_key_param] = last_change_value
                elif self.update_mode == "by_timestamp" and self.update_since_param and last_run_end:
                    change_params[self.update_since_param] = last_run_end
                elif self.update_mode == "custom_script":
                    logging.warning("Custom update mode is configured but not implemented.")

            # Initialize progress tracking
            total_pages = end_page - start_page
            progress_bar = None
            if total_pages > 0:
                progress_bar = tqdm(total=total_pages, desc="Downloading pages", unit="page")

            consecutive_errors = 0
            def fetch_page(target_page: int) -> Dict[str, Any]:
                local_change_params = dict(change_params)
                local_params = dict(params)
                local_url_params = dict(url_params) if url_params else None
                local_flatten = dict(flatten) if flatten else None

                if self.page_size_param and len(self.page_size_param) > 0:
                    local_change_params[self.page_size_param] = self.page_limit
                if self.iterate_by == "page":
                    local_change_params[self.page_number_param] = target_page
                elif self.iterate_by == "skip":
                    local_change_params[self.count_skip_param] = (target_page - 1) * self.page_limit
                elif self.iterate_by == "range":
                    local_change_params[self.count_from_param] = (target_page - 1) * self.page_limit
                    local_change_params[self.count_to_param] = target_page * self.page_limit

                if self.query_mode in ("params", "mixed"):
                    if local_url_params is None:
                        local_url_params = {}
                    local_url_params.update(local_change_params)
                else:
                    local_params = update_dict_values(local_params, local_change_params)
                    if self.flat_params and len(local_params.keys()) > 0:
                        local_flatten = {}
                        for k, v in local_params.items():
                            local_flatten[k] = str(v)

                if self.query_mode == "params":
                    request_url = _url_replacer(self.start_url, local_url_params or {})
                elif self.query_mode == "mixed":
                    request_url = _url_replacer(self.start_url, local_url_params or {}, query_mode=True)
                else:
                    request_url = self.start_url

                try:
                    hook_result = self._run_hook("before_request", {
                        "url": request_url,
                        "headers": headers,
                        "params": local_params,
                        "mode": mode,
                        "page": target_page
                    })
                    local_headers = headers
                    if isinstance(hook_result, dict):
                        request_url = hook_result.get("url", request_url)
                        local_headers = hook_result.get("headers", headers)
                        local_params = hook_result.get("params", local_params)
                    response = self._single_request(request_url, local_headers, local_params, local_flatten)
                    self._run_hook("after_response", {
                        "url": request_url,
                        "headers": local_headers,
                        "params": local_params,
                        "mode": mode,
                        "page": target_page,
                        "response": self._serialize_response(response)
                    })
                except requests.exceptions.RequestException as e:
                    return {"page": target_page, "error": str(e), "status": None}
                except (ValueError, RuntimeError, IOError) as e:
                    return {"page": target_page, "error": str(e), "status": None}

                time.sleep(self.default_delay)

                if self._should_retry(response.status_code):
                    max_retries = max(self.retry_max_retries, 0)
                    for attempt in range(1, max_retries + 1):
                        delay = self._get_retry_delay(attempt, response)
                        time.sleep(delay)
                        try:
                            response = self._single_request(request_url, local_headers, local_params, local_flatten)
                        except requests.exceptions.RequestException:
                            continue
                        if not self._should_retry(response.status_code):
                            break

                return {
                    "page": target_page,
                    "status": response.status_code,
                    "content": response.content
                }

            _result_lock = threading.Lock()

            def handle_success(target_page: int, content: bytes) -> bool:
                nonlocal pages_processed, total_bytes, total_records, last_change_value
                if num_pages is not None:
                    logging.info("Saving page %d of %d", target_page, num_pages)
                else:
                    logging.info("Saving page %d", target_page)
                if self.resp_type == "json":
                    outdata = content
                    try:
                        page_data = json.loads(content)
                    except (ValueError, json.JSONDecodeError):
                        page_data = None
                elif self.resp_type == "xml":
                    page_data = xmltodict.parse(content)
                    outdata = json.dumps(page_data, ensure_ascii=False)
                elif self.resp_type == "html":
                    if process_func is None:
                        logging.error("HTML response type requires process function")
                        return False
                    page_data = process_func(content)
                    outdata = json.dumps(page_data, ensure_ascii=False)
                else:
                    logging.warning("Unknown response type: %s", self.resp_type)
                    return False

                if len(outdata) == 0:
                    logging.info("Empty results on page %d. Stopped", target_page)
                    return False
                if storage_backend:
                    storage_backend.save_page("page_%d.json" % (target_page), outdata)
                with _result_lock:
                    total_bytes += len(outdata)
                    pages_processed += 1
                    if page_data is not None:
                        try:
                            items = get_dict_value(page_data, self.data_key,
                                                   splitter=self.field_splitter)
                            if isinstance(items, list):
                                total_records += len(items)
                            elif items is not None:
                                total_records += 1
                            if self.change_key and isinstance(items, list):
                                for item in items:
                                    if isinstance(item, dict):
                                        value = get_dict_value(item, self.change_key,
                                                               splitter=self.field_splitter)
                                        if value is not None:
                                            if not last_change_value or value > last_change_value:
                                                last_change_value = value
                        except (TypeError, ValueError):
                            pass
                self._run_hook("after_page", {
                    "page": target_page,
                    "mode": mode,
                    "records_processed": total_records,
                    "bytes_written": len(outdata)
                })
                if progress_bar:
                    progress_bar.update(1)
                    elapsed = max(1e-6, time.time() - start)
                    with _result_lock:
                        current_pages = pages_processed
                    speed = current_pages / elapsed
                    eta_seconds = int((total_pages - current_pages) / speed) if speed else 0
                    progress_bar.set_postfix({
                        "speed_p/s": f"{speed:.2f}",
                        "eta_s": eta_seconds
                    })
                if self.checkpoint_interval_pages:
                    with _result_lock:
                        current_processed = pages_processed
                    if current_processed > 0 and current_processed % self.checkpoint_interval_pages == 0:
                        checkpoint_payload = {
                            "last_page": target_page,
                            "records_processed": total_records,
                            "storage_bytes": total_bytes,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        self._save_checkpoint(checkpoint_payload)
                if self.page_limit and len(outdata) < int(self.page_limit):
                    logging.info("Page %d size is %d, less than expected page size %s. Stopped",
                                 target_page, len(outdata), str(self.page_limit))
                    return False
                return True

            pages = list(range(start_page, end_page))
            if self.parallelism <= 1:
                for page in pages:
                    result = fetch_page(page)
                    if result.get("error") or self._should_retry(result.get("status")):
                        consecutive_errors += 1
                        if result.get("status") is not None:
                            error_counts[str(result.get("status"))] = (
                                error_counts.get(str(result.get("status")), 0) + 1
                            )
                        if consecutive_errors >= self.max_consecutive_errors:
                            if progress_bar:
                                progress_bar.close()
                            if storage_backend:
                                storage_backend.close()
                            return
                        if not self.continue_on_error:
                            if progress_bar:
                                progress_bar.close()
                            if storage_backend:
                                storage_backend.close()
                            return
                        if progress_bar:
                            progress_bar.update(1)
                        continue
                    consecutive_errors = 0
                    if not handle_success(page, result["content"]):
                        break
            else:
                for offset in range(0, len(pages), self.parallelism):
                    batch = pages[offset:offset + self.parallelism]
                    results: Dict[int, Dict[str, Any]] = {}
                    with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
                        future_map = {executor.submit(fetch_page, page): page for page in batch}
                        for future in as_completed(future_map):
                            result = future.result()
                            results[result["page"]] = result
                    for page in batch:
                        result = results.get(page)
                        if result is None:
                            continue
                        if result.get("error") or self._should_retry(result.get("status")):
                            consecutive_errors += 1
                            if result.get("status") is not None:
                                error_counts[str(result.get("status"))] = (
                                    error_counts.get(str(result.get("status")), 0) + 1
                                )
                            if consecutive_errors >= self.max_consecutive_errors:
                                if progress_bar:
                                    progress_bar.close()
                                if storage_backend:
                                    storage_backend.close()
                                return
                            if not self.continue_on_error:
                                if progress_bar:
                                    progress_bar.close()
                                if storage_backend:
                                    storage_backend.close()
                                return
                            if progress_bar:
                                progress_bar.update(1)
                            continue
                        consecutive_errors = 0
                        if not handle_success(page, result["content"]):
                            return

            run_end_time = datetime.now(timezone.utc)
            state_payload = {
                "last_run_start": run_start_time.isoformat(),
                "last_run_end": run_end_time.isoformat(),
                "last_page": (start_page + pages_processed - 1) if pages_processed > 0 else start_page,
                "last_change_key": last_change_value,
                "records_processed": total_records,
                "bytes_processed": total_bytes
            }
            self._save_state(state_payload)
            print("Run summary:")
            print(f"  Pages processed: {pages_processed}")
            if total_records:
                print(f"  Total records: {total_records}")
            print(f"  Total bytes: {total_bytes}")
            if error_counts:
                print("  Errors by status:")
                for code, count in sorted(error_counts.items()):
                    print(f"    {code}: {count}")
            else:
                print("  Errors by status: none")

            self._run_hook("after_run", {
                "mode": mode,
                "pages_processed": pages_processed,
                "records_processed": total_records,
                "bytes_processed": total_bytes,
                "errors": error_counts
            })

            if progress_bar:
                progress_bar.close()
            if storage_backend:
                try:
                    storage_backend.close()
                except (IOError, OSError) as e:
                    logging.error("Error closing storage backend: %s", e)
        except (ValueError, RuntimeError, IOError) as e:
            logging.error("Fatal error in run method: %s", e)
            print(f"Error: Fatal error occurred: {e}")
            if storage_backend:
                try:
                    storage_backend.close()
                except Exception:
                    pass
            if progress_bar:
                try:
                    progress_bar.close()
                except Exception:
                    pass

        # pass

    def update(self, resume: bool = False) -> None:
        """Run update mode with state tracking."""
        self.run("update", resume=resume)

    def _detect_suggestions(self, data: Any) -> Dict[str, Any]:
        suggestions: Dict[str, Any] = {}
        if isinstance(data, dict):
            for key in ["results", "items", "data"]:
                if isinstance(data.get(key), list):
                    suggestions["data_key"] = key
                    break
            if "data_key" not in suggestions:
                for key, value in data.items():
                    if isinstance(value, list):
                        suggestions["data_key"] = key
                        break
            for key in ["total", "count", "total_count"]:
                if key in data:
                    suggestions["total_number_key"] = key
                    break
            if "page" in data or "pages" in data:
                suggestions["iterate_by"] = "page"
            elif "offset" in data or "skip" in data:
                suggestions["iterate_by"] = "skip"
        return suggestions

    def _apply_detection(self, suggestions: Dict[str, Any]) -> None:
        if not suggestions:
            return
        if not self.config.has_option("data", "data_key") and suggestions.get("data_key"):
            self.data_key = suggestions["data_key"]
        if not self.config.has_option("data", "total_number_key") and suggestions.get("total_number_key"):
            self.total_number_key = suggestions["total_number_key"]
        if not self.config.has_option("project", "iterate_by") and suggestions.get("iterate_by"):
            self.iterate_by = suggestions["iterate_by"]

    def detect(self, write_config: bool = False) -> Dict[str, Any]:
        """Detect pagination and data keys from a sample request."""
        headers = load_json_file(os.path.join(self.project_path, "headers.json"), default={})
        params = load_json_file(os.path.join(self.project_path, "params.json"), default={})
        url_params = load_json_file(os.path.join(self.project_path, "url_params.json"), default=None)
        if self.query_mode == "params":
            url = _url_replacer(self.start_url, url_params or {})
        elif self.query_mode == "mixed":
            url = _url_replacer(self.start_url, url_params or {}, query_mode=True)
        else:
            url = self.start_url
        response = self._single_request(url, headers, params, None)
        if self.resp_type != "json":
            print("Detection only supports JSON responses.")
            return {}
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            print("Detection failed: response is not valid JSON.")
            return {}
        suggestions = self._detect_suggestions(data)
        if write_config and self.config_format == "yaml" and hasattr(self.config, "_data"):
            yaml_data = self.config._data
            yaml_data.setdefault("data", {})
            yaml_data.setdefault("project", {})
            if suggestions.get("data_key") and "data_key" not in yaml_data.get("data", {}):
                yaml_data["data"]["data_key"] = suggestions["data_key"]
            if suggestions.get("total_number_key") and "total_number_key" not in yaml_data.get("data", {}):
                yaml_data["data"]["total_number_key"] = suggestions["total_number_key"]
            if suggestions.get("iterate_by") and "iterate_by" not in yaml_data.get("project", {}):
                yaml_data["project"]["iterate_by"] = suggestions["iterate_by"]
            if YAML_AVAILABLE:
                with open(self.config_filename, "w", encoding="utf8") as fobj:
                    yaml.safe_dump(yaml_data, fobj, sort_keys=False, allow_unicode=True)
        return suggestions

    def _follow_rule(
        self,
        rule: Dict[str, Any],
        mode: str,
        params: Dict[str, Any],
        headers: Dict[str, Any],
        process_func: Optional[Any]
    ) -> None:
        follow_mode = rule.get("follow_mode") or rule.get("mode") or self.follow_mode
        follow_pattern = rule.get("follow_pattern") or self.follow_pattern
        follow_item_key = rule.get("follow_item_key") or self.follow_item_key
        follow_data_key = rule.get("follow_data_key") or self.follow_data_key
        follow_url_key = rule.get("follow_url_key") or self.follow_url_key
        follow_http_mode = rule.get("follow_http_mode") or self.follow_http_mode
        follow_param = rule.get("follow_param") or self.follow_param
        iterate_by = rule.get("iterate_by")
        rule_params = rule.get("params") or {}
        page_number_param = rule_params.get("page_number_param")
        page_size_param = rule_params.get("page_size_param")
        page_size_limit = rule_params.get("page_size_limit")
        max_pages = rule_params.get("max_pages", 1000)

        details_storage_file = self.details_storage_file
        if rule.get("name"):
            details_storage_file = os.path.join(self.storagedir, f"details_{rule['name']}.zip")

        source_zip = ZipFile(self.storage_file, mode="r", compression=ZIP_DEFLATED)

        if follow_mode == "item":
            allkeys = []
            logging.info("Extract unique key values from downloaded data")
            file_list = source_zip.namelist()
            extract_progress = None
            if len(file_list) > 0:
                extract_progress = tqdm(total=len(file_list), desc="Extracting keys", unit="file")
            for fname in file_list:
                tf = source_zip.open(fname, "r")
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data,
                                               self.data_key,
                                               splitter=self.field_splitter):
                        allkeys.append(item[follow_item_key])
                except (KeyError, TypeError):
                    logging.info("Data key: %s not found" % (self.data_key))
                if extract_progress:
                    extract_progress.update(1)
            if extract_progress:
                extract_progress.close()
            logging.info("%d allkeys to process", len(allkeys))
            if mode == "full":
                details_zip = ZipFile(details_storage_file,
                                      mode="w",
                                      compression=ZIP_DEFLATED)
                finallist = allkeys
            else:
                details_zip = ZipFile(details_storage_file,
                                      mode="a",
                                      compression=ZIP_DEFLATED)
                keys = []
                filenames = details_zip.namelist()
                for name in filenames:
                    if name.endswith(".json"):
                        base = name.rsplit(".", 1)[0]
                        base = base.rsplit("_page_", 1)[0]
                        keys.append(base)
                finallist = list(set(allkeys) - set(keys))
            logging.info("%d keys in final list", len(finallist))

            progress_bar = None
            if len(finallist) > 0:
                progress_bar = tqdm(total=len(finallist), desc="Following items", unit="item")
            for key in finallist:
                if iterate_by and page_number_param and page_size_limit:
                    page = 1
                    while page <= max_pages:
                        change_params = {}
                        if follow_param:
                            change_params[follow_param] = key
                        if page_size_param:
                            change_params[page_size_param] = page_size_limit
                        change_params[page_number_param] = page
                        request_params = update_dict_values(dict(params), change_params)
                        if follow_http_mode == "GET":
                            response = self.http.get(
                                follow_pattern,
                                params=request_params,
                                headers=headers if headers else None,
                                verify=self.verify_ssl
                            )
                        else:
                            response = self.http.post(
                                follow_pattern,
                                params=request_params,
                                headers=headers if headers else None,
                                verify=self.verify_ssl
                            )
                        if self.resp_type == 'json':
                            content = response.content
                            try:
                                data = response.json()
                            except (ValueError, json.JSONDecodeError):
                                data = None
                        elif self.resp_type == 'html':
                            data = process_func(response.content) if process_func else None
                            content = json.dumps(data, ensure_ascii=False).encode("utf8")
                        else:
                            data = None
                            content = response.content
                        details_zip.writestr(f"{key}_page_{page}.json", content)
                        items = None
                        if data is not None and follow_data_key:
                            items = get_dict_value(data, follow_data_key, splitter=self.field_splitter)
                        if not items or (isinstance(items, list) and len(items) < page_size_limit):
                            break
                        page += 1
                else:
                    change_params = {}
                    if follow_param:
                        change_params[follow_param] = key
                    request_params = update_dict_values(dict(params), change_params)
                    if follow_http_mode == "GET":
                        response = self.http.get(follow_pattern,
                                                 params=request_params,
                                                 headers=headers, verify=self.verify_ssl)
                    else:
                        response = self.http.post(follow_pattern,
                                                  params=request_params,
                                                  headers=headers, verify=self.verify_ssl)
                    logging.info("Saving object with id %s" % (key))
                    if self.resp_type == 'json':
                        details_zip.writestr('%s.json' % (key), response.content)
                    elif self.resp_type == 'html':
                        details_zip.writestr('%s.json' % (key), json.dumps(
                            process_func(response.content), ensure_ascii=False))
                time.sleep(DEFAULT_DELAY)
                if progress_bar:
                    progress_bar.update(1)
            if progress_bar:
                progress_bar.close()
            details_zip.close()
        elif follow_mode == "url":
            allkeys = {}
            logging.info("Extract urls to follow from downloaded data")
            file_list = source_zip.namelist()
            extract_progress = None
            if len(file_list) > 0:
                extract_progress = tqdm(total=len(file_list), desc="Extracting URLs", unit="file")
            for fname in file_list:
                tf = source_zip.open(fname, "r")
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data,
                                               self.data_key,
                                               splitter=self.field_splitter):
                        item_id = item[follow_item_key]
                        allkeys[item_id] = get_dict_value(
                            item,
                            follow_url_key,
                            splitter=self.field_splitter)
                except KeyError:
                    logging.info("Data key: %s not found" % (self.data_key))
                if extract_progress:
                    extract_progress.update(1)
            if extract_progress:
                extract_progress.close()
            if mode == "full":
                details_zip = ZipFile(details_storage_file, mode="w", compression=ZIP_DEFLATED)
            else:
                details_zip = ZipFile(details_storage_file, mode="a", compression=ZIP_DEFLATED)
            for key, url in allkeys.items():
                if follow_http_mode == "GET":
                    response = self.http.get(url, headers=headers, verify=self.verify_ssl)
                else:
                    response = self.http.post(url, headers=headers, verify=self.verify_ssl)
                details_zip.writestr('%s.json' % (key), response.content)
            details_zip.close()

        source_zip.close()

    def follow(self, mode: str = "full") -> None:
        """Collects data about each data using additional requests"""

        if self.config is None:
            self._raise_config_not_found()
            return
        if not self.follow_enabled:
            print("Follow mode not enabled")
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != "zip":
            print("Only zip storage supported right now")
            return

        if not os.path.exists(self.storage_file):
            print("Storage file not found")
            return


        process_func = None
        if self.code_postfetch is not None:
            script = run_path(self.code_follow)
            process_func = script['process']


        params = None
        params_file = os.path.join(self.project_path, "follow_params.json")
        if os.path.exists(params_file):
            with open(params_file, "r", encoding="utf8") as f:
                params = json.load(f)
        else:
            params = {}
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)

        headers_file = os.path.join(self.project_path, "headers.json")
        if os.path.exists(headers_file):
            with open(headers_file, "r", encoding="utf8") as f:
                headers = json.load(f)
        else:
            headers = {}

        if hasattr(self, "follow_rules") and self.follow_rules:
            for rule in self.follow_rules:
                self._follow_rule(rule, mode, params, headers, process_func)
            return

        mzip = ZipFile(self.storage_file, mode="r", compression=ZIP_DEFLATED)

        if self.follow_mode == "item":
            allkeys = []
            logging.info("Extract unique key values from downloaded data")
            file_list = mzip.namelist()
            extract_progress = None
            if len(file_list) > 0:
                extract_progress = tqdm(total=len(file_list), desc="Extracting keys", unit="file")
            for fname in file_list:
                tf = mzip.open(fname, "r")
                data = json.load(tf)
                tf.close()
                try:
                    for item in get_dict_value(data,
                                               self.data_key,
                                               splitter=self.field_splitter):
                        allkeys.append(item[self.follow_item_key])
                except (KeyError, TypeError):
                    logging.info("Data key: %s not found" % (self.data_key))
                if extract_progress:
                    extract_progress.update(1)
            if extract_progress:
                extract_progress.close()
            logging.info("%d allkeys to process", len(allkeys))
            if mode == "full":
                mzip = ZipFile(self.details_storage_file,
                               mode="w",
                               compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == "continue":
                mzip = ZipFile(self.details_storage_file,
                               mode="a",
                               compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(int(name.rsplit(".", 1)[0]))
                logging.info("%d filenames in zip file", len(keys))
                finallist = list(set(allkeys) - set(keys))
            logging.info("%d keys in final list", len(finallist))

            n = 0
            total = len(finallist)
            progress_bar = None
            if total > 0:
                progress_bar = tqdm(total=total, desc="Following items", unit="item")
            for key in finallist:
                n += 1
                change_params = {}
                change_params[self.follow_param] = key
                params = update_dict_values(params, change_params)
                if self.follow_http_mode == "GET":
                    if headers:
                        response = self.http.get(self.follow_pattern,
                                                 params=params,
                                                 headers=headers, verify=self.verify_ssl)
                    else:
                        response = self.http.get(self.follow_pattern,
                                                 params=params, verify=self.verify_ssl)
                else:
                    if headers:
                        response = self.http.post(self.follow_pattern,
                                                  params=params,
                                                  headers=headers, verify=self.verify_ssl)
                    else:
                        response = self.http.post(self.follow_pattern,
                                                  params=params, verify=self.verify_ssl)
                logging.info("Saving object with id %s. %d of %d" %
                             (key, n, total))
                if self.resp_type == 'json':
                    mzip.writestr('%s.json' % (key), response.content)
                elif self.resp_type == 'html':
                    mzip.writestr('%s.json' % (key), json.dumps(process_func(response.content), ensure_ascii=False))
                time.sleep(DEFAULT_DELAY)
                if progress_bar:
                    progress_bar.update(1)
            if progress_bar:
                progress_bar.close()
            mzip.close()
        elif self.follow_mode == "url":
            allkeys = {}
            logging.info("Extract urls to follow from downloaded data")
            file_list = mzip.namelist()
            extract_progress = None
            if len(file_list) > 0:
                extract_progress = tqdm(total=len(file_list), desc="Extracting URLs", unit="file")
            for fname in file_list:
                tf = mzip.open(fname, "r")
                data = json.load(tf)
                tf.close()
                #                logging.info(str(data))
                try:
                    for item in get_dict_value(data,
                                               self.data_key,
                                               splitter=self.field_splitter):
                        item_id = item[self.follow_item_key]  # noqa: W0622
                        allkeys[item_id] = get_dict_value(
                            item,
                            self.follow_url_key,
                            splitter=self.field_splitter)
                except KeyError:
                    logging.info("Data key: %s not found" % (self.data_key))
                if extract_progress:
                    extract_progress.update(1)
            if extract_progress:
                extract_progress.close()
            if mode == "full":
                mzip = ZipFile(self.details_storage_file,
                               mode="w",
                               compression=ZIP_DEFLATED)
                finallist = allkeys
                n = 0
            elif mode == "continue":
                mzip = ZipFile(self.details_storage_file,
                               mode="a",
                               compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(int(name.rsplit(".", 1)[0]))
                finallist = list(set(allkeys.keys()) - set(keys))
                n = len(keys)
            total = len(allkeys.keys())
            progress_bar = None
            if len(finallist) > 0:
                progress_bar = tqdm(total=len(finallist), desc="Following URLs", unit="item")
            for key in finallist:
                n += 1
                url = allkeys[key]
                if headers:
                    response = self.http.get(url,
                                             params=params,
                                             headers=headers, verify=self.verify_ssl)
                else:
                    response = self.http.get(url, params=params, verify=self.verify_ssl)
                logging.info("Saving object with id %s. %d of %d" %
                             (key, n, total))
                if self.resp_type == 'json':
                    mzip.writestr('%s.json' % (key), response.content)
                elif self.resp_type == 'html':
                    mzip.writestr('%s.json' % (key), json.dumps(process_func(response.content), ensure_ascii=False))
                time.sleep(DEFAULT_DELAY)
                if progress_bar:
                    progress_bar.update(1)
            if progress_bar:
                progress_bar.close()
            mzip.close()
        elif self.follow_mode == "drilldown":
            pass
        elif self.follow_mode == "prefix":
            allkeys = []
            logging.info("Extract unique key values from downloaded data")
            file_list = mzip.namelist()
            extract_progress = None
            if len(file_list) > 0:
                extract_progress = tqdm(total=len(file_list), desc="Extracting keys", unit="file")
            for fname in file_list:
                tf = mzip.open(fname, "r")
                data = json.load(tf)
                tf.close()
                try:
                    repeatable_data = get_dict_value(data,
                                               self.data_key,
                                               splitter=self.field_splitter) if self.data_key else data
                    if isinstance(repeatable_data, dict):
                        if extract_progress:
                            extract_progress.update(1)
                        continue
                    for item in repeatable_data:
                        allkeys.append(item[self.follow_item_key])
                except (KeyError, TypeError):
                    logging.info("Data key: %s not found" % (self.data_key))
                if extract_progress:
                    extract_progress.update(1)
            if extract_progress:
                extract_progress.close()
            if mode == "full":
                mzip = ZipFile(self.details_storage_file,
                               mode="w",
                               compression=ZIP_DEFLATED)
                finallist = allkeys
            elif mode == "continue":
                mzip = ZipFile(self.details_storage_file,
                               mode="a",
                               compression=ZIP_DEFLATED)
                keys = []
                filenames = mzip.namelist()
                for name in filenames:
                    keys.append(name.rsplit(".", 1)[0])
                finallist = list(set(allkeys) - set(keys))

            n = 0
            total = len(finallist)
            progress_bar = None
            if total > 0:
                progress_bar = tqdm(total=total, desc="Following prefix URLs", unit="item")
            for key in finallist:
                n += 1
                url = self.follow_pattern + str(key)
                #                print(url)
                response = self.http.get(url, verify=self.verify_ssl)
                logging.info("Saving object with id %s. %d of %d" %
                             (key, n, total))
                if self.resp_type == 'json':
                    mzip.writestr('%s.json' % (key), response.content)
                elif self.resp_type == 'html':
                    mzip.writestr('%s.json' % (key), json.dumps(process_func(response.content), ensure_ascii=False))
                time.sleep(DEFAULT_DELAY)
                if progress_bar:
                    progress_bar.update(1)
            if progress_bar:
                progress_bar.close()
            mzip.close()
        else:
            print("Follow section not configured. Please update config file")

    def getfiles(self, be_careful: bool = False) -> None:
        """Downloads all files associated with this API data"""
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

        headers = load_json_file(os.path.join(self.project_path,
                                              "headers.json"),
                                 default={})

        uniq_ids = set()

        allfiles_name = os.path.join(self.storagedir, "allfiles.csv")
        if not os.path.exists(allfiles_name):
            if not self.config.has_section("follow"):
                logging.info("Extract file urls from downloaded data")
                mzip = ZipFile(storage_file,
                               mode="r",
                               compression=ZIP_DEFLATED)
                file_list = mzip.namelist()
                extract_progress = None
                if len(file_list) > 0:
                    extract_progress = tqdm(total=len(file_list), desc="Extracting file URLs", unit="file")
                n = 0
                for fname in file_list:
                    n += 1
                    if n % 10 == 0:
                        logging.info("Processed %d files, uniq ids %d" %
                                     (n, len(uniq_ids)))
                    tf = mzip.open(fname, "r")
                    data = json.load(tf)
                    tf.close()
                    try:
                        if self.data_key:
                            iterate_data = get_dict_value(
                                data,
                                self.data_key,
                                splitter=self.field_splitter)
                        else:
                            iterate_data = data
                        for item in iterate_data:
                            if item:
                                for key in self.files_keys:
                                    file_data = get_dict_value(
                                        item,
                                        key,
                                        as_array=True,
                                        splitter=self.field_splitter,
                                    )
                                    if file_data:
                                        for uniq_id in file_data:
                                            if uniq_id is not None:
                                                if isinstance(uniq_id, list):
                                                    uniq_ids.update(
                                                        set(uniq_id))
                                                else:
                                                    uniq_ids.add(uniq_id)
                    except KeyError:
                        logging.info("Data key: %s not found" %
                                     (str(self.data_key)))
                    if extract_progress:
                        extract_progress.update(1)
                if extract_progress:
                    extract_progress.close()
                mzip.close()
            else:
                details_storage_file = os.path.join(self.storagedir,
                                                    "details.zip")
                mzip = ZipFile(details_storage_file,
                               mode="r",
                               compression=ZIP_DEFLATED)
                file_list = mzip.namelist()
                extract_progress = None
                if len(file_list) > 0:
                    extract_progress = tqdm(total=len(file_list), desc="Extracting file URLs", unit="file")
                n = 0
                for fname in file_list:
                    n += 1
                    if n % 1000 == 0:
                        logging.info("Processed %d records", n)
                    tf = mzip.open(fname, "r")
                    data = json.load(tf)
                    tf.close()
                    items = []
                    if self.follow_data_key:
                        for item in get_dict_value(
                                data,
                                self.follow_data_key,
                                splitter=self.field_splitter):
                            items.append(item)
                    else:
                        items = [
                            data,
                        ]
                    for item in items:
                        for key in self.files_keys:
                            urls = get_dict_value(item,
                                                  key,
                                                  as_array=True,
                                                  splitter=self.field_splitter)
                            if urls is not None:
                                for uniq_id in urls:
                                    if uniq_id is not None and len(
                                            str(uniq_id).strip()) > 0:
                                        uniq_ids.add(str(uniq_id))
                    if extract_progress:
                        extract_progress.update(1)
                if extract_progress:
                    extract_progress.close()
            mzip.close()

            logging.info("Storing all filenames")
            with open(allfiles_name, "w", encoding="utf8") as f:
                for u in uniq_ids:
                    f.write(str(u) + "\n")
        else:
            logging.info("Load all filenames")
            uniq_ids = load_file_list(allfiles_name)
        # Start download
        skipped_files_dict = {}
        files_storage_file = os.path.join(self.storagedir, "files.zip")
        files_list_storage = os.path.join(self.storagedir, "files.list")
        files_skipped = os.path.join(self.storagedir, "files_skipped.list")
        if os.path.exists(files_list_storage):
            list_file = open(files_list_storage, "a", encoding="utf8")
        else:
            list_file = open(files_list_storage, "w", encoding="utf8")
        if os.path.exists(files_skipped):
            skipped_files_dict = load_csv_data(files_skipped,
                                               key="filename",
                                               encoding="utf8")
            skipped_file = open(files_skipped, "a", encoding="utf8")
            skipped = csv.DictWriter(
                skipped_file,
                delimiter=";",
                fieldnames=["filename", "filesize", "reason"],
            )
        else:
            skipped_files_dict = {}
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
            aria2 = aria2p.API(
                aria2p.Client(host="http://localhost", port=6800, secret=""))
        else:
            aria2 = None
        if self.file_storage_type == "zip":
            fstorage = ZipFileStorage(files_storage_file,
                                      mode="a",
                                      compression=ZIP_DEFLATED)
        elif self.file_storage_type == "filesystem":
            fstorage = FilesystemStorage(os.path.join("storage", "files"))

        n = 0
        total_files = len(uniq_ids)
        download_progress = None
        if total_files > 0:
            download_progress = tqdm(total=total_files, desc="Downloading files", unit="file")
        try:
            for uniq_id in uniq_ids:
                if self.fetch_mode == "prefix":
                    url = self.root_url + str(uniq_id)
                elif self.fetch_mode == "pattern":
                    url = self.root_url.format(uniq_id)
                n += 1
                if n % 50 == 0:
                    logging.info("Downloaded %d files", n)
                if be_careful:
                    r = self.http.head(url, timeout=DEFAULT_TIMEOUT, verify=self.verify_ssl)
                    if ("content-disposition" in r.headers.keys()
                            and self.storage_mode == "filepath"):
                        filename = (r.headers["content-disposition"].rsplit(
                            "filename=", 1)[-1].strip('"'))
                    elif self.default_ext is not None:
                        filename = uniq_id + "." + self.default_ext
                    else:
                        filename = uniq_id
                    if ("content-length" in r.headers.keys() and int(
                            r.headers["content-length"]) > FILE_SIZE_DOWNLOAD_LIMIT
                            and self.file_storage_type == "zip"):
                        logging.info("File skipped with size %d and name %s" %
                                     (int(r.headers["content-length"]), url))
                        record = {
                            "filename":
                            filename,
                            "filesize":
                            str(r.headers["content-length"]),
                            "reason":
                            "File too large. More than %d bytes" %
                            (FILE_SIZE_DOWNLOAD_LIMIT),
                        }
                        skipped_files_dict[uniq_id] = record
                        skipped.writerow(record)
                        continue
                else:
                    if self.default_ext is not None:
                        filename = str(uniq_id) + "." + self.default_ext
                    else:
                        filename = str(uniq_id)
                if self.storage_mode == "filepath":
                    filename = urlparse(url).path
                logging.info("Processing %s as %s", url, filename)
                if fstorage.exists(filename):
                    logging.info("File %s already stored", filename)
                    if download_progress:
                        download_progress.update(1)
                    continue
                if not use_aria2:
                    response = self.http.get(url, headers=headers,
                                             timeout=DEFAULT_TIMEOUT,
                                             verify=self.verify_ssl)
                    fstorage.store(filename, response.content)
                    list_file.write(url + "\n")
                else:
                    aria2.add_uris(
                        uris=[
                            url,
                        ],
                        options={
                            "out": filename,
                            "dir":
                            os.path.abspath(os.path.join("storage", "files")),
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

    def estimate(self, mode: str) -> None:  # noqa: ARG002
        """Measures time, size and count of records"""
        if self.config is None:
            self._raise_config_not_found()
            return
        data = []
        params = {}
        data_size = 0

        process_func = None
        if self.code_postfetch is not None:
            script = run_path(self.code_postfetch)
            process_func = script['process']

        headers = None
        headers_file = os.path.join(self.project_path, "headers.json")
        if os.path.exists(headers_file):
            with open(headers_file, "r", encoding="utf8") as f:
                headers = json.load(f)
        else:
            headers = {}

        params_file = os.path.join(self.project_path, "params.json")
        if os.path.exists(params_file):
            with open(params_file, "r", encoding="utf8") as f:
                params = json.load(f)
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)
            params = flatten

        url_params = None
        params_file = os.path.join(self.project_path, "url_params.json")
        if os.path.exists(params_file):
            with open(params_file, "r", encoding="utf8") as f:
                url_params = json.load(f)
        if len(self.total_number_key) > 0:
            start = timer()
            if self.query_mode == "params":
                url = _url_replacer(self.start_url, url_params)
            elif self.query_mode == "mixed":
                url = _url_replacer(self.start_url,
                                    url_params,
                                    query_mode=True)
            else:
                url = self.start_url
            if self.http_mode == "GET":
                if self.flat_params and len(params.keys()) > 0:
                    s = []
                    for k, v in params.items():
                        s.append(
                            "%s=%s" %
                            (k, v.replace("'", '"').replace("True", "true")))
                    if headers:
                        start_page_data = self.http.get(
                            url + "?" + "&".join(s), headers=headers, verify=self.verify_ssl).json()
                    else:
                        start_page_data = self.http.get(url + "?" +
                                                        "&".join(s), verify=self.verify_ssl).json()
                else:
                    logging.debug("Start request params: %s headers: %s" %
                                  (str(params), str(headers)))
                    if headers and len(headers.keys()) > 0:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url,
                                                     params=params,
                                                     headers=headers,
                                                     verify=self.verify_ssl)
                        else:
                            response = self.http.get(url,
                                                     headers=headers,
                                                     verify=self.verify_ssl)
                    else:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url,
                                                     params=params,
                                                     verify=self.verify_ssl)
                        else:
                            response = self.http.get(url, verify=self.verify_ssl)

                    if self.resp_type == 'json':
                        start_page_data = response.json()
                    elif self.resp_type == 'html':
                        start_page_data = process_func(response.content)
            else:
                logging.info(url)
                if headers:
                    response = self.http.post(url,
                                              json=params,
                                              verify=self.verify_ssl,
                                              headers=headers)
                else:
                    response = self.http.post(url, json=params, verify=self.verify_ssl)

                if self.resp_type == 'json':
                    start_page_data = response.json()
                elif self.resp_type == 'html':
                    start_page_data = process_func(response.content)

            total = get_dict_value(start_page_data,
                                   self.total_number_key,
                                   splitter=self.field_splitter)
            end = timer()
        else:
            print(
                "Can't estimate without total_number_key field in config file")
            return
        request_time = end - start
        nr = 1 if total % self.page_limit > 0 else 0
        req_number = (total // self.page_limit) + nr
        if self.data_key:
            req_data = get_dict_value(start_page_data,
                                      self.data_key,
                                      splitter=self.field_splitter)
            data.extend(req_data)
        else:
            data.extend(start_page_data)
        for r in data:
            data_size += len(json.dumps(r))
        avg_size = float(data_size) / len(data) if len(data) > 0 else 0.0

        print("Total records: %d" % (total))
        print("Records per request: %d" % (self.page_limit))
        print("Total requests: %d" % (req_number))
        print("Average record size %.2f bytes" % (avg_size))
        print("Estimated size (json lines) %.2f MB" %
              ((avg_size * total) / 1000000))
        print("Avg request time, seconds %.4f " % (request_time))
        print("Estimated all requests time, seconds %.4f " %
              (request_time * req_number))

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
                "log_file": self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'
            },
            "configuration": {
                "page_limit": self.page_limit,
                "start_page": self.start_page,
                "iterate_by": self.iterate_by,
                "query_mode": self.query_mode,
                "default_delay": self.default_delay,
                "retry_count": self.retry_count,
                "retry_delay": self.retry_delay,
                "force_retry": self.force_retry
            },
            "data": {
                "data_key": self.data_key,
                "total_number_key": self.total_number_key if self.total_number_key else None,
                "pages_number_key": self.pages_number_key if self.pages_number_key else None
            },
            "params": {
                "page_number_param": self.page_number_param,
                "page_size_param": self.page_size_param,
                "count_skip_param": self.count_skip_param,
                "count_from_param": self.count_from_param,
                "count_to_param": self.count_to_param,
                "flat_params": self.flat_params
            }
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
            "proxies_configured": self.proxies is not None and len(self.proxies) > 0
        }

        # Add error handling configuration
        report["error_handling"] = {
            "retry_on_codes": self.error_retry_codes,
            "max_consecutive_errors": self.max_consecutive_errors,
            "continue_on_error": self.continue_on_error
        }

        # Add storage configuration
        report["storage_config"] = {
            "compression_level": self.compression_level,
            "max_file_size": self.max_file_size,
            "split_files": self.split_files
        }

        # Add authentication info if configured
        if self.auth_handler:
            report["authentication"] = {
                "type": self.auth_handler.auth_type
            }

        # Add rate limiting info if configured
        if self.rate_limiter:
            report["rate_limiting"] = {
                "enabled": True,
                "requests_per_second": self.rate_limiter.requests_per_second,
                "requests_per_minute": self.rate_limiter.requests_per_minute,
                "requests_per_hour": self.rate_limiter.requests_per_hour
            }
        else:
            report["rate_limiting"] = {
                "enabled": False
            }

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
                "url_key": self.follow_url_key
            }
        else:
            report["follow"] = {
                "enabled": False
            }

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
                "use_aria2": self.use_aria2 == "True"
            }
        else:
            report["files"] = {
                "enabled": False
            }

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

            # Storage statistics
            if self.storage_type == "sqlite":
                if os.path.exists(self.storage_file):
                    try:
                        storage_backend = build_storage_backend("sqlite", self.storage_file, "continue")
                        file_list = storage_backend.list_objects("page")
                        total_size = 0
                        total_records = 0
                        for fname in file_list:
                            try:
                                content = storage_backend.get_object(fname, "page")
                                if content is None:
                                    continue
                                total_size += len(content)
                                data = json.loads(content)
                                if self.data_key:
                                    items = get_dict_value(data, self.data_key, splitter=self.field_splitter)
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
                                logging.debug("Error counting records in %s: %s",
                                              fname, e)
                        stats_data["storage"] = {
                            "file_exists": True,
                            "total_files": len(file_list),
                            "total_size_bytes": total_size,
                            "total_size_mb": round(total_size / (1024 * 1024), 2),
                            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                            "total_records": total_records,
                            "avg_records_per_file": round(total_records / len(file_list), 2) if len(file_list) > 0 else 0
                        }
                        storage_backend.close()
                    except (IOError, OSError, ValueError) as e:
                        logging.error("Error reading sqlite storage: %s", e)
                        stats_data["storage"] = {
                            "file_exists": True,
                            "error": str(e)
                        }
                else:
                    stats_data["storage"] = {
                        "file_exists": False
                    }
            else:
                storage_file = os.path.join(self.storagedir, "storage.zip")
                if os.path.exists(storage_file):
                    try:
                        mzip = ZipFile(storage_file, mode="r", compression=ZIP_DEFLATED)
                        file_list = mzip.namelist()
                        total_size = sum(mzip.getinfo(f).file_size for f in file_list)

                        # Count all records accurately
                        total_records = 0
                        sample_count = 0
                        sample_records = 0

                        # Use progress bar for large files
                        if len(file_list) > 0:
                            progress_bar = None
                            if len(file_list) > 100:
                                progress_bar = tqdm(total=len(file_list), desc="Counting records", unit="file", leave=False)

                            for fname in file_list:
                                try:
                                    tf = mzip.open(fname, "r")
                                    data = json.load(tf)
                                    tf.close()

                                    if self.data_key:
                                        items = get_dict_value(data, self.data_key, splitter=self.field_splitter)
                                        if isinstance(items, list):
                                            total_records += len(items)
                                        elif items is not None:
                                            total_records += 1
                                    else:
                                        if isinstance(data, list):
                                            total_records += len(data)
                                        elif data is not None:
                                            total_records += 1

                                    # Track sample for average calculation
                                    if sample_count < 10:
                                        if self.data_key:
                                            items = get_dict_value(data, self.data_key, splitter=self.field_splitter)
                                            if isinstance(items, list):
                                                sample_records += len(items)
                                        else:
                                            if isinstance(data, list):
                                                sample_records += len(data)
                                        sample_count += 1
                                except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                                    logging.debug("Error counting records in %s: %s",
                                                 fname, e)

                                if progress_bar:
                                    progress_bar.update(1)

                            if progress_bar:
                                progress_bar.close()

                        stats_data["storage"] = {
                            "file_exists": True,
                            "total_files": len(file_list),
                            "total_size_bytes": total_size,
                            "total_size_mb": round(total_size / (1024 * 1024), 2),
                            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                            "total_records": total_records,
                            "avg_records_per_file": round(total_records / len(file_list), 2) if len(file_list) > 0 else 0
                        }

                        mzip.close()
                    except (IOError, OSError, zipfile.BadZipFile) as e:
                        logging.error("Error reading storage file: %s", e)
                        stats_data["storage"] = {
                            "file_exists": True,
                            "error": str(e)
                        }
                else:
                    stats_data["storage"] = {
                        "file_exists": False
                    }

            # Details storage statistics
            details_file = os.path.join(self.storagedir, "details.zip")
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
                        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3)
                    }

                    mzip.close()
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error("Error reading details file: %s", e)
                    stats_data["details"] = {
                        "file_exists": True,
                        "error": str(e)
                    }
            else:
                stats_data["details"] = {
                    "file_exists": False
                }

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
                        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3)
                    }

                    mzip.close()
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error("Error reading files storage: %s", e)
                    stats_data["files"] = {
                        "file_exists": True,
                        "error": str(e)
                    }
            else:
                stats_data["files"] = {
                    "file_exists": False
                }

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
                "last_change_key": state.get("last_change_key")
            }

        return report

    def validate_config(self, verbose: bool = False) -> bool:
        """Validate project configuration"""
        errors = []
        warnings = []

        if self.config is None:
            errors.append("Configuration file not found")
            return False

        if self.config_format == "ini":
            warnings.append("INI configuration is deprecated; use YAML instead")

        # For YAML configs, use schema validation first
        if self.config_format == 'yaml' and JSONSCHEMA_AVAILABLE:
            try:
                # Reload the YAML file to get raw data for schema validation
                if os.path.exists(self.config_filename):
                    with open(self.config_filename, "r", encoding="utf8") as fobj:
                        yaml_data = yaml.safe_load(fobj)

                    if yaml_data:
                        is_valid, validation_errors = validate_yaml_config(yaml_data)
                        if not is_valid:
                            for error in validation_errors:
                                path = error.get("path", "root")
                                msg = error.get("message", "Unknown error")
                                errors.append(f"Schema validation error at {path}: {msg}")
            except (IOError, OSError, ValueError) as e:
                if verbose:
                    warnings.append(f"Could not perform schema validation: {e}")

        # Check required sections
        required_sections = ["settings", "project", "params", "data", "storage"]
        for section in required_sections:
            if not self.config.has_section(section):
                errors.append(f"Missing required section: {section}")

        # Validate settings section
        if self.config.has_section("settings"):
            if not self.config.has_option("settings", "name"):
                errors.append("Missing required option: settings.name")

        # Validate project section
        if self.config.has_section("project"):
            if not self.config.has_option("project", "url"):
                errors.append("Missing required option: project.url")
            else:
                url = self.config.get("project", "url")
                if not url.startswith(("http://", "https://")):
                    errors.append(f"Invalid URL format: {url}")

            if not self.config.has_option("project", "http_mode"):
                errors.append("Missing required option: project.http_mode")
            else:
                http_mode = self.config.get("project", "http_mode")
                if http_mode not in ["GET", "POST"]:
                    errors.append(f"Invalid http_mode: {http_mode} (must be GET or POST)")

        # Validate params section
        if self.config.has_section("params"):
            if not self.config.has_option("params", "page_size_limit"):
                errors.append("Missing required option: params.page_size_limit")
            else:
                try:
                    limit = self.config.getint("params", "page_size_limit")
                    if limit <= 0:
                        errors.append("page_size_limit must be greater than 0")
                except ValueError:
                    errors.append("page_size_limit must be an integer")

        # Validate data section
        if self.config.has_section("data"):
            if not self.config.has_option("data", "data_key") and not self.config.has_option("data", "total_number_key"):
                warnings.append("Neither data_key nor total_number_key specified - may cause issues")

        # Validate storage section
        if self.config.has_section("storage"):
            if not self.config.has_option("storage", "storage_type"):
                errors.append("Missing required option: storage.storage_type")
            else:
                storage_type = self.config.get("storage", "storage_type")
                if storage_type not in ["zip", "filesystem", "sqlite"]:
                    warnings.append(f"Storage type '{storage_type}' may not be fully supported")

        # Validate authentication if configured
        if self.config.has_section("auth"):
            auth_type = self.config.get("auth", "type") if self.config.has_option("auth", "type") else None
            if not auth_type:
                errors.append("auth.type is required when auth section is present")
            elif auth_type == "basic":
                if not self.config.has_option("auth", "username"):
                    errors.append("auth.username is required for basic authentication")
                if not self.config.has_option("auth", "password") and not self.config.has_option("auth", "password_file"):
                    errors.append("auth.password or auth.password_file is required for basic authentication")
            elif auth_type == "bearer":
                if not self.config.has_option("auth", "token") and not self.config.has_option("auth", "token_file"):
                    errors.append("auth.token or auth.token_file is required for bearer authentication")
            elif auth_type == "apikey":
                if not self.config.has_option("auth", "api_key"):
                    errors.append("auth.api_key is required for apikey authentication")

        # Validate rate limiting if configured
        if self.config.has_section("rate_limit"):
            if self.config.has_option("rate_limit", "requests_per_second"):
                try:
                    rps = float(self.config.get("rate_limit", "requests_per_second"))
                    if rps <= 0:
                        errors.append("rate_limit.requests_per_second must be greater than 0")
                except ValueError:
                    errors.append("rate_limit.requests_per_second must be a number")

        # Print results
        if verbose or errors or warnings:
            if errors:
                print("Errors found:")
                for error in errors:
                    print(f"  ERROR: {error}")
            if warnings:
                print("Warnings:")
                for warning in warnings:
                    print(f"  WARNING: {warning}")

        return len(errors) == 0

    def to_package(self, filename: Optional[str] = None) -> None:  # noqa: ARG002
        if self.config is None:
            self._raise_config_not_found()
            return

        #        if not filename:
        #            filename = 'package.zip'
        #        print('Package saved as %s' % filename)
