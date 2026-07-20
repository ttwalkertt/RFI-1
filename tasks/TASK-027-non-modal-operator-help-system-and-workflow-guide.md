# TASK-027 — Non-Modal Operator Help System and Workflow Guide

## Status

Ready

## Purpose

Provide RFI-1 with a formal, repository-owned operator help system that supports competent use without requiring operators to memorize controls, workflows, or system state transitions.

The help system must function as an **operator companion**: an operator must be able to keep Help open beside the RFI-1 administration interface and follow its instructions while continuing to manipulate the application.

This task converts the application's existing scattered assistance—such as command help, labels, validation messages, and field-level explanations—into a coherent, navigable, workflow-oriented product capability.

## Problem Statement

RFI-1 now exposes multiple related controls, concepts, and workflows whose individual behavior may be understandable but whose combined operating model is not always intuitive.

Operators currently may need to infer:

- where a workflow begins;
- which prerequisites must already exist;
- which actions are read-only and which persist state;
- what validation, preview, save, revision, execution, import, and export mean;
- where results and retained evidence appear;
- how immutable revisions and lineage affect later actions;
- why a source, artifact, or stream is not runnable;
- how to recover from common configuration and repository failures.

Field-level tooltips and CLI `--help` output are useful but insufficient. They provide local information rather than an end-to-end operating model.

RFI-1 should explain its normal operation directly. AI assistance should remain optional and should not be required to discover or execute ordinary product workflows.

## User Outcome

An operator who has an initialized RFI-1 repository but does not remember the interface should be able to:

1. open Help in a separate, non-modal window or browser tab;
2. keep Help visible while continuing to use the administration interface;
3. navigate directly from the current application page to its relevant help topic;
4. understand the page's purpose, prerequisites, state-changing actions, and normal workflow;
5. follow concrete task procedures without first learning or memorizing the entire product;
6. locate related concepts, troubleshooting information, and command-line equivalents;
7. recover from ordinary configuration, acquisition, revision, import/export, and repository errors.

## Scope

### 1. Repository-Owned Operator Guide

Add a durable operator guide under the repository documentation tree.

The guide must be:

- version controlled with the application;
- usable without external network access;
- written for a capable operator who does not know the implementation history;
- organized primarily by operator tasks and workflows rather than internal modules;
- precise about persisted state, immutable records, side effects, and failure behavior;
- searchable and addressable by stable topic anchors or routes;
- suitable for rendering inside the application help experience;
- readable directly from the repository as Markdown or an equivalent canonical source.

The canonical guide should cover, as applicable to the implemented product:

1. getting started and normal startup;
2. the repository and its principal entities;
3. firms and firm configuration;
4. source profiles and source configuration;
5. source readiness and run eligibility;
6. source retrieval and acquisition results;
7. retained artifacts and artifact inspection;
8. streams and stream configuration;
9. validation and preview;
10. revisions, immutability, lineage, and comparison;
11. execution and result inspection;
12. YAML import and export;
13. repository verification, backup, and restore;
14. common failures and recovery procedures;
15. CLI equivalents and command reference;
16. glossary and cross-references.

Documentation must describe only implemented behavior. Unimplemented or future behavior must not be presented as available.

### 2. Separate Non-Modal Help Window

The administration interface must expose a clearly discoverable Help action.

Invoking Help must:

- open Help in a separate browser window or browser tab;
- leave the main administration interface fully interactive;
- avoid modal dialogs, blocking overlays, and in-page panels that prevent normal operation;
- allow the operator to place Help beside the application or on another monitor;
- permit independent scrolling, navigation, resizing, printing, and browser search;
- preserve unsaved application work;
- avoid requiring a second RFI-1 server process.

The implementation may rely on normal browser window or tab behavior. It must not claim control over browser policies that the application cannot guarantee.

### 3. Context-Sensitive Deep Links

Each major administration page must provide a Help entry that opens or reuses the non-modal Help experience at the topic corresponding to that page.

A context-sensitive topic should explain:

- the purpose of the page;
- when an operator normally uses it;
- prerequisites;
- the typical workflow;
- which actions change repository state;
- which actions do not change repository state;
- where resulting records or artifacts can be inspected;
- common operator mistakes and failure states;
- related pages and concepts;
- CLI equivalents, where applicable.

Deep links must use stable, testable topic identifiers, anchors, or routes. Renaming headings must not silently break application help links.

At minimum, context-sensitive Help must cover every major application area implemented when this task begins, including the areas for:

- firms;
- source profiles or source configuration;
- source pulls or acquisition execution;
- artifacts;
- streams;
- validation and preview;
- revisions;
- YAML import/export;
- repository administration.

### 4. Workflow Procedures

The guide must include concrete procedures that an operator can follow while using the application.

Procedures must be action-oriented and state-aware. They must identify prerequisites, expected results, and meaningful failure branches.

At minimum, include procedures for:

#### Acquisition workflow

