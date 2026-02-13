from __future__ import annotations

import queue
import time
from typing import Any

from mud_slop.ansi import _init_color_pairs
from mud_slop.config import Config, ProfileConfig, load_config, load_profile
from mud_slop.connection import MudConnection
from mud_slop.debug_log import DebugLogger
from mud_slop.gmcp import GMCPHandler
from mud_slop.types import ProtoEvent
from mud_slop.ui import MudUI

_HISTORY_TYPES = {
    "conversations": "history_show_conversations",
    "conversation": "history_show_conversations",
    "conv": "history_show_conversations",
    "help": "history_show_help",
    "maps": "history_show_maps",
    "map": "history_show_maps",
    "info": "history_show_info",
}


def _handle_history_cmd(ui: "MudUI", line: str):
    """Handle /history command for viewing/toggling history visibility."""
    parts = line.split()
    # /history — show current settings
    if len(parts) == 1:
        ui.add_system_message(f"History visibility: {ui.history_settings_text()}")
        return
    type_name = parts[1].lower()
    attr = _HISTORY_TYPES.get(type_name)
    if attr is None:
        valid = "conversations, help, maps, info"
        ui.add_system_message(f"Unknown type '{parts[1]}'. Valid: {valid}")
        return
    # /history <type> on|off — explicit set
    if len(parts) >= 3:
        val = parts[2].lower()
        if val in ("on", "true", "yes", "1"):
            setattr(ui, attr, True)
        elif val in ("off", "false", "no", "0"):
            setattr(ui, attr, False)
        else:
            ui.add_system_message(f"Invalid value '{parts[2]}'. Use on/off.")
            return
    else:
        # /history <type> — toggle
        setattr(ui, attr, not getattr(ui, attr))
    state = "ON" if getattr(ui, attr) else "OFF"
    ui.add_system_message(f"History {type_name}: {state} (affects new lines)")


def _hot_swap_config(ui: MudUI, conn: MudConnection, config_name: str, logger: DebugLogger):
    """Load a new config and rebuild trackers."""
    try:
        new_config = load_config(config_name)
    except FileNotFoundError as e:
        ui.add_system_message(f"Config error: {e}")
        return
    # Preserve connection settings (host/port don't change mid-session)
    new_config.connection = ui.config.connection
    # Preserve current profile
    new_config.profile = ui.config.profile
    ui.rebuild_trackers(new_config)
    ui._current_config_name = config_name
    ui.add_system_message(f"Config switched to: {config_name}")


def _hot_swap_profile(ui: MudUI, profile_name: str):
    """Load a new profile or clear it."""
    if not profile_name:
        ui.config.profile = ProfileConfig()
        ui._current_profile_name = None
        ui.add_system_message("Profile cleared")
        return
    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        ui.add_system_message(f"Profile error: {e}")
        return
    ui.config.profile = profile
    ui._current_profile_name = profile_name
    ui.add_system_message(f"Profile switched to: {profile_name}")


def _make_menu_handler(ui: MudUI, conn: MudConnection, logger: DebugLogger):
    """Create the menu on_select callback."""

    def on_menu_select(action_id: str, value: Any) -> None:
        if action_id == "quit":
            for cmd in ui.config.hooks.on_exit:
                conn.send_line(cmd)
            conn.close()
            logger.stop()
            raise KeyboardInterrupt  # reuse existing exit path
        elif action_id == "debug":
            state = logger.toggle()
            label = "ON" if state else "OFF"
            ui.add_system_message(f"Debug logging {label}")
            ui._sync_menu_toggles()
        elif action_id == "color":
            ui.color_enabled = bool(value)
            if ui.color_enabled:
                _init_color_pairs()
            ui.add_system_message(f"Color {'ON' if value else 'OFF'}")
        elif action_id == "conv_pos":
            ui.conv_pos = value
            ui.add_system_message(f"Conversation position: {value}")
        elif action_id == "config":
            _hot_swap_config(ui, conn, value, logger)
        elif action_id == "profile":
            _hot_swap_profile(ui, value)
        elif action_id.startswith("history_"):
            attr_map = {
                "history_conversations": "history_show_conversations",
                "history_help": "history_show_help",
                "history_maps": "history_show_maps",
                "history_info": "history_show_info",
            }
            attr = attr_map.get(action_id)
            if attr:
                setattr(ui, attr, value)
                label = action_id.replace("history_", "")
                state = "ON" if value else "OFF"
                ui.add_system_message(f"History {label}: {state}")

    return on_menu_select


