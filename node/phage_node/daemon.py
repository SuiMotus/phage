"""phage node daemon. manages vllm, pulls tasks, runs sandboxed execution."""

import json
import os
import signal
import threading
import time

import httpx

from .config import load_config
from .gpu import detect_gpu
from .sandbox import run_sandboxed
from .vllm_manager import VLLMManager


COORDINATOR_TIMEOUT = 15


class PhageDaemon:
    def __init__(self, config=None, config_path=None):
        self.config = config or load_config(config_path)
        self.node_id = None
        self.running = False
        self.vllm = None
        self.coord_url = self.config["coordinator"]["url"].rstrip("/")
        self._stats = {"completed": 0, "failed": 0, "total_tokens": 0}
        self._http = httpx.Client(timeout=COORDINATOR_TIMEOUT)

    def register(self):
        """register with coordinator, get node_id and certs."""
        gpu_cfg = self.config.get("gpu", {})
        gpu = detect_gpu(gpu_cfg.get("device", 0))

        print(f"detected: {gpu['name']} ({gpu['vram_mb'] // 1024} GB)")
        print(f"driver:   {gpu['driver']}")
        print()

        print(f"coordinator: {self.coord_url}")
        print("registering... ", end="", flush=True)

        resp = self._http.post(f"{self.coord_url}/api/register", json={
            "hostname": os.uname().nodename,
            "gpu_model": gpu["name"],
            "vram_mb": gpu["vram_mb"],
            "driver_version": gpu["driver"],
            "cuda_version": "",
            "os": f"{os.uname().sysname} {os.uname().release}",
        })
        resp.raise_for_status()
        data = resp.json()

        self.node_id = data["node_id"]
        model = data.get("model", "unknown")

        # store state
        state_dir = os.path.expanduser("~/.phage")
        os.makedirs(state_dir, exist_ok=True)
        os.makedirs(os.path.join(state_dir, "certs"), exist_ok=True)
        state = {
            "node_id": self.node_id,
            "gpu": gpu["name"],
            "vram_mb": gpu["vram_mb"],
            "coordinator": self.coord_url,
            "model": model,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(os.path.join(state_dir, "state.json"), "w") as f:
            json.dump(state, f, indent=2)

        print("done")
        print()
        print(f"node_id:  {self.node_id}")
        print(f"gpu:      {gpu['name']} ({gpu['vram_mb'] // 1024} GB)")
        print(f"model:    {model}")
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

        print(f"node {self.node_id}")
        print(f"connecting to {self.coord_url}")

        # start vllm
        vllm_cfg = self.config.get("vllm", {})
        self.vllm = VLLMManager(
            port=vllm_cfg.get("port", 8400),
            gpu_mem=vllm_cfg.get("gpu_memory_utilization", 0.80),
            max_model_len=vllm_cfg.get("max_model_len", 8192),
        )

        state = self._read_state()
        model = state.get("model", "Qwen/Qwen2.5-Coder-7B-Instruct")
        self.vllm.start(model)

        # heartbeat thread
        hb_interval = self.config.get("heartbeat", {}).get("interval_sec", 10)
        hb = threading.Thread(target=self._heartbeat_loop, args=(hb_interval,), daemon=True)
        hb.start()

        print("pulling tasks...")

        # task loop
        while self.running:
            task = self._fetch_task()
            if task and task.get("task_id"):
                print(f"task {task['task_id']}: {task['prompt'][:60]}...")
                result = self._execute_task(task)
                self._submit_result(task, result)
                self._update_stats(result)
            else:
                time.sleep(5)

    def stop(self):
        self.running = False
        if self.vllm:
            self.vllm.stop()
        self._save_stats()
        print("\nnode stopped")

    def _load_state(self):
        state = self._read_state()
        self.node_id = state.get("node_id") if state else None

    def _read_state(self):
        state_path = os.path.expanduser("~/.phage/state.json")
        if os.path.exists(state_path):
            with open(state_path) as f:
                return json.load(f)
        return None

    def _heartbeat_loop(self, interval):
        while self.running:
            try:
                self._send_heartbeat()
            except Exception as e:
                print(f"heartbeat failed: {e}")
            time.sleep(interval)

    def _send_heartbeat(self):
        """send heartbeat with GPU metrics to coordinator."""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(
                self.config.get("gpu", {}).get("device", 0)
            )
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            pynvml.nvmlShutdown()

            gpu_util = util.gpu
            vram_used = mem.used // (1024 * 1024)
            gpu_temp = temp
        except Exception:
            gpu_util = 0
            vram_used = 0
            gpu_temp = 0

        resp = self._http.post(f"{self.coord_url}/api/heartbeat", json={
            "node_id": self.node_id,
            "gpu_utilization": gpu_util,
            "vram_used_mb": vram_used,
            "gpu_temp": gpu_temp,
            "model_loaded": self.vllm.model if self.vllm else "",
            "active_tasks": 0,
        })
        resp.raise_for_status()

        data = resp.json()
        # handle model swap requests
        if data.get("load_model") and self.vllm:
            print(f"coordinator requested model swap: {data['load_model']}")
            self.vllm.swap_model(data["load_model"])

    def _fetch_task(self):
        """pull next task from coordinator."""
        try:
            state = self._read_state()
            resp = self._http.post(f"{self.coord_url}/api/fetch_task", json={
                "node_id": self.node_id,
                "model_loaded": self.vllm.model if self.vllm else "",
                "vram_available_mb": state.get("vram_mb", 0) if state else 0,
            })
            resp.raise_for_status()
            data = resp.json()
            if data.get("task_id"):
                return data
            return None
        except Exception as e:
            print(f"fetch_task failed: {e}")
            return None

    def _execute_task(self, task):
        """run the task: generate with vllm, then verify."""
        # generate code with vllm
        if self.vllm and self.vllm.is_alive():
            try:
                gen = self.vllm.generate(
                    prompt=task["prompt"],
                    max_tokens=task.get("max_tokens", 4096),
                    temperature=task.get("temperature", 0.7),
                )
                output = gen["text"]
                tokens = gen["tokens"]
            except Exception as e:
                print(f"inference failed: {e}")
                output = ""
                tokens = 0
        else:
            output = ""
            tokens = 0

        # sandbox verification
        sandbox_cfg = self.config.get("sandbox", {})
        sandbox_result = run_sandboxed(
            {
                "task_id": task["task_id"],
                "prompt": task["prompt"],
                "verifier_cmd": task.get("verifier_cmd", "exit 1"),
                "output": output,
            },
            sandbox_cfg,
        )

        sandbox_result["tokens"] = tokens
        sandbox_result["output"] = output
        return sandbox_result

    def _submit_result(self, task, result):
        """submit task result to coordinator."""
        try:
            resp = self._http.post(f"{self.coord_url}/api/submit_result", json={
                "task_id": task["task_id"],
                "node_id": self.node_id,
                "passed": result.get("passed", False),
                "output": (result.get("output", ""))[:5000],
                "tokens": result.get("tokens", 0),
                "wall_ms": result.get("wall_ms", 0),
                "attestation": result.get("attestation", {}).get("payload", {"task_id": task["task_id"]}),
            })
            resp.raise_for_status()
            data = resp.json()
            status = "PASS" if result.get("passed") else "FAIL"
            print(f"  -> {status} ({result.get('tokens', 0)} tokens, {result.get('wall_ms', 0)}ms) accepted={data.get('accepted')}")
        except Exception as e:
            print(f"submit_result failed: {e}")

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
