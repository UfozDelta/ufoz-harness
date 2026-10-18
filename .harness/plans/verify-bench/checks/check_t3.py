"""Acceptance: `verify.py --dry` prints exactly 27 distinct cell slugs and exits 0."""
import subprocess
import sys


def main():
    proc = subprocess.run([sys.executable, "bench/verify/verify.py", "--dry"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out[-800:]
    slugs = [ln.split()[0] for ln in out.splitlines()
             if ln.split() and ln.split()[0].startswith("verify-")]
    assert len(slugs) == 27, f"{len(slugs)} cells\n{out[-800:]}"
    assert len(set(slugs)) == 27, "duplicate slugs"
    print("DRY OK")
    return 0


raise SystemExit(main())