def run_client(
    stdscr,
    config: Config,
    color: bool = True,
    debug: bool = False,
    conv_pos: str = "bottom-right",
    config_name: str = "default",
    profile_name: str | None = None,
):
    proto_q: queue.Queue[ProtoEvent] = queue.Queue()
    text_q: queue.Queue[str] = queue.Queue()
    gmcp_q: queue.Queue[tuple[float, bytes]] = queue.Queue()

    logger = DebugLogger()
    if debug:
        logger.start()

    gmcp_handler = GMCPHandler()
    ui = MudUI(
        stdscr,
        gmcp_handler=gmcp_handler,
        color=color,
        debug_logger=logger,
        conv_pos=conv_pos,
        config=config,
    )
    ui._current_config_name = config_name
    ui._current_profile_name = profile_name
    conn = MudConnection(
        config.connection.host,
        config.connection.port,
        proto_q=proto_q,
        text_q=text_q,
        gmcp_q=gmcp_q,
        gmcp_config=config.gmcp,
    )

    # Wire up menu callback
    ui.menu_bar.on_select = _make_menu_handler(ui, conn, logger)

    try:
        conn.connect()
    except Exception as e:
        ui.add_system_message(f"Connect failed: {e}")
        ui.draw()
        time.sleep(2)
        return

    ui.add_system_message("Type /quit to exit.")
    ui.draw()

    # Auto-login state machine
    profile_username = config.profile.username
    profile_password = config.profile.password
    has_profile = profile_username is not None
    login_sent_username = False
    login_sent_password = False
    prev_echo_off = False

    try:
        while True:
            # Poll network
            conn.poll()

            # Sync password mode state from connection to UI
            ui.echo_off = conn.echo_off

            # Drain protocol queue
            while True:
                try:
                    ev = proto_q.get_nowait()
                except queue.Empty:
                    break
                logger.log_proto(ev)

            # Drain GMCP queue FIRST - so vitals are available before text processing
            while True:
                try:
                    ts, payload = gmcp_q.get_nowait()
                except queue.Empty:
                    break
                pkg, data = gmcp_handler.handle(ts, payload)
                logger.log_gmcp(pkg, data)

            # After login (GMCP vitals arrive): enable map detection and run
            # post-login hook commands from config. Must happen BEFORE text
            # processing so the initial room map is filtered.
            if (
                not ui.map_tracker.sent_initial
                and not ui.map_tracker.map_lines
                and gmcp_handler.vitals
            ):
                ui.map_tracker.enabled = True
                for cmd in ui.config.hooks.post_login:
                    conn.send_line(cmd)
                ui.map_tracker.sent_initial = True

            # Drain text queue AFTER map tracker is enabled
            while True:
                try:
                    t = text_q.get_nowait()
                except queue.Empty:
                    break
                ui.add_output_text(t)
                logger.log_output(t)

            # Auto-login: send username after first server text,
            # send password when echo_off (password mode) activates.
            if has_profile and not login_sent_username and ui.output_lines:
                conn.send_line(profile_username)
                login_sent_username = True
            if (
                has_profile
                and login_sent_username
                and not login_sent_password
                and profile_password
                and conn.echo_off
                and not prev_echo_off
            ):
                conn.send_line(profile_password)
                login_sent_password = True
            prev_echo_off = conn.echo_off

            # Tick timers
            now = time.time()
            if ui.conversation.visible:
                if ui.conversation.check_auto_close(now):
                    ui.conversation.dismiss()
            ui.info_tracker.tick(now)

            # Handle input (getch blocks up to 25ms via timeout())
            ch = ui.stdscr.getch()
            line, _ = ui.handle_key(ch)

            if line is not None:
                line = line.rstrip("\n")
                if line.strip().lower() == "/quit":
                    # Run on_exit hooks before closing
                    for cmd in ui.config.hooks.on_exit:
                        conn.send_line(cmd)
                    conn.close()
                    logger.stop()
                    return
                elif line.strip().lower() == "/debug":
                    state = logger.toggle()
                    label = "ON" if state else "OFF"
                    ui.add_system_message(f"Debug logging {label}")
                    ui._sync_menu_toggles()
                elif line.strip().lower() == "/clear":
                    ui.clear()
                elif line.strip().lower() == "/info":
                    ui.show_info_history()
                elif line.strip().lower().startswith("/history"):
                    _handle_history_cmd(ui, line.strip())
                    ui._sync_menu_toggles()
                else:
                    conn.send_line(line)
                    if not conn.echo_off:
                        ui.history.add(line)

            # Refresh UI
            ui.draw()

    except KeyboardInterrupt:
        # Run on_exit hooks before closing
        try:
            for cmd in ui.config.hooks.on_exit:
                conn.send_line(cmd)
        except Exception:
            pass
        conn.close()
        logger.stop()
        return
    except Exception as e:
        try:
            # Run on_exit hooks before closing
            for cmd in ui.config.hooks.on_exit:
                conn.send_line(cmd)
            conn.close()
            logger.stop()
        finally:
            # Try to show error briefly
            ui.add_system_message(f"Fatal error: {e}")
            ui.draw()
            time.sleep(2)
