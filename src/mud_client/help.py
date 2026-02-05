"""Help pager overlay for displaying {help}/{/help} tagged content."""

import re
from dataclasses import dataclass, field


@dataclass
class HelpContent:
    """Parsed help content from {help}/{/help} block."""
    title: str                        # From first non-tag line or "Help"
    header_lines: list[str] = field(default_factory=list)  # Lines before {helpbody} (metadata)
    body_lines: list[str] = field(default_factory=list)    # Raw ANSI lines from {helpbody}
    tags: list[str] = field(default_factory=list)          # Keywords from {helptags}


class HelpTracker:
    """Detects and displays help content using {help}/{/help} tags."""

    # Tag patterns
    _HELP_START_RE = re.compile(r'\{help\}')
    _HELP_END_RE = re.compile(r'\{/help\}')
    _HELPBODY_START_RE = re.compile(r'\{helpbody\}')
    _HELPBODY_END_RE = re.compile(r'\{/helpbody\}')
    _HELPTAGS_RE = re.compile(r'\{helptags\}(.*)$')
    _HELPKEYWORDS_RE = re.compile(r'\{helpkeywords\}')

    def __init__(self):
        # Public state (read by UI)
        self.content: HelpContent | None = None  # Current help content
        self.visible: bool = False               # Overlay shown
        self.scroll_offset: int = 0              # Lines scrolled from top

        # Set by UI after wrapping lines for display
        self._wrapped_line_count: int = 0

        # Internal parsing state
        self._in_help_block: bool = False
        self._in_body_block: bool = False
        self._header_lines: list[str] = []
        self._body_lines: list[str] = []
        self._tags: list[str] = []
        self._title: str = ""

    def feed_line(self, plain: str, raw: str) -> tuple[bool, list[str]]:
        """Process a line for help tags.

        Returns (consumed, overflow_raw_lines).
        consumed: True if this line is being held/consumed as help data.
        overflow: always empty (tag-based parsing doesn't produce overflow).
        """
        # Check for {help} tag - start of help block
        if self._HELP_START_RE.search(plain):
            self._in_help_block = True
            self._in_body_block = False
            self._header_lines = []
            self._body_lines = []
            self._tags = []
            self._title = ""
            return True, []

        # Check for {/help} tag - end of help block
        if self._HELP_END_RE.search(plain):
            if self._in_help_block:
                self._finalize_help()
            self._in_help_block = False
            self._in_body_block = False
            return True, []

        # Not in a help block - don't consume
        if not self._in_help_block:
            return False, []

        # Inside help block - check for nested tags

        # Check for {helpbody} start
        if self._HELPBODY_START_RE.search(plain):
            self._in_body_block = True
            return True, []

        # Check for {/helpbody} end
        if self._HELPBODY_END_RE.search(plain):
            self._in_body_block = False
            return True, []

        # Check for {helptags} line
        tags_match = self._HELPTAGS_RE.search(plain)
        if tags_match:
            tags_str = tags_match.group(1).strip()
            if tags_str:
                self._tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            return True, []

        # Inside helpbody - accumulate body lines
        if self._in_body_block:
            self._body_lines.append(raw)
            return True, []

        # Inside help block but outside helpbody - accumulate as header lines
        # Strip {helpkeywords} tag if present for cleaner display
        clean_raw = self._HELPKEYWORDS_RE.sub('', raw)
        self._header_lines.append(clean_raw)

        # Use first non-empty, non-separator line as title
        stripped = plain.strip()
        if stripped and not self._title and not stripped.startswith('-'):
            # Strip {helpkeywords} from title too
            clean_title = self._HELPKEYWORDS_RE.sub('', stripped).strip()
            if clean_title:
                self._title = clean_title

        return True, []

    def _finalize_help(self):
        """Finalize help content and show overlay."""
        title = self._title if self._title else "Help"
        self.content = HelpContent(
            title=title,
            header_lines=list(self._header_lines),
            body_lines=list(self._body_lines),
            tags=list(self._tags)
        )
        self.visible = True
        self.scroll_offset = 0
        self._wrapped_line_count = 0  # Will be set by UI after wrapping

    def scroll_down(self, scroll_amount: int, visible_height: int = 0):
        """Scroll down by scroll_amount lines (PgDn).

        visible_height is used to calculate max_offset (how far we can scroll).
        If not provided, scroll_amount is used as the visible height.
        """
        if not self.content:
            return
        visible_h = visible_height or scroll_amount
        # Use wrapped line count if available, otherwise fall back to raw line count
        total_lines = self._wrapped_line_count or (
            len(self.content.header_lines) + len(self.content.body_lines)
        )
        max_offset = max(0, total_lines - visible_h)
        self.scroll_offset = min(self.scroll_offset + scroll_amount, max_offset)

    def scroll_up(self, page_size: int):
        """Scroll up by page_size lines (PgUp)."""
        self.scroll_offset = max(0, self.scroll_offset - page_size)

    def scroll_to_top(self):
        """Scroll to top (Home)."""
        self.scroll_offset = 0

    def scroll_to_bottom(self, page_size: int):
        """Scroll to bottom (End)."""
        if not self.content:
            return
        # Use wrapped line count if available, otherwise fall back to raw line count
        total_lines = self._wrapped_line_count or (
            len(self.content.header_lines) + len(self.content.body_lines)
        )
        self.scroll_offset = max(0, total_lines - page_size)

    def dismiss(self):
        """Close the help overlay (ESC)."""
        self.visible = False

    def clear(self):
        """Reset all state."""
        self.content = None
        self.visible = False
        self.scroll_offset = 0
        self._wrapped_line_count = 0
        self._in_help_block = False
        self._in_body_block = False
        self._header_lines = []
        self._body_lines = []
        self._tags = []
        self._title = ""
