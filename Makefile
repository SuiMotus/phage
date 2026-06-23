.PHONY: build run-coordinator run-node proto install clean test

build:
	cd coordinator && cargo build --release

run-coordinator:
	cd coordinator && cargo run

run-node:
	cd node && python -m phage_node.cli start

install:
	bash install.sh

proto:
	protoc --proto_path=proto proto/phage.proto \
		--python_out=node/phage_node \
		--prost_out=coordinator/src

test:
	@echo "running task verifiers..."
	@for dir in tasks/*/; do \
		name=$$(basename $$dir); \
		if [ -f "$$dir/verify.sh" ]; then \
			echo "  $$name..."; \
			cd "$$dir" && bash verify.sh 2>/dev/null && echo "    pass" || echo "    fail (expected, needs solution.py)"; \
			cd ../..; \
		fi; \
	done

clean:
	cd coordinator && cargo clean
	rm -rf node/phage_node/*_pb2.py
	rm -rf node/*.egg-info node/dist
