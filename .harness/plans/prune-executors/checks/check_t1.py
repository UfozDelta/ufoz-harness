import pathlib, subprocess, sys
sys.path.insert(0, ".harness")
from runner.executors import REGISTRY
assert "cline" not in REGISTRY and "cline-acp" in REGISTRY, sorted(REGISTRY)
assert not pathlib.Path(".harness/runner/executors/cline.py").exists()
for f in (".harness/runner/watch.py", ".claude/skills/harness-band/hooks/register.tsx"):
    assert "'cline'" not in pathlib.Path(f).read_text(encoding="utf-8") and '"cline"' not in pathlib.Path(f).read_text(encoding="utf-8"), f
sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests/test_task_runner.py", "tests/test_scope.py", "-q"]))
