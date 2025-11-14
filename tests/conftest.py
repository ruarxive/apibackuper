"""Shared fixtures and test utilities"""
import os
import tempfile
import shutil
from typing import Generator
import pytest
import configparser
from unittest.mock import Mock, MagicMock


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_config_ini(temp_dir: str) -> str:
    """Create a sample INI config file"""
    config_path = os.path.join(temp_dir, "apibackuper.cfg")
    config = configparser.ConfigParser()
    
    config.add_section("project")
    config.set("project", "name", "test_project")
    config.set("project", "url", "https://api.example.com/data")
    config.set("project", "http_mode", "GET")
    config.set("project", "response_type", "json")
    config.set("project", "storage_type", "zip")
    config.set("project", "storage_path", "storage.zip")
    
    config.add_section("configuration")
    config.set("configuration", "page_limit", "10")
    config.set("configuration", "start_page", "1")
    config.set("configuration", "iterate_by", "page")
    config.set("configuration", "default_delay", "0.5")
    config.set("configuration", "retry_count", "3")
    
    config.add_section("data")
    config.set("data", "data_key", "items")
    config.set("data", "total_number_key", "total")
    
    config.add_section("params")
    config.set("params", "page_number_param", "page")
    config.set("params", "page_size_param", "size")
    
    with open(config_path, "w") as f:
        config.write(f)
    
    return config_path


@pytest.fixture
def sample_config_yaml(temp_dir: str) -> str:
    """Create a sample YAML config file"""
    config_path = os.path.join(temp_dir, "apibackuper.yaml")
    yaml_content = """project:
  name: test_project
  url: https://api.example.com/data
  http_mode: GET
  response_type: json
  storage_type: zip
  storage_path: storage.zip

configuration:
  page_limit: 10
  start_page: 1
  iterate_by: page
  default_delay: 0.5
  retry_count: 3

data:
  data_key: items
  total_number_key: total

params:
  page_number_param: page
  page_size_param: size
"""
    with open(config_path, "w") as f:
        f.write(yaml_content)
    
    return config_path


@pytest.fixture
def mock_requests_session():
    """Create a mock requests session"""
    session = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"items": [], "total": 0}
    response.text = '{"items": [], "total": 0}'
    response.content = b'{"items": [], "total": 0}'
    response.headers = {"Content-Type": "application/json"}
    session.get.return_value = response
    session.post.return_value = response
    return session


@pytest.fixture
def sample_json_data():
    """Sample JSON data for testing"""
    return {
        "items": [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
        ],
        "total": 2,
        "page": 1,
        "pages": 1
    }


@pytest.fixture
def sample_xml_data():
    """Sample XML data for testing"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<root>
    <item id="1">
        <name>Item 1</name>
        <value>100</value>
    </item>
    <item id="2">
        <name>Item 2</name>
        <value>200</value>
    </item>
</root>"""


@pytest.fixture
def sample_csv_data(temp_dir: str) -> str:
    """Create a sample CSV file"""
    csv_path = os.path.join(temp_dir, "test.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("id;name;value\n")
        f.write("1;Item 1;100\n")
        f.write("2;Item 2;200\n")
    return csv_path

