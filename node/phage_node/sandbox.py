"""sandboxed task execution via gvisor or docker."""

import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
import time

from .attestation import build_attestation


def run_sandboxed(task, sandbox_config, node_key_path=None):
    """execute a task inside a gvisor/docker sandbox.

    the sandbox has:
    - no network access
    - read-only root filesystem
    - writable scratch directory (tmpfs)
    - enforced time limit
    - resource caps (cpu, memory)
    """
    runtime = sandbox_config.get("runtime", "gvisor")
    max_time = sandbox_config.get("max_runtime_sec", 300)
    scratch = tempfile.mkdtemp(dir=sandbox_config.get("scratch_dir", "/tmp/phage/scratch"))

    task_id = task.get("task_id", "unknown")
    prompt = task.get("prompt", "")
    workspace_tar = task.get("workspace_tar")
    verifier = task.get("verifier_cmd", "exit 1")

    # extract workspace if provided
    if workspace_tar:
        workspace_path = os.path.join(scratch, "workspace")
        os.makedirs(workspace_path, exist_ok=True)
        tar_path = os.path.join(scratch, "workspace.tar")
        with open(tar_path, "wb") as f:
            f.write(workspace_tar)
        with tarfile.open(tar_path) as tf:
            tf.extractall(workspace_path)

    # hash inputs for attestation
    input_hash = hashlib.sha256(
        json.dumps({"prompt": prompt, "verifier": verifier}, sort_keys=True).encode()
    ).hexdigest()

    # build container command
    container_name = f"phage-task-{task_id[:12]}"
    run_cmd = _build_run_command(
        runtime=runtime,
        container_name=container_name,
        scratch_dir=scratch,
        max_time=max_time,
    )

    start = time.monotonic()

    try:
        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            timeout=max_time + 10,
            cwd=scratch,
        )
        output = result.stdout
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        output = ""
        exit_code = -1
        _kill_container(container_name)
    finally:
        wall_ms = int((time.monotonic() - start) * 1000)

    # run verifier
    passed = False
    if exit_code == 0:
        try:
            vresult = subprocess.run(
                ["bash", "-c", verifier],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=scratch,
            )
            passed = vresult.returncode == 0
        except subprocess.TimeoutExpired:
            passed = False

    attestation = build_attestation(
        task_id=task_id,
        sandbox_config=sandbox_config,
        input_hash=input_hash,
        output=output,
        node_key_path=node_key_path,
    )

    return {
        "task_id": task_id,
        "passed": passed,
        "output": output,
        "tokens": _estimate_tokens(output),
        "wall_ms": wall_ms,
        "attestation": attestation,
    }


def _build_run_command(runtime, container_name, scratch_dir, max_time):
    """build the docker/gvisor run command."""
    cmd = [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--runtime", runtime if runtime == "runsc" else "runc",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:size=512m",
        "--memory", "4g",
        "--cpus", "2",
        "-v", f"{scratch_dir}:/workspace:ro",
        "-w", "/workspace",
        "phage-sandbox:latest",
        "timeout", str(max_time),
        "bash", "-c", "python3 run.py",
    ]
    return cmd


def _kill_container(name):
    try:
        subprocess.run(["docker", "kill", name], capture_output=True, timeout=5)
    except Exception:
        pass


def _estimate_tokens(text):
    """rough token estimate. ~4 chars per token for code."""
    return len(text) // 4
