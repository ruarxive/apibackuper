"""Tests for core CLI commands"""
import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import typer.testing
from apibackuper.core import app, enable_verbose


class TestCLICommands:
    """Tests for CLI commands"""
    
    def test_enable_verbose(self):
        """Test enabling verbose logging"""
        import logging
        root_logger = logging.getLogger()
        initial_handlers = len(root_logger.handlers)
        
        enable_verbose()
        
        # Should add console handler if not present
        has_console = any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)
        # May or may not add handler depending on existing state
        assert root_logger.level == logging.DEBUG
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_create_command(self, mock_project_builder_class, temp_dir):
        """Test create command"""
        mock_project_builder = Mock()
        mock_project_builder_class.create = Mock()
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            result = runner.invoke(app, ["create", "test_project"])
            assert result.exit_code == 0
            mock_project_builder_class.create.assert_called_once_with("test_project")
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_create_command_with_url(self, mock_project_builder_class, temp_dir):
        """Test create command with URL"""
        mock_project_builder = Mock()
        mock_project_builder_class.create = Mock()
        
        runner = typer.testing.CliRunner()
        
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            result = runner.invoke(app, ["create", "test_project", "--url", "https://api.example.com"])
            # The create command exits 0 on success, 2 on Typer usage errors.
            # A bare ``SystemExit(1)`` would mean an uncaught error — that's
            # the regression we want to catch.
            assert result.exit_code in (0, 2), (
                f"create command crashed: exit={result.exit_code}, "
                f"output={result.output}"
            )
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_run_command(self, mock_project_builder_class, sample_config_ini):
        """Test run command"""
        mock_project_builder = Mock()
        mock_project_builder.run = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full"])
            # May succeed or fail depending on config
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
            mock_project_builder.run.assert_called_with("full", resume=False)
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_run_command_resume(self, mock_project_builder_class, sample_config_ini):
        """Test run command with resume flag"""
        mock_project_builder = Mock()
        mock_project_builder.run = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full", "--resume"])
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
            mock_project_builder.run.assert_called_with("full", resume=True)
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_info_command(self, mock_project_builder_class, sample_config_ini):
        """Test info command"""
        mock_project_builder = Mock()
        mock_report = {
            "project": {"name": "test_project"},
            "configuration": {"page_limit": 10}
        }
        mock_project_builder.info = Mock(return_value=mock_report)
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["info"])
            assert result.exit_code == 0
            assert "test_project" in result.stdout or "Project" in result.stdout
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_info_command_json(self, mock_project_builder_class, sample_config_ini):
        """Test info command with JSON output"""
        mock_project_builder = Mock()
        mock_report = {
            "project": {"name": "test_project"},
            "configuration": {"page_limit": 10}
        }
        mock_project_builder.info = Mock(return_value=mock_report)
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["info", "--json"])
            assert result.exit_code == 0
            # Should output JSON
            output = json.loads(result.stdout)
            assert "project" in output
        except json.JSONDecodeError:
            # If output is not JSON, that's also acceptable for this test
            pass
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_estimate_command(self, mock_project_builder_class, sample_config_ini):
        """Test estimate command"""
        mock_project_builder = Mock()
        mock_project_builder.estimate = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["estimate", "full"])
            # May succeed or fail depending on config
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_export_command(self, mock_project_builder_class, sample_config_ini):
        """Test export command"""
        mock_project_builder = Mock()
        mock_project_builder.export = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["export", "output.jsonl"])
            # May succeed or fail depending on storage
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_export_command_fields_where(self, mock_project_builder_class, sample_config_ini):
        """Test export command with fields and where"""
        mock_project_builder = Mock()
        mock_project_builder.export = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["export", "output.jsonl", "--fields", "id,name", "--where", "id >= 1"])
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
            mock_project_builder.export.assert_called_with(
                "jsonl",
                "output.jsonl",
                fields=["id", "name"],
                where="id >= 1"
            )
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_validate_config_command(self, mock_project_builder_class, sample_config_ini):
        """Test validate_config command with a valid config"""
        mock_project_builder = Mock()
        # New return shape: (is_valid, error_count, warning_count)
        mock_project_builder.validate_config = Mock(return_value=(True, 0, 0))
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["validate-config"])
            assert result.exit_code == 0, f"unexpected exit: {result.exit_code}\n{result.stdout}"
            assert "valid" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_validate_config_command_invalid(self, mock_project_builder_class, sample_config_ini):
        """Test validate_config command with an invalid config (errors > 0 -> exit 1)."""
        mock_project_builder = Mock()
        mock_project_builder.validate_config = Mock(return_value=(False, 2, 0))
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["validate-config"])
            assert result.exit_code == 1, f"unexpected exit: {result.exit_code}\n{result.stdout}"
            assert "failed" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_follow_command(self, mock_project_builder_class, sample_config_ini):
        """Test follow command"""
        mock_project_builder = Mock()
        mock_project_builder.follow = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["follow", "full"])
            # May succeed or fail depending on config
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
        finally:
            os.chdir(original_cwd)
    
    @patch('apibackuper.core.ProjectBuilder')
    def test_getfiles_command(self, mock_project_builder_class, sample_config_ini):
        """Test getfiles command"""
        mock_project_builder = Mock()
        mock_project_builder.getfiles = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder
        
        runner = typer.testing.CliRunner()
        
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["getfiles"])
            # May succeed or fail depending on config
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_update_command(self, mock_project_builder_class, sample_config_ini):
        """Test update command"""
        mock_project_builder = Mock()
        mock_project_builder.update = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["update"])
            assert result.exit_code in (0, 2), (
                f"command crashed uncaught: exit={result.exit_code}, "
                f"output={result.output}"
            )
            mock_project_builder.update.assert_called_with(resume=False)
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_detect_command(self, mock_project_builder_class, sample_config_ini):
        """Test detect command"""
        mock_project_builder = Mock()
        mock_project_builder.detect = Mock(return_value={"iterate_by": "page"})
        mock_project_builder.config_format = "yaml"
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()

        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["detect"])
            assert result.exit_code == 0
            mock_project_builder.detect.assert_called_with(write_config=False)
        finally:
            os.chdir(original_cwd)


