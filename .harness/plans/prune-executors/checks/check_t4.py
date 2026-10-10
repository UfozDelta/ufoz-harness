import pathlib, re
for f in (".harness/HARNESS.md", ".harness/MAIN.md"):
    t = pathlib.Path(f).read_text(encoding="utf-8")
    assert not re.search(r"--executor cline(?![-\w])", t), f
    assert "cline-acp" in t, f
    assert "cold: a fresh session" not in t, f
