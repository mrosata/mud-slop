import re
import time
from dataclasses import dataclass

_INFO_RE = re.compile(r"^INFO:\s+")


@dataclass
class InfoEntry:
    text: str       # ANSI-stripped message text
    raw_line: str   # original with ANSI preserved
    timestamp: float


class InfoTracker:
    """Tracks INFO channel messages and manages a news-ticker display."""

    def __init__(self, min_display: float = 10.0, auto_hide: float = 40.0,
                 max_history: int = 200):
        self.min_display = min_display    # minimum seconds to show each message
        self.auto_hide = auto_hide        # hide ticker after this many idle seconds
        self.max_history = max_history
        self.history: list[InfoEntry] = []
        self.current: InfoEntry | None = None
        self._queue: list[InfoEntry] = []
        self._display_since: float = 0.0  # when current message was shown

    def match(self, plain_text: str) -> bool:
        """Return True if plain_text is an INFO channel line."""
        return bool(_INFO_RE.match(plain_text))

    def add(self, plain_text: str, raw_line: str):
        entry = InfoEntry(text=plain_text, raw_line=raw_line,
                          timestamp=time.time())
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        if self.current is None:
            self._show(entry)
        else:
            self._queue.append(entry)

    def tick(self, now: float):
        """Called each loop iteration. Advances queue or hides ticker."""
        if self.current is None:
            return
        elapsed = now - self._display_since
        # Try to advance to queued message after min_display
        if self._queue and elapsed >= self.min_display:
            self._show(self._queue.pop(0))
        # Auto-hide after auto_hide seconds with nothing queued
        elif not self._queue and elapsed >= self.auto_hide:
            self.current = None

    def _show(self, entry: InfoEntry):
        self.current = entry
        self._display_since = time.time()

    @property
    def visible(self) -> bool:
        return self.current is not None
