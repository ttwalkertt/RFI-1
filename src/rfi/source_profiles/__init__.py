"""Independent firm source-profile aggregate and canonical acquisition template."""

from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    AddressabilityClass,
    CanonicalArtifact,
    CanonicalCategory,
    RetrievalCandidate,
    RetrievalFieldDefinition,
    RetrievalModeDefinition,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRevision,
    SourceProfileView,
)
from rfi.source_profiles.template import (
    canonical_template_path,
    load_canonical_template,
    validate_canonical_template,
)
from rfi.source_profiles.repository import SourceProfileRepository
from rfi.source_profiles.service import SourceProfileService

__all__ = [
    "AcquisitionTemplate",
    "AddressabilityClass",
    "CanonicalArtifact",
    "CanonicalCategory",
    "RetrievalCandidate",
    "RetrievalFieldDefinition",
    "RetrievalModeDefinition",
    "SourceProfileDraft",
    "SourceProfileError",
    "SourceProfileItem",
    "SourceProfileRevision",
    "SourceProfileRepository",
    "SourceProfileService",
    "SourceProfileView",
    "canonical_template_path",
    "load_canonical_template",
    "validate_canonical_template",
]
