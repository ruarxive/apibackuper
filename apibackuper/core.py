#!/usr/bin/env python
# -*- coding: utf8 -*-
"""Core CLI module for apibackuper"""
import contextlib
import functools
import json
import logging
import os
import sys
import tempfile
import warnings
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import typer
import urllib3
from typer.core import TyperGroup

from .cmds.fetch import CURSOR_MODES
from .cmds.project import LOG_HANDLER_MARK, ProjectBuilder, apply_detected_options
from .cmds.utils import remove_query_keys, set_progress
from .cmds.utils import slugify_name as _slugify_project_name

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# P2.26: previously this module called ``urllib3.disable_warnings`` and
# ``logging.basicConfig`` at *import* time. That hijacked the host
# application's root logger, suppressed ``InsecureRequestWarning`` even when the
# user opted in to ``verify_ssl = false``, and created ``apibackuper.log`` in
# whatever directory the host happened to be in. Both side effects now live
# inside ``_configure_logging_for_cli()`` which ``cli()`` calls (§5.5 of the
# 2026-10 analysis report).


def _configure_logging_for_cli() -> None:
    """Initialise file logging and silence noisy warnings for the CLI entry.

    Safe to call multiple times — handlers are reset on each call so importing
    ``apibackuper.core`` from a host application does *not* have side effects.
    """
    log_file = os.path.join(os.getcwd(), "apibackuper.log")
    root_logger = logging.getLogger()

    # Suppress the noisy warnings only when the CLI is actually running, not
    # when the package is imported as a library.
    try:
        urllib3.disable_warnings()
    except Exception:
        pass
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

    root_logger.handlers.clear()
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    # The project's own log file replaces this handler once a config loads.
    setattr(file_handler, LOG_HANDLER_MARK, True)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)


CONSOLE_HANDLER_MARK = "_apibackuper_console"


def enable_verbose() -> None:
    """Enable verbose output to console in addition to file logging"""
    root_logger = logging.getLogger()
    # Keep exactly one apibackuper console handler, bound to the current
    # stderr. Other stream handlers (file handlers, a host application's or
    # pytest's capture handlers) are left alone and do not count as the
    # console: they would make ``--verbose`` a silent no-op (see §4.3 of the
    # 2026-10 analysis report).
    for handler in list(root_logger.handlers):
        if getattr(handler, CONSOLE_HANDLER_MARK, False):
            root_logger.removeHandler(handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    setattr(console_handler, CONSOLE_HANDLER_MARK, True)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)


