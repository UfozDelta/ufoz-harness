"""Acceptance check for T1. Run from project root: python .harness/plans/bench-plan/checks/check_t1.py"""
import json
import os

SF = "storefront"


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8").read()


pkg = json.loads(read("package.json"))
assert pkg.get("scripts", {}).get("build") == "next build", pkg.get("scripts")
assert pkg.get("scripts", {}).get("dev") == "next dev", pkg.get("scripts")

deps = pkg.get("dependencies", {})
for name, version in (("next", "14.2.15"), ("react", "18.3.1"), ("react-dom", "18.3.1")):
    assert deps.get(name) == version, f"dependencies.{name} must be {version}, got {deps.get(name)}"
assert set(deps) == {"next", "react", "react-dom"}, f"unexpected dependencies: {sorted(deps)}"

dev = pkg.get("devDependencies", {})
for name in ("typescript", "@types/node", "@types/react", "@types/react-dom"):
    assert name in dev, f"missing devDependency {name}"
assert set(dev) == {"typescript", "@types/node", "@types/react", "@types/react-dom"}, sorted(dev)

ts = read("tsconfig.json")
for needle in ('"strict"', '"jsx"', '"preserve"', '"noEmit"', '"next-env.d.ts"'):
    assert needle in ts, f"tsconfig.json missing {needle}"

cfg = read("next.config.mjs")
assert "export default" in cfg, "next.config.mjs must have a default export"

ignore = read(".gitignore")
for needle in ("node_modules", ".next"):
    assert needle in ignore, f".gitignore missing {needle}"

env = read(".env.local")
for line in ("NEXT_PUBLIC_META_PIXEL_ID=000000000000000",
             "NEXT_PUBLIC_TIKTOK_PIXEL_ID=CXXXXXXXXXXXXXXXXXXX",
             "NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX"):
    assert line in env, f".env.local missing line: {line}"

assert os.path.isfile(os.path.join(SF, "node_modules", "next", "package.json")), \
    "npm install did not run: storefront/node_modules/next is missing"

print("SCAFFOLD OK")
