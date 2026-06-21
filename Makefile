.PHONY: build run-coordinator run-node proto clean

build:
	cd coordinator && cargo build --release

run-coordinator:
	cd coordinator && cargo run

run-node:
	cd node && python -m phage_node.cli start

proto:
	protoc --proto_path=proto proto/phage.proto \
		--python_out=node/phage_node \
		--prost_out=coordinator/src

clean:
	cd coordinator && cargo clean
	rm -rf node/phage_node/*_pb2.py
