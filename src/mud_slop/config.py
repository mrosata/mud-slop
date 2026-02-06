"""Configuration system with minimal YAML parser.

Supports loading configuration from YAML files in the configs/ directory.
Uses a minimal YAML parser (no external dependencies) supporting:
- Scalars (strings, numbers, booleans)
- Lists (- item syntax)
- Nested dictionaries (key: value syntax)
- Comments (# ...)
- Quoted strings (single and double)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


# --- Minimal YAML Parser ---

def parse_simple_yaml(text: str) -> dict:
    """Parse a simple YAML document into a Python dict.

    Supports:
    - Scalars: strings, integers, floats, booleans, null
    - Lists: using '- item' syntax
    - Nested dicts: using 'key:' with indented children
    - Comments: lines starting with # (or inline # comments)
    - Quoted strings: 'single' or "double" quoted
    """
    lines = text.split('\n')
    return _parse_block(lines, 0, 0)[0]


def _parse_block(lines: list[str], start: int, base_indent: int) -> tuple[dict | list, int]:
    """Parse a block of YAML starting at line `start` with `base_indent`."""
    result: dict | list = {}
    i = start
    is_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # Calculate indent
        indent = len(line) - len(stripped)

        # If we've dedented past base, we're done with this block
        if indent < base_indent:
            break

        # If we're at a lower indent level than expected, break
        if indent < base_indent:
            break

        # List item
        if stripped.startswith('- '):
            if not is_list:
                is_list = True
                result = []

            item_content = stripped[2:].strip()
            # Calculate where the content starts for this list item
            # This is indent + 2 (for "- ")
            item_content_indent = indent + 2

            # Check for inline dict (- key: value)
            if ':' in item_content and not _is_quoted_string(item_content):
                # This is an inline dict item
                colon_pos = _find_unquoted_colon(item_content)
                if colon_pos > 0:
                    key = item_content[:colon_pos].strip()
                    value_part = item_content[colon_pos + 1:].strip()

                    # Build a dict starting with this key
                    item_dict = {}
                    item_dict[key] = _parse_value(value_part) if value_part else None
                    i += 1

                    # Check if there are more lines at the same or greater indent
                    # that are additional keys for this dict item
                    while i < len(lines):
                        next_line = lines[i]
                        next_stripped = next_line.lstrip()
                        if not next_stripped or next_stripped.startswith('#'):
                            i += 1
                            continue
                        next_indent = len(next_line) - len(next_stripped)

                        # If dedented below item_content_indent, we're done with this item
                        if next_indent < item_content_indent:
                            break

                        # If this is another list item at same level, we're done
                        if next_indent == indent and next_stripped.startswith('- '):
                            break

                        # If this is a key-value pair at item level, add to dict
                        next_colon = _find_unquoted_colon(next_stripped)
                        if next_colon > 0:
                            next_key = next_stripped[:next_colon].strip()
                            next_value = next_stripped[next_colon + 1:].strip()
                            next_value = _remove_inline_comment(next_value)
                            item_dict[next_key] = _parse_value(next_value) if next_value else None
                            i += 1
                        else:
                            break

                    result.append(item_dict)
                    continue

            # Simple list item (scalar value)
            result.append(_parse_value(item_content))
            i += 1
            continue

        # Key-value pair
        colon_pos = _find_unquoted_colon(stripped)
        if colon_pos > 0:
            key = stripped[:colon_pos].strip()
            value_part = stripped[colon_pos + 1:].strip()

            # Remove inline comments
            value_part = _remove_inline_comment(value_part)

            if value_part:
                # Inline value
                result[key] = _parse_value(value_part)
                i += 1
            else:
                # Check for nested block - skip comments and empty lines to find actual content
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    next_stripped = next_line.lstrip()
                    if not next_stripped or next_stripped.startswith('#'):
                        j += 1
                        continue
                    break

                if j < len(lines):
                    next_line = lines[j]
                    next_stripped = next_line.lstrip()
                    next_indent = len(next_line) - len(next_stripped)

                    if next_indent > indent:
                        # Parse nested block
                        nested, i = _parse_block(lines, j, next_indent)
                        result[key] = nested
                        continue

                # No nested content
                result[key] = None
                i += 1
        else:
            i += 1

    return result, i


def _find_unquoted_colon(s: str) -> int:
    """Find the position of the first colon not inside quotes."""
    in_single = False
    in_double = False
    for i, c in enumerate(s):
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == ':' and not in_single and not in_double:
            return i
    return -1


def _is_quoted_string(s: str) -> bool:
    """Check if a string is quoted."""
    s = s.strip()
    return (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))


def _remove_inline_comment(s: str) -> str:
    """Remove inline comments from a value string."""
    # Only remove comments that have a space before #
    in_single = False
    in_double = False
    for i, c in enumerate(s):
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == '#' and not in_single and not in_double and i > 0 and s[i-1] == ' ':
            return s[:i].rstrip()
    return s


def _parse_value(s: str) -> str | int | float | bool | None:
    """Parse a scalar YAML value."""
    s = s.strip()

    # Empty
    if not s:
        return None

    # Null
    if s.lower() in ('null', '~', 'none'):
        return None

    # Boolean
    if s.lower() in ('true', 'yes', 'on'):
        return True
    if s.lower() in ('false', 'no', 'off'):
        return False

    # Quoted string
    if len(s) >= 2:
        if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
            return s[1:-1]

    # Number
    try:
        if '.' in s:
            return float(s)
        return int(s)
    except ValueError:
        pass

    # Plain string
    return s


# --- Configuration Dataclasses ---

@dataclass
class ConnectionConfig:
    """Connection settings."""
    host: str | None = None
    port: int | None = None


@dataclass
class GMCPConfig:
    """GMCP protocol configuration."""
    subscriptions: list[str] = field(default_factory=lambda: [
        "char 1", "char.vitals 1", "char.stats 1", "char.status 1", "char.maxstats 1"
    ])
    # Mapping paths for vitals display
    vitals: dict[str, str] = field(default_factory=lambda: {
        "hp": "vitals.hp",
        "max_hp": "maxstats.maxhp",
        "mana": "vitals.mana",
        "max_mana": "maxstats.maxmana",
        "moves": "vitals.moves",
        "max_moves": "maxstats.maxmoves",
    })
    status: dict[str, str] = field(default_factory=lambda: {
        "level": "status.level",
        "tnl": "status.tnl",
        "position": "status.position",
        "enemy": "status.enemy",
    })
    attributes: list[str] = field(default_factory=lambda: [
        "str", "int", "wis", "dex", "con", "luck"
    ])


@dataclass
class MapPatterns:
    """Map detection pattern configuration."""
    start_tag: str = r'<MAPSTART>'
    end_tag: str = r'<MAPEND>'
    rdesc_start: str = r'\{rdesc\}'
    rdesc_end: str = r'\{/rdesc\}'
    coords: str = r'\{coords\}(\S+)'
    exits: str = r'^\s*\[?\s*Exits:\s*.*\]?\s*$'


@dataclass
class InfoPatterns:
    """Info ticker pattern configuration."""
    prefix: str = r'^INFO:\s+'


@dataclass
class HelpPatterns:
    """Help pager pattern configuration."""
    start_tag: str = r'\{help\}'
    end_tag: str = r'\{/help\}'
    body_start: str = r'\{helpbody\}'
    body_end: str = r'\{/helpbody\}'
    tags: str = r'\{helptags\}(.*)$'


@dataclass
class ConversationPattern:
    """Single conversation pattern definition."""
    pattern: str
    label: str


@dataclass
class ConversationPatterns:
    """Conversation detection patterns."""
    patterns: list[ConversationPattern] = field(default_factory=lambda: [
        ConversationPattern(
            pattern=r"^(?P<speaker>[\w'-]+)\s+says?,?\s+(?P<quote>['\"])(?P<message>.+)",
            label="says"
        ),
        ConversationPattern(
            pattern=r"^(?P<speaker>[\w'-]+)\s+tells?\s+you,?\s+(?P<quote>['\"])(?P<message>.+)",
            label="tells"
        ),
        ConversationPattern(
            pattern=r"^(?P<speaker>[\w'-]+)\s+whispers?,?\s+(?P<quote>['\"])(?P<message>.+)",
            label="whispers"
        ),
        ConversationPattern(
            pattern=r"^(?P<speaker>[\w'-]+)\s+(?:yells?|shouts?),?\s+(?P<quote>['\"])(?P<message>.+)",
            label="yells"
        ),
        ConversationPattern(
            pattern=r"^(?P<speaker>[\w'-]+)\s+(?:asks?|exclaims?|questions?),?\s+(?P<quote>['\"])(?P<message>.+)",
            label="asks"
        ),
    ])


@dataclass
class PatternsConfig:
    """All pattern configurations."""
    map: MapPatterns = field(default_factory=MapPatterns)
    info: InfoPatterns = field(default_factory=InfoPatterns)
    help: HelpPatterns = field(default_factory=HelpPatterns)
    conversation: ConversationPatterns = field(default_factory=ConversationPatterns)


@dataclass
class ConversationTimers:
    """Conversation overlay timing."""
    auto_close: float = 8.0


@dataclass
class InfoTimers:
    """Info ticker timing."""
    min_display: float = 10.0
    auto_hide: float = 40.0
    max_history: int = 200


@dataclass
class TimersConfig:
    """Timer configurations."""
    conversation: ConversationTimers = field(default_factory=ConversationTimers)
    info: InfoTimers = field(default_factory=InfoTimers)


@dataclass
class UIConfig:
    """UI layout configuration."""
    right_panel_max_width: int = 70
    right_panel_ratio: float = 0.40
    max_output_lines: int = 5000


@dataclass
class HooksConfig:
    """Command hooks for various events."""
    post_login: list[str] = field(default_factory=lambda: ["map", "look"])
    on_exit: list[str] = field(default_factory=list)


@dataclass
class ProfileConfig:
    """Login profile for auto-login."""
    username: str | None = None
    password: str | None = None


@dataclass
class Config:
    """Complete application configuration."""
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    gmcp: GMCPConfig = field(default_factory=GMCPConfig)
    patterns: PatternsConfig = field(default_factory=PatternsConfig)
    timers: TimersConfig = field(default_factory=TimersConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    hooks: HooksConfig = field(default_factory=HooksConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)


# --- Config Loading ---

def _find_configs_dir() -> Path:
    """Find the configs directory relative to the package or CWD."""
    # Try package directory first
    pkg_dir = Path(__file__).parent.parent.parent  # src/mud_slop -> project root
    configs_in_pkg = pkg_dir / "configs"
    if configs_in_pkg.is_dir():
        return configs_in_pkg

    # Try current working directory
    cwd_configs = Path.cwd() / "configs"
    if cwd_configs.is_dir():
        return cwd_configs

    # Return package location even if it doesn't exist (for error messages)
    return configs_in_pkg


def load_config(config_name: str | None = None) -> Config:
    """Load configuration from a YAML file.

    Args:
        config_name: Name of config file (without .yml extension).
                    If None or empty, uses 'default'.

    Returns:
        Config object with loaded values merged over defaults.
    """
    if not config_name:
        config_name = "default"

    configs_dir = _find_configs_dir()
    config_path = configs_dir / f"{config_name}.yml"

    # Start with defaults
    config = Config()

    # If config file exists, load and merge
    if config_path.is_file():
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_data = parse_simple_yaml(f.read())
        _merge_config(config, yaml_data)

    return config


def _merge_config(config: Config, data: dict):
    """Merge parsed YAML data into a Config object."""
    if not isinstance(data, dict):
        return

    # Connection
    if 'connection' in data and isinstance(data['connection'], dict):
        conn = data['connection']
        if 'host' in conn:
            config.connection.host = conn['host']
        if 'port' in conn:
            config.connection.port = int(conn['port']) if conn['port'] is not None else None

    # GMCP
    if 'gmcp' in data and isinstance(data['gmcp'], dict):
        gmcp = data['gmcp']
        if 'subscriptions' in gmcp and isinstance(gmcp['subscriptions'], list):
            config.gmcp.subscriptions = gmcp['subscriptions']
        if 'vitals' in gmcp and isinstance(gmcp['vitals'], dict):
            config.gmcp.vitals = gmcp['vitals']
        if 'status' in gmcp and isinstance(gmcp['status'], dict):
            config.gmcp.status = gmcp['status']
        if 'attributes' in gmcp and isinstance(gmcp['attributes'], list):
            config.gmcp.attributes = gmcp['attributes']

    # Patterns
    if 'patterns' in data and isinstance(data['patterns'], dict):
        pats = data['patterns']

        # Map patterns
        if 'map' in pats and isinstance(pats['map'], dict):
            mp = pats['map']
            if 'start_tag' in mp:
                config.patterns.map.start_tag = mp['start_tag']
            if 'end_tag' in mp:
                config.patterns.map.end_tag = mp['end_tag']
            if 'rdesc_start' in mp:
                config.patterns.map.rdesc_start = mp['rdesc_start']
            if 'rdesc_end' in mp:
                config.patterns.map.rdesc_end = mp['rdesc_end']
            if 'coords' in mp:
                config.patterns.map.coords = mp['coords']
            if 'exits' in mp:
                config.patterns.map.exits = mp['exits']

        # Info patterns
        if 'info' in pats and isinstance(pats['info'], dict):
            ip = pats['info']
            if 'prefix' in ip:
                config.patterns.info.prefix = ip['prefix']

        # Help patterns
        if 'help' in pats and isinstance(pats['help'], dict):
            hp = pats['help']
            if 'start_tag' in hp:
                config.patterns.help.start_tag = hp['start_tag']
            if 'end_tag' in hp:
                config.patterns.help.end_tag = hp['end_tag']
            if 'body_start' in hp:
                config.patterns.help.body_start = hp['body_start']
            if 'body_end' in hp:
                config.patterns.help.body_end = hp['body_end']
            if 'tags' in hp:
                config.patterns.help.tags = hp['tags']

        # Conversation patterns
        if 'conversation' in pats and isinstance(pats['conversation'], list):
            conv_patterns = []
            for item in pats['conversation']:
                if isinstance(item, dict) and 'pattern' in item and 'label' in item:
                    conv_patterns.append(ConversationPattern(
                        pattern=item['pattern'],
                        label=item['label']
                    ))
            if conv_patterns:
                config.patterns.conversation.patterns = conv_patterns

    # Timers
    if 'timers' in data and isinstance(data['timers'], dict):
        timers = data['timers']

        if 'conversation' in timers and isinstance(timers['conversation'], dict):
            ct = timers['conversation']
            if 'auto_close' in ct:
                config.timers.conversation.auto_close = float(ct['auto_close'])

        if 'info' in timers and isinstance(timers['info'], dict):
            it = timers['info']
            if 'min_display' in it:
                config.timers.info.min_display = float(it['min_display'])
            if 'auto_hide' in it:
                config.timers.info.auto_hide = float(it['auto_hide'])
            if 'max_history' in it:
                config.timers.info.max_history = int(it['max_history'])

    # UI
    if 'ui' in data and isinstance(data['ui'], dict):
        ui = data['ui']
        if 'right_panel_max_width' in ui:
            config.ui.right_panel_max_width = int(ui['right_panel_max_width'])
        if 'right_panel_ratio' in ui:
            config.ui.right_panel_ratio = float(ui['right_panel_ratio'])
        if 'max_output_lines' in ui:
            config.ui.max_output_lines = int(ui['max_output_lines'])

    # Hooks
    if 'hooks' in data and isinstance(data['hooks'], dict):
        hooks = data['hooks']
        if 'post_login' in hooks and isinstance(hooks['post_login'], list):
            config.hooks.post_login = [str(cmd) for cmd in hooks['post_login']]
        if 'on_exit' in hooks and isinstance(hooks['on_exit'], list):
            config.hooks.on_exit = [str(cmd) for cmd in hooks['on_exit']]


def _find_profiles_dir() -> Path:
    """Find the profiles directory relative to the package or CWD."""
    pkg_dir = Path(__file__).parent.parent.parent
    profiles_in_pkg = pkg_dir / "profiles"
    if profiles_in_pkg.is_dir():
        return profiles_in_pkg

    cwd_profiles = Path.cwd() / "profiles"
    if cwd_profiles.is_dir():
        return cwd_profiles

    return profiles_in_pkg


def load_profile(profile_name: str) -> ProfileConfig:
    """Load a login profile from a YAML file in the profiles/ directory.

    Args:
        profile_name: Name of profile file (without .yml extension).

    Returns:
        ProfileConfig with username and password.

    Raises:
        FileNotFoundError: If the profile file does not exist.
    """
    profiles_dir = _find_profiles_dir()
    profile_path = profiles_dir / f"{profile_name}.yml"

    if not profile_path.is_file():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with open(profile_path, 'r', encoding='utf-8') as f:
        data = parse_simple_yaml(f.read())

    profile = ProfileConfig()
    if isinstance(data, dict):
        if 'username' in data:
            profile.username = str(data['username'])
        if 'password' in data:
            profile.password = str(data['password'])
    return profile


def create_profile(profile_name: str) -> Path:
    """Interactively create a login profile.

    Prompts for username and password (password hidden) and writes
    a YAML file to the profiles/ directory.

    Returns:
        Path to the created profile file.
    """
    import getpass

    profiles_dir = _find_profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{profile_name}.yml"

    if profile_path.exists():
        resp = input(f"Profile '{profile_name}' already exists. Overwrite? [y/N] ")
        if resp.strip().lower() != 'y':
            raise SystemExit("Aborted.")

    username = input("Username: ").strip()
    if not username:
        raise SystemExit("Username cannot be empty.")

    password = getpass.getpass("Password: ")

    lines = [f"# Login profile: {profile_name}\n"]
    lines.append(f"username: {username}\n")
    lines.append(f"password: {password}\n")

    with open(profile_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return profile_path


def get_default_config() -> Config:
    """Return a Config with all default values."""
    return Config()
