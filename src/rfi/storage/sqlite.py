"""Authoritative SQLite foundation for RFI structured runtime state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

DATABASE_NAME = "repository.sqlite3"
SCHEMA_VERSION = 12
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
CREATE TABLE IF NOT EXISTS firm_external_identities (
    firm_id TEXT NOT NULL REFERENCES firms(firm_id),
    provider TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    identifier TEXT NOT NULL,
    regime TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    verification_source TEXT NOT NULL,
    catalog_version INTEGER NOT NULL CHECK (catalog_version > 0),
    canonical_json TEXT NOT NULL,
    PRIMARY KEY (firm_id, provider)
) STRICT;
CREATE TABLE firm_config_authorities (
    firm_id TEXT PRIMARY KEY REFERENCES firms(firm_id),
    config_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    source_name TEXT NOT NULL,
    canonical_json TEXT NOT NULL
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
CREATE TABLE sec_sources (
    firm_id TEXT PRIMARY KEY REFERENCES firms(firm_id),
    applicability TEXT NOT NULL CHECK (applicability IN ('direct','parent','non_applicable')),
    legal_issuer TEXT NOT NULL,
    cik TEXT,
    filing_regime TEXT NOT NULL,
    parent_firm_id TEXT REFERENCES firms(firm_id),
    verification_status TEXT NOT NULL CHECK (verification_status = 'verified'),
    verified_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    CHECK ((applicability = 'non_applicable') = (cik IS NULL)),
    CHECK ((applicability = 'parent') = (parent_firm_id IS NOT NULL))
) STRICT;
CREATE TABLE sec_workflow_runs (
    run_id TEXT PRIMARY KEY,
    firm_id TEXT NOT NULL REFERENCES firms(firm_id),
    status TEXT NOT NULL,
    current_state TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    cancellation_requested INTEGER NOT NULL CHECK (cancellation_requested IN (0,1)),
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
CREATE TABLE IF NOT EXISTS canonical_mailing_list_messages (
    canonical_message_id TEXT PRIMARY KEY,
    normalized_message_id TEXT NOT NULL UNIQUE,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS mailing_list_message_conflicts (
    conflict_id TEXT PRIMARY KEY,
    normalized_message_id TEXT NOT NULL,
    canonical_message_id TEXT REFERENCES canonical_mailing_list_messages(canonical_message_id),
    canonical_artifact_id TEXT,
    candidate_artifact_id TEXT NOT NULL,
    candidate_document_id TEXT NOT NULL,
    source_id TEXT REFERENCES mailing_list_sources(source_id),
    run_id TEXT,
    detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unresolved','resolved')),
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count > 0),
    canonical_json TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_message_conflicts_identity
ON mailing_list_message_conflicts(normalized_message_id);
CREATE TABLE IF NOT EXISTS mailing_list_message_conflict_observations (
    run_id TEXT NOT NULL,
    conflict_id TEXT NOT NULL REFERENCES mailing_list_message_conflicts(conflict_id),
    normalized_message_id TEXT NOT NULL,
    candidate_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    observed_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome = 'conflicted_skipped'),
    PRIMARY KEY (run_id, conflict_id)
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
    canonical_message_id TEXT REFERENCES canonical_mailing_list_messages(canonical_message_id),
    observation_type TEXT NOT NULL CHECK (observation_type IN
      ('fetched','reused','unavailable')),
    content_fetched INTEGER NOT NULL CHECK (content_fetched IN (0,1)),
    artifact_created INTEGER NOT NULL CHECK (artifact_created IN (0,1)),
    canonical_created INTEGER NOT NULL CHECK (canonical_created IN (0,1)),
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
    canonical_message_id TEXT REFERENCES canonical_mailing_list_messages(canonical_message_id),
    canonical_json TEXT NOT NULL,
    UNIQUE (source_id, external_message_id)
) STRICT;
CREATE TABLE IF NOT EXISTS mailing_list_relationship_claims (
    claim_id TEXT PRIMARY KEY,
    child_canonical_message_id TEXT NOT NULL
      REFERENCES canonical_mailing_list_messages(canonical_message_id),
    referenced_raw TEXT NOT NULL,
    referenced_normalized_message_id TEXT,
    claim_role TEXT NOT NULL CHECK (claim_role IN
      ('immediate_parent','ancestor_reference')),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN
      ('header_in_reply_to','header_references','provider_immediate_parent',
       'fallback_heuristic_parent')),
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    child_external_message_id TEXT NOT NULL,
    child_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    observation_run_id TEXT NOT NULL REFERENCES mailing_list_runs(run_id),
    reference_ordinal INTEGER CHECK (reference_ordinal IS NULL OR reference_ordinal >= 0),
    acquisition_path TEXT NOT NULL CHECK (acquisition_path IN
      ('configured_archive','cross_archive_fallback')),
    evidenced_delivery_source_id TEXT REFERENCES mailing_list_sources(source_id),
    algorithm_id TEXT,
    observed_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    CHECK ((evidence_type = 'header_references') = (reference_ordinal IS NOT NULL)),
    CHECK ((evidence_type = 'fallback_heuristic_parent') = (algorithm_id IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_relationship_claims_child
ON mailing_list_relationship_claims(child_canonical_message_id,claim_role,evidence_type);
CREATE INDEX IF NOT EXISTS mailing_list_relationship_claims_reference
ON mailing_list_relationship_claims(referenced_normalized_message_id,claim_role);
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
CREATE TABLE IF NOT EXISTS mailing_list_fetch_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('completed','failed','cancelled','abandoned')),
    message TEXT NOT NULL DEFAULT '',
    queued_at TEXT,
    started_at TEXT,
    finished_at TEXT NOT NULL,
    windows_completed INTEGER NOT NULL DEFAULT 0,
    result_json TEXT
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_fetch_history_finished
ON mailing_list_fetch_history(finished_at DESC, history_id DESC);
CREATE TABLE IF NOT EXISTS mailing_list_fetch_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    event TEXT NOT NULL,
    stream_id TEXT,
    stream_name TEXT,
    message TEXT NOT NULL DEFAULT ''
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_fetch_events_sequence
ON mailing_list_fetch_events(sequence DESC, event_id DESC);
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
] + _SCHEMA[
    _SCHEMA.index("CREATE INDEX artifact_stream_dependencies_upstream") :
    _SCHEMA.index("CREATE TABLE IF NOT EXISTS mailing_list_fetch_history")
]

_MIGRATE_V5_TO_V6 = """
CREATE TABLE IF NOT EXISTS mailing_list_fetch_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('completed','failed','cancelled','abandoned')),
    message TEXT NOT NULL DEFAULT '',
    queued_at TEXT,
    started_at TEXT,
    finished_at TEXT NOT NULL,
    windows_completed INTEGER NOT NULL DEFAULT 0,
    result_json TEXT
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_fetch_history_finished
ON mailing_list_fetch_history(finished_at DESC, history_id DESC);
CREATE TABLE IF NOT EXISTS mailing_list_fetch_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    event TEXT NOT NULL,
    stream_id TEXT,
    stream_name TEXT,
    message TEXT NOT NULL DEFAULT ''
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_fetch_events_sequence
ON mailing_list_fetch_events(sequence DESC, event_id DESC);
"""

_MIGRATE_V3_TO_V4 = """
ALTER TABLE mailing_list_runs ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'succeeded'
  CHECK (lifecycle_status IN ('succeeded','partial','retryable_failure','terminal_failure'));
