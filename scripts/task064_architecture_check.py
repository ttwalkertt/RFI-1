#!/usr/bin/env python3
"""Static TASK-064 ownership and dependency assertions."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = (ROOT / "src/rfi/discovery.py").read_text(encoding="utf-8")
PROVIDER = (
    ROOT / "src/rfi/acquisition/providers/stockanalysis.py"
).read_text(encoding="utf-8")
ALL_SOURCE = "\n".join(
    path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")
)

checks = {
    "orchestrator_has_no_stockanalysis_hostname": "stockanalysis.com" not in ORCHESTRATOR,
    "provider_owns_stockanalysis_hostname": "stockanalysis.com" in PROVIDER,
    "provider_has_no_repository_dependency": "AcquisitionRepository" not in PROVIDER,
    "provider_has_no_search_dependency": "DiscoverySearch" not in PROVIDER
    and "DuckDuckGo" not in PROVIDER,
    "no_event_group_id": "event_group_id" not in ALL_SOURCE,
    "no_crawlee": "crawlee" not in ALL_SOURCE.casefold(),
    "no_playwright": "playwright" not in ALL_SOURCE.casefold(),
    "no_browser_automation": "selenium" not in ALL_SOURCE.casefold(),
    "static_urllib_transport": "UrllibEarningsTranscriptTransport" in (
        ROOT / "scripts/task064_live_validation.py"
    ).read_text(encoding="utf-8"),
}
print(json.dumps(checks, indent=2, sort_keys=True))
if not all(checks.values()):
    raise SystemExit(1)
