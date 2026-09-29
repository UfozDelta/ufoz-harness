/**
 * Deny-list extension: mirrors the opencode executor permissions
 * (.opencode/agent/executor.md). Rules live in .pi/deny.json.
 * Load explicitly: pi -e .pi/extensions/deny-list.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { type DenyRules, isChecksPath, isDeniedBash, isOutside } from "./deny-match.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const rules: DenyRules = JSON.parse(fs.readFileSync(path.join(here, "..", "deny.json"), "utf8"));

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName === "bash") {
			const hit = isDeniedBash(String(event.input.command ?? ""), rules);
			if (hit) return { block: true, reason: `denied by .pi/deny.json: "${hit}" is not allowed` };
		}
		if (event.toolName === "write" || event.toolName === "edit") {
			const p = String(event.input.path ?? "");
			if (p && isChecksPath(ctx.cwd, p)) {
				return { block: true, reason: `denied: checks/ is hash-locked, the executor may not edit acceptance checks: ${p}` };
			}
			if (rules.external_directory === "deny" && p && isOutside(ctx.cwd, p)) {
				return { block: true, reason: `denied by .pi/deny.json: ${p} is outside the working directory` };
			}
		}
		return undefined;
	});
}
