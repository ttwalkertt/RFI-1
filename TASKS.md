# RFI-1 task index

This file records authorized architectural milestones and their current repository status. A task
ticket defines its scope, invariants, acceptance criteria, and evidence requirements. The
repository-wide operating model is
[`docs/framework-task-operating-model.md`](docs/framework-task-operating-model.md).

## How to interpret status

- **Ready:** authorized but not demonstrated complete.
- **Complete:** the bounded milestone has implementation and accepted evidence. It may still be a
  POC, narrow, or absent from the operating product.
- **Implemented POC:** complete public contracts and executable evidence exist, but the stable
  application does not compose the subsystem.
- **Blocked:** implementation exists, but a known acceptance condition prevents supported
  operation.

This index is the current status authority. Some early tickets retain `Ready` in their original
header even though later committed implementation, tests, and review evidence completed the task;
those headers are historical planning residue. Do not rewrite a completed task's original scope to
make it describe later work.

Task numbers are historical identifiers, not a gap-free sequence. Two unrelated tickets were
issued as TASK-058; cite their titles or filenames. TASK-048A and TASK-048B are distinct follow-on
milestones.

## Current milestone

| Task | Architectural milestone | Current status |
|---|---|---|
| [TASK-068](tasks/TASK-068_Reconcile_Repository_Design_Guidance_and_Current_Architectural_State.md) | Reconcile repository design guidance and current architectural state | Complete |

## Historical and authorized milestones

