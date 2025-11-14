#!/usr/bin/env python
# -*- coding: utf8 -*-
import json
import logging
import urllib3
import warnings
import typer
from typing import Optional, List, Tuple, Dict, Any
import sys
import os

from .cmds.project import ProjectBuilder

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
    rootLogger = logging.getLogger()
    # Only add console handler if it doesn't already exist
    if not any(isinstance(h, logging.StreamHandler) for h in rootLogger.handlers):
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        rootLogger.addHandler(consoleHandler)
    rootLogger.setLevel(logging.DEBUG)


# Create main Typer app
app = typer.Typer()


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
    url: Optional[str] = typer.Option(None, "--url", "-u", help="API URL (optional, for initialization)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Configuration file name"),
    pagekey: Optional[str] = typer.Option(None, "--pagekey", "-k", help="Page/iteration key for API"),
    pagesize: Optional[str] = typer.Option(None, "--pagesize", "-s", help="Page size for iteration"),
    datakey: Optional[str] = typer.Option(None, "--datakey", "-d", help="Data field with object items in API responses"),
    itemkey: Optional[str] = typer.Option(None, "--itemkey", "-i", help="Item unique key to identify unique items. Multiple keys separated with comma could be used too."),
    changekey: Optional[str] = typer.Option(None, "--changekey", "-e", help="Field to identify data change"),
    iterateby: str = typer.Option("page", "--iterateby", "-b", help="Way to iterate API. By 'page' or 'number'"),
    http_mode: str = typer.Option("GET", "--http-mode", "-m", help="API mode: 'GET' or 'POST'"),
    work_modes: str = typer.Option("full", "--work-modes", "-w", help="Download modes supported by this API, could be 'full', 'incremental' or 'update'. Multiple modes could be used"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
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
                logging.info(f"Project '{name}' created. URL provided but auto-initialization is not yet fully implemented.")
                logging.info("Please edit the config file manually or use the init command separately.")
            print(f"Project '{name}' created. To initialize with API settings, please edit the config file manually.")
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
        logging.error(f"Permission denied creating project '{name}': {e}")
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
        logging.error(f"OS error creating project '{name}': {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to create project '{name}'\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Try running with --verbose flag for more information\n"
            f"    - Verify you have necessary permissions"
        )
        logging.error(f"Error creating project '{name}': {e}", exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def run(
    mode: str = typer.Argument("full", help="Run mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Executes project, collects data from API"""
    try:
        if verbose:
            enable_verbose()
        acmd = ProjectBuilder(projectpath)
        acmd.run(mode)
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
        logging.error(f"File not found: {e}")
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
        logging.error(f"Permission denied: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to run project\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Run with --verbose flag for more information\n"
            f"    - Verify configuration is correct\n"
            f"    - Check network connectivity if making API requests"
        )
        logging.error(f"Error running project: {e}", exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def estimate(
    mode: str = typer.Argument("full", help="Estimate mode"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Estimate data size, records number and execution time"""
    try:
        acmd = ProjectBuilder(projectpath)
        acmd.estimate(mode)
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
        logging.error(f"File not found: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to estimate project\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify configuration is correct\n"
            f"    - Ensure total_number_key is configured in [data] section\n"
            f"    - Check network connectivity if making API requests"
        )
        logging.error(f"Error estimating project: {e}", exc_info=True)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def export(
    filename: str = typer.Argument(..., help="Output filename"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Export format (jsonl, gzip, or parquet). If not specified, will be guessed from file extension"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output. Print additional info"),
):
    """Exports data as jsonl, gzip, or parquet file"""
    try:
        if verbose:
            enable_verbose()
        
        # Auto-detect format from filename extension if not specified
        if format is None:
            filename_lower = filename.lower()
            if filename_lower.endswith('.parquet'):
                format = 'parquet'
            elif filename_lower.endswith('.gz') or filename_lower.endswith('.gzip'):
                format = 'gzip'
            elif filename_lower.endswith('.jsonl') or filename_lower.endswith('.json'):
                format = 'jsonl'
            else:
                # Default to jsonl if extension is not recognized
                format = 'jsonl'
                if verbose:
                    logging.info(f"Format not specified and could not be detected from extension, defaulting to jsonl")
        
        acmd = ProjectBuilder(projectpath)
        acmd.export(format, filename)
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
        logging.error(f"File not found: {e}")
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
        logging.error(f"Permission denied: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except ValueError as e:
        error_msg = (
            f"Invalid value or format\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Verify the export format is correct (jsonl, gzip, or parquet)\n"
            f"    - Check if filename extension matches the format\n"
            f"    - For parquet format, ensure pandas and pyarrow are installed"
        )
        logging.error(f"Invalid value: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
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
        logging.error(f"Error exporting data: {e}", exc_info=verbose)
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
        logging.error(f"File not found: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to get project information\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify configuration file is valid\n"
            f"    - Check if project directory is accessible"
        )
        logging.error(f"Error getting project info: {e}", exc_info=True)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def follow(
    mode: str = typer.Argument(..., help="Follow mode: full or continue"),
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Follow already extracted data to collect details. Use one of modes: full or continue"""
    try:
        acmd = ProjectBuilder(projectpath)
        acmd.follow(mode)
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
        logging.error(f"File not found: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except ValueError as e:
        error_msg = (
            f"Invalid follow mode: {mode}\n"
            f"  Error: {str(e)}\n"
            f"  Valid modes: 'full' or 'continue'\n"
            f"  Suggestions:\n"
            f"    - Use 'full' to process all items from scratch\n"
            f"    - Use 'continue' to resume from where you left off"
        )
        logging.error(f"Invalid follow mode: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to follow data\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify follow configuration in config file\n"
            f"    - Ensure storage file exists and is not corrupted\n"
            f"    - Check network connectivity if making API requests"
        )
        logging.error(f"Error in follow operation: {e}", exc_info=True)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def getfiles(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
):
    """Download files associated with records"""
    try:
        acmd = ProjectBuilder(projectpath)
        acmd.getfiles()
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
        logging.error(f"File not found: {e}")
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
        logging.error(f"Permission denied: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to download files\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Verify files configuration in config file\n"
            f"    - Check network connectivity\n"
            f"    - Verify file URLs are accessible"
        )
        logging.error(f"Error downloading files: {e}", exc_info=True)
        print(f"Error: {error_msg}")
        sys.exit(1)


@app.command()
def validate_config(
    projectpath: Optional[str] = typer.Option(None, "--projectpath", "-p", help="Project path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Validate project configuration"""
    try:
        acmd = ProjectBuilder(projectpath)
        result = acmd.validate_config(verbose=verbose)
        if result:
            print("Configuration is valid")
            sys.exit(0)
        else:
            print("Configuration validation failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except FileNotFoundError as e:
        error_msg = (
            f"Configuration file not found\n"
            f"  Error: {str(e)}\n"
            f"  Suggestions:\n"
            f"    - Verify the project path is correct\n"
            f"    - Check if configuration file exists (apibackuper.yaml, apibackuper.yml, or apibackuper.cfg)\n"
            f"    - Use --projectpath to specify the correct project location"
        )
        logging.error(f"File not found: {e}")
        print(f"Error: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"Failed to validate configuration\n"
            f"  Error: {str(e)}\n"
            f"  Error type: {type(e).__name__}\n"
            f"  Suggestions:\n"
            f"    - Check logs for more details: apibackuper.log\n"
            f"    - Run with --verbose flag for more information\n"
            f"    - Review configuration file for syntax errors\n"
            f"    - Use 'apibackuper validate-config' to check configuration"
        )
        logging.error(f"Error validating configuration: {e}", exc_info=verbose)
        print(f"Error: {error_msg}")
        sys.exit(1)


def cli() -> None:
    """Main CLI entry point"""
    app()


# if __name__ == '__main__':
#    cli()