ALTER TABLE mailing_list_runs ADD COLUMN error_code TEXT;
ALTER TABLE mailing_list_runs ADD COLUMN retryable INTEGER NOT NULL DEFAULT 0
  CHECK (retryable IN (0,1));
"""

_MIGRATE_V6_TO_V7 = """
CREATE TABLE canonical_mailing_list_messages (
    canonical_message_id TEXT PRIMARY KEY,
    normalized_message_id TEXT NOT NULL UNIQUE,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE TABLE mailing_list_message_conflicts (
    conflict_id TEXT PRIMARY KEY,
    normalized_message_id TEXT NOT NULL,
    canonical_message_id TEXT REFERENCES canonical_mailing_list_messages(canonical_message_id),
    canonical_artifact_id TEXT,
    candidate_artifact_id TEXT NOT NULL,
    candidate_document_id TEXT NOT NULL,
    source_id TEXT REFERENCES mailing_list_sources(source_id),
    run_id TEXT,
    detected_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
CREATE INDEX mailing_list_message_conflicts_identity
ON mailing_list_message_conflicts(normalized_message_id);
ALTER TABLE mailing_list_run_items ADD COLUMN canonical_message_id TEXT
  REFERENCES canonical_mailing_list_messages(canonical_message_id);
ALTER TABLE mailing_list_run_items ADD COLUMN observation_type TEXT NOT NULL DEFAULT 'reused'
  CHECK (observation_type IN ('fetched','reused','unavailable'));
ALTER TABLE mailing_list_run_items ADD COLUMN content_fetched INTEGER NOT NULL DEFAULT 0
  CHECK (content_fetched IN (0,1));
ALTER TABLE mailing_list_run_items ADD COLUMN artifact_created INTEGER NOT NULL DEFAULT 0
  CHECK (artifact_created IN (0,1));
ALTER TABLE mailing_list_run_items ADD COLUMN canonical_created INTEGER NOT NULL DEFAULT 0
  CHECK (canonical_created IN (0,1));
"""

_MIGRATE_V8_TO_V9_CONFLICT_CASE = """
ALTER TABLE mailing_list_message_conflicts ADD COLUMN last_detected_at TEXT;
ALTER TABLE mailing_list_message_conflicts ADD COLUMN status TEXT NOT NULL DEFAULT 'unresolved'
  CHECK (status IN ('unresolved','resolved'));
ALTER TABLE mailing_list_message_conflicts ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1
  CHECK (occurrence_count > 0);
UPDATE mailing_list_message_conflicts SET last_detected_at=detected_at
  WHERE last_detected_at IS NULL;
"""

_MIGRATE_V8_TO_V9_OBSERVATIONS = """
CREATE TABLE mailing_list_message_conflict_observations (
    run_id TEXT NOT NULL,
    conflict_id TEXT NOT NULL REFERENCES mailing_list_message_conflicts(conflict_id),
    normalized_message_id TEXT NOT NULL,
    candidate_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    observed_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome = 'conflicted_skipped'),
    PRIMARY KEY (run_id, conflict_id)
) STRICT;
"""

_MIGRATE_V7_TO_V8 = """
CREATE TABLE IF NOT EXISTS sec_sources (
    firm_id TEXT PRIMARY KEY REFERENCES firms(firm_id),
    applicability TEXT NOT NULL CHECK (applicability IN ('direct','parent','non_applicable')),
    legal_issuer TEXT NOT NULL,
    cik TEXT,
    filing_regime TEXT NOT NULL,
    parent_firm_id TEXT REFERENCES firms(firm_id),
    verification_status TEXT NOT NULL CHECK (verification_status = 'verified'),
    verified_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    CHECK ((applicability = 'non_applicable') = (cik IS NULL)),
    CHECK ((applicability = 'parent') = (parent_firm_id IS NOT NULL))
) STRICT;
CREATE TABLE IF NOT EXISTS sec_workflow_runs (
    run_id TEXT PRIMARY KEY,
    firm_id TEXT NOT NULL REFERENCES firms(firm_id),
    status TEXT NOT NULL,
    current_state TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    cancellation_requested INTEGER NOT NULL CHECK (cancellation_requested IN (0,1)),
    canonical_json TEXT NOT NULL
) STRICT;
"""

_MIGRATE_V9_TO_V10 = """
CREATE TABLE IF NOT EXISTS firm_external_identities (
    firm_id TEXT NOT NULL REFERENCES firms(firm_id),
    provider TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    identifier TEXT NOT NULL,
    regime TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    verification_source TEXT NOT NULL,
    catalog_version INTEGER NOT NULL CHECK (catalog_version > 0),
    canonical_json TEXT NOT NULL,
    PRIMARY KEY (firm_id, provider)
) STRICT;
"""

_MIGRATE_V10_TO_V11 = """
CREATE TABLE IF NOT EXISTS firm_config_authorities (
    firm_id TEXT PRIMARY KEY REFERENCES firms(firm_id),
    config_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    source_name TEXT NOT NULL,
    canonical_json TEXT NOT NULL
) STRICT;
"""

_MIGRATE_V11_TO_V12_MESSAGE_LINK = """
ALTER TABLE mailing_list_messages ADD COLUMN canonical_message_id TEXT
  REFERENCES canonical_mailing_list_messages(canonical_message_id);
"""

_MIGRATE_V11_TO_V12 = """
CREATE TABLE IF NOT EXISTS mailing_list_relationship_claims (
    claim_id TEXT PRIMARY KEY,
    child_canonical_message_id TEXT NOT NULL
      REFERENCES canonical_mailing_list_messages(canonical_message_id),
    referenced_raw TEXT NOT NULL,
    referenced_normalized_message_id TEXT,
    claim_role TEXT NOT NULL CHECK (claim_role IN
      ('immediate_parent','ancestor_reference')),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN
      ('header_in_reply_to','header_references','provider_immediate_parent',
       'fallback_heuristic_parent')),
    source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),
    child_external_message_id TEXT NOT NULL,
    child_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    observation_run_id TEXT NOT NULL REFERENCES mailing_list_runs(run_id),
    reference_ordinal INTEGER CHECK (reference_ordinal IS NULL OR reference_ordinal >= 0),
    acquisition_path TEXT NOT NULL CHECK (acquisition_path IN
      ('configured_archive','cross_archive_fallback')),
    evidenced_delivery_source_id TEXT REFERENCES mailing_list_sources(source_id),
    algorithm_id TEXT,
    observed_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    CHECK ((evidence_type = 'header_references') = (reference_ordinal IS NOT NULL)),
    CHECK ((evidence_type = 'fallback_heuristic_parent') = (algorithm_id IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS mailing_list_relationship_claims_child
ON mailing_list_relationship_claims(child_canonical_message_id,claim_role,evidence_type);
CREATE INDEX IF NOT EXISTS mailing_list_relationship_claims_reference
ON mailing_list_relationship_claims(referenced_normalized_message_id,claim_role);
"""


def _backfill_task045(connection: sqlite3.Connection) -> None:
    """Link source projections and derive bounded claims from retained observations."""
    import hashlib

    from rfi.mailing_lists.parser import normalize_message_id

    canonical = {
        str(row[0]): str(row[1])
        for row in connection.execute(
            "SELECT normalized_message_id,canonical_message_id "
            "FROM canonical_mailing_list_messages"
        )
    }
    retained = connection.execute(
        "SELECT i.run_id,i.external_message_id,i.artifact_id,i.document_id,r.requested_at "
        "FROM mailing_list_run_items i JOIN artifacts a ON a.artifact_id=i.artifact_id "
        "JOIN mailing_list_runs r ON r.run_id=i.run_id "
        "WHERE a.media_type='message/rfc822' "
        "ORDER BY r.requested_at,i.run_id,i.source_id,i.external_message_id"
    ).fetchall()
    for row in retained:
        normalized = normalize_message_id(str(row[1]))
        if normalized is None:
            continue
        canonical_id = canonical.get(normalized)
        if canonical_id is None:
            canonical_id = _canonical_message_id(normalized)
            payload = canonical_json({
                "canonical_message_id": canonical_id,
                "normalized_message_id": normalized,
                "artifact_id": str(row[2]), "document_id": str(row[3]),
                "backfilled_task045": True,
            })
            connection.execute(
                "INSERT INTO canonical_mailing_list_messages VALUES (?,?,?,?,?,?)",
                (canonical_id, normalized, str(row[2]), str(row[3]), str(row[4]), payload),
            )
            canonical[normalized] = canonical_id
        connection.execute(
            "UPDATE mailing_list_run_items SET canonical_message_id=? "
            "WHERE run_id=? AND external_message_id=?",
            (canonical_id, str(row[0]), str(row[1])),
        )
    for row in connection.execute(
        "SELECT message_key,external_message_id FROM mailing_list_messages"
    ).fetchall():
        normalized = normalize_message_id(str(row[1]))
        if normalized in canonical:
            connection.execute(
                "UPDATE mailing_list_messages SET canonical_message_id=? WHERE message_key=?",
                (canonical[normalized], str(row[0])),
            )
    rows = connection.execute(
        "SELECT m.message_key,m.source_id,m.external_message_id,m.artifact_id,m.canonical_json,"
        "m.canonical_message_id,i.run_id,r.requested_at,r.canonical_json,"
        "rel.parent_external_message_id "
        "FROM mailing_list_messages m JOIN mailing_list_run_items i "
        "ON i.source_id=m.source_id AND i.external_message_id=m.external_message_id "
        "JOIN mailing_list_runs r ON r.run_id=i.run_id "
        "LEFT JOIN mailing_list_relationships rel ON rel.child_message_key=m.message_key "
        "WHERE m.canonical_message_id IS NOT NULL "
        "ORDER BY m.message_key,r.requested_at,i.run_id"
    ).fetchall()
    seen_messages: set[str] = set()
    for row in rows:
        message_key = str(row[0])
        if message_key in seen_messages:
            continue
        seen_messages.add(message_key)
        projection = json.loads(str(row[4]))
        manifest = json.loads(str(row[8]))
        fallback = str(row[2]) in set(manifest.get("fallback_message_ids", ()))
        assertions: list[tuple[str, str, str, int | None]] = []
        parent = row[9]
        if isinstance(parent, str) and parent:
            assertions.append((parent, "immediate_parent", "header_in_reply_to", None))
        for ordinal, reference in enumerate(projection.get("references", ())):
            if isinstance(reference, str) and reference:
                assertions.append((reference, "ancestor_reference", "header_references", ordinal))
        for raw, role, evidence, ordinal in assertions:
            normalized = normalize_message_id(raw)
            if normalized is None:
                continue
            identity = canonical_json({
                "child": str(row[5]), "raw": raw, "role": role,
                "evidence": evidence, "source_id": str(row[1]),
                "artifact_id": str(row[3]), "run_id": str(row[6]), "ordinal": ordinal,
            })
            claim_id = "mail-claim-" + hashlib.sha256(identity.encode()).hexdigest()[:32]
            payload = canonical_json({
                "claim_id": claim_id, "child_canonical_message_id": str(row[5]),
                "referenced_raw": raw, "referenced_normalized_message_id": normalized,
                "claim_role": role, "evidence_type": evidence, "source_id": str(row[1]),
                "child_external_message_id": str(row[2]), "child_artifact_id": str(row[3]),
                "observation_run_id": str(row[6]), "reference_ordinal": ordinal,
                "acquisition_path": "cross_archive_fallback" if fallback else "configured_archive",
                "evidenced_delivery_source_id": None, "algorithm_id": None,
                "backfilled": True,
            })
            connection.execute(
                "INSERT OR IGNORE INTO mailing_list_relationship_claims VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (claim_id, str(row[5]), raw, normalized, role, evidence, str(row[1]),
                 str(row[2]), str(row[3]), str(row[6]), ordinal,
                 "cross_archive_fallback" if fallback else "configured_archive",
                 None, None, str(row[7]), payload),
            )


def _canonical_message_id(normalized_message_id: str) -> str:
    import hashlib

    return "canonical-mail-" + hashlib.sha256(normalized_message_id.encode()).hexdigest()[:32]


def _backfill_task035(connection: sqlite3.Connection) -> None:
    """Add canonical mappings only for unambiguous retained RFC822 history."""
    from rfi.mailing_lists.parser import normalize_message_id

    rows = connection.execute(
        "SELECT i.run_id,i.source_id,i.external_message_id,i.artifact_id,i.document_id,"
        "a.media_type,r.requested_at FROM mailing_list_run_items i "
        "JOIN artifacts a ON a.artifact_id=i.artifact_id "
        "JOIN mailing_list_runs r ON r.run_id=i.run_id "
        "ORDER BY r.requested_at,i.run_id,i.source_id,i.external_message_id"
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        normalized = normalize_message_id(str(row[2]))
        if str(row[5]) != "message/rfc822" or normalized is None:
            connection.execute(
                "UPDATE mailing_list_run_items SET observation_type='unavailable' "
                "WHERE run_id=? AND external_message_id=?",
                (str(row[0]), str(row[2])),
            )
            continue
        grouped.setdefault(normalized, []).append(row)
    for normalized, candidates in grouped.items():
        artifacts = {str(row[3]) for row in candidates}
        canonical_id = _canonical_message_id(normalized)
        if len(artifacts) != 1:
            for row in candidates:
                payload = canonical_json({
                    "reason": "historical_message_id_byte_conflict",
                    "normalized_message_id": normalized,
                    "candidate_artifact_id": str(row[3]),
                    "candidate_document_id": str(row[4]),
                    "source_id": str(row[1]),
                    "run_id": str(row[0]),
                })
                import hashlib
                conflict_id = "mail-conflict-" + hashlib.sha256(payload.encode()).hexdigest()[:32]
                observed_at = utc_now()
                connection.execute(
                    "INSERT OR IGNORE INTO mailing_list_message_conflicts "
                    "(conflict_id,normalized_message_id,canonical_message_id,"
                    "canonical_artifact_id,candidate_artifact_id,candidate_document_id,"
                    "source_id,run_id,detected_at,last_detected_at,status,occurrence_count,"
                    "canonical_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (conflict_id, normalized, None, None, str(row[3]), str(row[4]),
                     str(row[1]), str(row[0]), observed_at, observed_at, "unresolved", 1,
                     payload),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO mailing_list_message_conflict_observations "
                    "VALUES (?,?,?,?,?,?,?)",
                    (str(row[0]), conflict_id, normalized, str(row[3]), str(row[1]),
                     observed_at, "conflicted_skipped"),
                )
            continue
        chosen = candidates[0]
        payload = canonical_json({
            "canonical_message_id": canonical_id,
            "normalized_message_id": normalized,
            "artifact_id": str(chosen[3]),
            "document_id": str(chosen[4]),
            "backfilled": True,
        })
        connection.execute(
            "INSERT INTO canonical_mailing_list_messages VALUES (?,?,?,?,?,?)",
            (canonical_id, normalized, str(chosen[3]), str(chosen[4]),
             str(chosen[6]), payload),
        )
        connection.execute(
            "UPDATE mailing_list_run_items SET canonical_message_id=? "
            "WHERE external_message_id IN (%s) AND artifact_id=?" % ",".join(
                "?" for _ in {str(row[2]) for row in candidates}
            ),
            (canonical_id, *sorted({str(row[2]) for row in candidates}), str(chosen[3])),
        )

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
                if version not in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}:
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
                if version <= 10:
                    scripts.append(_MIGRATE_V10_TO_V11)
                if version <= 9:
                    scripts.append(_MIGRATE_V9_TO_V10)
                if version == 1:
                    scripts.append(_MIGRATE_V1_TO_V2)
                if version <= 2:
                    scripts.append(_MIGRATE_V2_TO_V3)
                if version in {2, 3} and "lifecycle_status" not in mailing_columns:
                    scripts.append(_MIGRATE_V3_TO_V4)
                if version <= 5:
                    scripts.append(_MIGRATE_V5_TO_V6)
                existing_tables = {
                    str(item[0]) for item in connection.execute(
                        "SELECT name FROM sqlite_schema WHERE type='table'"
                    )
                }
                run_item_columns = {
                    str(item[1]) for item in connection.execute(
                        "PRAGMA table_info(mailing_list_run_items)"
                    )
                }
                conflict_columns = {
                    str(item[1]) for item in connection.execute(
                        "PRAGMA table_info(mailing_list_message_conflicts)"
                    )
                }
                message_columns = {
                    str(item[1])
                    for item in connection.execute("PRAGMA table_info(mailing_list_messages)")
                }
                if (
                    version != 1
                    and version <= 6
                    and "canonical_mailing_list_messages" not in existing_tables
                ):
                    scripts.append(_MIGRATE_V6_TO_V7)
                if version <= 7 and "sec_sources" not in existing_tables:
                    scripts.append(_MIGRATE_V7_TO_V8)
                if version != 1 and version <= 8:
                    if "last_detected_at" not in conflict_columns:
                        scripts.append(_MIGRATE_V8_TO_V9_CONFLICT_CASE)
                    if "mailing_list_message_conflict_observations" not in existing_tables:
                        scripts.append(_MIGRATE_V8_TO_V9_OBSERVATIONS)
                if version != 1 and version <= 11 and "canonical_message_id" not in message_columns:
                    scripts.append(_MIGRATE_V11_TO_V12_MESSAGE_LINK)
                if (
                    version != 1 and version <= 11
                    and "mailing_list_relationship_claims" not in existing_tables
                ):
                    scripts.append(_MIGRATE_V11_TO_V12)
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
                if version <= 6 and "canonical_message_id" not in run_item_columns:
                    _backfill_task035(connection)
                if version <= 11:
                    _backfill_task045(connection)
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
                canonical_rows = connection.execute(
                    "SELECT c.canonical_message_id,c.normalized_message_id,c.artifact_id,"
                    "d.current_artifact_id FROM canonical_mailing_list_messages c "
                    "JOIN documents d ON d.document_id=c.document_id"
                ).fetchall()
                source_message_rows = connection.execute(
                    "SELECT m.external_message_id,m.canonical_message_id,a.media_type "
                    "FROM mailing_list_messages m JOIN artifacts a ON a.artifact_id=m.artifact_id"
                ).fetchall()
                claim_rows = connection.execute(
                    "SELECT c.referenced_raw,c.referenced_normalized_message_id,c.claim_role,"
                    "c.evidence_type,c.reference_ordinal,c.algorithm_id "
                    "FROM mailing_list_relationship_claims c"
                ).fetchall()
                invalid_claim_observations = int(connection.execute(
                    "SELECT count(*) FROM mailing_list_relationship_claims c "
                    "WHERE NOT EXISTS (SELECT 1 FROM mailing_list_run_items i "
                    "WHERE i.run_id=c.observation_run_id AND i.source_id=c.source_id "
                    "AND i.external_message_id=c.child_external_message_id "
                    "AND i.artifact_id=c.child_artifact_id "
                    "AND i.canonical_message_id=c.child_canonical_message_id)"
                ).fetchone()[0])
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
        from rfi.mailing_lists.parser import normalize_message_id

        for row in canonical_rows:
            normalized = normalize_message_id(str(row[1]))
            if (
                normalized != str(row[1])
                or str(row[0]) != _canonical_message_id(str(row[1]))
                or str(row[2]) != str(row[3])
            ):
                raise StorageError(
                    "canonical_message_failure",
                    "canonical mailing-list message mapping is invalid",
                )
        canonical_by_normalized = {
            str(row[1]): str(row[0]) for row in canonical_rows
        }
        for row in source_message_rows:
            if str(row[2]) != "message/rfc822":
                continue
            normalized = normalize_message_id(str(row[0]))
            if (
                normalized is None
                or row[1] is None
                or canonical_by_normalized.get(normalized) != str(row[1])
            ):
                raise StorageError(
                    "canonical_message_failure",
                    "source mailing-list message has an invalid canonical link",
                )
        for row in claim_rows:
            normalized = normalize_message_id(str(row[0]))
            if normalized != row[1]:
                raise StorageError(
                    "canonical_lineage_failure",
                    "mailing-list relationship claim reference is invalid",
                )
            if (str(row[3]) == "header_references") != (row[4] is not None):
                raise StorageError(
                    "canonical_lineage_failure",
                    "mailing-list relationship claim ordinal is invalid",
                )
            if (str(row[3]) == "fallback_heuristic_parent") != (row[5] is not None):
                raise StorageError(
                    "canonical_lineage_failure",
                    "mailing-list relationship claim algorithm is invalid",
                )
        if invalid_claim_observations:
            raise StorageError(
                "canonical_lineage_failure",
                "mailing-list relationship claim observation provenance is invalid",
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
