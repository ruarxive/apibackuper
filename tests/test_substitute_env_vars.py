"""Tests for ``substitute_env_vars`` from ``cmds.config_loader``.

The helper walks a parsed config (dict / list / str) and replaces
``${VAR}`` placeholders with values from the environment. The CLI
calls it right after ``yaml.safe_load`` so secrets stay out of
config files (improve-security 4.1-4.3).
"""
import pytest

from apibackuper.cmds.config_loader import (
    UnresolvedEnvVarError,
    substitute_env_vars,
)


class TestScalarSubstitution:
    """Plain ``${VAR}`` lookups."""

    def test_simple_lookup(self):
        result = substitute_env_vars(
            "Bearer ${TOKEN}",
            environ={"TOKEN": "abc123"},
        )
        assert result == "Bearer abc123"

    def test_entire_string_is_variable(self):
        result = substitute_env_vars(
            "${API_KEY}",
            environ={"API_KEY": "secret"},
        )
        assert result == "secret"

    def test_multiple_vars_in_one_string(self):
        result = substitute_env_vars(
            "https://${USER}@${HOST}:${PORT}",
            environ={"USER": "alice", "HOST": "example.com", "PORT": "5432"},
        )
        assert result == "https://alice@example.com:5432"

    def test_no_var_in_string_unchanged(self):
        result = substitute_env_vars(
            "hello world",
            environ={},
        )
        assert result == "hello world"


class TestDefaultFallback:
    """POSIX ``${VAR:-default}`` semantics."""

    def test_default_used_when_unset(self):
        result = substitute_env_vars(
            "${MISSING:-fallback}",
            environ={},
        )
        assert result == "fallback"

    def test_default_used_when_empty(self):
        # POSIX: ``:-`` triggers the default when the variable is unset
        # OR empty.
        result = substitute_env_vars(
            "${EMPTY:-fallback}",
            environ={"EMPTY": ""},
        )
        assert result == "fallback"

    def test_default_ignored_when_set(self):
        result = substitute_env_vars(
            "${SET:-fallback}",
            environ={"SET": "real"},
        )
        assert result == "real"

    def test_empty_default(self):
        # ``${MISSING:-}`` is the canonical "default to empty string".
        result = substitute_env_vars(
            "[${MISSING:-}]",
            environ={},
        )
        assert result == "[]"


class TestUnresolvedVariable:
    """Missing variables must raise, not silently substitute."""

    def test_unset_raises(self):
        with pytest.raises(UnresolvedEnvVarError) as exc_info:
            substitute_env_vars(
                "Bearer ${MISSING_TOKEN}",
                environ={"OTHER": "x"},
            )
        assert exc_info.value.name == "MISSING_TOKEN"

    def test_unset_error_carries_source(self):
        with pytest.raises(UnresolvedEnvVarError) as exc_info:
            substitute_env_vars(
                "${SECRET}",
                environ={},
                source="project.yaml",
            )
        assert exc_info.value.source == "project.yaml"
        assert "project.yaml" in str(exc_info.value)

    def test_unresolved_is_keyerror_subclass(self):
        # KeyError lets callers catch with the standard exception type.
        with pytest.raises(KeyError):
            substitute_env_vars("${X}", environ={})


class TestRecursiveWalk:
    """Dicts, lists, and nested structures are walked fully."""

    def test_dict_replaced_recursively(self):
        result = substitute_env_vars(
            {
                "auth": {"token": "${TOKEN}"},
                "url": "https://${HOST}/api",
            },
            environ={"TOKEN": "abc", "HOST": "example.com"},
        )
        assert result == {
            "auth": {"token": "abc"},
            "url": "https://example.com/api",
        }

    def test_list_replaced_recursively(self):
        result = substitute_env_vars(
            ["${A}", "${B}", "literal"],
            environ={"A": "1", "B": "2"},
        )
        assert result == ["1", "2", "literal"]

    def test_nested_structure(self):
        result = substitute_env_vars(
            {
                "endpoints": [
                    {"path": "/${VERSION}/list", "auth": "${TOKEN}"},
                    {"path": "/${VERSION}/get"},
                ],
                "version": "${VERSION}",
            },
            environ={"VERSION": "v1", "TOKEN": "tok"},
        )
        assert result == {
            "endpoints": [
                {"path": "/v1/list", "auth": "tok"},
                {"path": "/v1/get"},
            ],
            "version": "v1",
        }

    def test_non_string_scalars_unchanged(self):
        result = substitute_env_vars(
            {"port": 8080, "enabled": True, "rate": 1.5, "retries": None},
            environ={},
        )
        assert result == {"port": 8080, "enabled": True, "rate": 1.5, "retries": None}


class TestKwargsOnly:
    """The signature is kwargs-only by convention (mirror the
    decomposition pattern used elsewhere)."""

    def test_positional_value_works(self):
        # First positional is `value`; everything else must be kwarg.
        result = substitute_env_vars("${X}", environ={"X": "y"})
        assert result == "y"

    def test_source_is_optional(self):
        # The default source=None should not crash.
        result = substitute_env_vars("${X}", environ={"X": "y"})
        assert result == "y"

    def test_environ_default_to_os_environ(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_VAR", "from-env")
        result = substitute_env_vars("hi ${MY_TEST_VAR}")
        assert result == "hi from-env"


class TestRealWorldConfig:
    """End-to-end shape tests that mimic typical YAML configs."""

    def test_apibackuper_style_config(self):
        # Mirrors the layout in examples/sozd or similar real configs.
        config = {
            "data": {
                "url": "${API_BASE_URL}/items",
                "headers": {
                    "Authorization": "Bearer ${API_TOKEN}",
                    "X-Tenant": "${TENANT_ID:-default-tenant}",
                },
            },
            "storage": {
                "type": "zip",
                "path": "${BACKUP_DIR:-/tmp/backups}",
            },
        }
        env = {
            "API_BASE_URL": "https://api.example.com",
            "API_TOKEN": "secret-xyz",
        }
        result = substitute_env_vars(config, environ=env)
        assert result["data"]["url"] == "https://api.example.com/items"
        assert result["data"]["headers"]["Authorization"] == "Bearer secret-xyz"
        assert result["data"]["headers"]["X-Tenant"] == "default-tenant"
        assert result["storage"]["path"] == "/tmp/backups"