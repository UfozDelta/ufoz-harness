"""Task registry: discovers fixtures/ dirs and builds cell slugs and arms."""
import re
import tomllib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIELDS = ("capability", "lang", "source", "licence", "description")


def discover_tasks() -> dict[str, dict]:
    tasks = {}
    for d in sorted(FIXTURES.iterdir()):
        if not d.is_dir() or d.name[0] in "_.":
            continue
        meta = {k: "" for k in FIELDS}
        meta["capability"] = "multi-file-feature"
        toml = d / "task.toml"
        if toml.exists():
            try:
                data = tomllib.loads(toml.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                raise ValueError(f"bad task.toml {toml}: {e}") from e
            for k in FIELDS:
                if k in data:
                    meta[k] = str(data[k])
        tasks[d.name] = {"id": d.name, **meta,
                         "has_plan_project": (d / "plan_project").is_dir()}
    return tasks


def model_slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def cell_slug(task: str, mode: str, executor: str, model: str, rep) -> str:
    m = model_slug(model) if model else ""
    return f"suite-{task}-{mode}-{executor}{'-' + m if m else ''}-r{rep}"


def parse_arms(value: str) -> list[tuple[str, str]]:
    arms = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        ex, _, model = part.partition(":")
        arms.append((ex, model))
    return arms
