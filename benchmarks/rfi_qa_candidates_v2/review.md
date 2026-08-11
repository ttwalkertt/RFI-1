# Independent v2 benchmark review record

## Scope review

The authored change is confined to `benchmarks/rfi_qa_candidates_v2/`. It introduces synthetic
benchmark data, schemas, taxonomy, partition metadata, documentation, and validation only.

No RFI, MCP, investigator, QA runtime, QA scoring, TASK-075 optimization, or test implementation is
modified by this benchmark-authoring commit. Pre-existing modified TASK-075 files in the worktree
are intentionally neither opened for diff review nor staged.

## Independence review

Authoring did not inspect or use:

- `src/rfi/investigation_qa/`;
- TASK-074 or TASK-075 QA implementation;
- TASK-075 calibration ledgers or optimization results;
- QA runtime outputs;
- observed QA failures or performance; or
- prior candidate case contents.

Permitted repository inputs were the operating model, normative benchmark requirements in the
active task ticket, and existing benchmark README/schema/taxonomy/validator conventions.

## Partition review

- Random seed: `20260811`.
- Randomization unit: complete matched pair.
- Algorithm: sorted pair IDs, Python MT19937 shuffle, first 22 calibration, remaining 14 validation.
- Rerandomization: none.
- Pair co-location: verified.
- Partition and fixture disjointness: verified.
- Quarantine exclusion: verified.
- Validation case content in split manifest: none.
- Held-out validation files in Git commit: prohibited by benchmark-local `.gitignore` and explicit
  staging scope.

## Validation evidence

Full local validation command:

```bash
python3 benchmarks/rfi_qa_candidates_v2/validate_candidates.py --full
```

Calibration-visible validation command after held-out removal:

```bash
python3 benchmarks/rfi_qa_candidates_v2/validate_candidates.py --visible
```

Expected authoritative corpus digest:

```text
09ec5ab31d4f9683e7ce7f9064fb294f388d4846b5f75a68875f69a6c740c54a
```

The commit scope is reviewed again immediately before staging by listing only new benchmark paths;
no prohibited modified file is included.
