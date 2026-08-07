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
    ArtifactAssociation,
    ArtifactContent,
    ArtifactDetail,
    ArtifactObservation,
    ArtifactOrder,
    ArtifactPage,
    ArtifactQuery,
    ArtifactQueryError,
    ArtifactReadDiagnostic,
    ArtifactSummary,
    ObservationSelection,
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
        snapshot, summaries, diagnostics = self._snapshot_summaries()
        filtered = [item for item in summaries if self._matches(item, query)]
        filtered.sort(key=self._sort_key, reverse=query.order == ArtifactOrder.NEWEST)
        offset = self._cursor_offset(query, snapshot)
        page = tuple(filtered[offset : offset + query.limit])
        next_offset = offset + len(page)
        next_cursor = None
        if next_offset < len(filtered):
            next_cursor = self._encode_cursor(snapshot, self._fingerprint(query), next_offset)
        return ArtifactPage(page, next_cursor, snapshot, len(filtered), diagnostics)

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
        _, summaries, _diagnostics = self._snapshot_summaries()
        counts: dict[str, int] = {}
        names: dict[str, str] = {}
        for item in summaries:
            if item.association_kind != ArtifactAssociation.FIRM_CANONICAL:
                continue
            assert item.firm_id is not None and item.firm_name is not None
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
            assert item.family_id is not None and item.family_label is not None
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
                assert item.canonical_artifact_id is not None
                assert item.canonical_artifact_label is not None
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

    def unassociated(self, limit: int = 50, cursor: str | None = None) -> ArtifactPage:
        """List durable artifacts for which firm/canonical identity is inapplicable."""
        return self.query(ArtifactQuery(
            association_kinds=(ArtifactAssociation.UNASSOCIATED,),
            limit=limit,
            cursor=cursor,
        ))

    def diagnostics(self) -> tuple[ArtifactReadDiagnostic, ...]:
        """Expose bounded malformed-state diagnostics without blocking valid reads."""
        _snapshot, _summaries, diagnostics = self._snapshot_summaries()
        return diagnostics

    def detail(
        self,
        document_id: str,
        observation: str | ObservationSelection = ObservationSelection.LAST,
    ) -> ArtifactDetail:
        """Resolve one artifact and exactly one of its immutable observations."""
        (
            snapshot, summaries, _records, observations, _sources, metadata, _diagnostics,
        ) = self._state()
        summary = next((item for item in summaries if item.document_id == document_id), None)
        if summary is None:
            raise ArtifactQueryError("unknown_document_id", f"unknown document ID: {document_id}")
        matching = sorted(
            [
                item
                for item in observations
                if item.get("document_id") == document_id
                and item.get("artifact_id") == summary.artifact_id
            ],
            key=self._observation_key,
        )
        if not matching:
            raise ArtifactQueryError(
                "repository_read_failure", "artifact has no readable observation"
            )
        index = self._observation_index(matching, str(observation))
        record = matching[index]
        value = self._observation(record)
        cursor = self._encode_observation_cursor(
            snapshot, document_id, summary.artifact_id, value.observation_id, index
        )
        return self._detail(summary, value, cursor, index, len(matching), metadata)

    def next(self, cursor: str) -> ArtifactDetail:
        """Navigate to the next observation in the cursor's immutable snapshot."""
        return self._navigate_observation(cursor, 1)

    def previous(self, cursor: str) -> ArtifactDetail:
        """Navigate to the previous observation in the cursor's immutable snapshot."""
        return self._navigate_observation(cursor, -1)

    def _detail(
        self,
        summary: ArtifactSummary,
        observation: ArtifactObservation,
        cursor: str,
        index: int,
        count: int,
        metadata: dict[str, dict[str, Any]],
    ) -> ArtifactDetail:
        """Build detail without merging metadata across observations."""
        locations = observation.provenance_locations
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
            observation,
            cursor,
            index > 0,
            index + 1 < count,
            locations,
            observation.retrieval_adapter_id,
            observation.retrieval_mechanism,
            observation.source_profile_revision_id,
            observation.candidate_id,
            observation.source_id,
            "verified" if artifact_meta else "unavailable",
            original is not None,
            original,
            observation.metadata,
        )

    def _observation(self, record: dict[str, Any]) -> ArtifactObservation:
        """Normalize one observation record without consulting adjacent observations."""
        discovery = record.get("candidate", {}).get("provenance", {})
        raw_locations = discovery.get("locations", [])
        locations = tuple(
            ProvenanceLocation(
                str(value),
                "original_artifact" if index == len(raw_locations) - 1 else "discovery",
            )
            for index, value in enumerate(raw_locations)
            if isinstance(value, str) and value
        )
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
        return ArtifactObservation(
            str(record["observation_id"]),
            str(record["attempt_id"]),
            str(record["artifact_id"]),
            str(record["document_id"]),
            str(record.get("observed_at", "")),
            self._text(record.get("retrieval_adapter_id")),
            str(record.get("mechanism", "")),
            self._text(record.get("source_profile_revision_id")),
            str(record.get("candidate_id", "")),
            str(record.get("source_id", "")),
            locations,
            provider_ids,
            dict(record.get("diagnostics", {})),
            dict(discovery.get("metadata", {})),
            str(record.get("outcome", "")),
        )

    def _navigate_observation(self, cursor: str, delta: int) -> ArtifactDetail:
        """Resolve one snapshot-bound cursor and move by one observation."""
        payload = self._decode_observation_cursor(cursor)
        (
            snapshot, summaries, _records, observations, _sources, metadata, _diagnostics,
        ) = self._state()
        if payload.get("snapshot") != snapshot:
            raise ArtifactQueryError(
                "stale_cursor", "repository changed; restart observation navigation"
            )
        document_id = payload.get("document_id")
        artifact_id = payload.get("artifact_id")
        index = payload.get("index")
        if (
            not isinstance(document_id, str)
            or not isinstance(artifact_id, str)
            or isinstance(index, bool)
            or not isinstance(index, int)
        ):
            raise ArtifactQueryError("invalid_cursor", "observation cursor is malformed")
        summary = next(
            (
                item
                for item in summaries
                if item.document_id == document_id and item.artifact_id == artifact_id
            ),
            None,
        )
        matching = sorted(
            (
                item
                for item in observations
                if item.get("document_id") == document_id
                and item.get("artifact_id") == artifact_id
            ),
            key=self._observation_key,
        )
        if summary is None or not 0 <= index < len(matching):
            raise ArtifactQueryError("invalid_cursor", "observation cursor target is invalid")
        if matching[index].get("observation_id") != payload.get("observation_id"):
            raise ArtifactQueryError("invalid_cursor", "observation cursor target is invalid")
        target = index + delta
        if not 0 <= target < len(matching):
            raise ArtifactQueryError(
                "observation_boundary", "no observation exists in that direction"
            )
        value = self._observation(matching[target])
        next_cursor = self._encode_observation_cursor(
            snapshot, document_id, artifact_id, value.observation_id, target
        )
        return self._detail(summary, value, next_cursor, target, len(matching), metadata)

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

    def _snapshot_summaries(
        self,
    ) -> tuple[str, tuple[ArtifactSummary, ...], tuple[ArtifactReadDiagnostic, ...]]:
        snapshot, summaries, _, _, _, _, diagnostics = self._state()
        return snapshot, summaries, diagnostics

    def _state(
        self,
    ) -> tuple[
        str,
        tuple[ArtifactSummary, ...],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        tuple[ArtifactReadDiagnostic, ...],
    ]:
        try:
            records = self._repository.history()
            observations = self._repository.observations()
            source_records = self._repository.sources()
            artifact_records = self._repository.artifact_metadata()
        except IntegrityError as error:
            raise ArtifactQueryError(
                "repository_read_failure", "repository state cannot be read"
            ) from error
        snapshot = f"sqlite-revision-{self._repository.repository_revision()}"
        sources = {str(item["source_id"]): item for item in source_records}
        metadata = {str(item["artifact_id"]): item for item in artifact_records}
        latest_by_document: dict[str, dict[str, Any]] = {}
        for observation in observations:
            if observation.get("outcome") != "success":
                continue
            record = {**observation, "occurred_at": observation.get("observed_at", "")}
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
        summaries: list[ArtifactSummary] = []
        diagnostics: list[ArtifactReadDiagnostic] = []
        for record in latest_by_document.values():
            source = sources.get(str(record.get("source_id")), {})
            try:
                projection, basis = self._projection(source)
                if projection is None:
                    continue
                summaries.append(self._summary(record, source, metadata, projection, basis))
            except ArtifactQueryError as error:
                diagnostics.append(ArtifactReadDiagnostic(
                    error.code,
                    str(error)[:512],
                    str(record.get("source_id", "")),
                    str(record.get("document_id", "")),
                    str(record.get("artifact_id", "")),
                ))
        diagnostics.sort(key=lambda item: (item.source_id, item.document_id, item.artifact_id))
        return (
            snapshot, tuple(summaries), records, observations, sources, metadata,
            tuple(diagnostics[:100]),
        )

    @staticmethod
    def _projection(source: dict[str, Any]) -> tuple[ArtifactAssociation | None, str]:
        """Reconcile legacy source policies without inventing missing identity."""
        policy = source.get("policy", {})
        if not isinstance(policy, dict):
            raise ArtifactQueryError(
                "malformed_source_reference", "repository source policy is malformed"
            )
        explicit = policy.get("repository_projection")
        if explicit in {"mailing-list", "stream"}:
            return None, "explicit"
        if explicit not in {None, "firm-artifact", "unassociated-artifact"}:
            raise ArtifactQueryError(
                "unsupported_repository_projection",
                f"repository source has unsupported projection: {explicit}",
            )
        firm_id = policy.get("firm_id")
        canonical_id = policy.get("artifact_id")
        has_firm = isinstance(firm_id, str) and bool(firm_id)
        has_canonical = isinstance(canonical_id, str) and bool(canonical_id)
        if explicit == "firm-artifact":
            if not has_firm or not has_canonical:
                raise ArtifactQueryError(
                    "malformed_source_reference",
                    "firm-artifact source requires firm and canonical artifact identity",
                )
            return ArtifactAssociation.FIRM_CANONICAL, "explicit"
        if explicit == "unassociated-artifact":
            if has_firm or has_canonical:
                raise ArtifactQueryError(
                    "malformed_source_reference",
                    "unassociated source must not claim firm or canonical artifact identity",
                )
            return ArtifactAssociation.UNASSOCIATED, "explicit"
        if has_firm and has_canonical:
            return ArtifactAssociation.FIRM_CANONICAL, "legacy_complete_identity"
        if not has_firm and not has_canonical:
            return ArtifactAssociation.UNASSOCIATED, "legacy_no_identity_claim"
        raise ArtifactQueryError(
            "malformed_source_reference",
            "repository source has a partial firm/canonical identity claim",
        )

    def _summary(
        self,
        record: dict[str, Any],
        source: dict[str, Any],
        metadata: dict[str, dict[str, Any]],
        projection: ArtifactAssociation,
        association_basis: str,
    ) -> ArtifactSummary:
        policy = source.get("policy", {})
        firm_id: str | None = None
        firm_name: str | None = None
        family_id: str | None = None
        family_label: str | None = None
        canonical_id: str | None = None
        canonical_label: str | None = None
        canonical_short_name: str | None = None
        if projection == ArtifactAssociation.FIRM_CANONICAL:
            firm_id = str(policy["firm_id"])
            primary_id = str(policy["artifact_id"])
            alternates = policy.get("alternate_artifact_ids", [])
            if not isinstance(alternates, list) or any(
                not isinstance(item, str) or not item for item in alternates
            ):
                raise ArtifactQueryError(
                    "malformed_source_reference",
                    "repository source alternate artifact authority is malformed",
                )
            observed_id = record.get("canonical_artifact_id", primary_id)
            if not isinstance(observed_id, str) or observed_id not in {
                primary_id, *alternates
            }:
                raise ArtifactQueryError(
                    "malformed_source_reference",
                    "artifact observation exceeds governed canonical artifact authority",
                )
            canonical_id = observed_id
            if canonical_id not in self._artifacts:
                raise ArtifactQueryError(
                    "unknown_canonical_artifact",
                    "repository source references an unknown canonical artifact",
                )
            canonical = self._artifacts[canonical_id]
            family = self._families[canonical.category_id]
            family_id, family_label = family.category_id, family.label
            canonical_label, canonical_short_name = canonical.label, canonical.short_name
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
        if firm_id is not None:
            try:
                firm_name = self._firms.get(firm_id).canonical_name
            except Exception:
                firm_name = firm_id
        filing_date = self._text(discovery_metadata.get("filing_date")) or self._text(
            discovery_metadata.get("publication_date")
        ) or self._text(
            discovery_metadata.get("publication_datetime")
        )
        period_date = self._text(discovery_metadata.get("period_of_report"))
        raw_locations = discovery.get("locations", [])
        original_location = next(
            (value for value in reversed(raw_locations) if isinstance(value, str) and value), None
        )
        display_title = (
            f"{canonical_short_name} · {period_date or filing_date or effective_value[:10]}"
            if canonical_short_name is not None
            else self._text(discovery_metadata.get("title"))
            or original_location
            or str(record.get("candidate_id", record["document_id"]))
        )
        return ArtifactSummary(
            str(record["document_id"]), repo_artifact_id, projection, association_basis,
            firm_id, firm_name, family_id, family_label, canonical_id, canonical_label,
            display_title,
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
            and (not query.association_kinds or item.association_kind in query.association_kinds)
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
        if set(query.association_kinds) - set(ArtifactAssociation):
            raise ArtifactQueryError(
                "invalid_query", "association kind must be firm-canonical or unassociated"
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

    @staticmethod
    def _observation_key(item: dict[str, Any]) -> tuple[str, str]:
        return str(item.get("observed_at", "")), str(item.get("observation_id", ""))

    @staticmethod
    def _observation_index(items: list[dict[str, Any]], selection: str) -> int:
        if selection == ObservationSelection.FIRST.value:
            return 0
        if selection == ObservationSelection.LAST.value:
            return len(items) - 1
        for index, item in enumerate(items):
            if item.get("observation_id") == selection:
                return index
        raise ArtifactQueryError(
            "unknown_observation_id", f"unknown observation ID: {selection}"
        )

    @staticmethod
    def _encode_observation_cursor(
        snapshot: str,
        document_id: str,
        artifact_id: str,
        observation_id: str,
        index: int,
    ) -> str:
        payload = json.dumps(
            {
                "snapshot": snapshot,
                "document_id": document_id,
                "artifact_id": artifact_id,
                "observation_id": observation_id,
                "index": index,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_observation_cursor(cursor: str) -> dict[str, Any]:
        if not cursor or len(cursor) > 2048:
            raise ArtifactQueryError("invalid_cursor", "observation cursor is malformed")
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor + "===").decode())
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactQueryError("invalid_cursor", "observation cursor is malformed") from error
        if not isinstance(payload, dict):
            raise ArtifactQueryError("invalid_cursor", "observation cursor is malformed")
        return payload

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
