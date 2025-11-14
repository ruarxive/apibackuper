# -* coding: utf-8 -*-
import configparser
import csv
import json
import logging
import os
import time
import zipfile
import warnings
from timeit import default_timer as timer
from zipfile import ZipFile, ZIP_DEFLATED
import gzip
from urllib.parse import urlparse
import requests
from contextlib import suppress
from runpy import run_path
from typing import Optional, Dict, List, Any, Union, Tuple

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

from ..common import get_dict_value, set_dict_value, update_dict_values
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
from ..storage import FilesystemStorage, ZipFileStorage
from ..auth import AuthHandler
from ..rate_limiter import RateLimiter

from tqdm import tqdm

try:
    import pandas as pd
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

# Import from refactored modules
from .utils import load_file_list, load_csv_data, _url_replacer
from .config_loader import (
    load_json_file,
    load_schema,
    validate_yaml_config,
    YAMLConfigParser,
    JSONSCHEMA_AVAILABLE
)
from .http_client import HTTPClient


class ProjectBuilder:
    """Project builder"""

    def __init__(self, project_path: Optional[str] = None) -> None:
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
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
            except Exception as e:
                logging.error("Error reading YAML config file: %s" % str(e))
                return
        else:
            # INI format
            conf = configparser.ConfigParser()
            conf.read(filename, encoding="utf8")
            self.config = conf
        
        if self.config is not None:
            storagedir = (self.config.get(
                "storage", "storage_path") if self.config.has_option(
                    "storage", "storage_path") else "storage")
            self.storagedir = os.path.join(self.project_path, storagedir)
            self.field_splitter = (self.config.get(
                "settings", "splitter") if self.config.has_option(
                    "settings", "splitter") else FIELD_SPLITTER)
            self.id = (self.config.get("settings", "id") if self.config.has_option(
                "settings", "id") else None)
            self.name = self.config.get("settings", "name")
            self.logfile = (self.config.get("settings", "logfile") if self.config.has_option(
                "settings", "logfile") else "apibackuper.log")
            self.data_key = self.config.get("data", "data_key") if self.config.has_option('data', 'data_key') else None
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
            self.storage_file = os.path.join(self.storagedir, "storage.zip")
            self.details_storage_file = os.path.join(self.storagedir,
                                                     "details.zip")

            self.code_postfetch = self.config.get('code', 'postfetch') if self.config.has_option('code', 'postfetch') else None
            self.code_follow = self.config.get('code', 'follow') if self.config.has_option('code', 'follow') else None

            self.follow_enabled = False
            if self.config.has_section("follow"):
                self.follow_enabled = True
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
            
            # Request configuration
            self.request_timeout = DEFAULT_TIMEOUT
            self.connect_timeout = 30
            self.read_timeout = DEFAULT_TIMEOUT
            self.verify_ssl = True
            self.user_agent = "apibackuper/1.0.11"
            self.max_redirects = 5
            self.allow_redirects = True
            self.proxies = None
            
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
            if self.proxies:
                self.http.proxies.update(self.proxies)

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
                    logging.info("url: %s" % (url + "?" + "&".join(s)))
                    if headers:
                        request_kwargs["headers"] = headers
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                    else:
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                else:
                    logging.info("url: %s, params: %s" % (url, str(params)))
                    if headers:
                        request_kwargs["headers"] = headers
                    request_kwargs["params"] = params
                    response = self.http.get(url, **request_kwargs)
            else:
                logging.debug("Request %s, params %s, headers %s" %
                              (url, str(params), str(headers)))
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
                f"  Suggestions:\n"
                f"    - Increase timeout values in [request] section:\n"
                f"      connect_timeout = {self.connect_timeout * 2}\n"
                f"      read_timeout = {self.read_timeout * 2}\n"
                f"    - Check network connectivity and API server status\n"
                f"    - Verify the URL is correct and accessible"
            )
            logging.error(f"Request timeout for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.SSLError as e:
            error_msg = (
                f"SSL certificate verification failed for {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - If this is a trusted server, disable SSL verification in [request] section:\n"
                f"      verify_ssl = False\n"
                f"    - Or provide a path to a trusted certificate bundle:\n"
                f"      verify_ssl = /path/to/certificate.pem\n"
                f"    - Update your system's certificate store\n"
                f"    - Check if the server's certificate has expired"
            )
            logging.error(f"SSL error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            error_msg = (
                f"Failed to connect to {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check your internet connection\n"
                f"    - Verify the URL is correct: {url}\n"
                f"    - Check if the API server is running and accessible\n"
                f"    - If using a proxy, verify proxy settings in [request] section\n"
                f"    - Check firewall settings"
            )
            logging.error(f"Connection error for URL {url}: {e}")
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
                        f"  Suggestions:\n"
                        f"    - Check authentication credentials in [auth] section\n"
                        f"    - Verify API key or token is valid and not expired\n"
                        f"    - Check if authentication type matches API requirements"
                    )
                elif e.response.status_code == 403:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Check if your account has permission to access this resource\n"
                        f"    - Verify API key has required permissions\n"
                        f"    - Check rate limiting or quota restrictions"
                    )
                elif e.response.status_code == 404:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Verify the URL is correct: {url}\n"
                        f"    - Check if the API endpoint exists\n"
                        f"    - Review API documentation for correct endpoint path"
                    )
                elif e.response.status_code == 429:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - You are being rate limited. Wait before retrying\n"
                        f"    - Configure rate limiting in [rate_limit] section\n"
                        f"    - Increase delays between requests in [project] section:\n"
                        f"      default_delay = {self.default_delay * 2}"
                    )
                elif e.response.status_code >= 500:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - This is a server error. The API may be temporarily unavailable\n"
                        f"    - Wait a few minutes and try again\n"
                        f"    - Check API status page if available\n"
                        f"    - Increase retry settings in [project] section"
                    )
            logging.error(f"HTTP error for URL {url}: {e}")
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
            logging.error(f"Request error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = (
                f"Unexpected error while requesting {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Suggestions:\n"
                f"    - Check logs for more details: {self.logfile if hasattr(self, 'logfile') else 'apibackuper.log'}\n"
                f"    - Verify configuration is correct\n"
                f"    - Try running with --verbose flag for more information"
            )
            logging.error(f"Unexpected error in request to {url}: {e}", exc_info=True)
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
                    f = open(config_path, "w", encoding="utf8")
                    config.write(f)
                    f.close()
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
                    logging.error(f"Error writing config file {config_path}: {e}")
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
            logging.error(f"Permission denied creating project directory {name}: {e}")
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
            logging.error(f"OS error creating project {name}: {e}")
            raise RuntimeError(error_msg) from e

    def init(
        self,
        url: str,
        pagekey: str,
        pagesize: str,
        datakey: str,
        itemkey: str,
        changekey: str,
        iterateby: str,
        http_mode: str,
        work_modes: str,
    ) -> None:
        """[TBD] Unfinished method. Don't use it please"""
        self.__read_config(self.config_filename)
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
            return

    def export(self, format: str, filename: str) -> None:
        """Exports data as JSON lines, gzip, or parquet formats"""
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
            return
        
        if not filename:
            print("Error: Output filename is required")
            return
        
        try:
            # Check if parquet format is requested
            if format == "parquet":
                if not PARQUET_AVAILABLE:
                    print("Parquet format requires pandas and pyarrow. Please install them: pip install pandas pyarrow")
                    return
                # Collect all records first for parquet export
                all_records = []
            elif format == "jsonl":
                try:
                    outfile = open(filename, "w", encoding="utf8")
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
                    logging.error(f"Error opening output file {filename}: {e}")
                    print(f"Error: {error_msg}")
                    return
            elif format == "gzip":
                try:
                    outfile = gzip.open(filename, mode="wt", encoding="utf8")
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
                    logging.error(f"Error opening gzip file {filename}: {e}")
                    print(f"Error: {error_msg}")
                    return
            else:
                print("Supported formats: 'jsonl', 'gzip', 'parquet'")
                return
        except Exception as e:
            logging.error(f"Error setting up export: {e}")
            print(f"Error: Failed to set up export: {e}")
            return
        
        progress_bar = None
        try:
            details_file = os.path.join(self.storagedir, "details.zip")
            if self.config.has_section("follow") and os.path.exists(details_file):
                try:
                    mzip = ZipFile(details_file, mode="r", compression=ZIP_DEFLATED)
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    logging.error(f"Error opening details zip file: {e}")
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
                            logging.info("Loading %s" % (fname))
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
                                        if format == "parquet":
                                            all_records.append(follow_data)
                                        else:
                                            outfile.write(
                                                json.dumps(follow_data, ensure_ascii=False) +
                                                "\n")
                                    else:
                                        for item in follow_data:
                                            if format == "parquet":
                                                all_records.append(item)
                                            else:
                                                outfile.write(
                                                    json.dumps(item, ensure_ascii=False) +
                                                    "\n")
                                else:
                                    if format == "parquet":
                                        all_records.append(data)
                                    else:
                                        outfile.write(
                                            json.dumps(data, ensure_ascii=False) + "\n")
                            except KeyError:
                                logging.info("Data key: %s not found" % (self.data_key))
                        except Exception as e:
                            logging.warning(f"Error processing file {fname}: {e}")
                        finally:
                            if progress_bar:
                                progress_bar.update(1)
                finally:
                    if progress_bar:
                        progress_bar.close()
                    mzip.close()
            else:
                storage_file = os.path.join(self.storagedir, "storage.zip")
                if not os.path.exists(storage_file):
                    print("Storage file not found %s" % (storage_file))
                    if format != "parquet":
                        outfile.close()
                    return
                try:
                    mzip = ZipFile(storage_file, mode="r", compression=ZIP_DEFLATED)
                except (IOError, OSError, zipfile.BadZipFile) as e:
                    error_msg = (
                        f"Cannot read storage file: {details_file}\n"
                        f"  Error: {str(e)}\n"
                        f"  Suggestions:\n"
                        f"    - Check if the file exists and is accessible\n"
                        f"    - Verify file permissions\n"
                        f"    - The file may be corrupted - try running the backup again\n"
                        f"    - Check if the file is locked by another process"
                    )
                    logging.error(f"Error opening storage zip file {details_file}: {e}")
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
                                        if format == "parquet":
                                            all_records.append(item)
                                        else:
                                            outfile.write(
                                                json.dumps(item, ensure_ascii=False) + "\n")
                                else:
                                    for item in data:
                                        if format == "parquet":
                                            all_records.append(item)
                                        else:
                                            outfile.write(
                                                json.dumps(item, ensure_ascii=False) + "\n")
                            except KeyError:
                                logging.info("Data key: %s not found" % (self.data_key))
                        except Exception as e:
                            logging.warning(f"Error processing file {fname}: {e}")
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
                    logging.info("Data exported to %s (%d records)" % (filename, len(all_records)))
                except Exception as e:
                    logging.error("Error exporting to parquet: %s" % str(e))
                    print("Error exporting to parquet: %s" % str(e))
            else:
                try:
                    outfile.close()
                    logging.info("Data exported to %s" % (filename))
                except Exception as e:
                    logging.error(f"Error closing output file: {e}")
        except Exception as e:
            logging.error(f"Error during export: {e}")
            print(f"Error: Export failed: {e}")
            if progress_bar:
                try:
                    progress_bar.close()
                except:
                    pass
            if format != "parquet" and 'outfile' in locals():
                try:
                    outfile.close()
                except:
                    pass

    def run(self, mode: str) -> None:
        """Run data collection"""
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
            return
        
        mzip = None
        progress_bar = None
        try:
            if not os.path.exists(self.storagedir):
                try:
                    os.mkdir(self.storagedir)
                except (OSError, PermissionError) as e:
                    logging.error(f"Error creating storage directory: {e}")
                    print(f"Error: Cannot create storage directory: {e}")
                    return

            process_func = None
            if self.code_postfetch is not None:
                try:
                    script = run_path(self.code_postfetch)
                    process_func = script.get('process')
                    if process_func is None:
                        logging.warning("No 'process' function found in postfetch script")
                except Exception as e:
                    logging.error(f"Error loading postfetch script: {e}")
                    print(f"Warning: Error loading postfetch script: {e}")

            if self.storage_type != "zip":
                print("Only zip storage supported right now")
                return
            
            storage_file = os.path.join(self.storagedir, "storage.zip")
            try:
                if mode == "full":
                    mzip = ZipFile(storage_file, mode="w", compression=ZIP_DEFLATED)
                else:
                    mzip = ZipFile(storage_file, mode="a", compression=ZIP_DEFLATED)
            except (IOError, OSError, zipfile.BadZipFile, PermissionError) as e:
                logging.error(f"Error opening storage file: {e}")
                print(f"Error: Cannot open storage file: {e}")
                return

            start = timer()
            try:
                headers = load_json_file(os.path.join(self.project_path,
                                                      "headers.json"),
                                         default={})
            except Exception as e:
                logging.warning(f"Error loading headers.json: {e}")
                headers = {}

            try:
                params = load_json_file(os.path.join(self.project_path, "params.json"),
                                        default={})
            except Exception as e:
                logging.warning(f"Error loading params.json: {e}")
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
            except Exception as e:
                logging.warning(f"Error loading url_params.json: {e}")
                url_params = None
            
            try:
                if self.query_mode == "params":
                    url = _url_replacer(self.start_url, url_params or {})
                elif self.query_mode == "mixed":
                    url = _url_replacer(self.start_url, url_params or {}, query_mode=True)
                else:
                    url = self.start_url
                response = self._single_request(url, headers, params, flatten)
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
                logging.error(f"Error making initial request to {url}: {e}")
                print(f"Error: {error_msg}")
                mzip.close()
                return
            except Exception as e:
                error_msg = (
                    f"Unexpected error during initial request\n"
                    f"  URL: {url}\n"
                    f"  Error: {str(e)}\n"
                    f"  Error type: {type(e).__name__}\n"
                    f"  Check logs for details: {self.logfile}"
                )
                logging.error(f"Unexpected error in initial request to {url}: {e}", exc_info=True)
                print(f"Error: {error_msg}")
                mzip.close()
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
                    logging.error(f"Unsupported response type: {self.resp_type}")
                    print(f"Error: {error_msg}")
                    mzip.close()
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
                logging.error(f"Error parsing response from {url}: {e}")
                print(f"Error: {error_msg}")
                mzip.close()
                return
            except Exception as e:
                error_msg = (
                    f"Failed to process API response\n"
                    f"  Error: {str(e)}\n"
                    f"  Response type: {self.resp_type}\n"
                    f"  Error type: {type(e).__name__}\n"
                    f"  Check logs for more details: {self.logfile}"
                )
                logging.error(f"Error processing response from {url}: {e}", exc_info=True)
                print(f"Error: {error_msg}")
                mzip.close()
                return

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
                    num_pages = (total / self.page_limit) + nr
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
                     logging.info("Total pages %d, records %d" % (num_pages, total))
                     num_pages = int(num_pages)
                else: 
                     num_pages = DEFAULT_NUMBER_OF_PAGES
            except (ValueError, TypeError, KeyError) as e:
                logging.warning(f"Error extracting page count: {e}, using default")
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
                pagenames = mzip.namelist()
                for page in range(self.start_page, num_pages):
                    if "page_%d.json" % (page) not in pagenames:
                        if page > self.start_page:
                            start_page = page
                        else:
                            start_page = page
                        break
                logging.debug("Start page number %d" % (start_page))
            
            # Initialize progress tracking
            total_pages = end_page - start_page
            progress_bar = None
            if total_pages > 0:
                progress_bar = tqdm(total=total_pages, desc="Downloading pages", unit="page")
            
            consecutive_errors = 0
            for page in range(start_page, end_page):
                try:
                    if self.page_size_param and len(self.page_size_param) > 0:
                        change_params[self.page_size_param] = self.page_limit
                    if self.iterate_by == "page":
                        change_params[self.page_number_param] = page
                    elif self.iterate_by == "skip":
                        change_params[self.count_skip_param] = (page -
                                                                1) * self.page_limit
                    elif self.iterate_by == "range":
                        change_params[self.count_from_param] = (page -
                                                                1) * self.page_limit
                        change_params[self.count_to_param] = page * self.page_limit
                    url = (self.start_url if self.query_mode != "params" else
                           _url_replacer(self.start_url, url_params or {}))
                    if self.query_mode in ("params", "mixed"):
                        if url_params is None:
                            url_params = {}
                        url_params.update(change_params)
                    else:
                        #                print(params, change_params)
                        params = update_dict_values(params, change_params)
                        if self.flat_params and len(params.keys()) > 0:
                            for k, v in params.items():
                                flatten[k] = str(v)
                    if self.query_mode == "params":
                        url = _url_replacer(self.start_url, url_params or {})
                    elif self.query_mode == "mixed":
                        url = _url_replacer(self.start_url,
                                            url_params or {},
                                            query_mode=True)
                    else:
                        url = self.start_url
                    try:
                        response = self._single_request(url, headers, params, flatten)
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Request error on page {page}: {e}")
                        consecutive_errors += 1
                        if consecutive_errors >= self.max_consecutive_errors:
                            logging.error("Too many consecutive errors (%d). Stopping." % consecutive_errors)
                            if progress_bar:
                                progress_bar.close()
                            mzip.close()
                            return
                        if not self.continue_on_error:
                            if progress_bar:
                                progress_bar.close()
                            mzip.close()
                            return
                        if progress_bar:
                            progress_bar.update(1)
                        continue
                    except Exception as e:
                        logging.error(f"Unexpected error on page {page}: {e}")
                        consecutive_errors += 1
                        if consecutive_errors >= self.max_consecutive_errors:
                            logging.error("Too many consecutive errors (%d). Stopping." % consecutive_errors)
                            if progress_bar:
                                progress_bar.close()
                            mzip.close()
                            return
                        if not self.continue_on_error:
                            if progress_bar:
                                progress_bar.close()
                            mzip.close()
                            return
                        if progress_bar:
                            progress_bar.update(1)
                        continue
                    
                    time.sleep(self.default_delay)
                    
                    if response.status_code in self.error_retry_codes:
                        rc = 0
                        for rc in range(1, self.retry_count, 1):
                            logging.info("Retry attempt %d of %d, delay %d" %
                                         (rc, self.retry_count, self.retry_delay))
                            time.sleep(self.retry_delay)
                            try:
                                response = self._single_request(url, headers, params,
                                                                flatten)
                            except requests.exceptions.RequestException as e:
                                logging.warning(f"Retry request failed: {e}")
                                continue
                            if response.status_code not in self.error_retry_codes:
                                logging.info(
                                    "Looks like finally we have proper response on %d attempt"
                                    % (rc))
                                consecutive_errors = 0
                                break
                        if response.status_code in self.error_retry_codes:
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                logging.error("Too many consecutive errors (%d). Stopping." % consecutive_errors)
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if not self.continue_on_error:
                                logging.error("Error on page %d and continue_on_error is False. Stopping." % page)
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if progress_bar:
                                progress_bar.update(1)
                            continue
                    
                    if response.status_code not in self.error_retry_codes:
                        consecutive_errors = 0
                        try:
                            if num_pages is not None:
                                logging.info("Saving page %d of %d" % (page, num_pages))
                            else:
                                logging.info("Saving page %d" % (page))
                            if self.resp_type == "json":
                                outdata = response.content
                            elif self.resp_type == "xml":
                                outdata = json.dumps(xmltodict.parse(response.content), ensure_ascii=False)
                            elif self.resp_type == "html":
                                if process_func is None:
                                    logging.error("HTML response type requires process function")
                                    continue
                                outdata = json.dumps(process_func(response.content), ensure_ascii=False)
                            else:
                                logging.warning(f"Unknown response type: {self.resp_type}")
                                continue
                            
                            if len(outdata) == 0:
                                logging.info("Empty results on page %d. Stopped" % (page))
                                break             
                            mzip.writestr("page_%d.json" % (page), outdata)
                            if self.page_limit:                    
                                if len(outdata) < int(self.page_limit):
                                    logging.info("Page %d size is %d, less than expected page size %s. Stopped" % (page, len(outdata), str(self.page_limit)))
                                    if progress_bar:
                                        progress_bar.update(1)
                                        progress_bar.close()
                                    break
                            if progress_bar:
                                progress_bar.update(1)
                        except (json.JSONDecodeError, ValueError) as e:
                            logging.error(f"Error processing response for page {page}: {e}")
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if not self.continue_on_error:
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if progress_bar:
                                progress_bar.update(1)
                        except Exception as e:
                            logging.error(f"Error saving page {page}: {e}")
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if not self.continue_on_error:
                                if progress_bar:
                                    progress_bar.close()
                                mzip.close()
                                return
                            if progress_bar:
                                progress_bar.update(1)
                    else:
                        logging.info("Errors persist on page %d. Stopped" % (page))
                        if progress_bar:
                            progress_bar.update(1)
                        if not self.continue_on_error:
                            break
                except Exception as e:
                    logging.error(f"Unexpected error processing page {page}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= self.max_consecutive_errors:
                        logging.error("Too many consecutive errors (%d). Stopping." % consecutive_errors)
                        if progress_bar:
                            progress_bar.close()
                        mzip.close()
                        return
                    if not self.continue_on_error:
                        if progress_bar:
                            progress_bar.close()
                        mzip.close()
                        return
                    if progress_bar:
                        progress_bar.update(1)
            
            if progress_bar:
                progress_bar.close()
            if mzip:
                try:
                    mzip.close()
                except Exception as e:
                    logging.error(f"Error closing zip file: {e}")
        except Exception as e:
            logging.error(f"Fatal error in run method: {e}")
            print(f"Error: Fatal error occurred: {e}")
            if mzip:
                try:
                    mzip.close()
                except:
                    pass
            if progress_bar:
                try:
                    progress_bar.close()
                except:
                    pass

        # pass

    def follow(self, mode: str = "full") -> None:
        """Collects data about each data using additional requests"""
 
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
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
            f = open(params_file, "r", encoding="utf8")
            params = json.load(f)
            f.close()
        else:
            params = {}
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)

        headers_file = os.path.join(self.project_path, "headers.json")
        if os.path.exists(headers_file):
            f = open(headers_file, "r", encoding="utf8")
            headers = json.load(f)
            f.close()
        else:
            headers = {}

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
            logging.info("%d allkeys to process" % (len(allkeys)))
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
                logging.info("%d filenames in zip file" % (len(keys)))
                finallist = list(set(allkeys) - set(keys))
            logging.info("%d keys in final list" % (len(finallist)))

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
                                                 headers=headers, verify=False)
                    else:
                        response = self.http.get(self.follow_pattern,
                                                 params=params, verify=False)
                else:
                    if headers:
                        response = self.http.post(self.follow_pattern,
                                                  params=params,
                                                  headers=headers, verify=False)
                    else:
                        response = self.http.post(self.follow_pattern,
                                                  params=params, verify=False)
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
                        id = item[self.follow_item_key]
                        allkeys[id] = get_dict_value(
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
                                             headers=headers, verify=False)
                else:
                    response = self.http.get(url, params=params, verify=False)
                #                else:
                #                if http_mode == 'GET':
                #                    response = self.http.post(start_url, json=params)
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
                response = self.http.get(url, verify=False)
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
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
                        logging.info("Processed %d records" % (n))
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
            f = open(allfiles_name, "w", encoding="utf8")
            for u in uniq_ids:
                f.write(str(u) + "\n")
            f.close()
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
        for uniq_id in uniq_ids:
            if self.fetch_mode == "prefix":
                url = self.root_url + str(uniq_id)
            elif self.fetch_mode == "pattern":
                url = self.root_url.format(uniq_id)
            n += 1
            if n % 50 == 0:
                logging.info("Downloaded %d files" % (n))
            #            if url in processed_files:
            #                continue
            if be_careful:
                r = self.http.head(url, timeout=DEFAULT_TIMEOUT, verify=False)
                if ("content-disposition" in r.headers.keys()
                        and self.storage_mode == "filepath"):
                    filename = (r.headers["content-disposition"].rsplit(
                        "filename=", 1)[-1].strip('"'))
                elif self.default_ext is not None:
                    filename = uniq_id + "." + self.default_ext
                else:
                    filename = uniq_id
                #                if not 'content-length' in r.headers.keys():
                #                    logging.info('File %s skipped since content-length not found in headers' % (url))
                #                    record = {'filename' : filename, 'filesize' : "0", 'reason' : 'Content-length not set in headers'}
                #                    skipped_files_dict[uniq_id] = record
                #                    skipped.writerow(record)
                #                    continue
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
            logging.info("Processing %s as %s" % (url, filename))
            if fstorage.exists(filename):
                logging.info("File %s already stored" % (filename))
                if download_progress:
                    download_progress.update(1)
                continue
            if not use_aria2:
                response = self.http.get(url, headers=headers,
                                         timeout=DEFAULT_TIMEOUT,
                                         verify=False)
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

        if download_progress:
            download_progress.close()
        fstorage.close()
        list_file.close()
        skipped_file.close()

    def estimate(self, mode: str) -> None:
        """Measures time, size and count of records"""
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
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
            f = open(headers_file, "r", encoding="utf8")
            headers = json.load(f)
            f.close()
        else:
            headers = {}

        params_file = os.path.join(self.project_path, "params.json")
        if os.path.exists(params_file):
            f = open(params_file, "r", encoding="utf8")
            params = json.load(f)
            f.close()
        if self.flat_params:
            flatten = {}
            for k, v in params.items():
                flatten[k] = str(v)
            params = flatten

        url_params = None
        params_file = os.path.join(self.project_path, "url_params.json")
        if os.path.exists(params_file):
            f = open(params_file, "r", encoding="utf8")
            url_params = json.load(f)
            f.close()
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
                            url + "?" + "&".join(s), headers=headers, verify=False).json()
                    else:
                        start_page_data = self.http.get(url + "?" +
                                                        "&".join(s), verify=False).json()
                else:
                    logging.debug("Start request params: %s headers: %s" %
                                  (str(params), str(headers)))
                    if headers and len(headers.keys()) > 0:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url,
                                                     params=params,
                                                     headers=headers,
                                                     verify=False)
                        else:
                            response = self.http.get(url,
                                                     headers=headers,
                                                     verify=False)
                    else:
                        if params and len(params.keys()) > 0:
                            response = self.http.get(url,
                                                     params=params,
                                                     verify=False)
                        else:
                            response = self.http.get(url, verify=False)

                    if self.resp_type == 'json':
                        start_page_data = response.json()
                    elif self.resp_type == 'html':
                        start_page_data = process_func(response.content)
            else:
                logging.info(url)
                if headers:
                    response = self.http.post(url,
                                              json=params,
                                              verify=False,
                                              headers=headers)
                else:
                    response = self.http.post(url, json=params, verify=False)

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
        req_number = (total / self.page_limit) + nr
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location\n"
                f"    - Check if config file exists and has correct name"
            )
            print(f"Error: {error_msg}")
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
                "log_file": self.logfile
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
                                logging.debug(f"Error counting records in {fname}: {e}")
                                pass
                            
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
                except Exception as e:
                    logging.error(f"Error reading storage file: {e}")
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
                except Exception as e:
                    logging.error(f"Error reading details file: {e}")
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
                except Exception as e:
                    logging.error(f"Error reading files storage: {e}")
                    stats_data["files"] = {
                        "file_exists": True,
                        "error": str(e)
                    }
            else:
                stats_data["files"] = {
                    "file_exists": False
                }
            
            report["statistics"] = stats_data
        
        return report

    def validate_config(self, verbose: bool = False) -> bool:
        """Validate project configuration"""
        errors = []
        warnings = []
        
        if self.config is None:
            errors.append("Configuration file not found")
            return False
        
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
            except Exception as e:
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
                if storage_type not in ["zip", "filesystem"]:
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

    def to_package(self, filename: Optional[str] = None) -> None:
        if self.config is None:
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
                f"  Suggestions:\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Navigate to the project directory first\n"
                f"    - Use --projectpath option to specify project location"
            )
            print(f"Error: {error_msg}")
            return

        #        if not filename:
        #            filename = 'package.zip'
        #        print('Package saved as %s' % filename)
        pass
