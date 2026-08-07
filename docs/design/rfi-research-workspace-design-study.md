# RFI Research Workspace — Product and Architecture Design Study

**Status:** Reconciled recommendation and implementation-planning baseline; no implementation authorized

**Date:** 2026-08-07

**Scope:** Interactive research over retained RFI data, with a governed path to later internet augmentation

## 1. Executive summary

RFI should build an **investigation-centric research workspace with conversational assistance, a persistent evidence desk, and visible bounded research plans**. A chat transcript should not be the product's durable center. The durable center should be an investigation: a consulting problem with questions, executions, operator notes, selected evidence, hypotheses or claims, unresolved questions, comparison/timeline views, and deliverable projections.

The normal experience should combine three modes without forcing the operator to choose a different product:

1. **Ask and direct** — natural-language questions and commands initiate or refine bounded work.
2. **Search and inspect** — repository search, filters, source browsing, citation expansion, and provenance traversal remain independently usable.
3. **Organize and conclude** — the operator pins evidence, records notes, compares runs or subjects, tracks gaps and contradictions, and creates a briefing or report projection.

This is preferable to a conventional chatbot because RFI's advantage is not fluent prose. It is retained evidence, authority separation, inspectability, provenance, replay, and work that compounds over time. A chat-first product would subordinate those advantages to a fragile linear transcript and encourage generated answers to become accidental working truth.

The recommendation survives reconciliation with the current repository. The important update is that RFI now has a credible retained transcript corpus path for the representative use case. TASK-069 added bounded historical transcript backfill, and TASK-070 now classifies substantial non-earnings management events separately from earnings calls while retaining both as governed evidence. Public POC contracts also exist for source objects, derived knowledge, governed retrieval, evidence packages, bounded intelligence, and durable investigations. The remaining frontier is therefore **product composition**, not reinvention of those layers.

That frontier is still material. Current source-object parsing is SEC-specific and cannot cite transcript turns or paragraphs. Retrieval and intelligence remain proof-oriented, the planner and reasoner are deterministic substitutes, investigation persistence is not integrated with the main application state, and the browser product exposes none of these capabilities. The smallest useful first implementation should use the current Seagate transcript corpus to prove one honest end-to-end question: **“How has Seagate management's positioning on HAMR changed over the last two years?”**

The smallest useful first implementation should be **repository-only, single-operator, and deliberately narrow**. It should prove one end-to-end vertical slice against actual RFI application state:

- open or create a durable investigation;
- ask a question against governed repository data;
- constrain Seagate, the last two years, and retained `earnings_transcript` plus `management_transcript` evidence;
- see and, before execution, adjust the interpreted scope;
- execute a bounded research plan through public retrieval and evidence contracts;
- receive claim-level citations with clear authority labels;
- inspect every cited excerpt and traverse to the immutable artifact;
- see contradictions, gaps, truncation, failures, and stopping reason;
- retain the execution, operator notes, and selected evidence references without treating the answer as repository truth; and
- reopen the investigation and understand what happened.

Internet research should be added only after these semantics work with repository evidence. Stage 1 should reserve authority and adapter seams for external evidence, but should not implement search, fetching, browser agents, or acquisition promotion. The recommended later architecture uses an RFI-owned external-research gateway and evidence class. External discoveries are ephemeral by default, visibly ungoverned, and cannot become repository evidence except through an explicit acquisition workflow such as **Add to RFI**. That action proposes or launches ordinary governed acquisition; it does not allow the research layer to write canonical evidence.

## 2. Study basis and current-state reconciliation

This study used the repository's governing design material, relevant task tickets and ADRs, current source contracts and implementations, focused tests, operator documentation, committed history, and a live inspection of the local browser product.

The 2026-08-07 reconciliation additionally reviewed the completed TASK-068 through TASK-070 work, the current transcript classification and retention evidence, the product composition roots, and the live browser product. Key evidence included:

- [ARCHITECTURE.md](../../ARCHITECTURE.md), [DESIGN_PRINCIPLES.md](../../DESIGN_PRINCIPLES.md), [RFI_MANIFESTO.md](../../RFI_MANIFESTO.md), [ROADMAP.md](../../ROADMAP.md), and [TASKS.md](../../TASKS.md);
- TASK-005 through TASK-008 tickets and ADR-0005 through ADR-0008;
- TASK-068 through TASK-070 tickets, reviews, tests, and validation evidence;
- [source-object and derived-knowledge design](../source-objects-and-derived-knowledge.md), [governed retrieval design](../governed-retrieval-and-source-browser.md), [model-guided intelligence design](../model-guided-source-grounded-intelligence.md), and [consulting workspace design](../consulting-workspace-and-execution-journal.md);
- current contracts under `rfi.source_objects`, `rfi.knowledge`, `rfi.retrieval`, `rfi.intelligence`, `rfi.workspace`, and `rfi.artifacts`;
- the current admin server and artifact-browser implementation; and
- focused execution of the research POC and current transcript tests.

### 2.1 Reconciliation finding

The documentation-status mismatch identified in the first version of this study has been repaired by TASK-068. `TASKS.md`, `docs/current-state.md`, and `ROADMAP.md` now consistently distinguish **product-integrated capabilities** from **implemented POCs**. TASK-005 through TASK-008 remain real architectural inputs, but they are not composed into the operating product.

TASK-069 and TASK-070 materially improve the evidence foundation for this design:

- historical transcript pulls can select successive earlier earnings transcripts within a bounded date range, including when a newer checkpoint already exists;
- only deterministically established earnings calls enter `earnings_transcript`;
- conferences, investor days, fireside chats, analyst events, and other substantial management speech enter `management_transcript`;
- the repository-owned `TranscriptEventKind` preserves a provider-neutral canonical classification while raw provider disposition remains inspectable; and
- repeated pulls retain a management transcript once without corrupting the earnings-selection checkpoint.

The research product must consume these canonical artifact classes and event-kind diagnostics. It must not create another transcript taxonomy, scrape an alternate corpus, or reinterpret provider observations in the UI or model layer.

### 2.2 Live product finding

The running browser product currently supports concept and firm administration, acquisition workflows, feed and mailing-list operation, streams, and a read-only artifact browser. It does not expose source-object search, derived knowledge, evidence packages, intelligence executions, or saved investigations.

Existing UI concepts worth reusing are:

- explicit read-only and authority language;
- a persistent tree/detail evidence browser;
- normalized metadata plus expandable technical detail;
- an isolated preview of untrusted stored content;
- provenance and integrity alongside the stored artifact;
- progressive disclosure rather than mandatory raw JSON; and
- visible incomplete, failed, and repairable operational states.

Existing UI concepts that should not constrain the research product are the global admin navigation, configuration-form orientation, sparse one-object detail layouts, and reliance on raw JSON for the TASK-006 through TASK-008 proofs.

### 2.3 Summary of changes from the 2026-08-06 study

| Baseline conclusion | Reconciled conclusion |
|---|---|
| Investigation-centric workspace was the recommended product model | Unchanged; now tied to one concrete Seagate HAMR vertical slice |
| Research readiness was a generic source/knowledge/retrieval composition problem | Narrowed to transcript source-object construction, corpus lifecycle, retrieval quality, and product composition |
| Transcript availability and event semantics were uncertain | Historical backfill and canonical earnings-versus-management classification now exist |
| TASKS/roadmap status was stale | Repaired by TASK-068; no longer an architectural gap |
| A new research application API was needed | Refined to a stable `ResearchApplicationService` facade over existing public contracts |
| Workspace POC could be extended without a persistence decision | Product integration should use the application's structured-state authority behind preserved workspace semantics; copying a second filesystem authority is not the default |
| A named evidence set belonged in the first slice | Deferred; execution-scoped citations and notes are sufficient to prove the first vertical slice |
| Internet gateway was an early staged component | Only authority and adapter hooks are reserved initially; no web implementation belongs in the first four tasks |

### 2.4 Current assessment

| Capability | Assessment after reconciliation |
|---|---|
| Immutable artifacts, observations, content inspection | Product-integrated and suitable as the evidence authority |
| Historical management transcript acquisition | Product-integrated with bounded provider coverage; corpus completeness remains indeterminate rather than guaranteed |
| Canonical transcript classification | Product-integrated; sufficient for earnings versus broader management research scope |
| Transcript source objects | Missing; the blocking semantic-evidence gap for the HAMR slice |
| Governed retrieval and evidence packages | Implemented POC contracts; not composed against live application state and not quality-validated for transcripts |
| Bounded intelligence and claim mappings | Implemented POC contracts; no live replaceable model runtime or transcript evaluation |
| Durable investigations | Implemented local POC semantics; not product-composed and not integrated with the main structured-state authority |
| Operator research interface | Missing; current browser offers reusable artifact inspection only |
| Internet research | Intentionally absent; later design remains valid, but provider decisions are premature |

## 3. Current-state architecture relevant to research

RFI currently has six conceptually separate layers. The first four are repository and access layers; the fifth is non-authoritative reasoning; the sixth is durable operator workflow state.

