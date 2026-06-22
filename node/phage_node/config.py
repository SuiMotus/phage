"""configuration loading and defaults."""

import os
import toml

DEFAULT_CONFIG = {
    "coordinator": {
        "url": "https://coordinator.phage.dev:9090",
    },
    "gpu": {
        "device": 0,
        "max_vram_pct": 85,
    },
    "sandbox": {
        "runtime": "gvisor",
        "max_runtime_sec": 300,
        "scratch_dir": "/tmp/phage/scratch",
    },
    "vllm": {
        "port": 8400,
        "gpu_memory_utilization": 0.80,
        "max_model_len": 8192,
    },
    "heartbeat": {
        "interval_sec": 10,
        "miss_threshold": 3,
    },
    "logging": {
        "level": "info",
        "file": "~/.phage/phage-node.log",
    },
}

CONFIG_PATH = os.path.expanduser("~/.phage/config.toml")


def load_config(path=None):
    path = os.path.expanduser(path or CONFIG_PATH)
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()

    user = toml.load(path)
    merged = DEFAULT_CONFIG.copy()
    for section in merged:
        if section in user:
            if isinstance(merged[section], dict):
                merged[section].update(user[section])
            else:
                merged[section] = user[section]
    return merged


def write_default_config(path=None):
    path = os.path.expanduser(path or CONFIG_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        toml.dump(DEFAULT_CONFIG, f)
    return path
