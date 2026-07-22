"""Authoritative SQLite foundation for RFI structured runtime state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

DATABASE_NAME = "repository.sqlite3"
SCHEMA_VERSION = 5
BUSY_TIMEOUT_MS = 5_000
_COMPONENT_DIRECTORIES = {
    "firm-catalog",
    "source-profiles",
    "acquisition",
    "pull-workflows",
    "firms",
    "profiles",
}


class StorageError(RuntimeError):
    """Sanitized structured-state initialization or access failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _ClosingConnection(sqlite3.Connection):
    """Make ``with connect()`` both finalize and close short-lived connections."""

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        result = super().__exit__(exc_type, exc, traceback)
        self.close()
        return result


def canonical_json(value: Any) -> str:
    """Encode deterministic JSON for immutable row comparison."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def state_root_for(component_root: Path) -> Path:
    """Resolve legacy constructor roots onto one application SQLite authority."""
    return (
        component_root.parent
        if component_root.name in _COMPONENT_DIRECTORIES
        else component_root
    )


_SCHEMA = """
CREATE TABLE schema_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL,
    applied_at TEXT NOT NULL,
    schema_name TEXT NOT NULL CHECK (schema_name = 'rfi-structured-state')
) STRICT;
CREATE TABLE repository_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    repository_id TEXT NOT NULL UNIQUE,
    authority_revision INTEGER NOT NULL CHECK (authority_revision >= 0),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE concepts (
    concept_id TEXT PRIMARY KEY,
    current_revision_id TEXT NOT NULL UNIQUE
) STRICT;
CREATE TABLE concept_revisions (
    revision_id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) DEFERRABLE INITIALLY DEFERRED,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    predecessor_id TEXT REFERENCES concept_revisions(revision_id),
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    UNIQUE (concept_id, revision_number)
) STRICT;
CREATE TABLE firms (
    firm_id TEXT PRIMARY KEY,
    current_revision_id TEXT NOT NULL UNIQUE
) STRICT;
CREATE TABLE firm_revisions (
    revision_id TEXT PRIMARY KEY,
    firm_id TEXT NOT NULL REFERENCES firms(firm_id) DEFERRABLE INITIALLY DEFERRED,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    predecessor_id TEXT REFERENCES firm_revisions(revision_id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    UNIQUE (firm_id, revision_number)
) STRICT;
CREATE TABLE firm_identifiers (
    revision_id TEXT NOT NULL REFERENCES firm_revisions(revision_id),
    kind TEXT NOT NULL,
    market TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (revision_id, kind, market, value)
) STRICT;
CREATE TABLE firm_domains (
    revision_id TEXT NOT NULL REFERENCES firm_revisions(revision_id),
    domain TEXT NOT NULL,
    PRIMARY KEY (revision_id, domain)
) STRICT;
CREATE TABLE source_profiles (
    firm_id TEXT PRIMARY KEY REFERENCES firms(firm_id),
    current_revision_id TEXT NOT NULL UNIQUE
) STRICT;
CREATE TABLE source_profile_revisions (
    revision_id TEXT PRIMARY KEY,
    firm_id TEXT NOT NULL REFERENCES firms(firm_id),
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    predecessor_id TEXT REFERENCES source_profile_revisions(revision_id),
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    UNIQUE (firm_id, revision_number)
) STRICT;
CREATE TABLE source_profile_items (
    revision_id TEXT NOT NULL REFERENCES source_profile_revisions(revision_id),
    artifact_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    operator_notes TEXT NOT NULL,
    PRIMARY KEY (revision_id, artifact_id),
    UNIQUE (revision_id, ordinal)
) STRICT;
CREATE TABLE retrieval_candidates (
    revision_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    priority INTEGER NOT NULL CHECK (priority > 0),
    mode TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    PRIMARY KEY (revision_id, artifact_id, priority),
    FOREIGN KEY (revision_id, artifact_id)
      REFERENCES source_profile_items(revision_id, artifact_id)
) STRICT;
CREATE TABLE governed_sources (
    source_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    mechanism TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE CHECK (length(sha256) = 64),
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    media_type TEXT NOT NULL,
    content_reference TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    current_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    durable_status TEXT NOT NULL CHECK (durable_status = 'durable')
) STRICT;
CREATE TABLE acquisition_attempts (
    attempt_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES governed_sources(source_id),
    candidate_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('success','failed','skipped','duplicate')),
    occurred_at TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    artifact_id TEXT REFERENCES artifacts(artifact_id),
    observation_id TEXT UNIQUE,
    canonical_json TEXT NOT NULL,
    CHECK ((outcome = 'success') = (artifact_id IS NOT NULL))
) STRICT;
CREATE TABLE artifact_observations (
    observation_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES acquisition_attempts(attempt_id)
      DEFERRABLE INITIALLY DEFERRED,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES governed_sources(source_id),
    observed_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE checkpoint_events (
    event_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES governed_sources(source_id),
    attempt_id TEXT NOT NULL REFERENCES acquisition_attempts(attempt_id),
    position TEXT NOT NULL CHECK (position <> ''),
    cursor TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    UNIQUE (source_id, position, cursor)
) STRICT;
CREATE TABLE current_checkpoints (
    source_id TEXT PRIMARY KEY REFERENCES governed_sources(source_id),
    event_id TEXT NOT NULL REFERENCES checkpoint_events(event_id),
    position TEXT NOT NULL CHECK (position <> ''),
    cursor TEXT NOT NULL
) STRICT;
CREATE TABLE pull_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE mailing_list_sources (
    source_id TEXT PRIMARY KEY REFERENCES governed_sources(source_id),
    list_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    archive_base_url TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE mailing_list_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('connected','truncated','incomplete','quarantined')),
    seed_limit INTEGER NOT NULL CHECK (seed_limit > 0),
    context_limit INTEGER NOT NULL CHECK (context_limit > 0),
    seed_count INTEGER NOT NULL CHECK (seed_count >= 0),
    message_count INTEGER NOT NULL CHECK (message_count >= 0),
    canonical_json TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'succeeded' CHECK (lifecycle_status IN
      ('succeeded','partial','retryable_failure','terminal_failure')),
    error_code TEXT,
    retryable INTEGER NOT NULL DEFAULT 0 CHECK (retryable IN (0,1))
) STRICT;
CREATE TABLE mailing_list_run_items (
    run_id TEXT NOT NULL REFERENCES mailing_list_runs(run_id),
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    external_message_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    inclusion_reason TEXT NOT NULL CHECK (inclusion_reason IN
      ('seed_match','explicit_request','ancestor_context','descendant_context',
       'relationship_context')),
    is_seed INTEGER NOT NULL CHECK (is_seed IN (0,1)),
    connectivity_state TEXT NOT NULL CHECK (connectivity_state IN
      ('connected','truncated','incomplete','quarantined')),
    PRIMARY KEY (run_id, external_message_id)
) STRICT;
CREATE TABLE mailing_list_messages (
    message_key TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    external_message_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    subject TEXT NOT NULL,
    normalized_subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    message_date TEXT,
    text_content TEXT NOT NULL,
    connectivity_state TEXT NOT NULL CHECK (connectivity_state IN
      ('connected','truncated','incomplete','quarantined')),
    canonical_json TEXT NOT NULL,
    UNIQUE (source_id, external_message_id)
) STRICT;
CREATE TABLE mailing_list_relationships (
    child_message_key TEXT PRIMARY KEY REFERENCES mailing_list_messages(message_key),
    parent_external_message_id TEXT NOT NULL,
    parent_message_key TEXT REFERENCES mailing_list_messages(message_key),
    authority TEXT NOT NULL CHECK (authority IN ('header','archive','inferred')),
    certainty TEXT NOT NULL CHECK (certainty IN ('direct','heuristic','unresolved')),
    CHECK ((parent_message_key IS NULL) = (certainty = 'unresolved'))
) STRICT;
CREATE TABLE mailing_list_discussions (
    discussion_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    root_message_key TEXT NOT NULL UNIQUE REFERENCES mailing_list_messages(message_key),
    connectivity_state TEXT NOT NULL CHECK (connectivity_state IN
      ('connected','truncated','incomplete','quarantined')),
    descendant_truncated INTEGER NOT NULL CHECK (descendant_truncated IN (0,1)),
    message_count INTEGER NOT NULL CHECK (message_count > 0),
    first_message_at TEXT,
    last_message_at TEXT,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE mailing_list_discussion_members (
    discussion_id TEXT NOT NULL REFERENCES mailing_list_discussions(discussion_id),
    message_key TEXT NOT NULL UNIQUE REFERENCES mailing_list_messages(message_key),
    depth INTEGER NOT NULL CHECK (depth >= 0),
    PRIMARY KEY (discussion_id, message_key)
) STRICT;
CREATE TABLE artifact_streams (
    stream_id TEXT PRIMARY KEY,
    current_revision_id TEXT NOT NULL UNIQUE
) STRICT;
CREATE TABLE artifact_stream_revisions (
    revision_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL REFERENCES artifact_streams(stream_id)
      DEFERRABLE INITIALLY DEFERRED,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    predecessor_id TEXT REFERENCES artifact_stream_revisions(revision_id),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    input_kind TEXT NOT NULL CHECK (input_kind IN ('external','streams')),
    schema_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    UNIQUE (stream_id, revision_number)
) STRICT;
CREATE TABLE artifact_stream_dependencies (
    revision_id TEXT NOT NULL REFERENCES artifact_stream_revisions(revision_id),
    upstream_stream_id TEXT NOT NULL REFERENCES artifact_streams(stream_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (revision_id, upstream_stream_id),
    UNIQUE (revision_id, ordinal)
) STRICT;
CREATE TABLE artifact_stream_projections (
    artifact_id TEXT PRIMARY KEY REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    schema_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    effective_at TEXT,
    title TEXT NOT NULL,
    searchable_text TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    context_id TEXT,
    context_depth INTEGER,
    completeness TEXT,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE artifact_stream_runs (
    run_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL REFERENCES artifact_streams(stream_id),
    revision_id TEXT NOT NULL REFERENCES artifact_stream_revisions(revision_id),
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed')),
    input_fingerprint TEXT NOT NULL,
    direct_count INTEGER NOT NULL DEFAULT 0 CHECK (direct_count >= 0),
    context_count INTEGER NOT NULL DEFAULT 0 CHECK (context_count >= 0),
    error_code TEXT,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE artifact_stream_run_plans (
    run_id TEXT PRIMARY KEY REFERENCES artifact_stream_runs(run_id),
    publication_json TEXT NOT NULL
) STRICT;
CREATE TABLE artifact_stream_memberships (
    membership_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES artifact_stream_runs(run_id),
    stream_id TEXT NOT NULL REFERENCES artifact_streams(stream_id),
    revision_id TEXT NOT NULL REFERENCES artifact_stream_revisions(revision_id),
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    inclusion_kind TEXT NOT NULL CHECK (inclusion_kind IN ('direct','context')),
    inclusion_reason TEXT NOT NULL,
    expansion_strategy TEXT NOT NULL,
    completeness TEXT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    canonical_json TEXT NOT NULL,
    UNIQUE (run_id, artifact_id),
    UNIQUE (run_id, ordinal)
) STRICT;
CREATE TABLE artifact_stream_membership_lineage (
    lineage_id TEXT PRIMARY KEY,
    membership_id TEXT NOT NULL REFERENCES artifact_stream_memberships(membership_id),
    upstream_stream_id TEXT REFERENCES artifact_streams(stream_id),
    upstream_membership_id TEXT,
    seed_artifact_id TEXT REFERENCES artifacts(artifact_id),
    inclusion_reason TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE INDEX artifacts_sha256 ON artifacts(sha256);
CREATE INDEX attempts_document_time ON acquisition_attempts(document_id, occurred_at, attempt_id);
CREATE INDEX attempts_source_time ON acquisition_attempts(source_id, occurred_at, attempt_id);
CREATE INDEX observations_artifact_order
ON artifact_observations(artifact_id, observed_at, observation_id);
CREATE INDEX observations_document_order
ON artifact_observations(document_id, observed_at, observation_id);
CREATE INDEX pull_runs_requested ON pull_runs(requested_at DESC, run_id DESC);
CREATE INDEX mailing_list_runs_source_time
ON mailing_list_runs(source_id, requested_at DESC, run_id DESC);
CREATE INDEX mailing_list_items_message
ON mailing_list_run_items(source_id, external_message_id, run_id);
CREATE INDEX mailing_list_messages_source_date
ON mailing_list_messages(source_id, message_date DESC, message_key);
CREATE INDEX mailing_list_relationship_parent
ON mailing_list_relationships(parent_message_key, child_message_key);
CREATE INDEX mailing_list_discussions_source_date
ON mailing_list_discussions(source_id, last_message_at DESC, discussion_id);
CREATE INDEX artifact_stream_dependencies_upstream
ON artifact_stream_dependencies(upstream_stream_id, revision_id);
CREATE INDEX artifact_stream_projections_schema_source
ON artifact_stream_projections(schema_id, source_id, effective_at, artifact_id);
CREATE INDEX artifact_stream_runs_stream_time
ON artifact_stream_runs(stream_id, requested_at DESC, run_id DESC);
CREATE UNIQUE INDEX artifact_stream_runs_idempotent_success
ON artifact_stream_runs(revision_id, input_fingerprint) WHERE status = 'succeeded';
CREATE INDEX artifact_stream_memberships_stream_run
ON artifact_stream_memberships(stream_id, run_id, ordinal);
CREATE INDEX artifact_stream_lineage_membership
ON artifact_stream_membership_lineage(membership_id, lineage_id);
"""

_MIGRATE_V1_TO_V2 = _SCHEMA[
    _SCHEMA.index("CREATE TABLE mailing_list_sources") :
    _SCHEMA.index("CREATE TABLE artifact_streams")
] + _SCHEMA[
    _SCHEMA.index("CREATE INDEX mailing_list_runs_source_time") :
    _SCHEMA.index("CREATE INDEX artifact_stream_dependencies_upstream")
]

_MIGRATE_V2_TO_V3 = _SCHEMA[
    _SCHEMA.index("CREATE TABLE artifact_streams") :
    _SCHEMA.index("CREATE INDEX artifacts_sha256")
] + _SCHEMA[_SCHEMA.index("CREATE INDEX artifact_stream_dependencies_upstream") :]

_MIGRATE_V3_TO_V4 = """
ALTER TABLE mailing_list_runs ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'succeeded'
  CHECK (lifecycle_status IN ('succeeded','partial','retryable_failure','terminal_failure'));
ALTER TABLE mailing_list_runs ADD COLUMN error_code TEXT;
ALTER TABLE mailing_list_runs ADD COLUMN retryable INTEGER NOT NULL DEFAULT 0
  CHECK (retryable IN (0,1));
"""

_V4_LORE_TRANSPORT_DEFAULT = {
    "user_agent": "RFI-1 bounded-mailing-list/2",
    "minimum_request_interval_seconds": 1.0,
    "maximum_concurrency": 1,
    "timeout_seconds": 20.0,
    "maximum_response_bytes": 5_000_000,
    "maximum_attempts_per_request": 3,
    "backoff_initial_seconds": 1.0,
    "backoff_maximum_seconds": 30.0,
}

_TASK028_SOURCE_ID = "linux-block-lore"
_TASK028_LIST_ID = "linux-block"
_TASK028_PROVIDER = "lore-public-inbox"
_TASK028_MALFORMED_URL = "https://lore-kernel-org/linux-block"
_TASK028_CANONICAL_URL = "https://lore.kernel.org/linux-block/"


def _migrate_v4_task028_legacy_linux_block_source(connection: sqlite3.Connection) -> bool:
    """Repair only the known unused TASK-028 legacy source, or leave it untouched."""
    mailing_row = connection.execute(
        "SELECT list_id,archive_base_url,canonical_json FROM mailing_list_sources "
        "WHERE source_id=?",
        (_TASK028_SOURCE_ID,),
    ).fetchone()
    governed_row = connection.execute(
        "SELECT mechanism,canonical_json FROM governed_sources WHERE source_id=?",
        (_TASK028_SOURCE_ID,),
    ).fetchone()
    if mailing_row is None or governed_row is None:
        return False
    if (
        str(mailing_row[0]) != _TASK028_LIST_ID
        or str(mailing_row[1]) != _TASK028_MALFORMED_URL
        or str(governed_row[0]) != _TASK028_PROVIDER
    ):
        return False
    try:
        mailing = json.loads(str(mailing_row[2]))
        governed = json.loads(str(governed_row[1]))
    except (json.JSONDecodeError, TypeError):
        return False
    configuration = governed.get("configuration")
    if not isinstance(configuration, dict):
        return False
    if (
        mailing.get("source_id") != _TASK028_SOURCE_ID
        or mailing.get("list_id") != _TASK028_LIST_ID
        or mailing.get("provider") != _TASK028_PROVIDER
        or mailing.get("archive_base_url") != _TASK028_MALFORMED_URL
        or governed.get("source_id") != _TASK028_SOURCE_ID
        or governed.get("mechanism") != _TASK028_PROVIDER
        or configuration.get("list_id") != _TASK028_LIST_ID
        or configuration.get("archive_base_url") != _TASK028_MALFORMED_URL
    ):
        return False

    for table in (
        "acquisition_attempts",
        "artifact_observations",
        "checkpoint_events",
        "current_checkpoints",
        "mailing_list_runs",
        "mailing_list_run_items",
        "mailing_list_messages",
        "mailing_list_discussions",
        "artifact_stream_projections",
    ):
        if connection.execute(
            f"SELECT 1 FROM {table} WHERE source_id=? LIMIT 1", (_TASK028_SOURCE_ID,)
        ).fetchone() is not None:
            return False
    for row in connection.execute(
        "SELECT canonical_json FROM artifact_stream_revisions WHERE input_kind='external'"
    ):
        try:
            revision = json.loads(str(row[0]))
        except (json.JSONDecodeError, TypeError):
            return False
        if _TASK028_SOURCE_ID in revision.get("input_ids", []):
            return False

    mailing["archive_base_url"] = _TASK028_CANONICAL_URL
    configuration["archive_base_url"] = _TASK028_CANONICAL_URL
    connection.execute(
        "UPDATE governed_sources SET canonical_json=? WHERE source_id=?",
        (canonical_json(governed), _TASK028_SOURCE_ID),
    )
    connection.execute(
        "UPDATE mailing_list_sources SET archive_base_url=?,canonical_json=? "
        "WHERE source_id=?",
        (_TASK028_CANONICAL_URL, canonical_json(mailing), _TASK028_SOURCE_ID),
    )
    return True


class RepositoryDatabase:
    """Own schema lifecycle, connections, and repository-wide revisions."""

    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.path = state_root / DATABASE_NAME

    @classmethod
    def initialize(cls, state_root: Path) -> RepositoryDatabase:
        database = cls(state_root)
        state_root.mkdir(parents=True, exist_ok=True)
        if database.path.exists():
            if database.legacy_entries():
                raise StorageError(
                    "legacy_state_detected",
                    "legacy structured state cannot be mixed with SQLite authority",
                )
            database.migrate()
            database.validate()
            return database
        legacy = database.legacy_entries()
        if legacy:
            raise StorageError(
                "legacy_state_detected",
                "legacy structured state detected; automatic migration is unsupported; "
                "select a fresh state path or archive the legacy state",
            )
        try:
            with database.connect() as connection:
                connection.executescript(_SCHEMA)
                timestamp = utc_now()
                repository_id = "repository-" + __import__("secrets").token_hex(16)
                connection.execute(
                    "INSERT INTO schema_metadata VALUES (1, ?, ?, 'rfi-structured-state')",
                    (SCHEMA_VERSION, timestamp),
                )
                connection.execute(
                    "INSERT INTO repository_state VALUES (1, ?, 0, ?)",
                    (repository_id, timestamp),
                )
        except sqlite3.Error as error:
            database.path.unlink(missing_ok=True)
            raise StorageError(
                "initialization_failed", "could not initialize repository state"
            ) from error
        database.validate()
        return database

    @classmethod
    def open(cls, state_root: Path) -> RepositoryDatabase:
        database = cls(state_root)
        if not database.path.is_file():
            if database.legacy_entries():
                raise StorageError(
                    "legacy_state_detected",
                    "legacy structured state detected; automatic migration is unsupported",
                )
            raise StorageError(
                "missing_database",
                "repository state is not initialized; run 'rfi init'",
            )
        if database.legacy_entries():
            raise StorageError(
                "legacy_state_detected",
                "legacy structured state cannot be mixed with SQLite authority",
            )
        database.migrate()
        database.validate()
        return database

    def migrate(self) -> bool:
        """Upgrade the only supported prior structured-state schema in place."""
        try:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT schema_version FROM schema_metadata WHERE singleton = 1"
                ).fetchone()
                if row is None:
                    raise StorageError(
                        "uninitialized_state", "repository schema metadata is absent"
                    )
                version = int(row[0])
                if version == SCHEMA_VERSION:
                    return False
                if version not in {1, 2, 3, 4}:
                    raise StorageError(
                        "incompatible_schema",
                        f"repository schema version {version} is unsupported; "
                        f"expected {SCHEMA_VERSION}",
                    )
                connection.execute("BEGIN IMMEDIATE")
                mailing_columns = {
                    str(item[1])
                    for item in connection.execute("PRAGMA table_info(mailing_list_runs)")
                }
                scripts = []
                if version == 1:
                    scripts.append(_MIGRATE_V1_TO_V2)
                if version <= 2:
                    scripts.append(_MIGRATE_V2_TO_V3)
                if version in {2, 3} and "lifecycle_status" not in mailing_columns:
                    scripts.append(_MIGRATE_V3_TO_V4)
                for script in scripts:
                    for statement in script.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                if version <= 3:
                    for source in connection.execute(
                        "SELECT source_id,canonical_json FROM governed_sources "
                        "WHERE mechanism='lore-public-inbox'"
                    ):
                        value = json.loads(str(source[1]))
                        policy = value.setdefault("policy", {})
                        policy.setdefault("transport", _V4_LORE_TRANSPORT_DEFAULT)
                        connection.execute(
                            "UPDATE governed_sources SET canonical_json=? WHERE source_id=?",
                            (canonical_json(value), str(source[0])),
                        )
                if version <= 4 and _migrate_v4_task028_legacy_linux_block_source(connection):
                    self.advance_revision(connection)
                connection.execute(
                    "UPDATE schema_metadata SET schema_version = ?, applied_at = ? "
                    "WHERE singleton = 1",
                    (SCHEMA_VERSION, utc_now()),
                )
                connection.commit()
            return True
        except StorageError:
            raise
        except sqlite3.Error as error:
            raise StorageError(
                "migration_failed", "repository schema migration failed"
            ) from error

    def connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        try:
            if read_only:
                connection = sqlite3.connect(
                    f"file:{self.path}?mode=ro",
                    uri=True,
                    timeout=BUSY_TIMEOUT_MS / 1000,
                    factory=_ClosingConnection,
                )
            else:
                connection = sqlite3.connect(
                    self.path,
                    timeout=BUSY_TIMEOUT_MS / 1000,
                    factory=_ClosingConnection,
                )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            if not read_only:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = FULL")
            return connection
        except sqlite3.Error as error:
            raise StorageError(
                "database_open_failed", "repository database cannot be opened"
            ) from error

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise StorageError(
                "integrity_constraint", "structured-state constraint failed"
            ) from error
        except sqlite3.OperationalError as error:
            connection.rollback()
            code = "database_busy" if "locked" in str(error).lower() else "transaction_failed"
            raise StorageError(code, "structured-state transaction failed") from error
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def advance_revision(connection: sqlite3.Connection) -> int:
        connection.execute(
            "UPDATE repository_state SET authority_revision = authority_revision + 1 "
            "WHERE singleton = 1"
        )
        row = connection.execute(
            "SELECT authority_revision FROM repository_state WHERE singleton = 1"
        ).fetchone()
        assert row is not None
        return int(row[0])

    def revision(self) -> int:
        with self.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT authority_revision FROM repository_state WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise StorageError("corrupt_database", "repository revision state is absent")
        return int(row[0])

    def validate(self) -> dict[str, Any]:
        try:
            with self.connect(read_only=True) as connection:
                metadata = connection.execute(
                    "SELECT schema_version, schema_name FROM schema_metadata WHERE singleton = 1"
                ).fetchone()
                if metadata is None:
                    raise StorageError(
                        "uninitialized_state", "repository schema metadata is absent"
                    )
                if int(metadata[0]) != SCHEMA_VERSION:
                    raise StorageError(
                        "incompatible_schema",
                        f"repository schema version {metadata[0]} is unsupported; "
                        f"expected {SCHEMA_VERSION}",
                    )
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
                tables = connection.execute(
                    "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
                ).fetchall()
        except StorageError:
            raise
        except sqlite3.DatabaseError as error:
            raise StorageError(
                "corrupt_database", "repository database failed integrity validation"
            ) from error
        if integrity != "ok":
            raise StorageError(
                "corrupt_database", "repository database failed integrity validation"
            )
        if foreign_keys:
            raise StorageError(
                "foreign_key_failure", "repository database has invalid relationships"
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "integrity": "ok",
            "foreign_keys": "ok",
            "tables": len(tables),
            "result": "PASS",
        }

    def legacy_entries(self) -> tuple[str, ...]:
        markers = (
            "catalog.json",
            "firm-catalog/catalog.json",
            "source-profiles/catalog.json",
            "acquisition/authoritative",
            "authoritative",
            "pull-workflows/runs",
        )
        return tuple(marker for marker in markers if (self.state_root / marker).exists())
