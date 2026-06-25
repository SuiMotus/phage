#!/bin/bash
set -e

echo "phage-node installer"
echo "===================="
echo

# check python
if ! command -v python3 &>/dev/null; then
    echo "error: python3 not found"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "error: python 3.11+ required (found $PY_VERSION)"
    exit 1
fi

echo "python:  $PY_VERSION"

# check nvidia
if ! command -v nvidia-smi &>/dev/null; then
    echo "error: nvidia-smi not found. install NVIDIA drivers first."
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -1)
GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)

echo "gpu:     $GPU_NAME ($GPU_VRAM MB)"
echo "driver:  $DRIVER"

if [ "$GPU_VRAM" -lt 8000 ]; then
    echo "error: 8 GB+ VRAM required"
    exit 1
fi

# check cuda
if ! command -v nvcc &>/dev/null; then
    echo "warning: nvcc not found. vllm may handle CUDA internally."
else
    CUDA_VER=$(nvcc --version | grep "release" | sed 's/.*release \([0-9.]*\).*/\1/')
    echo "cuda:    $CUDA_VER"
fi

# check docker (for gvisor sandbox)
if ! command -v docker &>/dev/null; then
    echo "warning: docker not found. sandbox execution requires docker + gvisor."
    echo "         install docker and runsc (gvisor) for full functionality."
fi

echo

# install phage-node
echo "installing phage-node..."
pip install --user -e node/ 2>&1 | tail -1

# create config directory
PHAGE_DIR="$HOME/.phage"
mkdir -p "$PHAGE_DIR/certs"

# write default config if not present
if [ ! -f "$PHAGE_DIR/config.toml" ]; then
    cat > "$PHAGE_DIR/config.toml" << 'EOF'
[coordinator]
url = "https://kellphage.com"

[gpu]
device = 0
max_vram_pct = 85

[sandbox]
runtime = "gvisor"
max_runtime_sec = 300

[vllm]
port = 8400
gpu_memory_utilization = 0.80
max_model_len = 8192

[heartbeat]
interval_sec = 10

[logging]
level = "info"
file = "~/.phage/phage-node.log"
EOF
    echo "wrote config to $PHAGE_DIR/config.toml"
else
    echo "config already exists at $PHAGE_DIR/config.toml"
fi

echo
echo "install complete."
echo
echo "next steps:"
echo "  1. edit ~/.phage/config.toml (set coordinator URL)"
echo "  2. phage-node register"
echo "  3. phage-node start"
echo
echo "run as service:"
echo "  sudo cp contrib/phage-node.service /etc/systemd/system/"
echo "  sudo systemctl enable --now phage-node"
