from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mud_client.config import InfoPatterns, InfoTimers


@dataclass
class InfoEntry:
    text: str       # ANSI-stripped message text
    raw_line: str   # original with ANSI preserved
    timestamp: float


class InfoTracker:
    """Tracks INFO channel messages and manages a news-ticker display."""

    def __init__(self, patterns: "InfoPatterns | None" = None,
                 timers: "InfoTimers | None" = None):
        # Compile pattern from config or use default
        if patterns:
            self._info_re = re.compile(patterns.prefix)
        else:
            self._info_re = re.compile(r"^INFO:\s+")

        # Timer settings
        if timers:
            self.min_display = timers.min_display
            self.auto_hide = timers.auto_hide
            self.max_history = timers.max_history
        else:
            self.min_display = 10.0
            self.auto_hide = 40.0
            self.max_history = 200

        self.history: list[InfoEntry] = []
        self.current: InfoEntry | None = None
        self._queue: list[InfoEntry] = []
        self._display_since: float = 0.0  # when current message was shown

    def match(self, plain_text: str) -> bool:
        """Return True if plain_text is an INFO channel line."""
        return bool(self._info_re.match(plain_text))

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
