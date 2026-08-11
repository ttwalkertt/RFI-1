# TASK-075 preregistered experiment controls

These controls were authored and committed before partition generation or QA execution.

- `scoring-contract.json` defines disposition, finding, grounding, pair, indeterminate, and
  repeatability metrics; invalid evaluations; consensus; and conjunctive success thresholds.
- `optimization-config.json` fixes the split seed/policy, held-out visibility barrier, run counts,
  runtime identity policy, RBF budget, stopping rules, freeze contents, one-shot validation, and
  conditional live-transfer gate.

Changing either file after partition creation invalidates TASK-075. A future experiment must use a
new version instead of weakening this contract.
