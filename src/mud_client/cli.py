import argparse
import curses
import sys

from mud_client.app import run_client
from mud_client.config import load_config, load_profile, create_profile


def main():
    p = argparse.ArgumentParser(description="Curses MUD client")
    p.add_argument("-c", "--config", default="default",
                   help="Configuration name (loads configs/<name>.yml)")
    p.add_argument("host", nargs="?", default=None,
                   help="MUD host (domain or IP) - overrides config")
    p.add_argument("port", nargs="?", type=int, default=None,
                   help="MUD port - overrides config")
    p.add_argument("--no-color", action="store_true", default=False,
                   help="Disable ANSI color rendering (strip escape sequences)")
    p.add_argument("-d", "--debug", action="store_true", default=False,
                   help="Enable debug logging to mud_*.log files in current directory")
    p.add_argument("-p", "--profile",
                   default=None,
                   help="Login profile name (loads profiles/<name>.yml for auto-login)")
    p.add_argument("--create-profile", metavar="NAME",
                   help="Create a login profile interactively and exit")
    p.add_argument("--conv-pos",
                   choices=["top-left", "top-center", "top-right",
                            "bottom-left", "bottom-center", "bottom-right"],
                   default="bottom-right",
                   help="Conversation overlay position (default: bottom-right)")
    args = p.parse_args()

    # Handle --create-profile and exit
    if args.create_profile:
        path = create_profile(args.create_profile)
        print(f"Profile saved to {path}")
        return

    # Load configuration
    config = load_config(args.config)

    # Load login profile if specified
    if args.profile:
        try:
            config.profile = load_profile(args.profile)
        except FileNotFoundError as e:
            p.error(str(e))

    # CLI arguments override config values
    if args.host is not None:
        config.connection.host = args.host
    if args.port is not None:
        config.connection.port = args.port

    # Validate that we have host and port from some source
    if not config.connection.host:
        p.error("host is required (via CLI argument or config file)")
    if not config.connection.port:
        p.error("port is required (via CLI argument or config file)")

    curses.wrapper(run_client, config,
                   color=not args.no_color, debug=args.debug,
                   conv_pos=args.conv_pos)