```mermaid
flowchart TD
    A["Acquisition services"] --> B["Immutable artifacts and observations"]
    B --> C["Source objects"]
    C --> D["Derived knowledge"]
    C --> E["Governed retrieval and evidence packages"]
    D --> E
    E --> F["Bounded intelligence execution"]
    F --> G["Investigation workspace and journal"]
    B --> H["Artifact query and isolated inspection"]
    C --> H
    D --> H
    E --> H

    classDef authority fill:#dbeafe,stroke:#2563eb,color:#0f172a;
    classDef derived fill:#fef3c7,stroke:#d97706,color:#0f172a;
    classDef projection fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
    class B authority;
    class C,E,H derived;
    class D,F,G projection;
```

### 3.1 Immutable evidence and acquisition observations

Exact acquired bytes remain authoritative. Content-addressed artifacts are separate from immutable acquisition observations, attempts, provider diagnostics, and interval coverage. Acquisition adapters cannot assign repository identity or bypass the repository ingress. Current artifact query contracts provide typed firm, artifact-family, canonical-type, provider, association, status, date, order, limit, and cursor constraints without exposing SQLite.

The artifact browser uses the same repository-owned read contracts as automated consumers. It verifies stored content, serves it with restrictive headers, and renders hostile HTML in a capability-denying sandbox. Original URLs remain provenance conveniences rather than the inspection authority.

For transcripts, repository authority now includes a useful separation that Research must preserve: the provider observation is retained as observed, while repository-owned canonical artifact type and `TranscriptEventKind` determine whether the evidence is an earnings call, conference, investor day, fireside chat, analyst event, or other management event. Source-effective date, speaker/event metadata available in the retained content, and canonical artifact classification are evidence properties; model-generated topic or position labels are not.

### 3.2 Source objects

`SourceObject` provides stable structural identity, exact artifact byte spans, hierarchy, role, and digest. `SourceObjectReader` supports inventory, identity lookup, document lookup, and normalized field value access. This is the correct evidence-location abstraction for citations and context expansion.

Current semantic coverage is very narrow. The only parser is a deterministic SEC complete-submission parser. It identifies the SEC header, embedded document regions, and selected header/document fields. It does not segment transcript turns or paragraphs. A transcript parser that creates exact, digest-bound source objects from retained transcript bytes is the first new semantic capability needed. It should carry human-readable event, date, and speaker metadata where deterministically available without converting topic interpretation into source evidence.

### 3.3 Derived repository knowledge

`DerivedObject` has stable identity, version identity, object type, semantic key, payload, status, confidence, provenance, derivation identity, supersession, and annotations. Status explicitly distinguishes confirmed, uncertain, conflicted, superseded, and stale knowledge. The repository supports provenance verification, correction, supersession, failures, and reverse navigation from source object to derived objects.

The current deriver constructs only SEC issuer entities, filing observations, and issuer-filed relationships from submission headers. This proves lifecycle and authority separation; it does not provide the substantive knowledge needed for the representative consulting workflows in this study.

### 3.4 Governed retrieval and evidence assembly

`RetrievalQuery` and `MetadataConstraints` provide repository-owned query semantics. Results preserve source-evidence versus derived-knowledge classes. A `RetrievalTrace` records candidate decisions, scores, failures, coverage notes, truncation, index generation, and authority fingerprint. `EvidencePackage` combines exact contexts, source and derived results, omissions, coverage gaps, contradictions, completeness, and byte-budget use.

Important limitations are:

- the vector implementations are deterministic POC mechanisms, not validated semantic retrieval;
- retrieval operates over the narrow source-object and knowledge inventory;
- entity constraints are low-level entity IDs rather than an operator-friendly canonical firm/topic scope;
- the artifact query service and governed retrieval service have adjacent but separate filter vocabularies;
- no integrated application lifecycle builds and refreshes source, knowledge, and retrieval generations from the live application repository; and
- no browser/API surface exposes this subsystem in the current product.

`MetadataConstraints` can already bind retrieval to document, artifact, entity, document-type, source-kind/role, knowledge-type/status, and period constraints. The missing product boundary is an operator-facing `ResearchScope` expressed in canonical firm IDs, artifact types, source-effective dates, and optional event kinds. The application service should resolve that scope through `ArtifactQueryService` and translate it to existing retrieval identities; neither the UI nor the model should manufacture low-level retrieval constraints.

### 3.5 Bounded intelligence

`InformationNeed`, `RetrievalPlan`, `RetrievalStep`, `IntelligenceBudget`, `IntelligenceClaim`, `EvidenceReference`, `IntelligenceResult`, and `ExecutionTrace` are strong provider-neutral foundations. The orchestrator validates plans, bounds retrieval and disclosure, validates evidence packages, requires claim-to-evidence mappings, requires uncertainty on model inference, and fails closed on unsupported or unmapped output.

The POC has no live planner or reasoner adapter. The deterministic implementations recognize a small SEC-oriented vocabulary and prove control semantics, not research quality. The result's three claim kinds — source evidence, derived knowledge, and model inference — also lack a future external-evidence kind.

### 3.6 Durable workspace

The current workspace makes an investigation the durable object. An append-only, hash-chained journal stores investigation lifecycle, execution starts and terminals, annotations, exports, metrics, and reference snapshots. It supports reopen, rerun, semantic comparison, export, backup, restore, integrity checks, and partial-write recovery.

This is directionally aligned with the recommendation. It is nevertheless a thin POC:

- investigations have title, purpose, customer/engagement, status, execution IDs, annotation IDs, and export IDs;
- evidence sets, hypotheses, unresolved questions, and reusable comparison/timeline definitions are not first-class;
- retained execution projections intentionally omit exact source context and raw model exchange;
- the workspace must rehydrate evidence from upstream authorities to provide rich later inspection;
- the store is local, single-writer, and filesystem based; and
- it has no integrated browser or application API.

The POC's append-only execution semantics, reference snapshots, integrity checks, and explicit non-authority should be preserved. Product composition should not casually introduce a second authoritative filesystem state root beside the application's current SQLite structured-state authority. The preferred direction is to place product investigation state behind a public investigation repository using the application's structured state while preserving append-only event meaning. The exact persistence decision remains a human architectural decision, not something to smuggle into a UI task.

## 4. Representative research workflows

The design should be judged against complete consulting workflows, not isolated question answering.

### 4.1 Position change over time

**Need:** “How has Seagate management's positioning on HAMR changed over the last two years?”

This is the acceptance scenario for the first vertical slice. The assumed repository contains retained Seagate earnings calls, management conference transcripts, investor-day transcripts, and related evidence. The flow is:

1. Create an investigation titled “Seagate HAMR positioning — last two years.”
2. Set repository-only scope to Seagate, the trailing two-year source-effective date range, and canonical `earnings_transcript` plus `management_transcript` artifact types.
3. Review corpus readiness: eligible artifacts, indexed documents, unsupported/failed items, freshness, and the distinction between **research-index coverage** and indeterminate **acquisition coverage**.
4. Ask the question. RFI interprets it as a chronological comparison of management statements, not a request for a current product-status fact alone.
5. Execute bounded retrieval across periods and event kinds, expand exact context, assemble an evidence package, and perform grounded synthesis.
6. Present source-fact claims about what management said separately from the model inference that positioning “changed.” Show conflicting language, speakers, event context, missing periods, and stopping reason.
7. Expand a citation to see the exact excerpt, bounded neighboring context, speaker/event/date, source-object identity, immutable artifact, and acquisition observation.
8. Save the execution in the investigation, close the product, reopen it, and rehydrate the same evidence references or visibly report stale/missing upstream authorities.

The first slice does not require a generated timeline, cross-firm comparison, named evidence set, report builder, web search, or acquisition action. Those are later projections over semantics this flow must establish first.

### 4.2 Thesis support and contradiction

**Need:** “What supports or contradicts the thesis that vendor A is deprioritizing technology X?”

The system decomposes support, contradiction, and missing-evidence searches. The answer is organized by claims rather than a single narrative. Each claim shows its authority class and evidence mapping. Contradictions remain separate objects; the model may explain them but cannot silently resolve them. The operator can mark a claim as a working hypothesis without promoting it to repository knowledge.

### 4.3 Firm comparison

**Need:** “Compare Seagate and Western Digital on product timing, stated customer demand, and capital intensity.”

The operator uses a comparison matrix whose rows are explicit dimensions and whose columns are firms or periods. Each cell contains evidence-backed claims, not free text alone. Empty cells are visible gaps. The matrix can be regenerated from a saved definition when repository evidence changes.

### 4.4 Technical event reconstruction

**Need:** “What happened in the Linux block-layer discussion leading to this patch revision?”

Search and graph browsing are primary. The system assembles the message thread, ancestor/descendant boundary, patch revisions, and exact message excerpts. Conversation helps ask follow-ups, but the core work surface is the discussion graph and evidence sequence.

### 4.5 Current-state briefing with external augmentation

