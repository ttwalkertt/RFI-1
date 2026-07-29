Concept of Operation

The acquisition subsystem consists of independent document-type acquisition packages, beginning with 1 Earnings Calls and 2 Press Releases. Each package is responsible for locating, evaluating, and retrieving a specific class of public documents for an explicitly requested target, such as an issuer and fiscal period or an issuer and publication date range. Acquisition packages may employ deterministic provider logic, bounded search, or future reasoning-assisted methods to locate candidate documents, but they always return the same typed acquisition result containing the retrieved payload, transport evidence, provenance, and acquisition outcome. They do not persist repository state, assign canonical identities, or make retention decisions.

The repository invokes an acquisition package by supplying an acquisition target and optional bounded historical retrieval context (hints) derived from prior successful acquisitions. The target may identify a single reporting period, an arbitrary historical range, or a focused analytical window. Historical retrieval context serves only as advisory evidence to improve discovery efficiency—for example, by indicating prior successful providers or URL patterns—and never establishes truth or bypasses validation. Every acquisition request is independently auditable and replayable from its retained inputs and evidence. Nondeterministic discovery is not required during replay because the retained search observations and acquisition evidence become the authoritative record of how the artifact was acquired.

Acquisition packages may use deterministic provider logic, bounded web search, or nondeterministic LLM-assisted discovery and candidate reasoning to locate potential documents. Such methods are advisory and may produce different candidate sets across runs. Regardless of the discovery method used, the package must preserve the search inputs, bounded historical context, method and model configuration, candidate evidence, ranking rationale, and selected retrieval path in the returned provenance. Retrieval, payload validation, and construction of the typed acquisition result remain governed by explicit contracts, and the package does not treat an LLM-selected candidate as canonical truth.

Upon completion, the acquisition package returns an immutable acquisition result to the repository caller through a stable ingestion contract. The repository caller alone determines canonical identity, conflict resolution, artifact organization, provenance persistence, indexing, and repository policy. As additional document-type acquisition packages are developed, only the contracts and mechanisms demonstrated to be semantically equivalent across independent implementations are extracted into shared infrastructure. This allows the architecture to evolve from proven operational experience rather than speculative generalization while preserving a clean separation between external acquisition and internal repository management.

We define one tiny shared contracts package before writing either vertical—not because we know the framework yet, but because there are a few concepts that are almost certainly universal:
* RetrievedPayload
* ContentHash
* TransportMetadata
* AcquisitionOutcome

Since the earnings call transcript and Press Release retrievers are stand-alone dedicated adapters, we use desctiptive names (not generic framework names) e.g.
earnings_call_acquisition
* find_candidate_transcript(...)
* rank_transcript_candidates(...)
* retrieve_transcript(...)
* validate_transcript(...)

The first implementation should be narrow:
issuer + fiscal period
        ↓
bounded search
        ↓
candidate assessment
        ↓
one selected retrieval
        ↓
typed earnings-call result