"""Tests for the UI-agnostic menu model."""

from mud_slop.menu import (
    ChoiceOption,
    Menu,
    MenuBar,
    MenuItem,
    MenuItemType,
    MenuState,
)


def _make_file_menu():
    return Menu(
        title="File",
        shortcut_key="f",
        items=[
            MenuItem(
                item_type=MenuItemType.ACTION, label="Quit", action_id="quit", hotkey="Ctrl+C"
            ),
        ],
    )


def _make_settings_menu():
    return Menu(
        title="Settings",
        shortcut_key="s",
        items=[
            MenuItem(
                item_type=MenuItemType.CHOICE,
                label="Config: default",
                action_id="config",
                choices=[
                    ChoiceOption("default", "default", selected=True),
                    ChoiceOption("aardwolf", "aardwolf"),
                ],
            ),
            MenuItem(
                item_type=MenuItemType.CHOICE,
                label="Profile: (none)",
                action_id="profile",
                choices=[
                    ChoiceOption("(none)", "", selected=True),
                    ChoiceOption("mychar", "mychar"),
                ],
            ),
            MenuItem(item_type=MenuItemType.SEPARATOR),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="Color",
                action_id="color",
                toggled=True,
            ),
            MenuItem(
                item_type=MenuItemType.CHOICE,
                label="Conv Position",
                action_id="conv_pos",
                choices=[
                    ChoiceOption("top-left", "top-left"),
                    ChoiceOption("top-center", "top-center"),
                    ChoiceOption("top-right", "top-right"),
                    ChoiceOption("bottom-left", "bottom-left"),
                    ChoiceOption("bottom-center", "bottom-center"),
                    ChoiceOption("bottom-right", "bottom-right", selected=True),
                ],
            ),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="Debug",
                action_id="debug",
                toggled=False,
            ),
            MenuItem(item_type=MenuItemType.SEPARATOR),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="History: Conversations",
                action_id="history_conversations",
                toggled=True,
            ),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="History: Help",
                action_id="history_help",
                toggled=False,
            ),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="History: Maps",
                action_id="history_maps",
                toggled=False,
            ),
            MenuItem(
                item_type=MenuItemType.TOGGLE,
                label="History: Info",
                action_id="history_info",
                toggled=False,
            ),
        ],
    )


def _make_bar():
    bar = MenuBar([_make_file_menu(), _make_settings_menu()])
    return bar