```text
Create or select a firm
→ configure its source profile
→ evaluate readiness and run eligibility
→ execute a source pull
→ interpret the result
→ locate and inspect the retained artifact and retrieval record
```

#### Stream workflow

```text
Create or edit a stream draft
→ validate
→ preview normalized behavior
→ inspect meaningful differences
→ save a revision
→ execute the saved revision
→ inspect results, membership, and lineage
→ export canonical YAML
```

#### Import workflow

```text
Select or provide YAML
→ validate without persistence
→ inspect normalization or semantic differences
→ import intentionally
→ verify the resulting saved state
```

#### Repository protection workflow

```text
Identify the active repository
→ verify repository health
→ create a backup
→ restore or validate a restore in the supported manner
→ confirm integrity and expected application access
```

Procedures must distinguish clearly among validation, preview, persistence, execution, and inspection.

### 5. Search and Navigation

The rendered Help experience must provide practical navigation for a manual of this size.

It must include:

- a table of contents or equivalent topic navigation;
- stable links to major sections;
- browser-search-compatible rendered text;
- links among related procedures and concepts;
- a visible way to return to the Help home or contents.

A custom full-text search engine is not required unless the existing application architecture already provides one. The help design must not prevent later addition of indexed search.

### 6. Consistent Topic Structure

Major page-oriented help topics should use a consistent structure so operators learn how to read Help without memorizing the product.

Use the following conceptual pattern where applicable:

1. Purpose
2. When to use this page
3. Prerequisites
4. Typical workflow
5. Controls and actions
6. What changes repository state
7. What does not change repository state
8. Expected results
9. Common problems and recovery
10. Related topics
11. CLI equivalent
12. Advanced notes

The exact visual formatting may vary, but the information model should remain recognizable across topics.

### 7. Documentation-Driven Usability Findings

While documenting actual workflows, record genuine usability defects discovered during the work.

Examples include:

- ambiguous control names;
- hidden prerequisites;
- unclear saved-versus-draft state;
- misleading action labels;
- failures that do not identify corrective action;
- screens that do not expose where output was stored;
- workflows that cannot be described accurately because application state is ambiguous.

This task may correct small defects required to make Help truthful and usable, such as:

- adding Help links;
- correcting misleading labels;
- exposing an already-known state;
- improving a directly relevant error message;
- adding stable topic identifiers.

Broader redesigns must be captured as bounded follow-up work rather than absorbed into this task.

## Required Design Properties

### Help Is a Product Surface

Help is part of the supported application, not an informal README appendix.

The canonical source, rendered experience, application links, and tested workflows must remain consistent.

### Recognition Over Memorization

The system should help an operator recognize the correct action and follow a procedure. It should not assume that the operator remembers earlier sessions or has completed formal training.

### Task Orientation

Lead with what the operator is trying to accomplish. Introduce internal terms only where they are necessary to understand state, provenance, revisions, or consequences.

### Explicit State Semantics

For every significant operation, Help should state whether it:

- reads current state;
- validates proposed state;
- previews normalized or derived state;
- persists a new record;
- creates an immutable revision;
- executes acquisition or stream behavior;
- exports a representation;
- imports and persists a representation;
- modifies, replaces, or leaves existing records unchanged.

### Honest Browser Behavior

The application may request a separate window or tab and may reuse a named Help window where supported.

It must not assert that it can override browser popup policies, force a particular monitor, or guarantee tab-versus-window placement.

### No External Dependency

Normal Help use must not require an external documentation service, public website, AI service, or internet connection.

## Non-Goals

This task does not:

- redesign the entire administration interface;
- add an AI chatbot to Help;
- create an autonomous in-product tutorial agent;
- require onboarding tours, badges, completion scoring, or training analytics;
- document unimplemented roadmap capabilities;
- replace concise CLI `--help` output;
- make Help modal or embed it in a blocking overlay;
- guarantee browser-controlled placement of windows or tabs;
- build a general-purpose documentation platform;
- introduce broad architecture changes unrelated to operator help;
- silently change repository semantics to make documentation easier.

## Acceptance Criteria

### Canonical documentation

- [ ] A canonical, repository-owned operator guide exists.
- [ ] The guide is organized around operator workflows and includes a usable contents structure.
- [ ] The guide covers all major administration areas implemented at task start.
- [ ] The guide distinguishes validation, preview, save, revision creation, execution, import, export, and inspection.
- [ ] The guide describes only behavior verified in the current application.
- [ ] The guide includes acquisition, stream, import, and repository-protection procedures.
- [ ] The guide includes troubleshooting and a glossary.

### Non-modal help experience

- [ ] The administration interface exposes a clearly discoverable Help action.
- [ ] Help opens separately from the main application interface.
- [ ] The main interface remains usable while Help is open.
- [ ] Opening Help does not discard or alter unsaved application state.
- [ ] Help can be independently navigated, scrolled, resized, printed, and searched using ordinary browser capabilities.
- [ ] Help does not depend on internet access or an external documentation server.

### Context sensitivity

