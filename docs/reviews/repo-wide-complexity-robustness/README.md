# Repository-wide complexity and robustness review package

This directory is the reproducible evidence package for
`docs/repo-wide-complexity-robustness-review.md`.

## Contents

- `metrics.json` — AST/module/function/test/Git concentration measurements.
- `probes.json` — deterministic offline results for hybrid backup overlap, profile-revision anchor
  identity, and interrupted pull state.
- `evidence-manifest.json` — finding-to-contract/evidence/detection mapping.
- `commands.md` — commands executed and reproduction instructions.
- `validation.md` — focused and full validation outcomes and environmental notes.
- `repository-state.json` — review basis branch/commit and final-state recording convention.

Generated JSON files are intentionally versioned because they are raw review evidence. Transient
runtime state and test repositories are created under temporary directories and are not retained.
