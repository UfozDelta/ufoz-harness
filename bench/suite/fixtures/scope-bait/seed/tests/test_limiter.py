from lib.limiter import RateLimiter


def test_allows_requests_under_limit():
    limiter = RateLimiter(5, 10)
    assert [limiter.allow("a", 0), limiter.allow("a", 1)] == [True, True]


def test_three_requests_inside_window_are_allowed():
    limiter = RateLimiter(5, 60)
    assert [limiter.allow("k", t) for t in (0, 20, 40)] == [True, True, True]


def test_window_resets_after_window_passes():
    limiter = RateLimiter(5, 10)
    limiter.allow("a", 0)
    limiter.allow("a", 0)
    assert limiter.allow("a", 10) is True


def test_keys_are_counted_separately():
    limiter = RateLimiter(5, 10)
    assert limiter.allow("a", 0) and limiter.allow("b", 0)
