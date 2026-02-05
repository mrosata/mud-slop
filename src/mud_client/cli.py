import argparse
import curses

from mud_client.app import run_client


def main():
    p = argparse.ArgumentParser(description="Curses MUD client")
    p.add_argument("host", help="MUD host (domain or IP)")
    p.add_argument("port", type=int, help="MUD port")
    p.add_argument("--no-color", action="store_true", default=False,
                   help="Disable ANSI color rendering (strip escape sequences)")
    p.add_argument("-d", "--debug", action="store_true", default=False,
                   help="Enable debug logging to mud_*.log files in current directory")
    p.add_argument("--conv-pos",
                   choices=["top-left", "top-center", "top-right",
                            "bottom-left", "bottom-center", "bottom-right"],
                   default="bottom-right",
                   help="Conversation overlay position (default: bottom-right)")
    args = p.parse_args()

    curses.wrapper(run_client, args.host, args.port,
                   color=not args.no_color, debug=args.debug,
                   conv_pos=args.conv_pos)
