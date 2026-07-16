# DESIGN_PRINCIPLES.md

# Repository-First Intelligence (RFI) Design Principles

> These are enduring engineering principles, not implementation requirements.
>
> When architecture, implementation, schedule, or convenience are in tension, this document provides the preferred direction for making tradeoffs.

---

# 1. The Repository Is the Primary Product

The repository is the long-lived system of record.

Reports, dashboards, presentations, and interactive conversations are valuable outputs, but they are generated from repository state rather than becoming the repository themselves.

---

# 2. Reports Are Projections

Outputs are projections of repository state at a point in time.

Whenever practical, a projection should be reproducible from the repository and its supporting evidence.

---

# 3. Evidence Precedes Interpretation

Collect and preserve evidence before introducing interpretation.

Architecturally distinguish evidence from observations, observations from derivations, and derivations from claims.

---

# 4. Provenance Is Mandatory

Every meaningful repository object should be traceable to its origin.

A result without provenance is incomplete.

---

# 5. Preserve Immutable Evidence

Source artifacts are durable records.

Knowledge may evolve; evidence should not.

---

# 6. Replay Is a First-Class Capability

The repository should support replay of stored evidence through improved processing pipelines.

Learning should not depend on waiting for external sources to publish again.

---

# 7. Separate Acquisition from Projection

Information acquisition, knowledge development, and information projection are independent architectural concerns.

Coupling them unnecessarily reduces flexibility.

---

# 8. Build from Observed Source Behavior

Architectural abstractions should emerge from real acquisition experience rather than speculation.

Prefer evidence over anticipation.

---

# 9. Development Acceleration Is Acceptable; Architectural Dependency Is Not

Commercial APIs, AI services, and helper libraries may accelerate development.

They should remain replaceable behind stable repository contracts.

---

# 10. Deterministic Acquisition Before AI Reasoning

Routine acquisition should rely on explicit contracts, deterministic software, and governed source profiles.

Use AI where it adds value, not where conventional engineering is more reliable.

---

# 11. Prefer Stable Identity

Repository relationships should be based on stable internal identifiers.

Treat filenames, URLs, page layouts, and provider-specific identifiers as external attributes rather than primary identity.

---

# 12. Preserve Architectural Optionality

Delay decisions that can be informed by operational evidence.

Do not postpone decisions required to preserve provenance, replayability, or repository integrity.

---

# 13. Optimize for Understanding

Choose designs that make the repository easier to understand, inspect, debug, and explain.

Simple, explicit models generally outlast clever ones.

---

# 14. Let the Repository Teach the Architecture

The first implementation is expected to reveal assumptions that are wrong.

The architecture should improve through observation of the repository, the publishers, and operational experience rather than adherence to an initial design.

---

# Using These Principles

These principles are intentionally stable.

Implementation guidance, task tickets, APIs, technologies, and data models will evolve.

When making tradeoffs, prefer the option that best aligns with these principles, even if it is not the shortest path to the next feature.
