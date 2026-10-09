import sys

sys.path.insert(0, ".harness/plans/bench-isolate/checks")
from _common import cells, cell, fake_kit, subjects  # noqa: E402

assert callable(cells.ensure_kit) and issubclass(cells.ProjectError, Exception)
assert cells.node_modules_cache("small", cells.REPO_ROOT) is None
c = cell(98)
project = cells.make_project(c, kit=fake_kit())
try:
    assert project.is_dir() and str(project).startswith(str(cells.TEMP_ROOT))
    assert subjects(project) == ["harness", "seed"], subjects(project)
    assert (project / "HARNESS.txt").is_file()
    assert c["project"] and c["seed_commit"]
finally:
    cells.cleanup_project(c)
assert not project.exists()
print("T3 OK")
