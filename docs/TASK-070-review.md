# TASK-070 Corrective Verification Report

## Result

TASK-070 is Complete. Only deterministically established earnings calls now qualify as
`earnings_transcript`. Substantial conference, investor-day, fireside-chat, analyst-event, and
otherwise unknown management transcripts remain immutable repository evidence under one broad
`management_transcript` canonical classification, with a bounded event-kind diagnostic for
research precision.

The solution is provider- and firm-neutral. It uses trusted explicit event disposition when
available, otherwise deterministic event-title semantics. It does not use an LLM. An unknown event
fails closed for the earnings corpus but remains retainable as `other_management` when the existing
source-governance and transcript-substance gates pass.

## Live evidence inspected

The supplied `pull-results.txt` Seagate trace is 1,202,438 bytes (23,755 lines), with SHA-256
`ad7dfcd8f1381f85cdfbc5384c51907483d7af2790cdd22d6e0c0bcd3ac2d882`. It contains 20 substantial
transcript evaluations, all with observed `event_disposition: unknown`, including earnings calls
and clearly named events such as Citi's Global TMT Conference, UBS Global Technology and AI
Conference, Wells Fargo's TMT Summit, and Investor Day 2025. The trace remains operator-supplied
evidence and is not copied into the repository or review ZIP.

## Root-cause analysis

| Architectural layer | Finding | Responsibility |
|---|---|---|
| Discovery metadata | Candidate titles and link labels were present and survived discovery. | Not the defect. |
| Event classification | The provider correctly preserved `unknown` because its artifact-local metadata did not establish a trusted event type; no repository-owned deterministic fallback existed. | Missing capability exposed by the defect. |
| Artifact qualification | `TranscriptTerminalSelectionPolicy.qualify()` rejected only `explicit_non_earnings`, so a substantial `unknown` event was eligible for earnings selection. | Primary admission defect. |
| Artifact mapping | A transcript source had only the primary `earnings_transcript` mapping, so every retained successful transcript projected into that corpus. | Secondary retention/mapping defect. |

The repair therefore belongs at the provider-neutral transcript qualification and repository
association boundary. Provider adapters continue to report observations rather than asserting
repository truth. The qualification policy resolves a canonical class and event kind from trusted
metadata. The ordinary repository ingress validates the resolved association against governed
source policy and stores it on the append-only observation.

## Architectural model and boundary justification

One broad alternate canonical artifact, `management_transcript`, is preferable to separate
canonical artifacts for conferences, investor days, analyst events, fireside chats, summits, and
future title variants. It permits broad research such as “everything management has said about
HAMR” while `earnings_transcript` remains a precise corpus. The bounded `transcript_event_kind`
(`conference`, `investor_day`, `fireside_chat`, `analyst_event`, or `other_management`) supplies
event precision without proliferating catalog and source-profile types.

Classification is a pure provider-neutral policy. Non-earnings semantics take precedence over
earnings words in mixed titles. Explicit trusted provider dispositions remain authoritative;
otherwise normalized event labels are matched against small deterministic vocabularies. A label
that establishes neither class resolves to `management_transcript/other_management`, never to
earnings.

Raw provider observation remains separately inspectable as `observed_event_disposition`. Resolved
repository semantics are recorded as `resolved_canonical_artifact_id`, `transcript_event_kind`, and
`transcript_classification_basis`. Provider diagnostics cannot independently choose an alternate
artifact: the source profile must explicitly authorize `management_transcript`, and repository
ingress rejects any other mapping.

Immutable bytes and content-addressed artifact identity do not change when a legacy observation is
corrected. A subsequent pull appends a new current observation associating the same artifact bytes
with `management_transcript`; it does not mutate the historical observation. Artifact queries use
the current observation's repository-authorized mapping and retain a legacy fallback for records
created before TASK-070.

Historical source-profile revisions remain valid immutable evidence even though the current
catalog gained `management_transcript`. Startup verification now accepts a historical catalog only
when it is an ordered immutable subset of the current catalog and its original canonical digest is
exact. It neither injects the new item into old revisions nor weakens digest verification.

## Representative classifications

| Observed event title | Raw disposition | Canonical artifact | Event kind | Basis |
|---|---|---|---|---|
| Earnings Call: Q4 2025 | unknown | `earnings_transcript` | `earnings_call` | deterministic earnings label |
| Citi's Global TMT Conference 2024 | unknown | `management_transcript` | `conference` | deterministic non-earnings label |
| UBS Global Technology and AI Conference | unknown | `management_transcript` | `conference` | deterministic non-earnings label |
| Wells Fargo 8th Annual TMT Summit | unknown | `management_transcript` | `conference` | deterministic non-earnings label |
| Investor Day 2025 | unknown | `management_transcript` | `investor_day` | deterministic non-earnings label |
| Executive Fireside Chat | unknown | `management_transcript` | `fireside_chat` | deterministic non-earnings label |
| Annual Analyst Briefing | unknown | `management_transcript` | `analyst_event` | deterministic non-earnings label |
| Management discussion | unknown | `management_transcript` | `other_management` | fail closed |

## Regression evidence

