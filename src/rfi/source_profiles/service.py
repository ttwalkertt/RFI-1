"""Application service for template-driven, firm-specific acquisition configuration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rfi.firms.contracts import FirmCatalog
from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    RetrievalCandidate,
    SourceProfileCatalog,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRevision,
    SourceProfileView,
)


class SourceProfileService:
    """Use-case boundary keeping firm identity, template data, and persistence separate."""

    def __init__(
        self,
        catalog: SourceProfileCatalog,
        firms: FirmCatalog,
        template: AcquisitionTemplate,
    ) -> None:
        self.catalog = catalog
        self.firms = firms
        self.template = template

    def canonical_template(self) -> dict[str, Any]:
        """Return the exact validated template model consumed by service and UI."""
        return asdict(self.template)

    def detail(self, firm_id: str, revision_id: str | None = None) -> SourceProfileView:
        """Return a revision or canonical defaults when the firm has never saved a profile."""
        self.firms.get(firm_id)
        revision = self.catalog.get(firm_id, revision_id)
        if revision is None:
            items = tuple(
                SourceProfileItem(item.artifact_id, item.default_enabled)
                for item in self.template.artifacts
            )
            return SourceProfileView(
                firm_id, None, 0, items, "", None, None, None, True
            )
        return self._view(revision)

    def history(self, firm_id: str) -> tuple[SourceProfileRevision, ...]:
        """Return only saved immutable revisions; defaults are not fabricated history."""
        self.firms.get(firm_id)
        return self.catalog.history(firm_id)

    def validate(self, firm_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return explicit validation results without creating either aggregate revision."""
        try:
            self.firms.get(firm_id)
            self.catalog.validate(self.draft(firm_id, payload))
        except (SourceProfileError, TypeError, ValueError, KeyError) as error:
            return {"valid": False, "errors": [str(error)]}
        return {"valid": True, "errors": []}

    def publish(
        self,
        firm_id: str,
        payload: dict[str, Any],
        expected_revision_id: str | None,
    ) -> SourceProfileRevision:
        """Publish source-profile intent without writing the target-firm aggregate."""
        self.firms.get(firm_id)
        return self.catalog.publish(self.draft(firm_id, payload), expected_revision_id)

    @staticmethod
    def draft(firm_id: str, payload: dict[str, Any]) -> SourceProfileDraft:
        """Decode JSON-compatible UI input into strict typed acquisition intent."""
        if not isinstance(payload, dict):
            raise SourceProfileError("source-profile payload must be an object")
        items = tuple(
            SourceProfileService._item(value)
            for value in SourceProfileService._objects(payload, "items")
        )
        notes = payload.get("operator_notes", "")
        if not isinstance(notes, str):
            raise SourceProfileError("source-profile operator_notes must be a string")
        return SourceProfileDraft(firm_id, items, notes)

    @staticmethod
    def _item(value: dict[str, Any]) -> SourceProfileItem:
        artifact_id = value.get("artifact_id")
        enabled = value.get("enabled")
        notes = value.get("operator_notes", "")
        if not isinstance(artifact_id, str) or not isinstance(enabled, bool):
            raise SourceProfileError("source-profile items require artifact_id and enabled")
        if not isinstance(notes, str):
            raise SourceProfileError("source-profile item operator_notes must be a string")
        candidates = tuple(
            SourceProfileService._candidate(item)
            for item in SourceProfileService._objects(value, "retrieval_candidates")
        )
        return SourceProfileItem(artifact_id, enabled, candidates, notes)

    @staticmethod
    def _candidate(value: dict[str, Any]) -> RetrievalCandidate:
        mode = value.get("mode")
        priority = value.get("priority")
        if not isinstance(mode, str):
            raise SourceProfileError("retrieval candidate mode must be a string")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise SourceProfileError("retrieval candidate priority must be an integer")
        allowed = {
            "mode",
            "priority",
            "url",
            "locator",
            "preferred_domains",
            "discovery_hints",
            "expected_media_type",
            "parser_hint",
            "operator_notes",
        }
        unknown = set(value).difference(allowed)
        if unknown:
            raise SourceProfileError(
                f"unknown retrieval candidate fields: {', '.join(sorted(unknown))}"
            )
        strings: dict[str, str] = {}
        for name in (
            "url",
            "locator",
            "expected_media_type",
            "parser_hint",
            "operator_notes",
        ):
            field = value.get(name, "")
            if not isinstance(field, str):
                raise SourceProfileError(f"retrieval candidate {name} must be a string")
            strings[name] = field
        preferred = SourceProfileService._string_array(value, "preferred_domains")
        hints = SourceProfileService._string_array(value, "discovery_hints")
        return RetrievalCandidate(
            mode,
            priority,
            strings["url"],
            strings["locator"],
            preferred,
            hints,
            strings["expected_media_type"],
            strings["parser_hint"],
            strings["operator_notes"],
        )

    @staticmethod
    def _objects(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
        value = payload.get(name, [])
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise SourceProfileError(f"{name} must be an array of objects")
        return value

    @staticmethod
    def _string_array(payload: dict[str, Any], name: str) -> tuple[str, ...]:
        value = payload.get(name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise SourceProfileError(f"retrieval candidate {name} must be a string array")
        return tuple(value)

    @staticmethod
    def _view(revision: SourceProfileRevision) -> SourceProfileView:
        return SourceProfileView(
            revision.firm_id,
            revision.source_profile_revision_id,
            revision.revision_number,
            revision.items,
            revision.operator_notes,
            revision.created_at,
            revision.updated_at,
            revision.supersedes_revision_id,
            False,
        )
