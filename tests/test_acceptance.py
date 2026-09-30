"""Tests for the acceptance runner (real subprocesses, no network)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.acceptance import run_acceptance  # noqa: E402


def test_non_codepage_output_does_not_crash():
    # vitest prints UTF-8 marks; byte 0x9d is undefined in cp1252 and used to leave stdout None
    cmd = f'"{sys.executable}" -c "import sys; sys.stdout.buffer.write(bytes([0xe2, 0x9c, 0x93, 0x9d]) + b\' ok\')"'
    ok, out = run_acceptance(cmd, "ok")
    assert ok
    assert "ok" in out


def test_timeout_with_held_grandchild_pipe_returns_fast():
    # the grandchild keeps the inherited stdout pipe open; communicate() must not wait
    # for it (before: the run hung for the child's full 30s lifetime)
    cmd = (f'"{sys.executable}" -c "import subprocess,sys,time; '
           f"subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
           f'time.sleep(30)"')
    t0 = time.monotonic()
    ok, out = run_acceptance(cmd, None, timeout=1)
    elapsed = time.monotonic() - t0
    assert (ok, out) == (False, "acceptance command timed out")
    assert elapsed < 10, elapsed
