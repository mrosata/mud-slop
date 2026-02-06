"""Tests for configuration loading and YAML parsing."""

import pytest

from mud_client.config import (
    parse_simple_yaml,
    load_config,
    get_default_config,
    Config,
)


class TestParseSimpleYaml:
    """Tests for the minimal YAML parser."""

    def test_empty_document(self):
        result = parse_simple_yaml("")
        assert result == {}

    def test_simple_key_value(self):
        result = parse_simple_yaml("key: value")
        assert result == {"key": "value"}

    def test_integer_value(self):
        result = parse_simple_yaml("port: 4000")
        assert result == {"port": 4000}

    def test_float_value(self):
        result = parse_simple_yaml("ratio: 0.40")
        assert result == {"ratio": 0.40}

    def test_boolean_true(self):
        result = parse_simple_yaml("enabled: true")
        assert result == {"enabled": True}

    def test_boolean_false(self):
        result = parse_simple_yaml("enabled: false")
        assert result == {"enabled": False}

    def test_null_value(self):
        result = parse_simple_yaml("host: null")
        assert result == {"host": None}

    def test_quoted_string_double(self):
        result = parse_simple_yaml('message: "hello world"')
        assert result == {"message": "hello world"}

    def test_quoted_string_single(self):
        result = parse_simple_yaml("message: 'hello world'")
        assert result == {"message": "hello world"}

    def test_comments_ignored(self):
        yaml = """
# This is a comment
key: value  # inline comment
# Another comment
other: data
"""
        result = parse_simple_yaml(yaml)
        assert result == {"key": "value", "other": "data"}

    def test_nested_dict(self):
        yaml = """
connection:
  host: localhost
  port: 4000
"""
        result = parse_simple_yaml(yaml)
        assert result == {
            "connection": {
                "host": "localhost",
                "port": 4000
            }
        }

    def test_simple_list(self):
        yaml = """
items:
  - one
  - two
  - three
"""
        result = parse_simple_yaml(yaml)
        assert result == {"items": ["one", "two", "three"]}

    def test_list_of_dicts(self):
        yaml = """
patterns:
  - pattern: "^test$"
    label: test
  - pattern: "^other$"
    label: other
"""
        result = parse_simple_yaml(yaml)
        assert result == {
            "patterns": [
                {"pattern": "^test$", "label": "test"},
                {"pattern": "^other$", "label": "other"}
            ]
        }

    def test_deeply_nested(self):
        yaml = """
level1:
  level2:
    level3:
      value: deep
"""
        result = parse_simple_yaml(yaml)
        assert result == {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }

    def test_special_characters_in_value(self):
        yaml = r"""
pattern: '^\s*\[?\s*Exits:\s*.*\]?\s*$'
"""
        result = parse_simple_yaml(yaml)
        assert result["pattern"] == r'^\s*\[?\s*Exits:\s*.*\]?\s*$'

    def test_comments_before_nested_content(self):
        """Comments between key and nested content should be skipped."""
        yaml = """
hooks:
  # This is a comment
  post_login:
    - map
    - look
"""
        result = parse_simple_yaml(yaml)
        assert result == {
            "hooks": {
                "post_login": ["map", "look"]
            }
        }


class TestLoadConfig:
    """Tests for config loading."""

    def test_default_config_has_all_sections(self):
        config = get_default_config()
        assert config.connection is not None
        assert config.gmcp is not None
        assert config.patterns is not None
        assert config.timers is not None
        assert config.ui is not None

    def test_default_gmcp_subscriptions(self):
        config = get_default_config()
        assert "char 1" in config.gmcp.subscriptions
        assert "char.vitals 1" in config.gmcp.subscriptions

    def test_default_patterns(self):
        config = get_default_config()
        assert config.patterns.map.start_tag == r'<MAPSTART>'
        assert config.patterns.info.prefix == r'^INFO:\s+'

    def test_default_timers(self):
        config = get_default_config()
        assert config.timers.conversation.auto_close == 8.0
        assert config.timers.info.min_display == 10.0

    def test_default_ui_settings(self):
        config = get_default_config()
        assert config.ui.right_panel_max_width == 70
        assert config.ui.right_panel_ratio == 0.40
        assert config.ui.max_output_lines == 5000


class TestConfigMerging:
    """Tests for merging config values."""

    def test_connection_values_mergeable(self):
        # Test that we can override connection values
        config = get_default_config()
        assert config.connection.host is None
        assert config.connection.port is None

        # These would be set by CLI or config file
        config.connection.host = "test.host"
        config.connection.port = 1234
        assert config.connection.host == "test.host"
        assert config.connection.port == 1234


class TestHooksConfig:
    """Tests for hooks configuration."""

    def test_default_post_login_hooks(self):
        config = get_default_config()
        assert config.hooks.post_login == ["map", "look"]

    def test_default_on_exit_hooks_empty(self):
        config = get_default_config()
        assert config.hooks.on_exit == []

    def test_hooks_from_yaml(self):
        yaml = """
hooks:
  post_login:
    - config mapshow on
    - map
    - look
  on_exit:
    - quit
"""
        from mud_client.config import _merge_config
        config = get_default_config()
        data = parse_simple_yaml(yaml)
        _merge_config(config, data)

        assert config.hooks.post_login == ["config mapshow on", "map", "look"]
        assert config.hooks.on_exit == ["quit"]
