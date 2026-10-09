# Spec (deprecation-cleanup): stop using deprecated datetime calls in clock helpers

Our `clock` helpers call `datetime.utcnow()` and `datetime.utcfromtimestamp()`, which raise deprecation warnings on newer Python, and our test config turns warnings into errors, so the helpers break. Please move them off the deprecated calls without changing what they return: `now_utc()`, `from_timestamp(ts)` and `age_seconds(then, now=None)` must still give naive UTC datetimes and the same numbers as before. Do not edit `pytest.ini`, since the warnings-as-errors setting is intentional.
