import re
import sys
from pathlib import Path

st = Path(".harness/selftest.py").read_text(encoding="utf-8")
bn = Path(".harness/bench/bench.py").read_text(encoding="utf-8")
if st.count("--no-worktree") < 1 or st.count("--no-window") < 1:
    sys.exit("FAIL selftest.py lacks opt-outs")
if bn.count("--no-worktree") < 2 or bn.count("--no-window") < 2:
    sys.exit("FAIL bench.py needs opt-outs on both real-run calls")
for m in re.finditer(r'"bench-plan", "--lint"', bn):
    pass
compile(st, "selftest.py", "exec")
compile(bn, "bench.py", "exec")
print("OK")
