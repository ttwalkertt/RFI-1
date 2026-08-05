#!/usr/bin/env python3
"""Capture and verify bounded, non-browser TASK-066 transport evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from rfi.acquisition.engine import AdapterFailure
from rfi.acquisition.wdc_press_release import (
    SEARCH_URL,
    UrllibPressReleaseTransport,
)

DETAIL_URL = (
    "https://www.businesswire.com/news/home/20260129523920/en/"
    "Western-Digital-Reports-Fiscal-Second-Quarter-2026-Financial-Results"
)
PUBLIC_RSS_URL = (
    "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpQWQ=="
)
WDC_IR_LISTING = "https://investor.wdc.com/news-releases"
WDC_IR_DETAIL = (
    "https://investor.wdc.com/news-releases/news-release-details/"
    "western-digital-reports-fiscal-second-quarter-2026-financial"
)
def _raw_probe(name: str, url: str, raw_directory: Path) -> dict[str, object]:
    raw_directory.mkdir(parents=True, exist_ok=True)
    body_path = raw_directory / f"{name}.body"
    headers_path = raw_directory / f"{name}.headers"
    result = subprocess.run(
        [
            "curl", "--http1.1", "--max-time", "30", "--location", "--silent", "--show-error",
            "--dump-header", str(headers_path),
            "--output", str(body_path), "--write-out",
            "%{http_code}\t%{url_effective}\t%{content_type}\t%{size_download}", url,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=35,
        check=False,
    )
    values = result.stdout.split("\t", 3)
    values.extend([""] * (4 - len(values)))
    status_text, resolved_url, media_type, _size = values
    status = int(status_text) if status_text.isdigit() else 0
    body = body_path.read_bytes() if body_path.is_file() else b""
    return {
        "name": name,
        "requested_url": url,
        "resolved_url": resolved_url,
        "status": status,
        "media_type": media_type,
        "body_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "error": result.stderr.strip(),
        "raw_body": body_path.name,
        "raw_headers": headers_path.name,
    }


def _production_probe(url: str) -> dict[str, object]:
    try:
        response = UrllibPressReleaseTransport(timeout_seconds=10).get(url)
        return {
            "result": "response",
            "status": response.status,
            "resolved_url": response.url,
            "media_type": response.media_type,
            "body_bytes": len(response.content),
            "body_sha256": hashlib.sha256(response.content).hexdigest(),
        }
    except AdapterFailure as exc:
        return {
            "result": "adapter_failure",
            "failure_class": exc.classification.value,
            "failure_code": exc.code,
            "retryable": exc.retryable,
            "message": str(exc),
            "cause": repr(exc.__cause__),
        }


def _rss_assessment(raw_directory: Path) -> dict[str, object]:
    content = (raw_directory / "businesswire-public-rss.body").read_bytes()
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return {"parseable": False}
    items = root.findall("./channel/item")
    descriptions = [(item.findtext("description") or "") for item in items]
    links = [(item.findtext("link") or "") for item in items]
    return {
        "parseable": True,
        "channel_title": root.findtext("./channel/title") or "",
        "item_count": len(items),
        "western_digital_item_count": sum(
            "western digital" in " ".join(item.itertext()).casefold()
            for item in items
        ),
        "maximum_description_characters": max(map(len, descriptions), default=0),
        "all_item_links_require_businesswire_detail": bool(links) and all(
            "businesswire.com/news/home/" in link for link in links
        ),
        "surface_kind": "preconfigured category headline RSS; not full release text",
    }


def capture(output: Path) -> dict[str, object]:
    raw_directory = output.parent / "transport-raw"
    probes = [
        _raw_probe("businesswire-newsroom", SEARCH_URL, raw_directory),
        _raw_probe("businesswire-detail", DETAIL_URL, raw_directory),
        _raw_probe(
            "businesswire-robots", "https://www.businesswire.com/robots.txt", raw_directory
        ),
        _raw_probe(
            "businesswire-sitemap", "https://www.businesswire.com/sitemap.xml", raw_directory
        ),
        _raw_probe(
            "businesswire-feed-help",
            "https://www.businesswire.com/help/feed-options",
            raw_directory,
        ),
        _raw_probe("businesswire-public-rss", PUBLIC_RSS_URL, raw_directory),
        _raw_probe("wdc-ir-listing", WDC_IR_LISTING, raw_directory),
        _raw_probe("wdc-ir-detail", WDC_IR_DETAIL, raw_directory),
    ]
    value: dict[str, object] = {
        "captured_at": datetime.now(UTC).isoformat(),
        "method": (
            "production UrllibPressReleaseTransport probes plus bounded conventional curl "
            "raw-response capture; no browser headers, cookies, or evasion"
        ),
        "prohibited_methods_used": [],
        "production_transport": {
            "newsroom": _production_probe(SEARCH_URL),
            "detail": _production_probe(DETAIL_URL),
        },
        "raw_http_probes": probes,
        "public_rss_assessment": _rss_assessment(raw_directory),
        "businesswire_direct_transport_viable": False,
        "task066_operational_status": "blocked",
        "decision": (
            "No tested lawful public Business Wire surface provides deterministic "
            "WDC discovery plus complete release bytes from this execution environment."
        ),
        "recommendation": (
            "Authorize a separate WDC issuer-archive transport feasibility task; if direct "
            "access is established there, use WDC for discovery and acquisition and retain "
            "the Business Wire URL as related-source metadata. Otherwise explicitly defer "
            "Business Wire support."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate(value)
    return value


def validate(value: dict[str, object]) -> None:
    if value.get("task066_operational_status") != "blocked":
        raise RuntimeError("TASK-066 evidence must retain the blocking status")
    if value.get("businesswire_direct_transport_viable") is not False:
        raise RuntimeError("evidence unexpectedly claims viable Business Wire transport")
    production = value.get("production_transport")
    if not isinstance(production, dict):
        raise RuntimeError("production transport evidence is missing")
    for key in ("newsroom", "detail"):
        result = production.get(key)
        if not isinstance(result, dict) or result.get("result") != "adapter_failure":
            raise RuntimeError(f"production {key} did not record an adapter failure")
    rss = value.get("public_rss_assessment")
    if not isinstance(rss, dict) or rss.get("parseable") is not True:
        raise RuntimeError("public Business Wire RSS evidence is missing")
    if rss.get("all_item_links_require_businesswire_detail") is not True:
        raise RuntimeError("RSS evidence no longer matches the assessed headline surface")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        value = json.loads(args.verify.read_text(encoding="utf-8"))
        validate(value)
        print(json.dumps({"verified": str(args.verify)}, indent=2))
        return 0
    if args.output is None:
        parser.error("--output is required unless --verify is supplied")
    print(json.dumps(capture(args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
