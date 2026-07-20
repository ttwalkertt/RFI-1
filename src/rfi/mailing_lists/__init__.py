"""Bounded Linux development-mailing-list acquisition and query vertical."""

from rfi.mailing_lists.contracts import (
    AcquisitionLimits,
    AcquisitionManifest,
    AcquisitionPreview,
    AcquisitionRunStatus,
    ArchiveMessage,
    ConnectivityState,
    DiscussionProjection,
    DiscussionSummary,
    InclusionReason,
    MailingListError,
    MailingListSource,
    LoreTransportPolicy,
    MessageDetail,
    MessageSummary,
    SelectionCriteria,
)
from rfi.mailing_lists.provider import FixtureMailingListArchive, LoreArchive
from rfi.mailing_lists.repository import MailingListRepository
from rfi.mailing_lists.service import MailingListAcquisitionService, MailingListQueryService

LINUX_BLOCK_SOURCE = MailingListSource(
    "linux-block-lore", "linux-block", "Linux block layer",
    "https://lore.kernel.org/linux-block/",
)

__all__ = [
    "AcquisitionLimits", "AcquisitionManifest", "AcquisitionPreview", "AcquisitionRunStatus",
    "ArchiveMessage", "ConnectivityState",
    "DiscussionProjection", "DiscussionSummary", "FixtureMailingListArchive", "InclusionReason",
    "LINUX_BLOCK_SOURCE", "LoreArchive", "MailingListAcquisitionService", "MailingListError",
    "LoreTransportPolicy", "MailingListQueryService", "MailingListRepository",
    "MailingListSource", "MessageDetail",
    "MessageSummary", "SelectionCriteria",
]
