# Repository-First Intelligence (RFI)

## A Working Manifesto

Repository-First Intelligence (RFI) is an architectural pattern for building AI systems whose primary product is a persistent, evidence-backed knowledge repository rather than a transient report or conversation.

The repository accumulates immutable evidence, explicit provenance, and structured knowledge over time. Reports, analyses, consulting briefs, and interactive question answering are projections derived from repository state.

Acquisition and projection are intentionally independent and asynchronous. Information enters the repository through governed acquisition processes and is later consumed by downstream processes without coupling to the timing or mechanics of the original sources.

## Core Principles

- Evidence before interpretation.
- Provenance before assertion.
- Deterministic acquisition before AI reasoning.
- Persistent knowledge before transient output.
- Evolution guided by observed behavior rather than speculative design.

Commercial services, AI models, and retrieval technologies are implementation choices rather than architectural dependencies. They may accelerate development, but they do not define repository semantics or own repository identity.

**The repository becomes the durable foundation for information ingress, knowledge development, and downstream outputs.**

RFI is intended to support domains where understanding compounds over time: engineering, competitive intelligence, scientific research, medicine, law, finance, standards, and other evidence-driven disciplines. The architecture is domain-independent; only the sources, taxonomies, and projections change.

This manifesto is intentionally pragmatic. It describes an engineering philosophy rather than a product, implementation, or standard. It should evolve as experience and evidence improve the architecture.
