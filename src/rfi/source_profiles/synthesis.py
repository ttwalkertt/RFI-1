"""Provider-neutral default retrieval synthesis from verified firm identity."""

from __future__ import annotations

import re

from rfi.firms.contracts import FirmCatalog, FirmExternalIdentity
from rfi.source_profiles.contracts import RetrievalCandidate, SourceProfileItem

SEC_ARTIFACTS = frozenset({"sec_10k", "sec_10q", "sec_8k", "sec_20f", "sec_6k"})
_SEC_CIK = re.compile(r"^[0-9]{10}$")


def synthesized_candidate(
    identity: FirmExternalIdentity | None, artifact_id: str
) -> RetrievalCandidate | None:
    """Return the deterministic provider default without persisting runtime URLs."""
    if (
        identity is None
        or identity.provider != "sec"
        or identity.verification_status != "verified"
        or not _SEC_CIK.fullmatch(identity.identifier)
        or identity.identifier == "0000000000"
        or artifact_id not in SEC_ARTIFACTS
    ):
        return None
    return RetrievalCandidate("identifier", 1, locator=f"CIK:{identity.identifier}")


def effective_items(
    firms: FirmCatalog, firm_id: str, items: tuple[SourceProfileItem, ...]
) -> tuple[SourceProfileItem, ...]:
    """Apply defaults only where an operator has supplied no explicit candidates."""
    identity = firms.external_identity(firm_id, "sec")
    return tuple(
        item if item.retrieval_candidates else SourceProfileItem(
            item.artifact_id, item.enabled,
            (candidate,)
            if (candidate := synthesized_candidate(identity, item.artifact_id))
            else (),
            item.operator_notes,
        )
        for item in items
    )
