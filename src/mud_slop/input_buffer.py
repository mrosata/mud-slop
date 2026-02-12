class InputBuffer:
    """Editable text buffer with cursor position tracking.

    Supports cursor movement (left/right, home/end, word jumps),
    insertion at cursor, backspace, and delete.
    """

    def __init__(self):
        self._text = ""
        self._cursor = 0

    @property
    def text(self) -> str:
        return self._text

    @property
    def cursor(self) -> int:
        return self._cursor

    def insert(self, ch: str):
        """Insert a character at the cursor position."""
        self._text = self._text[: self._cursor] + ch + self._text[self._cursor :]
        self._cursor += len(ch)

    def backspace(self):
        """Delete the character before the cursor."""
        if self._cursor > 0:
            self._text = self._text[: self._cursor - 1] + self._text[self._cursor :]
            self._cursor -= 1

    def delete(self):
        """Delete the character at the cursor."""
        if self._cursor < len(self._text):
            self._text = self._text[: self._cursor] + self._text[self._cursor + 1 :]

    def move_left(self):
        """Move cursor one position to the left."""
        if self._cursor > 0:
            self._cursor -= 1

    def move_right(self):
        """Move cursor one position to the right."""
        if self._cursor < len(self._text):
            self._cursor += 1

    def move_home(self):
        """Move cursor to the beginning of the buffer."""
        self._cursor = 0

    def move_end(self):
        """Move cursor to the end of the buffer."""
        self._cursor = len(self._text)

    def move_word_left(self):
        """Move cursor to the beginning of the previous word."""
        pos = self._cursor
        # Skip whitespace going left
        while pos > 0 and not self._text[pos - 1].isalnum():
            pos -= 1
        # Skip word characters going left
        while pos > 0 and self._text[pos - 1].isalnum():
            pos -= 1
        self._cursor = pos

    def move_word_right(self):
        """Move cursor to the end of the next word."""
        pos = self._cursor
        length = len(self._text)
        # Skip non-word characters going right
        while pos < length and not self._text[pos].isalnum():
            pos += 1
        # Skip word characters going right
        while pos < length and self._text[pos].isalnum():
            pos += 1
        self._cursor = pos

    def kill_word_back(self):
        """Delete from cursor back to start of previous word (Ctrl+W)."""
        if self._cursor == 0:
            return
        old_cursor = self._cursor
        self.move_word_left()
        self._text = self._text[: self._cursor] + self._text[old_cursor:]

    def kill_to_start(self):
        """Delete from cursor to start of line (Ctrl+U)."""
        self._text = self._text[self._cursor :]
        self._cursor = 0

    def kill_to_end(self):
        """Delete from cursor to end of line (Ctrl+K)."""
        self._text = self._text[: self._cursor]

    def set_text(self, text: str):
        """Replace buffer content and move cursor to end."""
        self._text = text
        self._cursor = len(text)

    def clear(self) -> str:
        """Clear the buffer and return the previous content."""
        text = self._text
        self._text = ""
        self._cursor = 0
        return text
