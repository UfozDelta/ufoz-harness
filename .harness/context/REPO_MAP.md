# Repo map
fingerprint: 409f883bd1a4
Regenerate: `python .harness/build_map.py` (check: `--check`). Read this before exploring.

## Routes
- none

## Files
- .agents/skills/animate-expo/RECIPES.md
- .agents/skills/animate-expo/SKILL.md
- .agents/skills/animate/RECIPES.md
- .agents/skills/animate/SKILL.md
- .agents/skills/animation-vocabulary/SKILL.md
- .agents/skills/apple-design/SKILL.md
- .agents/skills/ask-sonner/API.md
- .agents/skills/ask-sonner/SKILL.md
- .agents/skills/emil-design-eng/SKILL.md
- .agents/skills/find-animation-opportunities/SKILL.md
- .agents/skills/frontend-design/LICENSE.txt
- .agents/skills/frontend-design/SKILL.md
- .agents/skills/improve-animations/AUDIT.md
- .agents/skills/improve-animations/PLAN-TEMPLATE.md
- .agents/skills/improve-animations/SKILL.md
- .agents/skills/mobile-native/SKILL.md
- .agents/skills/pick-ui-library/SKILL.md
- .agents/skills/prototype/PICKER.md
- .agents/skills/prototype/SKILL.md
- .agents/skills/review-animations/SKILL.md
- .agents/skills/review-animations/STANDARDS.md
- .agents/skills/write-swift/SKILL.md
- .gitignore
- .pi/deny.json
- .pi/executor.md
- .pi/extensions/deny-list.ts
- .pi/extensions/deny-match.test.mjs
- .pi/extensions/deny-match.ts: DenyRules, isDeniedBash, isOutside
- AGENTS.md
- ARCHITECTURE.md
- CLAUDE.md
- FLOWS.md
- README.md
- harness-speed-test/LATENCY.md
- harness-speed-test/README.md
- harness-speed-test/RESULTS.md
- harness-speed-test/duel.py: parse_models, model_for, cline_binary, parse, task_prompt, acp_run, command_for, display_command, test_result, append_result, ...
- harness-speed-test/fixtures/opencode.jsonl
- harness-speed-test/fixtures/pi.jsonl
- harness-speed-test/latency.py: pi_command, opencode_command, build_opencode_config, append_rows, summarize_trace, summarize_opencode_trace, harness_rows, run_startup, run_direct, task_prompt, ...
- harness-speed-test/report.py: number, display, table, build_report, main
- harness-speed-test/results.csv
- harness-speed-test/run.log
- mermaid.md
- opencode.json
- packages/ufoz-harness/README.md
- packages/ufoz-harness/THIRD_PARTY_NOTICES.md
- packages/ufoz-harness/export_kit.py: fail_missing, copy_file, export, main
- packages/ufoz-harness/index.js
- packages/ufoz-harness/kit/.pi/deny.json
- packages/ufoz-harness/kit/.pi/executor.md
- packages/ufoz-harness/kit/.pi/extensions/deny-list.ts
- packages/ufoz-harness/kit/.pi/extensions/deny-match.ts: DenyRules, isDeniedBash, isOutside
- packages/ufoz-harness/kit/AGENTS.md
- packages/ufoz-harness/kit/CLAUDE.md
- packages/ufoz-harness/kit_readme.md
- packages/ufoz-harness/package.json
- packages/ufoz-harness/test/install.test.js
- skills-lock.json
- tests/test_build_map.py: run_map, test_python_symbols_and_syntax_error, test_typescript_and_javascript_export_symbols, test_public_symbol_truncation, test_routes_and_skipped_paths, test_check_status_and_writes_nothing, test_notes_preserved_and_fingerprint_stable, test_repeated_rebuilds_are_byte_identical_with_custom_notes
- tests/test_envfile.py: test_comments_and_blank_lines_ignored, test_malformed_lines_skipped, test_missing_file_returns_empty, test_load_env_does_not_overwrite_existing
- tests/test_guards.py: test_runner_owned_covers_runner_artifacts_only, test_marker_counts_counts_occurrences, test_suppression_markers_reports_only_new_occurrences, test_lock_hashes_covers_tasks_and_checks
- tests/test_lint.py: make_plan, test_missing_brief_is_an_error, test_acceptance_that_passes_untouched_is_check_invalid, test_shared_files_without_dep_warns_but_passes
- tests/test_llama_executor.py: test_start_writes_provider_and_loads_unloaded_model, test_start_does_not_load_an_already_loaded_model, test_explicit_model_is_used_over_the_served_one, test_ambiguous_models_exit_listing_ids, test_no_models_exit, test_dead_url_exits_with_the_start_command, test_probe_true_and_false, test_stop_removes_the_agent_dir, test_run_forwards_env_to_run_pi
- tests/test_staged.py: test_parse_score_counts_stage_only, test_transcript_usage_window_dedup_cache_and_context, test_transcript_usage_dedup_and_unknown_price, test_csv_line_uses_columns_and_replaces_commas, test_claude_call_returns_error_note, test_score_returns_crash_note
- tests/test_task_runner.py: FakeExecutor, make_plan, test_retry_then_repair_feedback_files_and_eventual_pass, test_still_failing_after_repair_is_not_ok

## Notes
- (main session: add decisions/conventions here)
