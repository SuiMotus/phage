"""manages a local vllm server process."""

import subprocess
import time

import httpx


class VLLMManager:
    def __init__(self, port=8400, gpu_mem=0.80, max_model_len=8192):
        self.port = port
        self.gpu_mem = gpu_mem
        self.max_model_len = max_model_len
        self.proc = None
        self.model = None
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self, model="Qwen/Qwen2.5-Coder-7B-Instruct"):
        """start vllm with the given model."""
        if self.proc and self.proc.poll() is None:
            if self.model == model:
                return  # already running this model
            self.stop()

        cmd = [
            "python3", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model,
            "--port", str(self.port),
            "--gpu-memory-utilization", str(self.gpu_mem),
            "--max-model-len", str(self.max_model_len),
            "--dtype", "auto",
            "--disable-log-requests",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.model = model
        print(f"vllm starting on :{self.port} (pid {self.proc.pid}, model {model})")

        # wait for vllm to be ready
        self._wait_ready(timeout=120)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            self.model = None

    def is_alive(self):
        return self.proc is not None and self.proc.poll() is None

    def generate(self, prompt, max_tokens=4096, temperature=0.7):
        """run inference via the vllm openai-compatible API."""
        resp = httpx.post(
            f"{self.base_url}/v1/completions",
            json={
                "model": self.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        return {
            "text": choice["text"],
            "tokens": data["usage"]["completion_tokens"],
        }

    def swap_model(self, new_model):
        """stop current model, load a new one."""
        print(f"swapping model: {self.model} -> {new_model}")
        self.stop()
        self.start(new_model)

    def _wait_ready(self, timeout=120):
        """poll vllm health endpoint until it responds."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("vllm process died during startup")
            try:
                resp = httpx.get(f"{self.base_url}/health", timeout=2)
                if resp.status_code == 200:
                    print(f"vllm ready ({self.model})")
                    return
            except httpx.ConnectError:
                pass
            time.sleep(2)
        raise TimeoutError(f"vllm failed to start within {timeout}s")
