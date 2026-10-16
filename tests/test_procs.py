import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import procs  # noqa: E402

CHILD_SRC = """
import os, subprocess, sys, time

pidfile, gofile = sys.argv[1], sys.argv[2]
while not os.path.exists(gofile):
    time.sleep(0.02)
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
gc = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(120)"],
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
open(pidfile, "w").write(str(gc.pid))
time.sleep(120)
"""


@pytest.mark.skipif(os.name != "nt", reason="job objects are Windows-only")
def test_job_kills_detached_grandchild(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(CHILD_SRC, encoding="utf-8")
    pidfile = tmp_path / "grandchild.pid"
    gofile = tmp_path / "go"

    child = subprocess.Popen([sys.executable, str(script), str(pidfile), str(gofile)])
    try:
        job = procs.create_job()
        assert job
        assert procs.assign_job(job, child.pid)
        procs.register_job(child.pid, job)

        gofile.write_text("go", encoding="utf-8")
        deadline = time.time() + 20
        while time.time() < deadline:
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip():
                break
            time.sleep(0.05)
        grandchild = int(pidfile.read_text(encoding="utf-8").strip())

        assert procs.pid_alive(child.pid)
        assert procs.pid_alive(grandchild)

        procs.stop_process_tree(child, timeout=15)

        assert not procs.pid_alive(child.pid)
        assert not procs.pid_alive(grandchild)
    finally:
        child.wait(timeout=10)
