"""UI-agnostic menu bar data model, state machine, and navigation.

No mud_slop imports — this module sits at Layer 0 of the dependency graph
and can be tested without curses or any other project module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class MenuItemType(Enum):
    ACTION = auto()
    TOGGLE = auto()
    CHOICE = auto()
    SEPARATOR = auto()


class MenuState(Enum):
    CLOSED = auto()
    OPEN = auto()
    SUBMENU = auto()


@dataclass
class ChoiceOption:
    label: str
    value: str
    selected: bool = False


@dataclass
class MenuItem:
    item_type: MenuItemType
    label: str = ""
    action_id: str = ""
    enabled: bool = True
    hotkey: str = ""
    toggled: bool = False
    choices: list[ChoiceOption] = field(default_factory=list)
    selected_index: int = 0
    choices_supplier: Callable[[], list[tuple[str, str]]] | None = None


@dataclass
class Menu:
    title: str
    shortcut_key: str
    items: list[MenuItem] = field(default_factory=list)

    def width(self) -> int:
        """Minimum width needed to render this menu's dropdown."""
        w = 0
        for item in self.items:
            if item.item_type == MenuItemType.SEPARATOR:
                continue
            label_w = len(item.label)
            if item.item_type == MenuItemType.TOGGLE:
                label_w += 4  # "[x] " or "[ ] "
            if item.item_type == MenuItemType.CHOICE:
                label_w += 2  # " >"
            if item.hotkey:
                label_w += len(item.hotkey) + 2  # "  hotkey"
            w = max(w, label_w)
        return w + 4  # 2 padding each side


