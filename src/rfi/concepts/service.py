"""Application service shared by programmatic callers and the admin console."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rfi.concepts.contracts import (
    ConceptCatalog,
    ConceptDraft,
    ConceptError,
    ConceptRevision,
    ConceptStatus,
    ObservationMethod,
)


class ConceptService:
    """Stable use-case boundary that keeps UI code away from persistence internals."""

    def __init__(self, catalog: ConceptCatalog) -> None:
        self.catalog = catalog

    def list_concepts(
        self,
        query: str = "",
        tag: str | None = None,
        status: str | None = None,
        valid_on: str | None = None,
    ) -> tuple[ConceptRevision, ...]:
        """Look up current concepts through public catalog semantics."""
        parsed_status = ConceptStatus(status) if status else None
        return self.catalog.lookup(query, tag, parsed_status, valid_on)

    def detail(self, concept_id: str, revision_id: str | None = None) -> ConceptRevision:
        """Return one current or historical detail view."""
        return self.catalog.get(concept_id, revision_id)

    def history(self, concept_id: str) -> tuple[ConceptRevision, ...]:
        """Return inspectable immutable history."""
        return self.catalog.history(concept_id)

    def create(self, payload: dict[str, Any]) -> ConceptRevision:
        """Validate browser or program input and create one concept."""
        return self.catalog.create(self.draft(payload))

    def revise(
        self,
        concept_id: str,
        payload: dict[str, Any],
        expected_revision_id: str,
    ) -> ConceptRevision:
        """Validate a change and append a new revision."""
        draft = self.draft({**payload, "concept_id": concept_id})
        return self.catalog.revise(concept_id, draft, expected_revision_id)

    def retire(self, concept_id: str, expected_revision_id: str) -> ConceptRevision:
        """Retire through the repository public lifecycle when supported."""
        retire = getattr(self.catalog, "retire", None)
        if retire is None:
            raise ConceptError("catalog does not provide retirement")
        return retire(concept_id, expected_revision_id)

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return explicit validation results without persisting a revision."""
        try:
            draft = self.draft(payload)
            self.catalog.validate(draft)
        except (ConceptError, ValueError, TypeError, KeyError) as error:
            return {"valid": False, "errors": [str(error)]}
        return {"valid": True, "errors": []}

    @staticmethod
    def draft(payload: dict[str, Any]) -> ConceptDraft:
        """Decode a JSON-compatible payload into typed editable intent."""
        if not isinstance(payload, dict):
            raise ConceptError("concept payload must be an object")
        methods_raw = payload.get("methods", [])
        if not isinstance(methods_raw, list):
            raise ConceptError("methods must be an array")
        methods: list[ObservationMethod] = []
        for raw in methods_raw:
            if not isinstance(raw, dict):
                raise ConceptError("each method must be an object")
            value = dict(raw)
            for field_name in (
                "aliases",
                "extraction_hints",
                "expected_evidence_locations",
                "required_inputs",
                "optional_inputs",
                "units",
                "dimensions",
                "validation_conditions",
                "confidence_rules",
                "warnings",
                "sample_cases",
            ):
                value[field_name] = tuple(value.get(field_name, ()))
            methods.append(ObservationMethod(**value))
        try:
            status = ConceptStatus(payload.get("status", ConceptStatus.DRAFT))
            return ConceptDraft(
                concept_id=str(payload.get("concept_id", "")),
                display_name=str(payload.get("display_name", "")),
                definition=str(payload.get("definition", "")),
                comments=str(payload.get("comments", "")),
                aliases=tuple(payload.get("aliases", ())),
                hints=tuple(payload.get("hints", ())),
                status=status,
                tags=tuple(payload.get("tags", ())),
                classifications=dict(payload.get("classifications", {})),
                valid_from=str(payload.get("valid_from", "")),
                valid_through=payload.get("valid_through") or None,
                sample_date=payload.get("sample_date") or None,
                methods=tuple(methods),
                related_concept_ids=tuple(payload.get("related_concept_ids", ())),
                samples=tuple(payload.get("samples", ())),
                warnings=tuple(payload.get("warnings", ())),
            )
        except (TypeError, ValueError) as error:
            raise ConceptError(f"malformed concept payload: {error}") from error

    @staticmethod
    def encode(revision: ConceptRevision) -> dict[str, Any]:
        """Encode public contracts for JSON and browser clients."""
        return asdict(revision)
