import re

from mud_client.ansi import strip_ansi


class MapTracker:
    """Detects and extracts ASCII map blocks using <MAPSTART>/<MAPEND> tags and room descriptions using {rdesc}/{/rdesc} tags."""

    # Matches the <MAPSTART> and <MAPEND> tags
    _MAPSTART_RE = re.compile(r'<MAPSTART>')
    _MAPEND_RE = re.compile(r'<MAPEND>')

    # Matches room description tags: {rdesc} and {/rdesc}
    _RDESC_START_RE = re.compile(r'\{rdesc\}')
    _RDESC_END_RE = re.compile(r'\{/rdesc\}')

    # Matches coords line: {coords}x,y,z
    _COORDS_RE = re.compile(r'\{coords\}(\S+)')

    # Matches exits line: [ Exits: ... ]
    _EXITS_RE = re.compile(r'^\s*\[?\s*Exits:\s*.*\]?\s*$', re.IGNORECASE)

    # Room name line after <MAPEND>: "Room Name" or "Room Name (G)" or "Room Name (123)" or "Room Name (G) (123)"
    # Starts with a letter, may have optional (X) markers at the end
    _ROOM_NAME_LINE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9\s\'\-,\.]+(?:\s*\([A-Za-z0-9]+\))*\s*$')

    # Map line detection: no runs of 2+ alpha chars
    _ALPHA_RUN = re.compile(r'[a-zA-Z]{2,}')

    def __init__(self):
        self.map_lines: list[str] = []       # current map (raw ANSI lines)
        self.room_name: str = ""             # plain text room name
        self.room_name_raw: str = ""         # raw ANSI room name line
        self.room_desc: list[str] = []       # description lines (raw ANSI)
        self.coords: str = ""                # coordinates string (e.g., "0,30,20")
        self.exits: str = ""                 # exits string (plain text)
        self.exits_raw: str = ""             # exits string (raw ANSI)

        self._in_map_block: bool = False     # between <MAPSTART> and <MAPEND>
        self._in_rdesc_block: bool = False   # between {rdesc} and {/rdesc}
        self._expect_room_name: bool = False # expecting room name line after <MAPEND>
        self._block_lines: list[tuple[str, str]] = []  # (plain, raw) accumulator
        self._rdesc_lines: list[str] = []    # description lines accumulator

        self.sent_initial: bool = False       # sent initial 'map' command
        self.enabled: bool = False            # only detect maps after login

    def _is_map_line(self, plain: str) -> bool:
        """No runs of 2+ alpha chars (used to identify map ASCII art)."""
        stripped = plain.strip()
        if not stripped:
            return False  # blank line is not a map line for this check
        return not bool(self._ALPHA_RUN.search(stripped))

    def feed_line(self, plain: str, raw: str) -> tuple[bool, list[str]]:
        """Process a line.
        Returns (consumed, overflow_raw_lines).
        consumed: True if this line is being held/consumed as map data.
        overflow: always empty (tag-based parsing doesn't produce overflow).
        """
        if not self.enabled:
            return False, []

        # Check for <MAPSTART> tag
        if self._MAPSTART_RE.search(plain):
            self._in_map_block = True
            self._expect_room_name = False
            self._block_lines = []
            return True, []  # consume the <MAPSTART> line itself

        # Check for <MAPEND> tag
        if self._MAPEND_RE.search(plain):
            if self._in_map_block:
                self._finalize_block()
            self._in_map_block = False
            self._expect_room_name = True  # expect room name line after <MAPEND>
            return True, []  # consume the <MAPEND> line itself

        # If we're inside a map block, accumulate lines
        if self._in_map_block:
            self._block_lines.append((plain, raw))
            return True, []

        # Check for {rdesc} tag (start of room description)
        if self._RDESC_START_RE.search(plain):
            self._in_rdesc_block = True
            self._expect_room_name = False
            self._rdesc_lines = []
            return True, []  # consume the {rdesc} line itself

        # Check for {/rdesc} tag (end of room description)
        if self._RDESC_END_RE.search(plain):
            if self._in_rdesc_block:
                self._finalize_rdesc()
            self._in_rdesc_block = False
            return True, []  # consume the {/rdesc} line itself

        # If we're inside a rdesc block, accumulate description lines
        if self._in_rdesc_block:
            self._rdesc_lines.append(raw)
            return True, []

        # Outside map block: check for {coords} line
        coords_match = self._COORDS_RE.search(plain)
        if coords_match:
            self.coords = coords_match.group(1)
            self._expect_room_name = False
            return True, []  # consume coords line

        # After <MAPEND>, expect a room name line (blank lines are skipped)
        if self._expect_room_name:
            stripped = plain.strip()
            if not stripped:
                return True, []  # consume blank lines while expecting room name
            # Check if this looks like a room name line
            if self._ROOM_NAME_LINE_RE.match(stripped):
                # Extract just the room name (strip the (G) and (123) parts)
                # Keep the name part before any parenthetical markers
                name_match = re.match(r'^([A-Za-z][A-Za-z0-9\s\'\-,\.]+?)(?:\s*\([A-Za-z0-9]+\))*\s*$', stripped)
                if name_match:
                    self.room_name = name_match.group(1).strip()
                    self.room_name_raw = raw
                self._expect_room_name = False
                return True, []  # consume room name line
            # Not a room name - stop expecting
            self._expect_room_name = False

        return False, []

    def _finalize_rdesc(self):
        """Process accumulated description lines.

        Detects whether the block is ASCII art or prose.  Art blocks
        (majority of non-blank lines lack 2+ consecutive alpha chars)
        are kept as individual lines to preserve spatial layout.  Prose
        blocks have consecutive non-empty lines joined into paragraphs,
        with empty lines acting as paragraph breaks.  Raw ANSI codes
        are preserved in both cases.
        """
        non_blank = [(raw, strip_ansi(raw).strip())
                     for raw in self._rdesc_lines
                     if strip_ansi(raw).strip()]
        if not non_blank:
            self.room_desc = []
            return

        # If most non-blank lines lack word-like content, it's ASCII art
        art_count = sum(1 for _, p in non_blank
                        if not self._ALPHA_RUN.search(p))
        if art_count > len(non_blank) // 2:
            # Keep lines separate to preserve art layout
            self.room_desc = list(self._rdesc_lines)
            return

        # Prose: join consecutive non-empty lines into paragraphs
        paragraphs: list[str] = []
        current_parts: list[str] = []
        for raw_line in self._rdesc_lines:
            plain = strip_ansi(raw_line).strip()
            if not plain:
                if current_parts:
                    paragraphs.append(' '.join(current_parts))
                    current_parts = []
            else:
                current_parts.append(raw_line)
        if current_parts:
            paragraphs.append(' '.join(current_parts))
        self.room_desc = paragraphs

    def _finalize_block(self):
        """Parse accumulated block lines into room name, map, and exits."""
        if not self._block_lines:
            return

        # Find first non-empty line as room name
        room_idx = -1
        for i, (plain, raw) in enumerate(self._block_lines):
            if plain.strip():
                self.room_name = plain.strip()
                self.room_name_raw = raw
                room_idx = i
                break

        if room_idx < 0:
            # No room name found
            return

        # Find exits line (usually near the end)
        exits_idx = -1
        for i in range(len(self._block_lines) - 1, room_idx, -1):
            plain, raw = self._block_lines[i]
            if self._EXITS_RE.match(plain):
                self.exits = plain.strip()
                self.exits_raw = raw
                exits_idx = i
                break

        # Lines between room name and exits (or end) are map lines
        end_idx = exits_idx if exits_idx > 0 else len(self._block_lines)
        middle_lines = self._block_lines[room_idx + 1:end_idx]

        # Collect map lines (ASCII art with no 2+ alpha runs)
        map_lines: list[str] = []
        for plain, raw in middle_lines:
            stripped = plain.strip()
            if not stripped:
                # Blank line - include in map if we have content
                if map_lines:
                    map_lines.append(raw)
                continue
            # All non-blank lines inside the block are map lines
            map_lines.append(raw)

        # Trim leading/trailing blank lines from map
        while map_lines and not strip_ansi(map_lines[0]).strip():
            map_lines.pop(0)
        while map_lines and not strip_ansi(map_lines[-1]).strip():
            map_lines.pop()

        self.map_lines = map_lines

    def clear(self):
        self.map_lines.clear()
        self.room_name = ""
        self.room_name_raw = ""
        self.room_desc.clear()
        self.coords = ""
        self.exits = ""
        self.exits_raw = ""
        self._block_lines.clear()
        self._rdesc_lines.clear()
        self._in_map_block = False
        self._in_rdesc_block = False
        self._expect_room_name = False
