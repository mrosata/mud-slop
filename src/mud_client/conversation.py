import re
import textwrap
import time
from dataclasses import dataclass


@dataclass
class SpeechPattern:
    pattern: re.Pattern
    label: str


@dataclass
class ConversationEntry:
    speaker: str
    message: str
    raw_line: str  # original with ANSI preserved
    timestamp: float


class ConversationTracker:
    def __init__(self, patterns: list[SpeechPattern]):
        self.patterns = patterns
        self.entries: list[ConversationEntry] = []
        self.view_index: int = 0
        self.visible: bool = False
        self.last_speech_time: float = 0.0
        self.auto_close_seconds: float = 8.0
        # Multi-line speech accumulation state
        self._pending_entry: ConversationEntry | None = None
        self._open_quote: str = ""  # the quote character that opened the block

    def match(self, plain_text: str):
        """Try to match plain_text against speech patterns.
        Returns (speaker, message, open_quote) or None."""
        for sp in self.patterns:
            m = sp.pattern.match(plain_text)
            if m:
                try:
                    speaker = m.group("speaker")
                    message = m.group("message")
                    open_quote = m.group("quote")
                    # Strip trailing quote if present (single-line speech)
                    if message and message[-1] in ("'", '"'):
                        message = message[:-1]
                    return speaker, message, open_quote
                except IndexError:
                    continue
        return None

    def is_continuing(self) -> bool:
        """True when accumulating a multi-line speech block."""
        return self._pending_entry is not None

    def feed_line(self, plain_text: str, raw_line: str) -> bool:
        """Process one line through speech detection.

        Returns True if the line was consumed as speech (should not go to
        display_lines), False if it's normal text.
        """
        # If we're inside a multi-line speech block, accumulate
        if self._pending_entry is not None:
            stripped = plain_text.rstrip()
            self._pending_entry.message += " " + plain_text.strip()
            self._pending_entry.raw_line += "\n" + raw_line
            # Check if this line closes the quote
            if stripped.endswith(self._open_quote):
                # Remove the trailing quote from message
                msg = self._pending_entry.message
                if msg.endswith(self._open_quote):
                    self._pending_entry.message = msg[:-1]
                self._finish_pending()
            return True

        # Try to match a new speech line
        result = self.match(plain_text)
        if result is None:
            return False

        speaker, message, open_quote = result

        entry = ConversationEntry(
            speaker=speaker, message=message,
            raw_line=raw_line, timestamp=time.time()
        )

        # Check if the speech is already closed (single-line)
        stripped = plain_text.rstrip()
        if open_quote and stripped.endswith(open_quote) and stripped.count(open_quote) >= 2:
            # Single-line: quote opens and closes on same line
            self.add_entry(entry)
        else:
            # Multi-line: store as pending until closing quote
            self._pending_entry = entry
            self._open_quote = open_quote
        return True

    def _finish_pending(self):
        """Finalize a pending multi-line entry."""
        if self._pending_entry is not None:
            self.add_entry(self._pending_entry)
            self._pending_entry = None
            self._open_quote = ""

    def add_entry(self, entry: ConversationEntry):
        self.entries.append(entry)
        self.last_speech_time = entry.timestamp
        if not self.visible:
            self.visible = True
            self.view_index = len(self.entries) - 1
        # If already visible, new entry is queued — user navigates to it

    def navigate_next(self):
        if not self.entries:
            return
        if self.view_index < len(self.entries) - 1:
            self.view_index += 1
            self.last_speech_time = time.time()
        elif self.view_index >= len(self.entries) - 1:
            self.dismiss()

    def navigate_prev(self):
        if not self.entries:
            return
        if self.view_index > 0:
            self.view_index -= 1
            self.last_speech_time = time.time()

    def dismiss(self):
        self.visible = False
        self.entries.clear()
        self.view_index = 0
        self._pending_entry = None
        self._open_quote = ""

    @property
    def current_entry(self):
        if self.entries and 0 <= self.view_index < len(self.entries):
            return self.entries[self.view_index]
        return None

    @property
    def queue_status(self) -> str:
        if not self.entries:
            return ""
        return f"{self.view_index + 1}/{len(self.entries)}"

    @property
    def has_unread(self) -> bool:
        return self.view_index < len(self.entries) - 1

    def check_auto_close(self, now: float) -> bool:
        """Returns True if the overlay should be closed."""
        if not self.visible:
            return False
        elapsed = now - self.last_speech_time
        if elapsed >= self.auto_close_seconds and not self.has_unread:
            return True
        return False


DEFAULT_SPEECH_PATTERNS = [
    SpeechPattern(re.compile(r"^(?P<speaker>[\w'-]+)\s+says?,?\s+(?P<quote>['\"])(?P<message>.+)"), "says"),
    SpeechPattern(re.compile(r"^(?P<speaker>[\w'-]+)\s+tells?\s+you,?\s+(?P<quote>['\"])(?P<message>.+)"), "tells"),
    SpeechPattern(re.compile(r"^(?P<speaker>[\w'-]+)\s+whispers?,?\s+(?P<quote>['\"])(?P<message>.+)"), "whispers"),
    SpeechPattern(re.compile(r"^(?P<speaker>[\w'-]+)\s+(?:yells?|shouts?),?\s+(?P<quote>['\"])(?P<message>.+)"), "yells"),
    SpeechPattern(re.compile(r"^(?P<speaker>[\w'-]+)\s+(?:asks?|exclaims?|questions?),?\s+(?P<quote>['\"])(?P<message>.+)"), "asks"),
]


def _wrap_text(text: str, width: int) -> list[str]:
    """Simple word wrap for overlay rendering."""
    if width <= 0:
        return [text]
    return textwrap.wrap(text, width) or [""]
