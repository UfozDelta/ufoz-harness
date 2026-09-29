"""Summarize runs/arms.csv: per arm x task means, eligibility (100% hidden on every rep), ranking by $ x minutes.

Usage: python .harness/bench/summarize_arms.py [--exclude task,arm,rep ...]
Prints Markdown tables for RESULTS.md.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV = HERE / "runs" / "arms.csv" if (HERE / "runs" / "arms.csv").exists() else HERE / "data" / "arms.csv"
ARMS = ["A", "P", "C", "S1", "S2", "S3", "S1-bunny", "C-bunny", "S3-bunny", "L", "H"]
TASKS = ["medium", "large", "large_lego", "crm"]


def main():
    excl = set(sys.argv[sys.argv.index("--exclude") + 1:]) if "--exclude" in sys.argv else set()
    rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8"))
            if f"{r['task']},{r['arm']},{r['rep']}" not in excl]
    by = defaultdict(list)
    for r in rows:
        by[(r["task"], r["arm"])].append(r)

    print("| task | arm | reps | plan $ | build $ | review $ | total $ | plan min | build min | wall min | hidden | retries |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t in TASKS:
        for a in ARMS:
            rs = by.get((t, a))
            if not rs:
                continue
            f = lambda k: sum(float(r[k]) for r in rs) / len(rs)
            hidden = " ".join(f"{r['hidden_passed']}/{int(r['hidden_passed']) + int(r['hidden_failed'])}" for r in rs)
            print(f"| {t} | {a} | {len(rs)} | {f('plan_usd'):.2f} | {f('build_usd'):.2f} | {f('review_usd'):.2f} | "
                  f"{f('total_usd'):.2f} | {f('plan_min'):.1f} | {f('build_min'):.1f} | {f('wall_min'):.1f} | "
                  f"{hidden} | {sum(int(r['retries']) for r in rs)} |")

    print("\n**Ranking** (eligible = every rep passed 100% of hidden tests; score = mean total $ x mean wall min)\n")
    print("| arm | eligible | fails | mean total $ | mean wall min | $ x min |")
    print("|---|---|---|---|---|---|")
    ranked = []
    for a in ARMS:
        rs = [r for r in rows if r["arm"] == a]
        if not rs:
            continue
        fails = [f"{r['task']}#{r['rep']}" for r in rs if int(r["hidden_failed"]) > 0]
        usd = sum(float(r["total_usd"]) for r in rs) / len(rs)
        mins = sum(float(r["wall_min"]) for r in rs) / len(rs)
        ranked.append((bool(fails), usd * mins, a, fails, usd, mins))
    for inelig, score, a, fails, usd, mins in sorted(ranked):
        print(f"| {a} | {'no' if inelig else 'yes'} | {', '.join(fails) or '-'} | {usd:.2f} | {mins:.1f} | {score:.2f} |")

    print("\n**Per task, $ x min** (mean over reps; * = a rep failed hidden tests)\n")
    print("| task | " + " | ".join(ARMS) + " |")
    print("|---|" + "---|" * len(ARMS))
    for t in TASKS:
        cells = []
        for a in ARMS:
            rs = by.get((t, a))
            if not rs:
                cells.append("-")
                continue
            usd = sum(float(r["total_usd"]) for r in rs) / len(rs)
            mins = sum(float(r["wall_min"]) for r in rs) / len(rs)
            bad = any(int(r["hidden_failed"]) > 0 for r in rs)
            cells.append(f"{usd * mins:.2f}{'*' if bad else ''}")
        print(f"| {t} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
