# Retained transcript investigation vertical slice

TASK-071 establishes an experimental headless path from repository-retained transcripts through a
rebuildable transcript knowledge-access layer to a bounded, replaceable investigating model. It is
an architectural learning instrument, not a stable application workflow and not a declaration
that this IQA is final.

## Boundary and authority

```text
ArtifactQueryService summary/detail/content
        authoritative retained identity, metadata, bytes, provenance
                         |
                         v
TranscriptKnowledgeAccess
        disposable in-memory FTS index + exact paragraph locators
                         |
                         v
TranscriptInvestigator
        bounded generation -> closed record
                         |
                         v
InvestigationModel
        replaceable adapter; OpenAI Responses is the first live implementation
                         |
                         v
ClosedRecordAdjudicator
        non-retrieving consistency, calibration, and report lead
                         |
               optional one-cycle rework
        evaluator-scoped recovery -> second closure -> final adjudication
```

`TranscriptKnowledgeAccess` imports the public artifact-query boundary, not acquisition tables or
artifact paths. Its in-memory SQLite FTS5 database is rebuilt from public summaries and verified
content on each process run. Segment identities contain artifact identity, exact byte bounds, and
the exact line digest. Search rankings and snippets are candidates; only `expand_segments` returns
citable evidence after re-reading the public artifact content and hashing the expanded span.

The investigator cannot mutate the repository. Generation first closes an immutable set of
expanded evidence and candidate claims. A separate deterministic adjudicator then decides what
RFI can responsibly say from that completed record; it cannot search, inspect, expand, or call the
model. Its answers and traces are non-authoritative and
are written only when the operator supplies `--output`. It cannot use the web, unrelated artifact
families, physical storage, or model memory as evidence. TASK-070 canonical transcript
classification remains repository authority.

## Model-facing data dictionary and capabilities

Every run must call `describe_corpus` first. It exposes:

- corpus authority and immutable repository snapshot;
- requested firm, canonical artifact types, and optional date scope;
- document/artifact identities, retained titles, source-effective event dates, canonical type,
  event kind and speaker availability, checksum/size, segment count, provider, and provenance;
- corpus date bounds and classification/event-kind counts;
- explicit metadata and coverage gaps; and
- descriptions of the allowlisted operations.

The remaining operations are:

- `search_transcripts`: FTS5 lexical candidate search with `any`/`all` term matching, relevance,
  oldest, or latest ordering, date/document filters, bounded results, per-document diversity, and
  honest empty/truncated-result semantics;
- `expand_segments`: exact retained-byte context plus checksum, identity, event date, canonical
  type, optional speaker/event kind, and provenance. These are the only citable IDs;
- `inspect_document`: a bounded ordered paragraph window for local context; and
- `submit_investigation`: a structured supported/partial/insufficient decision with claims,
  evidence IDs, evidence-backed retained event dates for temporal claims, interpretation,
  limitations, gaps, failed searches, and stopping reason.

The harness requires iterative orientation, discovery, and expansion. Each provider turn receives
a monotonic urgency factor derived from the hard turn budget: early turns preserve exploration,
middle turns prioritize expansion and gaps, late turns stop broad search, and the final turn is
forced to close the investigation. The adjudicator rejects or narrows unexpanded citations,
temporal periods without same-date evidence, unsupported candidate claims, and overbroad temporal
coverage. It uses categorical `strong`/`bounded`/`none` support and
`complete`/`partial`/`insufficient` completeness rather than pseudo-precise scores. Its lead
paragraph becomes the head of the report; the generator's proposed prose cannot override it.

One bounded recovery cycle is permitted only when the first adjudication enumerates remediable
deficiencies and target periods. Recovery has a fresh six-turn/six-call budget, does not extend the
original budget, and can submit only supplemental claims. It begins from evaluator-supplied
authoritative document IDs. One evidence-derived search may leave the target period when expanded
recovery evidence directly requires it; that call must cite the expanded IDs, state a rationale,
and preserve the deficiency topic. A second closure and non-retrieving adjudication then end the
run. Supported and genuinely insufficient records do not receive recovery.

Deterministically invalid document or segment identifiers return a structured
`tool_protocol_failure` warning with bounded valid identifiers and corrective guidance. The warning
explicitly is not evidence absence. A valid zero-hit search remains a substantive search result,
so protocol misuse cannot silently become an insufficiency claim.

## Operator use

The task script intentionally remains outside the stable `rfi` CLI:

```sh
PYTHONPATH=src .venv/bin/python scripts/task071_investigate.py corpus \
  --state STATE

set -a
source .env.local
set +a
PYTHONPATH=src .venv/bin/python scripts/task071_investigate.py ask \
  --state STATE \
  --question "How did cloud demand commentary change?" \
  --max-tool-calls 10 \
  --max-model-turns 8 \
  --max-output-tokens 1200 \
  --output TRACE.json
```

The state root must already contain the operating product's `acquisition` and `firm-catalog`
state. The script opens firm state read-only and uses the public artifact service. It does not
initialize a repository, build a durable corpus, or acquire missing material.

The OpenAI adapter reads `OPENAI_API_KEY` only from the process environment, sends `store=false`,
disables parallel tool calls, applies low reasoning effort only to model families that support the
parameter, and does not place the key in requests, runtime identity, results, or traces. The
modest default is `gpt-4.1-mini`; the initially proposed `gpt-5-mini` was rejected by the selected
project because that organization was not verified for the model. The operator must separately
authorize disclosure of
retained transcript excerpts to the configured model provider. Account-level spend controls are
outside this repository; the local defaults provide a modest hard bound of 12 tool calls, 10 model
turns, 1,800 output tokens per turn, and 75,000 disclosed tool-result characters. Progressive
disclosure keeps orientation metadata compact and withholds per-document checksums, provider, and
provenance until exact evidence expansion. Individual operations remain narrow: at most 12 search
candidates, four expanded segments with a one-line context radius, or a five-paragraph document
window.

