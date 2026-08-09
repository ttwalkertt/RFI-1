# TASK-071 — Establish Retained-Truth Access Baseline and Transcript Investigation Vertical Slice

**Status:** Complete
**Type:** Research-architecture and vertical-slice milestone
**Scope:** Retained-truth catalog, knowledge-access/IQA boundary, headless investigating-agent vertical slice over retained earnings-call transcripts

## Objective

Establish the first working boundary from RFI retained truth, through a replaceable knowledge-access / Index-Query Adapter (IQA) layer, to an investigating LLM.

Use retained earnings-call transcripts as the proving corpus. The implementation is expected to drive architectural discovery: do not assume the first access model, indexing strategy, query abstraction, transcript segmentation, or investigative procedure will survive unchanged.

The task is complete only when the resulting vertical slice can proficiently investigate materially different questions over the retained earnings-call transcript corpus, producing evidence-supported answers when the corpus supports them and explicitly reporting insufficiency when it does not.

## Architectural baseline

Preserve these boundaries:

```text
Retained truth
    artifact/content
    authoritative retained metadata
    directly derived deterministic metadata
        |
        | authority boundary
        v
Knowledge access / IQAs
    views / indexes / virtualization
    query, inspection, traversal, expansion
    generic where useful; bespoke where justified
        |
        | reasoning boundary
        v
Investigative harness
    iterative tool use
    investigation control and trace
        |
        v
Replaceable LLM
```

The boundary is more important than the initial implementation placement. SQL views, indexes, materialized structures, query code, and adapter code may all participate in the knowledge-access layer.

Retained truth remains authoritative. Access structures are derived or replaceable and must not silently become a competing source of truth.

## Required study and catalog

Before imposing a general access abstraction, inspect the current repository and catalog the retained-truth instance types that contain substantive content.

For each relevant type, identify at least:

- canonical identity and repository authority;
- retained content or artifact bytes;
- authoritative retained metadata;
- directly derived deterministic metadata;
- provenance and source association;
- temporal semantics;
- retained relationships;
- current read/query/navigation paths;
- useful existing indexes, views, projections, or adapters;
- semantic commonality with other retained-truth types; and
- type-specific behavior whose fidelity or efficiency may justify a bespoke access path.

Use this catalog to propose harmonization where semantics are genuinely shared. Do not force unrelated evidence types through a lowest-common-denominator abstraction merely for interface uniformity.

The catalog and resulting architectural findings are required review artifacts.

## Knowledge-access / IQA requirement

Establish the minimum model-facing knowledge-access capability required by the transcript vertical slice.

The investigating process must be able to orient itself to the available transcript corpus and progressively discover, inspect, and expand retained evidence. A clear data dictionary, schema/capability description, and useful indices or equivalent navigation affordances are part of this problem.

The task does **not** prescribe:

- one universal IQA;
- one universal index;
- classical RAG;
- vector retrieval;
- a graph store;
- a particular transcript source-object granularity;
- an explicit corpus-build subsystem;
- the existing TASK-006 retrieval/evidence-package POC as the mandatory interface; or
- a particular planner or agent framework.

Existing POC contracts and implementations should be reused where they prove useful, but they are architectural inputs rather than mandatory final shapes.

A well-bounded bespoke access method is acceptable when implementation evidence shows that it materially improves correctness, fidelity, or investigative efficiency.

## Vertical slice

Build one headless, end-to-end investigative slice over retained earnings-call transcripts.

The slice must allow an LLM to investigate rather than receive a preassembled context intended to contain everything needed for the answer.

The expected interaction pattern is conceptually:

```text
question
   |
   v
LLM determines what it needs
   |
   v
IQA discovery / orientation
   |
   v
compact results
   |
   v
LLM chooses what to inspect or expand
   |
   v
IQA returns retained evidence + provenance
   |
   v
LLM continues investigation as needed
   |
   v
supported answer OR explicit insufficiency
```

The implementation may differ from this exact sequence if evidence from the work supports a better investigative pattern.

## Proving questions

Use management sentiment across earnings calls as the initial proving question. For example:

> How has management sentiment about the business outlook changed across the retained earnings calls, and what transcript evidence supports that assessment?

This question is a probe, not a hard-coded workflow.

Acceptance requires the same slice to investigate **materially different, previously unengineered questions** over the retained earnings-call transcripts without adding a bespoke retrieval workflow for each question.

Questions may concern, for example, changes in management statements over time, recurring risks, product or technology commentary, demand, explanations for business changes, speakers, or first/last discussion of a topic.

The only substantive scope limitation is:

> The question must be answerable from the retained earnings-call transcripts, or the system must correctly determine that the retained transcript corpus does not provide enough evidence to answer it.

For this slice, do not silently augment answers from the web, model pretraining, unrelated RFI artifact families, or unstated external knowledge.

## Investigation quality

A technically functioning demo is insufficient.

Drive the slice through observation, repair, refactoring, and RBF until it demonstrates useful investigative proficiency.

The system must be able to:

