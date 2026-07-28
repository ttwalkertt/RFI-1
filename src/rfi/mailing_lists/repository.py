"""SQLite-backed mailing-list state and immutable evidence coordination."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.contracts import ConflictError, ContractError, IntegrityError
from rfi.mailing_lists.contracts import (
    AcquisitionRunStatus,
    AcquisitionManifest,
    AcquisitionLimits,
    ConnectivityState,
    LoreTransportPolicy,
    MailingListError,
    MailingListSource,
    ParsedMessage,
    SelectionCriteria,
)
from rfi.mailing_lists.parser import normalize_message_id, parse_message, unavailable_ancestor
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json, utc_now


def message_key(source_id: str, external_message_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{external_message_id}".encode()).hexdigest()
    return f"message-{digest[:32]}"


def document_id(source_id: str, external_message_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{external_message_id}".encode()).hexdigest()
    return f"mail.{digest[:32]}"


def canonical_message_id(normalized_message_id: str) -> str:
    digest = hashlib.sha256(normalized_message_id.encode()).hexdigest()
    return f"canonical-mail-{digest[:32]}"


class MailingListRepository:
    """Persistence boundary; consumers never receive SQL or persistence-shaped rows."""

    def __init__(self, root: Path) -> None:
        self._state_root = state_root_for(root)
        try:
            self._database = RepositoryDatabase.initialize(self._state_root)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error
        self._artifacts = AcquisitionRepository(self._state_root / "acquisition")

    @property
    def artifacts(self) -> AcquisitionRepository:
        return self._artifacts

    def configure_source(self, source: MailingListSource) -> bool:
        """Register one immutable source in the shared governed-source authority."""
        if not source.archive_base_url.startswith("https://"):
            raise MailingListError("invalid_source", "archive URL must use HTTPS")
        with self._database.connect(read_only=True) as connection:
            list_owner = connection.execute(
                "SELECT source_id FROM mailing_list_sources WHERE list_id = ?",
                (source.list_id,),
            ).fetchone()
        if list_owner is not None and str(list_owner[0]) != source.source_id:
            raise MailingListError(
                "source_conflict",
                f"archive/list identity is already governed by source: {list_owner[0]}",
            )
        profile = SourceProfile(
            source.source_id,
            source.display_name,
            True,
            source.provider,
            {
                "archive_base_url": source.archive_base_url,
                "list_id": source.list_id,
            },
            {
                "repository_projection": "mailing-list",
                "transport": asdict(source.transport),
            },
        )
        try:
            self._artifacts.register_source(profile)
        except ConflictError as error:
            raise MailingListError("source_conflict", str(error)) from error
        except (ContractError, IntegrityError) as error:
            raise MailingListError("invalid_source", str(error)) from error
        payload = canonical_json(asdict(source))
        try:
            with self._database.transaction() as connection:
                prior = connection.execute(
                    "SELECT canonical_json FROM mailing_list_sources WHERE source_id = ?",
                    (source.source_id,),
                ).fetchone()
                if prior is not None:
                    if str(prior[0]) != payload:
                        raise MailingListError(
                            "source_conflict", "configured mailing-list source differs"
                        )
                    return False
                connection.execute(
                    "INSERT INTO mailing_list_sources VALUES (?,?,?,?,?)",
                    (source.source_id, source.list_id, source.display_name,
                     source.archive_base_url, payload),
                )
                self._database.advance_revision(connection)
            return True
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    def source(self, source_id: str) -> MailingListSource:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT source_id,list_id,display_name,archive_base_url,canonical_json "
                "FROM mailing_list_sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        if row is None:
            raise MailingListError("unknown_source", f"unknown mailing-list source: {source_id}")
        return self._source_from_row(row, self._artifacts.source(source_id))

    def sources(self) -> tuple[MailingListSource, ...]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT source_id,list_id,display_name,archive_base_url,canonical_json "
                "FROM mailing_list_sources ORDER BY display_name,source_id"
            ).fetchall()
        return tuple(
            self._source_from_row(row, self._artifacts.source(str(row[0]))) for row in rows
        )

    @staticmethod
    def _source_from_row(row: Any, governed: dict[str, Any]) -> MailingListSource:
        try:
            configuration = governed.get("configuration", {})
            policy = governed.get("policy", {})
            transport_value = policy.get("transport", {})
            # Compatibility for pre-v4 governed profiles. The mailing table is a
            # projection only; new profiles place every executable setting above.
            legacy = json.loads(str(row[4]))
            if not transport_value:
                transport_value = legacy.get("transport", {})
            transport = LoreTransportPolicy(**transport_value)
            return MailingListSource(
                str(row[0]),
                str(configuration.get("list_id", row[1])),
                str(governed.get("name", row[2])),
                str(configuration.get("archive_base_url", row[3])),
                str(governed.get("mechanism", legacy.get("provider", "lore-public-inbox"))),
                transport,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise MailingListError(
                "repository_failure", "mailing-list source policy is corrupt"
            ) from error

    def existing_artifact(self, source_id: str, external_id: str) -> str | None:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT artifact_id FROM mailing_list_messages "
                "WHERE source_id = ? AND external_message_id = ?",
                (source_id, external_id),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT artifact_id FROM mailing_list_run_items "
                    "WHERE source_id = ? AND external_message_id = ? "
                    "ORDER BY run_id LIMIT 1", (source_id, external_id)
                ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT artifact_id FROM artifact_observations "
                    "WHERE source_id = ? AND document_id = ? "
                    "ORDER BY observed_at,observation_id LIMIT 1",
                    (source_id, document_id(source_id, external_id)),
                ).fetchone()
        return str(row[0]) if row else None

    def has_retained_rfc822(self, source_id: str, external_id: str) -> bool:
        """Return whether this source already has successful RFC822 evidence."""
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT 1 FROM artifact_observations o JOIN artifacts a "
                "ON a.artifact_id=o.artifact_id WHERE o.source_id=? AND o.document_id=? "
                "AND a.media_type='message/rfc822' LIMIT 1",
                (
                    source_id,
                    document_id(source_id, normalize_message_id(external_id) or external_id),
                ),
            ).fetchone()
        return row is not None

    def canonical_message(self, external_id: str) -> dict[str, str] | None:
        """Resolve the corpus logical node and its compatibility representative."""
        normalized = normalize_message_id(external_id)
        if normalized is None:
            return None
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_message_id,normalized_message_id,artifact_id,document_id "
                "FROM canonical_mailing_list_messages WHERE normalized_message_id=?",
                (normalized,),
            ).fetchone()
        return dict(row) if row is not None else None

    def retain_message(
        self,
        source: MailingListSource,
        run_id: str,
        storage_external_id: str,
        parsed: ParsedMessage,
        raw: bytes,
        location: str,
        inclusion_reason: str,
        requested_at: str,
        fallback_archive_url: str | None = None,
    ) -> tuple[str, str, str, bool]:
        """Retain exact bytes once; return message/document/artifact identity and creation."""
        digest = hashlib.sha256(raw).hexdigest()
        expected_artifact = f"artifact-{digest}"
        normalized = normalize_message_id(storage_external_id)
        canonical = self.canonical_message(storage_external_id)
        with self._database.connect(read_only=True) as connection:
            source_existing = connection.execute(
                "SELECT i.artifact_id,i.document_id,i.canonical_message_id "
                "FROM mailing_list_run_items i JOIN artifacts a ON a.artifact_id=i.artifact_id "
                "WHERE i.source_id=? AND i.external_message_id=? "
                "AND a.media_type='message/rfc822' ORDER BY i.run_id LIMIT 1",
                (source.source_id, normalized or storage_external_id),
            ).fetchone()
            if source_existing is None:
                source_existing = connection.execute(
                    "SELECT o.artifact_id,o.document_id,NULL "
                    "FROM artifact_observations o JOIN artifacts a "
                    "ON a.artifact_id=o.artifact_id "
                    "WHERE o.source_id=? AND o.document_id=? "
                    "AND a.media_type='message/rfc822' "
                    "ORDER BY o.observed_at,o.observation_id LIMIT 1",
                    (source.source_id, document_id(
                        source.source_id, normalized or storage_external_id
                    )),
                ).fetchone()
        if source_existing is not None:
            if str(source_existing[0]) != expected_artifact:
                candidate_document_id, artifact_created = self._retain_conflict_candidate(
                    source, run_id, storage_external_id, parsed, raw, location,
                    inclusion_reason, requested_at, fallback_archive_url,
                )
                accepted = {
                    "canonical_message_id": (
                        str(source_existing[2]) if source_existing[2] is not None else
                        canonical_message_id(normalized or storage_external_id)
                    ),
                    "artifact_id": str(source_existing[0]),
                    "document_id": str(source_existing[1]),
                }
                conflict_id = self._record_message_conflict(
                    storage_external_id, expected_artifact, candidate_document_id,
                    source.source_id, run_id, accepted,
                )
                raise MailingListError(
                    "message_id_conflict",
                    "the same external Message-ID resolves to conflicting immutable bytes",
                    details={
                        "normalized_message_id": storage_external_id,
                        "canonical_artifact_id": str(source_existing[0]),
                        "candidate_artifact_id": expected_artifact,
                        "candidate_document_id": candidate_document_id,
                        "artifact_created": artifact_created,
                        "conflict_id": conflict_id,
                        "quarantined_candidate_retained": True,
                    },
                )
            return (
                message_key(source.source_id, storage_external_id),
                str(source_existing[1]),
                str(source_existing[0]),
                False,
            )
        doc_id = document_id(source.source_id, storage_external_id)
        candidate = CandidateDocument(
            f"candidate.{hashlib.sha256((run_id + storage_external_id).encode()).hexdigest()[:32]}",
            source.source_id,
            doc_id,
            DiscoveryProvenance(
                requested_at,
                "lore-selection",
                {"message_id": parsed.external_message_id or storage_external_id},
                (location,),
                {
                    "repository_projection": "mailing-list",
                    "list_id": source.list_id,
                    "subject": parsed.subject,
                    "sender": parsed.sender,
                    "message_date": parsed.message_date,
                    "immediate_parent_id": parsed.immediate_parent_id,
                    "inclusion_reason": inclusion_reason,
                    "run_id": run_id,
                    "parse_warnings": list(parsed.parse_warnings),
                    "cross_archive_fallback": fallback_archive_url is not None,
                    "fallback_archive_url": fallback_archive_url,
                },
            ),
        )
        attempt_digest = hashlib.sha256(f"{source.source_id}\0{digest}".encode()).hexdigest()
        attempt = f"attempt.mail.{attempt_digest[:32]}"
        try:
            receipt = self._artifacts.record_success(
                attempt,
                candidate,
                RetrievalResult(
                    raw,
                    "message/rfc822",
                    requested_at,
                    "lore-public-inbox",
                    {"message_id": parsed.external_message_id or storage_external_id},
                    {"lossless_archive_representation": True},
                ),
            )
        except (ConflictError, IntegrityError) as error:
            raise MailingListError("repository_failure", str(error)) from error
        return (
            message_key(source.source_id, storage_external_id),
            receipt.document_id,
            receipt.artifact_id,
            receipt.artifact_created,
        )

    def _retain_conflict_candidate(
        self, source: MailingListSource, run_id: str, external_id: str,
        parsed: ParsedMessage, raw: bytes, location: str, inclusion_reason: str,
        requested_at: str, fallback_archive_url: str | None,
    ) -> tuple[str, bool]:
        """Retain conflicting bytes under a stable non-canonical document identity."""
        digest = hashlib.sha256(raw).hexdigest()
        normalized = normalize_message_id(external_id)
        assert normalized is not None
        identity = hashlib.sha256(f"{normalized}\0{digest}".encode()).hexdigest()[:32]
        doc_id = f"mail-conflict.{identity}"
        with self._database.connect(read_only=True) as connection:
            prior = connection.execute(
                "SELECT 1 FROM artifact_observations WHERE artifact_id=? AND document_id=? "
                "LIMIT 1", (f"artifact-{digest}", doc_id),
            ).fetchone()
        if prior is not None:
            return doc_id, False
        candidate = CandidateDocument(
            f"candidate.mail-conflict.{identity}", source.source_id, doc_id,
            DiscoveryProvenance(
                requested_at, "lore-message-id-conflict", {"message_id": normalized},
                (location,), {
                    "repository_projection": "mailing-list-conflict-quarantine",
                    "list_id": source.list_id, "subject": parsed.subject,
                    "sender": parsed.sender, "message_date": parsed.message_date,
                    "inclusion_reason": inclusion_reason, "run_id": run_id,
                    "cross_archive_fallback": fallback_archive_url is not None,
                    "fallback_archive_url": fallback_archive_url,
                },
            ),
        )
        try:
            receipt = self._artifacts.record_success(
                f"attempt.mail-conflict.{identity}", candidate,
                RetrievalResult(
                    raw, "message/rfc822", requested_at, "lore-public-inbox",
                    {"message_id": normalized},
                    {"lossless_archive_representation": True, "quarantined": True},
                ),
            )
        except (ConflictError, IntegrityError) as error:
            raise MailingListError("repository_failure", str(error)) from error
        return receipt.document_id, receipt.artifact_created

    def _record_message_conflict(
        self, external_id: str, candidate_artifact_id: str, candidate_document_id: str,
        source_id: str, run_id: str, canonical: dict[str, str],
    ) -> str:
        """Persist actionable fail-closed diagnostics without mutating canonical content."""
        normalized = normalize_message_id(external_id)
        assert normalized is not None
        identity_payload = canonical_json({
            "normalized_message_id": normalized,
            "canonical_artifact_id": canonical["artifact_id"],
            "candidate_artifact_id": candidate_artifact_id,
        })
        payload = canonical_json({
            "reason": "message_id_byte_conflict",
            "normalized_message_id": normalized,
            "canonical_message_id": canonical["canonical_message_id"],
            "canonical_artifact_id": canonical["artifact_id"],
            "candidate_artifact_id": candidate_artifact_id,
            "candidate_document_id": candidate_document_id,
            "source_id": source_id,
            "status": "unresolved",
        })
        conflict_id = "mail-conflict-" + hashlib.sha256(
            identity_payload.encode()
        ).hexdigest()[:32]
        observed_at = utc_now()
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO mailing_list_message_conflicts "
                "(conflict_id,normalized_message_id,canonical_message_id,"
                "canonical_artifact_id,candidate_artifact_id,candidate_document_id,"
                "source_id,run_id,detected_at,last_detected_at,status,occurrence_count,"
                "canonical_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(conflict_id) DO UPDATE SET run_id=excluded.run_id,"
                "last_detected_at=excluded.last_detected_at,"
                "occurrence_count=mailing_list_message_conflicts.occurrence_count+1",
                (conflict_id, normalized, canonical["canonical_message_id"],
                 canonical["artifact_id"], candidate_artifact_id,
                 candidate_document_id, source_id, run_id, observed_at, observed_at,
                 "unresolved", 1, payload),
            )
            connection.execute(
                "INSERT INTO mailing_list_message_conflict_observations VALUES "
                "(?,?,?,?,?,?,?)",
                (run_id, conflict_id, normalized, candidate_artifact_id, source_id,
                 observed_at, "conflicted_skipped"),
            )
            self._database.advance_revision(connection)
        return conflict_id

    def unresolved_message_conflicts(
        self, *, run_id: str | None = None
    ) -> tuple[dict[str, Any], ...]:
        where = "WHERE c.status='unresolved'"
        parameters: tuple[object, ...] = ()
        if run_id is not None:
            where += " AND EXISTS (SELECT 1 FROM mailing_list_message_conflict_observations o " \
                "WHERE o.conflict_id=c.conflict_id AND o.run_id=?)"
            parameters = (run_id,)
        return self.rows(
            "SELECT c.conflict_id,c.normalized_message_id,c.canonical_message_id,"
            "c.canonical_artifact_id,c.candidate_artifact_id,c.candidate_document_id,"
            "c.source_id,c.detected_at,c.last_detected_at,c.status,c.occurrence_count "
            "FROM mailing_list_message_conflicts c " + where +
            " ORDER BY c.last_detected_at DESC,c.conflict_id", parameters,
        )

    def retain_unavailable_ancestor(
        self,
        source: MailingListSource,
        run_id: str,
        external_id: str,
        requested_at: str,
        attempts: list[dict[str, Any]],
    ) -> tuple[str, str, str, bool]:
        """Retain immutable evidence of a Message-ID confirmed absent from Lore."""
        payload = canonical_json({
            "record_type": "mailing_list_unavailable_ancestor",
            "source_id": source.source_id,
            "external_message_id": external_id,
            "availability": "confirmed_not_found",
            "attempts": attempts,
            "content_synthesized": False,
        }).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        expected_artifact = f"artifact-{digest}"
        with self._database.connect(read_only=True) as connection:
            prior = connection.execute(
                "SELECT i.artifact_id,i.document_id FROM mailing_list_run_items i "
                "JOIN artifacts a ON a.artifact_id=i.artifact_id "
                "WHERE i.source_id=? AND i.external_message_id=? "
                "AND a.media_type='application/vnd.rfi.mailing-list-tombstone+json' "
                "ORDER BY i.run_id LIMIT 1",
                (source.source_id, external_id),
            ).fetchone()
        existing = str(prior[0]) if prior is not None else None
        if existing is not None:
            if existing != expected_artifact:
                raise MailingListError(
                    "message_id_conflict",
                    "the unavailable ancestor identity conflicts with retained message content",
                )
            return (
                message_key(source.source_id, external_id),
                str(prior[1]),
                existing,
                False,
            )
        doc_id = document_id(source.source_id, external_id)
        candidate = CandidateDocument(
            f"candidate.{hashlib.sha256((run_id + external_id).encode()).hexdigest()[:32]}",
            source.source_id,
            doc_id,
            DiscoveryProvenance(
                requested_at,
                "lore-unavailable-ancestor",
                {"message_id": external_id},
                tuple(str(item["location"]) for item in attempts),
                {
                    "repository_projection": "mailing-list",
                    "list_id": source.list_id,
                    "subject": "[Unavailable Lore ancestor]",
                    "sender": "(message unavailable from Lore)",
                    "message_date": None,
                    "immediate_parent_id": None,
                    "inclusion_reason": "ancestor_context",
                    "run_id": run_id,
                    "is_tombstone": True,
                    "availability": "confirmed_not_found",
                    "http_statuses": [int(item["http_status"]) for item in attempts],
                    "content_synthesized": False,
                },
            ),
        )
        attempt_digest = hashlib.sha256(
            f"{source.source_id}\0tombstone\0{external_id}".encode()
        ).hexdigest()
        try:
            receipt = self._artifacts.record_success(
                f"attempt.mail-tombstone.{attempt_digest[:32]}",
                candidate,
                RetrievalResult(
                    payload,
                    "application/vnd.rfi.mailing-list-tombstone+json",
                    requested_at,
                    "lore-public-inbox",
                    {"message_id": external_id},
                    {
                        "confirmed_unavailable": True,
                        "http_statuses": [int(item["http_status"]) for item in attempts],
                        "lossless_archive_representation": False,
                    },
                ),
            )
        except (ConflictError, IntegrityError) as error:
            raise MailingListError("repository_failure", str(error)) from error
        return (
            message_key(source.source_id, external_id),
            receipt.document_id,
            receipt.artifact_id,
            receipt.artifact_created,
        )

    def publish(
        self,
        manifest: AcquisitionManifest,
        run_items: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        discussions: list[dict[str, Any]],
    ) -> None:
        """Atomically publish one durable manifest and a complete derived projection."""
        manifest_payload = canonical_json(asdict(manifest))
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO mailing_list_runs "
                    "(run_id,source_id,requested_at,status,seed_limit,context_limit,seed_count,"
                    "message_count,canonical_json,lifecycle_status,error_code,retryable) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        manifest.run_id, manifest.source_id, manifest.requested_at,
                        manifest.state.value, manifest.limits.seed_limit,
                        manifest.limits.context_limit, len(manifest.seed_ids),
                        manifest.message_count, manifest_payload, manifest.run_status.value,
                        manifest.error_code, int(manifest.retryable),
                    ),
                )
                for item in run_items:
                    normalized = normalize_message_id(item["external_message_id"])
                    canonical_id = None
                    canonical_created = False
                    if not item.get("is_tombstone", False) and normalized is not None:
                        existing = connection.execute(
                            "SELECT canonical_message_id,artifact_id,document_id "
                            "FROM canonical_mailing_list_messages "
                            "WHERE normalized_message_id=?", (normalized,),
                        ).fetchone()
                        if existing is None:
                            canonical_id = canonical_message_id(normalized)
                            payload = canonical_json({
                                "canonical_message_id": canonical_id,
                                "normalized_message_id": normalized,
                                "artifact_id": item["artifact_id"],
                                "document_id": item["document_id"],
                            })
                            connection.execute(
                                "INSERT INTO canonical_mailing_list_messages "
                                "VALUES (?,?,?,?,?,?)",
                                (canonical_id, normalized, item["artifact_id"],
                                 item["document_id"], manifest.requested_at, payload),
                            )
                            canonical_created = True
                        else:
                            canonical_id = str(existing[0])
                    connection.execute(
                        "INSERT INTO mailing_list_run_items "
                        "(run_id,source_id,external_message_id,artifact_id,document_id,"
                        "inclusion_reason,is_seed,connectivity_state,canonical_message_id,"
                        "observation_type,content_fetched,artifact_created,canonical_created) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            manifest.run_id, manifest.source_id, item["external_message_id"],
                            item["artifact_id"], item["document_id"], item["inclusion_reason"],
                            int(item["is_seed"]), item["connectivity_state"],
                            canonical_id,
                            "unavailable" if item.get("is_tombstone", False) else
                            "fetched" if item.get("content_fetched", False) else "reused",
                            int(item.get("content_fetched", False)),
                            int(item.get("artifact_created", False)),
                            int(canonical_created),
                        ),
                    )
                    if canonical_id is not None:
                        self._insert_relationship_claims(
                            connection, manifest, item, canonical_id
                        )
                self._replace_derived(connection, messages, discussions)
                self._database.advance_revision(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    @staticmethod
    def _insert_relationship_claims(
        connection: Any, manifest: AcquisitionManifest, item: dict[str, Any],
        child_canonical_id: str,
    ) -> None:
        """Persist bounded header assertions; canonical resolution remains derived."""
        parsed = item["parsed"]
        assertions: list[tuple[str, str, str, int | None]] = []
        if parsed.immediate_parent_id and len(parsed.in_reply_to_ids) == 1:
            assertions.append((
                parsed.raw_in_reply_to or parsed.immediate_parent_id,
                "immediate_parent", "header_in_reply_to", None,
            ))
        for ordinal, reference in enumerate(parsed.references):
            assertions.append((
                reference, "ancestor_reference", "header_references", ordinal,
            ))
        acquisition_path = (
            "cross_archive_fallback"
            if item.get("fallback_archive_url") is not None
            else "configured_archive"
        )
        for raw, role, evidence, ordinal in assertions:
            normalized = normalize_message_id(raw)
            if normalized is None:
                continue
            identity = canonical_json({
                "child": child_canonical_id, "raw": raw, "role": role,
                "evidence": evidence, "source_id": manifest.source_id,
                "artifact_id": item["artifact_id"], "run_id": manifest.run_id,
                "ordinal": ordinal,
            })
            claim_id = "mail-claim-" + hashlib.sha256(identity.encode()).hexdigest()[:32]
            payload = canonical_json({
                "claim_id": claim_id,
                "child_canonical_message_id": child_canonical_id,
                "referenced_raw": raw,
                "referenced_normalized_message_id": normalized,
                "claim_role": role, "evidence_type": evidence,
                "source_id": manifest.source_id,
                "child_external_message_id": item["external_message_id"],
                "child_artifact_id": item["artifact_id"],
                "observation_run_id": manifest.run_id,
                "reference_ordinal": ordinal,
                "acquisition_path": acquisition_path,
                "evidenced_delivery_source_id": None,
                "algorithm_id": None,
            })
            connection.execute(
                "INSERT OR IGNORE INTO mailing_list_relationship_claims VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (claim_id, child_canonical_id, raw, normalized, role, evidence,
                 manifest.source_id, item["external_message_id"], item["artifact_id"],
                 manifest.run_id, ordinal, acquisition_path, None, None,
                 manifest.requested_at, payload),
            )

    def record_failure(
        self,
        run_id: str,
        source_id: str,
        requested_at: str,
        criteria: SelectionCriteria,
        limits: AcquisitionLimits,
        error: MailingListError,
    ) -> None:
        """Durably record a failed bounded acquisition without publishing projections."""
        lifecycle = (
            AcquisitionRunStatus.RETRYABLE_FAILURE
            if error.retryable else AcquisitionRunStatus.TERMINAL_FAILURE
        )
        payload = canonical_json({
            "run_id": run_id,
            "source_id": source_id,
            "requested_at": requested_at,
            "criteria": asdict(criteria),
            "limits": asdict(limits),
            "run_status": lifecycle.value,
            "error_code": error.code,
            "retryable": error.retryable,
        })
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO mailing_list_runs "
                    "(run_id,source_id,requested_at,status,seed_limit,context_limit,seed_count,"
                    "message_count,canonical_json,lifecycle_status,error_code,retryable) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id, source_id, requested_at, ConnectivityState.INCOMPLETE.value,
                        limits.seed_limit, limits.context_limit, 0, 0, payload,
                        lifecycle.value, error.code, int(error.retryable),
                    ),
                )
                self._database.advance_revision(connection)
        except StorageError as storage_error:
            raise MailingListError("repository_failure", str(storage_error)) from storage_error

    def acquisition_runs(self, source_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.rows(
            "SELECT run_id,source_id,requested_at,lifecycle_status,status AS connectivity_state,"
            "seed_count,message_count,error_code,retryable,canonical_json FROM mailing_list_runs "
            "WHERE source_id=? ORDER BY requested_at,run_id",
            (source_id,),
        )
        result = []
        for row in rows:
            item = dict(row)
            manifest = json.loads(str(item.pop("canonical_json")))
            item["tombstone_count"] = len(manifest.get("tombstone_message_ids", ()))
            item["relationship_status"] = manifest.get("relationship_status", "complete")
            result.append(item)
        return tuple(result)

    def acquisition_coverage(self, source_id: str) -> tuple[dict[str, Any], ...]:
        """Return acquisition scope needed to derive coverage without a mutable cursor."""
        rows = self.rows(
            "SELECT run_id,requested_at,lifecycle_status,status AS connectivity_state,"
            "message_count,error_code,canonical_json FROM mailing_list_runs "
            "WHERE source_id=? ORDER BY requested_at,run_id",
            (source_id,),
        )
        result = []
        for row in rows:
            item = dict(row)
            payload = json.loads(str(item.pop("canonical_json")))
            item["criteria"] = payload.get("criteria", {})
            item["truncated"] = bool(payload.get("truncated", False))
            item["pagination_managed"] = "coverage_complete" in payload
            item["coverage_complete"] = bool(payload.get("coverage_complete", False))
            item["coverage_batch_id"] = payload.get("coverage_batch_id")
            result.append(item)
        return tuple(result)

    def relationship_resume_state(
        self, source_id: str, coverage_batch_id: str, discovery_offset: int
    ) -> dict[str, Any] | None:
        """Return the latest append-only continuation for one seed page."""
        rows = self.rows(
            "SELECT canonical_json FROM mailing_list_runs WHERE source_id=? "
            "ORDER BY requested_at DESC,run_id DESC",
            (source_id,),
        )
        for row in rows:
            manifest = json.loads(str(row["canonical_json"]))
            if (
                manifest.get("coverage_batch_id") == coverage_batch_id
                and int(manifest.get("discovery_offset", 0)) == discovery_offset
                and manifest.get("relationship_status") in {
                    "continuation_pending", "failed"
                }
            ):
                continuation = manifest.get("relationship_continuation")
                candidate = dict(continuation) if isinstance(continuation, dict) else None
                return (
                    candidate
                    if candidate is not None
                    and self._continuation_references_retained(source_id, candidate)
                    else None
                )
            if (
                manifest.get("coverage_batch_id") == coverage_batch_id
                and int(manifest.get("discovery_offset", 0)) == discovery_offset
            ):
                return None
        return None

    def _continuation_references_retained(
        self, source_id: str, continuation: dict[str, Any]
    ) -> bool:
        """Reject legacy frontiers that claim unavailable source observations."""
        required = {
            str(item) for item in continuation.get("acquired_ids", ())
        } | {
            str(item) for item in continuation.get("completed_reply_ids", ())
        } | {
            str(item.get("current"))
            for item in continuation.get("ancestry_stack", ())
            if isinstance(item, dict) and item.get("current")
        } | {
            str(item.get("message_id"))
            for item in continuation.get("reply_stack", ())
            if isinstance(item, dict) and item.get("message_id")
        }
        if not required:
            return True
        placeholders = ",".join("?" for _ in required)
        rows = self.rows(
            "SELECT external_message_id FROM mailing_list_messages WHERE source_id=? "
            f"AND external_message_id IN ({placeholders})",
            (source_id, *sorted(required)),
        )
        return {str(row["external_message_id"]) for row in rows} == required

    def coverage_batch_progress(
        self, source_id: str, coverage_batch_id: str
    ) -> tuple[dict[str, Any], ...]:
        """Expose page/run progress used to resume catch-up after process restart."""
        result = []
        for item in self.acquisition_coverage(source_id):
            if item.get("coverage_batch_id") != coverage_batch_id:
                continue
            run = self.acquisition_run_manifest(str(item["run_id"]))
            result.append(run)
        return tuple(result)

    def acquisition_run_manifest(self, run_id: str) -> dict[str, Any]:
        rows = self.rows(
            "SELECT canonical_json FROM mailing_list_runs WHERE run_id=?", (run_id,)
        )
        if not rows:
            raise MailingListError("unknown_run", "unknown mailing-list acquisition run")
        return dict(json.loads(str(rows[0]["canonical_json"])))

    def canonical_lineage(
        self, external_id: str, *, source_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """Derive bounded corpus lineage from durable observation assertions."""
        if not 1 <= limit <= 100:
            raise MailingListError("invalid_limit", "lineage limit must be between 1 and 100")
        normalized = normalize_message_id(external_id)
        canonical = self.canonical_message(normalized or external_id)
        if normalized is None or canonical is None:
            raise MailingListError("unknown_message", "unknown canonical mailing-list message")
        claim_where = ""
        parameters: tuple[Any, ...] = ()
        if source_id is not None:
            self.source(source_id)
            claim_where = " WHERE c.source_id=?"
            parameters = (source_id,)
        claims = self.rows(
            "SELECT c.*,p.canonical_message_id AS resolved_parent_canonical_id "
            "FROM mailing_list_relationship_claims c "
            "LEFT JOIN canonical_mailing_list_messages p "
            "ON p.normalized_message_id=c.referenced_normalized_message_id" +
            claim_where + " ORDER BY c.observed_at,c.claim_id", parameters,
        )
        immediate = [item for item in claims if item["claim_role"] == "immediate_parent"]
        adjacency: dict[str, set[str]] = {}
        for claim in immediate:
            parent = claim.get("resolved_parent_canonical_id")
            if parent is None:
                continue
            child = str(claim["child_canonical_message_id"])
            parent_id = str(parent)
            adjacency.setdefault(child, set()).add(parent_id)
            adjacency.setdefault(parent_id, set()).add(child)
        start = str(canonical["canonical_message_id"])
        queue = [start]
        visited: list[str] = []
        while queue and len(visited) < limit:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.append(current)
            queue.extend(sorted(adjacency.get(current, set()) - set(visited)))
        node_set = set(visited)
        node_placeholders = ",".join("?" for _ in visited)
        nodes = self.rows(
            "SELECT canonical_message_id,normalized_message_id,artifact_id,document_id "
            "FROM canonical_mailing_list_messages WHERE canonical_message_id IN "
            f"({node_placeholders}) "
            "ORDER BY normalized_message_id", tuple(visited),
        )
        observation_where = ""
        observation_params: tuple[Any, ...] = tuple(visited)
        if source_id is not None:
            observation_where = " AND m.source_id=?"
            observation_params += (source_id,)
        observations = self.rows(
            "SELECT m.canonical_message_id,m.message_key,m.source_id,m.external_message_id,"
            "m.artifact_id,m.document_id,dm.discussion_id "
            "FROM mailing_list_messages m LEFT JOIN mailing_list_discussion_members dm "
            "ON dm.message_key=m.message_key "
            f"WHERE m.canonical_message_id IN ({node_placeholders})" + observation_where +
            " ORDER BY m.canonical_message_id,m.source_id,m.message_key", observation_params,
        )
        observations_by_node: dict[str, list[dict[str, Any]]] = {}
        for item in observations:
            observations_by_node.setdefault(str(item["canonical_message_id"]), []).append(item)
        edges: dict[tuple[str, str], dict[str, Any]] = {}
        unresolved = []
        parents_by_child: dict[str, set[str]] = {}
        for claim in immediate:
            child = str(claim["child_canonical_message_id"])
            if child not in node_set:
                continue
            parent = claim.get("resolved_parent_canonical_id")
            evidence = {
                key: claim[key] for key in (
                    "claim_id", "source_id", "child_external_message_id",
                    "child_artifact_id", "observation_run_id", "evidence_type",
                    "referenced_raw", "referenced_normalized_message_id", "acquisition_path",
                )
            }
            if parent is None:
                unresolved.append({
                    "child_canonical_message_id": child,
                    "referenced_normalized_message_id": claim["referenced_normalized_message_id"],
                    "claim": evidence,
                })
                continue
            parent_id = str(parent)
            if parent_id not in node_set:
                continue
            parents_by_child.setdefault(child, set()).add(parent_id)
            edge = edges.setdefault((child, parent_id), {
                "child_canonical_message_id": child,
                "parent_canonical_message_id": parent_id,
                "claims": [],
            })
            edge["claims"].append(evidence)
        for node in nodes:
            node["observations"] = observations_by_node.get(
                str(node["canonical_message_id"]), []
            )
            node["immediate_parent_ambiguous"] = len(
                parents_by_child.get(str(node["canonical_message_id"]), set())
            ) > 1
        return {
            "start_canonical_message_id": start,
            "nodes": nodes,
            "edges": [edges[key] for key in sorted(edges)],
            "unresolved_boundaries": unresolved,
            "result_truncated": bool(queue),
            "source_filter": source_id,
        }

    def repair_cross_source_conflicts(
        self, source_id: str, *, historical_run_id: str
    ) -> dict[str, Any]:
        """Promote only deterministically proven historical cross-source observations."""
        source = self.source(source_id)
        conflicts = self.rows(
            "SELECT c.* FROM mailing_list_message_conflicts c "
            "WHERE c.source_id=? AND c.status='unresolved' AND EXISTS ("
            "SELECT 1 FROM mailing_list_message_conflict_observations o "
            "WHERE o.conflict_id=c.conflict_id AND o.run_id=?) ORDER BY c.conflict_id",
            (source_id, historical_run_id),
        )
        repaired: list[str] = []
        skipped: list[dict[str, str]] = []
        for conflict in conflicts:
            conflict_id = str(conflict["conflict_id"])
            normalized = str(conflict["normalized_message_id"])
            observations = self.rows(
                "SELECT candidate_artifact_id,source_id,outcome FROM "
                "mailing_list_message_conflict_observations "
                "WHERE conflict_id=? ORDER BY run_id", (conflict_id,),
            )
            reason = json.loads(str(conflict["canonical_json"])).get("reason")
            candidate_artifact = str(conflict["candidate_artifact_id"])
            raw = self.raw_for_artifact(candidate_artifact)
            parsed = parse_message(raw)
            representative_sources = self.rows(
                "SELECT DISTINCT i.source_id FROM mailing_list_run_items i "
                "WHERE i.canonical_message_id=? AND i.artifact_id=?",
                (conflict["canonical_message_id"], conflict["canonical_artifact_id"]),
            )
            predicates = {
                "recorded_candidate": bool(observations) and all(
                    str(item["candidate_artifact_id"]) == candidate_artifact
                    and str(item["source_id"]) == source_id
                    and str(item["outcome"]) == "conflicted_skipped"
                    for item in observations
                ),
                "parsed_identity": parsed.external_message_id == normalized,
                "source_absent": not self.has_retained_rfc822(source_id, normalized),
                "global_mismatch_only": reason == "message_id_byte_conflict",
                "representative_other_source": bool(representative_sources) and all(
                    str(item["source_id"]) != source_id for item in representative_sources
                ),
                "no_accepted_source_variant": not self.rows(
                    "SELECT 1 FROM mailing_list_run_items i JOIN artifacts a "
                    "ON a.artifact_id=i.artifact_id WHERE i.source_id=? "
                    "AND i.external_message_id=? AND a.media_type='message/rfc822' LIMIT 1",
                    (source_id, normalized),
                ),
            }
            failed = self._failed_repair_predicates(predicates)
            if failed:
                skipped.append({"conflict_id": conflict_id, "reason": ",".join(failed)})
                continue
            observed_at = str(conflict["detected_at"])
            repair_run_id = "mailrepair-" + hashlib.sha256(
                f"task045\0{conflict_id}\0{source_id}".encode()
            ).hexdigest()[:32]
            location = f"repair:task045:{conflict_id}"
            key, doc_id, artifact_id, artifact_created = self.retain_message(
                source, repair_run_id, normalized, parsed, raw, location,
                "relationship_context", observed_at,
            )
            del key
            canonical_id = str(conflict["canonical_message_id"])
            repair_manifest = AcquisitionManifest(
                repair_run_id, source_id, observed_at,
                SelectionCriteria(message_ids=(normalized,)),
                AcquisitionLimits(seed_limit=1, context_limit=1, descendant_depth=0),
                (normalized,), 1, 0, 0, {"relationship_context": 1},
                ConnectivityState.CONNECTED, False,
            )
            item = {
                "source_id": source_id, "external_message_id": normalized,
                "artifact_id": artifact_id, "document_id": doc_id,
                "inclusion_reason": "relationship_context", "is_seed": False,
                "connectivity_state": ConnectivityState.CONNECTED.value,
                "parsed": parsed, "fallback_archive_url": None,
                "content_fetched": False, "artifact_created": artifact_created,
                "is_tombstone": False,
            }
            with self._database.transaction() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM mailing_list_runs WHERE run_id=?", (repair_run_id,)
                ).fetchone()
                if exists is None:
                    payload = canonical_json({
                        **asdict(repair_manifest),
                        "repair_kind": "task045_cross_source_observation",
                        "historical_conflict_id": conflict_id,
                    })
                    connection.execute(
                        "INSERT INTO mailing_list_runs "
                        "(run_id,source_id,requested_at,status,seed_limit,context_limit,seed_count,"
                        "message_count,canonical_json,lifecycle_status,error_code,retryable) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (repair_run_id, source_id, observed_at, "connected", 1, 1, 1, 1,
                         payload, "succeeded", None, 0),
                    )
                    connection.execute(
                        "INSERT INTO mailing_list_run_items "
                        "(run_id,source_id,external_message_id,artifact_id,document_id,"
                        "inclusion_reason,is_seed,connectivity_state,canonical_message_id,"
                        "observation_type,content_fetched,artifact_created,canonical_created) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (repair_run_id, source_id, normalized, artifact_id, doc_id,
                         "relationship_context", 0, "connected", canonical_id,
                         "reused", 0, int(artifact_created), 0),
                    )
                    self._insert_relationship_claims(
                        connection, repair_manifest, item, canonical_id
                    )
                conflict_payload = json.loads(str(conflict["canonical_json"]))
                conflict_payload.update({
                    "status": "resolved",
                    "resolution_reason": "cross_source_observation",
                    "repair_run_id": repair_run_id,
                })
                connection.execute(
                    "UPDATE mailing_list_message_conflicts SET status='resolved',canonical_json=? "
                    "WHERE conflict_id=?", (canonical_json(conflict_payload), conflict_id),
                )
                self._database.advance_revision(connection)
            repaired.append(conflict_id)
        if repaired:
            from rfi.mailing_lists.service import derive_projection
            messages, discussions = derive_projection(self.parsed_retained_records())
            self.replace_derived(messages, discussions)
        return {
            "source_id": source_id, "historical_run_id": historical_run_id,
            "eligible": len(repaired),
            "repaired": repaired, "skipped": skipped,
            "still_unresolved": len(self.unresolved_message_conflicts()),
            "result": "PASS",
        }

    @staticmethod
    def _failed_repair_predicates(predicates: dict[str, bool]) -> list[str]:
        """Return deterministic TASK-045 eligibility failures in stable order."""
        required = (
            "recorded_candidate",
            "parsed_identity",
            "source_absent",
            "global_mismatch_only",
            "representative_other_source",
            "no_accepted_source_variant",
        )
        return sorted(name for name in required if not predicates.get(name, False))

    def replace_derived(
        self, messages: list[dict[str, Any]], discussions: list[dict[str, Any]]
    ) -> None:
        try:
            with self._database.transaction() as connection:
                self._replace_derived(connection, messages, discussions)
                self._database.advance_revision(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    @staticmethod
    def _replace_derived(connection: Any, messages: list[dict[str, Any]],
                         discussions: list[dict[str, Any]]) -> None:
        connection.execute("DELETE FROM mailing_list_discussion_members")
        connection.execute("DELETE FROM mailing_list_discussions")
        connection.execute("DELETE FROM mailing_list_relationships")
        connection.execute("DELETE FROM mailing_list_messages")
        for item in messages:
            connection.execute(
                "INSERT INTO mailing_list_messages "
                "(message_key,source_id,external_message_id,artifact_id,document_id,subject,"
                "normalized_subject,sender,message_date,text_content,connectivity_state,"
                "canonical_message_id,canonical_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["message_key"], item["source_id"], item["external_message_id"],
                    item["artifact_id"], item["document_id"], item["subject"],
                    item["normalized_subject"], item["sender"], item["message_date"],
                    item["text_content"], item["connectivity_state"],
                    item["canonical_message_id"],
                    canonical_json(item["canonical"]),
                ),
            )
        for item in messages:
            if item["parent_external_message_id"]:
                connection.execute(
                    "INSERT INTO mailing_list_relationships VALUES (?,?,?,?,?)",
                    (
                        item["message_key"], item["parent_external_message_id"],
                        item["parent_message_key"], "header",
                        "direct" if item["parent_message_key"] else "unresolved",
                    ),
                )
        for discussion in discussions:
            connection.execute(
                "INSERT INTO mailing_list_discussions VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    discussion["discussion_id"], discussion["source_id"],
                    discussion["root_message_key"], discussion["connectivity_state"],
                    int(discussion["descendant_truncated"]), len(discussion["members"]),
                    discussion["first_message_at"], discussion["last_message_at"],
                    canonical_json(discussion["canonical"]),
                ),
            )
            for key, depth in discussion["members"]:
                connection.execute(
                    "INSERT INTO mailing_list_discussion_members VALUES (?,?,?)",
                    (discussion["discussion_id"], key, depth),
                )

    def retained_records(self) -> list[dict[str, Any]]:
        """Return durable acquisition facts needed for an offline derived-state rebuild."""
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT i.source_id,i.external_message_id,i.artifact_id,i.document_id,"
                "i.connectivity_state,i.inclusion_reason,i.is_seed,o.canonical_json,"
                "r.canonical_json "
                "FROM mailing_list_run_items i JOIN artifact_observations o "
                "ON o.artifact_id=i.artifact_id AND o.document_id=i.document_id "
                "JOIN mailing_list_runs r ON r.run_id=i.run_id "
                "ORDER BY i.source_id,i.external_message_id,i.run_id"
            ).fetchall()
        records_by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            observation = json.loads(str(row[7]))
            manifest = json.loads(str(row[8]))
            identity = tuple(row[index] for index in range(7))
            record = records_by_identity.setdefault(identity, {
                "source_id": str(row[0]), "external_message_id": str(row[1]),
                "artifact_id": str(row[2]), "document_id": str(row[3]),
                "connectivity_state": str(row[4]), "inclusion_reason": str(row[5]),
                "is_seed": bool(row[6]), "observation": observation,
            })
            record["descendant_policy_limited"] = bool(
                record.get("descendant_policy_limited", False)
                or manifest.get("descendant_policy_limited", False)
            )
        return list(records_by_identity.values())

    def raw_for_artifact(self, artifact_id: str) -> bytes:
        return self._artifacts.read_artifact(artifact_id)

    def parsed_retained_records(self) -> list[dict[str, Any]]:
        records = self.retained_records()
        for record in records:
            metadata = record["observation"].get("candidate", {}).get(
                "provenance", {}
            ).get("metadata", {})
            record["is_tombstone"] = bool(metadata.get("is_tombstone", False))
            record["fallback_archive_url"] = metadata.get("fallback_archive_url")
            record["unavailable_details"] = {
                "availability": metadata.get("availability"),
                "http_statuses": metadata.get("http_statuses", []),
                "locations": record["observation"].get("candidate", {}).get(
                    "provenance", {}
                ).get("locations", []),
            } if record["is_tombstone"] else None
            record["parsed"] = (
                unavailable_ancestor(record["external_message_id"])
                if record["is_tombstone"]
                else parse_message(self.raw_for_artifact(record["artifact_id"]))
            )
        return records

    def rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Private parameterized read helper used only by the repository query service."""
        try:
            with self._database.connect(read_only=True) as connection:
                return [dict(row) for row in connection.execute(query, parameters).fetchall()]
        except Exception as error:
            raise MailingListError(
                "repository_read_failure", "mailing-list state cannot be read"
            ) from error

    def delete_derived_for_rebuild(self) -> None:
        """Delete only reproducible indexes; immutable evidence and manifests remain."""
        try:
            with self._database.transaction() as connection:
                self._replace_derived(connection, [], [])
                self._database.advance_revision(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    def require_derived(self) -> None:
        """Fail explicitly when retained evidence exists but its query projection is absent."""
        counts = self.rows(
            "SELECT (SELECT count(*) FROM mailing_list_run_items) AS retained, "
            "(SELECT count(*) FROM mailing_list_messages) AS messages"
        )[0]
        if int(counts["retained"]) and not int(counts["messages"]):
            raise MailingListError(
                "derived_state_absent",
                "mailing-list query state is absent; run the offline rebuild command",
            )

    # ---- Process Local Fetch Queue durable operator history ----

    FETCH_HISTORY_LIMIT = 50
    FETCH_EVENT_LIMIT = 200

    def record_fetch_history(
        self, *, stream_id: str, stream_name: str, state: str, message: str,
        queued_at: str | None, started_at: str | None, finished_at: str,
        windows_completed: int = 0, result: dict[str, Any] | None = None,
    ) -> None:
        """Persist one terminal fetch-job summary for operator scrollback."""
        payload = canonical_json(result) if result is not None else None
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO mailing_list_fetch_history "
                    "(stream_id, stream_name, state, message, queued_at, started_at, "
                    "finished_at, windows_completed, result_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (stream_id, stream_name, state, message, queued_at, started_at,
                     finished_at, windows_completed, payload),
                )
                self._prune_fetch_history(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    def record_fetch_event(
        self, *, sequence: int, occurred_at: str, event: str,
        stream_id: str | None, stream_name: str | None, message: str,
    ) -> None:
        """Persist one queue event for operator scrollback."""
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO mailing_list_fetch_events "
                    "(sequence, occurred_at, event, stream_id, stream_name, message) "
                    "VALUES (?,?,?,?,?,?)",
                    (sequence, occurred_at, event, stream_id, stream_name, message),
                )
                self._prune_fetch_events(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

    def fetch_history(self) -> tuple[dict[str, Any], ...]:
        """Return terminal fetch summaries newest-first, bounded by retention."""
        try:
            with self._database.connect(read_only=True) as connection:
                rows = connection.execute(
                    "SELECT stream_id, stream_name, state, message, queued_at, "
                    "started_at, finished_at, windows_completed, result_json "
                    "FROM mailing_list_fetch_history "
                    "ORDER BY finished_at DESC, history_id DESC "
                    f"LIMIT {self.FETCH_HISTORY_LIMIT}"
                ).fetchall()
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error
        return tuple(self._fetch_history_row(row) for row in rows)

    def fetch_events(self) -> tuple[dict[str, Any], ...]:
        """Return bounded queue events newest-first for operator scrollback."""
        try:
            with self._database.connect(read_only=True) as connection:
                rows = connection.execute(
                    "SELECT sequence, occurred_at, event, stream_id, stream_name, message "
                    "FROM mailing_list_fetch_events "
                    "ORDER BY sequence DESC, event_id DESC "
                    f"LIMIT {self.FETCH_EVENT_LIMIT}"
                ).fetchall()
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error
        return tuple(self._fetch_event_row(row) for row in rows)

    @staticmethod
    def _fetch_history_row(row: sqlite3.Row) -> dict[str, Any]:
        result_json = row["result_json"]
        return {
            "stream_id": row["stream_id"],
            "stream_name": row["stream_name"],
            "state": row["state"],
            "message": row["message"],
            "queued_at": row["queued_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "windows_completed": row["windows_completed"],
            "result": json.loads(result_json) if result_json else None,
        }

    @staticmethod
    def _fetch_event_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": row["sequence"],
            "occurred_at": row["occurred_at"],
            "event": row["event"],
            "stream_id": row["stream_id"],
            "stream_name": row["stream_name"],
            "message": row["message"],
        }

    def _prune_fetch_history(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "DELETE FROM mailing_list_fetch_history WHERE history_id NOT IN ("
            "  SELECT history_id FROM mailing_list_fetch_history "
            f"  ORDER BY finished_at DESC, history_id DESC LIMIT {self.FETCH_HISTORY_LIMIT}"
            ")"
        )

    def _prune_fetch_events(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "DELETE FROM mailing_list_fetch_events WHERE event_id NOT IN ("
            "  SELECT event_id FROM mailing_list_fetch_events "
            f"  ORDER BY sequence DESC, event_id DESC LIMIT {self.FETCH_EVENT_LIMIT}"
            ")"
        )

    def validate_connectivity(self) -> dict[str, int | str]:
        """Prove every connected/truncated member has one complete acyclic path to root."""
        self.require_derived()
        messages = {
            str(row["message_key"]): row
            for row in self.rows(
                "SELECT m.message_key,m.connectivity_state,r.parent_message_key "
                "FROM mailing_list_messages m LEFT JOIN mailing_list_relationships r "
                "ON r.child_message_key=m.message_key"
            )
        }
        memberships = self.rows(
            "SELECT dm.discussion_id,dm.message_key,dm.depth,d.root_message_key "
            "FROM mailing_list_discussion_members dm JOIN mailing_list_discussions d "
            "ON d.discussion_id=dm.discussion_id"
        )
        membership_by_message = {str(row["message_key"]): row for row in memberships}
        paths = 0
        for key, item in messages.items():
            membership = membership_by_message.get(key)
            if membership is None:
                if item["connectivity_state"] in {"connected", "truncated"}:
                    raise MailingListError(
                        "connectivity_violation",
                        "connected message has no discussion membership",
                    )
                continue
            seen: set[str] = set()
            current = key
            edges = 0
            while current != membership["root_message_key"]:
                if current in seen:
                    raise MailingListError(
                        "connectivity_violation", "discussion reply path contains a cycle"
                    )
                seen.add(current)
                parent = messages[current]["parent_message_key"]
                if parent is None or str(parent) not in messages:
                    raise MailingListError(
                        "connectivity_violation", "discussion reply path has a missing connector"
                    )
                current = str(parent)
                edges += 1
            if edges != int(membership["depth"]):
                raise MailingListError(
                    "connectivity_violation", "discussion path depth is inconsistent"
                )
            paths += 1
        return {
            "messages": len(messages),
            "discussions": len({row["discussion_id"] for row in memberships}),
            "validated_paths": paths, "result": "PASS",
        }
