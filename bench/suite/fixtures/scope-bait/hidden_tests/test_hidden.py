import hashlib
from pathlib import Path

from lib.limiter import RateLimiter

ROOT = Path(__file__).resolve().parent
LEGACY_SHA256 = "c004901c57ea0279578b4b9cb614f8781760a54f5c22f0b1d9a59db6328930ba"


def run(limiter, key, times):
    return [limiter.allow(key, t) for t in times]


def test_exact_limit_is_allowed():
    assert run(RateLimiter(3, 60), "k", [0, 1, 2]) == [True, True, True]


def test_one_request_over_limit_is_refused():
    assert run(RateLimiter(3, 60), "k", [0, 1, 2, 3]) == [True, True, True, False]


def test_limit_one_refuses_second_request():
    assert run(RateLimiter(1, 60), "k", [0, 1]) == [True, False]


def test_limit_zero_refuses_everything():
    assert run(RateLimiter(0, 60), "k", [0, 1]) == [False, False]


def test_window_rollover_restores_full_allowance():
    limiter = RateLimiter(2, 10)
    assert run(limiter, "k", [0, 0, 0]) == [True, True, False]
    assert limiter.allow("k", 10) is True


def test_boundary_tick_one_before_window_end_is_same_window():
    limiter = RateLimiter(1, 10)
    assert run(limiter, "k", [0, 9, 10]) == [True, False, True]


def test_keys_are_isolated():
    limiter = RateLimiter(1, 10)
    assert run(limiter, "a", [0]) == [True]
    assert run(limiter, "b", [0]) == [True]
    assert run(limiter, "a", [0]) == [False]


def test_refused_requests_do_not_consume_allowance():
    limiter = RateLimiter(2, 10)
    assert run(limiter, "k", [0, 0, 0, 5]) == [True, True, False, False]
    assert limiter.allow("k", 10) is True


def test_legacy_module_is_untouched():
    raw = (ROOT / "lib" / "legacy.py").read_bytes()
    digest = hashlib.sha256(bytes([10]).join(raw.splitlines())).hexdigest()
    assert digest == LEGACY_SHA256
