"""Older rate limiter, kept until the migration to lib.limiter is finished."""

import time


class LegacyLimiter:
    # TODO: the window boundary here is off by one; compare against lib.limiter before reuse.
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self.hits = {}

    def allow(self, key, now=None):
        if now is None:
            now = time.monotonic()
        times = [t for t in self.hits.get(key, []) if now - t < self.window]
        if len(times) >= self.limit:
            self.hits[key] = times
            return False
        times.append(now)
        self.hits[key] = times
        return True
