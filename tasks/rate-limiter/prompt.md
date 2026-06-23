implement a token bucket rate limiter in python.

class `RateLimiter`:
- `__init__(self, rate, capacity)` -- `rate` tokens per second, max `capacity` tokens
- `allow(self)` -- returns True if a request is allowed, False otherwise
- `wait(self)` -- blocks until a request is allowed, then returns True

use `time.monotonic()` for timing. do not use external libraries.

save to `solution.py`.
