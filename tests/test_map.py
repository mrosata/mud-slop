"""Tests for MapTracker tag-based map detection (<MAPSTART>/<MAPEND>)."""

import pytest
from typing import List, Optional, Tuple

from mud_client.map import MapTracker
from mud_client.ansi import strip_ansi


# --- Helper factories ---

def _map_block(room_name: str, map_lines: List[str], exits: str = "N S E W") -> List[Tuple[str, str]]:
    """Build a complete map block as (plain, raw) pairs."""
    lines = []
    lines.append(("<MAPSTART>", "<MAPSTART>"))
    lines.append((room_name, room_name))
    lines.append(("", ""))  # blank line after title
    for ml in map_lines:
        lines.append((ml, ml))
    lines.append((f"[ Exits: {exits} ]", f"[ Exits: {exits} ]"))
    lines.append(("<MAPEND>", "<MAPEND>"))
    return lines


def _rdesc_block(desc_lines: List[str]) -> List[Tuple[str, str]]:
    """Build a room description block as (plain, raw) pairs."""
    lines = []
    lines.append(("{rdesc}", "{rdesc}"))
    for desc in desc_lines:
        lines.append((desc, desc))
    lines.append(("{/rdesc}", "{/rdesc}"))
    return lines


def _structural_map() -> List[str]:
    """Return standard structural map lines."""
    return [
        "  +---+---+---+  ",
        "  |   |   | * |  ",
        "  +---+---+---+  ",
        "  |       |   |  ",
        "  +---+---+---+  ",
        "  |   |   |   |  ",
        "  +---+---+---+  ",
    ]


# --- Tag-based parsing tests ---

class TestMapStartEnd:
    def _make_tracker(self) -> MapTracker:
        mt = MapTracker()
        mt.enabled = True
        return mt

    def test_basic_map_block(self):
        """<MAPSTART>...<MAPEND> block is captured correctly."""
        mt = self._make_tracker()
        block = _map_block("Test Room", _structural_map(), exits="N S")

        for plain, raw in block:
            consumed, overflow = mt.feed_line(plain, raw)
            assert consumed
            assert overflow == []

        assert mt.room_name == "Test Room"
        assert len(mt.map_lines) > 0
        assert mt.exits == "[ Exits: N S ]"

    def test_room_name_extracted(self):
        """First non-empty line after <MAPSTART> becomes room name."""
        mt = self._make_tracker()
        block = _map_block("Grand Hall", _structural_map())

        for plain, raw in block:
            mt.feed_line(plain, raw)

        assert mt.room_name == "Grand Hall"

    def test_exits_extracted(self):
        """Exits line is detected and stored."""
        mt = self._make_tracker()
        block = _map_block("Exit Room", _structural_map(), exits="E W U D")

        for plain, raw in block:
            mt.feed_line(plain, raw)

        assert "E W U D" in mt.exits

    def test_coords_after_mapend(self):
        """Coordinates line after <MAPEND> is captured."""
        mt = self._make_tracker()
        block = _map_block("Coord Room", _structural_map())

        for plain, raw in block:
            mt.feed_line(plain, raw)

        # Feed coords line after the block
        consumed, _ = mt.feed_line("{coords}10,20,30", "{coords}10,20,30")
        assert consumed
        assert mt.coords == "10,20,30"

    def test_coords_overwritten_by_new_block(self):
        """New map block's coords replace old coords."""
        mt = self._make_tracker()

        # First block
        block1 = _map_block("Room 1", _structural_map())
        for plain, raw in block1:
            mt.feed_line(plain, raw)
        mt.feed_line("{coords}1,1,1", "{coords}1,1,1")
        assert mt.coords == "1,1,1"

        # Second block
        block2 = _map_block("Room 2", _structural_map())
        for plain, raw in block2:
            mt.feed_line(plain, raw)
        mt.feed_line("{coords}2,2,2", "{coords}2,2,2")
        assert mt.coords == "2,2,2"
        assert mt.room_name == "Room 2"

    def test_description_lines(self):
        """Description lines from {rdesc} tags are captured."""
        mt = self._make_tracker()

        # First, send the map block
        block = _map_block("Described Room", _structural_map())
        for plain, raw in block:
            mt.feed_line(plain, raw)

        # Then send the room description via {rdesc} tags
        mt.feed_line("{rdesc}", "{rdesc}")
        mt.feed_line("A grand hall with marble columns.", "A grand hall with marble columns.")
        mt.feed_line("{/rdesc}", "{/rdesc}")

        assert mt.room_name == "Described Room"
        assert len(mt.room_desc) == 1
        assert "marble columns" in strip_ansi(mt.room_desc[0])

    def test_lines_outside_block_not_consumed(self):
        """Lines outside <MAPSTART>/<MAPEND> are not consumed."""
        mt = self._make_tracker()

        consumed, _ = mt.feed_line("Regular text.", "Regular text.")
        assert not consumed

        consumed, _ = mt.feed_line("More regular text.", "More regular text.")
        assert not consumed

    def test_mapstart_starts_accumulation(self):
        """<MAPSTART> line itself is consumed and starts accumulation."""
        mt = self._make_tracker()

        consumed, _ = mt.feed_line("<MAPSTART>", "<MAPSTART>")
        assert consumed
        assert mt._in_map_block

    def test_mapend_stops_accumulation(self):
        """<MAPEND> line is consumed and finalizes the block."""
        mt = self._make_tracker()

        # Start block
        mt.feed_line("<MAPSTART>", "<MAPSTART>")
        mt.feed_line("Room Name", "Room Name")
        for ml in _structural_map():
            mt.feed_line(ml, ml)
        mt.feed_line("[ Exits: N ]", "[ Exits: N ]")

        consumed, _ = mt.feed_line("<MAPEND>", "<MAPEND>")
        assert consumed
        assert not mt._in_map_block
        assert mt.room_name == "Room Name"

    def test_disabled_tracker_ignores_all(self):
        """When disabled, all lines pass through."""
        mt = MapTracker()  # enabled = False by default

        consumed, _ = mt.feed_line("<MAPSTART>", "<MAPSTART>")
        assert not consumed

        consumed, _ = mt.feed_line("Room", "Room")
        assert not consumed

        consumed, _ = mt.feed_line("<MAPEND>", "<MAPEND>")
        assert not consumed


