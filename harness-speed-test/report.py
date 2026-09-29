#!/usr/bin/env python3
"""Create a Markdown comparison report from harness speed-test results."""

import argparse
import csv
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "harness-speed-test" / "results.csv"
DEFAULT_OUT = ROOT / "harness-speed-test" / "RESULTS.md"
COLUMNS = [
    ("runs", "Runs"),
    ("pass rate", "Pass rate"),
    ("median wall_s", "Median wall_s"),
    ("median output tokens", "Median output tokens"),
    ("median input+cache_read tokens", "Median input+cache_read tokens"),
    ("median tool_calls", "Median tool_calls"),
    ("median turns", "Median turns"),
]


def number(row, key):
    value = row.get(key, 0) or 0
    return float(value)


def display(value):
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def table(title, rows, level=2):
    lines = [f"{'#' * level} {title}", ""]
    lines.append("| " + " | ".join(label for _, label in COLUMNS) + " |")
    lines.append("| " + " | ".join("---" for _ in COLUMNS) + " |")
    for harness in sorted({row["harness"] for row in rows}):
        group = [row for row in rows if row["harness"] == harness]
        passed = sum(
            number(row, "tests_passed") == number(row, "tests_total")
            and number(row, "tests_total") > 0
            for row in group
        )
        pass_rate = f"{100 * passed / len(group):.1f}%" if group else "0.0%"
        input_cache = [number(row, "input") + number(row, "cache_read") for row in group]
        values = [
            str(len(group)),
            pass_rate,
            display(median(number(row, "wall_s") for row in group)),
            display(median(number(row, "output") for row in group)),
            display(median(input_cache)),
            display(median(number(row, "tool_calls") for row in group)),
            display(median(number(row, "turns") for row in group)),
        ]
        lines.append("| " + harness + " | " + " | ".join(values) + " |")
    lines.append("")
    return lines


def build_report(rows):
    models = sorted({row.get("model", "") for row in rows if row.get("model", "")})
    model_text = ", ".join(models) if models else "no models"
    lines = [f"# Harness comparison: {model_text}", ""]
    tasks = []
    for row in rows:
        task = row.get("task", "")
        if task not in tasks:
            tasks.append(task)
    for task in tasks:
        lines.extend(table(task, [row for row in rows if row.get("task", "") == task]))
    lines.extend(table("Overall", rows))
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    with args.csv.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_report(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
