#!/usr/bin/env python
# -*- coding: utf8 -*-
"""Core CLI module for apibackuper"""
import json
import logging
import os
import sys
import warnings
import tempfile
import re
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlparse

import functools
import typer
import urllib3

from .cmds.project import ProjectBuilder
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Suppress various warnings
urllib3.disable_warnings()
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=PendingDeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

# Configure logging to file by default, without stdout/stderr output
log_file = os.path.join(os.getcwd(), "apibackuper.log")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
    handlers=[logging.FileHandler(log_file)])


def enable_verbose() -> None:
    """Enable verbose output to console in addition to file logging"""
    root_logger = logging.getLogger()
    # Only add console handler if it doesn't already exist
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)


# Create main Typer app
app = typer.Typer()


def _slugify_project_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned or "apibackuper-project"


def _build_detect_config(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    name_seed = parsed.netloc or parsed.path.strip("/").split("/")[0] or "apibackuper-project"
    project_name = _slugify_project_name(name_seed)
    return {
        "settings": {
            "name": project_name,
            "initialized": False
        },
        "project": {
            "url": url,
            "http_mode": "GET",
            "work_modes": "full",
            "resp_type": "json"
        },
        "params": {
            "page_size_limit": 100
        },
        "data": {},
        "storage": {
            "storage_type": "zip",
            "storage_path": "storage"
        }
    }


def _apply_detect_suggestions(config_data: Dict[str, Any], suggestions: Dict[str, Any]) -> None:
    if not suggestions:
        return
    data_section = config_data.setdefault("data", {})
    project_section = config_data.setdefault("project", {})
    if suggestions.get("data_key") and "data_key" not in data_section:
        data_section["data_key"] = suggestions["data_key"]
    if suggestions.get("total_number_key") and "total_number_key" not in data_section:
        data_section["total_number_key"] = suggestions["total_number_key"]
    if suggestions.get("iterate_by") and "iterate_by" not in project_section:
        project_section["iterate_by"] = suggestions["iterate_by"]


def _handle_cli_errors(func):
    """Decorator that handles common CLI exceptions with consistent error messages."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            sys.exit(1)
        except FileNotFoundError as e:
            error_msg = (
                f"Required file not found\n"
                f"  Error: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Verify the project path is correct\n"
                f"    - Check if configuration file exists\n"
                f"    - Run 'apibackuper create <name>' to create a new project\n"
                f"    - Use --projectpath to specify the correct project location"
            )
            logging.error("File not found: %s", e)
            print(f"Error: {error_msg}")
            sys.exit(1)
        except PermissionError as e:
            error_msg = (
                f"Permission denied\n"
                f"  Error: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check file and directory permissions\n"
                f"    - Verify you have read/write access to the project directory\n"
                f"    - Try running with appropriate permissions"
            )
            logging.error("Permission denied: %s", e)
            print(f"Error: {error_msg}")
            sys.exit(1)
        except (ValueError, RuntimeError, IOError) as e:
            error_msg = (
                f"Operation failed\n"
                f"  Error: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Suggestions:\n"
                f"    - Check logs for more details: apibackuper.log\n"
                f"    - Run with --verbose flag for more information\n"
                f"    - Verify configuration is correct\n"
                f"    - Check network connectivity if making API requests"
            )
            logging.error("Error: %s", e)
            print(f"Error: {error_msg}")
            sys.exit(1)
    return wrapper


def _print_project_info_text(report: Dict[str, Any]) -> None:
    """Print project information in a human-readable text format."""

    def _print_section(title: str, data: Optional[Dict[str, Any]], field_labels: List[Tuple[str, str]]) -> None:
        if not data:
            return
        typer.echo(title)
        for key, label in field_labels:
            value = data.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, bool):
                value = "yes" if value else "no"
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value) if value else "none"
            typer.echo(f"  {label}: {value}")
        typer.echo()

    project = report.get("project") or {}
    configuration = report.get("configuration") or {}
    data_config = report.get("data") or {}
    params_config = report.get("params") or {}
    request_config = report.get("request") or {}
    error_handling = report.get("error_handling") or {}
    storage_config = report.get("storage_config") or {}
    authentication = report.get("authentication") or {}
    rate_limiting = report.get("rate_limiting") or {}
    follow = report.get("follow") or {}
    files = report.get("files") or {}
    code = report.get("code") or {}
    run = report.get("run") or {}
    statistics = report.get("statistics") or {}

    _print_section(
        "Project",
        project,
        [
            ("name", "Name"),
            ("description", "Description"),
            ("url", "URL"),
            ("http_mode", "HTTP mode"),
            ("response_type", "Response type"),
            ("storage_type", "Storage type"),
            ("storage_path", "Storage path"),
            ("log_file", "Log file"),
        ],
    )

    _print_section(
        "Configuration",
        configuration,
        [
            ("page_limit", "Page limit"),
            ("start_page", "Start page"),
            ("iterate_by", "Iterate by"),
            ("query_mode", "Query mode"),
            ("default_delay", "Default delay"),
            ("retry_count", "Retry count"),
            ("retry_delay", "Retry delay"),
            ("force_retry", "Force retry"),
        ],
    )

    _print_section(
        "Data",
        data_config,
        [
            ("data_key", "Data key"),
            ("total_number_key", "Total number key"),
            ("pages_number_key", "Pages number key"),
        ],
    )

    _print_section(
        "Parameters",
        params_config,
        [
            ("page_number_param", "Page number param"),
            ("page_size_param", "Page size param"),
            ("count_skip_param", "Count skip param"),
            ("count_from_param", "Count from param"),
            ("count_to_param", "Count to param"),
            ("flat_params", "Flat params"),
        ],
    )

    _print_section(
        "Request",
        request_config,
        [
            ("timeout", "Timeout (seconds)"),
            ("connect_timeout", "Connect timeout (seconds)"),
            ("read_timeout", "Read timeout (seconds)"),
            ("verify_ssl", "Verify SSL"),
            ("user_agent", "User agent"),
            ("max_redirects", "Max redirects"),
            ("allow_redirects", "Allow redirects"),
            ("proxies_configured", "Proxies configured"),
        ],
    )

    _print_section(
        "Error Handling",
        error_handling,
        [
            ("retry_on_codes", "Retry on codes"),
            ("max_consecutive_errors", "Max consecutive errors"),
            ("continue_on_error", "Continue on error"),
        ],
    )

    _print_section(
        "Storage Configuration",
        storage_config,
        [
            ("compression_level", "Compression level"),
            ("max_file_size", "Max file size"),
            ("split_files", "Split files"),
        ],
    )

    if authentication:
        _print_section(
            "Authentication",
            authentication,
            [
                ("type", "Type"),
            ],
        )

    if rate_limiting:
        _print_section(
            "Rate limiting",
            rate_limiting,
            [
                ("enabled", "Enabled"),
                ("requests_per_second", "Requests/sec"),
                ("requests_per_minute", "Requests/min"),
                ("requests_per_hour", "Requests/hour"),
            ],
        )

    if follow and follow.get("enabled"):
        _print_section(
            "Follow",
            follow,
            [
                ("enabled", "Enabled"),
                ("mode", "Mode"),
                ("http_mode", "HTTP mode"),
                ("data_key", "Data key"),
                ("item_key", "Item key"),
                ("param", "Param"),
                ("pattern", "Pattern"),
                ("url_key", "URL key"),
            ],
        )

    if files and files.get("enabled"):
        _print_section(
            "Files",
            files,
            [
                ("enabled", "Enabled"),
                ("fetch_mode", "Fetch mode"),
                ("root_url", "Root URL"),
                ("keys", "Keys"),
                ("storage_mode", "Storage mode"),
                ("file_storage_type", "File storage type"),
                ("default_ext", "Default extension"),
                ("use_aria2", "Use aria2"),
            ],
        )

    if code:
        _print_section(
            "Code",
            code,
            [
                ("postfetch", "Postfetch script"),
                ("follow", "Follow script"),
            ],
        )

    if run:
        _print_section(
            "Last Run",
            run,
            [
                ("status", "Status"),
                ("last_run_start", "Start time"),
                ("last_run_end", "End time"),
                ("records_processed", "Records"),
                ("bytes_processed", "Bytes"),
                ("last_page", "Last page"),
                ("last_change_key", "Last change key"),
            ],
        )

    if statistics:
        storage_stats = statistics.get("storage") or {}
        if storage_stats:
            typer.echo("Statistics")
            typer.echo("  Storage")
            for key, label in [
                ("file_exists", "    File exists"),
                ("total_files", "    Total files"),
                ("total_size_bytes", "    Total size (bytes)"),
                ("total_size_mb", "    Total size (MB)"),
                ("total_size_gb", "    Total size (GB)"),
                ("total_records", "    Total records"),
                ("avg_records_per_file", "    Avg records per file"),
                ("error", "    Error"),
            ]:
                value = storage_stats.get(key)
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = "yes" if value else "no"
                typer.echo(f"{label}: {value}")
            typer.echo()

        details_stats = statistics.get("details") or {}
        if details_stats and details_stats.get("file_exists"):
            typer.echo("  Details Storage")
            for key, label in [
                ("file_exists", "    File exists"),
                ("total_files", "    Total files"),
                ("total_size_bytes", "    Total size (bytes)"),
                ("total_size_mb", "    Total size (MB)"),
                ("total_size_gb", "    Total size (GB)"),
                ("error", "    Error"),
            ]:
                value = details_stats.get(key)
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = "yes" if value else "no"
                typer.echo(f"{label}: {value}")
            typer.echo()

        files_stats = statistics.get("files") or {}
        if files_stats and files_stats.get("file_exists"):
            typer.echo("  Files Storage")
            for key, label in [
                ("file_exists", "    File exists"),
                ("total_files", "    Total files"),
                ("total_size_bytes", "    Total size (bytes)"),
                ("total_size_mb", "    Total size (MB)"),
                ("total_size_gb", "    Total size (GB)"),
                ("error", "    Error"),
            ]:
                value = files_stats.get(key)
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = "yes" if value else "no"
                typer.echo(f"{label}: {value}")
            typer.echo()


@app.command()
def create(
    name: str = typer.Argument(..., help="Project name"),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="API URL (optional, for initialization)"),
    config: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--config", "-c", help="Configuration file name"),
    pagekey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--pagekey", "-k", help="Page/iteration key for API"),
    pagesize: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--pagesize", "-s", help="Page size for iteration"),
    datakey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--datakey", "-d",
        help="Data field with object items in API responses"),
    itemkey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--itemkey", "-i",
        help=("Item unique key to identify unique items. "
              "Multiple keys separated with comma could be used too.")),
    changekey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--changekey", "-e", help="Field to identify data change"),
    iterateby: str = typer.Option(  # noqa: ARG001
        "page", "--iterateby", "-b",
        help="Way to iterate API. By 'page' or 'number'"),
    http_mode: str = typer.Option(  # noqa: ARG001
        "GET", "--http-mode", "-m", help="API mode: 'GET' or 'POST'"),
    work_modes: str = typer.Option(  # noqa: ARG001
        "full", "--work-modes", "-w",
        help=("Download modes supported by this API, could be 'full', "
              "'incremental' or 'update'. Multiple modes could be used")),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Creates a new project. Optionally initializes it with API configuration if URL is provided."""
    try:
        if verbose:
            enable_verbose()

        # Create the project directory
        ProjectBuilder.create(name)

        # If URL is provided, initialize the project
        if url:
            # Note: The init method is currently not fully implemented in ProjectBuilder
            # For now, we'll just create the project structure
            # Users can manually edit the config file or use init separately if needed
            if verbose:
                logging.info(
                    "Project '%s' created. URL provided but auto-initialization "
                    "is not yet fully implemented.", name)
                logging.info(
                    "Please edit the config file manually or use the init "
                    "command separately.")
            print(f"Project '{name}' created. To initialize with API settings, "
                  "please edit the config file manually.")
        else:
            print(f"Project '{name}' created successfully.")
            print("Edit the config file to configure API settings.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except PermissionError as e:
        error_msg = (
            f"Permission denied creating project '{name}'\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Check if you have write permissions in the current directory\n"
            f"    - Try running with appropriate permissions\n"
            f"    - Choose a different location for the project"
        )
        logging.error("Permission denied creating project '%s': %s", name, e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except OSError as e:
        error_msg = (
            f"Failed to create project '{name}'\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check if the directory already exists\n"
            f"    - Verify disk space is available\n"
            f"    - Check filesystem permissions"
        )
        logging.error("OS error creating project '%s': %s", name, e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        error_msg = (
            f"Failed to create project '{name}'\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Try running with --verbose flag for more information\n"
            f"    - Verify you have necessary permissions"
        )
        logging.error("Error creating project '%s': %s", name, e,
                      exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
@_handle_cli_errors
def run(
    mode: str = typer.Argument("full", help="Run mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    resume: bool = typer.Option(False, "--resume", help="Resume from checkpoint"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Executes project, collects data from API"""
    if verbose:
        enable_verbose()
    acmd = ProjectBuilder(projectpath)
    if acmd.config_format == "ini":
        print("Warning: INI configuration is deprecated; use YAML instead.")
    acmd.run(mode, resume=resume)


@app.command()
@_handle_cli_errors
def update(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    resume: bool = typer.Option(False, "--resume", help="Resume from checkpoint"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Executes project update mode using stored state"""
    if verbose:
        enable_verbose()
    acmd = ProjectBuilder(projectpath)
    if acmd.config_format == "ini":
        print("Warning: INI configuration is deprecated; use YAML instead.")
    acmd.update(resume=resume)


@app.command()
def detect(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="API URL to detect and generate config for"),
    write_config: bool = typer.Option(False, "--write-config", help="Write suggestions to YAML config"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Detect pagination and data keys for a project"""
    try:
        if verbose:
            enable_verbose()
        if url:
            if not YAML_AVAILABLE:
                print("Error: PyYAML is required to generate YAML config output.")
                sys.exit(1)
            config_data = _build_detect_config(url)
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_config_path = os.path.join(temp_dir, "apibackuper.yaml")
                with open(temp_config_path, "w", encoding="utf8") as fobj:
                    yaml.safe_dump(config_data, fobj, sort_keys=False, allow_unicode=True)
                acmd = ProjectBuilder(temp_dir)
                suggestions = acmd.detect(write_config=False)
            _apply_detect_suggestions(config_data, suggestions)
            if write_config:
                target_dir = projectpath or os.getcwd()
                target_path = os.path.join(target_dir, "apibackuper.yaml")
                if os.path.exists(target_path):
                    raise RuntimeError(f"Config file already exists: {target_path}")
                with open(target_path, "w", encoding="utf8") as fobj:
                    yaml.safe_dump(config_data, fobj, sort_keys=False, allow_unicode=True)
                typer.echo(f"Config written to {target_path}")
            else:
                typer.echo(yaml.safe_dump(config_data, sort_keys=False, allow_unicode=True))
        else:
            acmd = ProjectBuilder(projectpath)
            suggestions = acmd.detect(write_config=write_config)
            if suggestions:
                typer.echo(json.dumps(suggestions, indent=2, sort_keys=True))
            else:
                typer.echo("No suggestions detected")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except (ValueError, RuntimeError, IOError) as e:
        error_msg = (
            f"Failed to detect configuration\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify configuration and network connectivity"
        )
        logging.error("Error detecting configuration: %s", e, exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
@_handle_cli_errors
def estimate(
    mode: str = typer.Argument("full", help="Estimate mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Estimate data size, records number and execution time"""
    acmd = ProjectBuilder(projectpath)
    acmd.estimate(mode)


@app.command()
def export(
    filename: str = typer.Argument(..., help="Output filename"),
    format: Optional[str] = typer.Option(  # noqa: A002, W0622
        None, "--format", "-f",
        help=("Export format (jsonl, gzip, zstd, or parquet). "
              "If not specified, will be guessed from file extension")),
    fields: Optional[str] = typer.Option(
        None, "--fields", help="Comma-separated list of fields to export"),
    where: Optional[str] = typer.Option(
        None, "--where", help="Simple filter expression, e.g. \"updated_at >= 2024-01-01\""),
    projectpath: Optional[str] = typer.Option(
        None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Exports data as jsonl, gzip, zstd, or parquet file"""
    try:
        if verbose:
            enable_verbose()

        # Auto-detect format from filename extension if not specified
        if format is None:
            filename_lower = filename.lower()
            if filename_lower.endswith('.parquet'):
                format = 'parquet'
            elif filename_lower.endswith('.zst'):
                format = 'zstd'
            elif filename_lower.endswith('.gz') or filename_lower.endswith('.gzip'):
                format = 'gzip'
            elif filename_lower.endswith('.jsonl') or filename_lower.endswith('.json'):
                format = 'jsonl'
            else:
                # Default to jsonl if extension is not recognized
                format = 'jsonl'  # noqa: A001
                if verbose:
                    logging.info(
                        "Format not specified and could not be detected from "
                        "extension, defaulting to jsonl")

        acmd = ProjectBuilder(projectpath)
        fields_list = [f.strip() for f in fields.split(",")] if fields else None
        acmd.export(format, filename, fields=fields_list, where=where)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except FileNotFoundError as e:
        error_msg = (
            f"Required file not found\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Verify the project path is correct\n"
            f"    - Check if storage file exists (run 'apibackuper run' first)\n"
            f"    - Use --projectpath to specify the correct project location"
        )
        logging.error("File not found: %s", e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except PermissionError as e:
        error_msg = (
            f"Permission denied writing to file\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Check if you have write permissions for the output file/directory\n"
            f"    - Verify the directory exists and is accessible\n"
            f"    - Choose a different output location"
        )
        logging.error("Permission denied: %s", e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except ValueError as e:
        error_msg = (
            f"Invalid value or format\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Verify the export format is correct (jsonl, gzip, zstd, or parquet)\n"
            f"    - Check if filename extension matches the format\n"
            f"    - For parquet format, ensure pandas and pyarrow are installed"
        )
        logging.error("Invalid value: %s", e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except (RuntimeError, IOError) as e:
        error_msg = (
            f"Failed to export data\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Run with --verbose flag for more information\n"
            f"    - Verify storage file exists and is not corrupted\n"
            f"    - Check if you have sufficient disk space"
        )
        logging.error("Error exporting data: %s", e, exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def info(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    as_json: bool = typer.Option(False, "--json", help="Output project info in JSON format"),
):
    """Information about project like params and stats"""
    try:
        acmd = ProjectBuilder(projectpath)
        report = acmd.info(stats=True)
        if not report:
            print("No project information available")
            return

        if as_json:
            typer.echo(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_project_info_text(report)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except FileNotFoundError as e:
        error_msg = (
            f"Required file not found\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Verify the project path is correct\n"
            f"    - Check if configuration file exists\n"
            f"    - Use --projectpath to specify the correct project location"
        )
        logging.error("File not found: %s", e)
        print(f"Error: {error_msg}")
        sys.exit(1)
    except (ValueError, RuntimeError, IOError) as e:
        error_msg = (
            f"Failed to get project information\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify configuration file is valid\n"
            f"    - Check if project directory is accessible"
        )
        logging.error("Error getting project info: %s", e, exc_info=True)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
@_handle_cli_errors
def follow(
    mode: str = typer.Argument(..., help="Follow mode: full or continue"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Follow already extracted data to collect details. Use one of modes: full or continue"""
    acmd = ProjectBuilder(projectpath)
    acmd.follow(mode)


@app.command()
@_handle_cli_errors
def getfiles(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Download files associated with records"""
    acmd = ProjectBuilder(projectpath)
    acmd.getfiles()


@app.command()
@_handle_cli_errors
def validate_config(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Validate project configuration"""
    acmd = ProjectBuilder(projectpath)
    result = acmd.validate_config(verbose=verbose)
    if result:
        print("Configuration is valid")
        sys.exit(0)
    else:
        print("Configuration validation failed")
        sys.exit(1)


def cli() -> None:
    """Main CLI entry point"""
    app()


# if __name__ == '__main__':
#    cli()