class TestMenuState:
    def test_initial_state_is_closed(self):
        bar = _make_bar()
        assert bar.state == MenuState.CLOSED
        assert not bar.is_open

    def test_open_menu(self):
        bar = _make_bar()
        bar.open_menu(0)
        assert bar.state == MenuState.OPEN
        assert bar.active_menu == 0
        assert bar.is_open

    def test_close_menu(self):
        bar = _make_bar()
        bar.open_menu(0)
        bar.close()
        assert bar.state == MenuState.CLOSED
        assert not bar.is_open

    def test_toggle_menu_opens(self):
        bar = _make_bar()
        bar.toggle_menu(0)
        assert bar.is_open
        assert bar.active_menu == 0

    def test_toggle_menu_closes_same(self):
        bar = _make_bar()
        bar.toggle_menu(0)
        bar.toggle_menu(0)
        assert not bar.is_open

    def test_toggle_menu_switches(self):
        bar = _make_bar()
        bar.toggle_menu(0)
        bar.toggle_menu(1)
        assert bar.is_open
        assert bar.active_menu == 1

    def test_open_menu_out_of_range(self):
        bar = _make_bar()
        bar.open_menu(99)
        assert not bar.is_open

    def test_submenu_opens_on_choice(self):
        bar = _make_bar()
        bar.open_menu(1)
        # First item is a CHOICE (Config)
        assert bar.active_item == 0
        bar.select()
        assert bar.state == MenuState.SUBMENU

    def test_submenu_closes_on_left(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # open submenu on Config
        assert bar.state == MenuState.SUBMENU
        bar.move_left()
        assert bar.state == MenuState.OPEN


class TestNavigation:
    def test_move_down_skips_separator(self):
        bar = _make_bar()
        bar.open_menu(1)
        # Start at item 0 (Config), move down to item 1 (Profile)
        bar.move_down()
        assert bar.active_item == 1
        # Move down again — should skip separator at index 2
        bar.move_down()
        assert bar.active_item == 3  # Color

    def test_move_up_skips_separator(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.active_item = 3  # Color
        bar.move_up()
        # Should skip separator at index 2
        assert bar.active_item == 1  # Profile

    def test_move_down_wraps(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.active_item = 10  # last item (History: Info)
        bar.move_down()
        assert bar.active_item == 0  # wraps to Config

    def test_move_up_wraps(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.active_item = 0  # Config
        bar.move_up()
        assert bar.active_item == 10  # wraps to History: Info

    def test_left_cycles_menus(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.move_left()
        assert bar.active_menu == 0

    def test_right_cycles_menus(self):
        bar = _make_bar()
        bar.open_menu(0)
        bar.move_right()
        assert bar.active_menu == 1

    def test_right_wraps_around(self):
        bar = _make_bar()
        bar.open_menu(1)
        # active item is 0 (Config, a CHOICE) — right opens submenu
        bar.move_right()
        # When on a CHOICE, right opens submenu instead of cycling
        assert bar.state == MenuState.SUBMENU

    def test_right_on_non_choice_cycles(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.active_item = 3  # Color (TOGGLE, not CHOICE)
        bar.move_right()
        assert bar.active_menu == 0  # cycles to File

    def test_submenu_navigation(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # open Config submenu
        assert bar.active_choice == 0  # "default" is selected
        bar.move_down()
        assert bar.active_choice == 1
        bar.move_up()
        assert bar.active_choice == 0

    def test_submenu_wraps(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # open Config submenu
        bar.move_up()  # wrap around
        assert bar.active_choice == 1  # last choice

    def test_submenu_right_cycles_menu(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # open submenu
        bar.move_right()
        # Right from submenu cycles to next top-level menu
        assert bar.active_menu == 0
        assert bar.state == MenuState.OPEN

    def test_first_selectable_skips_separator(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(item_type=MenuItemType.SEPARATOR),
                MenuItem(item_type=MenuItemType.ACTION, label="Item", action_id="item"),
            ],
        )
        bar = MenuBar([menu])
        bar.open_menu(0)
        assert bar.active_item == 1


class TestSelection:
    def test_action_fires_callback_and_closes(self):
        bar = _make_bar()
        results = []
        bar.on_select = lambda aid, val: results.append((aid, val))
        bar.open_menu(0)
        bar.select()  # Quit
        assert results == [("quit", None)]
        assert not bar.is_open

    def test_toggle_flips_and_stays_open(self):
        bar = _make_bar()
        results = []
        bar.on_select = lambda aid, val: results.append((aid, val))
        bar.open_menu(1)
        bar.active_item = 3  # Color (toggled=True)
        bar.select()
        assert results == [("color", False)]
        assert bar.is_open
        # Toggle again
        bar.select()
        assert results[-1] == ("color", True)

    def test_choice_opens_submenu(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.active_item = 0  # Config
        bar.select()
        assert bar.state == MenuState.SUBMENU

    def test_submenu_selection_fires_callback(self):
        bar = _make_bar()
        results = []
        bar.on_select = lambda aid, val: results.append((aid, val))
        bar.open_menu(1)
        bar.active_item = 0  # Config
        bar.select()  # open submenu
        bar.active_choice = 1  # "aardwolf"
        bar.select()  # select it
        assert results == [("config", "aardwolf")]
        # Should return to dropdown (not closed)
        assert bar.state == MenuState.OPEN

    def test_submenu_updates_selected_marker(self):
        bar = _make_bar()
        bar.on_select = lambda aid, val: None
        bar.open_menu(1)
        bar.select()  # open Config submenu
        bar.active_choice = 1
        bar.select()  # select "aardwolf"
        config_item = bar.menus[1].items[0]
        assert config_item.choices[0].selected is False
        assert config_item.choices[1].selected is True

    def test_disabled_item_not_selectable(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(
                    item_type=MenuItemType.ACTION,
                    label="Disabled",
                    action_id="dis",
                    enabled=False,
                ),
                MenuItem(
                    item_type=MenuItemType.ACTION,
                    label="Enabled",
                    action_id="en",
                ),
            ],
        )
        bar = MenuBar([menu])
        results = []
        bar.on_select = lambda aid, val: results.append((aid, val))
        bar.open_menu(0)
        assert bar.active_item == 1  # first selectable
        bar.active_item = 0  # force to disabled
        bar.select()
        assert results == []  # nothing fired


class TestAltKey:
    def test_alt_f_opens_file(self):
        bar = _make_bar()
        assert bar.handle_alt_key("f")
        assert bar.is_open
        assert bar.active_menu == 0

    def test_alt_s_opens_settings(self):
        bar = _make_bar()
        assert bar.handle_alt_key("s")
        assert bar.is_open
        assert bar.active_menu == 1

    def test_alt_toggles(self):
        bar = _make_bar()
        bar.handle_alt_key("f")
        assert bar.is_open
        bar.handle_alt_key("f")
        assert not bar.is_open

    def test_alt_switches(self):
        bar = _make_bar()
        bar.handle_alt_key("f")
        bar.handle_alt_key("s")
        assert bar.active_menu == 1

    def test_unknown_key_returns_false(self):
        bar = _make_bar()
        assert not bar.handle_alt_key("z")
        assert not bar.is_open

    def test_case_insensitive(self):
        bar = _make_bar()
        assert bar.handle_alt_key("F")
        assert bar.active_menu == 0


class TestHitTesting:
    def test_bar_hit_first_menu(self):
        bar = _make_bar()
        # "File" at col 1..6 (1 pad + "File" + 1 pad = 6 chars starting at col 1)
        assert bar.hit_test_bar(1) == 0
        assert bar.hit_test_bar(6) == 0

    def test_bar_hit_second_menu(self):
        bar = _make_bar()
        # "File" takes cols 1-6, gap at 7, "Settings" starts at col 8
        # "Settings" = 8 chars + 2 pad = 10, so cols 8..17
        assert bar.hit_test_bar(8) == 1
        assert bar.hit_test_bar(17) == 1

    def test_bar_miss(self):
        bar = _make_bar()
        assert bar.hit_test_bar(0) is None
        assert bar.hit_test_bar(100) is None

    def test_dropdown_hit(self):
        bar = _make_bar()
        bar.open_menu(0)
        row, col = bar.dropdown_position()
        # Items start at row+1. File menu has 1 item (Quit) at index 0
        result = bar.hit_test_dropdown(col + 1, row + 1)
        assert result == 0

    def test_dropdown_miss_separator(self):
        bar = _make_bar()
        bar.open_menu(1)
        row, col = bar.dropdown_position()
        # Index 2 is a separator
        result = bar.hit_test_dropdown(col + 1, row + 1 + 2)
        assert result is None

    def test_dropdown_miss_outside(self):
        bar = _make_bar()
        bar.open_menu(0)
        assert bar.hit_test_dropdown(0, 0) is None

    def test_submenu_hit(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # open Config submenu
        s_row, s_col = bar.submenu_position()
        result = bar.hit_test_submenu(s_col + 1, s_row + 1)
        assert result == 0
        result = bar.hit_test_submenu(s_col + 1, s_row + 2)
        assert result == 1

    def test_submenu_miss_when_closed(self):
        bar = _make_bar()
        bar.open_menu(1)
        # Submenu not open
        assert bar.hit_test_submenu(0, 0) is None

    def test_dropdown_position_correct(self):
        bar = _make_bar()
        bar.open_menu(0)
        row, col = bar.dropdown_position()
        assert row == 1  # below menu bar
        assert col == 1  # first menu starts at col 1

    def test_dropdown_position_second_menu(self):
        bar = _make_bar()
        bar.open_menu(1)
        row, col = bar.dropdown_position()
        assert row == 1
        # "File" = 4 chars + 2 pad + 1 gap = 7
        assert col == 8


class TestDynamicChoices:
    def test_supplier_called_on_open(self):
        call_count = [0]

        def supplier():
            call_count[0] += 1
            return [("opt1", "v1"), ("opt2", "v2")]

        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(
                    item_type=MenuItemType.CHOICE,
                    label="Dynamic",
                    action_id="dyn",
                    choices_supplier=supplier,
                ),
            ],
        )
        bar = MenuBar([menu])
        bar.open_menu(0)
        assert call_count[0] == 1
        assert len(bar.menus[0].items[0].choices) == 2
        assert bar.menus[0].items[0].choices[0].label == "opt1"

    def test_supplier_refreshed_each_open(self):
        counter = [0]

        def supplier():
            counter[0] += 1
            return [(f"opt{counter[0]}", f"v{counter[0]}")]

        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(
                    item_type=MenuItemType.CHOICE,
                    label="Dynamic",
                    action_id="dyn",
                    choices_supplier=supplier,
                ),
            ],
        )
        bar = MenuBar([menu])
        bar.open_menu(0)
        assert bar.menus[0].items[0].choices[0].label == "opt1"
        bar.close()
        bar.open_menu(0)
        assert bar.menus[0].items[0].choices[0].label == "opt2"

    def test_supplier_preserves_selection(self):
        def supplier():
            return [("A", "a"), ("B", "b"), ("C", "c")]

        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(
                    item_type=MenuItemType.CHOICE,
                    label="Dynamic",
                    action_id="dyn",
                    choices_supplier=supplier,
                    choices=[ChoiceOption("B", "b", selected=True)],
                ),
            ],
        )
        bar = MenuBar([menu])
        bar.open_menu(0)
        choices = bar.menus[0].items[0].choices
        assert choices[1].selected is True  # "B" preserved
        assert choices[0].selected is False


class TestMenuWidth:
    def test_basic_width(self):
        menu = Menu(
            title="File",
            shortcut_key="f",
            items=[
                MenuItem(item_type=MenuItemType.ACTION, label="Quit"),
            ],
        )
        # "Quit" = 4 chars + 4 padding = 8
        assert menu.width() == 8

    def test_toggle_adds_prefix(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(item_type=MenuItemType.TOGGLE, label="Color"),
            ],
        )
        # "Color" = 5 + 4 prefix ("[x] ") + 4 padding = 13
        assert menu.width() == 13

    def test_choice_adds_arrow(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(item_type=MenuItemType.CHOICE, label="Config"),
            ],
        )
        # "Config" = 6 + 2 arrow (" >") + 4 padding = 12
        assert menu.width() == 12

    def test_hotkey_adds_space(self):
        menu = Menu(
            title="File",
            shortcut_key="f",
            items=[
                MenuItem(item_type=MenuItemType.ACTION, label="Quit", hotkey="Ctrl+C"),
            ],
        )
        # "Quit" = 4 + "  Ctrl+C" = 4 + 8 = 12 + 4 padding = 16
        assert menu.width() == 16

    def test_separator_ignored(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(item_type=MenuItemType.SEPARATOR),
                MenuItem(item_type=MenuItemType.ACTION, label="OK"),
            ],
        )
        # "OK" = 2 + 4 padding = 6
        assert menu.width() == 6


