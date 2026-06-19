"""cli entry point."""

import sys
from .daemon import PhageDaemon


def main():
    if len(sys.argv) < 2:
        print("usage: phage-node <register|start|status>")
        sys.exit(1)

    cmd = sys.argv[1]
    daemon = PhageDaemon()

    if cmd == "register":
        daemon.register()
    elif cmd == "start":
        daemon.start()
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)
