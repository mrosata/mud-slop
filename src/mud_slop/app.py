import queue
import time

from mud_slop.config import Config
from mud_slop.debug_log import DebugLogger
from mud_slop.gmcp import GMCPHandler
from mud_slop.ui import MudUI
from mud_slop.connection import MudConnection


def run_client(stdscr, config: Config, color: bool = True,
               debug: bool = False, conv_pos: str = "bottom-right"):
    proto_q: "queue.Queue[ProtoEvent]" = queue.Queue()
    text_q: "queue.Queue[str]" = queue.Queue()
    gmcp_q: "queue.Queue[tuple[float, bytes]]" = queue.Queue()

    logger = DebugLogger()
    if debug:
        logger.start()

    gmcp_handler = GMCPHandler()
    ui = MudUI(stdscr, gmcp_handler=gmcp_handler, color=color,
               debug_logger=logger, conv_pos=conv_pos, config=config)
    conn = MudConnection(config.connection.host, config.connection.port,
                         proto_q=proto_q, text_q=text_q, gmcp_q=gmcp_q,
                         gmcp_config=config.gmcp)

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

            # Drain queues
            while True:
                try:
                    ev = proto_q.get_nowait()
                except queue.Empty:
                    break
                logger.log_proto(ev)

            while True:
                try:
                    t = text_q.get_nowait()
                except queue.Empty:
                    break
                ui.add_output_text(t)
                logger.log_output(t)

            while True:
                try:
                    ts, payload = gmcp_q.get_nowait()
                except queue.Empty:
                    break
                pkg, data = gmcp_handler.handle(ts, payload)
                logger.log_gmcp(pkg, data)

            # Auto-login: send username after first server text,
            # send password when echo_off (password mode) activates.
            if has_profile and not login_sent_username and ui.output_lines:
                conn.send_line(profile_username)
                login_sent_username = True
            if (has_profile and login_sent_username and not login_sent_password
                    and profile_password and conn.echo_off and not prev_echo_off):
                conn.send_line(profile_password)
                login_sent_password = True
            prev_echo_off = conn.echo_off

            # After login (GMCP vitals arrive): enable map detection and run
            # post-login hook commands from config.
            if (not ui.map_tracker.sent_initial
                    and not ui.map_tracker.map_lines
                    and gmcp_handler.vitals):
                ui.map_tracker.enabled = True
                for cmd in config.hooks.post_login:
                    conn.send_line(cmd)
                ui.map_tracker.sent_initial = True

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
                    for cmd in config.hooks.on_exit:
                        conn.send_line(cmd)
                    conn.close()
                    logger.stop()
                    return
                elif line.strip().lower() == "/debug":
                    state = logger.toggle()
                    label = "ON" if state else "OFF"
                    ui.add_system_message(f"Debug logging {label}")
                elif line.strip().lower() == "/clear":
                    ui.clear()
                elif line.strip().lower() == "/info":
                    ui.show_info_history()
                else:
                    conn.send_line(line)
                    if not conn.echo_off:
                        ui.history.add(line)

            # Refresh UI
            ui.draw()

    except KeyboardInterrupt:
        # Run on_exit hooks before closing
        for cmd in config.hooks.on_exit:
            conn.send_line(cmd)
        conn.close()
        logger.stop()
        return
    except Exception as e:
        try:
            # Run on_exit hooks before closing
            for cmd in config.hooks.on_exit:
                conn.send_line(cmd)
            conn.close()
            logger.stop()
        finally:
            # Try to show error briefly
            ui.add_system_message(f"Fatal error: {e}")
            ui.draw()
            time.sleep(2)
