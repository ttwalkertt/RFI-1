# TASK-029 --- Simplify Linux Mailing List Stream Operations

## Objective

This task is **explicitly focused on simplifying the operator experience
for managing and running Linux mailing-list intelligence streams.**

The current implementation is functionally correct, but it requires the
operator to interact with configuration and acquisition controls more
often than necessary. This task shifts the page toward an
operations-first workflow where the common activities are:

-   selecting an existing stream;
-   understanding its current state;
-   updating its configuration only when necessary; and
-   keeping acquisition current with minimal effort.

Throughout this implementation, **prefer modern usability standards**.
Favor progressive disclosure, clear operator feedback, obvious primary
actions, consistent interaction patterns, minimal cognitive load, and
interfaces that make the correct action the easiest action. Preserve
existing repository guarantees while improving usability.

------------------------------------------------------------------------

# Scope

Implement these changes **only** on the **Linux Mailing Lists** page.

Do **not** modify the separate **Streams** tab.

The current page combines saved-stream selection, editing, acquisition
execution, and evidence viewing in a single workflow. Convert it into
two primary modes:

1.  **Stream Summary Mode** (default)
2.  **Stream Editor Mode** (entered explicitly)

------------------------------------------------------------------------

# Requirements

## 1. Stream Summary Mode

When an existing stream is selected, show a concise, human-friendly
summary instead of immediately opening the editor.

Include at least:

-   stream name
-   description
-   mailing list/source
-   configured relevance criteria
-   configured acquisition limits
-   effective last-fetch date
-   latest acquisition result
-   indication of partial/incomplete/truncated outcomes when applicable

Provide an **Edit** button.

Selecting **Edit** opens the existing editor.

------------------------------------------------------------------------

## 2. Stream Editor Mode

Reuse the current editor.

After Save:

-   persist the authoritative revision
-   display a modal information dialog confirming success

Do not rely only on a transient status message.

------------------------------------------------------------------------

## 3. Stream Cards

Each saved stream card must display:

-   effective last-fetch date
-   Fetch up to date action

The effective last-fetch date represents repository acquisition
coverage, not merely when the last fetch finished.

------------------------------------------------------------------------

## 4. Fetch Up To Date

Run acquisition beginning with a deterministic 1--2 day overlap before
the effective last-fetch date and ending at today.

Honor existing source acquisition limits (including Lore's bounded
acquisition window). If necessary, perform multiple bounded windows.

------------------------------------------------------------------------

## 5. Queue

Create a simple process-local FIFO queue.

Requirements:

-   asynchronous from UI
-   one fetch at a time (unless existing implementation safely supports
    more)
-   duplicate suppression
-   queued/running/completed/failed/cancelled state
-   minimal implementation

Do not build a general scheduling framework.

------------------------------------------------------------------------

## 6. Sidebar Controls

Add:

-   Fetch All up to date
-   Cancel / Abandon all Fetches

Fetch All queues every eligible stream.

Cancel / Abandon:

-   removes queued work
-   requests cancellation of running work
-   leaves durable evidence intact

No per-stream removal is required.

------------------------------------------------------------------------

## 7. Status Area

Add a bounded operator status panel at the bottom showing:

-   queued
-   duplicate ignored
-   started
-   completed
-   failed
-   cancellation requested
-   abandoned
-   cancelled

This is operational status, not permanent audit history.

------------------------------------------------------------------------

## 8. API

Provide endpoints for:

-   queue one stream
-   queue all streams
-   cancel/abandon all
-   inspect queue/status

Endpoints must return immediately after enqueueing.

Document curl examples.

------------------------------------------------------------------------

# Constraints

-   Do not modify the Streams tab.
-   Preserve immutable evidence.
-   Preserve bounded acquisition.
-   Preserve existing partial/incomplete semantics.
-   Preserve the retained Fixes header.
-   Preserve independently scrollable message display.

------------------------------------------------------------------------

# Design Notes

Document:

1.  effective last-fetch derivation
2.  overlap policy
3.  multi-window catch-up
4.  duplicate suppression
5.  cancellation checkpoints
6.  restart behavior
7.  status retention
8.  browser update mechanism

------------------------------------------------------------------------

# Verification Package

Include:

-   design summary
-   changed files
-   API documentation
-   focused tests
-   full validation
-   queue ordering proof
-   duplicate suppression proof
-   fetch-all proof
-   bounded acquisition proof
-   cancellation proof
-   restart proof
-   effective last-fetch proof
-   save-modal proof
-   screenshots of summary mode, editor mode, queue, status area,
    sidebar controls
-   live API evidence
-   regression evidence confirming the Streams tab was not modified

Do not commit, merge, push, or clean the branch.

------------------------------------------------------------------------

# UI Polish Follow-up

The follow-up refinement is limited to the Stream Summary pane, saved-stream cards, and
operator-facing repository-coverage wording. It improves hierarchy, selected-state visibility,
health and coverage comprehension, and adds a concise last-acquisition summary before retained
evidence. Retained evidence is collapsed by default and remains independently scrollable when
expanded.

This refinement does not authorize changes to acquisition behavior, the fetch queue, editor or
save workflows, APIs, the separate Streams page, repository semantics, immutable evidence, or
bounded acquisition.
