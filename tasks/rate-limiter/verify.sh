#!/bin/bash
set -e
python3 -c "
import time
from solution import RateLimiter

# basic allow/deny
rl = RateLimiter(rate=10, capacity=5)
allowed = sum(rl.allow() for _ in range(10))
assert allowed == 5, f'expected 5, got {allowed}'

# refill
time.sleep(0.3)
assert rl.allow(), 'should have refilled'

# wait blocks
rl2 = RateLimiter(rate=100, capacity=1)
rl2.allow()
start = time.monotonic()
rl2.wait()
elapsed = time.monotonic() - start
assert elapsed < 0.1, f'wait took too long: {elapsed}'

print('all tests passed')
"
