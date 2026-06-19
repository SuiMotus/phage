"""sandboxed task execution via gvisor or docker."""

import subprocess
import tempfile


def run_sandboxed(task, sandbox_config):
    runtime = sandbox_config.get("runtime", "docker")
    max_time = sandbox_config.get("max_runtime_sec", 300)
    scratch = tempfile.mkdtemp(dir=sandbox_config.get("scratch_dir", "/tmp/phage"))

    return {
        "task_id": task.get("task_id"),
        "passed": False,
        "output": "",
        "tokens": 0,
        "wall_ms": 0,
    }