**Need:** “What do we know about the announced acquisition, and what has changed since the last retained filing?”

Repository-only results establish the governed baseline. In a separate web-augmentation mode, external discoveries appear with a visually distinct authority class and freshness timestamp. The operator can request acquisition of a source. Until that completes through normal RFI acquisition, the web material remains external research evidence.

### 4.6 Resume and deliver

The operator reopens an investigation days later, sees its last conclusion, selected evidence, unresolved questions, and whether referenced repository generations have changed. The operator reruns only selected questions, compares runs, accepts or rejects model-proposed changes, and projects chosen claims and evidence into a briefing outline. The export remains a projection, not a new repository authority.

## 5. Design principles and hard constraints

1. **Investigation before transcript.** A consulting problem, not a sequence of chat messages, is the durable unit of work.
2. **Evidence before prose.** The system should be useful for search and inspection even if synthesis is unavailable.
3. **Authority is a type, not a disclaimer.** Repository evidence, derived knowledge, external evidence, model inference, and operator-authored material must remain machine-distinguishable.
4. **One retrieval semantics, multiple consumers.** Operator search, model retrieval, saved evidence sets, and deliverable citations should depend on the same repository-owned contracts.
5. **Inspectability follows capability.** Anything available to the planner or reasoner must be navigable by the operator.
6. **Normal work is calm; detail is available.** The ordinary view shows scope, plan, claims, evidence, gaps, and stopping reason. Scores, candidate decisions, raw exchanges, and full traces are on demand or diagnostic.
7. **Incomplete is a useful result.** Empty results, incomplete coverage, contradictions, budget exhaustion, stale indexes, and provider failures must not be rewritten as confidence-colored prose.
8. **Saved does not mean authoritative.** Durable investigation state can include notes and model results while clearly remaining outside repository evidence and knowledge authorities.
9. **External discovery cannot mutate the repository.** Promotion requires an explicit acquisition command and ordinary acquisition validation.
10. **Provider and UI replaceability.** Model, search provider, browser automation, ranking, and UI should depend on stable application contracts rather than define them.
11. **No raw-persistence shortcuts.** Research services must not query SQLite tables, workspace files, artifact paths, or event logs directly.
12. **Bounded autonomy.** Plans, iterations, evidence disclosure, network scope, and stopping conditions are explicit and operator-visible.

## 6. Alternatives explored

### A. Conventional conversational interface

The operator asks questions in a linear chat and receives answers with attached citations.

**Strengths:** familiar; low initial learning cost; strong for quick exploration and follow-up; simplest route to a model-backed demo.  
**Weaknesses:** evidence becomes subordinate to prose; scope and filters are easy to lose; citations are often inspected only after trust has already been granted; comparisons, timelines, and gaps fit poorly; resumption depends on rereading a transcript; raw conversation history tends to become accidental state.  
**Failure modes:** unsupported synthesis looks complete, corrections are buried, stale answers remain visually equivalent to current ones, and the user cannot tell whether retrieval or wording changed.  
**Architecture fit:** the TASK-007 result can render in chat, but the model wastes much of TASK-006 and TASK-008's value.

### B. Conversation plus evidence workspace

Chat occupies one pane; a persistent second pane contains retrieved artifacts, excerpts, provenance, contradictions, and retrieval activity.

**Strengths:** substantially better citation use and inspectability; supports exploratory dialogue while keeping evidence present; compatible with current artifact inspection concepts.  
**Weaknesses:** the transcript still tends to own the research structure; evidence collections, hypotheses, and comparisons are awkward add-ons; long-running investigations become a chat plus a pile of pins.  
**Failure modes:** evidence pane becomes decorative, only the latest answer is understandable, and operators lose the relationship among multiple runs.  
**Architecture fit:** good incremental fit but incomplete as the long-term consulting workspace.

### C. Investigation-centric workspace

The investigation is primary. Questions, executions, evidence sets, claims, notes, gaps, comparisons, timelines, and deliverables are views or objects within it. Conversation is one way to create and manipulate those objects.

**Strengths:** best resumption, comparison, evidence organization, and deliverable transition; aligns with the existing TASK-008 boundary; makes authority and run history explicit; supports both exploratory and precise work.  
**Weaknesses:** requires a coherent information architecture; risks overwhelming the operator if every object is visible at once; needs disciplined staged delivery.  
**Failure modes:** a generic “canvas” becomes cluttered, generated objects proliferate, or the investigation model is over-designed before real use.  
**Architecture fit:** strongest. It extends an implemented investigation concept instead of inventing a chat authority.

### D. Research-plan / agent-oriented interface

The operator states a need; the product visibly constructs and executes a plan, showing steps, coverage, follow-ups, budgets, stopping conditions, and results.

**Strengths:** excellent activity inspectability; makes bounds and stopping behavior concrete; good for complex, multi-step questions; aligns with TASK-007.  
**Weaknesses:** plan watching is not the same as research; high cognitive load for routine questions; encourages anthropomorphic agent expectations; weak durable organization after execution.  
**Failure modes:** theatrical plans, unnecessary steps, operator micromanagement, and a plan trace that obscures the evidence itself.  
**Architecture fit:** valuable as a run view within an investigation, not as the product's primary object.

### E. Search/browse-first with conversational synthesis

Repository search, filters, timelines, source trees, and evidence selection are primary. The model synthesizes selected or retrieved evidence and handles follow-up explanation.

**Strengths:** strongest operator control and evidence precision; works when models are unavailable; naturally supports source browsing and narrow investigations; keeps provenance salient.  
**Weaknesses:** higher query-formulation burden; weaker for ambiguous early exploration; manual selection can miss evidence; less approachable for broad consulting questions.  
**Failure modes:** the model merely summarizes a biased operator selection, discovery becomes slow, or sophisticated filters reproduce persistence concepts.  
**Architecture fit:** strong, especially given the artifact browser and retrieval contracts. It should be a first-class mode inside the recommended workspace.

### F. Evidence-ledger / claim-map notebook

The primary surface is a structured notebook or claim graph. Operators create hypotheses and claims, attach supporting or contradicting evidence, and build deliverables from the graph. There may be no continuous chat transcript.

**Strengths:** clearest authority, contradiction, and claim-to-evidence representation; excellent resumption and report preparation; supports collaborative review later.  
**Weaknesses:** highest modeling and UI complexity; premature ontologies can constrain actual research; slower for open-ended exploration; risks turning every thought into durable pseudo-knowledge.  
**Failure modes:** card sprawl, false precision, confusing overlap with derived repository knowledge, and expensive migrations as workflows evolve.  
**Architecture fit:** conceptually strong but should influence the investigation model incrementally rather than be implemented as a full claim graph first.

### 6.1 Full qualitative comparison

| Alternative | Operator workflow | Cognitive load | Exploratory research | Precise evidence work | Provenance and citations | Uncertainty, contradiction, activity inspection |
|---|---|---|---|---|---|---|
| A. Chat | Ask, read, follow up in one stream | Low initially; high when history grows | Excellent for ambiguous starts | Weak; scope and selected evidence are implicit | Citations are convenient but usually subordinate to prose | Commonly compressed into answer language; trace feels bolted on |
| B. Chat + evidence | Ask in chat; inspect or pin beside it | Moderate | Excellent | Good for checking an answer; weaker for organizing many answers | Strong if evidence pane remains synchronized at claim level | Good current-run visibility; cross-run contradiction remains awkward |
| C. Investigation | Choose/create investigation; ask, search, inspect, organize, compare | Moderate, controlled by views and progressive disclosure | Very good | Excellent | First-class, claim-level, independently navigable | First-class gaps/contradictions plus on-demand plan and trace views |
| D. Plan/agent | State need; monitor, intervene in, or approve steps | High for routine work | Good for complex questions | Good when steps are well formed | Good package/step provenance; citation work still follows execution | Excellent activity visibility; may expose too much machinery |
| E. Search-first | Filter/browse/select; ask model to synthesize selection or results | Moderate to high query burden | Fair to good | Excellent | Excellent because evidence precedes synthesis | Strong source conflict visibility; retrieval omissions may reflect operator selection |
| F. Evidence ledger | Build claim/hypothesis map; attach supporting/contradicting material | High until conventions become familiar | Fair | Excellent | Excellent and structurally explicit | Excellent, but risks over-formalizing provisional thought |

