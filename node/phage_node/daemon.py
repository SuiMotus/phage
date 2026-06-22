"""phage node daemon. manages vllm, pulls tasks, runs sandboxed execution."""

import json
import os
import signal
import threading
import time

from .config import load_config
from .gpu import detect_gpu
from .sandbox import run_sandboxed
from .vllm_manager import VLLMManager


class PhageDaemon:
    def __init__(self, config=None, config_path=None):
        self.config = config or load_config(config_path)
        self.node_id = None
        self.running = False
        self.vllm = None
        self._stats = {"completed": 0, "failed": 0, "total_tokens": 0}

    def register(self):
        """register with coordinator, get node_id and certs."""
        gpu_cfg = self.config.get("gpu", {})
        gpu = detect_gpu(gpu_cfg.get("device", 0))

        print(f"detected: {gpu['name']} ({gpu['vram_mb'] // 1024} GB)")
        print(f"driver:   {gpu['driver']}")
        print()

        coord_url = self.config["coordinator"]["url"]
        print(f"coordinator: {coord_url}")
        print("registering... ", end="", flush=True)

        # gRPC Register call
        # sends NodeInfo, receives node_id + mTLS certs
        self.node_id = f"ph_n_{os.urandom(4).hex()}"

        # store state
        state_dir = os.path.expanduser("~/.phage")
        os.makedirs(state_dir, exist_ok=True)
        state = {
            "node_id": self.node_id,
            "gpu": gpu["name"],
            "vram_mb": gpu["vram_mb"],
            "coordinator": coord_url,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(os.path.join(state_dir, "state.json"), "w") as f:
            json.dump(state, f, indent=2)

        print("done")
        print()
        print(f"node_id:  {self.node_id}")
        print(f"gpu:      {gpu['name']} ({gpu['vram_mb'] // 1024} GB)")
        print(f"status:   registered")
        print()
        print(f"certs written to {state_dir}/certs/")
        print(f"start with: phage-node start")

    def start(self):
        """main loop: start vllm, heartbeat, pull tasks."""
        self._load_state()
        if not self.node_id:
            print("not registered. run 'phage-node register' first.")
            return

        self.running = True
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        coord_url = self.config["coordinator"]["url"]
        print(f"node {self.node_id}")
        print(f"connecting to {coord_url}")

        # start vllm
        vllm_cfg = self.config.get("vllm", {})
        self.vllm = VLLMManager(
            port=vllm_cfg.get("port", 8400),
            gpu_mem=vllm_cfg.get("gpu_memory_utilization", 0.80),
            max_model_len=vllm_cfg.get("max_model_len", 8192),
        )
        self.vllm.start()

        # heartbeat thread
        hb_interval = self.config.get("heartbeat", {}).get("interval_sec", 10)
        hb = threading.Thread(target=self._heartbeat_loop, args=(hb_interval,), daemon=True)
        hb.start()

        print("pulling tasks...")

        # task loop
        while self.running:
            task = self._fetch_task()
            if task:
                result = self._execute_task(task)
                self._submit_result(result)
                self._update_stats(result)
            else:
                time.sleep(2)

    def stop(self):
        self.running = False
        if self.vllm:
            self.vllm.stop()
        self._save_stats()
        print("\nnode stopped")

    def _load_state(self):
        state_path = os.path.expanduser("~/.phage/state.json")
        if os.path.exists(state_path):
            with open(state_path) as f:
                state = json.load(f)
            self.node_id = state.get("node_id")

    def _heartbeat_loop(self, interval):
        while self.running:
            self._send_heartbeat()
            time.sleep(interval)

    def _send_heartbeat(self):
        """send heartbeat with GPU metrics to coordinator."""
        # gRPC Heartbeat call
        # sends: node_id, gpu_utilization, vram_used, temp, active_tasks, model_loaded
        # receives: ack, optional model swap command
        pass

    def _fetch_task(self):
        """pull next task from coordinator."""
        # gRPC FetchTask call
        # sends: node_id, model_loaded, vram_available
        # receives: task assignment or empty (no work)
        return None

    def _execute_task(self, task):
        sandbox_cfg = self.config.get("sandbox", {})
        key_path = os.path.expanduser("~/.phage/certs/node.key")
        return run_sandboxed(task, sandbox_cfg, node_key_path=key_path)

    def _submit_result(self, result):
        """submit task result + attestation to coordinator."""
        # gRPC SubmitResult call
        # sends: task_id, node_id, passed, output, attestation, tokens, wall_ms
        # receives: accepted/rejected + reason
        pass

    def _update_stats(self, result):
        if result.get("passed"):
            self._stats["completed"] += 1
        else:
            self._stats["failed"] += 1
        self._stats["total_tokens"] += result.get("tokens", 0)
        self._stats["last_task_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save_stats()

    def _save_stats(self):
        stats_path = os.path.expanduser("~/.phage/stats.json")
        try:
            with open(stats_path, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception:
            pass
