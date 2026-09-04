# Benchmark contract

## Authority and scope

The sole truth authority is the frozen manifest in `corpus/seagate-transcript-corpus-manifest.json`. Every non-quarantined case declares the same `corpus_scope_id`. Exact evidence identity is the immutable artifact plus deterministic segment byte range and SHA-256; embedded excerpt text is a review convenience and must match that locator.

Canonical artifact classification remains repository authority. Titles, event-kind interpretation, speaker inference, access indices, benchmark labels, and generated analyses cannot replace it. Source-effective chronology uses retained trusted event dates rather than filenames, ingestion time, or filesystem time.

## Case semantics

An independent scenario owns one question, answer obligation, and evidence universe. Matched members keep the same question and evidence universe. The acceptable member is a defensible answer; the defective member changes the answer, not evidence.

`proposition_state` and `answer_quality` are independent. `primary_failure` identifies the earliest stable material failure. `acceptable_failure_classes` deliberately permits overlapping defensible taxonomy labels. Secondary defects are optional.

Minimum decisive evidence is the smallest selected set used for the reference judgment. Material qualifying/counterevidence identifies selected passages whose omission would change scope or interpretation. The full governed corpus remains the evidence universe even when only decisive passages are listed.

## Isolation and immutability

The calibration-visible tree must not contain held-out case-level information. The complete held-out boundary is `withheld/`. Remove it before optimization and restore it only for one-shot verification. `digests.json`, `split-manifest.json`, `withheld/payload-digest.json`, and `withheld/archive-digest.json` provide restoration checks.

Do not repartition answer members, relabel cases from QA behavior, mutate evidence, or tune this corpus against a QA implementation. Cases with unstable reference judgment belong in quarantine.

## Acceptance controls

The validator must pass against the frozen retained state. Pair question and evidence identity must be exact. Every locator must resolve to the recorded document, artifact, ordinal, byte range, hash, date, title, classification, and exact text. The fixed-seed split must replay by scenario. Quarantine must remain disjoint.

Evidence-withheld controls are corpus audit tools, not QA optimization. No tested superficial answer-quality control may reach 0.70 accuracy, and defect-family text-only accuracy must remain below 0.35. Passing does not prove that all leakage is absent.

## Human acceptance

The authored labels are review-ready reference truth, not self-ratifying authority. A human reviewer should inspect `withheld/human-review-packet.md` before authorizing use. It includes every quarantined case, difficult chronology/insufficiency/compound cases, and fixed-seed ordinary controls with readable exact evidence.
