import sys, time
sys.path.insert(0, "bench/verify")
import verify
code = ("import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
        "print('hi', flush=True); time.sleep(120)")
t0 = time.time()
rc, out, timed_out = verify._run_cmd([sys.executable, "-c", code], ".", 3)
assert timed_out and rc is None, (rc, timed_out)
assert time.time() - t0 < 40, time.time() - t0
assert "hi" in out, out
rc, out, timed_out = verify._run_cmd([sys.executable, "-c", "print('ok')"], ".", 30)
assert rc == 0 and not timed_out and "ok" in out
