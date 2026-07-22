"""Bounded Linux development-mailing-list acquisition and query vertical."""

from rfi.mailing_lists.contracts import (
    AcquisitionLimits,
    AcquisitionMessage,
    AcquisitionManifest,
    AcquisitionPreview,
    AcquisitionRunStatus,
    RelationshipAcquisitionStatus,
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
from rfi.mailing_lists.queue import MailingListFetchQueue
from rfi.mailing_lists.repository import MailingListRepository
from rfi.mailing_lists.service import (
    MailingListAcquisitionService,
    MailingListQueryService,
    MailingListSourceService,
)
from rfi.mailing_lists.workflow import (
    ArchiveValidationResult,
    FetchUpToDateResult,
    LinuxMailingListWorkflowService,
    LoreCatalogEntry,
    MailingListWorkflowDraft,
    MailingListWorkflowReview,
    SavedMailingListWorkflow,
    WorkflowCreateResult,
    WorkflowTestResult,
    normalize_lore_archive,
)

LINUX_BLOCK_SOURCE = MailingListSource(
    "linux-block-lore", "linux-block", "Linux block layer",
    "https://lore.kernel.org/linux-block/",
)

__all__ = [
    "AcquisitionLimits", "AcquisitionManifest", "AcquisitionMessage", "AcquisitionPreview",
    "AcquisitionRunStatus", "RelationshipAcquisitionStatus",
    "ArchiveValidationResult",
    "FetchUpToDateResult",
    "ArchiveMessage", "ConnectivityState",
    "DiscussionProjection", "DiscussionSummary", "FixtureMailingListArchive", "InclusionReason",
    "LINUX_BLOCK_SOURCE", "LoreArchive", "MailingListAcquisitionService", "MailingListError",
    "LinuxMailingListWorkflowService", "LoreCatalogEntry",
    "MailingListFetchQueue",
    "LoreTransportPolicy", "MailingListQueryService", "MailingListRepository",
    "MailingListSourceService",
    "MailingListSource", "MailingListWorkflowDraft", "MailingListWorkflowReview", "MessageDetail",
    "MessageSummary", "SelectionCriteria",
    "SavedMailingListWorkflow", "WorkflowCreateResult",
    "WorkflowTestResult",
    "normalize_lore_archive",
]
