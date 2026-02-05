# mud-client

A terminal-based MUD (Multi-User Dungeon) client with GMCP support, ANSI color rendering, and protocol inspection. Built entirely with the Python standard library.

## Features

- **ANSI color rendering** — full support for 8 foreground/background colors, bright variants, bold, underline, and reverse
- **GMCP support** — negotiates with Aardwolf-style servers and displays HP/Mana/Moves bars and character attributes in a stats pane
- **Conversation overlay** — speech lines (says, tells, whispers, yells, asks) are captured and shown in a navigable overlay panel
- **Info ticker** — `INFO:` channel messages display in a ticker bar above the input line
- **Map pane** — ASCII maps are extracted using `<MAPSTART>`/`<MAPEND>` tags, room descriptions via `{rdesc}`/`{/rdesc}` tags, and rendered in a fixed panel on the right side of the screen showing room name, coords, map, exits, and word-wrapped description
- **Help pager** — help content wrapped in `{help}`/`{/help}` tags is displayed in a scrollable overlay with paging controls (PgUp/PgDn/Home/End/ESC), allowing users to read help while still typing commands
- **Debug logging** — writes output, protocol, and GMCP streams to log files
- **Scrollback** — Page Up/Down to scroll through history; full unfiltered history available when scrolled up
- **Command history** — Up/Down arrows with prefix filtering
- **Line editing** — Left/Right arrows, Ctrl+A/E (home/end), Ctrl+Left/Right (word jump), Ctrl+W/U/K (kill word/to-start/to-end), Delete key
- **Password masking** — input is hidden when the server signals password mode (via telnet WILL ECHO)

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
git clone <repo-url> && cd mud-client
uv sync
```

## Usage

```bash
uv run mud-client <host> <port>
```

### Options

| Flag | Description |
|---|---|
| `--no-color` | Disable ANSI color rendering |
| `-d`, `--debug` | Enable debug logging to `mud_*.log` files |
| `--conv-pos {top-left\|top-center\|...\|bottom-right}` | Conversation overlay position (default: `bottom-right`) |

### Example

```bash
# Connect to Aardwolf
uv run mud-client aardmud.org 4000

# With debug logging enabled
uv run mud-client aardmud.org 4000 --debug
```

### In-app commands

| Command | Action |
|---|---|
| `/quit` | Exit the client |
| `/clear` | Clear output pane (and conversation, map, ticker) |
| `/debug` | Toggle debug logging on/off at runtime |
| `/info` | Show timestamped info message history |

Everything else typed at the prompt is sent to the server.

### Keyboard shortcuts

| Key | Action |
|---|---|
| Enter | Send input |
| Left / Right | Move cursor within input line |
| Ctrl+A | Jump to start of input |
| Ctrl+E | Jump to end of input |
| Ctrl+Left / Ctrl+Right | Jump word left/right |
| Backspace | Delete character before cursor |
| Delete | Delete character at cursor |
| Ctrl+W | Delete word backwards |
| Ctrl+U | Delete to start of line |
| Ctrl+K | Delete to end of line |
| Up / Down | Navigate command history |
| Page Up / Page Down | Scroll output (or help pager when open) |
| Home / End | Jump to top/bottom of scrollback (or help pager when open) |
| Shift+Right / Shift+Left | Navigate conversation entries |
| Escape | Dismiss conversation overlay or help pager |
| W / A / S / D | Move north/west/south/east (only when input is empty, after login) |
| F1 | Toggle help overlay |
| Ctrl+C | Quit |

### UI layout

The UI has up to five regions:

- **Output pane** — main MUD text (filtered: speech, info, and map lines removed at scroll position 0)
- **Stats pane** — GMCP vitals/status/attributes (appears automatically when GMCP data arrives, 24-char column on the right)
- **Map pane** — fixed panel on the right side (below stats if both present) showing room name, coordinates, ASCII map, exits, and word-wrapped description (appears after login when map data is received)
- **Help pager** — scrollable overlay on the right side showing help content (appears when server sends `{help}` tags, covers stats/map panes)
- **Info ticker** — single-row bar above the input line showing `INFO:` channel messages
- **Input line** — command entry with `> ` prompt

The conversation overlay draws on top of the output pane. The map pane is a fixed panel on the right side of the screen (below the stats pane if both are present), and is hidden while the conversation overlay is visible. Scrolling up reveals the full unfiltered history including speech, info, and map lines.

Debug logging (`-d` or `/debug`) writes to `mud_output.log`, `mud_proto.log`, and `mud_gmcp.log` in the current directory.

## Development

```bash
# Install in dev mode
uv sync

# Run via entry point
uv run mud-client <host> <port>

# Run via python -m
uv run python -m mud_client <host> <port>
```

The project has zero runtime dependencies. See `CLAUDE.md` for detailed architecture notes and the module dependency graph.

```bash
# Run tests
uv run python -m pytest tests/ -v
```
