"""Fixed-window rate limiter with one window per key."""


class RateLimiter:
    """Allow up to `limit` requests per key in each `window` seconds."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._state: dict[str, tuple[float, int]] = {}

    def allow(self, key: str, now: float) -> bool:
        start, count = self._state.get(key, (now, 0))
        if now - start >= self.window:
            start, count = now, 0
        allowed = count <= self.limit
        if allowed:
            count += 1
        self._state[key] = (start, count)
        return allowed
