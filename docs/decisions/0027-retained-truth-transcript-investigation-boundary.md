# ADR-0027: Retained-truth access and transcript investigation boundary

## Status

Accepted for the TASK-071 experimental vertical slice.

## Context

RFI retains authoritative artifact bytes and metadata, plus several independent POC layers for SEC
source objects, derived knowledge, retrieval packages, intelligence, and workspaces. TASK-071
requires an investigating model to work iteratively over retained transcripts without allowing an
index, prompt, or generated answer to become repository truth. The retained transcript corpus is
normalized plain text, lacks historical speaker/event-kind metadata, and is not represented by the
SEC structural source-object catalog.

Mechanical composition of TASK-005 through TASK-007 would require inventing transcript source
objects, a durable retrieval generation, and a preplanned evidence-package workflow before the
question was understood. Direct model access to acquisition tables or content paths would instead
leak persistence layout and weaken the existing artifact authority.

## Decision

1. Use public `ArtifactQueryService` summary, detail, and verified content reads as the only
   retained-transcript authority presented to the knowledge-access layer.
2. Repair artifact source-effective chronology to consider retained trusted/validated event dates
   before observation/retrieval fallback; do not create a second transcript date authority.
3. Build a disposable transcript-specific FTS5 paragraph index in process. Stable candidate
   identity binds artifact identity, exact byte span, and exact digest. The index is derived and
   rebuildable, never repository authority.
4. Separate compact discovery from citable expansion. Only exact expanded bytes re-read through
   the artifact service may support claims.
5. Expose corpus orientation, lexical/temporal search, exact expansion, and bounded document
   inspection through an explicit IQA capability dictionary.
6. Place a provider-neutral, bounded iterative harness between IQA and model. It owns execution
   budgets, tool order, trace, and stopping; provider prompt mechanics remain replaceable.
7. Close generation before reporting. A subsequent non-retrieving adjudicator owns claim/evidence
   admission, temporal coverage, categorical support/completeness calibration, insufficiency, and
   the report lead. Generated prose has no authority over that decision.
8. Permit at most one fresh, evaluator-scoped recovery cycle for enumerated remediable
   deficiencies. Recovery has a separate hard budget, fail-closed citation admission, a maximum of
   one expanded-evidence-derived scope follow-up, a second closure, and a final adjudication.
   Supported and genuinely insufficient records bypass recovery.
9. Return actionable structured warnings for deterministic invalid identifiers so tool/protocol
   failure cannot be misread as evidence absence or silently consume the bounded investigation.
10. Treat all investigation conclusions and traces as non-authoritative analysis. TASK-071 does not
   persist them into artifact, source-object, knowledge, stream, or workspace authority.

## Consequences

- The model never imports or receives physical repository layout and cannot mutate retained truth.
- Existing artifact and intelligence contracts earn selective reuse without forcing the SEC
  source-object/retrieval lifecycle onto transcripts.
- Exact citations remain verifiable after index replacement; lexical ranking can evolve without
  changing repository semantics.
- Oldest/latest ordering supports chronology questions that relevance ranking alone cannot answer.
- Transcript paragraph segmentation is deliberately bespoke and provisional. A future richer
  transcript parser may replace it behind the same authority/expansion boundary.
- Missing speaker/event-kind metadata and conservative acquisition coverage are visible evidence
  limits, not conditions the model may repair from memory.
- Closed-record adjudication is reproducible and non-retrieving, but semantic entailment remains a
  proficiency/evaluation concern rather than repository semantics.
- Recovery can repair a known incomplete evidence path without an open-ended convergence loop.
  Allowing one evidence-derived follow-up introduces a bounded but real scope-control risk that
  traces and future evaluations must test.
- A future product task must decide lifecycle, disclosure policy, operator review, evaluation,
  correction, and workspace retention before composing this POC into the stable application.
