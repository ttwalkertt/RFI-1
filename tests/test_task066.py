"""Focused acceptance evidence for TASK-066 WDC Business Wire acquisition."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    PressReleaseAcquisitionSelection,
    RunStatus,
    SourceProfile,
)
from rfi.acquisition.contracts import IntegrityError
from rfi.acquisition.wdc_press_release import (
    ADAPTER_ID,
    PressReleaseHttpResponse,
    SEARCH_URL,
    WdcBusinessWirePressReleaseAdapter,
    parse_press_release,
)
from rfi.firms import FirmDraft, FirmRepository, FirmStatus
from rfi.firm_configuration import load_firm_configurations
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/press-releases"
LATEST = "https://www.businesswire.com/news/home/20260805177075/en/Latest-WDC"
FALSE = "https://www.businesswire.com/news/home/20260805455789/en/Sandisk-Mentions-WDC"
OLDER = "https://www.businesswire.com/news/home/20260720524833/en/Older-WDC"
EARLIEST = "https://www.businesswire.com/news/home/20260601510484/en/Earliest-WDC"


class Transport:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> PressReleaseHttpResponse:
        self.requests.append(url)
        if url not in self.responses:
            raise OSError(url)
        return PressReleaseHttpResponse(url, 200, "text/html", self.responses[url])


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def responses(*, second_page: bool = False) -> dict[str, bytes]:
    value = {
        SEARCH_URL: fixture("businesswire-wdc-page-1.html"),
        LATEST: fixture("businesswire-wdc-latest.html"),
        FALSE: fixture("businesswire-false-positive.html"),
    }
    if second_page:
        value.update({
            SEARCH_URL + "&page=2": fixture("businesswire-wdc-page-2.html"),
            OLDER: fixture("businesswire-wdc-older.html"),
            EARLIEST: fixture("businesswire-wdc-earliest.html"),
        })
    return value


def profile(**configuration: object) -> SourceProfile:
    return SourceProfile(
        "source-wdc-press-release",
        "Western Digital press releases",
        True,
        ADAPTER_ID,
        {
            "mode": "discovery",
            "provider": ADAPTER_ID,
            "discovery_hint_kind": "configured_search_url",
            "discovery_hint_value": SEARCH_URL,
            **configuration,
        },
        {
            "firm_id": "western-digital",
            "artifact_id": "press_release",
            "retrieval_adapter_id": ADAPTER_ID,
            "source_profile_revision_id": "profile-wdc-r1",
        },
    )


class Task066Tests(unittest.TestCase):
    @staticmethod
    def repository() -> AcquisitionRepository:
        root = Path(tempfile.mkdtemp())
        firms = FirmRepository.initialize(root / "firm-catalog")
        firms.create(FirmDraft(
            "western-digital", "Western Digital", "2020-01-01",
            legal_name="Western Digital Corporation", status=FirmStatus.ACTIVE,
        ))
        return AcquisitionRepository(root / "acquisition")

    def run_engine(
        self,
        transport: Transport,
        selection: PressReleaseAcquisitionSelection | None = None,
        *,
        repository: AcquisitionRepository | None = None,
        run_key: str = "task066",
        source: SourceProfile | None = None,
    ):
        repository = repository or self.repository()
        source = source or profile()
        repository.register_source(source)
        adapter = WdcBusinessWirePressReleaseAdapter(
            transport,
            lambda: "2026-08-05T22:00:00+00:00",
            selection,
        )
        result = AcquisitionEngine(
            repository,
            AdapterRegistry((adapter,)),
            lambda: "2026-08-05T22:00:00+00:00",
        ).run_source(source.source_id, run_key)
        return repository, result

    def test_registration_and_authoritative_wdc_firm_configuration(self) -> None:
        adapter = WdcBusinessWirePressReleaseAdapter(Transport({}))
        self.assertEqual(AdapterRegistry((adapter,)).registrations(), {
            ADAPTER_ID: "WdcBusinessWirePressReleaseAdapter"
        })
        schema = json.loads(
            (ROOT / "src/rfi/resources/firm-config-v1.schema.json").read_text()
        )
        configured = json.loads(
            (ROOT / "docs/western-digital.firm-config.example.json").read_text()
        )
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(configured)), [])
        self.assertEqual(
            configured["sources"]["press_release"]["discovery_hint"]["value"],
            SEARCH_URL,
        )
        root = Path(tempfile.mkdtemp())
        database = RepositoryDatabase.initialize(root)
        directory = root / "firm-config"
        directory.mkdir()
        (directory / "western-digital.firm-config.json").write_bytes(
            (ROOT / "docs/western-digital.firm-config.example.json").read_bytes()
        )
        loaded = load_firm_configurations(root, database)
        press_release = next(
            item for item in loaded[0].profile.items
            if item.artifact_id == "press_release"
        )
        self.assertEqual(press_release.retrieval_candidates[0].provider, ADAPTER_ID)
        self.assertEqual(
            press_release.retrieval_candidates[0].discovery_hint_value, SEARCH_URL
        )

    def test_latest_qualifies_wdc_and_rejects_newer_false_positive(self) -> None:
        transport = Transport(responses())
        repository, result = self.run_engine(transport)
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(result.skips, 1)
        attempt = next(x for x in repository.history() if x.get("outcome") == "success")
        normalized = attempt["diagnostics"]["normalized_press_release"]
        self.assertEqual(normalized["issuer"], "Western Digital Corporation")
        self.assertEqual(normalized["ticker"], "NASDAQ:WDC")
        self.assertEqual(normalized["businesswire_release_id"], "20260805177075")
        self.assertEqual(repository.read_artifact(attempt["artifact_id"]), fixture(
            "businesswire-wdc-latest.html"
        ))

    def test_complete_body_and_pertinent_metadata_extraction(self) -> None:
        parsed = parse_press_release(fixture("businesswire-wdc-latest.html"), LATEST)
        self.assertIn("final paragraph proves complete", parsed.body)
        self.assertEqual(parsed.dateline, "SAN JOSE, Calif.")
        self.assertIn("First highlight", parsed.summary)
        self.assertIn("investor@wdc.com", parsed.contacts)
        self.assertEqual(parsed.attachments[0]["label"], "Download report")
        self.assertEqual(parsed.publication_timestamp, "2026-08-05T20:02:00+00:00")

    def test_inclusive_range_returns_earliest_qualified_release(self) -> None:
        selection = PressReleaseAcquisitionSelection.first_in_date_range(
            date(2026, 6, 1), date(2026, 7, 31)
        )
        transport = Transport(responses(second_page=True))
        repository, result = self.run_engine(transport, selection)
        self.assertEqual(result.status, RunStatus.COMPLETE)
        attempt = next(x for x in repository.history() if x.get("outcome") == "success")
        self.assertEqual(
            attempt["diagnostics"]["normalized_press_release"]["businesswire_release_id"],
            "20260601510484",
        )
        self.assertIn(SEARCH_URL + "&page=2", transport.requests)

    def test_range_no_result_is_explicit_success(self) -> None:
        selection = PressReleaseAcquisitionSelection.first_in_date_range(
            date(2026, 5, 1), date(2026, 5, 31)
        )
        _repository, result = self.run_engine(
            Transport(responses(second_page=True)), selection
        )
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(result.failures, 0)
        self.assertGreater(result.skips, 0)

    def test_pagination_preserves_search_and_suppresses_duplicate(self) -> None:
        selection = PressReleaseAcquisitionSelection.first_in_date_range(
            date(2026, 6, 1), date(2026, 7, 31)
        )
        _repository, result = self.run_engine(
            Transport(responses(second_page=True)), selection
        )
        page = result.diagnostics[0]
        self.assertEqual(page["listing_pages_fetched"], 2)
        self.assertEqual(page["duplicate_release_urls_suppressed"], 1)
        self.assertEqual(page["pagination_mechanism"], "preserve query and append page=N")

    def test_idempotency_and_changed_source_bytes_append_observations(self) -> None:
        transport = Transport(responses())
        repository = self.repository()
        repository, first = self.run_engine(transport, repository=repository, run_key="one")
        _repository, replay = self.run_engine(transport, repository=repository, run_key="two")
        self.assertEqual(first.durable_acquisitions, 1)
        self.assertEqual(replay.unchanged, 1)
        changed = fixture("businesswire-wdc-latest.html").replace(
            b"complete release body extraction.", b"complete release body extraction changed."
        )
        changed_transport = Transport({**responses(), LATEST: changed})
        _repository, revised = self.run_engine(
            changed_transport, repository=repository, run_key="three"
        )
        self.assertEqual(revised.durable_acquisitions, 1)
        successful = [x for x in repository.history() if x.get("outcome") == "success"]
        self.assertEqual(len({x["artifact_id"] for x in successful}), 2)

    def test_malformed_discovery_detail_and_pagination_loop_fail_observably(self) -> None:
        for name, mapping, expected in (
            ("discovery", {SEARCH_URL: b"<html>changed</html>"}, "unsupported_discovery_page"),
            (
                "detail",
                {**responses(), LATEST: b"<html><h1>broken</h1></html>"},
                "malformed_detail_page",
            ),
            (
                "loop",
                {
                    **responses(second_page=True),
                    SEARCH_URL + "&page=2": fixture("businesswire-wdc-page-1.html"),
                },
                "pagination_loop",
            ),
        ):
            with self.subTest(name=name):
                selection = (
                    PressReleaseAcquisitionSelection.first_in_date_range(
                        date(2026, 6, 1), date(2026, 7, 31)
                    )
                    if name == "loop" else None
                )
                _repository, result = self.run_engine(Transport(mapping), selection)
                self.assertNotEqual(result.status, RunStatus.COMPLETE)
                codes = {str(x.get("failure_code")) for x in result.diagnostics}
                self.assertIn(expected, codes)

    def test_repository_failure_is_not_hidden(self) -> None:
        repository = self.repository()
        original = repository.record_success

        def fail(*args, **kwargs):
            raise IntegrityError("injected repository failure")

        repository.record_success = fail  # type: ignore[method-assign]
        try:
            _repository, result = self.run_engine(
                Transport(responses()), repository=repository
            )
        finally:
            repository.record_success = original  # type: ignore[method-assign]
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertTrue(any(
            item.get("failure_class") == "repository_integrity"
            for item in result.diagnostics
        ))

    def test_wdc_specific_boundary_rejects_parallel_firm_use(self) -> None:
        invalid = replace(profile(), policy={
            **profile().policy, "firm_id": "sandisk"
        })
        repository = self.repository()
        repository.register_source(invalid)
        result = AcquisitionEngine(
            repository,
            AdapterRegistry((WdcBusinessWirePressReleaseAdapter(Transport({})),)),
            lambda: "2026-08-05T22:00:00+00:00",
        ).run_source(invalid.source_id, "wrong-firm")
        self.assertEqual(result.status, RunStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
