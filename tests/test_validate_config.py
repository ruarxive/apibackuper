"""Tests for the rewritten ``ProjectBuilder.validate_config``.

The method now returns ``(is_valid, error_count, warning_count)`` instead of
a bare ``bool`` so the CLI can distinguish "valid with warnings" from
"valid clean" and exit codes can be chosen without re-reading output.
"""
import configparser
import os

from apibackuper.cmds.project import ProjectBuilder


def _write_minimal_yaml(tmp_path, **overrides):
    yaml_path = tmp_path / "apibackuper.yaml"
    data = {
        "settings": {"name": "t"},
        "project": {
            "url": "https://api.example.com/items",
            "http_mode": "GET",
        },
        "params": {"page_size_limit": 10},
        "data": {},
        "storage": {"storage_type": "zip", "storage_path": "storage"},
    }
    for k, v in overrides.items():
        section, key = k.split(".", 1)
        data.setdefault(section, {})[key] = v
    import yaml
    yaml_path.write_text(yaml.safe_dump(data), encoding="utf8")
    return str(yaml_path)


class TestValidateConfigReturnShape:
    def test_returns_three_tuple(self, tmp_path):
        cfg = _write_minimal_yaml(tmp_path)
        builder = ProjectBuilder(str(tmp_path))
        result = builder.validate_config(verbose=False)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_valid_config_returns_zero_errors(self, tmp_path):
        _write_minimal_yaml(tmp_path)
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, warnings = builder.validate_config(verbose=False)
        # The minimal config has no errors and may have warnings (e.g. INI
        # deprecation, missing data_key). We don't assert on warnings here.
        assert errors == 0
        assert is_valid is True

    def test_missing_required_section_reports_error(self, tmp_path):
        # Write a config without the 'settings' section. Use ``__new__`` to
        # bypass the ``__init__`` which would crash trying to read
        # ``settings.name`` directly.
        yaml_path = tmp_path / "apibackuper.yaml"
        import yaml
        yaml_path.write_text(yaml.safe_dump({
            "project": {"url": "https://x", "http_mode": "GET"},
            "params": {"page_size_limit": 1},
            "data": {},
            "storage": {"storage_type": "zip", "storage_path": "x"},
        }))
        builder = ProjectBuilder.__new__(ProjectBuilder)
        builder.config_filename = str(yaml_path)
        builder.config_format = "yaml"
        # Reload the YAML into a YAMLConfigParser (the __init__ would
        # have done this for us).
        from apibackuper.cmds.config_loader import YAMLConfigParser
        with open(yaml_path, "r", encoding="utf8") as f:
            builder.config = YAMLConfigParser(yaml.safe_load(f))
        builder.field_splitter = "."
        is_valid, errors, warnings = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_missing_config_returns_error(self, tmp_path):
        # No config file in the directory.
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, warnings = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1
        assert isinstance(warnings, int)

    def test_unknown_storage_type_is_error(self, tmp_path):
        # The schema enum rejects ``foobar`` before the project-specific
        # rule gets a chance to warn. Net result: at least one error.
        yaml_path = tmp_path / "apibackuper.yaml"
        import yaml
        yaml_path.write_text(yaml.safe_dump({
            "settings": {"name": "t"},
            "project": {"url": "https://x", "http_mode": "GET"},
            "params": {"page_size_limit": 1},
            "data": {},
            "storage": {"storage_type": "foobar", "storage_path": "x"},
        }))
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, warnings = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_invalid_http_mode_is_error(self, tmp_path):
        _write_minimal_yaml(tmp_path, **{"project.http_mode": "WALK"})
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, _ = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_invalid_url_is_error(self, tmp_path):
        _write_minimal_yaml(tmp_path, **{"project.url": "not-a-url"})
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, _ = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_page_size_limit_zero_is_error(self, tmp_path):
        _write_minimal_yaml(tmp_path, **{"params.page_size_limit": 0})
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, _ = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_page_size_limit_non_integer_is_error(self, tmp_path):
        # The schema's ``integer`` type rejects a string value before the
        # project-specific getint() check has a chance to run.
        _write_minimal_yaml(tmp_path, **{"params.page_size_limit": "abc"})
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, _ = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_auth_basic_missing_credentials(self, tmp_path):
        _write_minimal_yaml(tmp_path)
        cfg_path = tmp_path / "apibackuper.yaml"
        import yaml
        existing = yaml.safe_load(cfg_path.read_text())
        existing["auth"] = {"type": "basic"}
        cfg_path.write_text(yaml.safe_dump(existing))
        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, _ = builder.validate_config(verbose=False)
        assert is_valid is False
        assert errors >= 1

    def test_warnings_count_returned(self, tmp_path):
        # INI config triggers the "INI is deprecated" warning; we don't
        # need a real run, just verify the validator returns an int.
        ini = configparser.ConfigParser()
        ini.add_section("settings")
        ini.set("settings", "name", "t")
        ini.add_section("project")
        ini.set("project", "url", "https://x")
        ini.set("project", "http_mode", "GET")
        ini.add_section("params")
        ini.set("params", "page_size_limit", "1")
        ini.add_section("data")
        ini.add_section("storage")
        ini.set("storage", "storage_type", "zip")
        cfg_path = tmp_path / "apibackuper.cfg"
        with open(cfg_path, "w") as f:
            ini.write(f)

        builder = ProjectBuilder(str(tmp_path))
        is_valid, errors, warnings = builder.validate_config(verbose=False)
        # INI is deprecated -> warning; no errors -> is_valid
        assert errors == 0
        assert warnings >= 1
        assert is_valid is True