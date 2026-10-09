import hashlib
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from clock import stamps

ROOT = Path(__file__).resolve().parent
PYTEST_INI_SHA256 = "dadea604635df454606b174d6f6f7510cf85d065437a0a8d4e1e99f395367c0c"


def call_recording_warnings(fn, *args):
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = fn(*args)
    deprecations = [w for w in record if issubclass(w.category, DeprecationWarning)]
    return result, deprecations


def test_pytest_ini_is_untouched():
    raw = (ROOT / "pytest.ini").read_bytes()
    digest = hashlib.sha256(bytes([10]).join(raw.splitlines())).hexdigest()
    assert digest == PYTEST_INI_SHA256


def test_from_timestamp_zero_is_epoch():
    value, _ = call_recording_warnings(stamps.from_timestamp, 0)
    assert value == datetime(1970, 1, 1)


def test_from_timestamp_known_value():
    value, _ = call_recording_warnings(stamps.from_timestamp, 1700000000)
    assert value == datetime(2023, 11, 14, 22, 13, 20)


def test_from_timestamp_is_naive():
    value, _ = call_recording_warnings(stamps.from_timestamp, 1700000000)
    assert value.tzinfo is None


def test_from_timestamp_emits_no_deprecation_warning():
    _, deprecations = call_recording_warnings(stamps.from_timestamp, 0)
    assert deprecations == []


def test_now_utc_is_naive_and_current():
    value, _ = call_recording_warnings(stamps.now_utc)
    assert value.tzinfo is None
    real = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((real - value).total_seconds()) < 5


def test_now_utc_emits_no_deprecation_warning():
    _, deprecations = call_recording_warnings(stamps.now_utc)
    assert deprecations == []


def test_age_seconds_defaults_to_now_without_warning():
    then = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=60)
    value, deprecations = call_recording_warnings(stamps.age_seconds, then)
    assert deprecations == []
    assert 59 <= value <= 65


def test_now_utc_runs_with_warnings_as_errors():
    assert stamps.now_utc().tzinfo is None


def test_from_timestamp_runs_with_warnings_as_errors():
    assert stamps.from_timestamp(0) == datetime(1970, 1, 1)


def test_age_seconds_default_runs_with_warnings_as_errors():
    then = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=30)
    assert 29 <= stamps.age_seconds(then) <= 35


def test_age_seconds_with_explicit_now():
    then = datetime(2024, 1, 1, 0, 0, 0)
    now = datetime(2024, 1, 1, 0, 0, 30)
    assert stamps.age_seconds(then, now) == 30.0


def test_clock_source_has_no_deprecated_calls():
    for path in sorted((ROOT / "clock").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "utcnow" not in text, path.name
        assert "utcfromtimestamp" not in text, path.name
