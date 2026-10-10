import pathlib, subprocess, sys
for f in ("bench/suite/suite.py", "bench/suite/cells.py", "bench/speed/duel.py"):
    for n, line in enumerate(pathlib.Path(f).read_text(encoding="utf-8").splitlines(), 1):
        if "which(" in line or "node_modules" in line:
            continue  # cline_binary() path lookup may stay
        assert '"cline"' not in line and "'cline'" not in line, f"{f}:{n}: {line.strip()}"
sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests/test_harness_suite.py", "-q"]))
