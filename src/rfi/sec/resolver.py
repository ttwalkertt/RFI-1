"""Conservative authoritative SEC identity resolution from governed firm identifiers."""

from __future__ import annotations

from rfi.acquisition.sec_provider import SecProviderClient
from rfi.firms.contracts import FirmRevision
from rfi.sec.contracts import (
    SecApplicability,
    SecResolution,
    SecSourceKnowledge,
)


class FirmIdentifierSecResolver:
    """Resolve only explicit SEC CIK identifiers and verify them with SEC submissions."""

    def __init__(self, provider: SecProviderClient) -> None:
        self._provider = provider

    def resolve(self, firm: FirmRevision, verified_at: str) -> SecResolution:
        values = []
        for item in firm.identifiers:
            if item.kind.casefold() == "cik":
                values.append(self._provider.normalize_cik(item.value))
        candidates = tuple(sorted(set(values)))
        if not candidates:
            return SecResolution(None, (), "firm has no authoritative SEC CIK identifier")
        if len(candidates) != 1:
            return SecResolution(None, candidates, "firm has competing SEC CIK identifiers")
        cik = candidates[0]
        self._provider.filings(cik)
        return SecResolution(
            SecSourceKnowledge(
                firm.firm_id, SecApplicability.DIRECT,
                firm.legal_name or firm.canonical_name, cik, "domestic_periodic",
                "verified", verified_at,
            )
        )

    def validate(
        self, firm: FirmRevision, source: SecSourceKnowledge, verified_at: str
    ) -> SecResolution:
        if source.applicability == SecApplicability.NON_APPLICABLE:
            return SecResolution(source.__class__(
                **{**source.__dict__, "verified_at": verified_at}
            ))
        resolved = self.resolve(firm, verified_at)
        if resolved.source is None:
            return resolved
        if (
            resolved.source.cik != source.cik
            or resolved.source.applicability != source.applicability
            or resolved.source.parent_firm_id != source.parent_firm_id
        ):
            return SecResolution(
                resolved.source, resolved.candidates,
                "authoritative SEC identity conflicts with durable source knowledge",
            )
        return SecResolution(SecSourceKnowledge(
            source.firm_id, source.applicability,
            resolved.source.legal_issuer, source.cik, source.filing_regime,
            "verified", verified_at, source.parent_firm_id,
        ))