def _build_detect_config(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    name_seed = parsed.netloc or parsed.path.strip("/").split("/")[0] or "apibackuper-project"
    project_name = _slugify_project_name(name_seed)
    return {
        "settings": {"name": project_name, "initialized": False},
        "project": {"url": url, "http_mode": "GET", "work_modes": "full", "resp_type": "json"},
        "params": {"page_size_limit": 100},
        "data": {},
        "storage": {"storage_type": "zip", "storage_path": "storage"},
    }


def _apply_detect_suggestions(config_data: Dict[str, Any], suggestions: Dict[str, Any]) -> None:
    """Apply suggestions to a config generated from a URL, including the probed page size."""
    if suggestions.get("page_size_limit"):
        config_data["params"].pop("page_size_limit", None)
    apply_detected_options(config_data, suggestions)
    config_data["params"].setdefault("page_size_limit", 100)
    # Pagination values are added on each page; drop stale ones from the URL.
    names = [
        suggestions[name]
        for name in ("page_number_param", "count_skip_param", "page_size_param")
        if suggestions.get(name)
    ]
    config_data["project"]["url"] = remove_query_keys(config_data["project"]["url"], names)


# Global ``--json`` mode: human output goes to stderr and exactly one JSON
# object with the result or the error goes to the original stdout.
_JSON: Dict[str, Any] = {"enabled": False, "stdout": None, "emitted": False}


def _json_mode() -> bool:
    return bool(_JSON["enabled"])


def _emit_json(payload: Dict[str, Any]) -> None:
    """Write the single JSON object of a ``--json`` invocation."""
    stream = _JSON["stdout"] or sys.stdout
    stream.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
    stream.flush()
    _JSON["emitted"] = True


def _error_code(exc: BaseException) -> str:
    """Return a stable machine-readable code for a command failure."""
    from .cmds.config_loader import UnresolvedEnvVarError

    message = str(exc)
    if isinstance(exc, UnresolvedEnvVarError):
        return "unset_env_var"
    if isinstance(exc, KeyboardInterrupt):
        return "cancelled"
    if isinstance(exc, FileExistsError):
        return "already_exists"
    if isinstance(exc, FileNotFoundError):
        return "config_not_found" if "onfiguration file" in message else "not_found"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if "Invalid project configuration" in message:
        return "invalid_config"
    if "ignore the pagination parameter" in message:
        return "pagination_ignored"
    if "Backup is incomplete" in message:
        return "backup_incomplete"
    if isinstance(exc, ValueError):
        return "invalid_value"
    if isinstance(exc, OSError):
        return "io_error"
    return "operation_failed"


def _hints(error_msg: str) -> List[str]:
    """Return the suggestion lines of a human error message."""
    _, _, suggestions = error_msg.partition("Suggestions:")
    return [line.strip()[2:] for line in suggestions.splitlines() if line.strip().startswith("- ")]


def _fail(error_msg: str, exc: BaseException, exit_code: int = 1) -> None:
    """Report a failed command as text, or as JSON in ``--json`` mode, and exit."""
    if _json_mode():
        _emit_json(
            {
                "ok": False,
                "error": {
                    "code": _error_code(exc),
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "hints": _hints(error_msg),
                },
                "exit_code": exit_code,
            }
        )
    else:
        print(f"Error: {error_msg}")
    sys.exit(exit_code)


class _CliGroup(TyperGroup):
    """Command group whose ``--json`` option yields exactly one JSON object on stdout."""

    def invoke(self, ctx: Any) -> Any:
        if not ctx.params.get("json_output"):
            return super().invoke(ctx)
        _JSON.update(enabled=True, stdout=sys.stdout, emitted=False)

        def finish(payload: Dict[str, Any]) -> None:
            if not _JSON["emitted"]:
                _emit_json(dict(payload, command=ctx.invoked_subcommand))

        try:
            with contextlib.redirect_stdout(sys.stderr):
                result = super().invoke(ctx)
            finish({"ok": True, "result": result})
            return result
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else int(exc.code is not None)
            finish({"ok": code == 0, "exit_code": code})
            raise
        except typer.Exit as exc:
            finish({"ok": exc.exit_code == 0, "exit_code": exc.exit_code})
            raise
        except Exception as exc:
            # Click usage errors (bundled with Typer or not) carry these attributes.
            if hasattr(exc, "format_message") and hasattr(exc, "exit_code"):
                error = {"code": "usage_error", "message": exc.format_message()}
                finish({"ok": False, "error": error, "exit_code": exc.exit_code})
            else:
                error = {"code": _error_code(exc), "type": type(exc).__name__, "message": str(exc)}
                finish({"ok": False, "error": error, "exit_code": 1})
            raise
        finally:
            _JSON.update(enabled=False, stdout=None)


# Create main Typer app
app = typer.Typer(cls=_CliGroup)


@app.callback()
def main(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Write one JSON object with the result or error to stdout; other output goes to stderr.",
    ),
    no_progress: bool = typer.Option(False, "--no-progress", help="Do not draw progress bars."),
) -> None:
    """Archive paginated APIs into local storage and export their records."""
    set_progress(not (no_progress or json_output))


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
            _fail(error_msg, e)
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
            _fail(error_msg, e)
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
            _fail(error_msg, e)
        except KeyError as e:
            # UnresolvedEnvVarError is a KeyError subclass — give it a
            # dedicated, user-actionable message ("you forgot to export X")
            # rather than the generic ValueError/IOError fallback above.
            from .cmds.config_loader import UnresolvedEnvVarError

            if isinstance(e, UnresolvedEnvVarError):
                error_msg = (
                    f"configuration references unset environment variable\n"
                    f"  Variable: {e.name}\n"
                    f"  Source: {e.source or '<unknown>'}\n"
                    f"  Suggestions:\n"
                    f"    - Export the variable: export {e.name}=...\n"
                    f"    - Or set it in your shell profile / .env file\n"
                    rf"    - Or use ${{{e.name}:-default}} to provide an inline default"
                )
                _fail(error_msg, e, exit_code=2)
            raise

    return wrapper


