"""Representative HDD-industry target firms used as consulting proof."""

from __future__ import annotations

from rfi.firms.contracts import (
    FirmDraft,
    FirmIdentifier,
    FirmRelationship,
    FirmStatus,
    SourceDiscoveryHint,
)


def sample_firms() -> tuple[FirmDraft, ...]:
    """Return representative identities and discovery metadata, not a security master."""
    common = {
        "status": FirmStatus.ACTIVE,
        "valid_from": "2020-01-01",
        "sector": "Technology",
        "industry": "Data storage",
        "technology_focus": ("hard disk drives", "nearline storage"),
    }
    seagate = FirmDraft(
        firm_id="seagate",
        canonical_name="Seagate",
        legal_name="Seagate Technology Holdings plc",
        aliases=("Seagate Technology", "STX"),
        identifiers=(
            FirmIdentifier("ticker", "STX", "NASDAQ"),
            FirmIdentifier("cik", "0001137789", "SEC"),
        ),
        domains=("seagate.com",),
        headquarters="Fremont, California, United States",
        jurisdiction="Ireland",
        relationships=(FirmRelationship("competitor", "western-digital"),),
        source_hints=(
            SourceDiscoveryHint("investor-relations", "investors.seagate.com"),
            SourceDiscoveryHint("sec-company", "CIK 0001137789"),
        ),
        notes="Primary HDD consulting target; retain the Irish legal issuer identity.",
        **common,
    )
    western_digital = FirmDraft(
        firm_id="western-digital",
        canonical_name="Western Digital",
        legal_name="Western Digital Corporation",
        aliases=("WDC", "WD"),
        identifiers=(
            FirmIdentifier("ticker", "WDC", "NASDAQ"),
            FirmIdentifier("cik", "0000106040", "SEC"),
        ),
        domains=("westerndigital.com",),
        headquarters="San Jose, California, United States",
        jurisdiction="Delaware, United States",
        relationships=(FirmRelationship("competitor", "seagate"),),
        source_hints=(
            SourceDiscoveryHint("investor-relations", "investor.wdc.com"),
            SourceDiscoveryHint("sec-company", "CIK 0000106040"),
        ),
        notes="HDD and flash-storage consulting target; aliases require source context.",
        **common,
    )
    toshiba = FirmDraft(
        firm_id="toshiba",
        canonical_name="Toshiba",
        legal_name="Toshiba Corporation",
        aliases=("Toshiba Group",),
        identifiers=(FirmIdentifier("ticker", "6502", "TSE"),),
        domains=("global.toshiba",),
        headquarters="Tokyo, Japan",
        jurisdiction="Japan",
        relationships=(
            FirmRelationship(
                "related",
                "toshiba-electronic-devices-and-storage",
                "HDD operating organization",
            ),
        ),
        source_hints=(
            SourceDiscoveryHint("corporate", "global.toshiba"),
            SourceDiscoveryHint("product", "toshiba.semicon-storage.com"),
        ),
        notes=(
            "Parent-company identity. Future entity work may split the HDD operating "
            "organization without changing this firm ID."
        ),
        **common,
    )
    return seagate, western_digital, toshiba
