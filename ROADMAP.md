# ROADMAP.md

# Repository-First Intelligence (RFI) Roadmap

> This roadmap communicates the intended direction of the project.
>
> It is intentionally lightweight and is **not** a project plan or a commitment.
> Implementation will be guided by experience gained in each preceding phase.
>
> Unscheduled candidates belong in `BACKLOG.md`. Authorized implementation work belongs in
> `TASKS.md` and its governing task tickets.

---

# Phase 0 — Acquisition POC (Current)

Objective:

Establish a trustworthy acquisition substrate.

Focus areas:

- Source Registry
- Deterministic source profiles
- Acquisition engine
- Immutable artifact storage
- Append-only retrieval ledger
- Rebuildable document index
- Replay capability
- Initial commercial SEC provider evaluation
- Initial direct Investor Relations retrievers

Success is measured by reliable acquisition and replay rather than downstream intelligence.

Storage direction after TASK-020: migrate authoritative structured state to an explicit hybrid
SQLite/file architecture only through a separately authorized milestone. Exact artifact bytes
remain content-addressed filesystem evidence. The migration must preserve public contracts, use
offline reconciliation and one authority cutover, and prove backup/restore and rollback. A server
database remains trigger-driven rather than a current prerequisite.

---

# Phase 1 — Observations

Transform source artifacts into explicit observations.

Potential capabilities:

- text extraction
- document segmentation
- observation records
- evidence references
- observation provenance
- confidence where appropriate

Primary goal:

Represent what the evidence says without introducing interpretation.

---

# Phase 2 — Derivations

Compute reproducible knowledge from observations.

Potential capabilities:

- calculations
- rankings
- timelines
- trends
- comparisons
- consistency checks

Primary goal:

Generate deterministic knowledge that can always be reproduced from repository state.

---

# Phase 3 — Enrichments

Attach additional semantic structure to repository objects.

Potential capabilities:

- classifications
- technology taxonomy
- market segments
- entity relationships
- cross-document linking
- AI-assisted tagging

Primary goal:

Improve organization and retrieval while preserving provenance.

---

# Phase 4 — Claims

Develop evidence-backed assertions.

Potential capabilities:

- claim lifecycle
- supporting evidence
- confidence
- review workflow
- contradiction detection

Primary goal:

Represent reasoned conclusions while remaining traceable to supporting evidence.

---

# Phase 5 — Positions

Develop higher-level viewpoints from multiple claims.

Examples:

- competitive assessments
- technology outlooks
- market interpretations
- strategic analyses

Primary goal:

Capture the repository's current understanding while preserving the underlying evidence chain.

---

# Phase 6 — Projections

Generate consumable outputs.

Potential capabilities:

- consulting briefs
- research reports
- dashboards
- presentations
- interactive question answering
- social media content

Primary goal:

Produce high-quality outputs from repository state without embedding business logic in the acquisition layer.

---

# Future Exploration

Possible future areas include:

- exploratory web-search scouts
- multi-provider reconciliation
- knowledge graph support
- agent-assisted enrichment
- citation-aware report generation
- domain-specific RFI implementations
- collaborative review workflows
- repository health metrics
- long-term knowledge evolution

These items are intentionally exploratory and should not influence near-term architectural decisions.

---

# Guiding Principle

The roadmap is expected to evolve.

The architectural principles are intended to remain comparatively stable, while implementation priorities should be driven by operational experience and evidence gathered during each preceding phase.
