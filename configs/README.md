# Configuration Guide

This directory contains YAML configuration files for different MUD servers. Use `-c <name>` to load `configs/<name>.yml`.

## Quick Start

```bash
# Use a config by name (loads configs/aardwolf.yml)
uv run mud-client -c aardwolf

# Override host/port from command line
uv run mud-client -c aardwolf localhost 4000
```

## Creating a Config for a New MUD

### Step 1: Start with the Default Config

Copy `default.yml` as a starting point:

```bash
cp configs/default.yml configs/mymud.yml
```

### Step 2: Set Connection Details

Edit the connection section:

```yaml
connection:
  host: mymud.example.com
  port: 4000
```

### Step 3: Enable Debug Mode

Connect with debug logging enabled to capture protocol data:

```bash
uv run mud-client -c mymud --debug
```

This creates three log files in the current directory:
- `mud_output.log` - Raw display text with ANSI codes preserved
- `mud_proto.log` - Telnet protocol events (negotiations, IAC sequences)
- `mud_gmcp.log` - GMCP messages as JSON

You can also toggle debug mode at runtime with `/debug`.

### Step 4: Analyze GMCP Packages

Check `mud_gmcp.log` to see what GMCP packages your MUD sends. Look for patterns like:

```
[12:34:56] char.vitals {"hp": 100, "maxhp": 100, "mana": 50, "maxmana": 50}
[12:34:56] char.status {"level": 10, "position": "Standing"}
[12:34:57] room.info {"name": "Town Square", "exits": {"n": 1234, "s": 1235}}
```

Update your config's GMCP subscriptions to match what the server supports:

```yaml
gmcp:
  subscriptions:
    - "char 1"
    - "char.vitals 1"
    - "room 1"
    # Add packages your MUD supports
```

### Step 5: Identify Map and Room Patterns

Many MUDs use different tags for maps and room descriptions. Search `mud_output.log` for:
- Map delimiters (e.g., `<MAPSTART>`, `[MAP]`, or ASCII borders)
- Room description tags (e.g., `{rdesc}`, `<DESC>`)
- Coordinate formats

Update the patterns section:

```yaml
patterns:
  map:
    start_tag: '<MAPSTART>'      # Regex for map start
    end_tag: '<MAPEND>'          # Regex for map end
    rdesc_start: '\{rdesc\}'     # Room description start
    rdesc_end: '\{/rdesc\}'      # Room description end
    coords: '\{coords\}(\S+)'    # Coordinate line pattern
    exits: '^\s*\[?\s*Exits:'    # Exits line pattern
```

**Note:** These are regular expressions. Escape special characters like `{`, `}`, `[`, `]` with backslashes.

### Step 6: Configure Info Channel

If your MUD has an info/news channel, find its prefix in `mud_output.log`:

```yaml
patterns:
  info:
    prefix: '^INFO:\s+'    # or '^NEWS:\s+' or '^\[Info\]\s+'
```

### Step 7: Configure Conversation Patterns

Speech patterns vary by MUD. Check `mud_output.log` for examples like:
- `Bob says, "Hello!"`
- `Bob tells you, "Hello!"`
- `[Bob]: Hello!`

Add custom patterns:

```yaml
patterns:
  conversation:
    - pattern: "^(?P<speaker>[\\w'-]+)\\s+says?,?\\s+(?P<quote>['\"])(?P<message>.+)"
      label: says
    - pattern: "^\\[(?P<speaker>[\\w'-]+)\\]:\\s+(?P<quote>)(?P<message>.+)"
      label: channel
```

**Pattern requirements:**
- Must have named groups: `speaker`, `quote`, `message`
- `quote` captures the opening quote character (can be empty for unquoted speech)
- `message` captures the speech content

### Step 8: Set Up Command Hooks

Configure commands to run automatically:

```yaml
hooks:
  # Commands after login (when GMCP vitals arrive)
  post_login:
    - config mapshow on     # Enable map display
    - brief off             # Full room descriptions
    - map                   # Show initial map
    - look                  # Look at current room

  # Commands before disconnect
  on_exit:
    - quit                  # Graceful logout
```

### Step 9: Adjust Timers (Optional)

Fine-tune UI behavior:

```yaml
timers:
  conversation:
    auto_close: 8.0       # Seconds before auto-closing speech overlay

  info:
    min_display: 10.0     # Minimum seconds to show each info message
    auto_hide: 40.0       # Hide ticker after idle seconds
    max_history: 200      # Max info messages to keep
```

## Debug Process Checklist

1. **Connection issues?**
   - Check `mud_proto.log` for telnet negotiation
   - Look for `WILL`/`WONT`/`DO`/`DONT` sequences
   - Verify GMCP (option 201) is being negotiated

2. **GMCP not working?**
   - Check `mud_gmcp.log` for incoming packages
   - Verify subscription names match what the server expects
   - Some servers use different package names (e.g., `Char.Vitals` vs `char.vitals`)

3. **Map not displaying?**
   - Search `mud_output.log` for map content
   - Identify the exact start/end markers
   - Test your regex patterns with Python:
     ```python
     import re
     pattern = re.compile(r'<MAPSTART>')
     print(pattern.search('<MAPSTART>'))  # Should match
     ```

4. **Speech not captured?**
   - Find speech examples in `mud_output.log`
   - Test patterns against actual output
   - Ensure named groups are correct

5. **Patterns not matching?**
   - Remember to escape regex special chars: `{ } [ ] ( ) . * + ? ^ $ |`
   - Use raw strings in YAML: `'pattern'` or `"pattern"`
   - Double backslashes in double-quoted strings: `"\\{rdesc\\}"`

## Config File Reference

```yaml
# Connection settings
connection:
  host: mymud.example.com
  port: 4000

# GMCP protocol settings
gmcp:
  subscriptions:
    - "char 1"
    - "char.vitals 1"
  vitals:
    hp: vitals.hp
    max_hp: vitals.maxhp
  status:
    level: status.level
  attributes:
    - str
    - int

# Pattern matching (all values are regex)
patterns:
  map:
    start_tag: '<MAPSTART>'
    end_tag: '<MAPEND>'
    rdesc_start: '\{rdesc\}'
    rdesc_end: '\{/rdesc\}'
    coords: '\{coords\}(\S+)'
    exits: '^\s*Exits:'
  info:
    prefix: '^INFO:\s+'
  help:
    start_tag: '\{help\}'
    end_tag: '\{/help\}'
    body_start: '\{helpbody\}'
    body_end: '\{/helpbody\}'
    tags: '\{helptags\}(.*)$'
  conversation:
    - pattern: "^(?P<speaker>[\\w'-]+)\\s+says?.*(?P<quote>['\"])(?P<message>.+)"
      label: says

# Timing settings
timers:
  conversation:
    auto_close: 8.0
  info:
    min_display: 10.0
    auto_hide: 40.0
    max_history: 200

# UI layout
ui:
  right_panel_max_width: 70
  right_panel_ratio: 0.40
  max_output_lines: 5000

# Command hooks
hooks:
  post_login:
    - map
    - look
  on_exit: []
```

## Tips

- Start with minimal changes and add features incrementally
- Keep debug logs from successful sessions for reference
- Test pattern changes with a small script before updating the config
- Some MUDs require specific login sequences - use `post_login` hooks for setup commands
