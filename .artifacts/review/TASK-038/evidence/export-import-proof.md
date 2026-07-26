# Export and import contract proof

Authoritative implementation evidence is included in the archive as
`src/rfi/storage/configuration.py` and `src/rfi/cli.py`. Executable acceptance evidence is included
as `tests/test_task038.py`.

## Export

- Opens only initialized, compatible repository state.
- Reads current effective firms, source profiles, mailing-list sources, SEC identities, and streams.
- Removes revision IDs and timestamps that belong to revision history rather than current intent.
- Emits human-readable YAML with `format: rfi-config` and independent `version: 1`.
- Orders every category by stable domain identity, producing byte-identical repeated exports.
- Does not read or package content-store bytes.

## Import

- Refuses missing, uninitialized, legacy, or incompatible target state through repository-owned
  current-schema checks.
- Parses and structurally validates the complete YAML before target mutation.
- Reconstructs the package through public domain repositories in an isolated current-schema staging
  repository, validating firm metadata, source-profile policy, source transport policy, SEC
  relationships, stream schemas, and stream dependency order.
- Compares existing and incoming configuration through stable firm, source, canonical
  artifact-family, and stream identities.
- Rejects materially different target configuration with an actionable conflict.
- Copies only missing, already validated configuration within one target transaction.
- Advances repository revision only when configuration was created.
- Returns zero created counts on exact re-import.

Focused tests cover deterministic output, CLI workflow, initialized/current-schema enforcement,
malformed/version rejection, conflict/no-mutation behavior, late validation failure, transactional
rollback, and idempotent repetition.
