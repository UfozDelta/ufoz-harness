import sys
sys.path.insert(0, "bench/verify")
import backends
ce = backends.check_escape
assert ce("ls C:/Users/x/Temp/ufoz-bench/verify-pi-pi-pi-r1/src", "verify-pi-pi-pi-r1") == (True, "")
assert ce("ls C:/Users/x/Temp/ufoz-bench/_kit/", "verify-pi-pi-pi-r1")[0] is True
ok, line = ce("Read C:/Temp/ufoz-bench/verify-a-b-c-r1/test_hidden.py failed", "verify-pi-pi-pi-r1")
assert not ok and "test_hidden" in line
assert not ce(r"cat C:\Temp\ufoz-bench\suite-x\a.py", "verify-pi-pi-pi-r1")[0]
assert not ce("cat bench/suite/fixtures/small/hidden_tests/t.py", "s")[0]
assert ce("", "s") == (True, "") and ce(None, "s") == (True, "")
