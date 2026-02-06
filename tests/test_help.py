"""Tests for help pager functionality."""

import pytest
from mud_slop.help import HelpTracker, HelpContent


class TestHelpTags:
    """Test {help}/{/help} tag detection and parsing."""

    def test_basic_help_block(self):
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("Test Help Topic", "Test Help Topic"),
            ("{helpbody}", "{helpbody}"),
            ("This is the body text.", "This is the body text."),
            ("Second body line.", "Second body line."),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.visible
        assert tracker.content is not None
        assert tracker.content.title == "Test Help Topic"
        assert tracker.content.header_lines == ["Test Help Topic"]
        assert tracker.content.body_lines == [
            "This is the body text.",
            "Second body line.",
        ]

    def test_header_with_metadata(self):
        """Test that header lines before {helpbody} are captured."""
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("----------------------------------------------------------------------------", "----------------------------------------------------------------------------"),
            ("{helpkeywords}Help Keywords : Stats.", "{helpkeywords}Help Keywords : Stats."),
            ("Help Category : Information.", "Help Category : Information."),
            ("Related Helps : Foo, Bar.", "Related Helps : Foo, Bar."),
            ("----------------------------------------------------------------------------", "----------------------------------------------------------------------------"),
            ("{helpbody}", "{helpbody}"),
            ("Body content here.", "Body content here."),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        # Title should be first non-separator line (with {helpkeywords} stripped)
        assert tracker.content.title == "Help Keywords : Stats."
        # Header should have all lines with {helpkeywords} tag stripped
        assert len(tracker.content.header_lines) == 5
        assert "Help Keywords : Stats." in tracker.content.header_lines[1]
        assert "{helpkeywords}" not in tracker.content.header_lines[1]
        assert tracker.content.body_lines == ["Body content here."]

    def test_help_with_tags(self):
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("Spell Help", "Spell Help"),
            ("{helpbody}", "{helpbody}"),
            ("Fireball spell info.", "Fireball spell info."),
            ("{/helpbody}", "{/helpbody}"),
            ("{helptags}fireball, magic, spells", "{helptags}fireball, magic, spells"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        assert tracker.content.tags == ["fireball", "magic", "spells"]

    def test_help_consumed_lines(self):
        tracker = HelpTracker()
        # All lines inside {help} block should be consumed
        assert tracker.feed_line("{help}", "{help}") == (True, [])
        assert tracker.feed_line("Title", "Title") == (True, [])
        assert tracker.feed_line("{helpbody}", "{helpbody}") == (True, [])
        assert tracker.feed_line("Body text", "Body text") == (True, [])
        assert tracker.feed_line("{/helpbody}", "{/helpbody}") == (True, [])
        assert tracker.feed_line("{/help}", "{/help}") == (True, [])

    def test_lines_outside_help_not_consumed(self):
        tracker = HelpTracker()
        # Lines outside should not be consumed
        assert tracker.feed_line("Normal text", "Normal text") == (False, [])
        assert tracker.feed_line("More text", "More text") == (False, [])

    def test_help_block_shows_overlay(self):
        tracker = HelpTracker()
        assert not tracker.visible
        tracker.feed_line("{help}", "{help}")
        tracker.feed_line("Title", "Title")
        tracker.feed_line("{helpbody}", "{helpbody}")
        tracker.feed_line("Body", "Body")
        tracker.feed_line("{/helpbody}", "{/helpbody}")
        assert not tracker.visible  # Not yet visible
        tracker.feed_line("{/help}", "{/help}")
        assert tracker.visible  # Now visible

    def test_default_title_when_empty(self):
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("{helpbody}", "{helpbody}"),
            ("Just body", "Just body"),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        assert tracker.content.title == "Help"  # Default title

    def test_ansi_preserved_in_body(self):
        tracker = HelpTracker()
        ansi_line = "\x1b[1;32mGreen bold text\x1b[0m"
        lines = [
            ("{help}", "{help}"),
            ("ANSI Test", "ANSI Test"),
            ("{helpbody}", "{helpbody}"),
            ("Green bold text", ansi_line),  # plain vs raw
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        assert tracker.content.body_lines[0] == ansi_line


class TestScrolling:
    """Test help pager scrolling functionality."""

    def test_scroll_down(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 100, [])
        tracker.visible = True
        tracker.scroll_offset = 0
        tracker._wrapped_line_count = 100

        tracker.scroll_down(20)
        assert tracker.scroll_offset == 20

        tracker.scroll_down(20)
        assert tracker.scroll_offset == 40

    def test_scroll_down_capped(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 50, [])
        tracker.visible = True
        tracker.scroll_offset = 0
        tracker._wrapped_line_count = 50

        tracker.scroll_down(30)
        assert tracker.scroll_offset == 20  # max_offset = 50 - 30 = 20

    def test_scroll_up(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 100, [])
        tracker.visible = True
        tracker.scroll_offset = 40
        tracker._wrapped_line_count = 100

        tracker.scroll_up(20)
        assert tracker.scroll_offset == 20

        tracker.scroll_up(20)
        assert tracker.scroll_offset == 0

    def test_scroll_up_capped_at_zero(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 100, [])
        tracker.visible = True
        tracker.scroll_offset = 10
        tracker._wrapped_line_count = 100

        tracker.scroll_up(20)
        assert tracker.scroll_offset == 0

    def test_scroll_to_top(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 100, [])
        tracker.visible = True
        tracker.scroll_offset = 50
        tracker._wrapped_line_count = 100

        tracker.scroll_to_top()
        assert tracker.scroll_offset == 0

    def test_scroll_to_bottom(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["line"] * 100, [])
        tracker.visible = True
        tracker.scroll_offset = 0
        tracker._wrapped_line_count = 100

        tracker.scroll_to_bottom(30)
        assert tracker.scroll_offset == 70  # 100 - 30 = 70

    def test_scroll_with_wrapped_lines(self):
        """Test scrolling uses wrapped line count, not raw body lines."""
        tracker = HelpTracker()
        # 10 raw lines, but UI says they wrap to 25 display lines
        tracker.content = HelpContent("Title", [], ["line"] * 10, [])
        tracker.visible = True
        tracker.scroll_offset = 0
        tracker._wrapped_line_count = 25

        tracker.scroll_to_bottom(10)
        assert tracker.scroll_offset == 15  # 25 - 10 = 15


class TestDismiss:
    """Test help overlay dismiss functionality."""

    def test_dismiss_hides_overlay(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["body"], [])
        tracker.visible = True

        tracker.dismiss()
        assert not tracker.visible

    def test_dismiss_keeps_content(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", [], ["body"], [])
        tracker.visible = True

        tracker.dismiss()
        assert tracker.content is not None  # Content preserved


class TestClear:
    """Test help tracker clear functionality."""

    def test_clear_resets_all(self):
        tracker = HelpTracker()
        tracker.content = HelpContent("Title", ["header"], ["body"], ["tag"])
        tracker.visible = True
        tracker.scroll_offset = 10
        tracker._wrapped_line_count = 50
        tracker._in_help_block = True
        tracker._in_body_block = True
        tracker._header_lines = ["header"]
        tracker._body_lines = ["accumulated"]
        tracker._tags = ["tag"]
        tracker._title = "Test"

        tracker.clear()

        assert tracker.content is None
        assert not tracker.visible
        assert tracker.scroll_offset == 0
        assert tracker._wrapped_line_count == 0
        assert not tracker._in_help_block
        assert not tracker._in_body_block
        assert tracker._header_lines == []
        assert tracker._body_lines == []
        assert tracker._tags == []
        assert tracker._title == ""


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_body(self):
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("Title", "Title"),
            ("{helpbody}", "{helpbody}"),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        assert tracker.content.body_lines == []

    def test_empty_helptags(self):
        tracker = HelpTracker()
        lines = [
            ("{help}", "{help}"),
            ("Title", "Title"),
            ("{helpbody}", "{helpbody}"),
            ("Body", "Body"),
            ("{/helpbody}", "{/helpbody}"),
            ("{helptags}", "{helptags}"),
            ("{/help}", "{/help}"),
        ]
        for plain, raw in lines:
            tracker.feed_line(plain, raw)

        assert tracker.content is not None
        assert tracker.content.tags == []

    def test_consecutive_help_blocks(self):
        tracker = HelpTracker()
        # First block
        for plain, raw in [
            ("{help}", "{help}"),
            ("First", "First"),
            ("{helpbody}", "{helpbody}"),
            ("Body 1", "Body 1"),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]:
            tracker.feed_line(plain, raw)

        assert tracker.content.title == "First"
        tracker.dismiss()

        # Second block
        for plain, raw in [
            ("{help}", "{help}"),
            ("Second", "Second"),
            ("{helpbody}", "{helpbody}"),
            ("Body 2", "Body 2"),
            ("{/helpbody}", "{/helpbody}"),
            ("{/help}", "{/help}"),
        ]:
            tracker.feed_line(plain, raw)

        assert tracker.content.title == "Second"
        assert tracker.content.body_lines == ["Body 2"]

    def test_scroll_with_no_content(self):
        tracker = HelpTracker()
        # Should not crash
        tracker.scroll_down(20)
        tracker.scroll_up(20)
        tracker.scroll_to_top()
        tracker.scroll_to_bottom(20)
