"""cli entry point for phage-node."""

import json
import os
import sys

from .config import load_config, write_default_config, CONFIG_PATH
from .daemon import PhageDaemon
from .gpu import detect_gpu
from .chat import chat, check_key


def main():
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "register":
        _register()
    elif cmd == "start":
        _start()
    elif cmd == "status":
        _status()
    elif cmd == "init":
        _init()
    elif cmd == "chat":
        _chat()
    elif cmd in ("--help", "-h", "help"):
        _usage()
    else:
        print(f"unknown command: {cmd}")
        _usage()
        sys.exit(1)


def _usage():
    print("usage: phage-node <command>")
    print()
    print("commands:")
    print("  init       create default config at ~/.phage/config.toml")
    print("  register   detect GPU and register with coordinator")
    print("  start      start the node daemon (connect, pull tasks, run)")
    print("  status     show node status, GPU info, task history")
    print("  chat       talk to kell (requires $KELL holder API key)")
    print("  help       show this message")


def _init():
    if os.path.exists(os.path.expanduser(CONFIG_PATH)):
        print(f"config already exists: {CONFIG_PATH}")
        print("edit it or delete to regenerate.")
        return
    path = write_default_config()
    print(f"wrote default config to {path}")
    print("edit coordinator.url before registering.")


def _register():
    config = load_config()
    daemon = PhageDaemon(config=config)
    daemon.register()


def _start():
    config = load_config()
    daemon_mode = "--daemon" in sys.argv
    daemon = PhageDaemon(config=config)

    if daemon_mode:
        _daemonize()

    daemon.start()


def _status():
    config = load_config()
    state_path = os.path.expanduser("~/.phage/state.json")
    gpu_device = config.get("gpu", {}).get("device", 0)

    print("phage-node status")
    print("=" * 40)

    # node identity
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        print(f"node_id:   {state.get('node_id', 'unknown')}")
        print(f"registered: {state.get('registered_at', 'unknown')}")
    else:
        print("node_id:   not registered")
        print()
        print("run 'phage-node register' first.")
        return

    # gpu info
    try:
        gpu = detect_gpu(gpu_device)
        vram_gb = gpu["vram_mb"] // 1024
        print(f"gpu:       {gpu['name']} ({vram_gb} GB)")
        print(f"driver:    {gpu['driver']}")
    except Exception as e:
        print(f"gpu:       detection failed ({e})")

    # coordinator
    coord_url = config.get("coordinator", {}).get("url", "not set")
    print(f"coordinator: {coord_url}")

    # task stats
    stats_path = os.path.expanduser("~/.phage/stats.json")
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            stats = json.load(f)
        print(f"tasks:     {stats.get('completed', 0)} done, {stats.get('failed', 0)} failed")
        print(f"tokens:    {stats.get('total_tokens', 0)}")
        if stats.get("last_task_at"):
            print(f"last:      {stats['last_task_at']}")
    else:
        print("tasks:     no history yet")


def _chat():
    config = load_config()
    key = None
    message = None

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--key" and i + 1 < len(args):
            key = args[i + 1]
            i += 2
        elif args[i] == "--check":
            # check key status
            k = key or config.get("chat", {}).get("key", "")
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                k = args[i + 1]
            check_key(k)
            return
        else:
            message = args[i]
            i += 1

    if not key:
        key = config.get("chat", {}).get("key", "")

    if not message:
        print("usage: phage-node chat [--key kell_xxxx] \"your message\"")
        print("       phage-node chat --check [key]")
        sys.exit(1)

    chat(key, message)


def _daemonize():
    """fork to background."""
    pid = os.fork()
    if pid > 0:
        print(f"phage-node started (pid {pid})")
        sys.exit(0)
    os.setsid()
    # redirect stdio
    devnull = open(os.devnull, "w")
    sys.stdout = devnull
    sys.stderr = devnull
