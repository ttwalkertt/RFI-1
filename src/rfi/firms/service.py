"""Application service shared by target-firm callers and the admin console."""

from __future__ import annotations

import math
from typing import Any

from rfi.firms.contracts import (
    FirmCatalog,
    FirmDraft,
    FirmError,
    FirmIdentifier,
    FirmRevision,
    FirmStatus,
    SourceDiscoveryHint,
)


class FirmService:
    """Stable use-case boundary that keeps adapters away from persistence internals."""

    def __init__(self, catalog: FirmCatalog) -> None:
        self.catalog = catalog

    def list_firms(
        self,
        query: str = "",
        status: str | None = None,
        sector: str | None = None,
        industry: str | None = None,
        minimum_relevance: float | None = None,
    ) -> tuple[FirmRevision, ...]:
        """Look up current target firms through public catalog semantics."""
        parsed_status = FirmStatus(status) if status else None
        if minimum_relevance is not None and (
            isinstance(minimum_relevance, bool)
            or not math.isfinite(minimum_relevance)
            or not 0 <= minimum_relevance <= 100
        ):
            raise FirmError("minimum relevance must be a finite number from 0 through 100")
        return self.catalog.lookup(query, parsed_status, sector, industry, minimum_relevance)

    def detail(self, firm_id: str, revision_id: str | None = None) -> FirmRevision:
        """Return one current or historical firm record."""
        return self.catalog.get(firm_id, revision_id)

    def history(self, firm_id: str) -> tuple[FirmRevision, ...]:
        """Return inspectable immutable history."""
        return self.catalog.history(firm_id)

    def create(self, payload: dict[str, Any]) -> FirmRevision:
        """Validate JSON-compatible input and create one stable firm."""
        return self.catalog.create(self.draft(payload))

    def revise(
        self,
        firm_id: str,
        payload: dict[str, Any],
        expected_revision_id: str,
    ) -> FirmRevision:
        """Validate a change and append one immutable revision."""
        draft = self.draft({**payload, "firm_id": firm_id})
        return self.catalog.revise(firm_id, draft, expected_revision_id)

    def retire(self, firm_id: str, expected_revision_id: str) -> FirmRevision:
        """Retire a firm through the public catalog lifecycle."""
        retire = getattr(self.catalog, "retire", None)
        if retire is None:
            raise FirmError("firm catalog does not provide retirement")
        return retire(firm_id, expected_revision_id)

    def validate(
        self, payload: dict[str, Any], current_firm_id: str | None = None
    ) -> dict[str, Any]:
        """Return explicit validation results without publishing a revision."""
        try:
            self.catalog.validate(self.draft(payload), current_firm_id)
        except (FirmError, TypeError, ValueError, KeyError) as error:
            return {"valid": False, "errors": [str(error)]}
        return {"valid": True, "errors": []}

    @staticmethod
    def draft(payload: dict[str, Any]) -> FirmDraft:
        """Decode JSON-compatible values into typed editable intent."""
        if not isinstance(payload, dict):
            raise FirmError("firm payload must be an object")
        if "relationships" in payload:
            raise FirmError(
                "relationships are outside the firm identity authority and require "
                "evidence-backed graph records"
            )
        try:
            identifiers = tuple(
                FirmIdentifier(
                    kind=str(item.get("kind", "")),
                    value=str(item.get("value", "")),
                    market=str(item["market"]) if item.get("market") else None,
                )
                for item in FirmService._objects(payload, "identifiers")
            )
            source_hints = tuple(
                SourceDiscoveryHint(
                    kind=str(item.get("kind", "")),
                    value=str(item.get("value", "")),
                    notes=str(item.get("notes", "")),
                )
                for item in FirmService._objects(payload, "source_hints")
            )
            return FirmDraft(
                firm_id=str(payload.get("firm_id", "")),
                canonical_name=str(payload.get("canonical_name", "")),
                legal_name=str(payload.get("legal_name", "")),
                aliases=tuple(payload.get("aliases", ())),
                identifiers=identifiers,
                domains=tuple(payload.get("domains", ())),
                headquarters=str(payload.get("headquarters", "")),
                jurisdiction=str(payload.get("jurisdiction", "")),
                sector=str(payload.get("sector", "")),
                industry=str(payload.get("industry", "")),
                technology_focus=tuple(payload.get("technology_focus", ())),
                source_hints=source_hints,
                notes=str(payload.get("notes", "")),
                relevance=payload.get("relevance", 0.0),
                status=FirmStatus(payload.get("status", FirmStatus.DRAFT)),
                valid_from=str(payload.get("valid_from", "")),
                valid_through=payload.get("valid_through") or None,
            )
        except (TypeError, ValueError) as error:
            raise FirmError(f"malformed firm payload: {error}") from error

    @staticmethod
    def _objects(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
        value = payload.get(name, [])
        if not isinstance(value, (list, tuple)):
            raise FirmError(f"{name} must be an array")
        if any(not isinstance(item, dict) for item in value):
            raise FirmError(f"each {name} entry must be an object")
        return list(value)
