from __future__ import annotations

import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.admin.help import (  # noqa: E402
    GUIDE_PATH,
    HELP_TOPICS,
    HELP_WINDOW_NAME,
    PAGE_HELP_TOPICS,
    TOPICS_BY_ID,
    guide_source,
    guide_topic_ids,
    render_guide_markdown,
    topic_url,
)
from rfi.cli import initialize  # noqa: E402


class HelpContractCase(unittest.TestCase):
    def test_canonical_guide_topics_are_explicit_stable_and_unique(self) -> None:
        self.assertEqual(GUIDE_PATH, ROOT / "docs/operator-guide.md")
        topic_ids = guide_topic_ids()
        self.assertEqual(topic_ids, tuple(topic.topic_id for topic in HELP_TOPICS))
        self.assertEqual(len(topic_ids), len(set(topic_ids)))
        self.assertTrue(all(TOPICS_BY_ID[item].topic_id == item for item in topic_ids))

    def test_every_major_page_has_one_valid_context_mapping(self) -> None:
        expected = {
            "/concepts", "/firms", "/source-profiles", "/external-sources",
            "/pull-sources", "/linux-mailing-lists", "/streams", "/artifacts",
        }
        self.assertEqual(set(PAGE_HELP_TOPICS), expected)
        self.assertTrue(set(PAGE_HELP_TOPICS.values()).issubset(TOPICS_BY_ID))
        self.assertEqual(len(PAGE_HELP_TOPICS), len(set(PAGE_HELP_TOPICS)))

    def test_canonical_links_and_rendered_representative_content(self) -> None:
        source = guide_source()
        internal_links = re.findall(r"\[[^]]+]\(#([a-z][a-z0-9-]*)\)", source)
        self.assertGreater(len(internal_links), 25)
        self.assertEqual(set(internal_links) - set(TOPICS_BY_ID), set())
        rendered = render_guide_markdown(source)
        for text in (
            '<h2 id="acquisition"',
            '<h2 id="streams"',
            '<h2 id="repository-protection"',
            "<pre><code>",
            'href="/help/artifacts#artifacts"',
            (
                'href="/help/external-sources#external-sources">save a repository-global '
                "External Source</a>"
            ),
            (
                'href="/help/stream-upstream-definitions#stream-upstream-definitions">save '
                "compatible upstream definitions</a>"
            ),
            '<h3 id="stream-upstream-definitions"',
            "Pull selected firms",
            "Save source-profile revision",
            "Review imported YAML",
            "rfi backup --state STATE --output repository-backup.zip",
        ):
            self.assertIn(text, rendered)
        self.assertNotIn("<script", rendered.casefold())

    def test_topic_url_rejects_unknown_identity(self) -> None:
        self.assertEqual(topic_url("firms"), "/help/firms#firms")
        with self.assertRaisesRegex(ValueError, "unknown help topic"):
            topic_url("not-a-topic")


class HelpServerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        initialize(self.state)
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def get(self, path: str) -> tuple[int, str, dict[str, str]]:
        try:
            response = urllib.request.urlopen(self.base + path, timeout=3)
        except urllib.error.HTTPError as error:
            body = error.read().decode()
            headers = dict(error.headers.items())
            error.close()
            return error.code, body, headers
        with response:
            return response.status, response.read().decode(), dict(response.headers.items())

    def test_help_is_served_locally_from_canonical_content(self) -> None:
        status, body, headers = self.get("/help")
        self.assertEqual(status, 200)
        self.assertIn("RFI-1 Operator Guide", body)
        self.assertIn("Acquisition procedure", body)
        self.assertIn("Use browser Find", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn('href="https://', body)

    def test_every_page_has_deep_link_with_shared_named_target(self) -> None:
        for page, topic_id in PAGE_HELP_TOPICS.items():
            with self.subTest(page=page):
                status, body, _headers = self.get(page)
                self.assertEqual(status, 200)
                expected = (
                    f'<a class="operator-help" href="{topic_url(topic_id)}" '
                    f'target="{HELP_WINDOW_NAME}"'
                )
                self.assertIn(expected, body)
                self.assertEqual(body.count('class="operator-help"'), 1)
                self.assertNotIn('href="/help" target="_self"', body)

    def test_deep_link_and_unknown_topic_handling(self) -> None:
        status, body, _headers = self.get("/help/streams")
        self.assertEqual(status, 200)
        self.assertIn('<h2 id="streams" tabindex="-1">Artifact Streams</h2>', body)
        status, body, _headers = self.get("/help/not-a-real-topic")
        self.assertEqual(status, 404)
        self.assertIn("Unknown Help topic", body)
        self.assertIn("no application state was changed", body)
        self.assertIn('href="/help/getting-started#getting-started"', body)

    def test_help_navigation_is_non_modal_and_does_not_submit_or_replace_page(self) -> None:
        _status, body, _headers = self.get("/streams")
        link = re.search(r'<a class="operator-help"[^>]+>', body)
        self.assertIsNotNone(link)
        markup = link.group(0)  # type: ignore[union-attr]
        self.assertIn('target="rfi-operator-help"', markup)
        self.assertNotIn("onclick=", markup)
        self.assertNotIn("download", markup)
        self.assertNotIn("modal", markup.casefold())
        self.assertIn('<form id="form">', body)


if __name__ == "__main__":
    unittest.main()
