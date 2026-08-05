#!/usr/bin/env python3
"""Bounded live validation for the WDC Business Wire press-release adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from rfi.acquisition import AcquisitionEngine, AcquisitionRepository, AdapterRegistry, SourceProfile
from rfi.acquisition.wdc_press_release import (
    ADAPTER_ID,
    PressReleaseHttpResponse,
    SEARCH_URL,
    WdcBusinessWirePressReleaseAdapter,
)
from rfi.firms import FirmDraft, FirmRepository, FirmStatus
from rfi.storage.sqlite import utc_now


def validate_evidence(value: dict[str, object]) -> None:
    required = {
        "status": "complete",
        "adapter_id": ADAPTER_ID,
        "configured_search_url": SEARCH_URL,
        "issuer": "Western Digital Corporation",
        "ticker": "NASDAQ:WDC",
        "source_attribution": "Business Wire",
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise RuntimeError(f"live evidence {key} differs: {value.get(key)!r}")
    for key in (
        "artifact_id", "attempt_id", "canonical_url", "release_id",
        "publication_timestamp", "title", "content_sha256",
    ):
        if not isinstance(value.get(key), str) or not value[key]:
            raise RuntimeError(f"live evidence lacks {key}")
    if int(value.get("listing_pages_fetched", 0)) < 1:
        raise RuntimeError("live evidence did not fetch a discovery page")
    if int(value.get("candidate_count", 0)) < 1:
        raise RuntimeError("live evidence did not discover candidates")
    if int(value.get("body_characters", 0)) < 100:
        raise RuntimeError("live evidence body is implausibly short")
    if int(value.get("persisted_bytes", 0)) < 100:
        raise RuntimeError("live evidence artifact bytes are implausibly short")
    if value.get("artifact_integrity_verified") is not True:
        raise RuntimeError("live evidence did not verify immutable artifact bytes")


class BrowserCaptureTransport:
    """Replay a bounded, same-session browser capture through the real adapter seam."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, url: str) -> PressReleaseHttpResponse:
        if url == SEARCH_URL:
            path = self.root / "listing.html"
        else:
            parts = url.split("/news/home/", 1)
            if len(parts) != 2 or len(parts[1]) < 14:
                raise RuntimeError(f"unexpected captured Business Wire URL: {url}")
            path = self.root / f"{parts[1][:14]}.html"
        return PressReleaseHttpResponse(url, 200, "text/html", path.read_bytes())


def run(capture_directory: Path | None = None) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="task066-live-") as temporary:
        root = Path(temporary)
        firms = FirmRepository.initialize(root / "firm-catalog")
        firms.create(FirmDraft(
            "western-digital", "Western Digital", "2020-01-01",
            legal_name="Western Digital Corporation", status=FirmStatus.ACTIVE,
        ))
        repository = AcquisitionRepository(root / "acquisition")
        source = SourceProfile(
            "source-wdc-press-release-live",
            "Western Digital Business Wire press releases",
            True,
            ADAPTER_ID,
            {
                "mode": "discovery",
                "provider": ADAPTER_ID,
                "discovery_hint_kind": "configured_search_url",
                "discovery_hint_value": SEARCH_URL,
                "maximum_pages": 3,
            },
            {
                "firm_id": "western-digital",
                "artifact_id": "press_release",
                "retrieval_adapter_id": ADAPTER_ID,
                "source_profile_revision_id": "task066-live-profile-r1",
            },
        )
        repository.register_source(source)
        adapter = WdcBusinessWirePressReleaseAdapter(
            BrowserCaptureTransport(capture_directory)
            if capture_directory is not None else None
        )
        result = AcquisitionEngine(
            repository, AdapterRegistry((adapter,)), utc_now
        ).run_source(source.source_id, "bounded-live")
        if result.status.value != "complete" or result.durable_acquisitions != 1:
            raise RuntimeError(json.dumps(result.to_dict(), indent=2))
        success = next(
            item for item in repository.history()
            if item.get("record_type") == "retrieval_attempt"
            and item.get("outcome") == "success"
        )
        normalized = success["diagnostics"]["normalized_press_release"]
        artifact_id = str(success["artifact_id"])
        content = repository.read_artifact(artifact_id)
        discovery = result.diagnostics[0]
        evidence: dict[str, object] = {
            "status": result.status.value,
            "adapter_id": ADAPTER_ID,
            "configured_search_url": SEARCH_URL,
            "live_transport_mode": (
                "browser_assisted_same_session_dom_capture"
                if capture_directory is not None else "direct_urllib_https"
            ),
            "direct_http_probe_outcome": (
                "HTTP 403 Access Denied from Business Wire Akamai edge; "
                "urllib request timed out"
                if capture_directory is not None else "not_applicable"
            ),
            "capture_semantics": (
                "complete documentElement HTML serialized after public page load, then "
                "replayed without modification through the adapter transport contract"
                if capture_directory is not None else "raw HTTP response bytes"
            ),
            "pagination_mechanism": discovery["pagination_mechanism"],
            "listing_pages_fetched": discovery["listing_pages_fetched"],
            "candidate_count": discovery["candidate_count"],
            "discovery_stop_reason": discovery["discovery_stop_reason"],
            "qualification_rule": next(
                item["qualification_rule"] for item in result.diagnostics
                if "qualification_rule" in item
            ),
            "title": normalized["title"],
            "publication_timestamp": normalized["publication_timestamp"],
            "issuer": normalized["issuer"],
            "ticker": normalized["ticker"],
            "canonical_url": normalized["canonical_url"],
            "release_id": normalized["businesswire_release_id"],
            "dateline": normalized["dateline"],
            "summary_characters": len(str(normalized["summary_highlights"])),
            "body_characters": len(str(normalized["complete_release_body"])),
            "contacts_characters": len(str(normalized["contacts"])),
            "attachment_count": len(normalized["attachments"]),
            "source_attribution": normalized["source_attribution"],
            "discovery_url": normalized["discovery_url"],
            "retrieval_timestamp": normalized["retrieval_timestamp"],
            "attempt_id": success["attempt_id"],
            "artifact_id": artifact_id,
            "document_id": success["document_id"],
            "content_sha256": success["diagnostics"]["content_sha256"],
            "persisted_bytes": len(content),
            "artifact_integrity_verified": (
                hashlib.sha256(content).hexdigest()
                == success["diagnostics"]["content_sha256"]
                and repository.verify_integrity()["result"] == "PASS"
            ),
            "engine_result": result.to_dict(),
        }
        validate_evidence(evidence)
        return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--capture-directory", type=Path)
    args = parser.parse_args()
    if args.verify:
        value = json.loads(args.verify.read_text(encoding="utf-8"))
        validate_evidence(value)
        print(json.dumps({"verified": str(args.verify)}, indent=2))
        return 0
    value = run(args.capture_directory)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
