"""SQLite-backed mailing-list state and immutable evidence coordination."""

from __future__ import annotations

import hashlib
import json
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
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json


def message_key(source_id: str, external_message_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{external_message_id}".encode()).hexdigest()
    return f"message-{digest[:32]}"


def document_id(source_id: str, external_message_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{external_message_id}".encode()).hexdigest()
    return f"mail.{digest[:32]}"


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
        existing = self.existing_artifact(source.source_id, storage_external_id)
        if existing is not None:
            if existing != expected_artifact:
                raise MailingListError(
                    "message_id_conflict",
                    "the same external Message-ID resolves to conflicting immutable bytes",
                )
            return (
                message_key(source.source_id, storage_external_id),
                document_id(source.source_id, storage_external_id),
                existing,
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
                    connection.execute(
                        "INSERT INTO mailing_list_run_items VALUES (?,?,?,?,?,?,?,?)",
                        (
                            manifest.run_id, manifest.source_id, item["external_message_id"],
                            item["artifact_id"], item["document_id"], item["inclusion_reason"],
                            int(item["is_seed"]), item["connectivity_state"],
                        ),
                    )
                self._replace_derived(connection, messages, discussions)
                self._database.advance_revision(connection)
        except StorageError as error:
            raise MailingListError("repository_failure", str(error)) from error

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
        return tuple(self.rows(
            "SELECT run_id,source_id,requested_at,lifecycle_status,status AS connectivity_state,"
            "seed_count,message_count,error_code,retryable FROM mailing_list_runs "
            "WHERE source_id=? ORDER BY requested_at,run_id",
            (source_id,),
        ))

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
                "INSERT INTO mailing_list_messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["message_key"], item["source_id"], item["external_message_id"],
                    item["artifact_id"], item["document_id"], item["subject"],
                    item["normalized_subject"], item["sender"], item["message_date"],
                    item["text_content"], item["connectivity_state"],
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
                "i.connectivity_state,i.inclusion_reason,i.is_seed,o.canonical_json "
                "FROM mailing_list_run_items i JOIN artifact_observations o "
                "ON o.artifact_id=i.artifact_id AND o.document_id=i.document_id "
                "GROUP BY i.source_id,i.external_message_id,i.artifact_id,i.document_id,"
                "i.connectivity_state,i.inclusion_reason,i.is_seed "
                "ORDER BY i.source_id,i.external_message_id"
            ).fetchall()
        records = []
        for row in rows:
            observation = json.loads(str(row[7]))
            records.append({
                "source_id": str(row[0]), "external_message_id": str(row[1]),
                "artifact_id": str(row[2]), "document_id": str(row[3]),
                "connectivity_state": str(row[4]), "inclusion_reason": str(row[5]),
                "is_seed": bool(row[6]), "observation": observation,
            })
        return records

    def raw_for_artifact(self, artifact_id: str) -> bytes:
        return self._artifacts.read_artifact(artifact_id)

    def parsed_retained_records(self) -> list[dict[str, Any]]:
        records = self.retained_records()
        for record in records:
            record["parsed"] = parse_message(self.raw_for_artifact(record["artifact_id"]))
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