class TestClear:
    def test_clear_resets_all(self):
        """clear() resets all state including coords."""
        mt = MapTracker()
        mt.enabled = True

        block = _map_block("Clear Room", _structural_map())
        for plain, raw in block:
            mt.feed_line(plain, raw)
        mt.feed_line("{coords}5,5,5", "{coords}5,5,5")

        assert mt.room_name == "Clear Room"
        assert mt.map_lines
        assert mt.coords == "5,5,5"

        mt.clear()

        assert mt.room_name == ""
        assert mt.room_name_raw == ""
        assert mt.room_desc == []
        assert mt.map_lines == []
        assert mt.coords == ""
        assert mt.exits == ""
        assert not mt._in_map_block


class TestEdgeCases:
    def _make_tracker(self) -> MapTracker:
        mt = MapTracker()
        mt.enabled = True
        return mt

    def test_empty_block(self):
        """Empty block (no lines between tags) doesn't crash."""
        mt = self._make_tracker()

        mt.feed_line("<MAPSTART>", "<MAPSTART>")
        mt.feed_line("<MAPEND>", "<MAPEND>")

        assert mt.room_name == ""
        assert mt.map_lines == []

    def test_block_with_only_title(self):
        """Block with only a title line."""
        mt = self._make_tracker()

        mt.feed_line("<MAPSTART>", "<MAPSTART>")
        mt.feed_line("Lonely Room", "Lonely Room")
        mt.feed_line("<MAPEND>", "<MAPEND>")

        assert mt.room_name == "Lonely Room"
        assert mt.map_lines == []

    def test_ansi_in_room_name(self):
        """Room name with ANSI codes is handled correctly."""
        mt = self._make_tracker()
        room_raw = "\x1b[1;32mColored Room\x1b[0m"

        mt.feed_line("<MAPSTART>", "<MAPSTART>")
        mt.feed_line(strip_ansi(room_raw), room_raw)
        for ml in _structural_map():
            mt.feed_line(ml, ml)
        mt.feed_line("[ Exits: N ]", "[ Exits: N ]")
        mt.feed_line("<MAPEND>", "<MAPEND>")

        assert mt.room_name == "Colored Room"
        assert "\x1b[1;32m" in mt.room_name_raw

    def test_coords_without_block(self):
        """Coords line without a map block is still captured."""
        mt = self._make_tracker()

        consumed, _ = mt.feed_line("{coords}0,0,0", "{coords}0,0,0")
        assert consumed
        assert mt.coords == "0,0,0"

    def test_consecutive_blocks(self):
        """Multiple consecutive map blocks are handled correctly."""
        mt = self._make_tracker()

        # First block
        block1 = _map_block("Room One", _structural_map())
        for plain, raw in block1:
            mt.feed_line(plain, raw)
        assert mt.room_name == "Room One"

        # Second block immediately after
        block2 = _map_block("Room Two", _structural_map())
        for plain, raw in block2:
            mt.feed_line(plain, raw)
        assert mt.room_name == "Room Two"

    def test_exits_variations(self):
        """Various exit line formats are recognized."""
        mt = self._make_tracker()

        # Test case-insensitive matching
        exits_formats = [
            "[ Exits: N S E W ]",
            "[Exits: N]",
            "  Exits: N S  ",
        ]

        for exits in exits_formats:
            mt._in_map_block = True
            mt._block_lines = [
                ("Room", "Room"),
                ("  |---|  ", "  |---|  "),
                (exits, exits),
            ]
            mt._finalize_block()
            assert exits.strip() in mt.exits or "Exits" in mt.exits

    def test_rdesc_tags_captured(self):
        """Room description from {rdesc} tags is captured."""
        mt = self._make_tracker()

        # Send rdesc block
        consumed, _ = mt.feed_line("{rdesc}", "{rdesc}")
        assert consumed
        assert mt._in_rdesc_block

        consumed, _ = mt.feed_line("A beautiful room.", "A beautiful room.")
        assert consumed

        consumed, _ = mt.feed_line("With ornate decorations.", "With ornate decorations.")
        assert consumed

        consumed, _ = mt.feed_line("{/rdesc}", "{/rdesc}")
        assert consumed
        assert not mt._in_rdesc_block

        # Consecutive non-empty lines are joined into a single paragraph
        assert len(mt.room_desc) == 1
        assert "beautiful room" in mt.room_desc[0]
        assert "ornate decorations" in mt.room_desc[0]

    def test_rdesc_updates_on_new_room(self):
        """New rdesc block replaces previous description."""
        mt = self._make_tracker()

        # First description
        for plain, raw in _rdesc_block(["Old description."]):
            mt.feed_line(plain, raw)
        assert "Old description" in mt.room_desc[0]

        # Second description replaces first
        for plain, raw in _rdesc_block(["New description."]):
            mt.feed_line(plain, raw)
        assert len(mt.room_desc) == 1
        assert "New description" in mt.room_desc[0]

    def test_room_name_after_mapend(self):
        """Room name line after <MAPEND> is captured."""
        mt = self._make_tracker()

        # Send map block
        block = _map_block("Simple Room", _structural_map())
        for plain, raw in block:
            mt.feed_line(plain, raw)

        # After <MAPEND>, blank line then room name with ID
        consumed, _ = mt.feed_line("", "")
        assert consumed  # blank line consumed while expecting room name

        consumed, _ = mt.feed_line("The Academy Clinic (G) (123)", "The Academy Clinic (G) (123)")
        assert consumed
        assert mt.room_name == "The Academy Clinic"  # without the (G) and (123) parts

    def test_room_name_without_markers(self):
        """Room name without (G) or ID markers is captured."""
        mt = self._make_tracker()

        block = _map_block("Simple Room", _structural_map())
        for plain, raw in block:
            mt.feed_line(plain, raw)

        consumed, _ = mt.feed_line("Hallway in the Academy", "Hallway in the Academy")
        assert consumed
        assert mt.room_name == "Hallway in the Academy"

    def test_room_name_with_id_only(self):
        """Room name with just room ID (no G marker) is captured."""
        mt = self._make_tracker()

        block = _map_block("Simple Room", _structural_map())
        for plain, raw in block:
            mt.feed_line(plain, raw)

        consumed, _ = mt.feed_line("Hallway in the Academy (624)", "Hallway in the Academy (624)")
        assert consumed
        assert mt.room_name == "Hallway in the Academy"
