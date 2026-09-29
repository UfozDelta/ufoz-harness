// Pure deny-list matching for the pi deny-list extension. No pi imports, so
// Node can load it directly (type stripping) for deny-match.test.mjs.
import path from "node:path";

export interface DenyRules {
	bash: string[];
	external_directory?: "deny" | "allow";
}

// Git global options that take a separate value argument.
const GIT_OPTS_WITH_VALUE = new Set(["-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"]);
const WRAPPERS = new Set(["sudo", "env", "command", "exec", "nohup", "time"]);

function tokenize(segment: string): string[] {
	const tokens: string[] = [];
	const re = /"((?:\\.|[^"\\])*)"|'([^']*)'|(\S+)/g;
	let m: RegExpExecArray | null;
	while ((m = re.exec(segment)) !== null) tokens.push(m[1] ?? m[2] ?? m[3]);
	return tokens;
}

function segments(cmd: string): string[] {
	return cmd.split(/&&|\|\||[;|\n\r`]|\$\(|\)/).map((s) => s.trim()).filter(Boolean);
}

function isGit(token: string): boolean {
	const base = token.replace(/\\/g, "/").split("/").pop()!.toLowerCase();
	return base === "git" || base === "git.exe";
}

function checkTokens(tokens: string[], rules: DenyRules, depth: number): string | null {
	let i = 0;
	while (i < tokens.length && (/^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[i]) || WRAPPERS.has(tokens[i]))) i++;
	if (i >= tokens.length) return null;
	const head = tokens[i];
	const base = head.replace(/\\/g, "/").split("/").pop()!.toLowerCase();

	// sh -c "..." / bash -c "..." : check the inner script too.
	if (["sh", "bash", "zsh", "dash", "sh.exe", "bash.exe"].includes(base)) {
		const c = tokens.indexOf("-c", i + 1);
		if (c !== -1 && tokens[c + 1] !== undefined && depth < 3) return isDeniedBash(tokens[c + 1], rules, depth + 1);
		return null;
	}
	if (!isGit(head)) return null;

	let j = i + 1;
	while (j < tokens.length && tokens[j].startsWith("-")) {
		const opt = tokens[j].split("=")[0];
		j += GIT_OPTS_WITH_VALUE.has(opt) && !tokens[j].includes("=") ? 2 : 1;
	}
	const sub = tokens[j];
	if (!sub) return null;
	for (const rule of rules.bash) {
		const [, ruleSub] = rule.split(/\s+/);
		if (ruleSub && sub === ruleSub) return rule;
	}
	return null;
}

/** Returns the matched deny rule, or null when the command is allowed. */
export function isDeniedBash(cmd: string, rules: DenyRules, depth = 0): string | null {
	for (const seg of segments(cmd)) {
		const hit = checkTokens(tokenize(seg), rules, depth);
		if (hit) return hit;
	}
	return null;
}

/** True when p (relative to cwd, or absolute) resolves outside cwd. */
export function isOutside(cwd: string, p: string): boolean {
	const rel = path.relative(path.resolve(cwd), path.resolve(cwd, p));
	return rel === ".." || rel.startsWith(".." + path.sep) || rel.startsWith("../") || path.isAbsolute(rel);
}

/** True when p (relative to cwd, or absolute) lands in a hash-locked checks/ directory. */
export function isChecksPath(cwd: string, p: string): boolean {
	const rel = path.relative(path.resolve(cwd), path.resolve(cwd, p));
	const parts = rel.split(/[\\/]+/);
	return parts.includes("checks");
}

// No-op: pi auto-loads every .ts under .pi/extensions/ and requires a default
// export factory, but this file is a pure helper imported by deny-list.ts.
export default function () {}
