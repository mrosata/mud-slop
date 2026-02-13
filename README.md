# mud-slop

![image](./assets/logo.png)

A terminal-based MUD (Multi-User Dungeon) client with GMCP support, ANSI color rendering, and protocol inspection. Built entirely with the Python standard library.

## Features

- **ANSI color rendering** — full support for 8 foreground/background colors, bright variants, bold, underline, and reverse
- **GMCP support** — negotiates with Aardwolf-style servers and displays HP/Mana/Moves bars and character attributes in a stats pane
- **Conversation overlay** — speech lines (says, tells, whispers, yells, asks) are captured and shown in a navigable overlay panel
- **Info ticker** — `INFO:` channel messages display in a ticker bar above the input line
- **Map pane** — ASCII maps, room descriptions are extracted using configurable pattern matching (ie: `<MAPSTART>/<MAPEND>` or `{rdesc}{/rdesc}` tags), and rendered in a fixed panel on the right side of the screen showing room name, coords, map, exits, and word-wrapped description
- **Help pager** — help content wrapped in `{help}`/`{/help}` tags, _(unless configured otherwise)_, is displayed in a scrollable overlay with paging controls (PgUp/PgDn/Home/End/ESC), allowing users to read help while still typing commands
- **Debug logging** — writes output, protocol, and GMCP streams to log files
- **Scrollback** — Page Up/Down to scroll through history; configurable content visibility when scrolled up (conversations shown by default, help/maps/info hidden; toggle with `/history`)
- **Command history** — Up/Down arrows with prefix filtering
- **Line editing** — Left/Right arrows, Ctrl+A/E (home/end), Ctrl+Left/Right (word jump), Ctrl+W/U/K (kill word/to-start/to-end), Delete key
- **Auto-login profiles** — store credentials in YAML profile files (`~/.mud-slop/profiles/<name>.yml`, `./profiles/<name>.yml`) and use `-p <name>` to log in automatically.
- **Menu bar** — mouse and keyboard (Alt+F, Alt+S) access to File and Settings menus. Switch configs and profiles at runtime, toggle color/debug/history settings, and change conversation overlay position — all without restarting the client.

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### From PyPI (recommended)

```bash
pip install mud-slop
# Check install
mud-slop --version
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install mud-slop
# Check install
mud-slop --version
```

### From source

```bash
git clone <repo-url> && cd mud-slop
uv sync
# Check install
uv run mud-slop --version
```

## Usage

**Using a config**
Currently we only support `aardwolf` as a config
```bash
# mud-slop <host> <port>
mud-slop <host> <port>
# mud-slop -c <profile>
mud-slop -c aardwolf
```

**Using host and port explicitly**
```bash
# mud-slop <host> <port>
mud-slop 23.111.142.226 4000
```

### Options

