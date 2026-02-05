import curses
import re

_ANSI_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# curses color index for the 8 standard ANSI colors
_ANSI_COLORS = [
    curses.COLOR_BLACK,
    curses.COLOR_RED,
    curses.COLOR_GREEN,
    curses.COLOR_YELLOW,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_CYAN,
    curses.COLOR_WHITE,
]


def _init_color_pairs():
    """Initialize curses color pairs for ANSI color combinations.

    Pair layout: pair_id = fg_index * 9 + bg_index + 1
      fg_index 0-7 = the 8 ANSI colors
      bg_index 0   = default background (-1)
      bg_index 1-8 = the 8 ANSI background colors
    Total: 72 pairs (indices 1-72).
    """
    curses.start_color()
    curses.use_default_colors()
    for fg_idx in range(8):
        for bg_idx in range(9):
            pair_id = fg_idx * 9 + bg_idx + 1
            fg = _ANSI_COLORS[fg_idx]
            bg = -1 if bg_idx == 0 else _ANSI_COLORS[bg_idx - 1]
            try:
                curses.init_pair(pair_id, fg, bg)
            except curses.error:
                pass


def _color_pair_id(fg: int, bg: int) -> int:
    """Return curses color pair id for given fg (0-7) and bg (-1 or 0-7)."""
    fg_idx = fg  # 0-7
    bg_idx = 0 if bg < 0 else bg + 1  # 0 for default, 1-8 for colors
    return fg_idx * 9 + bg_idx + 1


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text."""
    return _ANSI_SGR_RE.sub("", text)


def parse_ansi(text: str, fg: int = 7, bg: int = -1, bold: bool = False,
               underline: bool = False, reverse: bool = False):
    """Parse ANSI SGR sequences in text, returning colored segments.

    Args:
        text: String possibly containing ANSI escape sequences.
        fg, bg, bold, underline, reverse: Initial state carried from previous line.

    Returns:
        (segments, state) where:
          segments = list of (plain_text, curses_attr) tuples
          state = (fg, bg, bold, underline, reverse) for next line
    """
    segments = []
    last_end = 0

    for m in _ANSI_SGR_RE.finditer(text):
        # Text before this escape sequence
        before = text[last_end:m.start()]
        if before:
            attr = _build_attr(fg, bg, bold, underline, reverse)
            segments.append((before, attr))
        last_end = m.end()

        # Parse SGR parameters
        params_str = m.group(1)
        if not params_str:
            codes = [0]
        else:
            codes = [int(c) for c in params_str.split(";") if c.isdigit()]

        for code in codes:
            if code == 0:
                fg, bg, bold, underline, reverse = 7, -1, False, False, False
            elif code == 1:
                bold = True
            elif code == 4:
                underline = True
            elif code == 7:
                reverse = True
            elif code == 22:
                bold = False
            elif code == 24:
                underline = False
            elif code == 27:
                reverse = False
            elif 30 <= code <= 37:
                fg = code - 30
            elif 40 <= code <= 47:
                bg = code - 40
            elif 39 == code:
                fg = 7  # default foreground
            elif 49 == code:
                bg = -1  # default background
            elif 90 <= code <= 97:
                fg = code - 90
                bold = True

    # Remaining text after last escape
    remaining = text[last_end:]
    if remaining:
        attr = _build_attr(fg, bg, bold, underline, reverse)
        segments.append((remaining, attr))

    return segments, (fg, bg, bold, underline, reverse)


def _build_attr(fg: int, bg: int, bold: bool, underline: bool, reverse: bool) -> int:
    """Build a curses attribute integer from ANSI state."""
    attr = 0
    # Only apply color pair if non-default
    if fg != 7 or bg >= 0:
        try:
            attr = curses.color_pair(_color_pair_id(fg, bg))
        except curses.error:
            pass
    if bold:
        attr |= curses.A_BOLD
    if underline:
        attr |= curses.A_UNDERLINE
    if reverse:
        attr |= curses.A_REVERSE
    return attr