The deterministic two-pull evidence begins with one conference followed by two earnings calls in
the requested historical range. The first pull retains the conference through ordinary repository
ingress and selects the first earnings call. The second identical pull hydrates the already-retained
conference without reacquiring or re-recording it, excludes the retained first earnings call, and
selects the next earnings call.

- Pull summaries: two completed successes, no warnings or duplicates.
- Earnings query: two distinct earnings documents dated 2025-06-03 and 2025-09-08.
- Management query: one conference document, absent from the earnings query.
- Conference network retrieval count: one across both pulls.
- Canonical successful observations: two earnings and one management.
- Source authority: primary `earnings_transcript`, explicitly authorized alternate
  `management_transcript`.
- Immutable evidence: three content-addressed artifacts; database, observation, provenance, and
  content integrity all PASS.
- Checkpoint: advances only for selected earnings calls; retaining the conference does not advance
  earnings progress.
- Legacy correction: the same content-addressed artifact ID receives an append-only management
  observation; its historical incorrect earnings observation remains immutable.

The exact classifications, Pull Workflow summaries, document and artifact identities, management
observation, diagnostics, provenance, request counts, checkpoint, source policy, and integrity
report are captured in `validation/classification-and-retention.json` in the review package.

## Changed files

- `src/rfi/acquisition/transcript_classification.py`: deterministic provider-neutral event
  classification and bounded event kinds.
- `src/rfi/discovery.py`: transcript qualification fails closed for earnings and emits resolved
  retention semantics.
- `src/rfi/acquisition/engine.py`: retains authorized non-target transcripts, preserves latest and
  historical reduction behavior, and avoids reacquisition of repository-known artifacts.
- `src/rfi/acquisition/repository.py` and `src/rfi/artifacts/service.py`: validate, persist, hydrate,
  and query per-observation canonical association while preserving legacy compatibility.
- `src/rfi/acquisition/contracts.py`, `src/rfi/acquisition/__init__.py`, and
  `src/rfi/acquisition/earnings_transcripts.py`: event-kind contract, exports, and trusted generic
  transcript metadata.
- `src/rfi/pull/workflow.py` and `src/rfi/resources/source-profile-template.yaml`: governed alternate
  mapping and the single broad catalog item.
- `src/rfi/source_profiles/repository.py`: exact-digest historical catalog subset compatibility.
- `tests/test_task070.py`, compatibility tests, evidence scripts, baseline boundary check, Makefile,
  task ticket, current state, architecture, task index, and design baseline: focused regression and
  review evidence.

## Verification results

- Focused TASK-070 regression and adjacent transcript/Pull Workflow gate: PASS, 213 tests.
- Deterministic classification, two-pull retention/backfill, query separation, duplicate reuse,
  legacy correction, provenance, authority, checkpoint, and repository-integrity evidence: PASS.
- WDC press-release latest/range isolation regression: PASS, 11 tests.
- Lint, format, lightweight type, import, documentation, baseline, and diff checks: PASS.
- Full repository-standard `make validate`: PASS, 690 tests plus every repository proof and build
  gate.

The commit-aware review package captures the exact reviewed base/head/range, complete patch,
changed-file inventory, focused and full validation output, deterministic evidence, manifest
hashes, ZIP, and ZIP SHA-256.

## Limitations

- Deterministic title vocabularies are intentionally bounded; unfamiliar labels safely remain
  `other_management` until a trusted metadata source or reviewed vocabulary extension identifies
  them.
- A provider may continue to report raw `unknown`; TASK-070 resolves repository semantics without
  fabricating provider certainty.
- Already-misclassified retained artifacts are corrected append-only when observed by a subsequent
  pull; this task does not rewrite history or run a bulk migration.
- Current production transcript provider coverage remains narrow. Classification and repository
  contracts are provider-neutral, but each additional provider still needs its own validated
  parsing adapter.
- Management subtypes are diagnostics, not independent canonical artifact catalogs.

## Architectural Status Summary

| Subsystem | Responsibility | Status after TASK-070 | Important limitation / next milestone |
|---|---|---|---|
| Provider discovery | Preserve provider-local titles, metadata, and raw event disposition | Complete, unchanged | Raw event type may remain unknown |
| Transcript classifier | Resolve deterministic canonical class and bounded event kind | Complete | Vocabulary is deliberately bounded |
| Earnings qualification | Admit only established earnings calls | Complete | Unknown events fail closed |
| Non-earnings retention | Retain substantial management transcripts under governed alternate authority | Complete | One broad canonical class |
| Repository | Own immutable bytes, observations, provenance, identity, mapping authority, and integrity | Complete | Legacy correction occurs on re-observation |
| Artifact query | Keep earnings precise and management speech broadly queryable | Complete | Event-kind filtering is diagnostic rather than a separate catalog hierarchy |
| Historical selection | Advance across earnings while hydrating retained management events | Complete | Existing bounded provider discovery remains authoritative |
| Provider coverage | Supply production transcript parsing | Provider-neutral boundary complete | Current production implementation remains narrow |

The next milestone should be separately authorized. TASK-070 does not imply a bulk migration, new
provider, automatic full-corpus backfill loop, LLM classification, or a canonical artifact type for
every management-event subtype.