def _emit_dry_run_plan(
    acmd: "ProjectBuilder",
    *,
    command: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Print a JSON dry-run plan and return it. Shared by ``--profile`` /
    ``--dry-run`` on the run / update / follow commands.

    The helper is kwargs-only and side-effectful (prints + exits).
    It composes:

    * the command-specific ``extra`` block (callers pass resume flag,
      follow_mode, etc.)
    * the shared ``iteration`` / ``config`` fields pulled from
      ``acmd`` via ``getattr`` (so a missing attribute surfaces as
      ``None`` rather than crashing)
    * the ``estimate`` sub-dict from ``cmds.profile.compute_profile_estimate``
    * the resulting dict is dumped as JSON

    A blank line separates ``extra`` from the shared fields for
    human readability.
    """
    from .cmds.profile import compute_profile_estimate

    report = acmd.validation_report()
    warnings_found: List[str] = []
    if isinstance(report, dict):
        if not report["valid"]:
            raise ValueError("Invalid project configuration; run validate-config for details")
        warnings_found = [issue["message"] for issue in report["warnings"]]

    plan: Dict[str, Any] = {
        "command": command,
        "project": {
            "name": getattr(acmd, "name", None),
            "url": getattr(acmd, "start_url", None),
            "http_mode": getattr(acmd, "http_mode", None),
            "response_type": getattr(acmd, "resp_type", None),
            "storage_type": getattr(acmd, "storage_type", None),
            "storage_path": getattr(acmd, "storagedir", None),
        },
        "iteration": {
            "iterate_by": getattr(acmd, "iterate_by", None),
            "page_size_limit": getattr(acmd, "page_limit", None),
            "start_page": getattr(acmd, "start_page", None),
            "parallelism": getattr(acmd, "parallelism", None),
        },
        "rate_limit": {
            "requests_per_second": getattr(acmd, "rps", None),
            "burst_size": getattr(acmd, "burst", None),
            "default_delay": getattr(acmd, "default_delay", None),
        },
        "auth": {
            "type": getattr(acmd, "auth_handler", None) and acmd.auth_handler.auth_type or "none",
        },
        "config_format": acmd.config_format,
        "config_filename": os.path.basename(acmd.config_filename),
        "warnings": warnings_found,
    }
    if getattr(acmd, "iterate_by", None) in CURSOR_MODES:
        plan["iteration"].update(
            next_cursor_key=getattr(acmd, "next_cursor_key", None),
            next_url_key=getattr(acmd, "next_url_key", None),
            cursor_param=getattr(acmd, "cursor_param", None),
        )
    if extra:
        plan.update(extra)

    state_payload = acmd._load_state() if hasattr(acmd, "_load_state") else {}
    plan["estimate"] = compute_profile_estimate(
        page_limit=getattr(acmd, "page_limit", None),
        iterate_by=getattr(acmd, "iterate_by", None),
        total_number_key=getattr(acmd, "total_number_key", "") or None,
        rps=getattr(acmd, "rps", None),
        default_delay=getattr(acmd, "default_delay", None),
        state=state_payload,
    )
    if not _json_mode():
        print(json.dumps(plan, indent=2, default=str))
    return plan


def _print_project_info_text(report: Dict[str, Any]) -> None:
    """Print project information in a human-readable text format."""

    def _print_section(
        title: str, data: Optional[Dict[str, Any]], field_labels: List[Tuple[str, str]]
    ) -> None:
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

    verification = report.get("verification") or {}
    if verification:
        _print_section(
            "Last Verification",
            dict(verification, result="passed" if verification.get("ok") else "failed"),
            [("checked_at", "Checked at"), ("result", "Result"), ("strict", "Strict")],
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
        None, "--url", "-u", help="API URL (optional, for initialization)"
    ),
    config: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--config", "-c", help="Configuration file name"
    ),
    pagekey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--pagekey", "-k", help="Page/iteration key for API"
    ),
    pagesize: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--pagesize", "-s", help="Page size for iteration"
    ),
    datakey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--datakey", "-d", help="Data field with object items in API responses"
    ),
    itemkey: Optional[str] = typer.Option(  # noqa: ARG001
        None,
        "--itemkey",
        "-i",
        help=(
            "Item unique key to identify unique items. "
            "Multiple keys separated with comma could be used too."
        ),
    ),
    changekey: Optional[str] = typer.Option(  # noqa: ARG001
        None, "--changekey", "-e", help="Field to identify data change"
    ),
    iterateby: str = typer.Option(  # noqa: ARG001
        "page", "--iterateby", "-b", help="Way to iterate API. By 'page' or 'number'"
    ),
    http_mode: str = typer.Option(  # noqa: ARG001
        "GET", "--http-mode", "-m", help="API mode: 'GET' or 'POST'"
    ),
    work_modes: str = typer.Option(  # noqa: ARG001
        "full",
        "--work-modes",
        "-w",
        help=(
            "Download modes supported by this API, could be 'full', "
            "'incremental' or 'update'. Multiple modes could be used"
        ),
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"
    ),
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
                    "is not yet fully implemented.",
                    name,
                )
                logging.info(
                    "Please edit the config file manually or use the init " "command separately."
                )
            print(
                f"Project '{name}' created. To initialize with API settings, "
                "please edit the config file manually."
            )
        else:
            print(f"Project '{name}' created successfully.")
            print("Edit the config file to configure API settings.")
        return {"project_path": os.path.abspath(name)}

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
        _fail(error_msg, e)
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
        _fail(error_msg, e)
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
        logging.error("Error creating project '%s': %s", name, e, exc_info=verbose)
        _fail(error_msg, e)


@app.command()
@_handle_cli_errors
def run(
    mode: str = typer.Argument("full", help="Run mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    resume: bool = typer.Option(False, "--resume", help="Resume from checkpoint"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"
    ),
    profile: bool = typer.Option(
        False,
        "--profile",
        help="Print a pre-flight summary of the resolved config + estimated record count, then exit without making any requests.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Alias for --profile. Exits without making any HTTP requests.",
    ),
    max_pages: Optional[int] = typer.Option(
        None,
        "--max-pages",
        min=1,
        help=(
            "Sample run: fetch at most this many pages into a temporary archive, print "
            "the first records and leave the project's archive and state unchanged."
        ),
    ),
):
    """Executes project, collects data from API.

    With ``--profile`` (or its alias ``--dry-run``), prints a JSON
    profile of the resolved configuration (URL, headers, auth,
    iteration strategy, expected record count, ETA) to stdout and
    exits without making any requests.
    """
    acmd = ProjectBuilder(projectpath)
    if verbose:
        enable_verbose()
    if acmd.config is not None and acmd.config_format == "ini":
        print("Warning: INI configuration is deprecated; use YAML instead.")
    # ``--dry-run`` is an alias for ``--profile`` — the implementation
    # is identical (no HTTP requests + print the plan).
    if dry_run and not profile:
        profile = True
    if profile:
        return _emit_dry_run_plan(
            acmd,
            command="run",
            extra={"resume": resume, "mode": mode},
        )
    if max_pages is not None:
        if mode != "full" or resume:
            raise ValueError("--max-pages works only with 'run full' without --resume")
        sample = acmd.sample(max_pages)
        if not _json_mode():
            print(json.dumps(sample, indent=2, ensure_ascii=False, default=str))
        return sample
    acmd.run(mode, resume=resume)
    return {"mode": mode, "state": acmd._load_state()}


@app.command()
@_handle_cli_errors
def update(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    resume: bool = typer.Option(False, "--resume", help="Resume from checkpoint"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the resolved config + estimated record count, then exit without making any requests.",
    ),
):
    """Executes project update mode using stored state"""
    acmd = ProjectBuilder(projectpath)
    if verbose:
        enable_verbose()
    if acmd.config is not None and acmd.config_format == "ini":
        print("Warning: INI configuration is deprecated; use YAML instead.")
    if dry_run:
        return _emit_dry_run_plan(
            acmd,
            command="update",
            extra={"resume": resume},
        )
    acmd.update(resume=resume)
    return {"state": acmd._load_state()}


@app.command()
def detect(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="API URL to detect and generate config for"
    ),
    write_config: bool = typer.Option(
        False, "--write-config", help="Write suggestions to YAML config"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"
    ),
):
    """Detect pagination and data keys for a project"""
    try:
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
                if verbose:
                    enable_verbose()
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
            elif not _json_mode():
                typer.echo(yaml.safe_dump(config_data, sort_keys=False, allow_unicode=True))
            return {"config": config_data, "suggestions": suggestions}
        else:
            acmd = ProjectBuilder(projectpath)
            if verbose:
                enable_verbose()
            suggestions = acmd.detect(write_config=write_config)
            if _json_mode():
                return suggestions
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
        _fail(error_msg, e)


@app.command()
@_handle_cli_errors
def estimate(
    mode: str = typer.Argument("full", help="Estimate mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Estimate data size, records number and execution time"""
    acmd = ProjectBuilder(projectpath)
    return acmd.estimate(mode)


@app.command()
def export(
    filename: str = typer.Argument(..., help="Output filename"),
    format: Optional[str] = typer.Option(  # noqa: A002, W0622
        None,
        "--format",
        "-f",
        help=(
            "Export format (jsonl, gzip, zstd, parquet, or warc). "
            "If not specified, will be guessed from file extension"
        ),
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields", help="Comma-separated list of fields to export"
    ),
    where: Optional[str] = typer.Option(
        None, "--where", help='Simple filter expression, e.g. "updated_at >= 2024-01-01"'
    ),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output. Print additional info"
    ),
):
    """Exports data as jsonl, gzip, zstd, parquet, or WARC file"""
    try:
        acmd = ProjectBuilder(projectpath)
        if verbose:
            enable_verbose()

        # Auto-detect format from filename extension if not specified
        if format is None:
            filename_lower = filename.lower()
            if filename_lower.endswith((".warc", ".warc.gz")):
                format = "warc"
            elif filename_lower.endswith(".parquet"):
                format = "parquet"
            elif filename_lower.endswith(".zst"):
                format = "zstd"
            elif filename_lower.endswith(".gz") or filename_lower.endswith(".gzip"):
                format = "gzip"
            elif filename_lower.endswith(".jsonl") or filename_lower.endswith(".json"):
                format = "jsonl"
            else:
                # Default to jsonl if extension is not recognized
                format = "jsonl"  # noqa: A001
                if verbose:
                    logging.info(
                        "Format not specified and could not be detected from "
                        "extension, defaulting to jsonl"
                    )

        fields_list = [f.strip() for f in fields.split(",")] if fields else None
        acmd.export(format, filename, fields=fields_list, where=where)
        return {"output": os.path.abspath(filename), "format": format}
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
        _fail(error_msg, e)
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
        _fail(error_msg, e)
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
        _fail(error_msg, e)
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
        _fail(error_msg, e)


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

        if _json_mode():
            return report
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
        _fail(error_msg, e)
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
        _fail(error_msg, e)


