# TASK-071 architectural review

## Outcome

TASK-071 establishes a public retained-truth boundary, a disposable transcript-specific IQA, and
a bounded headless investigating process with a replaceable live model adapter. The slice operates
over retained Seagate transcript artifacts without importing acquisition persistence or promoting
search state and generated answers into repository authority.

The retained-truth catalog is
[`TASK-071-retained-truth-catalog.md`](TASK-071-retained-truth-catalog.md). The complete capability,
operation, RBF, and limitation record is
[`transcript-investigation-vertical-slice.md`](transcript-investigation-vertical-slice.md), and the
accepted boundary is recorded in
[`ADR-0027`](decisions/0027-retained-truth-transcript-investigation-boundary.md).

## Retained corpus observed

The evaluation snapshot is a byte-preserving copy/read link of the retained operator corpus, not a
new repository authority. Public artifact reads report:

- repository snapshot `sqlite-revision-8237`;
- 21 canonical `earnings_transcript` documents and 2,268 addressable paragraphs;
- source-effective dates from 2024-09-04 through 2026-07-28;
- exact content checksums, artifact/document identities, titles, and provenance for every document;
- no retained historical event-kind diagnostic on any of the 21 selected observations; and
- no retained speaker labels in the normalized artifact bytes.

Titles include investor days and technology conferences despite the historical canonical
`earnings_transcript` association. TASK-070 authority is append-only, so TASK-071 exposes this as a
corpus conflict and does not relabel history. Coverage remains bounded and cannot prove every
management event was acquired.

## Implemented boundary

`TranscriptKnowledgeAccess` depends on `ArtifactQueryService` summaries, details, and content. It
builds a process-local FTS5 index with stable artifact/byte/digest paragraph locators. Discovery is
compact and non-citable; exact expansion re-reads and verifies retained bytes and carries canonical
identity, event time, optional context, and provenance.

`TranscriptInvestigator` owns corpus-first orientation, iterative tool exchange, hard local
budgets, complete tool/result traces, and the rule that an uninvestigated insufficiency declaration
is invalid. Generation closes an admissible expanded-evidence set and candidate claims before a
separate non-retrieving adjudicator validates mappings and temporal coverage, rejects unsupported
or overbroad claims, calibrates categorical support/completeness, and writes the report lead.
`InvestigationModel` is the replaceable port. The first adapter uses OpenAI Responses with
environment-only credentials, `store=false`, no parallel tool calls, bounded output, and no
repository mutation.

One evaluator work order may start one separately budgeted recovery cycle for one or more named
remediable deficiencies. Recovery is limited to those periods/documents plus at most one
expanded-evidence-derived, topic-preserving follow-up. It closes and is evaluated once more, then
stops. Supported and genuinely insufficient records bypass recovery.

## Generic mechanisms retained

- public artifact summary/detail/content as the common retained-evidence envelope;
- repository snapshot, stable identity, source-effective time, canonical type, checksum, and
  provenance on every access generation;
- bounded typed query/tool schemas and provider-neutral model session contracts;
- separate candidate discovery and exact evidence expansion;
- explicit authority separation, evidence mapping, insufficiency, execution budgets, and trace;
- rebuildable access state whose implementation may change without changing retained truth; and
- explicit dependency tests preventing the IQA/harness from importing repository persistence.

## Bespoke mechanisms retained

- plain-text transcript paragraph segmentation using exact retained byte lines rather than the SEC
  SGML source-object grammar;
- FTS5 porter/unicode lexical access with per-document diversity, `any`/`all` semantics, and
  relevance/oldest/latest ordering;
- transcript corpus orientation that reports canonical classification conflicts and missing
  speaker/event metadata; and
- exact neighboring-paragraph expansion keyed by the selected transcript segment.

These mechanisms are small and evidence-specific. They preserve more fidelity and permit temporal
investigation with less lifecycle machinery than forcing transcripts through the current SEC
source-object and TASK-006 vector-generation POCs.

## RBF history and approaches replaced

