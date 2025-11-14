# -*- coding: utf-8 -*-
"""Configuration loading and parsing functionality"""
import configparser
import json
import logging
import os
from typing import Optional, Dict, List, Any, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    validate = None
    ValidationError = Exception


def load_json_file(filename: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Loads JSON file and return it as dict"""
    if default is None:
        default = {}
    if os.path.exists(filename):
        fobj = open(filename, "r", encoding="utf8")
        data = json.load(fobj)
        fobj.close()
    else:
        data = default
    return data


def load_schema() -> Optional[Dict[str, Any]]:
    """Load JSON schema for YAML config validation"""
    if not JSONSCHEMA_AVAILABLE:
        return None
    
    # Try multiple paths to find the schema file
    # First, try relative to this file (for development)
    schema_paths = [
        os.path.join(os.path.dirname(__file__), "..", "schemas", "config_schema.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas", "config_schema.json"),
    ]
    
    # Also try using importlib.resources if available (for installed packages)
    # Prefer importlib.resources over deprecated pkg_resources
    try:
        # Try Python 3.9+ importlib.resources.files API
        try:
            from importlib.resources import files as resource_files
            schema_path = resource_files('apibackuper') / 'schemas' / 'config_schema.json'
            if schema_path.is_file():
                schema_paths.insert(0, str(schema_path))
        except (ImportError, AttributeError):
            # Try Python 3.7-3.8 importlib.resources.path API
            try:
                import importlib.resources as importlib_resources_module
                try:
                    with importlib_resources_module.path('apibackuper.schemas', 'config_schema.json') as schema_path:
                        if os.path.exists(schema_path):
                            schema_paths.insert(0, str(schema_path))
                except Exception:
                    pass
            except (ImportError, AttributeError):
                # Try importlib_resources backport for Python 3.6
                try:
                    import importlib_resources
                    try:
                        with importlib_resources.path('apibackuper.schemas', 'config_schema.json') as schema_path:
                            if os.path.exists(schema_path):
                                schema_paths.insert(0, str(schema_path))
                    except Exception:
                        pass
                except (ImportError, AttributeError):
                    pass
    except Exception:
        pass
    
    for schema_path in schema_paths:
        if os.path.exists(schema_path):
            try:
                with open(schema_path, "r", encoding="utf8") as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Error loading schema file from {schema_path}: {e}")
                continue
    
    logging.warning("Schema file not found in any expected location")
    return None


def validate_yaml_config(yaml_data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[Dict[str, str]]]:
    """Validate YAML config data against JSON schema"""
    if not JSONSCHEMA_AVAILABLE:
        logging.warning("jsonschema not available, skipping validation")
        return True, []
    
    if schema is None:
        schema = load_schema()
    
    if schema is None:
        logging.warning("Schema file not found, skipping validation")
        return True, []
    
    errors = []
    try:
        validate(instance=yaml_data, schema=schema)
        return True, []
    except ValidationError as e:
        errors.append({
            "message": e.message,
            "path": ".".join(str(p) for p in e.path),
            "schema_path": ".".join(str(p) for p in e.schema_path)
        })
        # Collect all errors if possible
        if hasattr(e, 'context'):
            for error in e.context:
                errors.append({
                    "message": error.message,
                    "path": ".".join(str(p) for p in error.path),
                    "schema_path": ".".join(str(p) for p in error.schema_path)
                })
        return False, errors
    except Exception as e:
        logging.error(f"Error during schema validation: {e}")
        return True, []  # Don't fail on validation errors, just log them


class YAMLConfigParser:
    """Wrapper class to make YAML config work like ConfigParser"""
    
    def __init__(self, yaml_data: Optional[Dict[str, Any]]) -> None:
        """Initialize with YAML data (dict)"""
        self._data: Dict[str, Any] = yaml_data if yaml_data else {}
    
    def has_section(self, section: str) -> bool:
        """Check if section exists"""
        return section in self._data
    
    def has_option(self, section: str, option: str) -> bool:
        """Check if option exists in section"""
        return self.has_section(section) and option in self._data[section]
    
    def get(self, section: str, option: str, fallback: Optional[str] = None) -> str:
        """Get option value from section"""
        if not self.has_option(section, option):
            if fallback is not None:
                return fallback
            raise configparser.NoOptionError(option, section)
        return str(self._data[section][option])
    
    def getint(self, section: str, option: str, fallback: Optional[int] = None) -> Optional[int]:
        """Get integer option value from section"""
        value = self.get(section, option, fallback)
        if value is None:
            return None
        return int(value)
    
    def getboolean(self, section: str, option: str, fallback: Optional[bool] = None) -> Optional[bool]:
        """Get boolean option value from section"""
        value = self.get(section, option, fallback)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        value_lower = str(value).lower()
        if value_lower in ('true', 'yes', 'on', '1'):
            return True
        elif value_lower in ('false', 'no', 'off', '0'):
            return False
        raise ValueError("Not a boolean: %s" % value)

