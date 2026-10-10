t = open("log.md", encoding="utf-8").read()
assert "## 2026-09-29 oc-speed" not in t
assert "## 2026-09-30 oc-speed" in t and "## 2026-09-30 repo-cleanup" in t and "## 2026-09-30 usability-goal" in t
