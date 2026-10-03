"""Tests for common utility functions"""
import pytest
import lxml.etree as etree
from apibackuper.common import (
    etree_to_dict,
    get_dict_value,
    set_dict_value,
    update_dict_values
)


class TestEtreeToDict:
    """Tests for etree_to_dict function"""
    
    def test_simple_xml(self):
        """Test converting simple XML to dict"""
        xml_str = "<root>test</root>"
        root = etree.fromstring(xml_str)
        result = etree_to_dict(root)
        assert result == {"root": "test"}
    
    def test_xml_with_attributes(self):
        """Test converting XML with attributes"""
        xml_str = '<root id="1" name="test">content</root>'
        root = etree.fromstring(xml_str)
        result = etree_to_dict(root)
        assert result["root"]["@id"] == "1"
        assert result["root"]["@name"] == "test"
        assert result["root"]["#text"] == "content"
    
    def test_xml_with_children(self):
        """Test converting XML with child elements"""
        xml_str = """<root>
            <item id="1">Item 1</item>
            <item id="2">Item 2</item>
        </root>"""
        root = etree.fromstring(xml_str)
        result = etree_to_dict(root)
        assert "item" in result["root"]
        items = result["root"]["item"]
        assert isinstance(items, list)
        assert len(items) == 2
    
    def test_xml_with_namespace(self):
        """Test converting XML with namespace (prefix stripping)"""
        xml_str = '<ns:root xmlns:ns="http://example.com">test</ns:root>'
        root = etree.fromstring(xml_str)
        result = etree_to_dict(root, prefix_strip=True)
        assert "root" in result
    
    def test_xml_with_prefix_strip_false(self):
        """Test converting XML without prefix stripping"""
        xml_str = '<ns:root xmlns:ns="http://example.com">test</ns:root>'
        root = etree.fromstring(xml_str)
        result = etree_to_dict(root, prefix_strip=False)
        # Should contain namespace prefix
        assert any("ns:" in key or "{" in key for key in result.keys())


class TestGetDictValue:
    """Tests for get_dict_value function"""
    
    def test_simple_key(self):
        """Test getting value with simple key"""
        data = {"key": "value"}
        result = get_dict_value(data, "key")
        assert result == "value"
    
    def test_nested_key(self):
        """Test getting value with nested key"""
        data = {"level1": {"level2": {"level3": "value"}}}
        result = get_dict_value(data, "level1.level2.level3")
        assert result == "value"
    
    def test_missing_key(self):
        """Test getting value for missing key"""
        data = {"key": "value"}
        result = get_dict_value(data, "missing")
        assert result is None
    
    def test_list_access(self):
        """Test getting value from list"""
        data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        result = get_dict_value(data, "name")
        assert result == "Item 1"  # Returns first item
    
    def test_list_access_as_array(self):
        """Test getting values from list as array"""
        data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        result = get_dict_value(data, "name", as_array=True)
        assert result == ["Item 1", "Item 2"]
    
    def test_nested_list(self):
        """Test getting value from nested list"""
        data = {
            "items": [
                {"id": 1, "tags": ["tag1", "tag2"]},
                {"id": 2, "tags": ["tag3"]}
            ]
        }
        result = get_dict_value(data, "items.tags", as_array=True)
        assert isinstance(result, list)
        assert len(result) > 0


class TestSetDictValue:
    """Tests for set_dict_value function"""
    
    def test_simple_set(self):
        """Test setting simple value"""
        data = {}
        result = set_dict_value(data, "key", "value")
        assert result["key"] == "value"
    
    def test_nested_set(self):
        """Test setting nested value"""
        data = {}
        result = set_dict_value(data, "level1.level2.level3", "value")
        assert result["level1"]["level2"]["level3"] == "value"
    
    def test_update_existing(self):
        """Test updating existing value"""
        data = {"key": "old_value"}
        result = set_dict_value(data, "key", "new_value")
        assert result["key"] == "new_value"
    
    def test_create_nested_structure(self):
        """Test creating nested structure"""
        data = {"existing": "value"}
        result = set_dict_value(data, "new.nested.key", "value")
        assert result["existing"] == "value"
        assert result["new"]["nested"]["key"] == "value"