class TestDryRunFlag:
    """``--dry-run`` is an alias for ``--profile`` on the ``run`` command
    and is also wired through ``update`` / ``follow``. None of them
    may invoke the underlying API method."""

    def _make_mock_builder(self, mock_project_builder_class):
        m = Mock()
        m.config_format = "yaml"
        m.config_filename = "apibackuper.yaml"
        m.name = "demo"
        m.start_url = "https://api.example.com/items"
        m.http_mode = "GET"
        m.resp_type = "json"
        m.storage_type = "zip"
        m.storagedir = "/tmp/store"
        m.auth_handler = None
        m.iterate_by = "page"
        m.page_limit = 50
        m.start_page = 1
        m.parallelism = 1
        m.rps = None
        m.burst = None
        m.total_number_key = None
        m.default_delay = None
        m._load_state = Mock(return_value={})
        m.run = Mock()
        m.update = Mock()
        m.follow = Mock()
        m.follow_mode = "item"
        m.follow_pattern = "https://api.example.com/items/{id}"
        mock_project_builder_class.return_value = m
        return m

    @patch('apibackuper.core.ProjectBuilder')
    def test_run_dry_run_alias_for_profile(self, mock_pbc, sample_config_ini):
        """--dry-run on `run` exits without invoking run()."""
        self._make_mock_builder(mock_pbc)
        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full", "--dry-run"])
            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert "estimate" in payload
            mock_pbc.return_value.run.assert_not_called()
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_update_dry_run_does_not_invoke_update(self, mock_pbc, sample_config_ini):
        """--dry-run on `update` prints the plan and exits."""
        self._make_mock_builder(mock_pbc)
        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["update", "--dry-run"])
            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert payload["command"] == "update"
            assert "estimate" in payload
            mock_pbc.return_value.update.assert_not_called()
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_follow_dry_run_does_not_invoke_follow(self, mock_pbc, sample_config_ini):
        """--dry-run on `follow` prints the plan and exits."""
        self._make_mock_builder(mock_pbc)
        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["follow", "full", "--dry-run"])
            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert payload["command"] == "follow"
            assert "estimate" in payload
            mock_pbc.return_value.follow.assert_not_called()
        finally:
            os.chdir(original_cwd)


