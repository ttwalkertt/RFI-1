"""Reusable mechanics for artifact-specific SEC numbered-form adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, ClassVar

from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.engine import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
)
from rfi.acquisition.sec_provider import (
    SEC_ARCHIVES_ORIGIN,
    SecFilingMetadata,
    SecProviderClient,
)


class SecNumberedFormAdapter:
    """Share deterministic mechanics while leaving every filing policy concrete."""

    adapter_id: ClassVar[str]
    artifact_ids: ClassVar[tuple[str, ...]]
    retrieval_modes: ClassVar[tuple[str, ...]] = ("identifier",)
    mechanism: ClassVar[str]
    eligible_form: ClassVar[str]
    amendment_policy: ClassVar[str] = "exclude"
    artifact_multiplicity: ClassVar[str]
    no_eligible_code: ClassVar[str]
    semantic_name: ClassVar[str]

    def __init__(
        self, provider: SecProviderClient, clock: Callable[[], str]
    ) -> None:
        self._provider = provider
        self._clock = clock

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        """Resolve issuer identity and expose one policy-selected primary filing."""
        if continuation is not None:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                f"{self.semantic_name} retrieval does not support continuation",
                False,
                "malformed_provider_response",
            )
        cik = self._validate_profile(profile)
        filings = self._provider.filings(cik)
        selected, counts = self.select_filing(filings)
        return DiscoveryPage(
            (self._candidate(selected),),
            None,
            {
                "adapter_id": self.adapter_id,
                "provider": "SEC EDGAR",
                "provider_surface": "submissions-api",
                "issuer_cik": cik,
                "eligible_form": self.eligible_form,
                "amendment_policy": self.amendment_policy,
                "artifact_multiplicity": self.artifact_multiplicity,
                "provider_records": len(filings),
                "eligible_records": counts["eligible"],
                "amendment_records_excluded": counts["amendments_excluded"],
                "selected_accession": selected.accession_number,
                "selected_primary_document": selected.primary_document,
                "provider_usage": self._provider.usage(),
            },
        )

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        """Retrieve exact primary filing bytes identified during discovery."""
        cik = self._validate_profile(profile)
        metadata = candidate.provenance.metadata
        accession = metadata.get("accession_number")
        primary_document = metadata.get("primary_document")
        artifact_role = metadata.get("artifact_role")
        if (
            not isinstance(accession, str)
            or not isinstance(primary_document, str)
            or artifact_role != "primary_filing_document"
        ):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                f"{self.semantic_name} candidate lacks primary filing artifact identity",
                False,
                "missing_filing_identity",
            )
        document = self._provider.primary_document(cik, accession, primary_document)
        return RetrievalResult(
            document.content,
            document.media_type,
            self._clock(),
            self.mechanism,
            {
                "provider": "SEC EDGAR",
                "sec_cik": cik,
                "sec_accession": accession,
                "sec_primary_document": primary_document,
            },
            {
                "adapter_id": self.adapter_id,
                "provider": "SEC EDGAR",
                "provider_surface": "edgar-archives-primary-document",
                "archive_url": document.archive_url,
                "http_status": document.http_status,
                "bytes": len(document.content),
                "artifact_role": "primary_filing_document",
                "form_policy": self.eligible_form,
                "amendment_policy": self.amendment_policy,
                "provider_usage": self._provider.usage(),
            },
        )

    @classmethod
    def select_filing(
        cls, filings: tuple[SecFilingMetadata, ...]
    ) -> tuple[SecFilingMetadata, dict[str, int]]:
        """Apply the concrete adapter's exact-form policy and shared latest selector."""
        eligible = [item for item in filings if item.form == cls.eligible_form]
        amendments = sum(item.form == f"{cls.eligible_form}/A" for item in filings)
        if not eligible:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"SEC issuer has no eligible unamended {cls.semantic_name} filing",
                False,
                cls.no_eligible_code,
            )
        by_accession: dict[str, SecFilingMetadata] = {}
        for filing in eligible:
            if not filing.primary_document:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    f"eligible SEC {cls.semantic_name} lacks primary-document identity",
                    False,
                    "missing_filing_identity",
                )
            prior = by_accession.get(filing.accession_number)
            if prior is not None and prior != filing:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    f"SEC {cls.semantic_name} metadata is ambiguous for one accession",
                    False,
                    "ambiguous_filing_result",
                )
            by_accession[filing.accession_number] = filing
        unique = tuple(by_accession.values())
        for filing in unique:
            cls._selection_key(filing)
        ordered = sorted(unique, key=cls._selection_key, reverse=True)
        return ordered[0], {
            "eligible": len(unique),
            "amendments_excluded": amendments,
        }

    @classmethod
    def _candidate(cls, filing: SecFilingMetadata) -> AdapterCandidate:
        accession_digits = filing.accession_number.replace("-", "")
        archive_path = (
            f"/Archives/edgar/data/{filing.issuer_cik}/{accession_digits}/"
            f"{filing.primary_document}"
        )
        return AdapterCandidate(
            candidate_id=(
                f"candidate-sec-{filing.issuer_cik}-{accession_digits}-primary"
            ),
            document_id=f"document-sec-{filing.issuer_cik}-{accession_digits}",
            position=cls._position(filing),
            revision=f"filing-{accession_digits}-primary",
            provenance=DiscoveryProvenance(
                discovered_at=filing.acceptance_datetime,
                discovery_method=cls.mechanism,
                provider_identifiers={
                    "provider": "SEC EDGAR",
                    "sec_cik": filing.issuer_cik,
                    "sec_accession": filing.accession_number,
                    "sec_primary_document": filing.primary_document,
                },
                locations=(
                    filing.submissions_url,
                    f"{SEC_ARCHIVES_ORIGIN}{archive_path}",
                ),
                metadata={
                    "adapter_id": cls.adapter_id,
                    "provider": "SEC EDGAR",
                    "provider_surface": "submissions-api",
                    "issuer_cik": filing.issuer_cik,
                    "accession_number": filing.accession_number,
                    "form_type": filing.form,
                    "amendment": False,
                    "amendment_policy": cls.amendment_policy,
                    "filing_date": filing.filing_date,
                    "acceptance_datetime": filing.acceptance_datetime,
                    "period_of_report": filing.report_date,
                    "primary_document": filing.primary_document,
                    "artifact_role": "primary_filing_document",
                    "archive_path": archive_path,
                },
            ),
        )

    @classmethod
    def _validate_profile(cls, profile: SourceProfile) -> str:
        artifact_id = cls.artifact_ids[0]
        if profile.mechanism != cls.mechanism:
            raise ContractError(f"{cls.semantic_name} source mechanism is invalid")
        if profile.policy.get("artifact_id") != artifact_id:
            raise ContractError(
                f"{cls.semantic_name} adapter requires canonical artifact {artifact_id}"
            )
        if profile.configuration.get("mode") != "identifier":
            raise ContractError(
                f"{cls.semantic_name} adapter requires identifier retrieval mode"
            )
        locator = profile.configuration.get("locator")
        if not isinstance(locator, str) or not locator:
            raise ContractError(
                f"{cls.semantic_name} identifier candidate requires a SEC CIK locator"
            )
        try:
            return SecProviderClient.normalize_cik(locator)
        except ContractError as error:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"{cls.semantic_name} candidate contains an invalid SEC issuer identifier",
                False,
                "invalid_sec_issuer_identifier",
            ) from error

    @classmethod
    def _selection_key(cls, filing: SecFilingMetadata) -> tuple[str, str, str]:
        try:
            datetime.strptime(filing.filing_date, "%Y-%m-%d")
            datetime.fromisoformat(filing.acceptance_datetime.replace("Z", "+00:00"))
        except ValueError as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                f"SEC {cls.semantic_name} filing date or acceptance time is malformed",
                False,
                "malformed_provider_response",
            ) from error
        return filing.filing_date, filing.acceptance_datetime, filing.accession_number

    @staticmethod
    def _position(filing: SecFilingMetadata) -> int:
        accepted = datetime.fromisoformat(
            filing.acceptance_datetime.replace("Z", "+00:00")
        )
        if accepted.tzinfo is None:
            accepted = accepted.replace(tzinfo=UTC)
        microseconds = int(accepted.timestamp() * 1_000_000)
        sequence = int(filing.accession_number[-6:])
        return microseconds * 1_000_000 + sequence
