# phage

distributed inference across volunteer GPUs. one coordinator, many nodes, one agent.

kell takes a goal, breaks it into tasks, runs each task on every available GPU,
verifies results with real test suites, and keeps the winners.

more nodes, more attempts, higher success rate.

## how it works

a coordinator (Rust) dispatches work to nodes (Python + vLLM) over gRPC with mTLS.
each node runs sandboxed inference on its local GPU. results are verified by executing
test suites, not by trusting the output. attestation is signed with the node's mTLS key.

kell decides what to run and where. it breaks down goals into subtasks, estimates
difficulty, chooses how many attempts each needs, dispatches them across the culture
(the node pool), evaluates results, and decides what to try next. nodes drop and it
reassigns. new nodes appear and it absorbs them.

## install

```
git clone https://github.com/SuiMotus/phage
cd phage
bash install.sh
```

or manually:

```
pip install -e node/
phage-node init
phage-node register
phage-node start
```

requirements: Linux, Python 3.11+, NVIDIA GPU (8 GB+ VRAM), CUDA 12.1+, Docker.

see `contrib/config.example.toml` for configuration options.

## components

- `coordinator/` -- Rust. node registry, task dispatch, result verification, sticky model routing.
- `node/` -- Python. GPU detection, vLLM management, sandboxed execution, attestation.
- `proto/` -- gRPC service definitions. the wire protocol between coordinator and nodes.
- `tasks/` -- example tasks with prompts and verifier scripts. for testing and calibration.
- `contrib/` -- systemd unit, example config.

## run as a service

```
sudo cp contrib/phage-node.service /etc/systemd/system/
sudo systemctl enable --now phage-node
```

## status

early. the protocol works. verification works. attestation works. dynamic model
loading works. sticky routing works.

planned: tensor parallelism, speculative decoding, autonomous task generation, dashboard.

license: MIT