class MenuBar:
    def __init__(self, menus: list[Menu] | None = None):
        self.menus: list[Menu] = menus or []
        self.state: MenuState = MenuState.CLOSED
        self.active_menu: int = 0
        self.active_item: int = 0
        self.active_choice: int = 0
        self.on_select: Callable[[str, Any], None] | None = None

    @property
    def is_open(self) -> bool:
        return self.state != MenuState.CLOSED

    # --- Public API ---

    def open_menu(self, idx: int) -> None:
        """Open a top-level menu by index."""
        if idx < 0 or idx >= len(self.menus):
            return
        self.active_menu = idx
        self.state = MenuState.OPEN
        self._refresh_choices()
        self.active_item = self._first_selectable()

    def close(self) -> None:
        self.state = MenuState.CLOSED

    def toggle_menu(self, idx: int) -> None:
        """Open menu if closed (or different menu), close if same menu is open."""
        if self.is_open and self.active_menu == idx:
            self.close()
        else:
            self.open_menu(idx)

    def move_up(self) -> None:
        if self.state == MenuState.SUBMENU:
            self._submenu_move(-1)
        elif self.state == MenuState.OPEN:
            self._dropdown_move(-1)

    def move_down(self) -> None:
        if self.state == MenuState.SUBMENU:
            self._submenu_move(1)
        elif self.state == MenuState.OPEN:
            self._dropdown_move(1)

    def move_left(self) -> None:
        if self.state == MenuState.SUBMENU:
            # Close submenu, go back to dropdown
            self.state = MenuState.OPEN
        elif self.state == MenuState.OPEN:
            # Cycle to previous top-level menu
            idx = (self.active_menu - 1) % len(self.menus)
            self.open_menu(idx)

    def move_right(self) -> None:
        if self.state == MenuState.SUBMENU:
            # Cycle to next top-level menu (close submenu)
            idx = (self.active_menu + 1) % len(self.menus)
            self.open_menu(idx)
        elif self.state == MenuState.OPEN:
            item = self._current_item()
            if item and item.item_type == MenuItemType.CHOICE and item.enabled:
                self._open_submenu()
            else:
                # Cycle to next top-level menu
                idx = (self.active_menu + 1) % len(self.menus)
                self.open_menu(idx)

    def select(self) -> None:
        """Activate the currently highlighted item."""
        if self.state == MenuState.SUBMENU:
            self._select_choice()
        elif self.state == MenuState.OPEN:
            item = self._current_item()
            if not item or not item.enabled:
                return
            if item.item_type == MenuItemType.ACTION:
                self.close()
                if self.on_select:
                    self.on_select(item.action_id, None)
            elif item.item_type == MenuItemType.TOGGLE:
                item.toggled = not item.toggled
                if self.on_select:
                    self.on_select(item.action_id, item.toggled)
            elif item.item_type == MenuItemType.CHOICE:
                self._open_submenu()

    def handle_alt_key(self, char: str) -> bool:
        """Handle an Alt+<char> keypress. Returns True if consumed."""
        char_lower = char.lower()
        for i, menu in enumerate(self.menus):
            if menu.shortcut_key.lower() == char_lower:
                self.toggle_menu(i)
                return True
        return False

    # --- Hit-testing ---

    def hit_test_bar(self, x: int) -> int | None:
        """Given an x coordinate on row 0, return the menu index or None."""
        col = 1  # starts after 1 char padding
        for i, menu in enumerate(self.menus):
            label_w = len(menu.title) + 2  # 1 padding each side
            if col <= x < col + label_w:
                return i
            col += label_w + 1  # 1 gap between menus
        return None

    def dropdown_position(self) -> tuple[int, int]:
        """Return (row, col) for the top-left of the active dropdown."""
        col = 1
        for i in range(self.active_menu):
            col += len(self.menus[i].title) + 3  # 2 padding + 1 gap
        return (1, col)

    def hit_test_dropdown(self, x: int, y: int) -> int | None:
        """Given screen coordinates, return the item index or None.

        Returns None for separators and out-of-bounds.
        """
        if self.state == MenuState.CLOSED:
            return None
        menu = self.menus[self.active_menu]
        row, col = self.dropdown_position()
        w = menu.width()

        # Check bounds
        if x < col or x >= col + w:
            return None
        # y=row is top border, items start at row+1
        item_y = y - (row + 1)
        if item_y < 0 or item_y >= len(menu.items):
            return None
        item = menu.items[item_y]
        if item.item_type == MenuItemType.SEPARATOR or not item.enabled:
            return None
        return item_y

    def submenu_position(self) -> tuple[int, int]:
        """Return (row, col) for the top-left of the active submenu."""
        d_row, d_col = self.dropdown_position()
        menu = self.menus[self.active_menu]
        w = menu.width()
        # Submenu appears to the right of the dropdown, aligned with the active item
        return (d_row + 1 + self.active_item, d_col + w)

    def hit_test_submenu(self, x: int, y: int) -> int | None:
        """Given screen coordinates, return the choice index or None."""
        if self.state != MenuState.SUBMENU:
            return None
        item = self._current_item()
        if not item or not item.choices:
            return None
        s_row, s_col = self.submenu_position()
        # Submenu width based on longest choice label
        s_w = max(len(c.label) for c in item.choices) + 6  # "  * label  "
        if x < s_col or x >= s_col + s_w:
            return None
        choice_y = y - (s_row + 1)  # +1 for top border
        if choice_y < 0 or choice_y >= len(item.choices):
            return None
        return choice_y

    def dropdown_rect(self) -> tuple[int, int, int, int]:
        """Return (row, col, height, width) of the dropdown."""
        row, col = self.dropdown_position()
        menu = self.menus[self.active_menu]
        w = menu.width()
        h = len(menu.items) + 2  # +2 for borders
        return (row, col, h, w)

    def submenu_rect(self) -> tuple[int, int, int, int]:
        """Return (row, col, height, width) of the submenu."""
        s_row, s_col = self.submenu_position()
        item = self._current_item()
        if not item or not item.choices:
            return (s_row, s_col, 0, 0)
        s_w = max(len(c.label) for c in item.choices) + 6
        s_h = len(item.choices) + 2  # +2 for borders
        return (s_row, s_col, s_h, s_w)

    # --- Internal helpers ---

    def _current_item(self) -> MenuItem | None:
        menu = self.menus[self.active_menu]
        if 0 <= self.active_item < len(menu.items):
            return menu.items[self.active_item]
        return None

    def _first_selectable(self) -> int:
        menu = self.menus[self.active_menu]
        for i, item in enumerate(menu.items):
            if item.item_type != MenuItemType.SEPARATOR and item.enabled:
                return i
        return 0

    def _dropdown_move(self, direction: int) -> None:
        menu = self.menus[self.active_menu]
        n = len(menu.items)
        if n == 0:
            return
        idx = self.active_item
        for _ in range(n):
            idx = (idx + direction) % n
            item = menu.items[idx]
            if item.item_type != MenuItemType.SEPARATOR and item.enabled:
                self.active_item = idx
                return

    def _submenu_move(self, direction: int) -> None:
        item = self._current_item()
        if not item or not item.choices:
            return
        n = len(item.choices)
        self.active_choice = (self.active_choice + direction) % n

    def _open_submenu(self) -> None:
        item = self._current_item()
        if not item or item.item_type != MenuItemType.CHOICE:
            return
        self.state = MenuState.SUBMENU
        # Position active_choice on the currently selected option
        for i, c in enumerate(item.choices):
            if c.selected:
                self.active_choice = i
                return
        self.active_choice = 0

    def _select_choice(self) -> None:
        item = self._current_item()
        if not item or not item.choices:
            return
        if self.active_choice < 0 or self.active_choice >= len(item.choices):
            return
        choice = item.choices[self.active_choice]
        # Update selection state
        for c in item.choices:
            c.selected = False
        choice.selected = True
        item.selected_index = self.active_choice
        # Go back to dropdown (not closed — user may want more changes)
        self.state = MenuState.OPEN
        if self.on_select:
            self.on_select(item.action_id, choice.value)

    def _refresh_choices(self) -> None:
        """Refresh dynamic choices for all items in the active menu."""
        menu = self.menus[self.active_menu]
        for item in menu.items:
            if item.choices_supplier and item.item_type == MenuItemType.CHOICE:
                new_choices = item.choices_supplier()
                # Preserve current selection if possible
                current_value = None
                for c in item.choices:
                    if c.selected:
                        current_value = c.value
                        break
                item.choices = [
                    ChoiceOption(label=label, value=value, selected=(value == current_value))
                    for label, value in new_choices
                ]
                # If nothing selected, select first
                if not any(c.selected for c in item.choices) and item.choices:
                    item.choices[0].selected = True
