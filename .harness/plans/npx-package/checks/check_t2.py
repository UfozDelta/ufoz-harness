import sys
from pathlib import Path

PKG = Path("packages/ufoz-harness")
readme = (PKG / "README.md").read_text(encoding="utf-8")
for s in ["npx ufoz-harness", "npm publish", "pi-launcher.js", ".env.example"]:
    if s not in readme:
        sys.exit(f"FAIL README lacks {s}")
kr = (PKG / "kit_readme.md").read_text(encoding="utf-8")
for s in ["build_map.py", ".harness/.env", "llama"]:
    if s not in kr:
        sys.exit(f"FAIL kit_readme lacks {s}")
if "Apache-2.0" not in (PKG / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"):
    sys.exit("FAIL notices lack frontend-design")
s = Path(".harness/plans/npx-package/SUMMARY.md")
if not s.is_file() or not (0 < len(s.read_text(encoding="utf-8")) <= 600):
    sys.exit("FAIL SUMMARY.md missing or > 600 chars")
print("OK")
