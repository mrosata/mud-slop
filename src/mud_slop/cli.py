import argparse
import curses
import json
import sys
import urllib.request

from mud_slop import __version__
from mud_slop.app import run_client
from mud_slop.config import load_config, load_profile, create_profile


def _parse_version(v):
    """Parse version string to comparable tuple of ints."""
    parts = []
    for part in v.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_updates():
    """Check PyPI for a newer version. Prints a message if outdated."""
    try:
        if __version__ == "0.0.0.dev":
            return
        req = urllib.request.Request(
            "https://pypi.org/pypi/mud-slop/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        latest = data["info"]["version"]
        if _parse_version(latest) > _parse_version(__version__):
            print(
                f"\033[33mUpdate available: {__version__} \u2192 {latest}.\033[0m "
                f"Run '\033[1mpip install --upgrade mud-slop\033[0m' to update.",
                file=sys.stderr,
            )
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="Curses MUD client")
    p.add_argument("-v", "--version", action="version",
                   version=f"%(prog)s {__version__}")
    p.add_argument("-c", "--config", default="default",
                   help="Configuration name or path (searches ~/.mud-slop/configs/, ./configs/, or use full path)")
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
                   help="Login profile name or path (searches ~/.mud-slop/profiles/, ./profiles/, or use full path)")
    p.add_argument("--create-profile", metavar="NAME",
                   help="Create a login profile interactively (saves to ~/.mud-slop/profiles/)")
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
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        p.error(str(e))

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

    check_for_updates()

    curses.wrapper(run_client, config,
                   color=not args.no_color, debug=args.debug,
                   conv_pos=args.conv_pos)
