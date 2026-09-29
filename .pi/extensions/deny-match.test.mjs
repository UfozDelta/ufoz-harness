// Run: node .pi/extensions/deny-match.test.mjs
import fs from "node:fs";
import path from "node:path";
import { registerHooks } from "node:module";
import { fileURLToPath } from "node:url";

// The root package.json is "type": "commonjs", so node would load .ts files as CJS and
// their named exports would be invisible to this ESM test. Force the TS-ESM loader.
registerHooks({
	load(url, context, nextLoad) {
		if (url.endsWith(".ts")) {
			return { format: "module-typescript", source: fs.readFileSync(fileURLToPath(url), "utf8"), shortCircuit: true };
		}
		return nextLoad(url, context);
	},
});
const { isChecksPath, isDeniedBash, isOutside } = await import("./deny-match.ts");

const here = path.dirname(fileURLToPath(import.meta.url));
const rules = JSON.parse(fs.readFileSync(path.join(here, "..", "deny.json"), "utf8"));

const blocked = [
	"git commit -m x",
	"git -C . push",
	"echo a && git reset --hard",
	"FOO=1 git stash",
	'bash -c "git add ."',
	"git checkout main",
	"git --git-dir=.git rebase main",
	"ls | git clean -fd",
	"sudo git switch dev",
	"/usr/bin/git restore .",
	"echo $(git stash pop)",
	"git merge dev",
	"git branch -D x",
];
const allowed = ["git status", "git diff", "git log --oneline", "echo git commit", "ls", "python -m pytest", "git -C . status"];

let fail = 0;
for (const c of blocked) if (!isDeniedBash(c, rules)) { console.log("NOT BLOCKED:", c); fail++; }
for (const c of allowed) if (isDeniedBash(c, rules)) { console.log("WRONGLY BLOCKED:", c); fail++; }

const cwd = path.resolve("proj");
const pathCases = [["../x", true], ["sub/x", false], ["x.txt", false], [path.resolve("elsewhere/y"), true], [path.join(cwd, "a/b"), false]];
for (const [p, want] of pathCases) if (isOutside(cwd, p) !== want) { console.log("PATH WRONG:", p, "want", want); fail++; }

const checksCases = [
	["checks/check_t1.py", true],
	[path.join(".harness", "plans", "x", "checks", "check_t1.py"), true],
	[path.join(".harness", "plans", "x", "plan.md"), false],
	[path.join(".harness", "plans", "x", "checks.md"), false],
	[path.join(".harness", "checksnotes", "a.py"), false],
];
for (const [p, want] of checksCases) if (isChecksPath(cwd, p) !== want) { console.log("CHECKS WRONG:", p, "want", want); fail++; }

console.log(fail ? `FAIL ${fail}` : "OK");
process.exit(fail ? 1 : 0);
