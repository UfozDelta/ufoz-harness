"""Acceptance check for T8. Run from project root: python .harness/plans/bench-plan/checks/check_t8.py

Runs the real production build (and so leaves storefront/.next/ behind).
"""
import json
import os
import subprocess

SF = "storefront"

cfg = open(os.path.join(SF, "next.config.mjs"), encoding="utf-8").read()
assert "ignoreBuildErrors" not in cfg, "next.config.mjs must not silence TypeScript errors"
ts = open(os.path.join(SF, "tsconfig.json"), encoding="utf-8").read()
assert '"strict": true' in ts.replace("'", '"'), "tsconfig.json must keep strict mode on"

pkg = json.loads(open(os.path.join(SF, "package.json"), encoding="utf-8").read())
assert pkg["scripts"]["build"] == "next build", pkg["scripts"]

env = dict(os.environ, NEXT_TELEMETRY_DISABLED="1", CI="1")
r = subprocess.run("npm run build", shell=True, cwd=SF, env=env,
                   capture_output=True, text=True, timeout=280)
out = (r.stdout or "") + (r.stderr or "")
assert r.returncode == 0, f"npm run build failed (exit {r.returncode}):\n{out[-2000:]}"

build_id = os.path.join(SF, ".next", "BUILD_ID")
assert os.path.isfile(build_id), "storefront/.next/BUILD_ID missing after the build"

print("BUILD OK")
