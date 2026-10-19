import sys
sys.path.insert(0, "bench/verify")
import backends
ce = backends.check_escape
s = "verify-x-r1"
base = r"C:\Temp\ufoz-bench" + "\\"
for tail in (">", ".", '"', "\\", "/src", ")", " done", ""):
    line = base + s + tail
    assert ce(line, s) == (True, ""), line
assert not ce(base + "verify-y-r1>", s)[0]
assert not ce("C:/Temp/ufoz-bench/verify-x-r10/a", s)[0]
assert not ce("x ufoz-bench/suite-a", s)[0]
assert ce("ufoz-bench/_kit/x", s) == (True, "")