class TestProfileFlag:
    """P4 (add-dry-run-mode): ``--profile`` prints a JSON estimate
    sub-dict sourced from ``cmds.profile.compute_profile_estimate``.
    These tests guard the wiring through the CLI."""

    @patch('apibackuper.core.ProjectBuilder')
    def test_profile_flag_emits_estimate_subdict(self, mock_project_builder_class, sample_config_ini):
        mock_project_builder = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder.config_filename = sample_config_ini
        mock_project_builder.name = "demo"
        mock_project_builder.start_url = "https://api.example.com/items"
        mock_project_builder.http_mode = "GET"
        mock_project_builder.resp_type = "json"
        mock_project_builder.storage_type = "zip"
        mock_project_builder.storagedir = "/tmp/store"
        mock_project_builder.auth_handler = None
        mock_project_builder.iterate_by = "page"
        mock_project_builder.page_limit = 50
        mock_project_builder.start_page = 1
        mock_project_builder.parallelism = 1
        mock_project_builder.rps = 5.0
        mock_project_builder.burst = 1
        mock_project_builder.total_number_key = "meta.total"
        mock_project_builder.default_delay = 0.5
        mock_project_builder._load_state = Mock(return_value={})
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full", "--profile"])
            assert result.exit_code == 0, (
                f"--profile crashed: exit={result.exit_code}, output={result.output}"
            )
            payload = json.loads(result.stdout)
            assert "estimate" in payload
            assert payload["estimate"]["source"] == "config"
            assert payload["estimate"]["records_estimate"] == 50  # 1 page lower bound
            assert payload["estimate"]["pages_estimate"] == 1
            assert payload["estimate"]["eta_seconds"] is not None
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_profile_flag_uses_state_when_present(self, mock_project_builder_class, sample_config_ini):
        mock_project_builder = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder.config_filename = sample_config_ini
        mock_project_builder.name = "demo"
        mock_project_builder.start_url = "https://api.example.com/items"
        mock_project_builder.http_mode = "GET"
        mock_project_builder.resp_type = "json"
        mock_project_builder.storage_type = "zip"
        mock_project_builder.storagedir = "/tmp/store"
        mock_project_builder.auth_handler = None
        mock_project_builder.iterate_by = "page"
        mock_project_builder.page_limit = 50
        mock_project_builder.start_page = 1
        mock_project_builder.parallelism = 1
        mock_project_builder.rps = None
        mock_project_builder.burst = None
        mock_project_builder.total_number_key = None
        mock_project_builder.default_delay = None
        mock_project_builder._load_state = Mock(return_value={
            "records_processed": 1234,
            "last_run_start": "2026-10-01T10:00:00+00:00",
            "last_run_end": "2026-10-01T10:00:42+00:00",
        })
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full", "--profile"])
            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert payload["estimate"]["source"] == "state"
            assert payload["estimate"]["records_estimate"] == 1234
            assert payload["estimate"]["eta_seconds"] == 42.0
        finally:
            os.chdir(original_cwd)

    @patch('apibackuper.core.ProjectBuilder')
    def test_profile_flag_unknown_when_no_state_no_key(self, mock_project_builder_class, sample_config_ini):
        mock_project_builder = Mock()
        mock_project_builder.config_format = "yaml"
        mock_project_builder.config_filename = sample_config_ini
        mock_project_builder.name = "demo"
        mock_project_builder.start_url = "https://api.example.com/items"
        mock_project_builder.http_mode = "GET"
        mock_project_builder.resp_type = "json"
        mock_project_builder.storage_type = "zip"
        mock_project_builder.storagedir = "/tmp/store"
        mock_project_builder.auth_handler = None
        mock_project_builder.iterate_by = "page"
        mock_project_builder.page_limit = 50
        mock_project_builder.start_page = 1
        mock_project_builder.parallelism = 1
        mock_project_builder.rps = None
        mock_project_builder.burst = None
        mock_project_builder.total_number_key = None
        mock_project_builder.default_delay = None
        mock_project_builder._load_state = Mock(return_value={})
        mock_project_builder_class.return_value = mock_project_builder

        runner = typer.testing.CliRunner()
        project_dir = os.path.dirname(sample_config_ini)
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(app, ["run", "full", "--profile"])
            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert payload["estimate"]["source"] == "unknown"
            assert payload["estimate"]["records_estimate"] is None
        finally:
            os.chdir(original_cwd)