| Initial approach or assumption | Observation | Result |
|---|---|---|
| Compose TASK-005/006/007 mechanically | SEC objects do not expose transcript bodies, the retrieval generation would create an unearned durable corpus lifecycle, and one planned follow-up is too shallow for investigation | Reused locator/provenance/model-port ideas; replaced the composition with a public-artifact transcript IQA and iterative harness |
| Artifact summaries already carried transcript chronology | Historical transcript summaries used acquisition time because ordinary publication fields were absent, although observation diagnostics retained trusted event dates | Repaired repository source-effective ordering and title projection; IQA does not own a second chronology |
| Relevance ranking was sufficient | `40 terabyte` and areal-density probes returned more matches than a bounded result page, so relevance could not prove first/last discussion | Added generic oldest/latest ordering and ordinal tie-breaking |
| Search snippets could be cited | Snippets are clipped/ranked projections and may omit context | Split candidate discovery from checksum-verified exact expansion; harness rejects unexpanded citations |
| A model may declare insufficiency immediately | Structured insufficiency could pass without reading the corpus | Harness now requires successful orientation and search before any submission |
| Automatic tool choice would reliably terminate through the submit contract | The first full-corpus retry ended in plain prose after investigation, which the harness rejected | Require an allowlisted tool on every provider turn; final prose must use `submit_investigation` |
| Required tool choice would make the model decide within the turn budget | The next run kept exploring until all nine turns were consumed | Force `submit_investigation` only on the provider's final allowed turn so the bounded run ends with its best sufficiency decision |
| A 1,200-token turn cap was enough for structured final output | The forced sentiment submission was truncated while serializing several mapped claims | Restored the modest 1,800-token default and instructed concise final claims; disclosure/tool bounds remain unchanged |
| A final-turn force alone would produce timely, complete temporal synthesis | The first successful sentiment result stopped at 2025 even though the corpus extends through 2026 | Added monotonic per-turn urgency and required early/latest relevant coverage for change questions, otherwise `partial` |
| Claim evidence IDs alone made every stated sentiment period auditable | A temporally improved answer still relied on prose discipline to associate periods with citations | Added explicit retained event dates to temporal claims and reject any period without same-date expanded evidence |
| A forced final turn would reliably reuse only expanded IDs already in context | A period-aware run cited one search candidate it had not expanded, and the harness rejected the result | Late-turn instructions now enumerate the exact admissible expanded IDs and dates; search-only IDs remain invalid |
| Enumerating admissible IDs in final instructions was a sufficient constraint | A second run still selected a search-only ID despite the instruction | The final-turn submit schema now enumerates only session-expanded IDs and dates, with independent harness revalidation |
| One generated sufficiency decision was also an adequate final report | A live sentiment run cited each stated period correctly but generalized beyond the periods it had covered | Split generation from a non-retrieving closed-record adjudicator that rejects/narrows claims, calibrates support/completeness categorically, and writes the report lead |
| Extra grace turns were the natural repair for late evidence | The first demand proving path found a temporal-boundary candidate too late to expand | Kept the initial budget hard; added at most one fresh evaluator-scoped recovery cycle followed by a second closure/evaluation |
| A recovery request needed only a date | The first live recovery invented document identifiers and spent its bounded turns on invalid calls | Carry orientation-derived authoritative document IDs and return actionable protocol warnings with bounded allowlists |
| Recovery must never leave evaluator target periods | Evidence can directly establish that an adjacent lookup is necessary to repair the approved deficiency | Permit one expanded-evidence-derived, rationale-bearing, topic-preserving follow-up search; keep fail-closed expansion and one-cycle stopping |
| Generic exceptions were enough for invalid identifiers | An invented document ID looked like a failed investigative path and silently consumed recovery budget | Distinguish structured `tool_protocol_failure` warnings from valid empty searches; warn that protocol failure is not evidence absence and show authoritative IDs where bounded |
| `gpt-5-mini` was an available modest default | The selected project returned `model_not_found` because its organization is not verified for GPT-5 | Replaced the default with project-accessible `gpt-4.1-mini`; reasoning parameters are now capability-specific |
| Existing normalized bytes retained speaker context | All 21 artifacts had paragraph text but no speaker labels, despite acquisition diagnostics proving the provider parser once observed turns | Report the gap, prohibit invented attribution, and recommend a bounded turn/speaker fidelity follow-on |

## Vertical-slice evaluation

The checked synthetic live smoke passed with four model tool calls, two expanded/cited spans, a
supported two-period answer, and 6,506 total model tokens. The authorized retained-corpus
evaluation then passed exact-byte, citation-admission, period-mapping, dependency, and trace-shape
checks for all five cases:

| Case | Final calibration | Trace result |
|---|---|---|
| Management sentiment over time | partial / bounded | 8 cited spans across 8 claimed dates (2024-10-22 through 2026-07-28); evaluator correctly reports the uncited 2024-09-04 corpus boundary |
| Cloud/nearline demand and customer behavior | supported / strong | Initial five-turn closure was partial; one work order repaired missing 2026-07-28 evidence with 1 search, 1 expansion, and 1 submission; second evaluation passed |
| HAMR/Mozaic qualification and production progress | supported / strong | 8 cited spans across 4 dates; zero recovery cycles |
| First/latest discussion of 40-TB technology | supported / strong | Oldest/latest searches, 4 cited spans at 2024-09-04 and 2026-07-28; zero recovery cycles |
| Named-executive employee attrition by geography | insufficient / none | 3 searches, 2 valid empty searches, no cited claims, explicit speaker/coverage gap; zero recovery cycles |

