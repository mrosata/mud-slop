class CommandHistory:
    """Tracks command history with prefix-filtered up/down navigation."""

    def __init__(self, max_size: int = 1000):
        self._history: list[str] = []
        self._max_size = max_size
        self._index = -1  # -1 means not browsing
        self._saved_input = ""  # input buffer before browsing started
        self._prefix = ""  # prefix filter locked when browsing starts

    def add(self, cmd: str):
        """Add a command to history. Skip empty and consecutive duplicates."""
        if not cmd.strip():
            return
        if self._history and self._history[-1] == cmd:
            return
        self._history.append(cmd)
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size :]
        self.reset()

    def reset(self):
        """Reset browsing state."""
        self._index = -1
        self._saved_input = ""
        self._prefix = ""

    def _filtered(self) -> list[str]:
        """Return history entries matching the locked prefix (case insensitive)."""
        if not self._prefix:
            return self._history
        lp = self._prefix.lower()
        return [h for h in self._history if h.lower().startswith(lp)]

    def navigate_up(self, current_input: str) -> str:
        """Move to an older history entry. Returns the new input text."""
        if not self._history:
            return current_input
        if self._index == -1:
            # Start browsing — lock the current input as prefix
            self._saved_input = current_input
            self._prefix = current_input
        filtered = self._filtered()
        if not filtered:
            return current_input
        if self._index == -1:
            self._index = len(filtered) - 1
        elif self._index > 0:
            self._index -= 1
        return filtered[self._index]

    def navigate_down(self, current_input: str) -> str:
        """Move to a newer history entry. Returns the new input text."""
        if self._index == -1:
            return current_input
        filtered = self._filtered()
        if not filtered:
            result = self._saved_input
            self.reset()
            return result
        if self._index < len(filtered) - 1:
            self._index += 1
            return filtered[self._index]
        # Past the newest match — restore the saved input
        result = self._saved_input
        self.reset()
        return result