## Architectural discoveries and RBF

The retained Seagate corpus changed the initial design in several material ways:

1. **Artifact query was the correct authority boundary, but its transcript chronology was wrong.**
   Historical transcript discovery metadata lacks ordinary filing/publication dates, so summaries
   fell back to acquisition time even though trusted event dates were retained in observation
   diagnostics. The repository-facing repair makes trusted/validated event date an explicit
   source-effective candidate and exposes retained transcript titles. The IQA no longer needs a
   second chronology authority.
2. **TASK-006 could not simply be composed.** Its exact-context and provenance-validation ideas
   were retained, but the SEC source-object corpus and atomic vector-generation lifecycle do not
   address plain-text transcript bodies. A disposable FTS paragraph index over public artifact
   reads was smaller, easier to audit, and did not create a durable competing corpus.
3. **A generic relevance-only search was inadequate.** First/last discussion questions can have
   more hits than the disclosure budget. Oldest/latest ordering was added as a generic temporal
   affordance after live-corpus probing exposed that failure.
4. **Search snippets could not safely serve as citations.** Compact search is useful for model
   exploration, but citable evidence now requires a separate exact expansion and the harness
   rejects any candidate ID that was not expanded.
5. **One preassembled evidence package was too restrictive.** TASK-007's provider-neutral model
   and trace boundaries earned reuse, while its deterministic plan and one optional follow-up were
   replaced by a bounded multi-turn tool loop. Transcript questions require query reformulation,
   temporal comparison, local context, and meaningful failed searches.
6. **Transcript-specific paragraph addressability earned its keep.** The retained normalized text
   already has one paragraph/turn per line but lacks a stable parsed speaker structure. Exact
   byte-line locators preserve fidelity without pretending the SEC source-object grammar or a
   universal chunk ontology applies.
7. **The retained corpus is broader and poorer in metadata than its current label suggests.** All
   21 historical artifacts are canonically `earnings_transcript`, yet titles include investor and
   conference events; event-kind diagnostics and speaker labels predate current retention
   behavior and are absent. The IQA reports these conflicts and does not reinterpret canonical
   classification or invent speaker attribution.
8. **Generation and responsible reporting are different authority decisions.** Live runs produced
   individually valid period citations yet overbroad whole-corpus prose. Generation now stops at a
   closed evidence/claim record; a non-retrieving adjudicator validates mapping, temporal coverage,
   support, completeness, and writes the report lead without asking the model to repair itself.
9. **A fresh, bounded recovery is better than hidden grace turns.** The demand proving run closed
   partial after finding one temporal boundary too late. One evaluator-scoped recovery searched
   and expanded only the missing period, then a second adjudication upgraded the result. There is
   no budget continuation or convergence loop.
10. **Recovery needs authoritative identifiers and actionable failures.** The first recovery POC
    invented document IDs and consumed its budget. Work orders now carry orientation-derived IDs,
    and invalid identifiers receive structured warnings that distinguish protocol failure from a
    valid no-match result.

## Limits

- FTS5 lexical search is auditable and useful but has no learned synonym recall or transcript
  evaluation benchmark. Failed searches are not universal proof of absence.
- Index construction currently reads a bounded maximum of 100 transcript documents and is
  process-local; it is not incremental or optimized for latency.
- Historical normalized transcript bytes omit speaker labels even though the source pages may have
  contained turns. Speaker-specific questions are therefore often insufficient.
- Historical canonical classifications remain immutable even where titles resemble conferences;
  the investigator must report the mismatch instead of silently repairing it.
- The adjudicator validates citation admission, same-date mapping, and bounded temporal coverage;
  it still cannot mechanically prove full semantic entailment. Trace review remains necessary.
- There is no stable CLI/UI composition, durable investigation repository, correction workflow,
  model routing, account budget management, or cross-artifact investigation.
- Initial limits remain hard. Recovery is a separately evaluated and budgeted cycle, not a hidden
  grace turn. Evidence-derived scope-following is limited to one justified search and remains a
  new semantic-control risk requiring further evaluation.

## Architectural Status Summary

- **Repository foundation — Complete.** Task governance, validation, and commit-aware review
  packaging remain in force.
- **Immutable evidence and artifact query — Complete with TASK-071 repair.** Exact bytes,
  observation history, canonical type, source-effective event date, title, and provenance are the
  retained transcript authority.
- **Transcript acquisition/classification — Usable with limitations.** The retained slice is
  bounded to one provider; historical event-kind and speaker retention are incomplete and corpus
  coverage is conservative.
- **Transcript knowledge access/IQA — Implemented POC; provisional quality.** Public artifact
  reads, rebuildable lexical discovery, temporal ordering, exact expansion, and transparent gaps
  are established over the retained corpus. Recall and scale quality are not final.
- **Investigative harness — Implemented POC; usable with limitations.** Bounded generation,
  closed-record adjudication, categorical calibration, actionable protocol feedback, one scoped
  recovery cycle, evidence validation, insufficiency, and complete traces are established without
  making model behavior repository semantics.
- **Live model adapter — Implemented POC.** OpenAI Responses is replaceable and credential-safe;
  its demonstrated proficiency is bounded to the retained-corpus TASK-071 evaluation.
- **Consulting product composition — Missing/deferred.** The stable application does not expose or
  retain these investigations, and TASK-071 intentionally adds no UI or workspace publication.
