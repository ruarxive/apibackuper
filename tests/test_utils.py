"""Tests for utility functions"""
import os
import pytest
from apibackuper.cmds.utils import load_file_list, load_csv_data, _url_replacer


class TestLoadFileList:
    """Tests for load_file_list function"""
    
    def test_load_file_list(self, temp_dir):
        """Test loading file as list of lines"""
        file_path = os.path.join(temp_dir, "test.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("line1\n")
            f.write("line2\n")
            f.write("line3\n")
        
        result = load_file_list(file_path)
        assert result == ["line1", "line2", "line3"]
    
    def test_load_file_list_empty(self, temp_dir):
        """Test loading empty file"""
        file_path = os.path.join(temp_dir, "empty.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            pass
        
        result = load_file_list(file_path)
        assert result == []
    
    def test_load_file_list_strips_newlines(self, temp_dir):
        """Test that newlines are stripped"""
        file_path = os.path.join(temp_dir, "test.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("line1\n")
            f.write("line2\r\n")
            f.write("line3\n")
        
        result = load_file_list(file_path)
        assert all("\n" not in line and "\r" not in line for line in result)
    
    def test_load_file_list_custom_encoding(self, temp_dir):
        """Test loading file with custom encoding"""
        file_path = os.path.join(temp_dir, "test.txt")
        # Write UTF-8 content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("тест\n")
            f.write("测试\n")
        
        result = load_file_list(file_path, encoding="utf-8")
        assert "тест" in result
        assert "测试" in result


class TestLoadCsvData:
    """Tests for load_csv_data function"""
    
    def test_load_csv_data(self, temp_dir):
        """Test loading CSV data"""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("id;name;value\n")
            f.write("1;Item 1;100\n")
            f.write("2;Item 2;200\n")
        
        result = load_csv_data(file_path, "id")
        assert len(result) == 2
        assert "1" in result
        assert "2" in result
        assert result["1"]["name"] == "Item 1"
        assert result["2"]["name"] == "Item 2"
    
    def test_load_csv_data_custom_delimiter(self, temp_dir):
        """Test loading CSV with custom delimiter"""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("id,name,value\n")
            f.write("1,Item 1,100\n")
            f.write("2,Item 2,200\n")
        
        result = load_csv_data(file_path, "id", delimiter=",")
        assert len(result) == 2
        assert result["1"]["name"] == "Item 1"
    
    def test_load_csv_data_empty(self, temp_dir):
        """Test loading empty CSV"""
        file_path = os.path.join(temp_dir, "empty.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("id;name\n")
        
        result = load_csv_data(file_path, "id")
        assert result == {}
    
    def test_load_csv_data_duplicate_keys(self, temp_dir):
        """Test loading CSV with duplicate keys (last one wins)"""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("id;name;value\n")
            f.write("1;Item 1;100\n")
            f.write("1;Item 1 Updated;150\n")
        
        result = load_csv_data(file_path, "id")
        assert len(result) == 1
        assert result["1"]["name"] == "Item 1 Updated"


class TestUrlReplacer:
    """Tests for _url_replacer function"""
    
    def test_url_replacer_query_mode(self):
        """Test URL replacement in query mode"""
        url = "https://api.example.com/data"
        params = {"page": 1, "size": 10}
        result = _url_replacer(url, params, query_mode=True)
        
        assert "?" in result
        assert "page=1" in result
        assert "size=10" in result
        assert "&" in result
    
    def test_url_replacer_non_query_mode(self):
        """Test URL replacement in non-query mode"""
        url = "https://api.example.com/data"
        params = {"page": 1, "size": 10}
        result = _url_replacer(url, params, query_mode=False)
        
        assert ";" in result
        assert "page=1" in result
        assert "size=10" in result
    
    def test_url_replacer_empty_params(self):
        """Test URL replacement with empty params"""
        url = "https://api.example.com/data"
        params = {}
        result = _url_replacer(url, params, query_mode=True)
        
        assert result == url + "?"
    
    def test_url_replacer_existing_query(self):
        """Test URL replacement with existing query string"""
        url = "https://api.example.com/data?existing=value"
        params = {"page": 1}
        result = _url_replacer(url, params, query_mode=True)
        
        assert "existing=value" in result
        assert "page=1" in result
    
    def test_url_replacer_special_chars(self):
        """Test URL replacement with special characters in values"""
        url = "https://api.example.com/data"
        params = {"query": "test value", "id": "123&456"}
        result = _url_replacer(url, params, query_mode=True)
        
        assert "query=test value" in result
        assert "id=123&456" in result
    
    def test_url_replacer_numeric_values(self):
        """Test URL replacement with numeric values"""
        url = "https://api.example.com/data"
        params = {"page": 1, "size": 10, "offset": 0}
        result = _url_replacer(url, params, query_mode=True)
        
        assert "page=1" in result
        assert "size=10" in result
        assert "offset=0" in result
    
    def test_url_replacer_boolean_values(self):
        """Test URL replacement with boolean values"""
        url = "https://api.example.com/data"
        params = {"active": True, "deleted": False}
        result = _url_replacer(url, params, query_mode=True)
        
        assert "active=True" in result
        assert "deleted=False" in result

