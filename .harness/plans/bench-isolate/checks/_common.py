import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "bench/suite")
import cells  # noqa: E402


def fake_kit():
    root = Path(tempfile.mkdtemp(prefix="fakekit"))
    (root / "index.js").write_text(
        "const fs=require('fs');const i=process.argv.indexOf('--dir');"
        "fs.writeFileSync(process.argv[i+1]+'/HARNESS.txt','kit');", encoding="utf-8")
    return root, "fake1234"


def cell(rep, **extra):
    c = {"slug": f"suite-small-serial-pi-r{rep}", "size": "small", "mode": "serial",
         "executor": "pi", "rep": rep}
    c.update(extra)
    return c


def subjects(project):
    out = subprocess.run(["git", "log", "--format=%s"], cwd=str(project), capture_output=True,
                         text=True, check=True).stdout
    return out.split()
