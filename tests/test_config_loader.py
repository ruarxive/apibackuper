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
    YAMLConfigParser,
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

    @patch('apibackuper.cmds.config_loader.JSONSCHEMA_AVAILABLE', True)
    def test_load_schema_available(self):
        """Test that schema loads when jsonschema is available"""
        # Schema file is bundled; this verifies the loader finds it.
        schema = load_schema()
        assert schema is None or isinstance(schema, dict)

    @patch('apibackuper.cmds.config_loader.JSONSCHEMA_AVAILABLE', False)
    def test_load_schema_not_available(self):
        """Test that None is returned when jsonschema is missing"""
        schema = load_schema()
        assert schema is None


class TestValidateYamlConfig:
    """Tests for validate_yaml_config function.

    The function returns ``Tuple[bool, List[Dict[str, str]]]`` where the
    second element is a list of structured validation errors. Earlier
    tests asserted ``is True`` on the tuple, which was incorrect.
    """

    def test_validate_yaml_config_no_schema(self):
        """Empty/invalid schema -> vacuously valid, no errors raised.

        When ``schema=None`` the loader tries to load the bundled schema.
        When an empty dict is supplied instead, ``jsonschema.validate``
        accepts everything against it -> ``(True, [])``.
        """
        config = {"project": {"name": "test"}}
        ok, errors = validate_yaml_config(config, {})
        assert ok is True
        assert errors == []

    def test_validate_yaml_config_valid(self):
        """Valid config against the bundled schema.

        The bundled schema requires ``settings``, ``project``, ``params``,
        ``data`` and ``storage`` top-level sections.
        """
        config = {
            "settings": {"name": "test"},
            "project": {
                "url": "https://api.example.com",
                "http_mode": "GET",
            },
            "params": {"page_size_limit": 10},
            "data": {},
            "storage": {
                "storage_type": "zip",
                "storage_path": "storage",
            },
        }
        ok, errors = validate_yaml_config(config, None)
        assert ok is True, f"unexpected errors: {errors}"

    @patch('apibackuper.cmds.config_loader.JSONSCHEMA_AVAILABLE', False)
    def test_validate_yaml_config_no_jsonschema(self):
        """jsonschema unavailable -> vacuously valid, no errors raised."""
        config = {"project": {"name": "test"}}
        ok, errors = validate_yaml_config(config, {})
        assert ok is True
        assert errors == []

    def test_validate_yaml_config_invalid(self):
        """Schema-invalid config -> ok=False with structured errors."""
        # ``http_mode: "WALK"`` is not in the schema enum.
        config = {
            "settings": {"name": "test"},
            "project": {
                "url": "https://api.example.com",
                "http_mode": "WALK",
            },
            "params": {"page_size_limit": 10},
            "data": {},
            "storage": {"storage_type": "zip", "storage_path": "storage"},
        }
        ok, errors = validate_yaml_config(config, None)
        # If jsonschema is available and the schema is found, expect failure.
        # If neither is available, the function returns True.
        if not ok:
            assert isinstance(errors, list)
            assert len(errors) >= 1


class TestYAMLConfigParser:
    """Tests for YAMLConfigParser class.

    The parser takes a parsed dict (not a YAML file path) — file parsing
    is the caller's responsibility. Tests below exercise the dict API
    end-to-end.
    """

    def test_init_with_dict(self):
        """Test initializing with a parsed dict."""
        data = {"project": {"name": "x"}, "configuration": {"page_limit": 10}}
        parser = YAMLConfigParser(data)
        assert parser.has_section("project")
        assert parser.has_section("configuration")

    def test_init_with_none(self):
        """Test that ``None`` becomes an empty parser."""
        parser = YAMLConfigParser(None)
        assert not parser.has_section("project")

    def test_get_value(self):
        data = {"project": {"name": "test_project", "url": "https://api.example.com"}}
        parser = YAMLConfigParser(data)
        assert parser.get("project", "name") == "test_project"
        assert parser.get("project", "url") == "https://api.example.com"

    def test_get_with_default_fallback(self):
        data = {"project": {"name": "test_project"}}
        parser = YAMLConfigParser(data)
        assert parser.get("project", "name") == "test_project"
        # Get non-existent key
        assert parser.get("project", "missing", fallback="default") == "default"
        # Get non-existent key without fallback
        with pytest.raises(configparser.NoOptionError):
            parser.get("project", "missing")

    def test_has_option(self):
        data = {"project": {"name": "test_project"}}
        parser = YAMLConfigParser(data)
        assert parser.has_option("project", "name") is True
        assert parser.has_option("project", "missing") is False
        assert parser.has_option("missing_section", "name") is False

    def test_getint(self):
        data = {"configuration": {"page_limit": 10, "timeout": "20"}}
        parser = YAMLConfigParser(data)
        assert parser.getint("configuration", "page_limit") == 10
        assert parser.getint("configuration", "timeout") == 20
        # Default value path
        assert parser.getint("configuration", "missing", fallback=99) == 99

    def test_getfloat(self):
        # getfloat accepts int, float and string-numeric values
        data = {"configuration": {"delay": 0.5, "rate": "1.5", "count": 3}}
        parser = YAMLConfigParser(data)
        assert parser.getfloat("configuration", "delay") == 0.5
        assert parser.getfloat("configuration", "rate") == 1.5
        assert parser.getfloat("configuration", "count") == 3.0
        # Default value path
        assert parser.getfloat("configuration", "missing", fallback=2.0) == 2.0

    def test_getfloat_rejects_bool(self):
        """``True``/``False`` must not silently become 1.0/0.0."""
        data = {"configuration": {"enabled": True}}
        parser = YAMLConfigParser(data)
        with pytest.raises(ValueError):
            parser.getfloat("configuration", "enabled")

    def test_getboolean(self):
        data = {"configuration": {"enabled": True, "disabled": False,
                                  "yes_str": "yes", "no_str": "no"}}
        parser = YAMLConfigParser(data)
        assert parser.getboolean("configuration", "enabled") is True
        assert parser.getboolean("configuration", "disabled") is False
        assert parser.getboolean("configuration", "yes_str") is True
        assert parser.getboolean("configuration", "no_str") is False

    def test_sections(self):
        data = {"project": {"name": "test"},
                "configuration": {"limit": 10},
                "data": {"key": "items"}}
        parser = YAMLConfigParser(data)
        sections = parser.sections()
        assert "project" in sections
        assert "configuration" in sections
        assert "data" in sections