| Alternative | Resume later | Firm/period/claim comparison | Deliverable transition | Current RFI compatibility | Implementation complexity | Internet extension | Characteristic failure |
|---|---|---|---|---|---|---|---|
| A. Chat | Weak unless transcript is curated | Weak | Narrative export is easy; evidence-led briefing is weak | TASK-007 can render directly; underuses TASK-008 | Low | Easy to add but authority mixing is likely | Fluent answer becomes accidental truth |
| B. Chat + evidence | Moderate; pins help but transcript remains primary | Moderate | Better source appendix, weak reusable structure | Good incremental UI over TASK-006/007 | Moderate | Moderate; external items can occupy evidence pane if strongly typed | Evidence pane becomes decorative |
| C. Investigation | Excellent; executions and explicit objects reopen coherently | Excellent | Excellent; saved views and selected evidence project cleanly | Best fit with existing investigation journal and public contracts | High overall, but stageable | Excellent; external evidence becomes another typed investigation input | Generic workspace accumulates clutter |
| D. Plan/agent | Moderate; plans are history, not durable analysis organization | Moderate | Weak to moderate unless another workspace owns results | Strong TASK-007 fit | High orchestration and progress UX | Technically easy, operationally risky due to open-ended web steps | Plan theater and operator micromanagement |
| E. Search-first | Good with saved searches/evidence sets | Good to excellent | Good; curated evidence exports cleanly | Strong TASK-006/artifact-browser fit | Moderate | Good with a separate external-search corpus and labels | Manual selection bias or filter leakage |
| F. Evidence ledger | Excellent | Excellent | Excellent; claim map naturally becomes outline | Fits authority principles but exceeds current workspace contracts | Very high | Good if external nodes remain visibly ungoverned | Competing pseudo-knowledge system in workspace |

## 7. Comparative evaluation and decision matrix

Scores are 1 (poor) to 5 (excellent). The weighted total is a design aid, not empirical product evidence.

| Criterion | Weight | A Chat | B Chat + evidence | C Investigation | D Plan/agent | E Search-first | F Evidence ledger |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consulting-workflow fit | 15 | 3 | 4 | 5 | 4 | 4 | 5 |
| Exploratory research | 10 | 5 | 5 | 4 | 4 | 3 | 3 |
| Evidence precision | 15 | 2 | 4 | 5 | 4 | 5 | 5 |
| Authority/provenance visibility | 15 | 2 | 4 | 5 | 4 | 5 | 5 |
| Activity inspectability | 10 | 2 | 4 | 4 | 5 | 4 | 5 |
| Resume and reproduce | 10 | 2 | 3 | 5 | 3 | 4 | 5 |
| Comparison and deliverables | 10 | 2 | 3 | 5 | 3 | 4 | 5 |
| Current-architecture fit | 10 | 4 | 4 | 5 | 4 | 4 | 4 |
| Safe stageability | 5 | 5 | 4 | 4 | 3 | 4 | 2 |
| **Weighted total / 100** | **100** | **56** | **78** | **95** | **77** | **84** | **91** |

The recommendation is **C, with B, D, E, and selected F concepts embedded as views**. This is a product composition, not an averaged compromise:

- C defines the durable object and navigation model.
- B defines the always-available evidence desk.
- D defines the execution/progress view.
- E defines direct repository exploration and operator-controlled selection.
- F contributes explicit claim, contradiction, gap, and hypothesis cards only when they prove useful.

A is rejected as the primary model, though a familiar conversational entry surface remains valuable.

## 8. Recommended interaction model

### 8.1 Product shell

The top-level product should distinguish **Research** from **Repository operations**. Acquisition, source configuration, feeds, streams, and catalog administration remain operational surfaces. Research opens an investigation-oriented shell and consumes those authorities through application contracts.

Within Research:

- left rail: investigations, saved views, recent work, status;
- center: current investigation view — overview, question/run, comparison, timeline, or deliverable;
- right evidence desk: cited and selected evidence, source details, authority labels, and provenance traversal;
- bottom or inline run strip: plan progress, budget, coverage, stopping state, and failures.

Conversation should be available as an **input grammar and contextual activity stream**, not as the only history. Example commands include “compare these firms,” “search only transcripts since 2024,” “show contradictions,” “pin claims 2 and 4,” and “turn this comparison into a briefing outline.” Each command produces or updates inspectable investigation objects.

### 8.2 Interaction contract

Before a substantive run, show an editable interpretation summary:

- information need;
- firms/entities/topics;
- date/period;
- artifact/source types;
- repository-only or repository + external mode;
- evidence budget or depth preset; and
- intended output shape, if any.

The operator should not need to approve every plan step. Scope changes, internet access, unusually large disclosure/cost, or acquisition actions require explicit control. Ordinary bounded repository retrieval proceeds and remains inspectable.

### 8.3 Response organization

The result should render as:

1. concise answer or synthesis;
2. claim cards with authority class and claim-level citations;
3. contradictions and competing interpretations;
4. evidence gaps and “what would change this conclusion”;
5. stopping reason and coverage summary; and
6. suggested follow-ups that are clearly suggestions, not autonomous work.

No single confidence percentage should summarize the answer. Confidence belongs, when justified, to a typed claim or derived object and must not substitute for visible evidence quality, coverage, contradiction, and inference labels.

## 9. Representative screen and workflow designs

### 9.1 Main investigation view

```text
┌ Investigations ──────┬ Investigation: HAMR adoption ─────────────────────┬ Evidence desk ────────────┐
│ • HAMR adoption      │ Scope: Seagate | trailing 2y | earnings + mgmt   │ 12 repository items       │
│ • Kernel I/O trend   │ Mode: Repository only                 [Edit]      │  8 source evidence        │
│ • Acquisition brief  │                                                   │  4 derived knowledge       │
│                      │ Ask or direct research…                 [Run]      │                          │
│ Saved views          │                                                   │ Selected excerpt          │
│ • Firm comparison    │ Answer                                             │ “…”                      │
│ • Timeline           │ Management language moved from evaluation… [1][2] │ Source: FY25 call          │
│                      │                                                   │ Authority: Repository      │
│ Unresolved (3)       │ Claims                                             │ Artifact / span / digest   │
│ Contradictions (1)   │ [Source] Management stated…             [1]        │ [Open stored artifact]     │
│                      │ [Derived] Topic normalization indicates… [2][3]   │ [Show provenance]          │
│                      │ [Inference] This may imply…             [1][4]   │                          │
│                      │                                                   │ Why included               │
│                      │ Gaps: conference coverage indeterminate          │ matched scope + reranked   │
├──────────────────────┴ Run: 3/3 steps • incomplete • coverage bounded ──┴──────────────────────────┤
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Citation expansion

```text
Claim: “Management shifted from evaluation to qualified production language.”

  ├─ [Repository evidence] Earnings call, 2024-Q3, exact excerpt
  │    source object → document → immutable artifact → acquisition observation
  ├─ [Repository evidence] Earnings call, 2025-Q2, exact excerpt
  ├─ [Derived knowledge] normalized topic: HAMR adoption
  │    status: uncertain; derivation v3; supports comparison only
  └─ [Model inference] “shifted” is a synthesis across the two statements
       uncertainty: different speakers and contexts may limit comparability
```

The evidence desk defaults to the excerpt and human-readable provenance. Exact IDs, byte spans, checksums, scores, and candidate decisions are expandable.

### 9.3 Comparison view

```text
┌ Dimension ───────────────┬ Seagate ───────────────────┬ Western Digital ───────────┐
│ Technology readiness     │ Claim + 3 citations        │ Claim + 2 citations         │
│ Customer qualification   │ Contradictory evidence     │ Insufficient evidence       │
│ Product timing           │ 2025–2026 range            │ No repository statement     │
│ Capital intensity        │ Derived comparison         │ External-only item excluded │
└──────────────────────────┴────────────────────────────┴─────────────────────────────┘
Rows are saved comparison dimensions. Empty and conflicting cells are first-class states.
```

### 9.4 Repository + web mode

```text
Mode: Repository + external research

Repository baseline (governed)       External discoveries (not in RFI)
───────────────────────────────       ───────────────────────────────────
[R] FY25 filing excerpt               [W] Vendor newsroom, seen 18 min ago
[D] Derived issuer relationship       [W] Trade article, capture incomplete