| Task | Architectural milestone | Current status |
|---|---|---|
| [TASK-001](tasks/TASK-001.md) | Repository foundation and authoritative design baseline | Complete |
| [TASK-002](tasks/TASK-002.md) | Immutable acquisition substrate and repository-owned evidence contracts | Complete |
| [TASK-003](tasks/TASK-003.md) | Deterministic acquisition engine and provider adapter boundary | Complete |
| [TASK-004](tasks/TASK-004.md) | First live SEC acquisition and provider-independent evidence corpus | Complete; live access remains operator-gated |
| [TASK-005](tasks/TASK-005-independent-source-object-and-derived-knowledge-subsystems.md) | Independent source-object and derived-knowledge subsystems | Implemented POC |
| [TASK-006](tasks/TASK-006-governed-retrieval-evidence-assembly-and-source-browser.md) | Governed retrieval, evidence assembly, and source-browser contracts | Implemented POC; retrieval quality provisional |
| [TASK-007](tasks/TASK-007-model-guided-retrieval-planning-and-source-grounded-intelligence.md) | Bounded model-guided planning and source-grounded intelligence | Implemented POC; deterministic model substitutes |
| [TASK-008](tasks/TASK-008-consulting-workspace-execution-journal-and-operational-hardening.md) | Consulting workspace and execution journal | Implemented POC; not product-composed |
| [TASK-009](tasks/TASK-009-extensible-business-concept-catalog-and-admin-console.md) | Extensible business concept catalog and local admin console | Complete |
| [TASK-010](tasks/TASK-010-GUI_Editor_updates.md) | Schema-aware concept editor and admin usability | Complete |
| [TASK-011](tasks/TASK-011-target-firm-catalog-browser-and-admin-editor.md) | Target-firm catalog, browser, and editor | Complete |
| [TASK-012](tasks/TASK-012-stable-application-cli-and-operator-help.md) | Stable application CLI and operator help | Complete |
| [TASK-013](tasks/TASK-013-external-catalog-import.md) | External target-firm catalog import | Complete |
| [TASK-014](tasks/TASK-014-firm-source-profiles-and-acquisition-template.md) | Firm source profiles and canonical acquisition template | Complete |
| [TASK-015](tasks/TASK-015-pull-workflow.md) | Pull Workflow shared by GUI, CLI, and REST | Complete |
| [TASK-016](tasks/TASK-016-deterministic-sec-10k-retrieval.md) | Deterministic SEC Form 10-K vertical slice | Complete |
| [TASK-017](tasks/TASK-017-admin-preference-store.md) | Browser-local admin preference store | Complete |
| [TASK-018](tasks/TASK-018-artifact-query-service-and-browser-revised.md) | Repository-owned artifact query and read-only browser | Complete |
| [TASK-019](tasks/TASK-019-multiple-artifact-observations.md) | Multiple immutable artifact observations | Complete |
| [TASK-020](tasks/TASK-020-structured-repository-storage-architecture-review.md) | Structured storage architecture review | Complete; recommendation implemented by TASK-021 |
| [TASK-021](tasks/TASK-021-sqlite-structured-state-repository-foundation.md) | SQLite structured-state repository foundation | Complete |
| [TASK-022](tasks/TASK-022-additional-sec-numbered-form-adapters.md) | Form 10-Q, 8-K, 20-F, and 6-K adapters | Complete |
| [TASK-023](tasks/TASK-023-linux-kernel-mailing-list-intelligence-stream.md) | Bounded Linux kernel mailing-list evidence stream | Complete |
| [TASK-024](tasks/TASK-024-pull-result-configuration-repair-navigation.md) | Pull-result configuration repair navigation | Complete |
| [TASK-025](tasks/TASK-025-revisioned-multilevel-artifact-streams-and-configuration.md) | Revisioned multi-level artifact streams | Complete |
| [TASK-026](tasks/TASK-026-usable-stream-configuration-and-canonical-yaml.md) | Canonical stream YAML and usable configuration | Complete |
| [TASK-027](tasks/TASK-027-non-modal-operator-help-system-and-workflow-guide.md) | Non-modal help system and workflow guide | Complete |
| [TASK-028](tasks/TASK-028-linux-kernel-mailing-list-stream-workflow.md) | Linux mailing-list workflow façade | Complete |
| [TASK-029](tasks/TASK-029-Simplify-Linux-Mailing-List-Operator-Workflow.md) | Simplified mailing-list operator workflow | Complete |
| [TASK-030](tasks/TASK-030-confirmed-unavailable-mailing-list-ancestor-tombstones.md) | Confirmed-unavailable ancestor tombstones | Complete |
| [TASK-031](tasks/TASK-031-resumable-lore-relationship-acquisition.md) | Resumable Lore relationship acquisition | Complete |
| [TASK-032](tasks/TASK-032-process-local-fetch-queue-progress-history.md) | Process-local fetch progress and durable bounded history | Complete |
| [TASK-033](tasks/TASK-033-acquisition-history.md) | Compact acquisition-history presentation | Ready |
| [TASK-035](tasks/TASK-035-canonical-mailing-list-message-identity-and-observation-slice.md) | Canonical mailing-list identity and observation slice | Complete |
| [TASK-036](tasks/TASK-036-sec-authoritative-retrieval-workflow.md) | Authoritative SEC retrieval workflow | Complete |
| [TASK-037](tasks/TASK-037-message-id-conflict-quarantine.md) | Message-ID conflict quarantine | Complete |
| [TASK-038](tasks/TASK-038-configuration-backup-and-restore-for-rbf-resets.md) | Configuration backup and restore | Complete |
| [TASK-039](tasks/TASK-039-split-acquisition-batch-and-publication-limits.md) | Separate acquisition-batch and stream-publication limits | Complete |
| [TASK-040](tasks/TASK-040-Seeded-SEC-Firm-Identity-and-Automatic-Retrieval-Candidate-Synthesis.md) | Seeded SEC identity and candidate synthesis | Complete |
| [TASK-041](tasks/TASK-041-external-firm-configuration-materialization.md) | External firm-configuration materialization | Complete |
| [TASK-044](tasks/TASK-044-Consolidate-Firm-Browser.md) | Consolidated firm browser | Complete |
| [TASK-045](tasks/TASK-045-source-scoped-mailing-list-observations-and-canonical-cross-list-lineage.md) | Source-scoped mailing-list observations and cross-list lineage | Complete |
| [TASK-046](<tasks/TASK-046 — Remove External Sources Opera.md>) | Remove obsolete External Sources operator screen | Complete |
| [TASK-047](<tasks/TASK-047 — Define the Date-Delimited Acq.md>) | Shared date-delimited acquisition contract | Complete |
| [TASK-048](<tasks/TASK-048 — Acquire Earnings-Call Transcr.md>) | Official earnings-call transcript acquisition | Complete |
| [TASK-048A](<tasks/TASK-048A - Wire Transcript Acquisition into Pull Sources.md>) | Wire transcript acquisition into Pull Sources | Complete |
| [TASK-048B](tasks/TASK-048B-source-profile-startup-compatibility.md) | Restore source-profile digest/startup compatibility | Complete |
| [TASK-049](<tasks/TASK-049 — Acquire Official Press Releases.md>) | Official press-release acquisition | Ready; TASK-066 is only a blocked WDC slice |
| [TASK-050](<tasks/TASK-050 - Make Review Package Generation Commit-Aware.md>) | Commit-aware review-package generation | Complete |
| [TASK-051](tasks/TASK-051-preserve-indeterminate-coverage-in-pull-workflow-outcomes.md) | Preserve indeterminate Pull Workflow coverage | Complete |
| [TASK-052](tasks/TASK-052-restore-configured-discovery-hints-for-transcript-retrieval.md) | Restore transcript discovery hints | Complete |
| [TASK-053](tasks/TASK-053-apply-link-traversal-budget-after-eligibility-filtering.md) | Apply transcript traversal budget after eligibility | Complete |
| [TASK-054](tasks/TASK-054-reload-externally-managed-firm-profiles.md) | Reload externally managed firm profiles | Complete |
| [TASK-055](tasks/TASK-055-detect-unimported-external-firm-configuration-v2.md) | Detect unimported external firm configuration | Complete |
| [TASK-056](tasks/TASK-056-persistent-discovery-anchor-history.md) | Persistent transcript discovery-anchor history | Complete |
| [TASK-057](tasks/TASK-057-harden-transcript-discovery-traversal-and-diagnostics.md) | Harden transcript discovery traversal and diagnostics | Complete |
| [TASK-058 — orchestration](tasks/TASK-058-Externalize-Transcript-Acquisition-Orchestration.md) | Externalize transcript acquisition orchestration | Complete |
| [TASK-058 — progress](tasks/TASK-058-pull-workflow-progress-feedback.md) | Pull Workflow progress feedback | Complete |
| [TASK-059](tasks/TASK-059-Add-Explicit-Transcript-Acquisition-Selection-Criteria.md) | Explicit transcript acquisition selection | Complete |
| [TASK-060](tasks/TASK-060-Add-Seed-Injection-Transcript-Acquisition-API.md) | Transcript seed-injection API | Complete |
| [TASK-061](tasks/TASK-061-Add-Transcript-Learning-Inspection-API.md) | Transcript learning inspection API | Complete |
| [TASK-062](tasks/TASK-062-Separate-Candidate-Identity-from-Discovery-Occurrence.md) | Separate candidate identity from discovery occurrence | Complete |
| [TASK-063](tasks/TASK-063-Bounded-Transcript-Resolution-Session.md) | Bounded transcript resolution session | Complete |
| [TASK-064](tasks/TASK-064-Dedicated-StockAnalysis-Transcript-Provider-Adapter.md) | Dedicated StockAnalysis transcript provider | Complete with provider-specific limitations |
| [TASK-065](tasks/TASK-065-Require-Explicit-Transcript-Provider-for-Seed-Injection.md) | Explicit provider dispatch for seed injection | Complete |
| [TASK-066](tasks/TASK-066-Western-Digital-BusinessWire-Press-Release-Adapter.md) | WDC Business Wire press-release adapter | Implemented, operationally blocked by transport viability |
| [TASK-067](tasks/TASK-067-repository-owned-feed-sources.md) | Repository-owned feed sources and feed-driven acquisition | Complete |

## Governing progression

The conceptual dependency remains:

```text
Acquisition -> immutable evidence -> source objects -> derived knowledge
            -> governed retrieval -> grounded intelligence -> consulting workflows
```

Implementation now exists at every stage, but only acquisition/evidence and operational
projections are composed into the stable application. Use
[`docs/current-state.md`](docs/current-state.md) for that distinction and
[`ROADMAP.md`](ROADMAP.md) for the actual remaining frontier.
