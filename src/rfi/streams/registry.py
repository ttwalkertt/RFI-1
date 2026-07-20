"""Finite repository-owned schema, projection, and expansion registrations."""

from __future__ import annotations

from typing import Any

from rfi.streams.contracts import (
    ArtifactProjection,
    AttributeCapability,
    ExpandedProjection,
    RegisteredArtifactSchema,
    SchemaCapability,
    StreamDraft,
    StreamError,
)

_COMMON_FIELDS = {
    "schema": ("equals", "in"),
    "source": ("equals", "in"),
    "title": ("contains", "equals"),
    "text": ("contains", "equals"),
    "authors": ("contains", "equals", "in"),
    "effective_at": ("after_or_on", "before_or_on", "equals"),
}


class RetainedProjectionProvider:
    """Use projections populated by the owning acquisition/schema adapter."""

    def __init__(self, schema_id: str) -> None:
        self.schema_id = schema_id

    def refresh(self, repository: Any) -> int:
        del repository
        return 0


class MailingListProjectionProvider:
    schema_id = "mail.message"

    def refresh(self, repository: Any) -> int:
        rows = repository.rows(
            "SELECT m.artifact_id,m.document_id,m.source_id,m.message_date,m.subject,"
            "m.text_content,m.sender,m.connectivity_state,s.list_id,dm.discussion_id,dm.depth "
            "FROM mailing_list_messages m JOIN mailing_list_sources s ON s.source_id=m.source_id "
            "LEFT JOIN mailing_list_discussion_members dm ON dm.message_key=m.message_key"
        )
        return repository.upsert_projections(
            ArtifactProjection(
                artifact_id=str(row["artifact_id"]), document_id=str(row["document_id"]),
                schema_id=self.schema_id, source_id=str(row["source_id"]),
                effective_at=str(row["message_date"]) if row["message_date"] else None,
                title=str(row["subject"]), searchable_text=str(row["text_content"]),
                authors=(str(row["sender"]),),
                attributes={"mail.list_id": str(row["list_id"])},
                context_id=str(row["discussion_id"]) if row["discussion_id"] else None,
                context_depth=int(row["depth"]) if row["depth"] is not None else None,
                completeness=str(row["connectivity_state"]),
            )
            for row in rows
        )


class NoExpansion:
    strategy = "none"

    def __init__(self, schema_id: str) -> None:
        self.schema_id = schema_id

    def validate(self, expansion: dict[str, Any]) -> tuple[dict[str, str], ...]:
        depth = expansion.get("descendant_depth", 0)
        if depth not in {0, None}:
            return ({"code": "invalid_expansion", "message": "none expansion requires depth 0"},)
        return ()

    def expand(
        self,
        repository: Any,
        draft: StreamDraft,
        direct: tuple[ArtifactProjection, ...],
        upstream: dict[str, list[dict[str, Any]]],
    ) -> tuple[ExpandedProjection, ...]:
        del repository, draft, direct, upstream
        return ()


class ConnectedDiscussionExpansion:
    schema_id = "mail.message"
    strategy = "connected_discussion"

    def validate(self, expansion: dict[str, Any]) -> tuple[dict[str, str], ...]:
        errors = []
        if not bool(expansion.get("ancestor_closure", True)):
            errors.append({
                "code": "connectivity_required",
                "message": "connected discussion expansion requires ancestor closure",
            })
        depth = expansion.get("descendant_depth", 0)
        if not isinstance(depth, int) or not 0 <= depth <= 20:
            errors.append({
                "code": "invalid_expansion",
                "message": "descendant_depth must be between 0 and 20",
            })
        return tuple(errors)

    def expand(
        self,
        repository: Any,
        draft: StreamDraft,
        direct: tuple[ArtifactProjection, ...],
        upstream: dict[str, list[dict[str, Any]]],
    ) -> tuple[ExpandedProjection, ...]:
        invalid = [item for item in direct if item.completeness not in {"connected", "truncated"}]
        if invalid:
            raise StreamError(
                "incomplete_context",
                "connected discussion expansion rejected incomplete or quarantined context",
            )
        contexts = tuple(sorted({item.context_id for item in direct if item.context_id}))
        expanded = repository.context(self.schema_id, contexts)
        if len(expanded) > draft.bounds["expanded_limit"]:
            raise StreamError(
                "expansion_limit",
                "connected context exceeds expanded_limit; no partial component was published",
            )
        direct_ids = {item.artifact_id for item in direct}
        direct_by_context: dict[str, list[ArtifactProjection]] = {}
        for seed in direct:
            if seed.context_id:
                direct_by_context.setdefault(seed.context_id, []).append(seed)
        result = []
        for item in expanded:
            if item.artifact_id in direct_ids:
                continue
            lineage = []
            reasons = []
            for seed in direct_by_context.get(item.context_id or "", []):
                reason = (
                    "ancestor_context"
                    if (item.context_depth or 0) < (seed.context_depth or 0)
                    else "descendant_context"
                )
                reasons.append(reason)
                inherited = upstream.get(seed.artifact_id, [{}])[0]
                lineage.append({
                    "upstream_stream_id": inherited.get("upstream_stream_id"),
                    "upstream_membership_id": inherited.get("upstream_membership_id"),
                    "seed_artifact_id": seed.artifact_id,
                    "inclusion_reason": reason,
                })
            result.append(ExpandedProjection(
                item,
                sorted(reasons)[0] if reasons else "relationship_context",
                tuple(lineage),
            ))
        return tuple(result)


class StreamSchemaRegistry:
    def __init__(self, registrations: tuple[RegisteredArtifactSchema, ...]) -> None:
        self._items = {item.capability.schema_id: item for item in registrations}
        if len(self._items) != len(registrations):
            raise ValueError("stream schema registrations must be unique")

    def registrations(self) -> tuple[RegisteredArtifactSchema, ...]:
        return tuple(self._items.values())

    def registration(self, schema_id: str) -> RegisteredArtifactSchema | None:
        return self._items.get(schema_id)


def default_registry() -> StreamSchemaRegistry:
    mail = SchemaCapability(
        "mail.message", "Mailing-list message",
        {**_COMMON_FIELDS, "completeness": ("equals", "in")},
        (
            AttributeCapability("mail.list_id", "string", ("equals", "in"), "Mailing-list ID"),
            AttributeCapability(
                "mail.patch_version", "string", ("equals", "in"), "Patch version"
            ),
        ),
        ("none", "connected_discussion"),
    )
    sec = SchemaCapability(
        "sec.filing", "SEC filing", _COMMON_FIELDS,
        (
            AttributeCapability("sec.form_type", "string", ("equals", "in"), "SEC form type"),
            AttributeCapability("sec.accession", "string", ("equals", "in"), "SEC accession"),
        ),
        ("none",),
    )
    return StreamSchemaRegistry((
        RegisteredArtifactSchema(
            mail, MailingListProjectionProvider(),
            (NoExpansion(mail.schema_id), ConnectedDiscussionExpansion()),
        ),
        RegisteredArtifactSchema(
            sec, RetainedProjectionProvider(sec.schema_id), (NoExpansion(sec.schema_id),),
        ),
    ))
