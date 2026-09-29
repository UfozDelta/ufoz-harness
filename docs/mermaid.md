# Harness flow

```mermaid
flowchart TD
    A[You + main session<br/>agree scope and success criteria] --> B["@planner subagent<br/>writes plan.md + tasks.json<br/>--lint rejects node TS loads and missing tsc"]
    B --> C[Main session shows plan summary<br/>+ Unverified list]
    C -->|you say go| D["run_plan.py in .worktrees/slug<br/>one warm executor session<br/>pi (default) / opencode / claude / cline / cline-acp / llama"]

    subgraph Task["Per task, in order"]
        D --> E[Executor does the task]
        E --> F{Smoke check passes?<br/>only listed files touched?<br/>no new @ts-ignore / @ts-nocheck / eslint-disable?}
        F -->|yes| G[pass → next task]
        F -->|no, plain failure| H[Retry with feedback.md]
        H --> F2{passes?}
        F2 -->|yes| G
        F2 -->|no| R[Repair pass<br/>error + files of this task and all earlier tasks]
        R --> F3{passes?}
        F3 -->|yes| G2[REPAIRED → next task]
        F3 -->|no| X[Plan stops<br/>main session investigates]
    end

    G --> S[Last task: SUMMARY.md<br/>runs build, writes BUILD: pass / fail]
    G2 --> S
    S --> V[Main session reads SUMMARY, reports, git diff]
    V --> Y[You run --land, review and commit]
```

- Claude cost: planner call(s) + a thin main session. The executor is free with pi or
  opencode on Bunny, with cline on its free model, or with llama on a local GGUF;
  `--executor claude` bills Claude.
- Checks: `tsc --noEmit` / one-line smoke per task. Full build only in the last task, never a gate.
- Stray files, lock edits and timeouts skip the repair pass.
- `--parallel N` is refused for `cline`, `cline-acp` and `llama` (single shared session or one
  local model slot, not thread-safe).
- Every path in table form: `FLOWS.md`.
