# TASK-075 QA gauge calibration evaluation

## Disposition at the freeze checkpoint

**QA improved materially but did not meet the predetermined calibration gauge criteria.**

This is a frozen-calibration checkpoint, not the final TASK-075 disposition. The held-out
validation payload remains physically absent and has not been run. The frozen design must not be
changed before the authorized benchmark custodian restores the exact validation files.

The v3 gauge reached perfect one-run disposition and indeterminate accuracy on the visible
calibration partition, with no false accepts or false rejects. Its one allowed terminal
three-repeat assessment nevertheless failed the preregistered regime because two independent
judgments for one case exhausted both transport attempts. The scoring contract rejected that case
and forced all repeatability metrics to fail. Two other terminal consensuses used the wrong defect
class. Calibration success is therefore false; aggregate accuracy is not being substituted for
repeatability.

## Frozen benchmark and controls

- Benchmark: `rfi-qa-independent-v2.0.0`, authored independently at
  `ac2837034078ec101ea7e2a582916268b88663fb`.
- Corpus digest: `09ec5ab31d4f9683e7ce7f9064fb294f388d4846b5f75a68875f69a6c740c54a`.
- Objective population: 36 matched pairs / 72 cases.
- Calibration: 22 pairs / 44 cases; held-out validation: 14 pairs / 28 cases.
- Quarantine: four judgment-dependent cases, unchanged and excluded from all scoring and feedback.
- Split seed: `20260811`; first split accepted; no rerandomization or case movement.
- Scoring-contract digest:
  `79f6e5a5ef445d08880079f2c27a995e80ed16489bb7d823782c28795a197ae6`.
- Optimization-config digest:
  `b0670449fc0f24ff28af98e69f0bfe995a6b9009d81154084ca1ecf3a4d70330`.

The formulas, thresholds, diagnostic/terminal repeat counts, 240-call replacement-corpus budget,
three-material-change limit, one-terminal-assessment limit, and stopping rules remained unchanged.
Only integer count equivalents were mechanically recomputed for the v2 partition sizes before any
v2 result. The earlier v1 calibration trajectory remains provenance. Its 80 judgments are not
debited from the fresh 240-call v2 replacement-corpus counter, as clarified by the human operator
before v2 calibration.

## Optimization trajectory

The retained v1 material change was:

`authority ledger -> claim/obligation ledger -> deterministic verification -> three-state
epistemic decision -> exact-class precedence`

V2 used 220 of 240 logical judgments. Transport retries are recorded separately.

| Calibration stage | Runs / case | Disposition | False accept | False reject | Finding recall | Class F1 | Unsupported findings | Indeterminate | Pair discrimination | Repeatability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Retained v2 design baseline | 1 | 90.91% | 0% | 4.55% | 77.27% | 72.34% | 32.00% | 0% | 63.64% | Not measured |
| V3 diagnostic | 1 | 100% | 0% | 0% | 95.45% | 95.45% | 4.55% | 100% | 95.45% | Not measured |
| V3 terminal | 3 | 100% | 0% | 0% | 86.36% | 88.37% | 9.52% | 100% | 86.36% | Invalid / forced fail |

The baseline misses were attributed before the v3 change:

- **QA reasoning/prompt failure:** unresolved assertions were treated as refuted; evidence-mapping
  symptoms were double-counted; incidental wording was promoted to a material attribution; and
  exact-class precedence was underspecified.
- **Repository-authority limitation:** three cases intentionally lacked authority to establish or
  refute the submitted assertion. Correct behavior was `indeterminate`; more retrieval would not
  close the limitation.
- **QA orchestration failure:** none in the two diagnostic iterations.
- **MCP/access gap:** none.
- **Suspected benchmark defect:** none.

The single v2 material change made truth status dominant over calibration instructions, required a
minimal non-overlapping root cause, tightened materiality, and added general class precedence for
whole-answer inconsistency, omitted conflict, population qualification, and draft-versus-governing
source errors. Diagnostic utility rose from `0.8131586073500967` to
`0.9818181818181818`, so v3 satisfied the preregistered terminal-selection rule.

## Terminal result and stopping decision

The terminal run scheduled 132 logical judgments and made 138 transport invocations. Six judgments
used the allowed transport retry; eight invocations timed out. For `R2C-032`, two of three
independent judgments timed out twice at 180 seconds. The required complete consensus was therefore
invalid. `R2C-027` selected `boundary_inclusion_error` instead of
`temporal_scope_mismatch`; `R2C-069` selected `version_supersession_ignored` instead of
`provenance_authority_error`.

The final terminal score passed disposition, false-accept, false-reject, finding-recall, class-F1,
evidence-grounding, unsupported-finding, and indeterminate thresholds. It failed valid-evaluation,
matched-pair, and every repeatability threshold. The contract deliberately returns zero agreement
and Jaccard values plus failing false-positive variance when any case lacks all three independent
runs. No incomplete-case exclusion or post-hoc repeatability substitute was used for acceptance.

The one-terminal-assessment limit is exhausted, and the remaining 20 calls cannot fund another
44-case diagnostic or 132-call terminal assessment. Optimization stopped without retry or tuning.
The frozen design is `task075.epistemic-root-cause-v3`; freeze termination is `budget` and
calibration success is false.

## MCP/access disposition

No MCP or repository-access change was made. The accepted MCP design boundary in
`docs/design/rfi_mcp_surface_design.md` assigns authority, exact evidence, stable identity,
coverage, and provenance semantics to RFI while leaving question interpretation and judgment to the
runtime. The synthetic gauge input already supplied the exact authority declaration, complete or
bounded record set, and stable locators needed for every material miss. The observed failures were
reasoning/class selection or reviewer-runtime failures, not missing general access semantics.

## Freeze and held-out boundary

The freeze manifest is `experiments/task075/frozen-gauge-manifest.json`. It hashes the complete QA
implementation, prompts, contracts, scoring, v2 controls, v1 provenance, and calibration history.
Post-freeze tuning is prohibited.

Held-out validation has not been attempted. The human operator must restore exactly:

- `validation/cases.jsonl` —
  `22e98803f86c36fc1009ce8c16b153e3e4bc871b31740f2620bab13a16fb899d`
- `validation/fixtures.json` —
  `9afb3a99090a85574f6c2a5effaf8a56fe93648eb85bbe280e21ccd84fbb0bbf`

After restoration, the full benchmark validator and frozen-gauge integrity check must pass before
the one allowed validation run. No result from that run may cause TASK-075 retuning. The bounded
fresh-live-transfer test is permitted only if the held-out validation passes every threshold.
