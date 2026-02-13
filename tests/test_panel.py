"""Tests for the right panel mode toggle feature."""

from __future__ import annotations

from mud_slop.info import InfoTracker
from mud_slop.map import MapTracker


class FakeUI:
    """Minimal stand-in for MudUI to test panel logic without curses."""

    def __init__(self):
        self.RIGHT_PANEL_MODES = ["map", "info"]
        self.right_panel_mode = "map"
        self._info_panel_scroll = 0
        self.info_tracker = InfoTracker()
        self.map_tracker = MapTracker()

    def _has_map(self) -> bool:
        return bool(self.map_tracker.map_lines)

    def _has_panel_content(self) -> bool:
        if self.right_panel_mode == "map":
            return self._has_map()
        elif self.right_panel_mode == "info":
            return bool(self.info_tracker.history)
        return False

    def _cycle_panel_mode(self):
        idx = self.RIGHT_PANEL_MODES.index(self.right_panel_mode)
        self.right_panel_mode = self.RIGHT_PANEL_MODES[(idx + 1) % len(self.RIGHT_PANEL_MODES)]
        self._info_panel_scroll = 0

    def add_system_message(self, text: str):
        self._last_message = text


class TestHasPanelContent:
    def test_map_mode_no_map(self):
        ui = FakeUI()
        assert ui.right_panel_mode == "map"
        assert not ui._has_panel_content()

    def test_map_mode_with_map(self):
        ui = FakeUI()
        ui.map_tracker.map_lines = ["  X  "]
        assert ui._has_panel_content()

    def test_info_mode_no_history(self):
        ui = FakeUI()
        ui.right_panel_mode = "info"
        assert not ui._has_panel_content()

    def test_info_mode_with_history(self):
        ui = FakeUI()
        ui.right_panel_mode = "info"
        ui.info_tracker.add("INFO: test", "INFO: test")
        assert ui._has_panel_content()

    def test_unknown_mode_returns_false(self):
        ui = FakeUI()
        ui.right_panel_mode = "unknown"
        assert not ui._has_panel_content()


class TestCyclePanelMode:
    def test_map_to_info(self):
        ui = FakeUI()
        ui._cycle_panel_mode()
        assert ui.right_panel_mode == "info"

    def test_info_to_map(self):
        ui = FakeUI()
        ui.right_panel_mode = "info"
        ui._cycle_panel_mode()
        assert ui.right_panel_mode == "map"

    def test_cycle_wraps(self):
        ui = FakeUI()
        # Cycle through all modes and back
        for _ in range(len(ui.RIGHT_PANEL_MODES)):
            ui._cycle_panel_mode()
        assert ui.right_panel_mode == "map"

    def test_cycle_resets_scroll(self):
        ui = FakeUI()
        ui._info_panel_scroll = 10
        ui._cycle_panel_mode()
        assert ui._info_panel_scroll == 0


class TestPanelCommand:
    """Test the /panel command handler from app.py."""

    def _handle(self, ui, cmd):
        from mud_slop.app import _handle_panel_cmd

        _handle_panel_cmd(ui, cmd)

    def test_panel_show_current(self):
        ui = FakeUI()
        self._handle(ui, "/panel")
        assert "map" in ui._last_message

    def test_panel_switch_to_info(self):
        ui = FakeUI()
        self._handle(ui, "/panel info")
        assert ui.right_panel_mode == "info"
        assert "info" in ui._last_message

    def test_panel_switch_to_map(self):
        ui = FakeUI()
        ui.right_panel_mode = "info"
        self._handle(ui, "/panel map")
        assert ui.right_panel_mode == "map"

    def test_panel_next(self):
        ui = FakeUI()
        self._handle(ui, "/panel next")
        assert ui.right_panel_mode == "info"

    def test_panel_next_wraps(self):
        ui = FakeUI()
        ui.right_panel_mode = "info"
        self._handle(ui, "/panel next")
        assert ui.right_panel_mode == "map"

    def test_panel_invalid(self):
        ui = FakeUI()
        self._handle(ui, "/panel bogus")
        assert "Unknown panel" in ui._last_message
        assert ui.right_panel_mode == "map"  # unchanged

    def test_panel_resets_scroll(self):
        ui = FakeUI()
        ui._info_panel_scroll = 5
        self._handle(ui, "/panel info")
        assert ui._info_panel_scroll == 0

    def test_panel_case_insensitive(self):
        ui = FakeUI()
        self._handle(ui, "/panel INFO")
        assert ui.right_panel_mode == "info"


class TestInfoPanelScroll:
    def test_scroll_clamps_at_zero(self):
        ui = FakeUI()
        ui._info_panel_scroll = 2
        ui._info_panel_scroll = max(0, ui._info_panel_scroll - 5)
        assert ui._info_panel_scroll == 0

    def test_scroll_increments(self):
        ui = FakeUI()
        ui._info_panel_scroll += 3
        assert ui._info_panel_scroll == 3
