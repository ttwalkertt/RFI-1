# ADR 0024: Split Acquisition Batch and Connected-Component Publication Policy

## Status

Accepted for TASK-039.

## Context

Canonical stream configuration exposes `bounds.total_artifacts`. Lore workflow configuration maps
that field to the legacy internal `expanded_limit` key and uses it to calculate the bounded number
of seed plus context artifacts retained by one acquisition run. TASK-031 made relationship
acquisition resumable, so a complete discussion can legitimately be larger than one such run.

The connected-discussion projection also treated the same value as a ceiling on the completed
component. That rejected valid, fully acquired discussions even though membership publication was
already transactional.

## Decision

`bounds.total_artifacts` remains the acquisition-batch allowance. Existing canonical YAML, saved
revision JSON, workflow drafts, and operator inputs therefore translate deterministically without a
repository migration. The legacy internal key remains readable and writable for compatibility.

Connected-discussion publication has a different policy: every complete selected connected
component is included in the publication plan regardless of the number of acquisition batches that
produced it. The existing stream-repository transaction publishes the plan, memberships, lineage,
and successful run state together. Any failure rolls the transaction back, so no partial component
becomes visible.

The publication policy is explicitly component-integrity-based, not accidentally unlimited. It
first rejects incomplete or quarantined component projections and then admits the complete
component as one plan. A second finite artifact count was rejected because it would reproduce the
same corpus-size failure at a different threshold and contradict the requirement that batch count
must not determine publishability. Transactional rollback bounds failure exposure, and paginated
membership reads bound delivery. Durable/paged plan construction would be the appropriate future
safety mechanism if production component sizes require it, but would require repository work beyond
this no-migration milestone.

The existing `seed_limit` still bounds direct selection. Acquisition provider calls, continuation
manifests, and Lore relationship semantics are unchanged. Membership delivery remains paginated and
does not impose a publication ceiling.

## Consequences

- Raising `expanded_limit` is unnecessary and is not the solution.
- Memory required to construct one publication plan can grow with a completed component; durable
  paginated planning is deferred because this ticket requires no repository migration.
- Non-connected projections retain their existing direct-selection behavior.
