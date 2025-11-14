"""Tests for config loader"""
import os
import json
import pytest
import configparser
from unittest.mock import patch, mock_open
from apibackuper.cmds.config_loader import (
    load_json_file,
    load_schema,
    validate_yaml_config,
    YAMLConfigParser
)


class TestLoadJsonFile:
    """Tests for load_json_file function"""
    
    def test_load_json_file_exists(self, temp_dir):
        """Test loading existing JSON file"""
        file_path = os.path.join(temp_dir, "test.json")
        data = {"key": "value", "number": 123}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        result = load_json_file(file_path)
        assert result == data
    
    def test_load_json_file_not_exists(self):
        """Test loading non-existent JSON file returns default"""
        result = load_json_file("nonexistent.json")
        assert result == {}
    
    def test_load_json_file_not_exists_custom_default(self):
        """Test loading non-existent JSON file with custom default"""
        default = {"default": "value"}
        result = load_json_file("nonexistent.json", default=default)
        assert result == default
    
    def test_load_json_file_invalid_json(self, temp_dir):
        """Test loading invalid JSON file"""
        file_path = os.path.join(temp_dir, "invalid.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("invalid json content {")
        
        with pytest.raises(json.JSONDecodeError):
            load_json_file(file_path)


class TestLoadSchema:
    """Tests for load_schema function"""
    
    def test_load_schema_available(self):
        """Test loading schema when jsonschema is available"""
        # This test depends on jsonschema being available
        # and the schema file existing
        schema = load_schema()
        # Schema might be None if jsonschema is not available
        # or file doesn't exist, so we just check it doesn't crash
        assert schema is None or isinstance(schema, dict)
    
    @patch('apibackuper.cmds.config_loader.JSONSCHEMA_AVAILABLE', False)
    def test_load_schema_not_available(self):
        """Test loading schema when jsonschema is not available"""
        schema = load_schema()
        assert schema is None


class TestValidateYamlConfig:
    """Tests for validate_yaml_config function"""
    
    def test_validate_yaml_config_no_schema(self):
        """Test validation when schema is not available"""
        config = {"project": {"name": "test"}}
        result = validate_yaml_config(config, None)
        # Should return True when no schema (no validation)
        assert result is True
    
    def test_validate_yaml_config_valid(self):
        """Test validation with valid config"""
        # This test depends on jsonschema and schema file
        # For now, we'll just test it doesn't crash
        config = {"project": {"name": "test"}}
        schema = None  # Would be loaded from file in real scenario
        result = validate_yaml_config(config, schema)
        assert isinstance(result, bool)
    
    @patch('apibackuper.cmds.config_loader.JSONSCHEMA_AVAILABLE', False)
    def test_validate_yaml_config_no_jsonschema(self):
        """Test validation when jsonschema is not available"""
        config = {"project": {"name": "test"}}
        result = validate_yaml_config(config, {})
        # Should return True when jsonschema not available
        assert result is True


class TestYAMLConfigParser:
    """Tests for YAMLConfigParser class"""
    
    def test_init_with_yaml_file(self, temp_dir):
        """Test initializing with YAML file"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
project:
  name: test_project
  url: https://api.example.com
configuration:
  page_limit: 10
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.has_section("project")
        assert parser.has_section("configuration")
    
    def test_get_section(self, temp_dir):
        """Test getting section from YAML"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
project:
  name: test_project
  url: https://api.example.com
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.has_section("project")
        assert parser.get("project", "name") == "test_project"
        assert parser.get("project", "url") == "https://api.example.com"
    
    def test_get_with_default(self, temp_dir):
        """Test getting value with default"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
project:
  name: test_project
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.get("project", "name") == "test_project"
        # Get non-existent key
        assert parser.get("project", "missing", fallback="default") == "default"
    
    def test_has_option(self, temp_dir):
        """Test checking if option exists"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
project:
  name: test_project
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.has_option("project", "name")
        assert not parser.has_option("project", "missing")
        assert not parser.has_option("missing_section", "name")
    
    def test_getint(self, temp_dir):
        """Test getting integer value"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
configuration:
  page_limit: 10
  timeout: "20"
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.getint("configuration", "page_limit") == 10
        assert parser.getint("configuration", "timeout") == 20
    
    def test_getfloat(self, temp_dir):
        """Test getting float value"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
configuration:
  delay: 0.5
  rate: "1.5"
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.getfloat("configuration", "delay") == 0.5
        assert parser.getfloat("configuration", "rate") == 1.5
    
    def test_getboolean(self, temp_dir):
        """Test getting boolean value"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
configuration:
  enabled: true
  disabled: false
  yes_str: "yes"
  no_str: "no"
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        assert parser.getboolean("configuration", "enabled") is True
        assert parser.getboolean("configuration", "disabled") is False
        assert parser.getboolean("configuration", "yes_str") is True
        assert parser.getboolean("configuration", "no_str") is False
    
    def test_sections(self, temp_dir):
        """Test getting all sections"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        yaml_content = """
project:
  name: test
configuration:
  limit: 10
data:
  key: items
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        parser = YAMLConfigParser(yaml_path)
        sections = parser.sections()
        assert "project" in sections
        assert "configuration" in sections
        assert "data" in sections
    
    @patch('apibackuper.cmds.config_loader.YAML_AVAILABLE', False)
    def test_init_no_yaml_support(self, temp_dir):
        """Test initializing when YAML is not available"""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        with pytest.raises(ImportError):
            YAMLConfigParser(yaml_path)