class TestEdgeCases:
    def test_empty_menu(self):
        menu = Menu(title="Empty", shortcut_key="e", items=[])
        bar = MenuBar([menu])
        bar.open_menu(0)
        assert bar.active_item == 0
        # Moving should not crash
        bar.move_down()
        bar.move_up()

    def test_all_disabled_items(self):
        menu = Menu(
            title="Test",
            shortcut_key="t",
            items=[
                MenuItem(item_type=MenuItemType.ACTION, label="A", action_id="a", enabled=False),
                MenuItem(item_type=MenuItemType.ACTION, label="B", action_id="b", enabled=False),
            ],
        )
        bar = MenuBar([menu])
        bar.open_menu(0)
        # _first_selectable returns 0 when nothing selectable
        assert bar.active_item == 0
        # Select should not fire anything
        results = []
        bar.on_select = lambda aid, val: results.append((aid, val))
        bar.select()
        assert results == []

    def test_no_menus(self):
        bar = MenuBar([])
        bar.open_menu(0)
        assert not bar.is_open
        assert not bar.handle_alt_key("f")

    def test_dropdown_rect(self):
        bar = _make_bar()
        bar.open_menu(0)
        row, col, h, w = bar.dropdown_rect()
        assert row == 1
        assert h == 3  # 1 item + 2 borders

    def test_submenu_rect(self):
        bar = _make_bar()
        bar.open_menu(1)
        bar.select()  # Config submenu
        row, col, h, w = bar.submenu_rect()
        assert h == 4  # 2 choices + 2 borders

    def test_submenu_choice_positions_on_selected(self):
        bar = _make_bar()
        bar.open_menu(1)
        # Config item has "default" selected
        bar.select()  # open submenu
        assert bar.active_choice == 0  # "default" is first and selected

        # Now select aardwolf
        bar.active_choice = 1
        bar.on_select = lambda aid, val: None
        bar.select()  # select aardwolf
        # Close and reopen
        bar.close()
        bar.open_menu(1)
        bar.select()  # open Config submenu again
        assert bar.active_choice == 1  # should land on "aardwolf"