- discover what retained earnings-call evidence is available;
- understand enough of the repository/data dictionary to choose useful access operations;
- locate relevant transcript material without a question-specific hard-coded retrieval path;
- inspect and expand evidence iteratively;
- compare evidence across calls when the question requires it;
- preserve source-effective date, speaker/event context, canonical identity, and provenance where available;
- distinguish transcript evidence from model interpretation;
- support material conclusions with traceable retained evidence;
- expose meaningful gaps or failed searches;
- avoid manufacturing support when the corpus is insufficient; and
- produce an inspectable investigative trace sufficient to understand how the answer was reached.

## RBF and architectural discovery

This task is intentionally expected to expose assumptions that are wrong or incomplete.

Do not optimize for preserving the initial design unchanged. When implementation reveals:

- missing retained metadata;
- awkward repository semantics;
- weak or misleading indices;
- inadequate data-dictionary information;
- poor generic abstractions;
- useful type-specific access patterns;
- harness deficiencies;
- citation/provenance problems; or
- other blockers to proficient investigation,

document the finding and make the smallest justified repair or refactor within the task boundary.

Substantial discoveries that would expand the task beyond the transcript vertical slice should become explicit follow-on recommendations rather than uncontrolled scope growth.

## Required invariants

- Repository-retained truth remains authoritative.
- IQAs, views, indexes, caches, embeddings, or other access structures are not repository authority merely because the investigator uses them.
- The investigating agent does not depend directly on physical persistence layout.
- Model-specific prompt strategy, token limits, and investigation heuristics do not become repository semantics.
- Retained artifact identity, integrity, provenance, observation history, canonical transcript classification, and acquisition behavior remain unchanged unless a demonstrated defect requires a separately justified repository repair.
- `earnings_transcript` and `management_transcript` classification authority established by TASK-070 must not be reinterpreted in the model or access layer.
- Do not add web research or new acquisition paths to make the proving questions pass.
- Do not persist generated analytical conclusions as retained repository truth as part of this task.

## Verification

Verification must include at least:

1. automated coverage for any new repository-facing, IQA, index/view, or harness contracts;
2. proof that model-facing access does not require direct knowledge of SQLite tables, artifact-storage paths, or provider internals;
3. a retained-truth catalog review demonstrating the common and bespoke access findings;
4. successful end-to-end investigation of the initial sentiment question;
5. successful end-to-end investigation of multiple materially different transcript questions not encoded as dedicated workflows;
6. at least one negative/insufficient-evidence question where the system correctly declines to claim an answer from the transcript corpus;
7. trace inspection showing the evidence-discovery and expansion path for representative runs;
8. evidence that material answer claims can be traced to retained transcript content and provenance;
9. focused regression coverage for transcript repository and artifact-query behavior affected by the work; and
10. the repository's normal full validation appropriate to the changed surface.

Do not score the slice solely by whether an answer sounds plausible. Review whether the investigator found appropriate evidence, avoided unsupported claims, used the access layer coherently, and recognized insufficiency.

## Required review package

Generate the normal commit-aware review package.

In addition to the standard changed-file, validation, diff, integrity, and architectural-status material, include:

- the retained-truth instance catalog;
- the implemented knowledge-access/IQA boundary and why it was chosen;
- generic abstractions retained after experimentation;
- bespoke mechanisms retained and evidence that justified them;
- rejected or replaced approaches and the observed reason for RBF;
- the data dictionary / capability surface exposed to the investigator;
- representative investigative traces for the sentiment question, materially different questions, and the insufficiency case;
- known weaknesses or proficiency limits that remain;
- explicit recommendations for the next bounded task(s); and
- an updated architectural assessment of the boundary between retained truth, knowledge access/IQAs, and the investigating process.

The review should make clear what was learned during implementation that was not known when the task began.

## Out of scope

Unless required for the minimum headless proving slice, do not add:

- browser or operator research UI;
- general consulting-workspace product composition;
- internet research;
- new acquisition providers or transcript taxonomies;
- report authoring;
- durable generated claims as repository truth;
- cross-artifact-family research;
- a universal retained-truth schema;
- a universal query language;
- multi-user or distributed execution; or
- optimization for production latency, scale, or cost beyond what is required to evaluate the slice.

## Acceptance criteria

TASK-071 is complete when:

1. the repository's substantive retained-truth instance types and current access paths have been cataloged well enough to identify real harmonization opportunities and justified specialization;
2. a bounded knowledge-access/IQA layer exposes retained earnings-call truth to an investigating process without transferring repository authority;
3. a replaceable LLM operating through a headless investigative harness can answer the initial sentiment question and multiple materially different transcript questions through iterative investigation rather than question-specific preassembled RAG;
4. unsupported questions are explicitly identified as not answerable from the retained earnings-call transcript corpus;
5. representative answers preserve traceable evidence and provenance;
6. the implementation has been iterated through observed failures until the slice is demonstrably useful rather than merely operational;
7. focused and appropriate full regression validation pass;
8. the review package captures architectural discoveries, RBF history, remaining deficiencies, and recommended follow-on tasks; and
9. the completed work is committed and pushed on the task branch without merging to `main`.

The vertical slice is an experimental instrument and architectural learning milestone. Completion does not declare the IQA, index, harness, or investigative architecture final.