@app.command()
@_handle_cli_errors
def follow(
    mode: str = typer.Argument(..., help="Follow mode: full or continue"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the resolved config + estimated record count, then exit without making any requests.",
    ),
):
    """Follow already extracted data to collect details. Use one of modes: full or continue"""
    acmd = ProjectBuilder(projectpath)
    if dry_run:
        return _emit_dry_run_plan(
            acmd,
            command="follow",
            extra={
                "follow_mode": getattr(acmd, "follow_mode", None),
                "follow_pattern": getattr(acmd, "follow_pattern", None),
                "follow_mode_arg": mode,
            },
        )
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
def verify(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    strict: bool = typer.Option(
        False, "--strict", help="Also fail on unlisted pages and generations without a manifest"
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON"),
):
    """Check archive members against their fixity manifests"""
    acmd = ProjectBuilder(projectpath)
    report = acmd.verify(strict=strict)
    if _json_mode():
        _emit_json({"ok": report["ok"], "command": "verify", "result": report})
    elif as_json:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for entry in report["generations"]:
            name = entry["generation"]
            if not entry["manifest"]:
                typer.echo(f"{name}: no manifest ({len(entry['unlisted'])} pages unverified)")
                continue
            typer.echo(f"{name}: {entry['verified']} verified")
            for problem in ("changed", "missing", "unlisted"):
                for member in entry[problem]:
                    typer.echo(f"  {problem}: {member}")
        if not report["generations"]:
            typer.echo("No pages to verify")
        typer.echo("Verification passed" if report["ok"] else "Verification failed")
    if not report["ok"]:
        sys.exit(1)


@app.command()
@_handle_cli_errors
def validate_config(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as errors (exit 1 if any warnings, not just errors).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print errors and warnings as JSON, each with its configuration path and hint.",
    ),
):
    """Validate project configuration against the JSON schema and project-specific rules.

    Exit codes:
        0 - configuration is valid (and has no warnings, when --strict is set)
        1 - configuration has errors (or warnings when --strict is set)
        2 - configuration could not be loaded (missing config file)
    """
    acmd = ProjectBuilder(projectpath)
    if as_json or _json_mode():
        report = acmd.validation_report(verbose=verbose)
        failed = not report["valid"] or bool(strict and report["warnings"])
        if _json_mode():
            _emit_json({"ok": not failed, "command": "validate-config", "result": report})
        else:
            typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1 if failed else 0)
    result, error_count, warning_count = acmd.validate_config(verbose=verbose)
    if error_count > 0:
        print("Configuration validation failed")
        sys.exit(1)
    if strict and warning_count > 0:
        print("Configuration has warnings (--strict)")
        sys.exit(1)
    if result:
        print("Configuration is valid")
        sys.exit(0)
    print("Configuration has warnings (use --strict to fail)")
    sys.exit(0)


