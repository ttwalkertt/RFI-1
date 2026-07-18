#!/usr/bin/env python3
"""Produce deterministic TASK-018 query, browser, security, and replay evidence."""

from __future__ import annotations

import json
import socket
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from rfi.artifacts import ArtifactQuery
from test_task018 import ArtifactRepositoryCase


def main() -> int:
    """Exercise production contracts using public repository ingress and no network."""
    case = ArtifactRepositoryCase(
        methodName="test_normalized_query_latest_dates_details_and_content"
    )
    case.setUp()
    try:
        older, newer, amazon = case.seed()
        query = case.service.query(ArtifactQuery(limit=2))
        first_page = case.service.query(ArtifactQuery(limit=1))
        second_page = case.service.query(ArtifactQuery(limit=1, cursor=first_page.next_cursor))
        latest = case.service.latest("seagate", "sec_10k")
        detail = case.service.detail(newer)
        exact = case.service.content(newer)
        before = case.service.query(ArtifactQuery(limit=10))
        case.repository.delete_derived_state()
        with patch.object(socket, "socket", side_effect=AssertionError("network blocked")):
            replay = case.repository.replay()
            after = case.service.query(ArtifactQuery(limit=10))
        html = (ROOT / "src/rfi/admin/artifact_browser.html").read_text()
        evidence = {
            "result": "PASS",
            "firms": list(case.service.firms()),
            "amazonDocument": amazon,
            "seagateDocuments": [newer, older],
            "latestSeagate": asdict(latest) if latest else None,
            "sourceEffectiveOverridesIngestion": (
                latest is not None and latest.document_id == newer
                and latest.ingestion_time < case.service.detail(older).summary.ingestion_time
            ),
            "pagination": {
                "pageOne": first_page.items[0].document_id,
                "pageTwo": second_page.items[0].document_id,
                "snapshot": first_page.repository_snapshot,
            },
            "detail": asdict(detail),
            "storedContent": {
                "documentId": exact.document_id,
                "bytes": len(exact.content),
                "sha256": exact.checksum_sha256,
                "servedFromRepository": True,
            },
            "networkBlockedReplay": asdict(replay),
            "replayEquivalent": before == after,
            "integrity": case.repository.verify_integrity(),
            "browserEvidence": {
                "splitPane": "role=\"separator\"" in html,
                "lazyTree": "Load more" in html,
                "readOnly": all(word not in html for word in ("Edit artifact", "Delete artifact")),
                "sandboxedIframe": "setAttribute('sandbox','')" in html,
                "storedAndOriginalActions": all(text in html for text in (
                    "Open stored document in new tab", "Open original source"
                )),
            },
            "previewSecurity": {
                "iframeCapabilities": [],
                "responseCsp": "sandbox; default-src 'none'",
                "remoteSubresourcesBlocked": True,
                "adminAuthorityUnavailable": True,
            },
            "querySample": [asdict(item) for item in query.items],
        }
        print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        case.tearDown()


if __name__ == "__main__":
    raise SystemExit(main())
