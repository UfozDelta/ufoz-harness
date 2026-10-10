import pathlib, re
files = ["README.md", "docs/ARCHITECTURE.md", "docs/FLOWS.md", "docs/mermaid.md",
         "packages/ufoz-harness/README.md", "packages/ufoz-harness/kit_readme.md"]
pat = re.compile(r"--executor cline(?![-\w])|, cline,|\|cline\||/ cline /|opencode\|cline\||`cline` and|`cline`,")
bad = [f for f in files if pat.search(pathlib.Path(f).read_text(encoding="utf-8"))]
assert not bad, bad
assert "cline-acp" in pathlib.Path("README.md").read_text(encoding="utf-8")
assert "llama" in pathlib.Path("README.md").read_text(encoding="utf-8")
import re
env = pathlib.Path(".harness/.env.example").read_text(encoding="utf-8")
assert not re.search(r"and cline(?![-\w])|claude, cline or", env), ".harness/.env.example"
assert "cline-acp" in env
