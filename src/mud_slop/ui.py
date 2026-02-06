from __future__ import annotations

import curses
from typing import TYPE_CHECKING

from mud_slop.types import ts_str
from mud_slop.ansi import _init_color_pairs, strip_ansi, parse_ansi, _color_pair_id
from mud_slop.gmcp import GMCPHandler
from mud_slop.debug_log import DebugLogger
from mud_slop.history import CommandHistory
from mud_slop.input_buffer import InputBuffer
from mud_slop.conversation import ConversationTracker, DEFAULT_SPEECH_PATTERNS, build_speech_patterns, _wrap_text
from mud_slop.info import InfoTracker
from mud_slop.map import MapTracker
from mud_slop.help import HelpTracker

if TYPE_CHECKING:
    from mud_slop.config import Config


class MudUI:
    HELP_MIN_WIDTH = 65     # Minimum width for help pager
    HELP_MIN_HEIGHT = 30

    def __init__(self, stdscr, gmcp_handler: "GMCPHandler | None" = None,
                 color: bool = True, debug_logger: "DebugLogger | None" = None,
                 conv_pos: str = "bottom-right", config: "Config | None" = None):
        self.stdscr = stdscr
        self.conv_pos = conv_pos
        self.gmcp_handler = gmcp_handler
        self.color_enabled = color
        self.debug_logger = debug_logger
        self.config = config

        # UI layout settings from config or defaults
        if config and config.ui:
            self.RIGHT_PANEL_MAX_WIDTH = config.ui.right_panel_max_width
            self.RIGHT_PANEL_RATIO = config.ui.right_panel_ratio
            self.max_output_lines = config.ui.max_output_lines
        else:
            self.RIGHT_PANEL_MAX_WIDTH = 70
            self.RIGHT_PANEL_RATIO = 0.40
            self.max_output_lines = 5000

        self.output_lines = []   # main text area (full history)
        self.display_lines = []  # filtered view (conversation lines removed)
        self.input_buf = InputBuffer()
        self.history = CommandHistory()

        # Build trackers with config
        if config:
            # Conversation tracker with patterns and timer from config
            conv_patterns = build_speech_patterns(config.patterns.conversation.patterns)
            auto_close = config.timers.conversation.auto_close
            self.conversation = ConversationTracker(conv_patterns, auto_close)

            # Info tracker with pattern and timers from config
            self.info_tracker = InfoTracker(
                patterns=config.patterns.info,
                timers=config.timers.info
            )

            # Map tracker with patterns from config
            self.map_tracker = MapTracker(patterns=config.patterns.map)

            # Help tracker with patterns from config
            self.help_tracker = HelpTracker(patterns=config.patterns.help)
        else:
            self.conversation = ConversationTracker(DEFAULT_SPEECH_PATTERNS)
            self.info_tracker = InfoTracker()
            self.map_tracker = MapTracker()
            self.help_tracker = HelpTracker()

        self._skip_next_blank = False
        self._skip_blank_after_speech = False
        self._incomplete_line = ""  # Buffer for incomplete lines (no trailing \n)

        # Scroll state: 0 = pinned to bottom (auto-scroll), >0 = lines from bottom
        self._output_scroll = 0
        self._output_h = 1  # last known output panel height (updated during draw)
        # When True, show full output_lines even at scroll=0 (first step before scrolling)
        self._show_full_history = False

        self.status = "F1 help | Ctrl+C quit | /clear, /quit"
        self._help_mode = False
        self.echo_off = False  # True when server signals password mode (hide input)

        # ANSI color state persisted across lines (output_lines view)
        self._ansi_fg = 7    # default white
        self._ansi_bg = -1   # default background
        self._ansi_bold = False
        self._ansi_underline = False
        self._ansi_reverse = False

        # ANSI color state for display_lines (filtered view)
        self._display_ansi_fg = 7
        self._display_ansi_bg = -1
        self._display_ansi_bold = False
        self._display_ansi_underline = False
        self._display_ansi_reverse = False

        curses.curs_set(1)
        if color:
            _init_color_pairs()
        else:
            curses.start_color()
            curses.use_default_colors()
        self.stdscr.timeout(25)
        self.stdscr.keypad(True)

    def _is_other_speech(self, plain: str) -> bool:
        """Return True if the line is speech from someone other than 'You'.

        Also returns True if we're mid-accumulation of a multi-line speech
        block (continuation lines have no speaker to check).
        """
        if self.conversation.is_continuing():
            return True
        result = self.conversation.match(plain)
        if result is None:
            return False
        speaker = result[0]
        return speaker != "You"

    def _add_to_display(self, plain: str, line: str):
        """Route a single line through speech detection into display_lines."""
        if self._is_other_speech(plain) and self.conversation.feed_line(plain, line):
            # Speech line consumed - remove preceding blank and skip following blanks
            if self.display_lines and strip_ansi(self.display_lines[-1]).strip() == "":
                self.display_lines.pop()
            self._skip_blank_after_speech = True
        elif self._skip_blank_after_speech and plain.strip() == "":
            # Swallow blank lines after speech
            pass
        else:
            self._skip_next_blank = False
            self._skip_blank_after_speech = False
            self.display_lines.append(line)

    def add_output_text(self, text: str):
        # Prepend any buffered incomplete line from previous chunk
        if self._incomplete_line:
            text = self._incomplete_line + text
            self._incomplete_line = ""

        lines = text.split("\n")
        # MUD lines end with \r\n, so after normalization text ends with \n.
        # split() produces a trailing empty string — drop it to avoid blank lines
        # between received chunks. If no trailing empty string, the last element
        # is an incomplete line (TCP fragmentation) — buffer it for next chunk.
        if lines and lines[-1] == "":
            lines.pop()
        elif lines:
            # Last line is incomplete (no trailing \n) — buffer it
            self._incomplete_line = lines.pop()
        added = 0
        for line in lines:
            if not self.color_enabled:
                line = strip_ansi(line)
            self.output_lines.append(line)
            added += 1

            # Check for INFO channel messages, then map, then speech patterns
            plain = strip_ansi(line)
            if self.info_tracker.match(plain):
                self.info_tracker.add(plain, line)
                self._skip_next_blank = True
                # INFO lines are filtered from display_lines
                # Also remove preceding blank line if present
                if self.display_lines and strip_ansi(self.display_lines[-1]).strip() == "":
                    self.display_lines.pop()
            elif self._skip_next_blank and plain.strip() == "":
                # Swallow blank lines that follow an INFO message (keep skipping until content)
                pass
            else:
                # Reset the skip flag when we see actual content
                self._skip_next_blank = False
                # Help detection - check for {help}/{/help} tags
                help_consumed, _ = self.help_tracker.feed_line(plain, line)
                if help_consumed:
                    pass  # Help line held in tracker
                else:
                    # Map detection — may consume line or return overflow
                    consumed, overflow = self.map_tracker.feed_line(plain, line)
                    for ov_raw in overflow:
                        ov_plain = strip_ansi(ov_raw)
                        self._add_to_display(ov_plain, ov_raw)
                    if consumed:
                        pass  # Map line held in accumulator
                    else:
                        self._add_to_display(plain, line)

        # Keep scroll position stable when scrolled up
        if self._output_scroll > 0:
            self._output_scroll += added
        if len(self.output_lines) > self.max_output_lines:
            trimmed = len(self.output_lines) - self.max_output_lines
            self.output_lines = self.output_lines[-self.max_output_lines:]
            if self._output_scroll > 0:
                self._output_scroll = max(0, self._output_scroll - trimmed)
        # Trim display_lines to same limit
        if len(self.display_lines) > self.max_output_lines:
            self.display_lines = self.display_lines[-self.max_output_lines:]

    def add_system_message(self, text: str):
        """Add a system message to the output pane."""
        line = f"-- {text} --"
        self.output_lines.append(line)
        self.display_lines.append(line)

    def _has_stats(self) -> bool:
        return bool(self.gmcp_handler and self.gmcp_handler.vitals)

    def _show_ticker(self) -> bool:
        return self.info_tracker.visible

    def _has_map(self) -> bool:
        return bool(self.map_tracker.map_lines)

    def _has_help(self) -> bool:
        return self.help_tracker.visible and self.help_tracker.content is not None

    # Stats panel height (compact layout: HP/Mana/Moves bars + status + 2-col attributes)
    STATS_HEIGHT = 12

    def _layout(self):
        h, w = self.stdscr.getmaxyx()
        # Reserve rows at bottom: status (1) + input (1) + optional ticker (1)
        ticker_h = 1 if self._show_ticker() else 0
        bottom_rows = 2 + ticker_h
        usable_h = max(1, h - bottom_rows)

        # Right side panel: stats on top, map below (if both present)
        # Or just one if only one is present
        show_stats = self._has_stats()
        show_map = self._has_map()

        # Determine right panel width: 30% of screen, capped at max
        right_panel_w = 0
        if show_stats or show_map:
            right_panel_w = min(int(w * self.RIGHT_PANEL_RATIO), self.RIGHT_PANEL_MAX_WIDTH)

        # Output pane: left side, full height
        out_w = max(20, w - right_panel_w)
        out_win = curses.newwin(usable_h, out_w, 0, 0)

        # Right panel layout: stats on top (if present), map below (if present)
        stats_win = None
        map_win = None

        if right_panel_w > 0:
            right_x = out_w

            if show_stats and show_map:
                # Split right panel: stats gets fixed height, map gets rest
                stats_h = min(self.STATS_HEIGHT, usable_h // 2)
                map_h = usable_h - stats_h
                stats_win = curses.newwin(stats_h, right_panel_w, 0, right_x)
                map_win = curses.newwin(map_h, right_panel_w, stats_h, right_x)
            elif show_stats:
                # Only stats
                stats_win = curses.newwin(usable_h, right_panel_w, 0, right_x)
            elif show_map:
                # Only map
                map_win = curses.newwin(usable_h, right_panel_w, 0, right_x)

        ticker_win = None
        if ticker_h:
            ticker_win = curses.newwin(1, w, h - 3, 0)
        input_win = curses.newwin(1, w, h - 2, 0)
        status_win = curses.newwin(1, w, h - 1, 0)

        return out_win, stats_win, map_win, ticker_win, input_win, status_win

    def _draw_scrolling_text(self, win, lines, scroll_offset: int = 0):
        win.erase()
        h, w = win.getmaxyx()
        end = len(lines) - scroll_offset
        start = max(0, end - h)
        end = max(start, end)
        view = lines[start:end]
        for i, line in enumerate(view):
            try:
                win.addnstr(i, 0, line, w - 1)
            except curses.error:
                pass
        win.noutrefresh()

    def _draw_colored_text(self, win, lines, scroll_offset: int = 0,
                           state_key: str = "output"):
        """Draw lines with ANSI color support, maintaining state across lines.

        state_key selects which set of ANSI state to read/write:
        "output" uses _ansi_* fields, "display" uses _display_ansi_* fields.
        """
        win.erase()
        h, w = win.getmaxyx()
        end = len(lines) - scroll_offset
        start = max(0, end - h)
        end = max(start, end)
        view = lines[start:end]

        # When scrolled, re-parse ANSI state from the beginning up to the
        # visible region so colors are correct.  For performance, only replay
        # from the last 200 lines before the view (a reasonable bound).
        if scroll_offset > 0:
            replay_start = max(0, start - 200)
            fg, bg, bold, underline, reverse = 7, -1, False, False, False
            for line in lines[replay_start:start]:
                _, (fg, bg, bold, underline, reverse) = parse_ansi(
                    line, fg, bg, bold, underline, reverse
                )
        else:
            if state_key == "display":
                fg, bg = self._display_ansi_fg, self._display_ansi_bg
                bold = self._display_ansi_bold
                underline = self._display_ansi_underline
                reverse = self._display_ansi_reverse
            else:
                fg, bg = self._ansi_fg, self._ansi_bg
                bold, underline, reverse = self._ansi_bold, self._ansi_underline, self._ansi_reverse

        for i, line in enumerate(view):
            segments, (fg, bg, bold, underline, reverse) = parse_ansi(
                line, fg, bg, bold, underline, reverse
            )
            col = 0
            for text, attr in segments:
                remaining = w - 1 - col
                if remaining <= 0:
                    break
                try:
                    win.addnstr(i, col, text, remaining, attr)
                except curses.error:
                    pass
                col += min(len(text), remaining)

        # Only save state when pinned to bottom (normal auto-scroll)
        if scroll_offset == 0:
            if state_key == "display":
                self._display_ansi_fg = fg
                self._display_ansi_bg = bg
                self._display_ansi_bold = bold
                self._display_ansi_underline = underline
                self._display_ansi_reverse = reverse
            else:
                self._ansi_fg = fg
                self._ansi_bg = bg
                self._ansi_bold = bold
                self._ansi_underline = underline
                self._ansi_reverse = reverse

        win.noutrefresh()

    def _draw_stats(self, win):
        """Draw HP/Mana/Moves bars and character info from GMCP data."""
        if not win or not self.gmcp_handler:
            return
        win.erase()
        h, w = win.getmaxyx()

        # Draw left border (vertical line)
        for r in range(h):
            try:
                win.addch(r, 0, curses.ACS_VLINE)
            except curses.error:
                pass

        row = 0

        # Color pairs for bars: red=1, green=2, blue=4
        try:
            red_attr = curses.color_pair(_color_pair_id(1, -1))
            green_attr = curses.color_pair(_color_pair_id(2, -1))
            blue_attr = curses.color_pair(_color_pair_id(4, -1))
        except curses.error:
            red_attr = green_attr = blue_attr = 0

        def put(r, text, attr=0):
            if r >= h:
                return
            try:
                win.addnstr(r, 1, text, w - 2, attr)
            except curses.error:
                pass

        def bar(r, label, current, maximum, color_attr):
            """Draw a labeled bar with color. Returns next row."""
            if r + 1 >= h:
                return r
            try:
                cur = int(current)
                mx = max(int(maximum), 1)
            except (ValueError, TypeError):
                put(r, f"{label}: {current}/{maximum}", curses.A_BOLD)
                return r + 1
            # Label line with values
            put(r, f"{label}: {cur}/{mx}", curses.A_BOLD)
            r += 1
            if r >= h:
                return r
            # Bar line with color
            bar_w = w - 4
            if bar_w < 4:
                bar_w = 4
            filled = max(0, min(bar_w, int(bar_w * cur / mx)))
            empty = bar_w - filled
            # Draw colored filled part and empty part separately
            try:
                win.addstr(r, 1, "[", curses.A_BOLD)
                win.addstr(r, 2, "=" * filled, color_attr | curses.A_BOLD)
                win.addstr(r, 2 + filled, " " * empty)
                win.addstr(r, 2 + bar_w, "]", curses.A_BOLD)
            except curses.error:
                pass
            return r + 1

        vitals = self.gmcp_handler.vitals
        status = self.gmcp_handler.status
        stats = self.gmcp_handler.stats
        maxstats = self.gmcp_handler.maxstats

        if vitals:
            # Use maxstats for max values, fall back to vitals if not available
            max_hp = maxstats.get("maxhp") or vitals.get("maxhp", "?")
            max_mana = maxstats.get("maxmana") or vitals.get("maxmana", "?")
            max_moves = maxstats.get("maxmoves") or vitals.get("maxmoves", "?")
            row = bar(row, "HP", vitals.get("hp", "?"), max_hp, red_attr)
            row = bar(row, "Mana", vitals.get("mana", "?"), max_mana, blue_attr)
            row = bar(row, "Moves", vitals.get("moves", "?"), max_moves, green_attr)

        if status:
            # Compact status line
            status_parts = []
            if status.get("level"):
                status_parts.append(f"Lv{status['level']}")
            if status.get("tnl"):
                status_parts.append(f"TNL:{status['tnl']}")
            if status_parts and row < h:
                put(row, " ".join(status_parts))
                row += 1
            # Position and enemy on separate lines if present
            if status.get("position") and row < h:
                put(row, f"Pos: {status['position']}")
                row += 1
            if status.get("enemy") and row < h:
                put(row, f"Enemy: {status['enemy']}")
                row += 1

        if stats:
            # Display attributes in 2 columns
            attrs = ["str", "int", "wis", "dex", "con", "luck"]
            attr_values = []
            for attr in attrs:
                val = stats.get(attr)
                if val is not None:
                    max_key = f"max{attr}"
                    max_val = maxstats.get(max_key)
                    # Determine display text and color
                    try:
                        cur = int(val)
                        mx = int(max_val) if max_val else None
                        if mx is not None and cur < mx:
                            diff = cur - mx
                            text = f"{attr.upper()}:{val}({diff})"
                            color = 0
                        elif mx is not None and cur > mx:
                            text = f"{attr.upper()}:{val}"
                            color = green_attr
                        else:
                            text = f"{attr.upper()}:{val}"
                            color = 0
                    except (ValueError, TypeError):
                        text = f"{attr.upper()}:{val}"
                        color = 0
                    attr_values.append((text, color))

            # Draw in 2 columns
            col_w = (w - 3) // 2  # Two columns with a space between
            for i in range(0, len(attr_values), 2):
                if row >= h:
                    break
                # Left column
                text1, color1 = attr_values[i]
                try:
                    win.addnstr(row, 1, text1[:col_w], col_w, color1)
                except curses.error:
                    pass
                # Right column (if exists)
                if i + 1 < len(attr_values):
                    text2, color2 = attr_values[i + 1]
                    try:
                        win.addnstr(row, 1 + col_w + 1, text2[:col_w], col_w, color2)
                    except curses.error:
                        pass
                row += 1

        win.noutrefresh()

    def _draw_conversation_overlay(self, out_win):
        """Draw the conversation overlay on top of the output pane."""
        if not self.conversation.visible:
            return
        entry = self.conversation.current_entry
        if not entry:
            return

        out_h, out_w = out_win.getmaxyx()
        overlay_w = min(60, out_w - 4)
        if overlay_w < 20:
            return

        # Word-wrap the message text
        inner_w = overlay_w - 4  # 2 for border + 1 padding each side
        wrapped = _wrap_text(entry.message, inner_w)

        # Nav info line
        nav_parts = [self.conversation.queue_status]
        if self.conversation.has_unread:
            nav_parts.append("Shift+Right: next")
        if self.conversation.view_index > 0:
            nav_parts.append("Shift+Left: prev")
        nav_parts.append("Esc: close")
        nav_line = " | ".join(nav_parts)

        # Height: border top + message lines + blank + nav + border bottom
        overlay_h = min(len(wrapped) + 4, out_h - 2)
        if overlay_h < 4:
            return
        # Recalculate visible message lines
        msg_lines = overlay_h - 4  # top border, bottom border, nav, blank
        if msg_lines < 1:
            msg_lines = 1
            overlay_h = 5

        # Position overlay based on conv_pos setting
        v_pos, _, h_pos = self.conv_pos.partition("-")
        if h_pos == "left":
            x = 1
        elif h_pos == "right":
            x = max(0, out_w - overlay_w - 1)
        else:  # center
            x = max(0, (out_w - overlay_w) // 2)
        if v_pos == "bottom":
            y = max(0, out_h - overlay_h - 1)
        else:  # top
            y = 1

        try:
            overlay = out_win.derwin(overlay_h, overlay_w, y, x)
        except curses.error:
            return

        overlay.erase()
        try:
            overlay.border()
        except curses.error:
            pass

        # Speaker name on top border (bold)
        speaker_label = f" {entry.speaker} "
        try:
            overlay.addnstr(0, 2, speaker_label, overlay_w - 4, curses.A_BOLD)
        except curses.error:
            pass

        # Message lines (with ANSI color if enabled)
        for i, mline in enumerate(wrapped[:msg_lines]):
            row = 1 + i
            if row >= overlay_h - 1:
                break
            if self.color_enabled:
                segments, _ = parse_ansi(mline)
                col = 2
                for text, attr in segments:
                    remaining = overlay_w - 2 - col
                    if remaining <= 0:
                        break
                    try:
                        overlay.addnstr(row, col, text, remaining, attr)
                    except curses.error:
                        pass
                    col += min(len(text), remaining)
            else:
                try:
                    overlay.addnstr(row, 2, mline, overlay_w - 4)
                except curses.error:
                    pass

        # Nav info at bottom
        nav_row = overlay_h - 2
        if nav_row > 0:
            try:
                overlay.addnstr(nav_row, 2, nav_line, overlay_w - 4, curses.A_DIM)
            except curses.error:
                pass

        overlay.noutrefresh()

    def _draw_wrapped_colored(self, win, raw: str, start_row: int,
                              col_offset: int, inner_w: int,
                              pane_h: int) -> int:
        """Word-wrap and draw a raw ANSI line with colors.  Returns rows used."""
        segments, _ = parse_ansi(raw)
        # Flatten to (char, attr) pairs (visible characters only)
        chars: list[tuple[str, int]] = []
        for text, attr in segments:
            for ch in text:
                chars.append((ch, attr))
        if not chars:
            return 0

        # Build visual lines as (start, end) index ranges
        visual_lines: list[tuple[int, int]] = []
        pos = 0
        n = len(chars)
        while pos < n:
            end = min(pos + inner_w, n)
            if end >= n:
                visual_lines.append((pos, n))
                break
            # Look back for a word-break point (space or hyphen)
            break_at = end
            for i in range(end - 1, pos, -1):
                if chars[i][0] == ' ':
                    break_at = i + 1
                    break
            visual_lines.append((pos, break_at))
            pos = break_at
            # Skip leading spaces on the new line
            while pos < n and chars[pos][0] == ' ':
                pos += 1

        rows_used = 0
        for start, end in visual_lines:
            row = start_row + rows_used
            if row >= pane_h:
                break
            # Group consecutive chars with the same attr for efficient rendering
            col = col_offset
            run_start = start
            while run_start < end:
                run_attr = chars[run_start][1]
                run_end = run_start + 1
                while run_end < end and chars[run_end][1] == run_attr:
                    run_end += 1
                text = ''.join(c for c, _ in chars[run_start:run_end])
                remaining = inner_w - (col - col_offset)
                if remaining <= 0:
                    break
                try:
                    win.addnstr(row, col, text, remaining, run_attr)
                except curses.error:
                    pass
                col += min(len(text), remaining)
                run_start = run_end
            rows_used += 1
        return rows_used

    def _draw_map_pane(self, win):
        """Draw the map panel: room name, coords, map, exits, then description."""
        if not win:
            return
        win.erase()

        pane_h, pane_w = win.getmaxyx()

        # Draw left border (vertical line)
        for row in range(pane_h):
            try:
                win.addch(row, 0, curses.ACS_VLINE)
            except curses.error:
                pass

        inner_w = pane_w - 2  # 1 for left border, 1 for right margin
        row = 0

        # Room name as header (with ANSI colors if available)
        if self.map_tracker.room_name and row < pane_h:
            if self.color_enabled and self.map_tracker.room_name_raw:
                segments, _ = parse_ansi(self.map_tracker.room_name_raw)
                col = 2
                for text, attr in segments:
                    remaining = inner_w - (col - 2)
                    if remaining <= 0:
                        break
                    try:
                        win.addnstr(row, col, text, remaining, attr | curses.A_BOLD)
                    except curses.error:
                        pass
                    col += min(len(text), remaining)
            else:
                try:
                    win.addnstr(row, 2, self.map_tracker.room_name, inner_w, curses.A_BOLD)
                except curses.error:
                    pass
            row += 1

        # Coordinates
        if self.map_tracker.coords and row < pane_h:
            coords_text = f"Coords: {self.map_tracker.coords}"
            try:
                win.addnstr(row, 2, coords_text, inner_w, curses.A_DIM)
            except curses.error:
                pass
            row += 1

        # Blank line before map
        row += 1

        # Draw map lines with ANSI color support
        for raw in self.map_tracker.map_lines:
            if row >= pane_h:
                break
            if self.color_enabled:
                segments, _ = parse_ansi(raw)
                col = 2
                for text, attr in segments:
                    remaining = inner_w - (col - 2)
                    if remaining <= 0:
                        break
                    try:
                        win.addnstr(row, col, text, remaining, attr)
                    except curses.error:
                        pass
                    col += min(len(text), remaining)
            else:
                plain = strip_ansi(raw)
                try:
                    win.addnstr(row, 2, plain, inner_w)
                except curses.error:
                    pass
            row += 1

        # Draw exits below map (with ANSI colors if available)
        if self.map_tracker.exits and row < pane_h:
            if self.color_enabled and self.map_tracker.exits_raw:
                segments, _ = parse_ansi(self.map_tracker.exits_raw)
                col = 2
                for text, attr in segments:
                    remaining = inner_w - (col - 2)
                    if remaining <= 0:
                        break
                    try:
                        win.addnstr(row, col, text, remaining, attr)
                    except curses.error:
                        pass
                    col += min(len(text), remaining)
            else:
                try:
                    win.addnstr(row, 2, self.map_tracker.exits, inner_w)
                except curses.error:
                    pass
            row += 1

        # Blank line before description
        row += 1

        # Room description: render paragraphs with ANSI colors, word-wrapped
        if self.map_tracker.room_desc and row < pane_h:
            for desc_raw in self.map_tracker.room_desc:
                if row >= pane_h:
                    break
                desc_plain = strip_ansi(desc_raw).strip()
                if not desc_plain:
                    continue
                if self.color_enabled:
                    row += self._draw_wrapped_colored(
                        win, desc_raw, row, 2, inner_w, pane_h)
                else:
                    wrapped = _wrap_text(desc_plain, inner_w)
                    for wline in wrapped:
                        if row >= pane_h:
                            break
                        try:
                            win.addnstr(row, 2, wline, inner_w)
                        except curses.error:
                            pass
                        row += 1

        win.noutrefresh()

    def _draw_help_pager(self):
        """Draw the help pager overlay on the right side of the screen."""
        if not self.help_tracker.content:
            return

        content = self.help_tracker.content
        screen_h, screen_w = self.stdscr.getmaxyx()

        # Calculate pager dimensions - use 50% of screen width, with min/max bounds
        pager_w = max(self.HELP_MIN_WIDTH, int(screen_w * 0.50))
        pager_w = min(pager_w, screen_w - 4)  # Leave small margin on left
        pager_h = max(self.HELP_MIN_HEIGHT, screen_h - 4)
        pager_h = min(pager_h, screen_h - 2)  # Leave room for input/status

        if pager_w < 20 or pager_h < 10:
            return

        # Position on right side
        pager_x = max(0, screen_w - pager_w)
        pager_y = 0

        try:
            win = curses.newwin(pager_h, pager_w, pager_y, pager_x)
        except curses.error:
            return

        win.erase()
        try:
            win.border()
        except curses.error:
            pass

        inner_w = pager_w - 4  # 2 for border + 1 padding each side

        # Title on top border (bold)
        title_label = f" {content.title} "
        if len(title_label) > pager_w - 4:
            title_label = title_label[:pager_w - 5] + "..."
        try:
            win.addnstr(0, 2, title_label, pager_w - 4, curses.A_BOLD)
        except curses.error:
            pass

        # Calculate visible body area (minus borders, title row, controls row)
        body_h = pager_h - 4  # top border, gap after title, controls, bottom border
        if body_h < 1:
            body_h = 1

        # Pre-wrap all lines (header + body) that are too long for the display width
        # We wrap based on plain text length, preserving ANSI for lines that fit
        wrapped_lines: list[tuple[str, bool]] = []  # (line, has_ansi)

        # Process header lines first (metadata before {helpbody})
        for raw_line in content.header_lines:
            plain = strip_ansi(raw_line)
            if len(plain) <= inner_w:
                wrapped_lines.append((raw_line, True))
            else:
                wrapped = _wrap_text(plain, inner_w)
                for wline in wrapped:
                    wrapped_lines.append((wline, False))

        # Process body lines
        for raw_line in content.body_lines:
            plain = strip_ansi(raw_line)
            if len(plain) <= inner_w:
                wrapped_lines.append((raw_line, True))
            else:
                wrapped = _wrap_text(plain, inner_w)
                for wline in wrapped:
                    wrapped_lines.append((wline, False))

        # Draw body lines with scroll offset
        start_line = self.help_tracker.scroll_offset
        end_line = min(start_line + body_h, len(wrapped_lines))

        # Update scroll bounds based on wrapped line count
        self.help_tracker._wrapped_line_count = len(wrapped_lines)

        row = 2  # Start after border and title
        for i in range(start_line, end_line):
            if row >= pager_h - 2:  # Leave room for controls
                break
            line, has_ansi = wrapped_lines[i]
            if self.color_enabled and has_ansi:
                segments, _ = parse_ansi(line)
                col = 2
                for text, attr in segments:
                    remaining = inner_w - (col - 2)
                    if remaining <= 0:
                        break
                    try:
                        win.addnstr(row, col, text, remaining, attr)
                    except curses.error:
                        pass
                    col += min(len(text), remaining)
            else:
                # Plain text (either no color or wrapped continuation)
                plain = strip_ansi(line) if has_ansi else line
                try:
                    win.addnstr(row, 2, plain, inner_w)
                except curses.error:
                    pass
            row += 1

        # Draw controls at bottom row
        self._draw_help_controls(win, pager_h, pager_w)

        win.noutrefresh()

    def _draw_help_controls(self, win, pager_h: int, pager_w: int):
        """Draw paging controls at bottom of help pager."""
        controls_row = pager_h - 2
        inner_w = pager_w - 4

        # Show scroll position indicator on the right side
        offset = self.help_tracker.scroll_offset
        total = self.help_tracker._wrapped_line_count
        body_h = pager_h - 4
        if total > body_h:
            pos_text = f"[{offset + 1}-{min(offset + body_h, total)}/{total}]"
        else:
            pos_text = f"[1-{total}/{total}]" if total > 0 else ""

        # Calculate where position indicator will go (for limiting controls)
        pos_x = pager_w - len(pos_text) - 2 if pos_text else pager_w

        # Draw position indicator on the right
        if pos_text and pos_x > 2:
            try:
                win.addnstr(controls_row, pos_x, pos_text, len(pos_text), curses.A_DIM)
            except curses.error:
                pass

        # Format: PgUp/Dn: Scroll  ESC: Close
        # Keys in bold, actions in normal
        controls = [
            ("PgUp/Dn", "Scroll"),
            ("Home/End", "Top/Bot"),
            ("ESC", "Close"),
        ]

        col = 2
        max_col = pos_x - 2 if pos_text else pager_w - 4
        for i, (key, action) in enumerate(controls):
            if col >= max_col:
                break
            # Draw key in bold
            try:
                win.addnstr(controls_row, col, key, inner_w - (col - 2), curses.A_BOLD)
            except curses.error:
                pass
            col += len(key)

            # Draw ": action"
            text = f": {action}"
            try:
                win.addnstr(controls_row, col, text, inner_w - (col - 2))
            except curses.error:
                pass
            col += len(text)

            # Add spacing between controls (except last)
            if i < len(controls) - 1:
                col += 2

    def _draw_ticker(self, win):
        """Draw the info ticker bar."""
        win.erase()
        entry = self.info_tracker.current
        if not entry:
            win.noutrefresh()
            return
        _, w = win.getmaxyx()
        if self.color_enabled:
            segments, _ = parse_ansi(entry.raw_line)
            col = 0
            for text, attr in segments:
                remaining = w - 1 - col
                if remaining <= 0:
                    break
                try:
                    win.addnstr(0, col, text, remaining, attr)
                except curses.error:
                    pass
                col += min(len(text), remaining)
        else:
            try:
                win.addnstr(0, 0, entry.text, w - 1)
            except curses.error:
                pass
        win.noutrefresh()

    def draw(self):
        out_win, stats_win, map_win, ticker_win, input_win, status_win = self._layout()

        if self._help_mode:
            self._draw_help(out_win, stats_win, map_win, ticker_win, input_win, status_win)
            curses.doupdate()
            return

        # Track panel heights for scroll page size
        self._output_h = out_win.getmaxyx()[0]

        # Dual-view: when at scroll=0 and not in full history mode, show filtered
        # display_lines. When scrolled or in full history mode, show output_lines.
        if self._output_scroll == 0 and not self._show_full_history:
            view_lines = self.display_lines
            view_state_key = "display"
        else:
            view_lines = self.output_lines
            view_state_key = "output"

        if self.color_enabled:
            self._draw_colored_text(out_win, view_lines, self._output_scroll,
                                    state_key=view_state_key)
        else:
            self._draw_scrolling_text(out_win, view_lines, self._output_scroll)

        # Draw conversation overlay on top of the output pane
        self._draw_conversation_overlay(out_win)

        # Map pane (dedicated window, drawn after output so it paints on top)
        self._draw_map_pane(map_win)

        self._draw_stats(stats_win)

        # Help pager overlay (draws on right side, can cover stats/map)
        if self._has_help():
            self._draw_help_pager()

        # Info ticker
        if ticker_win:
            self._draw_ticker(ticker_win)

        # Input line
        input_win.erase()
        prompt = "> "
        _, w = input_win.getmaxyx()
        # Mask input when in password mode (server sent WILL ECHO)
        display_text = "*" * len(self.input_buf.text) if self.echo_off else self.input_buf.text
        full = prompt + display_text
        cursor_in_full = len(prompt) + self.input_buf.cursor
        # Compute visible window: ensure cursor is always visible
        max_visible = w - 1
        if len(full) <= max_visible:
            # Everything fits
            scroll_off = 0
        elif cursor_in_full < max_visible:
            # Cursor near the start — show from beginning
            scroll_off = 0
        else:
            # Slide window so cursor is visible with a small margin
            scroll_off = cursor_in_full - max_visible + 1
        shown = full[scroll_off:scroll_off + max_visible]
        try:
            input_win.addnstr(0, 0, shown, max_visible)
        except curses.error:
            pass
        input_win.noutrefresh()

        # Status line
        status_win.erase()
        status_text = self.status
        if self.debug_logger and self.debug_logger.enabled:
            status_text += " | DBG"
        if self._has_help():
            offset = self.help_tracker.scroll_offset
            status_text += " | HELP" + (f" +{offset}" if offset > 0 else "")
        if self.conversation.visible:
            status_text += f" | CONV {self.conversation.queue_status}"
        if self._output_scroll > 0:
            status_text += f" | SCROLL +{self._output_scroll}"
        elif self._show_full_history:
            status_text += " | HISTORY"
        try:
            status_win.addnstr(0, 0, status_text, status_win.getmaxyx()[1] - 1)
        except curses.error:
            pass
        status_win.noutrefresh()

        # Put cursor at correct position in input
        cursor_x = cursor_in_full - scroll_off
        try:
            self.stdscr.move(self.stdscr.getmaxyx()[0] - 2, cursor_x)
        except curses.error:
            pass

        curses.doupdate()

    def _draw_help(self, out_win, stats_win, map_win, ticker_win, input_win, status_win):
        help_text = [
            "Help",
            "",
            "Keys:",
            "  Enter        send current input",
            "  Left/Right   move cursor in input line",
            "  Ctrl+A       jump to start of input",
            "  Ctrl+E       jump to end of input",
            "  Ctrl+Left    jump word left",
            "  Ctrl+Right   jump word right",
            "  Ctrl+W       delete word backwards",
            "  Ctrl+U       delete to start of line",
            "  Ctrl+K       delete to end of line",
            "  Up/Down      cycle through command history",
            "  PgUp/PgDn    scroll output",
            "  Home/End     jump to top/bottom of scrollback",
            "  Shift+Right  next conversation entry",
            "  Shift+Left   previous conversation entry",
            "  Escape       dismiss conversation overlay",
            "  W/A/S/D      move north/west/south/east (empty input only)",
            "  Backspace    delete char before cursor",
            "  Delete       delete char at cursor",
            "  F1           toggle this help",
            "  Ctrl+C       quit",
            "",
            "Commands (typed into input):",
            "  /quit        quit",
            "  /clear       clear output pane",
            "  /debug       toggle debug logging to mud_*.log",
            "  /info        show info message history",
            "",
            "Notes:",
            "  Debug mode (-d or /debug) logs to mud_*.log files.",
            "  Telnet negotiation is stripped from the display stream.",
            "  GMCP-capable servers will show a stats pane on the right.",
            "  Speech lines (says/tells/whispers) appear in a conversation",
            "  overlay and are filtered from the main feed. Scroll up to",
            "  see the full unfiltered history.",
            "  INFO channel messages appear in a ticker bar above the input",
            "  line and are also viewable via /info.",
            "  ASCII maps from room displays are auto-detected and shown",
            "  in a dedicated pane (bottom-right of output area). A 'map'",
            "  command is sent once after login. Map lines are filtered",
            "  from the main feed.",
        ]
        out_win.erase()
        h, w = out_win.getmaxyx()
        for i, line in enumerate(help_text[:h]):
            try:
                out_win.addnstr(i, 0, line, w - 1)
            except curses.error:
                pass
        out_win.noutrefresh()

        self._draw_stats(stats_win)
        self._draw_map_pane(map_win)
        if ticker_win:
            self._draw_ticker(ticker_win)

        input_win.erase()
        input_win.noutrefresh()

        status_win.erase()
        status = "F1 close help"
        try:
            status_win.addnstr(0, 0, status, status_win.getmaxyx()[1] - 1)
        except curses.error:
            pass
        status_win.noutrefresh()

    def _scroll_up(self):
        # First scroll up from filtered view: switch to full history at bottom
        if self._output_scroll == 0 and not self._show_full_history:
            self._show_full_history = True
            return
        # Already in full history mode: actually scroll up
        page = max(1, self._output_h - 1)
        max_off = max(0, len(self.output_lines) - self._output_h)
        self._output_scroll = min(self._output_scroll + page, max_off)

    def _scroll_down(self):
        # If at bottom of full history view, switch back to filtered view
        if self._output_scroll == 0 and self._show_full_history:
            self._show_full_history = False
            return
        # Otherwise scroll down
        page = max(1, self._output_h - 1)
        self._output_scroll = max(0, self._output_scroll - page)

    def _scroll_to_top(self):
        self._show_full_history = True
        self._output_scroll = max(0, len(self.output_lines) - self._output_h)

    def _scroll_to_bottom(self):
        self._output_scroll = 0
        self._show_full_history = False

    def handle_key(self, ch: int):
        # Returns (line_to_send or None, quit_bool)
        if ch == -1:
            return None, False

        if ch == curses.KEY_F1:
            self._help_mode = not self._help_mode
            return None, False

        # Help pager captures paging keys when visible
        if self.help_tracker.visible:
            screen_h, _ = self.stdscr.getmaxyx()
            # Calculate visible height: pager_h - 4 (borders, title, controls)
            pager_h = min(max(self.HELP_MIN_HEIGHT, screen_h - 4), screen_h - 2)
            visible_h = max(1, pager_h - 4)
            # Scroll by visible height minus 2 lines overlap for context
            scroll_amount = max(1, visible_h - 2)
            if ch == 27:  # ESC - close help
                self.help_tracker.dismiss()
                return None, False
            if ch == curses.KEY_PPAGE:  # PgUp
                self.help_tracker.scroll_up(scroll_amount)
                return None, False
            if ch == curses.KEY_NPAGE:  # PgDn
                self.help_tracker.scroll_down(scroll_amount, visible_h)
                return None, False
            if ch == curses.KEY_HOME:
                self.help_tracker.scroll_to_top()
                return None, False
            if ch == curses.KEY_END:
                self.help_tracker.scroll_to_bottom(visible_h)
                return None, False
            # Other keys (typing, Enter) pass through - user can send commands

        # Conversation overlay keys (before scroll/help guards)
        if ch == 27:  # Escape
            if self.conversation.visible:
                self.conversation.dismiss()
                return None, False
        if ch == curses.KEY_SRIGHT:  # Shift+Right
            if self.conversation.visible:
                self.conversation.navigate_next()
                return None, False
        if ch == curses.KEY_SLEFT:  # Shift+Left
            if self.conversation.visible:
                self.conversation.navigate_prev()
                return None, False

        # Scroll keys work in help mode too
        if ch == curses.KEY_PPAGE:  # Page Up
            self._scroll_up()
            return None, False
        if ch == curses.KEY_NPAGE:  # Page Down
            self._scroll_down()
            return None, False
        if ch == curses.KEY_HOME:
            self._scroll_to_top()
            return None, False
        if ch == curses.KEY_END:
            self._scroll_to_bottom()
            return None, False

        # In help mode, ignore most typing
        if self._help_mode:
            return None, False

        if ch in (curses.KEY_ENTER, 10, 13):
            line = self.input_buf.clear()
            self.history.reset()
            return line, False

        if ch == curses.KEY_UP:
            self.input_buf.set_text(self.history.navigate_up(self.input_buf.text))
            return None, False

        if ch == curses.KEY_DOWN:
            self.input_buf.set_text(self.history.navigate_down(self.input_buf.text))
            return None, False

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            self.input_buf.backspace()
            self.history.reset()
            return None, False

        # Delete key
        if ch == curses.KEY_DC:
            self.input_buf.delete()
            self.history.reset()
            return None, False

        # Cursor movement
        if ch == curses.KEY_LEFT:
            self.input_buf.move_left()
            return None, False

        if ch == curses.KEY_RIGHT:
            self.input_buf.move_right()
            return None, False

        # Ctrl+A — move to start of line
        if ch == 1:
            self.input_buf.move_home()
            return None, False

        # Ctrl+E — move to end of line
        if ch == 5:
            self.input_buf.move_end()
            return None, False

        # Ctrl+Left — move word left
        # Key codes vary by terminal; check keyname for portability
        if ch >= 256:
            try:
                kn = curses.keyname(ch).decode("ascii", errors="ignore")
            except (ValueError, AttributeError):
                kn = ""
            if kn == "kLFT5":
                self.input_buf.move_word_left()
                return None, False
            if kn == "kRIT5":
                self.input_buf.move_word_right()
                return None, False

        # Ctrl+W — delete word backwards
        if ch == 23:
            self.input_buf.kill_word_back()
            self.history.reset()
            return None, False

        # Ctrl+U — delete to start of line
        if ch == 21:
            self.input_buf.kill_to_start()
            self.history.reset()
            return None, False

        # Ctrl+K — delete to end of line
        if ch == 11:
            self.input_buf.kill_to_end()
            self.history.reset()
            return None, False

        # Movement hotkeys: Shift+WASD sends direction commands
        # Only when input buffer is empty and user is logged in
        _MOVE_KEYS = {ord('W'): 'n', ord('A'): 'w', ord('S'): 's', ord('D'): 'e'}
        if (ch in _MOVE_KEYS
                and not self.input_buf.text
                and self.map_tracker.enabled):
            return _MOVE_KEYS[ch], False

        if ch >= 0 and ch < 256:
            c = chr(ch)
            if c.isprintable() or c == "\t":
                self.input_buf.insert(c)
                self.history.reset()
        return None, False

    def show_info_history(self):
        """Dump info message history into the output pane."""
        history = self.info_tracker.history
        if not history:
            self.display_lines.append("-- No info messages --")
            self.output_lines.append("-- No info messages --")
            return
        self.display_lines.append("-- Info History --")
        self.output_lines.append("-- Info History --")
        for entry in history:
            line = f"  {ts_str(entry.timestamp)} | {entry.text}"
            self.display_lines.append(line)
            self.output_lines.append(line)
        self.display_lines.append("-- End Info History --")
        self.output_lines.append("-- End Info History --")

    def clear(self):
        self.output_lines = []
        self.display_lines = []
        self._incomplete_line = ""
        self._output_scroll = 0
        self._show_full_history = False
        self._skip_next_blank = False
        self._skip_blank_after_speech = False
        self.conversation.dismiss()
        self.info_tracker.current = None
        self.info_tracker._queue.clear()
        self.map_tracker.clear()
        self.help_tracker.clear()