Every claimed sentiment period has same-date expanded evidence. The sentiment answer remains
partial because the repository cannot distinguish the 2024-09-04 conference-titled artifact from
an earnings call using absent historical event-kind metadata; the evaluator does not silently
discard the authoritative corpus boundary.

The review package retains every complete trace plus a condensed evaluator output that
checks corpus snapshot, first-call orientation, search/expansion path, exact-byte hashes, citation
admission, per-claim periods, both closures/evaluations, recovery count/scope, status, gaps, failed
searches, model usage, and stopping reason. Trace review evaluates whether searches were coherent
and claims were supported, not merely whether prose sounded plausible.

## Validation

- `tests.test_task071`: 13 focused contract/harness/provider-boundary tests pass, including
  closed-record adjudication, one-cycle recovery, supported-case bypass, and actionable invalid-ID
  feedback.
- `make task071-test`: 36 TASK-071, TASK-070, artifact-query/observation, and source-profile
  compatibility tests pass (with ephemeral localhost permission for existing browser tests).
- retained-corpus evidence validation: 5/5 cases pass against 21 documents, 2,268 segments, exact
  retained byte hashes, admissible evidence, claimed periods, and recovery-loop limits.
- lint, formatting, type checking, documentation links, design baseline, and diff checks pass.
- full `make validate` passes 703 tests plus all offline proofs, quality checks, documentation,
  baseline, import, and source-archive build. Earlier runs found only stale explicit package
  inventories; those guardrails now admit the complete `rfi.research` package while confining
  OpenAI transport to `rfi.research.openai`.
- the commit-aware review run remains required after the implementation commit.

## Remaining deficiencies

- Historical speaker/turn structure was not retained with the normalized artifacts, so named
  speaker questions cannot be answered reliably.
- Historical transcript event kinds are absent and canonical types include apparent conference
  titles; authority is preserved, but corpus semantics are coarser than the questions imply.
- Lexical recall has no evaluated synonym benchmark, learned semantic retrieval, or reranker.
- Exact evidence-ID validation does not mechanically establish semantic entailment; representative
  trace inspection remains part of acceptance.
- The access generation is process-local, reads at most 100 documents, and is neither incremental
  nor latency-optimized.
- Model disclosure is explicit at run time but there is no product source-policy UI, provider
  router, account spend control, durable evaluation registry, or correction workflow.
- Initial turn limits remain hard. One recovery cycle adds cost and a new failure surface; the
  first live attempt exposed invented identifiers before work-order allowlists and warnings were
  added.
- The single evidence-derived scope-following search is structurally bounded but semantic
  necessity is model-stated rather than mechanically proven.
- The stable application and consulting workspace do not compose this slice.

## Recommended next bounded task

The next task should establish **transcript structural fidelity and a durable evaluation corpus**:

1. retain speaker/role/section turn locators and exact byte relationships at acquisition ingress
   without changing artifact content identity;
2. backfill only metadata reproducible from retained bytes or explicitly reacquired observations,
   never from model inference;
3. define a checked diverse question/evidence/insufficiency benchmark for transcript IQA and
   investigator changes; and
4. evaluate lexical, hybrid, and richer transcript-structure access behind the TASK-071 boundary.

Product UI/workspace composition should follow that task, because current metadata and evaluation
limits would otherwise become product behavior before they are well understood.

## Architectural Status Summary

- **Repository foundation — Complete.** Governance, normal validation, current-state reconciliation,
  and commit-aware review packaging remain active.
- **Immutable evidence and artifact query — Complete with a bounded repair.** Exact bytes,
  observations, canonical classification, trusted transcript chronology, title, and provenance are
  the retained authority.
- **Retained-truth catalog — Complete for current substantive types.** Common evidence-envelope
  semantics and justified mail/feed/source-object/knowledge/stream/transcript specialization are
  documented.
- **Transcript acquisition/classification — Usable with limitations.** One provider, conservative
  coverage, missing historical event kind/speaker context, and append-only historical type
  conflicts remain.
- **Transcript knowledge access/IQA — Implemented POC; provisional quality.** Disposable lexical
  and temporal discovery plus exact expansion are useful on the retained corpus; recall, scale,
  and structure are not final.
- **Investigative harness — Implemented POC; usable with limitations.** Replaceable model control,
  hard initial budgets, closed-record adjudication, categorical calibration, one bounded recovery,
  protocol feedback, trace, evidence admission, and insufficiency are established; semantic
  grounding still requires evaluation.
- **Live model adapter — Implemented POC.** The project-accessible modest model passes the checked
  synthetic and five-case retained-corpus slices under explicit disclosure authorization.
- **Consulting product composition — Missing/deferred.** No stable CLI/UI, workspace publication,
  durable generated claims, or cross-artifact research is introduced.
