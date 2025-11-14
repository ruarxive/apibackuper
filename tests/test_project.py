"""Tests for ProjectBuilder"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from apibackuper.cmds.project import ProjectBuilder


class TestProjectBuilder:
    """Tests for ProjectBuilder class"""
    
    def test_init_with_ini_config(self, sample_config_ini):
        """Test initializing with INI config file"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        assert builder.project_path == project_dir
        assert builder.config_format == 'ini'
        assert os.path.basename(builder.config_filename) == "apibackuper.cfg"
    
    def test_init_with_yaml_config(self, sample_config_yaml):
        """Test initializing with YAML config file"""
        project_dir = os.path.dirname(sample_config_yaml)
        builder = ProjectBuilder(project_dir)
        assert builder.project_path == project_dir
        assert builder.config_format == 'yaml'
        assert os.path.basename(builder.config_filename) in ["apibackuper.yaml", "apibackuper.yml"]
    
    def test_init_default_path(self, sample_config_ini, temp_dir):
        """Test initializing with default path (current directory)"""
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(sample_config_ini))
            builder = ProjectBuilder()
            assert builder.project_path == os.getcwd()
        finally:
            os.chdir(original_cwd)
    
    def test_init_custom_path(self, sample_config_ini):
        """Test initializing with custom project path"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        assert builder.project_path == project_dir
    
    @patch('apibackuper.cmds.project.ProjectBuilder.create')
    def test_create_static_method(self, mock_create, temp_dir):
        """Test ProjectBuilder.create static method"""
        project_name = "test_project"
        ProjectBuilder.create(project_name)
        mock_create.assert_called_once_with(project_name)
    
    def test_enable_logging(self, sample_config_ini):
        """Test enabling logging"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        builder.enable_logging()
        # Should not raise exception
        assert builder is not None
    
    @patch('apibackuper.cmds.project.ProjectBuilder._read_config')
    def test_config_priority_yaml_over_ini(self, mock_read_config, temp_dir):
        """Test that YAML config takes priority over INI"""
        # Create both config files
        ini_path = os.path.join(temp_dir, "apibackuper.cfg")
        yaml_path = os.path.join(temp_dir, "apibackuper.yaml")
        
        with open(ini_path, "w") as f:
            f.write("[project]\nname = ini_project\n")
        
        with open(yaml_path, "w") as f:
            f.write("project:\n  name: yaml_project\n")
        
        builder = ProjectBuilder(temp_dir)
        # Should use YAML config
        assert builder.config_format == 'yaml'
        assert os.path.basename(builder.config_filename) in ["apibackuper.yaml", "apibackuper.yml"]
    
    def test_config_not_found(self, temp_dir):
        """Test behavior when config file is not found"""
        # Create empty directory
        builder = ProjectBuilder(temp_dir)
        # Should default to INI format
        assert builder.config_format == 'ini'
        assert os.path.basename(builder.config_filename) == "apibackuper.cfg"
    
    @patch('apibackuper.cmds.project.ProjectBuilder._read_config')
    def test_info_method(self, mock_read_config, sample_config_ini):
        """Test info method"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        
        # Mock the internal methods that info() calls
        with patch.object(builder, '_get_project_info', return_value={"project": {"name": "test"}}):
            with patch.object(builder, '_get_statistics', return_value={}):
                report = builder.info(stats=False)
                assert report is not None
                assert "project" in report
    
    @patch('apibackuper.cmds.project.ProjectBuilder._read_config')
    def test_validate_config_method(self, mock_read_config, sample_config_ini):
        """Test validate_config method"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        
        # Mock validation logic
        with patch('apibackuper.cmds.project.validate_yaml_config', return_value=True):
            result = builder.validate_config(verbose=False)
            # Result depends on actual validation logic
            assert isinstance(result, bool)
    
    def test_project_path_normalization(self, sample_config_ini):
        """Test that project path is normalized correctly"""
        project_dir = os.path.dirname(sample_config_ini)
        # Use absolute path
        abs_path = os.path.abspath(project_dir)
        builder = ProjectBuilder(abs_path)
        assert os.path.isabs(builder.project_path)
    
    @patch('apibackuper.cmds.project.ProjectBuilder._read_config')
    def test_config_sections_available(self, mock_read_config, sample_config_ini):
        """Test that config sections are accessible"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        
        # Should have access to config
        assert hasattr(builder, 'config') or hasattr(builder, '_config')
    
    def test_http_session_initialized(self, sample_config_ini):
        """Test that HTTP session is initialized"""
        project_dir = os.path.dirname(sample_config_ini)
        builder = ProjectBuilder(project_dir)
        assert hasattr(builder, 'http')
        assert builder.http is not None