External item actions: [Keep in investigation] [Propose Add to RFI] [Dismiss]
```

The visual distinction must survive export and not depend only on color. Use labels, iconography, grouping, and citation prefixes.

## 10. Repository research execution model

### 10.1 Stable research application boundary

Add one product-facing application facade, conceptually `rfi.research.ResearchApplicationService`. The name is illustrative; the dependency direction is the decision. Browser routes, a future CLI, and tests depend on this facade. The facade composes existing repository-owned ports and returns UI-ready, persistence-independent contracts. It must not become a second repository or a generic agent framework.

The facade should expose a small command/query surface:

| Operation | Responsibility |
|---|---|
| `create_investigation`, `list_investigations`, `get_investigation` | Durable operator-work organization, never repository evidence |
| `get_corpus_status`, `build_or_rebuild_corpus` | Explicit source/retrieval generation lifecycle, partial failures, staleness, and authority fingerprints |
| `interpret_need` | Normalize `InformationNeed` plus `ResearchScope` for operator review without performing hidden retrieval |
| `execute_question` | Bind one execution to an investigation, scope snapshot, corpus generations, budget, planner/reasoner runtime, and stop/failure semantics |
| `get_execution` | Return saved claims, evidence references, gaps, trace summary, runtime metadata, and historical authority fingerprints |
| `resolve_citation` | Rehydrate a claim reference to exact context and public provenance, or explicitly return stale/missing/superseded state |
| `add_note` | Append explicit operator-authored material outside repository authority |

Reuse existing contracts wherever their meaning already fits:

- `InformationNeed`, `IntelligenceBudget`, `RetrievalPlan`, `EvidencePackage`, `IntelligenceResult`, `ExecutionTrace`, and `EvidenceReference` remain the execution vocabulary.
- `ArtifactQueryService` resolves canonical firm, artifact-type, and source-effective-date scope and reads exact content.
- `SourceObjectReader`, `KnowledgeReader`, `RetrievalRepository`, and `EvidenceAssembler` remain the evidence gateway.
- `IntelligenceOrchestrator` remains responsible for bounded planning, model disclosure, claim mapping validation, and stopping.
- investigation/workspace contracts retain saved non-authoritative executions and notes.

Add only the missing application concepts:

- `ResearchScope`: canonical firm IDs, canonical artifact types, source-effective date interval, and optional repository-owned event kinds. It resolves to document/source identities through public query contracts.
- `ResearchCorpusStatus`: source/retrieval generation IDs, authority fingerprint, eligible/indexed/unsupported/failed counts, freshness, and a typed ready/partial/stale/unavailable state.
- `ResolvedCitation`: authority class, exact excerpt/context, human source label, source-object/document/artifact identities, provenance links, and stale/missing/superseded outcome.
- a product investigation repository port if the current workspace repository cannot safely own product state as implemented.

Do not create a parallel “research question,” “research claim,” transcript taxonomy, evidence package, or model result contract merely to make the browser convenient. UI projections should adapt the existing domain contracts.

### 10.2 Composition and dependency direction

```mermaid
flowchart LR
    UI["Browser / future CLI"] --> APP["ResearchApplicationService"]
    APP --> SCOPE["ArtifactQueryService"]
    APP --> CORPUS["ResearchCorpusCoordinator"]
    APP --> INT["IntelligenceOrchestrator"]
    APP --> INV["Investigation repository"]
    APP --> CITE["CitationResolver"]
    CORPUS --> SRC["Source-object builder and reader"]
    CORPUS --> RET["Retrieval repository / evidence assembler"]
    INT --> RET
    INT --> MODEL["Replaceable planner/reasoner ports"]
    CITE --> SCOPE
    CITE --> SRC
    CITE --> K["KnowledgeReader"]
    REP["Immutable repository authority"] --> SCOPE
    REP --> SRC
    K --> RET
    WEB["Future external-research gateway"] -. "reserved adapter seam; absent in Stage 1" .-> APP
```

Dependency rules:

1. The UI sends operator intent and renders projections; it does not build retrieval queries, enforce evidence budgets, resolve artifact paths, or validate claim mappings.
2. The model receives bounded evidence packages; it cannot query persistence, write investigation/repository state, classify authority, choose credentials, or decide acquisition.
3. Corpus construction enumerates retained artifacts through public artifact queries and reads bytes through public content contracts. It records generation/failure state explicitly and never rebuilds silently during a question.
4. Each execution snapshots normalized scope, generation identities, authority fingerprint, runtime/prompt identity, evidence references, gaps, and stopping reason. Raw conversation and raw model exchange remain ephemeral by default.
5. Thin `/research` browser routes may live in the existing local admin server, but the current broad request handler must delegate to the application facade rather than absorb orchestration logic.

### 10.3 Execution flow

```mermaid
sequenceDiagram
    actor O as Operator
    participant UI as Research workspace
    participant APP as Research application service
    participant INT as Intelligence orchestrator
    participant RET as Governed retrieval
    participant EVD as Evidence assembler
    participant REP as Repository authorities
    participant MOD as Replaceable planner/reasoner

    O->>UI: State information need and scope
    UI->>APP: InformationNeed + operator constraints + mode
    APP-->>UI: Editable interpretation and bounded plan summary
    APP->>INT: Execute approved/default-bounded run
    INT->>MOD: Construct structured retrieval plan
    MOD-->>INT: RetrievalPlan
    loop Bounded retrieval steps
        INT->>RET: RetrievalQuery
        RET->>REP: Public source/knowledge contracts
        REP-->>RET: Typed candidates and authority state
        RET->>EVD: RetrievalResponse
        EVD->>REP: Exact artifact read via public port
        EVD-->>INT: EvidencePackage + gaps + contradictions
        INT-->>UI: Step status and coverage summary
    end
    INT->>MOD: Bounded ModelEvidence
    MOD-->>INT: Untrusted ReasoningDraft
    INT->>INT: Validate claims, mappings, authority, bounds
    INT-->>APP: IntelligenceResult + ExecutionTrace
    APP->>APP: Append durable investigation execution projection
    APP-->>UI: Claims, citations, gaps, stop reason, evidence handles
    O->>UI: Inspect, pin, annotate, compare, or export
