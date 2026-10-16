# plan-check-gap

Give the planner a readable acceptance contract extracted from the hidden tests, never test source.

- bench.py: CONTRACT_FILENAME, hidden_contract (ast-only, source-free markdown), ensure_contract, contract_fingerprint, spec_with_contract. opus_plan and run_planner_arm prompt from it; opus_plan cache keys on the fingerprint.
- runner/planner.py: _local_contract copies the contract beside the spec; run_planner adds the binding line only when present.
- .gitignore: ignore tasks/*/contract.md.

BUILD: pass (pytest tests/test_staged.py -q -> 6 passed)
