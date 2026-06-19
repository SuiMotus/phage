"""phage node daemon. manages vllm, pulls tasks, runs sandboxed execution."""

import os
import time
import signal
import threading
import toml

from .gpu import detect_gpu
from .sandbox import run_sandboxed
from .vllm_manager import VLLMManager


class PhageDaemon:
    def __init__(self, config_path="~/.phage/config.toml"):
        self.config = toml.load(os.path.expanduser(config_path))
        self.node_id = None
        self.running = False
        self.vllm = None

    def register(self):
        gpu = detect_gpu(self.config.get("gpu", {}).get("device", 0))
        print(f"detected: {gpu['name']} ({gpu['vram_mb'] // 1024} GB)")
        self.node_id = f"ph_n_{os.urandom(4).hex()}"
        print(f"node_id:  {self.node_id}")
        print(f"status:   registered")

    def start(self):
        self.running = True
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        coord_url = self.config["coordinator"]["url"]
        print(f"connecting to {coord_url}")

        vllm_cfg = self.config.get("vllm", {})
        self.vllm = VLLMManager(
            port=vllm_cfg.get("port", 8400),
            gpu_mem=vllm_cfg.get("gpu_memory_utilization", 0.80),
        )
        self.vllm.start()

        hb = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb.start()

        while self.running:
            task = self._fetch_task()
            if task:
                result = self._execute_task(task)
                self._submit_result(result)
            else:
                time.sleep(2)

    def stop(self):
        self.running = False
        if self.vllm:
            self.vllm.stop()

    def _heartbeat_loop(self):
        while self.running:
            time.sleep(10)

    def _fetch_task(self):
        return None

    def _execute_task(self, task):
        return run_sandboxed(task, self.config.get("sandbox", {}))

    def _submit_result(self, result):
        pass
