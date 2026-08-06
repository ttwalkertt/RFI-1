#!/usr/bin/env python3
"""Generate deterministic TASK-067 CLI, API, persistence, RSS, and UI seed evidence."""

from __future__ import annotations

import base64
import io
import json
import shutil
import threading
from contextlib import redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from rfi.admin import create_admin_server
from rfi.admin.server import AdminConsole
from rfi.cli import initialize, main, seed
from rfi.feeds import FeedError, FeedPollRequest, FeedService, HttpResponse
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/feeds"


class FixtureTransport:
    def __init__(self) -> None:
        self.rss_url = "https://publisher.example/task067-rss"
        self.atom_url = "https://publisher.example/task067-atom"

    def fetch(self, url: str) -> HttpResponse:
        paths = {
            self.rss_url: ("rss.xml", "application/rss+xml"),
            self.atom_url: ("atom.xml", "application/atom+xml"),
            "https://content.example/rss-success": ("artifact-a.html", "text/html"),
            "https://content.example/atom-success": ("artifact-a.html", "text/html"),
            "https://alternate.example/manual": ("manual.txt", "text/plain"),
        }
        if url == "https://content.example/rss-unavailable":
            raise FeedError("HTTP 404")
        filename, media_type = paths[url]
        return HttpResponse((FIXTURES / filename).read_bytes(), media_type, url, 200)


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"review{self.value:06d}"


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_state(state: Path, transport: FixtureTransport) -> FeedService:
    if state.exists():
        shutil.rmtree(state)
    with redirect_stdout(io.StringIO()):
        initialize(state)
        seed(state)
    service = FeedService(state, transport=transport, identifier_factory=Ids())
    firm_ids = ["seagate", "western-digital"]
    service.create({
        "display_name": "Fixture RSS News", "feed_url": transport.rss_url,
        "enabled": True, "notes": "Review RSS source", "firm_ids": firm_ids,
    })
    service.create({
        "display_name": "Fixture Atom Commits", "feed_url": transport.atom_url,
        "enabled": True, "notes": "Review Atom source", "firm_ids": [],
    })
    return service


def request(
    server: AdminConsole,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    content = response.read()
    return {
        "request": {"method": method, "path": path, "body": body},
        "response": {
            "status": response.status,
            "content_type": response.getheader("Content-Type"),
            "body": (
                json.loads(content)
                if "json" in (response.getheader("Content-Type") or "")
                else content.decode()
            ),
        },
    }


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    transport = FixtureTransport()
    evidence_state = output / "evidence-state"
    service = create_state(evidence_state, transport)
    with patch("rfi.feeds.service.FeedHttpTransport.fetch", transport.fetch):
        human = io.StringIO()
        with redirect_stdout(human):
            human_code = main(["feeds", "poll", "--state", str(evidence_state)])
        (output / "cli-human.txt").write_text(
            "$ rfi feeds poll --state /absolute/path/to/state\n\n" + human.getvalue()
            + f"\nexit_code: {human_code}\n", encoding="utf-8",
        )
        structured = io.StringIO()
        with redirect_stdout(structured):
            json_code = main(["feeds", "poll", "--state", str(evidence_state), "--json"])
        (output / "cli-json.json").write_text(structured.getvalue(), encoding="utf-8")
        (output / "cli-json-exit.txt").write_text(f"exit_code: {json_code}\n", encoding="utf-8")

    latest = service.repository.runs(1)[0]
    json_write(output / "feed-run.json", latest)
    (output / "aggregate.rss").write_bytes(service.rss_export())
    reopened = FeedService(evidence_state, transport=transport)
    json_write(output / "restart-persistence.json", {
        "run_survived_restart": reopened.repository.run(latest["run_id"]) == latest,
        "feed_count": len(reopened.repository.list()),
        "observation_count": len(reopened.repository.export_items()),
        "unavailable_count": len(reopened.repository.tombstones("unresolved")),
    })

    unavailable = list(reopened.repository.tombstones("unresolved"))
    fulfilled = reopened.fulfill_upload(
        unavailable[0]["tombstone_id"],
        base64.b64encode((FIXTURES / "manual.txt").read_bytes()).decode(), "text/plain",
    )
    json_write(output / "manual-fulfillment.json", fulfilled)
    json_write(output / "schema-evidence.json", {
        "schema": RepositoryDatabase.open(evidence_state).validate(),
        "feed_revisions": sum(
            len(reopened.repository.history(item.feed_id))
            for item in reopened.repository.list()
        ),
    })
    (output / "cron-example.txt").write_text(
        "17 * * * * /absolute/path/to/rfi feeds poll --state /absolute/path/to/state --json\n",
        encoding="utf-8",
    )

    server = create_admin_server(evidence_state, port=0)
    server.feed_service = FeedService(evidence_state, transport=transport, identifier_factory=Ids())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        examples = [
            request(server, "GET", "/api/feeds"),
            request(server, "GET", "/api/feeds/runs"),
            request(server, "GET", "/api/feeds/unavailable?status=fulfilled"),
            request(server, "GET", "/api/feed-items.rss"),
        ]
        json_write(output / "api-examples.json", examples)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    ui_state = output / "ui-state"
    ui_service = create_state(ui_state, transport)
    ui_service.poll(FeedPollRequest(trigger="review_ui"))
    json_write(output / "ui-state-summary.json", {
        "state": str(ui_state), "feeds": len(ui_service.repository.list()),
        "runs": len(ui_service.repository.runs()),
        "unavailable": len(ui_service.repository.tombstones("unresolved")),
    })


if __name__ == "__main__":
    generate(ROOT / ".artifacts/task067-validation")
