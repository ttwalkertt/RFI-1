# ADR-0008: Durable consulting workspace and append-only execution journal

- Status: accepted
- Scope: TASK-008

## Context

TASK-007 produces bounded, inspectable intelligence records but deliberately does not retain
long-lived investigations. Consulting operators need to revisit questions, see exactly what ran,
separate their own interpretation from repository and model authorities, compare reruns, and move
or recover their work without turning a workflow store into a competing evidence repository.

## Decision

Create `rfi.workspace` as the first operator-product layer. It depends on the public TASK-007
executor and record contracts only. Represent every investigation mutation, execution start,
terminal outcome, annotation, and export as an immutable JSON event in a sequence-numbered,
SHA-256 hash chain. Derive current investigation views from events instead of maintaining mutable
records. Record execution intent before invocation so interruption remains visible.

Persist a frozen reference projection of each public intelligence record. The projection retains
the plan, queries, trace and package identities, authority fingerprint, exact source/derived
object and artifact/span/digest references, claim mappings, conclusions, uncertainty, failures,
and metrics. It deliberately omits source context text, model input, and raw model output. These
snapshots make old executions intelligible but are explicitly non-authoritative; evidence,
knowledge, retrieval state, and intelligence results remain owned by their existing subsystems.

Use semantic rerun comparison over question, configuration, plan, retrieval traces, referenced
evidence objects, claims, conclusions, status, and metric deltas. Export Markdown with a JSON
provenance/claim appendix. Back up the independently contained workspace as a ZIP with a complete
size-and-SHA-256 manifest; verify before publication and restore through verified staging.

Retain committed journal events indefinitely. Quarantine uncommitted partial files without
changing the committed chain. Keep structured diagnostics transient and redact likely credential
fields. Expose the same contracts through a scriptable JSON console rather than introducing a GUI
or database dependency for the POC.

## Consequences and tradeoffs

History is portable, inspectable with ordinary tools, recoverable after interruption, and hard to
rewrite accidentally. Event projections avoid mutable migration coupling, but listing a large
workspace requires replay and concurrent writers are not supported. Hash chaining detects
tampering but is not a signature against a malicious actor who can rewrite the whole workspace.

Reference snapshots duplicate public identifiers and result semantics intentionally. They do not
prove upstream objects still exist; missing evidence is visible during later inspection or rerun
and old journal meaning remains intact. Omitting source/model content reduces disclosure and backup
size, but a historical execution cannot be replayed solely from the workspace when upstream
authorities have been removed.

## Alternatives considered

- A shared database with retrieval and intelligence tables was rejected because it would couple
  workspace lifecycle to non-authoritative index and provider implementations.
- Mutable investigation and execution rows were rejected because correction and recovery history
  would be overwriteable.
- Full copies of evidence contexts were rejected because the workspace must reference, not own,
  immutable evidence and because unnecessary source content increases disclosure risk.
- Log files as the journal were rejected because diagnostics have different retention, secrecy,
  and integrity needs from durable business history.
- A GUI was deferred because stable product contracts and a complete operator workflow are the
  milestone; multi-user presentation is a separate concern.

## Proof limits

The proof establishes a single-operator local workspace, append-only integrity, deterministic
fixture consulting lifecycle, rerun comparison, metrics, export, backup/restore, and broad failure
visibility. It does not establish concurrent writers, cryptographic signing, authentication,
multi-user collaboration, scheduling, cloud durability, large-workspace query performance, live
frontier-model quality, or automatic upstream evidence availability.