| Flag | Description |
|---|---|
| `-c`, `--config` | Configuration name or path (see [Configuration](#configuration)) |
| `-p`, `--profile` | Login profile name or path (see [Profiles](#profiles)) |
| `--create-profile NAME` | Create a login profile interactively (saves to `~/.mud-slop/profiles/`) |
| `--no-color` | Disable ANSI color rendering |
| `-d`, `--debug` | Enable debug logging to `mud_*.log` files |
| `--conv-pos {top-left\|top-center\|...\|bottom-right}` | Conversation overlay position (default: `bottom-right`) |

### Examples

```bash
# Connect to Aardwolf using config file
uv run mud-slop -c aardwolf

# Connect with explicit host/port (overrides config)
uv run mud-slop aardmud.org 4000

# With debug logging enabled
uv run mud-slop -c aardwolf --debug

# Create a login profile (prompts for username/password)
uv run mud-slop --create-profile mychar

# Auto-login with a profile
uv run mud-slop -c aardwolf -p mychar

# Override host/port from config
uv run mud-slop -c aardwolf localhost 5000
```

### Configuration

Configuration files are YAML files loaded via `-c <name>` or `-c <path>`. CLI arguments override config values.

**Search order for config names:**
1. `~/.mud-slop/configs/<name>.yml` (user configs)
2. `./configs/<name>.yml` (current directory)
3. Package `configs/` directory (bundled configs)

You can also pass a full path: `-c ~/my-configs/custom.yml`

Example config structure (`configs/aardwolf.yml`):

```yaml
connection:
  host: aardmud.org
  port: 4000

gmcp:
  subscriptions:
    - "char 1"
    - "char.vitals 1"
    - "char.stats 1"

patterns:
  map:
    start_tag: '<MAPSTART>'
    end_tag: '<MAPEND>'
  info:
    prefix: '^INFO:\s+'

timers:
  conversation:
    auto_close: 8.0

ui:
  right_panel_max_width: 70
  max_output_lines: 5000
  history:
    conversations: true
    help: false

hooks:
  # Commands to run after login (when GMCP vitals first arrive)
  post_login:
    - map
    - look
  # Commands to run before disconnecting
  on_exit:
    - quit
```

See `configs/default.yml` for the complete schema with all options.

### Profiles

Login profiles store credentials for auto-login. Profile files are **gitignored** to prevent committing secrets.

**Search order for profile names:**
1. `~/.mud-slop/profiles/<name>.yml` (user profiles)
2. `./profiles/<name>.yml` (current directory)
3. Package `profiles/` directory

You can also pass a full path: `-p ~/my-profiles/mychar.yml`

Create a profile interactively (password input is hidden, saves to `~/.mud-slop/profiles/`):

```bash
mud-slop --create-profile mychar
```

Then use it to auto-login:

```bash
mud-slop -c aardwolf -p mychar
```

The client sends the username after the server's initial prompt and sends the password when the server enters password mode (telnet WILL ECHO). See `profiles/README.md` for details.

### In-app commands

| Command | Action |
|---|---|
| `/quit` | Exit the client |
| `/clear` | Clear output pane (and conversation, map, ticker) |
| `/debug` | Toggle debug logging on/off at runtime |
| `/info` | Show timestamped info message history |
| `/history` | Show history visibility settings |
| `/history <type> [on\|off]` | Toggle what shows when scrolled up (types: conversations, help, maps, info) |

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
| Page Up / Page Down | Scroll output by page (or help pager when open) |
| Mouse scroll | Scroll output by 3 lines (or help pager when open) |
| Home / End | Jump to top/bottom of scrollback (or help pager when open) |
| Shift+Right / Shift+Left | Navigate conversation entries |
| Escape | Dismiss conversation overlay or help pager |
| W / A / S / D | Move north/west/south/east (only when input is empty, after login) |
| Alt+F | Open File menu |
| Alt+S | Open Settings menu |
| F1 | Toggle help overlay |
| Ctrl+C | Quit |

### UI layout

The UI has a menu bar at the top and up to five regions below:

- **Menu bar** — File and Settings menus accessible via mouse click or Alt+F/Alt+S. Settings menu allows runtime config/profile switching, color/debug toggling, conversation position, and history visibility.
- **Output pane** — main MUD text (filtered: speech, info, and map lines removed at scroll position 0)
- **Stats pane** — GMCP vitals/status/attributes (appears automatically when GMCP data arrives, 24-char column on the right)
- **Map pane** — fixed panel on the right side (below stats if both present) showing room name, coordinates, ASCII map, exits, and word-wrapped description (appears after login when map data is received)
- **Help pager** — scrollable overlay on the right side showing help content (appears when server sends `{help}` tags, covers stats/map panes)
- **Info ticker** — single-row bar above the input line showing `INFO:` channel messages
- **Input line** — command entry with `> ` prompt

The conversation overlay draws on top of the output pane. The map pane is a fixed panel on the right side of the screen (below the stats pane if both are present), and is hidden while the conversation overlay is visible. Scrolling up reveals history with configurable content visibility — by default only conversation lines are included. Use `/history` to toggle what appears (conversations, help, maps, info).

Debug logging (`-d` or `/debug`) writes to `mud_output.log`, `mud_proto.log`, and `mud_gmcp.log` in the current directory.

## Development

```bash
# Install in dev mode
uv sync

# Run via entry point
uv run mud-slop <host> <port>

# Run via python -m
uv run python -m mud_slop <host> <port>
```

The project has zero runtime dependencies. See `CLAUDE.md` for detailed architecture notes and the module dependency graph.

```bash
# Run tests
uv run python -m pytest tests/ -v
```

### Releasing

Releases are fully automated via [Release Please](https://github.com/googleapis/release-please) and GitHub Actions. The process is:

1. **Use [Conventional Commits](https://www.conventionalcommits.org/)** in your commit messages:
   - `fix: <description>` — triggers a **patch** bump (e.g. 0.1.2 → 0.1.3)
   - `feat: <description>` — triggers a **minor** bump (e.g. 0.1.3 → 0.2.0)
   - `feat!: <description>` or a `BREAKING CHANGE:` footer — triggers a **minor** bump while pre-1.0

   Commits that don't follow this format (e.g. `chore:`, `docs:`, or no prefix) are ignored by Release Please and won't trigger a release.

2. **Merge to `main`** — on every push to `main`, Release Please analyzes new commits and opens (or updates) a release PR with a version bump and generated changelog.

3. **Merge the release PR** — this triggers the publish pipeline:
   - Builds the package with `python -m build`
   - Publishes to [PyPI](https://pypi.org/p/mud-slop) via trusted publishing
   - Uploads dist artifacts to the GitHub Release

**Important:** When merging PRs via GitHub, use **"Squash and merge"** and ensure the squash commit message follows conventional commits format (e.g. `fix: profile not loading when installed from PyPI`). GitHub defaults to using the branch name, which Release Please can't parse.