```

### 10.4 Visibility levels

| Execution concept | Normal view | On demand | Diagnostic only |
|---|---|---|---|
| Interpreted need and scope | Yes; editable before run | Full normalized request | Raw serialization |
| Plan | Step summary and progress | Purposes, queries, follow-ups, stop conditions | Raw planner output and validation details |
| Metadata constraints | Human-readable chips | Full constraint set | Contract encoding |
| Evidence budgets | Depth preset and exhaustion warning | Exact package/result/context limits | Internal counters |
| Evidence packages | Counts, completeness, gaps | Package contents and context | Package identity/digests |
| Source vs derived results | Always labeled | Full object details | Storage-independent raw contract |
| Candidate decisions/scores | “Why included” for selected items | Included/excluded rationale | Full decision list and vector components |
| Claim mappings | Citation per claim | Complete evidence mapping | Grounding validator details |
| Stop reason | Always visible | Related failures and bounds | Ordered execution trace |
| Raw model exchange | No | Only for privileged audit if retention permits | Diagnostic, redacted, policy controlled |

### 10.5 Follow-up semantics

A follow-up question can either:

- run against the investigation's current scope;
- narrow to selected evidence;
- broaden the scope and create a new run;
- ask for explanation without new retrieval; or
- create a durable operator object such as a note, unresolved question, or comparison dimension.

The UI should make that effect visible. “Use only these four sources” is materially different from “find more evidence about this claim.”

## 11. Evidence and authority model

| Class | Meaning | Authority | Default durability | Citation label | May support answer claims? |
|---|---|---|---|---|---|
| Repository evidence | Exact material admitted through RFI acquisition and retained as immutable artifacts/observations | Authoritative source evidence | Repository durable | `R` Repository evidence | Yes |
| Derived repository knowledge | Versioned interpretation built from repository source objects | Governed interpretation, not source authority | Repository durable and rebuildable/versioned | `D` Derived knowledge | Yes, with status and provenance |
| External research evidence | Web-discovered material not admitted to RFI | Investigation-scoped, ungoverned external information | Ephemeral by default; optionally kept in investigation under explicit retention | `W` External, not in RFI | Yes only in web mode and always separately labeled |
| Model inference | Synthesis or reasoning produced from consumed material | Non-authoritative | Execution-scoped; durable only as a labeled execution result | `I` Model inference | Yes, with evidence mapping and uncertainty |
| Operator material | Notes, corrections, hypotheses, conclusions, selections | Operator-authored workspace state | Durable when explicitly saved | `O` Operator note/hypothesis | Not source evidence; may guide later work |
| Deliverable projection | Briefing/report/timeline generated from selected state | Output projection | Durable export or version when explicitly created | Preserves underlying labels | N/A |

### 11.1 Answer rules

- A source-fact claim cites repository evidence directly.
- A derived-knowledge claim cites the derived object and allows one-step expansion to all supporting source evidence and status.
- A model inference cites the evidence used to infer it and includes an uncertainty statement. It must not masquerade as a source quotation.
- In repository-only mode, external evidence is unavailable rather than silently used.
- In repository + web mode, repository and external evidence can appear in one synthesis only if each claim's support mapping retains its authority class.
- A contradiction across classes reports both the content conflict and the authority asymmetry. A recent external article does not silently overrule an immutable filing; neither does the filing prove current state.

### 11.2 External evidence retention and Add to RFI

External discoveries should be ephemeral by default. A saved investigation may explicitly keep a bounded external-research record containing source URL, publisher/title, discovery time, search/query context, attributed excerpt or sanitized capture where policy permits, content digest, and retrieval status. It remains labeled `external-not-governed` and outside canonical repository evidence.

**Propose Add to RFI** should create an acquisition proposal or launch an already supported governed acquisition workflow. It must:

1. show what source and content are proposed;
2. select an existing source profile/adapter or report that none exists;
3. pass deterministic validation and normal repository ingress;
4. return an acquisition outcome with complete/incomplete/indeterminate coverage where applicable; and
5. only then link the investigation to the resulting repository artifact and source objects.

The external record remains useful historical discovery provenance. It is not rewritten to pretend it was always repository evidence.

## 12. Internet augmentation architecture

### 12.1 Approaches compared

| Approach | Benefits | Costs and risks | Recommended role |
|---|---|---|---|
| Model-native web search | Fast integration; model can interleave discovery and synthesis | Provider coupling; opaque ranking/queries; weaker replay; variable citations and cost; prompt-injection exposure inside model context | Optional discovery adapter, never the authority boundary |
| RFI-owned search/retrieval service | Explicit queries, budgets, source policy, caching, provenance, and replaceability | More orchestration, normalization, and operations work | Primary control plane |
| Provider-specific search APIs | Good freshness and explicit result metadata; simpler than crawling | Provider-specific ranking/licensing/cost; snippets may not support claims; source-quality variability | Replaceable search adapters behind RFI contracts |
| Bounded browser/research agent | Reaches dynamic sites and complex navigation | Highest nondeterminism, injection exposure, cost, and reproducibility risk; hard to define completeness | Escalation path for explicitly bounded sources, not default search |
| Search discovery then deterministic acquisition | Strongest later repository provenance and reproducibility | Slower; requires supported adapters and source validation; many pages will not be admissible | Required promotion path for governed evidence |

### 12.2 Recommended composition

Add a provider-neutral **ExternalResearchGateway** owned by the research application layer. It accepts a bounded external research request and returns typed `ExternalEvidenceItem` values plus an inspectable discovery trace. Behind it:

1. one or more replaceable search adapters discover candidate URLs and snippets;
2. RFI-owned policy ranks and filters domains, freshness, source class, duplication, and budget;
3. a deterministic fetch/extraction path captures ordinary pages where permitted;
4. a bounded browser agent is available only for a declared dynamic-page step;
5. content is sanitized, isolated, and labeled untrusted before any model sees it; and
6. the research orchestrator builds a combined model package whose authority types remain distinct.

This architecture permits a model-native web-search implementation behind the gateway while avoiding dependence on its provider-specific trace or citation format. The public result must record the RFI request, adapter identity/version, discovery time, URLs, fetch outcome, digests where available, omissions, and stopping reason.

### 12.3 Reproducibility expectation

Internet research cannot promise the same reproducibility as immutable repository evidence. The UI and result contract should distinguish:

- **replayable from retained repository evidence**;
- **reconstructable from a retained external capture**;
- **reference-only external discovery** whose source may change; and
- **non-reproducible model inference** tied to a recorded evidence set and runtime metadata.

Freshness should be an explicit timestamp and source property, not a confidence proxy.

## 13. Conversation and investigation state model

### 13.1 Long-term conceptual objects

| Object | Durable? | Authority | Reproducibility expectation |
|---|---|---|---|
| Investigation | Yes | Workspace organization | Rebuild current view from append-only events |
| Research run/execution | Yes | Non-authoritative historical projection | Re-executable when referenced authorities/runtime remain available; difference is visible |
| Operator question/information need | Yes when run or explicitly saved | Operator request | Exact text and normalized scope retained |
| Transient drafting conversation | No by default | None | None |
| Evidence set | Later, when explicitly pinned/named | References only; does not own evidence | Resolve current repository evidence and retain historical identities |
| External evidence set | Ephemeral by default; explicit keep | Ungoverned investigation material | Capture-dependent and clearly limited |
| Model conclusion | Within execution; separately saved only as labeled note/hypothesis | Model inference | Re-run may differ; source mapping retained |
| Operator note | Yes | Operator-authored | Exact append-only record |
| Hypothesis / unresolved question | Yes when explicitly created | Operator/workspace object, not repository knowledge | Exact history; status changes append events |
| Comparison/timeline definition | Yes when saved | Projection definition | Regenerable against selected evidence/run |
| Generated deliverable | Explicit versions only | Projection | Retain inputs, evidence references, labels, and digest |
| Raw model input/output | No by default | Diagnostic material | Retention policy may permit bounded audit capture |
| Full retrieval trace | Reference snapshot durable; rich detail policy controlled | Diagnostic execution state | Rehydrate where possible; retain IDs and stop/failure facts |

### 13.2 First-class objects to add cautiously

The first vertical slice needs only three durable first-class concepts: **investigation**, **execution**, and **operator note**. An execution retains the exact question, normalized scope, corpus/runtime fingerprints, structured result, evidence-reference identities, gaps, failures, and stopping reason. This is sufficient to save and reopen the Seagate HAMR investigation without making a conversation transcript or generated conclusion authoritative.

Named evidence sets, hypotheses, unresolved questions, comparisons, and timelines should first be projections or typed annotations over executions. Promote them to richer contracts only after observing repeated operator workflows. This avoids speculative persistence and a competing ontology. In particular, a saved citation is a reference to repository authority, not a copy that acquires its own truth status.

The product-integrated investigation repository should participate in the application's normal structured-state lifecycle, backup, and recovery. If the existing filesystem journal is not reused directly, its append-only execution meaning, integrity checks, explicit terminal outcomes, and immutable historical reference snapshots remain requirements of the replacement port.

### 13.3 Raw conversation history

Raw conversation history should not be treated as truth or as the only replay input. Durable state should record the exact information need for each execution, normalized scope, resulting plan/result/reference snapshot, and explicit operator actions. Transient explanatory exchanges may be discarded unless the operator converts them into a note, question, evidence selection, or deliverable change.

## 14. Provenance, citation, uncertainty, and contradiction UX

### 14.1 Citation anatomy

Every visible citation should resolve through a public application contract to:

- authority class;
- human-readable source identity and date;
- exact excerpt and bounded context where available;
- repository document, artifact, and source-object identity;
- derived-object identity, status, derivation, and supporting provenance where applicable;
- acquisition observation and original location on demand;
- retrieval package/trace and “why included” on demand; and
- external discovery/capture metadata for web items.

Citation numbers should be stable within an execution or deliverable version. They should not be globally stable identities.

### 14.2 Uncertainty

Use concrete uncertainty dimensions:

- evidence coverage;
- source authority/quality;
- recency;
- ambiguity of entity, term, period, or speaker;
- contradiction;
- extraction/derivation status;
- retrieval truncation or budget exhaustion; and
- inference strength.

Render these as explanations and states. Avoid a single red/amber/green badge that combines incomparable concerns.

### 14.3 Contradiction

A contradiction card should show the competing claims side by side, their authority classes, dates, scope, and exact support. The model may offer possible explanations — changed position, different period, definition mismatch, correction, or genuine conflict — but those explanations remain inference. An operator resolution creates a labeled note or later governed knowledge correction; it does not rewrite the source conflict.

### 14.4 Insufficient evidence

An insufficient result should say:

- what was searched;
- what was found;
- what requirement was not satisfied;
- whether coverage itself is incomplete or indeterminate;
- what follow-up retrieval was attempted;
- why the system stopped; and
- what additional source type, firm, period, or external search could help.

It should still allow the operator to inspect and pin partial evidence.

## 15. Security and prompt-injection considerations

Repository retention does not make content safe. Existing RFI behavior correctly treats stored HTML as hostile and isolates it. The same principle must apply to all text passed to models and all external research.

### 15.1 Trust boundaries

- Source and external content are data, never instructions.
- Planner and reasoner prompts must clearly delimit untrusted content.
- The model cannot directly write repository, workspace, acquisition, or configuration state.
- Research tools are allowlisted, typed, bounded, and supplied by orchestration; arbitrary shell, filesystem, credential, or browser access is unavailable.
- The UI initiates state-changing actions through application services and explicit operator intent.

### 15.2 External research controls

- domain and scheme policy, redirect limits, content-size limits, media-type gates, timeout and rate limits;
- network isolation and protection against requests to local/private infrastructure;
- sanitization and script-free rendering;
- separation of fetched content from search/provider metadata;
- detection and visible labeling of fetch failures, partial captures, and unsupported media;
- model disclosure budgets and sensitive-repository-content policy;
- no secrets in prompts, traces, retained captures, URLs, or provider logs;
- output validation that enforces authority types and claim mappings; and
- a separate acquisition boundary for any proposed promotion.

### 15.3 Browser-agent controls

If a browser agent is used later, it should receive one bounded research step, an allowlisted or operator-approved domain set, read-only navigation tools, a page/interaction/time budget, and no authenticated session by default. Downloads, form submissions, uploads, purchases, messaging, and account changes are outside research scope. The trace records visited URLs, observed redirects, extraction outcomes, and stopping reason without treating screenshots or rendered DOM as repository evidence.

### 15.4 Data disclosure and model replaceability

The current `RuntimePolicy` is a useful start: provider names, retention mode, sensitive-content permission, and credential environment-variable names remain separate from credentials. The production decision must additionally define source-level disclosure policy, redaction, jurisdiction/provider restrictions, prompt/version registry, usage/cost telemetry, and deletion/retention behavior. Provider-specific citation or web-search formats must be normalized before reaching the public result.

## 16. Mapping to current RFI contracts and architectural gaps

| Current contract/subsystem | What it already supports | Gap for the recommended product |
|---|---|---|
| `ArtifactQueryService` | Typed browsing, chronology, observations, exact content, isolated preview | No content search; no unified citation resolver; adjacent filter model differs from research retrieval |
| Transcript acquisition and classification | Historical bounded backfill; canonical earnings versus management artifact classes; repository event kind; raw observation retained | Provider coverage and completeness remain bounded/indeterminate; event kind is not a first-class artifact-query filter |
| `SourceObjectReader` | Stable exact spans, hierarchy, document navigation, bounded context | SEC SGML-only structure; no transcript turn/paragraph segmentation |
| `KnowledgeReader` / `DerivedObject` | Versioned status, confidence, provenance, corrections, reverse navigation | Very narrow issuer/filing ontology; no research-ready topic, claim, event, speaker, or temporal semantics |
| `RetrievalQuery` / `RetrievalRepository` | Source/derived classes, metadata filters, bounded ranked results, trace, health | POC ranking; no validated recall/precision; no operator-friendly canonical scope facade; not integrated with live application lifecycle |
| `EvidenceAssembler` / `EvidencePackage` | Verified contexts, budgets, gaps, omissions, contradictions | No cross-package evidence-set contract; no external evidence package class; artifact-reader composition is script-specific |
| `IntelligenceOrchestrator` | Structured plan, bounded follow-up, claim mapping, inference labels, failure/stop semantics | Deterministic planner/reasoner only; external authority absent; no async job/cancel/progress application boundary; no eval harness for research quality |
| `WorkspaceRepository` / `WorkspaceService` | Durable investigations, append-only executions, annotations, comparison, export, backup | POC filesystem authority is not product-composed; no browser/API; later evidence rehydration contract incomplete |
| Admin server and HTML pages | Local operator shell, progressive detail, acquisition UI, artifact inspection | No research routes or service composition; large handler is already broad and should not absorb research orchestration logic |
| Acquisition contracts | Governed ingress, immutable artifacts/observations, explicit interval outcomes, management transcript retention | No generic proposal/status bridge from future external research; intentionally independent of Stage 1 |

### 16.1 Most important gaps

1. **Application composition and lifecycle.** Source construction, knowledge derivation, retrieval indexing, intelligence, and workspace are proof-script compositions rather than a live application vertical slice over the main repository state.
2. **Transcript semantic evidence coverage.** RFI retains the right artifact classes but cannot cite or retrieve exact transcript turns/paragraphs while source objects remain SEC-header-specific.
3. **Research application boundary.** There is no repository-independent facade for investigation commands, async executions, citation resolution, evidence pinning, run comparison, or UI-ready progress.
4. **Integrated operator inspection.** The existing browser can inspect artifacts but cannot inspect the same source objects, derived objects, evidence packages, and intelligence mappings a model consumes.
5. **Retrieval quality and evaluation.** Contracts are strong; ranking quality, recall, result diversity, temporal comparison, and realistic consulting-answer evaluation are unproven.
6. **Live model adapter and runtime governance.** No provider adapter, prompt/version registry, transcript research evaluation, cost policy, or production retention policy exists.
7. **Citation resolution after save.** Workspace snapshots retain identities rather than source context. A stable resolver must rehydrate current evidence, report missing/stale authorities, and preserve historical meaning.
8. **Product investigation persistence.** The POC journal semantics exist, but the product must decide how investigation state participates in the application's structured-state, backup, restore, and integrity lifecycle.
9. **Canonical research constraints.** Firm IDs, entity IDs, artifact types, document types, source kinds, periods, and publication chronology need one operator-facing translation layer rather than leaking subsystem vocabularies.
10. **External evidence semantics, later.** There is no typed external evidence, discovery trace, combined authority mapping, retention policy, or acquisition-proposal bridge. These are intentional later gaps, not blockers for repository-only research.

### 16.2 Boundaries that must remain outside the UI

- retrieval planning and query validation;
- index health and authority fingerprinting;
- evidence assembly and byte-budget enforcement;
- claim grounding and authority validation;
- external fetch/search policy;
- acquisition proposal validation and execution; and
- workspace append/integrity semantics.

The UI owns interaction state, presentation, explicit operator intent, and view composition. It does not own evidence semantics.

### 16.3 Boundaries that must remain outside the reasoning/model layer

- repository reads other than the governed evidence gateway;
- workspace writes;
- acquisition writes or “Add to RFI” decisions;
- authority classification supplied by the repository/application contracts;
- credential resolution;
- budget enforcement and stopping authority;
- citation identity and provenance validation; and
- final acceptance of operator notes, hypotheses, or deliverables.

## 17. Recommended staged implementation

This is a proposed decomposition from which bounded task tickets can be written after architectural review. It is not authorization to implement, and no tickets are created by this study. The first four tasks form the repository-only vertical slice; each has a useful verification boundary and does not depend on the browser to prove its contracts.

### Task 1 — Product-composed transcript research corpus

**Objective:** Make governed Seagate transcript evidence research-addressable with exact provenance.

**In scope:**

- enumerate retained artifacts through `ArtifactQueryService` using canonical firm, `earnings_transcript`/`management_transcript`, and source-effective-date constraints;
- implement deterministic transcript source-object segmentation at an agreed paragraph or speaker-turn granularity, with exact retained-byte spans/digests and event/date/speaker metadata where available;
- add the minimal `ResearchScope`, corpus build/rebuild/status, generation, failure, staleness, and authority-fingerprint application contracts;
- compose existing source-object, retrieval, and evidence-package implementations against live application state; and
- add a headless corpus/retrieval proof for the Seagate trailing-two-year scope.

**Out of scope:** browser UI, model calls, investigation persistence, derived HAMR claims, web research, new acquisition, or a new transcript taxonomy.

**Acceptance evidence:** all eligible retained Seagate earnings and management transcripts in the chosen interval are accounted for as indexed, unsupported, or failed; exact excerpts round-trip to verified immutable artifact bytes; repeated builds have deterministic identities; stale/partial/unavailable states are distinguishable; and a bounded HAMR retrieval returns inspectable source contexts through public contracts.

**Primary risks:** exact span mapping in provider HTML, speaker-boundary ambiguity, and confusing research-index coverage with acquisition completeness.

### Task 2 — Repository-only research application execution

**Objective:** Establish the stable application facade and prove grounded question-to-claim execution without a browser.

**In scope:**

- implement `ResearchApplicationService` execution and citation-resolution operations over existing retrieval, evidence, and intelligence contracts;
- translate `ResearchScope` to repository-owned retrieval identities through public queries;
- add a replaceable planner/reasoner adapter behind the existing ports, deterministic test doubles, prompt/runtime identity, disclosure policy, budgets, and failure normalization;
- execute the representative Seagate HAMR question and return source facts, model inference, claim-to-evidence mappings, gaps, contradictions, uncertainty, and stopping reason; and
- resolve every visible citation to exact source context and artifact provenance, including explicit stale/missing outcomes.

**Out of scope:** durable investigations, browser UI, general agents, report generation, web search, or repository writes from the model.

**Acceptance evidence:** a headless execution cannot return unsupported or unmapped claims; model inference is distinct from source evidence; every claim citation resolves to the same corpus generation or reports why it cannot; budget exhaustion and insufficient evidence are usable results; and no application component reads SQLite, artifact paths, or index internals directly.

**Primary risks:** structural grounding without semantic entailment, model data-egress policy, and retrieval recall for temporal language change.

### Task 3 — Product-integrated durable investigations

**Objective:** Save and reopen non-authoritative research work without creating a second source of repository truth.

**In scope:**

- compose or adapt the current workspace contracts behind a product investigation repository;
- create/list/get investigations and append execution-started plus terminal outcomes and operator notes;
- retain exact information need, normalized scope, corpus/runtime fingerprints, structured result, evidence references, gaps/failures, and stop reason;
- reopen an investigation and rehydrate citations through `CitationResolver`, visibly reporting upstream change; and
- integrate investigation state with the application's backup, restore, integrity, and partial-write expectations.

**Out of scope:** raw conversation as durable truth, named evidence sets, hypotheses/claim graphs, comparison/timeline builders, collaboration, or reports.

**Acceptance evidence:** create → execute the HAMR question → save → terminate/restart → reopen produces the same historical execution projection and evidence identities; changed/missing upstream state is honest; failed or interrupted executions have explicit terminal semantics; and model output remains labeled non-authoritative.

**Primary risks:** persistence migration, preserving append-only meaning, and historical citation rehydration across corpus rebuilds.

### Task 4 — Operator research vertical slice

**Objective:** Deliver the smallest useful `/research` experience over the facade and validate it with an expert operator.

**In scope:**

- a thin local browser surface for investigation create/list/open;
- editable repository-only scope, corpus readiness, question execution, progress/stop state, answer and claim cards;
- an evidence desk with expandable citations, exact excerpt/context, event/date/speaker, provenance traversal, and deep link to the stored artifact;
- visible source-versus-inference labels, contradictions, gaps, truncation, partial failure, and insufficient-evidence behavior; and
- save, close, and reopen of the representative investigation.

**Out of scope:** web mode, autonomous planning controls, acquisition mutation, cross-firm comparison UI, generated timelines, named evidence sets, deliverable authoring, or product-wide visual redesign.

**Acceptance evidence:** an operator completes the entire Seagate HAMR flow without raw JSON or persistence knowledge; everything available to the model is inspectable; repository-only mode is enforced; the UI cannot bypass application budgets or authority validation; and a small qualitative evaluation records whether the result is useful, misleading, or insufficient.

**Primary risks:** UI density, long-running synchronous requests, and visually implying more corpus completeness than RFI can establish.

### Later stages — consulting projections and governed internet augmentation

Only after the vertical slice is useful should RFI consider named evidence sets, reusable comparisons/timelines, selected reruns, report or briefing projections, and richer claim/hypothesis workflows. The first internet pilot then introduces `ExternalResearchGateway`, one bounded search/fetch composition, typed external evidence, external inspection, explicit retention, and injection controls. A later **Propose Add to RFI** bridge may submit supported discoveries to existing acquisition services. Authentication, multi-user collaboration, distributed execution, and general browser agents remain need-driven rather than assumed milestones.

## 18. Key architectural decisions required before implementation

1. **Transcript citation unit:** Is a paragraph, speaker turn, or hybrid the stable source-object unit, and what exact-byte behavior is required when retained HTML splits or annotates text?
2. **Corpus lifecycle:** Are builds explicitly operator-triggered at first, post-acquisition, or both? This study recommends explicit build/rebuild/status for the first slice and no hidden rebuild during a question.
3. **Scope semantics:** Is `TranscriptEventKind` needed as a typed Stage-1 query constraint, or is canonical artifact type plus date sufficient while event kind remains display metadata? This study recommends the latter unless retrieval evaluation proves otherwise.
4. **Planner/reasoner runtime:** Which replaceable provider is allowed, what retained content may leave the local system, and what prompt, runtime, usage, cost, and raw-exchange metadata may be kept?
5. **Investigation persistence:** Should the existing hash-chained filesystem journal be adapted, or should a new port implementation place equivalent append-only semantics in the application's SQLite structured-state authority? This study recommends the latter direction unless a concrete integrity requirement favors the journal.
6. **Historical citation semantics:** On corpus rebuild, should a saved citation prefer the historical generation, current matching source identity, or both? What operator wording distinguishes stale, missing, and superseded?
7. **Research job boundary:** Is the first local execution short enough to be synchronous, or must the application facade expose durable jobs, progress polling, and cancellation from Task 2? The UI must not invent a separate job protocol.
8. **HAMR evaluation threshold:** What evidence set and human rubric establish that temporal retrieval and synthesis are sufficiently useful, not merely structurally grounded?
9. **Corpus availability:** Does the intended operational state contain enough licensed/retained Seagate evidence across the trailing two years, and how should indeterminate provider coverage constrain product claims?
10. **Internet hook shape:** Should Stage 1 reserve an external evidence variant in public results now or add it later through a versioned contract? No external provider or retention choice is required for the repository-only tasks.

## 19. Risks and unresolved questions

- **Usefulness risk:** strong contracts do not compensate for shallow source segmentation. The first corpus must contain substantive text and realistic multi-document questions.
- **Transcript-span risk:** provider HTML may make speaker turns visually obvious but hard to map to exact retained byte ranges without normalization drift.
- **Coverage-claim risk:** successful historical pulls prove bounded retained results, not completeness of all Seagate management remarks during the interval.
- **Retrieval-quality risk:** current deterministic tests prove bounds and provenance, not recall, ranking, or consulting relevance.
- **UX-density risk:** claims, evidence, gaps, plans, history, and diagnostics can overwhelm. Progressive disclosure and role-based defaults require operator testing.
- **Authority-comprehension risk:** too many badges can become visual noise. Language and interaction tests must verify that operators understand the distinctions.
- **Historical rehydration risk:** saved reference snapshots may point to rebuilt, superseded, or unavailable upstream state. The product must show this honestly.
- **Model-evaluation risk:** structural grounding validation cannot prove semantic entailment or analytical quality. Human evaluation sets are required.
- **Web-security risk:** external content increases injection, exfiltration, malicious-file, and source-impersonation exposure.
- **Capture-policy risk:** retaining external excerpts or pages may create privacy, licensing, or retention obligations even when they are not repository evidence.
- **Promotion confusion:** “Add to RFI” may be misread as immediate trust. The UI must show proposed, acquired, rejected, incomplete, indeterminate, and governed states separately.
- **Product-boundary risk:** integrating Research into the current admin server may entrench a monolithic handler. The UI can share a shell while using a separate research application service.
- **State-model risk:** making hypotheses and claims first-class too early could create a competing knowledge system inside the workspace.
- **Composition risk:** copying the workspace POC's filesystem store directly into the product could create an awkward second structured-state authority and backup path.

Human architectural judgment is especially required on transcript citation granularity, corpus lifecycle, live-model disclosure policy, investigation persistence, historical citation behavior, and the HAMR usefulness rubric.

## 20. Rejected alternatives and reasons

### Conventional chat as the primary product

Rejected because it optimizes the transient projection rather than RFI's durable advantage. It performs poorly for resumption, comparison, contradiction, evidence selection, and deliverable construction, and it creates pressure to treat conversation history as state.

### Autonomous general research agent

Rejected because RFI needs bounded retrieval and explicit authority, not open-ended tool use. A general agent increases security, cost, reproducibility, and operator-control risk without solving the durable investigation model.

### Search-only expert interface

Rejected as the sole model because it places too much query and synthesis burden on the operator and underuses bounded model assistance. It remains a first-class mode inside the recommendation.

### Full claim graph or ontology-first notebook

Rejected for the first implementation because it would add speculative persistence and risk overlap with derived repository knowledge. Selected claim/gap/hypothesis concepts should emerge from observed investigations.

### Model-native web search as the internet architecture

Rejected as the authority/control plane because it couples provenance, tracing, cost, and citation semantics to a model provider. It may be used behind an RFI-owned gateway.

### Automatic promotion of useful web results

Rejected because research discovery does not satisfy acquisition validation, identity, provenance, immutable retention, or coverage semantics. Promotion must remain explicit and governed.

## 21. Recommended next step

Hold a focused architectural review of this reconciliation and decide the items in section 18 that block Task 1 and Task 2, with special focus on:

1. transcript citation granularity and exact-byte requirements;
2. explicit corpus build/rebuild/status lifecycle;
3. live-model provider, disclosure, retention, and evaluation policy;
4. historical citation rehydration semantics; and
5. whether product investigation persistence should use the main structured-state authority behind preserved append-only workspace contracts.

After those decisions, write the bounded ticket for **Task 1 — Product-composed transcript research corpus** using section 17 as its scope and acceptance baseline. Do not start implementation from this study, and do not combine model integration, browser work, internet search, acquisition promotion, rich report authoring, collaboration, or a general agent into that first ticket.

## 22. Architectural Status Summary

| Subsystem | Status | Research-relevant responsibility and limitation |
|---|---|---|
| Repository foundation | Complete | Governing principles, immutable identity, public contracts, verification discipline, and current-state status language are reconciled |
| Acquisition substrate and engine | Product-integrated; usable with limitations | Multiple deterministic sources and immutable observations exist; historical transcript backfill is bounded and operational coverage varies by provider |
| Artifact query and inspection | Complete for current operator use | Strong normalized read/preview boundary; no research search or unified citation resolution |
| Transcript classification | Product-integrated | Earnings and broader management events are canonically distinct while provider observations remain inspectable |
| Source-object subsystem | Implemented POC with major semantic limitations | Stable exact spans and rebuild exist; only SEC submission structure is research-indexed and transcript segmentation is missing |
| Derived-knowledge subsystem | Usable with major ontology limitations | Versioning, status, provenance, and correction exist; current issuer/filing knowledge is too narrow for most workflows |
| Governed retrieval and evidence assembly | Complete contracts; provisional quality | Typed results, packages, traces, budgets, and fail-closed health exist; realistic ranking quality and application lifecycle are unproven |
| Model-guided intelligence | Complete POC contracts; provisional quality | Plans, bounds, mappings, failures, and replaceability exist; no live model or external evidence class |
| Consulting workspace | Implemented local POC; not product-composed | Durable investigations, runs, annotations, comparison, and export exist; product persistence, browser/API, and citation rehydration are unresolved |
| Current browser product | Complete for local administration; research not started | Reusable artifact-inspection and failure-visibility patterns exist; no research surface consumes TASK-006 through TASK-008 |
| Repository-only research workspace | Not started | Decomposed into four proposed bounded tasks: corpus, application execution, durable investigations, and operator vertical slice |
| Internet augmentation | Not started | Requires external evidence authority, gateway, security, retention, and acquisition-proposal decisions |

The next architectural milestone should be Task 1's product-composed transcript corpus, verified independently of model and UI behavior. The four-task sequence then proves one useful repository-only Seagate HAMR investigation end to end through public contracts. Internet augmentation should follow only after that authority and interaction model is validated.
