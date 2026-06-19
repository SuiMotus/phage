"""manages a local vllm server process."""

import subprocess
import time


class VLLMManager:
    def __init__(self, port=8400, gpu_mem=0.80):
        self.port = port
        self.gpu_mem = gpu_mem
        self.proc = None

    def start(self, model="Qwen/Qwen2.5-Coder-7B-Instruct"):
        cmd = [
            "python3", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model,
            "--port", str(self.port),
            "--gpu-memory-utilization", str(self.gpu_mem),
            "--dtype", "auto",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"vllm started on :{self.port} (pid {self.proc.pid})")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=10)

    def is_alive(self):
        return self.proc and self.proc.poll() is None