class TestUpdateDictValues:
    """Tests for update_dict_values function"""
    
    def test_single_update(self):
        """Test updating single value"""
        data = {"key1": "value1", "key2": "value2"}
        params = {"key1": "new_value1"}
        result = update_dict_values(data, params)
        assert result["key1"] == "new_value1"
        assert result["key2"] == "value2"
    
    def test_multiple_updates(self):
        """Test updating multiple values"""
        data = {"key1": "value1", "key2": "value2"}
        params = {"key1": "new_value1", "key2": "new_value2"}
        result = update_dict_values(data, params)
        assert result["key1"] == "new_value1"
        assert result["key2"] == "new_value2"
    
    def test_nested_updates(self):
        """Test updating nested values"""
        data = {"level1": {"level2": {"key": "old_value"}}}
        params = {"level1.level2.key": "new_value"}
        result = update_dict_values(data, params)
        assert result["level1"]["level2"]["key"] == "new_value"
    
    def test_add_new_keys(self):
        """Test adding new keys"""
        data = {"key1": "value1"}
        params = {"key2": "value2", "key3.nested": "value3"}
        result = update_dict_values(data, params)
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert result["key3"]["nested"] == "value3"


class TestGetDictValueDeepBranches:
    """Targeted coverage for branches that were historically skipped.

    The helper walks both ``dict`` and ``list`` containers. The
    list-with-as_array branches take a non-trivial amount of code
    that the basic tests don't reach — these guard them so the
    dot-path traversal remains trustworthy."""

    def test_list_of_dicts_with_as_array_at_top_level(self):
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = get_dict_value(data, "id", as_array=True)
        assert result == [1, 2, 3]

    def test_nested_path_into_list_of_dicts(self):
        # ``a.b.c`` traverses ``{"a": [{"b": [{"c": ...}]}]}``.
        data = {"a": [{"b": [{"c": "deep"}]}]}
        assert get_dict_value(data, "a.b.c") == "deep"

    def test_nested_path_into_list_of_dicts_as_array(self):
        # ``a.b.c`` with as_array=True walks each item in the
        # intermediate lists.
        data = {"a": [{"b": [{"c": 1}, {"c": 2}]}, {"b": [{"c": 3}]}]}
        result = get_dict_value(data, "a.b.c", as_array=True)
        assert result == [1, 2, 3]

    def test_list_index_zero_when_iterating(self):
        # First dict in a list with as_array=False returns the
        # matched value from item 0 only.
        data = [{"id": "first"}, {"id": "second"}]
        assert get_dict_value(data, "id") == "first"

    def test_missing_list_index_returns_none(self):
        # ``prefix[0] in adict[0].keys()`` is False → None.
        data = [{"name": "alice"}, {"age": 30}]
        assert get_dict_value(data, "id") is None

    def test_missing_top_level_dict_key_returns_none(self):
        # The ``prefix[0] not in adict.keys()`` branch.
        assert get_dict_value({"a": 1}, "z") is None

    def test_path_through_non_dict_returns_none(self):
        # ``{"a": 5}`` then ``a.b`` — string path not found.
        assert get_dict_value({"a": 5}, "a.b") is None

    def test_path_through_list_at_root_with_missing_key(self):
        # ``[{"a": 1}]`` then key ``"z"`` — None.
        assert get_dict_value([{"a": 1}], "z") is None

    def test_path_through_list_as_array_with_partial_match(self):
        # ``as_array=True`` skips dicts that don't have the prefix.
        data = [{"x": 1}, {"x": 2, "y": 100}, {"y": 200}]
        result = get_dict_value(data, "y", as_array=True)
        assert result == [100, 200]

    def test_path_with_dotted_key_keeps_falsy_values(self):
        # The comment at lines 78-80 warns about dropping falsy
        # values. This pins that the helper preserves them.
        data = {"count": 0, "enabled": False, "label": "", "items": []}
        assert get_dict_value(data, "count") == 0
        assert get_dict_value(data, "enabled") is False
        assert get_dict_value(data, "label") == ""
        assert get_dict_value(data, "items") == []

