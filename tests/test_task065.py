"""Focused acceptance evidence for TASK-065 explicit transcript-provider injection."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    SourceProfile,
    TranscriptAcquisitionTarget,
)
from rfi.acquisition.contracts import ContractError
from rfi.acquisition.providers import (
    StockAnalysisTranscriptProvider,
    TranscriptProviderRegistry,
)
from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.pull import (
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
DOCUMENT = (ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html").read_bytes()


class Transport:
    def __init__(
        self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]
    ) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def response(
    url: str, content: bytes, status: int = 200
) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(url, status, "text/html", content)


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )


def profile() -> SourceProfile:
    return SourceProfile(
        "source-oracle-transcript",
        "Oracle transcripts",
        True,
        "earnings_transcript",
        {
            "mode": "discovery",
            "provider": "stockanalysis",
            "discovery_hint_kind": "provider_identifier",
            "discovery_hint_value": "ORCL",
            "discovery_class": "standard",
            "discovery_hints": [],
        },
        {
            "firm_id": "oracle",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


class ExplicitProviderDispatchTests(unittest.TestCase):
    def test_registry_is_the_only_name_resolution_authority(self) -> None:
        registry = TranscriptProviderRegistry((StockAnalysisTranscriptProvider,))
        self.assertIs(
            registry.resolve("stockanalysis"), StockAnalysisTranscriptProvider
        )
        for invalid, message in (
            ("", "non-empty string"),
            ("   ", "non-empty string"),
            ("unknown", "unknown transcript provider"),
        ):
            with self.subTest(provider=invalid), self.assertRaisesRegex(
                ContractError, message
            ):
                registry.resolve(invalid)

    def test_request_provider_reaches_trial_without_url_inference_or_config_fallback(
        self,
    ) -> None:
        transport = Transport({})
        adapter = EarningsTranscriptPullAdapter(
            policies(), transport=transport,
            clock=lambda: "2026-08-04T00:00:00+00:00",
        )
        configured = profile()
        target = TranscriptAcquisitionTarget("oracle")
        trial = adapter.injected_trial(
            configured, target, "stockanalysis", DOCUMENT_URL
        )
        self.assertEqual(trial.provider, "stockanalysis")
        self.assertEqual(trial.seed_source, "operator_supplied")
        with self.assertRaisesRegex(ContractError, "unknown transcript provider"):
            adapter.injected_trial(
                configured, target, "unknown", DOCUMENT_URL
            )
        self.assertEqual(transport.requests, [])

    def test_direct_document_injection_succeeds_through_selected_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = profile()
            repository.register_source(configured)
            transport = Transport({DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT)})
            adapter = EarningsTranscriptPullAdapter(
                policies(), transport=transport, repository=repository,
                clock=lambda: "2026-08-04T00:00:00+00:00",
            )
            trial = adapter.injected_trial(
                configured,
                TranscriptAcquisitionTarget("oracle"),
                "stockanalysis",
                DOCUMENT_URL,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-04T00:00:00+00:00",
            ).run_source_trial(configured.source_id, "task065-direct", trial)

        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(trial.provider, "stockanalysis")
        self.assertEqual(transport.requests, [DOCUMENT_URL])

    def test_workflow_propagates_provider_to_direct_document_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firm-catalog")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            template = load_canonical_template()
            profiles = SourceProfileRepository.initialize(
                root / "source-profiles", template
            )
            profiles.publish(SourceProfileDraft(
                "oracle",
                tuple(
                    SourceProfileItem(
                        item.artifact_id,
                        item.artifact_id == "earnings_transcript",
                        (
                            RetrievalCandidate(
                                "discovery", 1, discovery_class="standard",
                                provider="stockanalysis",
                                discovery_hint_kind="provider_identifier",
                                discovery_hint_value="ORCL",
                            ),
                        ) if item.artifact_id == "earnings_transcript" else (),
                    )
                    for item in template.artifacts
                ),
            ), None)
            repository = AcquisitionRepository(root / "acquisition")
            transport = Transport({DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT)})
            adapter = EarningsTranscriptPullAdapter(
                policies(), transport=transport, repository=repository,
                clock=lambda: "2026-08-04T00:00:00+00:00",
            )
            workflow = PullWorkflow(
                firms,
                profiles,
                template,
                repository,
                RetrievalAdapterRegistry((RetrievalAdapterRegistration(
                    RetrievalAdapterCapability(
                        adapter.adapter_id, adapter.artifact_ids,
                        adapter.retrieval_modes,
                    ),
                    adapter,
                ),)),
                PullRunRepository(root / "pull-workflows"),
                lambda: "2026-08-04T00:00:00+00:00",
                lambda: "task065",
            )
            result = workflow.acquire_transcript_from_seed(
                TranscriptAcquisitionTarget("oracle"),
                "stockanalysis",
                DOCUMENT_URL,
            )

        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [DOCUMENT_URL])

    def test_selected_provider_failure_does_not_learn_or_advance_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = profile()
            repository.register_source(configured)
            transport = Transport({DOCUMENT_URL: response(DOCUMENT_URL, b"missing", 404)})
            adapter = EarningsTranscriptPullAdapter(
                policies(), transport=transport, repository=repository,
                clock=lambda: "2026-08-04T00:00:00+00:00",
            )
            trial = adapter.injected_trial(
                configured,
                TranscriptAcquisitionTarget("oracle"),
                "stockanalysis",
                DOCUMENT_URL,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-04T00:00:00+00:00",
            ).run_source_trial(configured.source_id, "task065-failure", trial)
            learning = repository.discovery_anchors(
                "oracle", configured.source_id, adapter.adapter_id
            )

        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(result.checkpoint_before, result.checkpoint_after)
        self.assertEqual(learning, ())


class ExplicitProviderApiTests(unittest.TestCase):
    def test_body_provider_is_required_and_query_selection_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            ConceptRepository.initialize(state)
            firms = FirmRepository.initialize(state / "firm-catalog")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            server = create_admin_server(state, port=0)
            result = Mock()
            result.to_dict.return_value = {"status": "complete"}

            registry = TranscriptProviderRegistry((StockAnalysisTranscriptProvider,))

            def dispatch(
                target: TranscriptAcquisitionTarget, provider: str, starting_seed: str
            ) -> Mock:
                del target, starting_seed
                registry.resolve(provider)
                return result

            server.pull_workflow.acquire_transcript_from_seed = Mock(side_effect=dispatch)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            endpoint = f"http://{host}:{port}/api/transcript-acquisitions/seed"

            def post(payload: dict[str, object], suffix: str = "") -> tuple[int, dict]:
                request = urllib.request.Request(
                    endpoint + suffix,
                    data=json.dumps(payload).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=3) as reply:
                        return reply.status, json.load(reply)
                except urllib.error.HTTPError as error:
                    try:
                        return error.code, json.load(error)
                    finally:
                        error.close()

            valid = {
                "firm_id": "oracle",
                "canonical_artifact_id": "earnings_transcript",
                "provider": "stockanalysis",
                "starting_seed": DOCUMENT_URL,
            }
            try:
                self.assertEqual(post(valid)[0], 200)
                self.assertEqual(post({key: value for key, value in valid.items()
                                      if key != "provider"})[0], 400)
                for blank in ("", "   "):
                    with self.subTest(provider=blank):
                        self.assertEqual(post({**valid, "provider": blank})[0], 400)
                status, body = post({**valid, "provider": "unknown"})
                self.assertEqual(status, 400)
                self.assertEqual(body["error_code"], "invalid_request")
                query_status, query_body = post(
                    {key: value for key, value in valid.items() if key != "provider"},
                    "?provider=stockanalysis",
                )
                self.assertEqual(query_status, 400)
                self.assertEqual(
                    query_body["error"],
                    "transcript seed acquisition does not accept query parameters",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