- [ ] Every major administration page has a context-sensitive Help entry.
- [ ] Each entry opens the corresponding help topic rather than only the manual home page.
- [ ] Help topic identifiers are stable and validated.
- [ ] Broken or missing page-to-topic mappings are detected by automated validation.
- [ ] Repeated Help invocation has defined and verified behavior, including the supported behavior when the prior Help window or tab remains open.

### Content quality

- [ ] Major page topics identify purpose, prerequisites, workflow, side effects, expected results, and recovery guidance.
- [ ] State-changing actions are distinguished from read-only or preview actions.
- [ ] Procedures identify where resulting records, artifacts, revisions, or execution results can be inspected.
- [ ] Command names, page names, labels, and examples match the implemented application.
- [ ] No documented workflow requires undocumented knowledge to reach its expected result.

### Usability findings

- [ ] Usability defects discovered during documentation are recorded.
- [ ] Small in-scope corrections are explicitly identified in the task report.
- [ ] Larger redesign opportunities are captured separately and are not implemented opportunistically.

## Verification Requirements

Implementation is not complete until a review package demonstrates the behavior from both documentation and application perspectives.

### Automated verification

Provide focused automated coverage for:

- Help route or rendering availability;
- offline/local serving behavior;
- every registered context-help link;
- uniqueness and stability of topic identifiers;
- detection of broken links or missing topics;
- safe handling of unknown help topics;
- preservation of application state when Help is invoked;
- repeated Help invocation behavior;
- representative rendering of headings, procedures, links, and code blocks;
- application startup with Help available;
- existing relevant regression suites.

Where practical, documentation examples that are commands must be checked against the current CLI surface or executed in a safe test environment.

### Browser-level proof

Provide reproducible browser-level evidence showing at least:

1. the main administration interface open;
2. an unsaved or in-progress form state present;
3. context Help invoked from that page;
4. Help visible in a separate non-modal window or tab;
5. the correct deep-linked topic displayed;
6. the original interface still interactive;
7. the in-progress state preserved;
8. navigation to a related workflow topic;
9. repeated invocation behavior;
10. an unknown or invalid topic handled safely.

Browser proof must verify behavior, not merely provide screenshots of static pages.

### Workflow proof

Execute and document representative supported workflows using the guide itself as the procedure:

- one acquisition workflow;
- one stream revision and execution workflow;
- one validation/preview/import or export workflow;
- one repository verification or backup workflow.

Record discrepancies between the guide and actual behavior. Resolve in-scope discrepancies before completion.

### Documentation review

Provide evidence that:

- all major application pages are mapped to help topics;
- terminology is consistent across application, CLI, and guide;
- side-effect statements agree with implementation and tests;
- future or unimplemented capabilities are not represented as current;
- links and anchors pass validation;
- the guide is readable directly as canonical source and through the rendered Help experience.

### Regression verification

Run the repository's complete validation suite and any required application smoke checks.

No pre-existing test may be weakened, deleted, skipped, or rewritten merely to accommodate this task without explicit justification.

## Required Review Package

Produce a complete TASK-027 review package containing at least:

1. task ticket;
2. implementation summary;
3. design and scope notes;
4. changed-file inventory;
5. canonical operator guide;
6. help topic registry or page-to-topic mapping;
7. automated test commands and complete outputs;
8. browser-level verification procedure and results;
9. workflow proof records;
10. screenshots or equivalent visual evidence supporting the non-modal behavior;
11. documentation link and anchor validation output;
12. full regression validation output;
13. usability findings and disposition;
14. known limitations, including browser-controlled window/tab behavior;
15. repository status, branch, and commit evidence as required by the normal workflow;
16. review-package manifest and integrity verification.

The package must be self-contained enough for a reviewer to determine:

- what was implemented;
- why the design satisfies the task;
- which workflows were verified;
- whether Help is genuinely non-modal;
- whether context links are complete and correct;
- whether documentation agrees with application behavior;
- whether regressions were introduced.

## Implementation Constraints

- Preserve existing repository and application semantics unless a change is explicitly required by this ticket.
- Keep the canonical documentation independent from a specific external documentation vendor.
- Prefer stable, explicit topic mappings over fragile heading-text inference.
- Do not duplicate authoritative behavioral rules across multiple sources without a defined synchronization mechanism.
- Do not place the only copy of operational guidance inside application templates or generated assets.
- Generated help output, if any, must be reproducible from repository-owned sources.
- Do not introduce network access into Help rendering.
- Treat documentation errors that could cause unintended state changes or data loss as functional defects.
- Maintain the project's separation between acquisition evidence, repository state, and presentation concerns.

## Completion Standard

TASK-027 is complete only when an operator can open Help beside RFI-1, follow the documented procedures while continuing to manipulate the interface, and successfully complete representative workflows without relying on remembered implementation details or external assistance.

A static Markdown file alone is insufficient.

A Help button that opens only the top of a manual is insufficient.

A modal, blocking overlay, or same-page replacement is insufficient.

Completion requires an integrated, non-modal, context-sensitive, repository-owned operator help system with a complete verification package.
