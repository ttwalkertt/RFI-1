"""Repository-owned normalized query service over authoritative acquisition records."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from rfi.acquisition import AcquisitionRepository
from rfi.acquisition.contracts import IntegrityError
from rfi.artifacts.contracts import (
    ArtifactContent,
    ArtifactDetail,
    ArtifactOrder,
    ArtifactPage,
    ArtifactQuery,
    ArtifactQueryError,
    ArtifactSummary,
    ProvenanceLocation,
    SourceEffectiveOrder,
)
from rfi.firms.contracts import FirmCatalog
from rfi.source_profiles.contracts import AcquisitionTemplate

_MAX_LIMIT = 100


class ArtifactQueryService:
    """Stable read surface; callers never traverse repository persistence."""

    def __init__(
        self,
        repository: AcquisitionRepository,
        firms: FirmCatalog,
        template: AcquisitionTemplate,
    ) -> None:
        self._repository = repository
        self._firms = firms
        self._template = template
        self._artifacts = {item.artifact_id: item for item in template.artifacts}
        self._families = {item.category_id: item for item in template.categories}

    def query(self, query: ArtifactQuery) -> ArtifactPage:
        """Return a deterministic page bound to one authoritative-state digest."""
        self._validate_query(query)
        snapshot, summaries = self._snapshot_summaries()
        filtered = [item for item in summaries if self._matches(item, query)]
        filtered.sort(key=self._sort_key, reverse=query.order == ArtifactOrder.NEWEST)
        offset = self._cursor_offset(query, snapshot)
        page = tuple(filtered[offset : offset + query.limit])
        next_offset = offset + len(page)
        next_cursor = None
        if next_offset < len(filtered):
            next_cursor = self._encode_cursor(snapshot, self._fingerprint(query), next_offset)
        return ArtifactPage(page, next_cursor, snapshot)

    def latest(self, firm_id: str, canonical_artifact_id: str) -> ArtifactSummary | None:
        """Project newest durable state through the ordinary query contract."""
        page = self.query(
            ArtifactQuery(
                firm_ids=(firm_id,),
                canonical_artifact_ids=(canonical_artifact_id,),
                order=ArtifactOrder.NEWEST,
                limit=1,
            )
        )
        return page.items[0] if page.items else None

    def oldest(self, firm_id: str, canonical_artifact_id: str) -> ArtifactSummary | None:
        """Project oldest durable state through the ordinary query contract."""
        page = self.query(
            ArtifactQuery(
                firm_ids=(firm_id,),
                canonical_artifact_ids=(canonical_artifact_id,),
                order=ArtifactOrder.OLDEST,
                limit=1,
            )
        )
        return page.items[0] if page.items else None

    def firms(self) -> tuple[dict[str, Any], ...]:
        """List only firms with durable artifact-document counts."""
        _, summaries = self._snapshot_summaries()
        counts: dict[str, int] = {}
        names: dict[str, str] = {}
        for item in summaries:
            counts[item.firm_id] = counts.get(item.firm_id, 0) + 1
            names[item.firm_id] = item.firm_name
        return tuple(
            {"firm_id": key, "firm_name": names[key], "durable_artifact_count": counts[key]}
            for key in sorted(counts, key=lambda value: (names[value].casefold(), value))
        )

    def families(self, firm_id: str) -> tuple[dict[str, Any], ...]:
        """List canonical families represented by durable content for one firm."""
        items = self.query(ArtifactQuery(firm_ids=(firm_id,), limit=_MAX_LIMIT)).items
        if not items and not self._firm_exists(firm_id):
            raise ArtifactQueryError("unknown_firm", f"unknown firm: {firm_id}")
        grouped: dict[str, set[str]] = {}
        labels: dict[str, str] = {}
        for item in self._all_for_firm(firm_id):
            grouped.setdefault(item.family_id, set()).add(item.document_id)
            labels[item.family_id] = item.family_label
        return tuple(
            {
                "family_id": family_id,
                "family_label": labels[family_id],
                "durable_artifact_count": len(grouped[family_id]),
            }
            for family_id in sorted(grouped, key=lambda value: self._families[value].order)
        )

    def canonical_types(self, firm_id: str, family_id: str) -> tuple[dict[str, Any], ...]:
        """List represented canonical types, never provider form taxonomy."""
        if family_id not in self._families:
            raise ArtifactQueryError(
                "unknown_artifact_family", f"unknown artifact family: {family_id}"
            )
        grouped: dict[str, set[str]] = {}
        labels: dict[str, str] = {}
        for item in self._all_for_firm(firm_id):
            if item.family_id == family_id:
                grouped.setdefault(item.canonical_artifact_id, set()).add(item.document_id)
                labels[item.canonical_artifact_id] = item.canonical_artifact_label
        return tuple(
            {
                "canonical_artifact_id": artifact_id,
                "canonical_artifact_label": labels[artifact_id],
                "durable_artifact_count": len(grouped[artifact_id]),
            }
            for artifact_id in sorted(grouped, key=lambda value: self._artifacts[value].order)
        )

    def detail(self, document_id: str) -> ArtifactDetail:
        """Resolve one logical repository document to its current immutable stored artifact."""
        _, summaries, records, sources, metadata = self._state()
        summary = next((item for item in summaries if item.document_id == document_id), None)
        if summary is None:
            raise ArtifactQueryError("unknown_document_id", f"unknown document ID: {document_id}")
        matching = [
            item
            for item in records
            if item.get("record_type") == "retrieval_attempt"
            and item.get("outcome") == "success"
            and item.get("document_id") == document_id
            and item.get("artifact_id") == summary.artifact_id
        ]
        record = max(
            matching,
            key=lambda item: (str(item.get("occurred_at", "")), item["attempt_id"]),
        )
        source = sources.get(str(record["source_id"]), {})
        discovery = record.get("candidate", {}).get("provenance", {})
        locations = tuple(
            ProvenanceLocation(
                str(value),
                "original_artifact"
                if index == len(discovery.get("locations", [])) - 1
                else "discovery",
            )
            for index, value in enumerate(discovery.get("locations", []))
            if isinstance(value, str) and value
        )
        original = next(
            (
                item.location
                for item in reversed(locations)
                if item.location.startswith(("https://", "http://"))
            ),
            None,
        )
        artifact_meta = metadata.get(summary.artifact_id, {})
        return ArtifactDetail(
            summary,
            locations,
            self._text(discovery.get("metadata", {}).get("adapter_id"))
            or self._text(source.get("policy", {}).get("retrieval_adapter_id")),
            str(record.get("mechanism", "")),
            self._text(source.get("policy", {}).get("source_profile_revision_id")),
            str(record.get("candidate_id", "")),
            str(record.get("source_id", "")),
            "verified" if artifact_meta else "unavailable",
            original is not None,
            original,
            dict(discovery.get("metadata", {})),
        )

    def content(self, document_id: str) -> ArtifactContent:
        """Return exact stored bytes after repository-owned integrity verification."""
        detail = self.detail(document_id)
        try:
            content = self._repository.read_artifact(detail.summary.artifact_id)
        except IntegrityError as error:
            code = "checksum_mismatch" if "mismatch" in str(error) else "missing_stored_content"
            raise ArtifactQueryError(
                code, "stored artifact content is unavailable or corrupt"
            ) from error
        return ArtifactContent(
            document_id,
            detail.summary.artifact_id,
            content,
            detail.summary.media_type,
            detail.summary.checksum_sha256,
        )

    def _snapshot_summaries(self) -> tuple[str, tuple[ArtifactSummary, ...]]:
        snapshot, summaries, _, _, _ = self._state()
        return snapshot, summaries

    def _state(
        self,
    ) -> tuple[
        str,
        tuple[ArtifactSummary, ...],
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        try:
            records = self._repository.history()
            source_records = self._repository.sources()
            artifact_records = self._repository.artifact_metadata()
        except IntegrityError as error:
            raise ArtifactQueryError(
                "repository_read_failure", "repository state cannot be read"
            ) from error
        snapshot_bytes = json.dumps(
            {"sources": source_records, "records": records, "artifacts": artifact_records},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        snapshot = hashlib.sha256(snapshot_bytes).hexdigest()
        sources = {str(item["source_id"]): item for item in source_records}
        metadata = {str(item["artifact_id"]): item for item in artifact_records}
        latest_by_document: dict[str, dict[str, Any]] = {}
        for record in records:
            if (
                record.get("record_type") != "retrieval_attempt"
                or record.get("outcome") != "success"
            ):
                continue
            document_id = str(record.get("document_id", ""))
            prior = latest_by_document.get(document_id)
            version_key = (
                str(record.get("occurred_at", "")),
                str(record.get("artifact_id", "")),
                str(record.get("attempt_id", "")),
            )
            if prior is None or version_key > (
                str(prior.get("occurred_at", "")),
                str(prior.get("artifact_id", "")),
                str(prior.get("attempt_id", "")),
            ):
                latest_by_document[document_id] = record
        summaries = tuple(
            self._summary(record, sources.get(str(record.get("source_id")), {}), metadata)
            for record in latest_by_document.values()
        )
        return snapshot, summaries, records, sources, metadata

    def _summary(
        self,
        record: dict[str, Any],
        source: dict[str, Any],
        metadata: dict[str, dict[str, Any]],
    ) -> ArtifactSummary:
        policy = source.get("policy", {})
        firm_id = str(policy.get("firm_id", "unknown"))
        artifact_id = str(policy.get("artifact_id", "unknown"))
        if artifact_id not in self._artifacts:
            raise ArtifactQueryError(
                "unknown_canonical_artifact",
                f"repository source references unknown canonical artifact: {artifact_id}",
            )
        canonical = self._artifacts[artifact_id]
        family = self._families[canonical.category_id]
        discovery = record.get("candidate", {}).get("provenance", {})
        discovery_metadata = discovery.get("metadata", {})
        provider_ids = {
            str(key): str(value)
            for key, value in discovery.get("provider_identifiers", {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        provider_ids.update(
            {
                str(key): str(value)
                for key, value in record.get("retrieval_provider_identifiers", {}).items()
                if isinstance(key, str) and isinstance(value, str)
            }
        )
        effective_value, basis = self._effective(discovery_metadata, discovery, record)
        secondary = str(
            discovery_metadata.get("accession_number")
            or provider_ids.get("sec_accession")
            or record.get("candidate_id", "")
        )
        repo_artifact_id = str(record.get("artifact_id", ""))
        artifact_meta = metadata.get(repo_artifact_id, {})
        try:
            firm_name = self._firms.get(firm_id).canonical_name
        except Exception:
            firm_name = firm_id
        filing_date = self._text(discovery_metadata.get("filing_date")) or self._text(
            discovery_metadata.get("publication_date")
        )
        period_date = self._text(discovery_metadata.get("period_of_report"))
        return ArtifactSummary(
            str(record["document_id"]), repo_artifact_id, firm_id, firm_name,
            family.category_id, family.label, canonical.artifact_id, canonical.label,
            f"{canonical.short_name} · {period_date or filing_date or effective_value[:10]}",
            SourceEffectiveOrder(
                effective_value,
                basis,
                secondary,
                f"{record['document_id']}:{repo_artifact_id}",
            ),
            filing_date, period_date,
            self._text(discovery_metadata.get("provider")) or provider_ids.get("provider"),
            self._text(discovery_metadata.get("form_type")), provider_ids, "durable",
            str(record.get("occurred_at", "")), str(artifact_meta.get("sha256", "")),
            str(artifact_meta.get("media_type", "application/octet-stream")),
            int(artifact_meta.get("size", 0)),
            bool(artifact_meta),
        )

    @staticmethod
    def _effective(
        metadata: dict[str, Any],
        discovery: dict[str, Any],
        record: dict[str, Any],
    ) -> tuple[str, str]:
        candidates = (
            ("acceptance_datetime", metadata.get("acceptance_datetime")),
            ("publication_datetime", metadata.get("publication_datetime")),
            ("filing_date", metadata.get("filing_date")),
            ("publication_date", metadata.get("publication_date")),
            ("source_observation", discovery.get("discovered_at")),
            ("retrieval_time_fallback", record.get("occurred_at")),
        )
        for basis, raw in candidates:
            if isinstance(raw, str) and raw:
                try:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        parsed = datetime.combine(date.fromisoformat(raw), datetime.min.time(), UTC)
                    except ValueError:
                        continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z"), basis
        raise ArtifactQueryError(
            "malformed_provenance",
            "artifact has no valid source-effective or fallback time",
        )

    @staticmethod
    def _sort_key(item: ArtifactSummary) -> tuple[str, str, str, str]:
        order = item.source_effective
        return order.value, order.secondary, item.document_id, item.artifact_id

    @staticmethod
    def _matches(item: ArtifactSummary, query: ArtifactQuery) -> bool:
        effective_date = item.source_effective.value[:10]
        return (
            (not query.firm_ids or item.firm_id in query.firm_ids)
            and (not query.family_ids or item.family_id in query.family_ids)
            and (
                not query.canonical_artifact_ids
                or item.canonical_artifact_id in query.canonical_artifact_ids
            )
            and (not query.provider_ids or item.provider in query.provider_ids)
            and item.durable_status in query.durable_statuses
            and (
                query.source_effective_from is None
                or effective_date >= query.source_effective_from
            )
            and (
                query.source_effective_through is None
                or effective_date <= query.source_effective_through
            )
        )

    def _validate_query(self, query: ArtifactQuery) -> None:
        if isinstance(query.limit, bool) or not 1 <= query.limit <= _MAX_LIMIT:
            raise ArtifactQueryError("invalid_query", f"limit must be between 1 and {_MAX_LIMIT}")
        if any(value not in self._families for value in query.family_ids):
            raise ArtifactQueryError(
                "unknown_artifact_family", "query references an unknown artifact family"
            )
        if any(value not in self._artifacts for value in query.canonical_artifact_ids):
            raise ArtifactQueryError(
                "unknown_canonical_artifact",
                "query references an unknown canonical artifact",
            )
        if set(query.durable_statuses) - {"durable"}:
            raise ArtifactQueryError(
                "unsupported_filter",
                "only durable repository status is currently supported",
            )
        for value in (query.source_effective_from, query.source_effective_through):
            if value is not None:
                try:
                    date.fromisoformat(value)
                except ValueError as error:
                    raise ArtifactQueryError(
                        "invalid_query", "date bounds must use YYYY-MM-DD"
                    ) from error
        if (
            query.source_effective_from
            and query.source_effective_through
            and query.source_effective_from > query.source_effective_through
        ):
            raise ArtifactQueryError("invalid_query", "source-effective date interval is reversed")

    def _all_for_firm(self, firm_id: str) -> tuple[ArtifactSummary, ...]:
        return self.query(ArtifactQuery(firm_ids=(firm_id,), limit=_MAX_LIMIT)).items

    def _firm_exists(self, firm_id: str) -> bool:
        try:
            self._firms.get(firm_id)
            return True
        except Exception:
            return False

    @staticmethod
    def _text(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _cursor_offset(self, query: ArtifactQuery, snapshot: str) -> int:
        if not query.cursor:
            return 0
        try:
            payload = json.loads(base64.urlsafe_b64decode(query.cursor + "===").decode())
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactQueryError("invalid_cursor", "pagination cursor is malformed") from error
        if payload.get("snapshot") != snapshot:
            raise ArtifactQueryError("stale_cursor", "repository changed; restart pagination")
        if payload.get("query") != self._fingerprint(query):
            raise ArtifactQueryError("invalid_cursor", "pagination cursor does not match query")
        offset = payload.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ArtifactQueryError("invalid_cursor", "pagination cursor offset is invalid")
        return offset

    @staticmethod
    def _fingerprint(query: ArtifactQuery) -> str:
        value = asdict(query)
        value["cursor"] = None
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _encode_cursor(snapshot: str, fingerprint: str, offset: int) -> str:
        payload = json.dumps(
            {"snapshot": snapshot, "query": fingerprint, "offset": offset},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")
