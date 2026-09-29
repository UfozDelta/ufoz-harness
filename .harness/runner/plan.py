"""One plan on disk: tasks.json, briefs, reports, the grader lock, and the file scope
each task owns (its own files plus the dep-closure of earlier ones)."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from .guards import lock_hashes


@dataclass
class Task:
    id: str
    acceptance: str
    files: list = field(default_factory=list)
    deps: list = field(default_factory=list)
    expect: str | None = None
    brief: str | None = None
    red_first: bool = True
    build_gate: bool = False
    repair_check: str | None = None
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, d):
        return cls(id=d["id"], acceptance=d.get("acceptance", ""), files=list(d.get("files", [])),
                   deps=list(d.get("deps", [])), expect=d.get("expect"), brief=d.get("brief"),
                   red_first=d.get("red_first", True), build_gate=d.get("build_gate") is True,
                   repair_check=d.get("repair_check"), raw=d)

    def get(self, key, default=None):  # dict-style access for keys this class doesn't name
        return self.raw.get(key, default)

    @property
    def norm_files(self):
        return {f.replace("\\", "/") for f in self.files}


class Plan:
    def __init__(self, slug, plans_root=".harness/plans"):
        self.slug = slug
        self.root = Path(plans_root)
        self.dir = self.root / slug
        self.metrics = self.root.parent / "metrics.jsonl"
        self.run_lock = self.dir / "run.lock"
        self.lock_path = self.dir / "plan.lock.json"
        self.tasks = [Task.load(t) for t in
                      json.loads((self.dir / "tasks.json").read_text(encoding="utf-8"))["tasks"]]
        self.by_id = {t.id: t for t in self.tasks}
        self._lock = None

    @property
    def items(self):
        return self.dir / "items"

    @property
    def logs(self):
        return self.dir / "logs"

    def prepare(self):
        (self.logs).mkdir(exist_ok=True)
        (self.items).mkdir(exist_ok=True)  # slim plans have no briefs, but reports land here

    def report_path(self, tid):
        return self.items / f"{tid}.report.md"

    def log_path(self, tid, suffix, executor):
        return self.logs / (f"{tid}.{executor}.log" if not suffix else f"{tid}.{suffix}.{executor}.log")

    def report_text(self, tid):
        rep = self.report_path(tid)
        return rep.read_text(encoding="utf-8") if rep.exists() else ""

    def passed(self, tid):
        return "RESULT: pass" in self.report_text(tid)

    def brief_of(self, t):  # slim plans: no items/T<n>.md, the task is a `## T<n>` section of plan.md
        if "brief" in t.raw:
            return (self.dir / t.brief).as_posix()
        return f"{(self.dir / 'plan.md').as_posix()}, section `## {t.id}` (plan.md's Decisions apply)"

    def prior_files(self, t):
        """Files the executor may touch while repairing this task: everything listed in
        earlier tasks, plus the dep-closure of the ones it depends on."""
        prior_files = set()
        current_index = next(i for i, task in enumerate(self.tasks) if task is t)
        for earlier in self.tasks[:current_index]:
            prior_files.update(f.replace("\\", "/") for f in earlier.get("files", []))
        pending = list(t.deps)
        visited = set()
        while pending:
            dep = pending.pop()
            if dep in visited or dep not in self.by_id:
                continue
            visited.add(dep)
            earlier = self.by_id[dep]
            prior_files.update(f.replace("\\", "/") for f in earlier.get("files", []))
            pending.extend(earlier.get("deps", []))
        return prior_files

    def lock_grader(self, relock=False):
        """Lock the grader on first run; held in memory so deleting the file mid-run
        changes nothing."""
        if relock or not self.lock_path.exists():
            self.lock_path.write_text(json.dumps(lock_hashes(self.dir), indent=2) + "\n", encoding="utf-8")
        self._lock = json.loads(self.lock_path.read_text(encoding="utf-8"))

    def lock_broken(self):
        if self._lock is None:
            self.lock_grader()
        now = lock_hashes(self.dir)
        return sorted(p for p in self._lock.keys() | now.keys() if self._lock.get(p) != now.get(p))
