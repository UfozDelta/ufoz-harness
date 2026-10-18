import sys, tempfile
sys.path.insert(0, "bench/verify")
import verify
with tempfile.TemporaryDirectory() as t:
    b = verify._plan_brief({"slug": "verify-x-r1", "size": "small"}, t)
assert "current directory" in b and "Do not read anything under .pi/" in b
