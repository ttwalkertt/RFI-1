# Configuration-only exclusion proof

The source state in `tests/test_task038.py` deliberately contains artifact and derived operational
state before export. Fixture acquisition and stream execution populate evidence, mailing-list, and
stream materialization tables. After import into a fresh state, the proof requires zero rows in:

- `artifacts`
- `acquisition_attempts`
- `mailing_list_runs`
- `mailing_list_fetch_history`
- `artifact_stream_projections`
- `artifact_stream_runs`
- `artifact_stream_memberships`
- `mailing_list_message_conflicts`
- `mailing_list_discussions`

The deterministic export test also rejects evidence artifact identity (`artifact-`), run identity,
coverage, conflict identity, projection fields, and the original absolute state path in serialized
YAML. No SQLite database, content object, artifact bytes, document records, hashes, observations,
checkpoints, queue events, coverage, projections, memberships, discussions, conflicts, or run
history is included in the review package's example contract or transferred by import.

Canonical artifact-family keys inside firm source profiles are configuration vocabulary owned by
the acquisition template; they are not content-addressed evidence artifact IDs.

The executable source for these assertions and the focused validation result are included in the
archive.