@app.command()
@_handle_cli_errors
def init(
    path: str = typer.Argument(..., help="Project directory to create"),
    url: str = typer.Option(..., "--url", "-u", help="List or search endpoint of the API"),
    method: str = typer.Option("GET", "--method", "-m", help="HTTP method: GET or POST"),
    header: Optional[List[str]] = typer.Option(
        None, "--header", "-H", help="Request header as 'Name: value'; repeatable"
    ),
    body: Optional[str] = typer.Option(
        None, "--body", help="JSON object sent as the POST body (saved to params.json)"
    ),
    auth: Optional[str] = typer.Option(
        None, "--auth", help="Authentication: bearer, apikey or basic"
    ),
    auth_env: Optional[str] = typer.Option(
        None,
        "--auth-env",
        help="Environment variable with the secret (default API_TOKEN, API_KEY or API_PASSWORD)",
    ),
    api_key_header: Optional[str] = typer.Option(
        None, "--api-key-header", help="Header carrying the API key (default X-API-Key)"
    ),
    username: Optional[str] = typer.Option(None, "--username", help="User name for --auth basic"),
    data_key: Optional[str] = typer.Option(
        None, "--data-key", help="Path to the record list, if detection picks the wrong one"
    ),
    probe: bool = typer.Option(
        True, "--probe/--no-probe", help="Send requests to detect records and pagination"
    ),
    force: bool = typer.Option(False, "--force", help="Replace an existing configuration"),
):
    """Create a project from an endpoint: probe it and write apibackuper.yaml.

    Prints a JSON report with the detected settings, record fields, a sample
    record, warnings and the next commands to run. Secrets are written as
    ${VAR} placeholders.
    """
    from .cmds.initialize import init_project, parse_headers

    payload = None
    if body:
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise ValueError(f"--body is not valid JSON: {exc}") from None
        if not isinstance(payload, dict):
            raise ValueError("--body must be a JSON object")
    report = init_project(
        path,
        url,
        method=method,
        headers=parse_headers(header),
        body=payload,
        auth=auth,
        auth_env=auth_env,
        api_key_header=api_key_header,
        username=username,
        data_key=data_key,
        probe=probe,
        force=force,
    )
    if not _json_mode():
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return report


@app.command()
def schema():
    """Print the configuration JSON Schema used by validate-config."""
    from .cmds.config_loader import load_schema

    document = load_schema()
    if document is None:
        raise RuntimeError("The bundled configuration schema is missing")
    if not _json_mode():
        typer.echo(json.dumps(document, indent=2, ensure_ascii=False))
    return document


def cli() -> None:
    """Main CLI entry point"""
    # P2.26: configure logging on entry, not at import time (§5.5).
    _configure_logging_for_cli()
    app()
