"""Rendered-browser coverage for the TASK-028 stored-message viewer."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.storage import RepositoryDatabase


ROOT = Path(__file__).resolve().parents[1]
MESSAGE_ID = "<task028-long-header@kernel.example>"


def long_header_message() -> bytes:
    headers = [
        f"Message-ID: {MESSAGE_ID}",
        "Subject: [PATCH] block: long-header viewer proof",
        "From: Viewer Proof <viewer@example.com>",
        "Date: Tue, 21 Jul 2026 18:00:00 +0000",
        "Content-Type: text/plain; charset=utf-8",
    ]
    headers.extend(
        f"X-Long-Header-{index:03d}: retained header value {index:03d}"
        for index in range(1, 221)
    )
    body = [f"BODY-LINE-{index:03d}: independently scrollable content" for index in range(400)]
    body.append("BODY-END-MARKER")
    return ("\r\n".join(headers) + "\r\n\r\n" + "\r\n".join(body) + "\r\n").encode()


class StoredMessageViewerBrowserCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.state = Path(cls.temporary.name)
        RepositoryDatabase.initialize(cls.state)
        FirmRepository.initialize(cls.state / "firm-catalog")
        repository = MailingListRepository(cls.state)
        repository.configure_source(LINUX_BLOCK_SOURCE)
        raw = long_header_message()
        service = MailingListAcquisitionService(
            repository,
            FixtureMailingListArchive({
                MESSAGE_ID: ArchiveMessage(raw, "fixture:task028-long-header.eml")
            }),
            clock=lambda: "2026-07-21T18:00:00+00:00",
            identifiers=lambda: "mailrun-task028-message-viewer",
        )
        service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(MESSAGE_ID,)),
            AcquisitionLimits(seed_limit=1, context_limit=5, descendant_depth=1),
        )
        message_key = str(repository.rows(
            "SELECT message_key FROM mailing_list_messages WHERE external_message_id=?",
            (MESSAGE_ID,),
        )[0]["message_key"])
        cls.server = create_admin_server(cls.state, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        screenshot = os.environ.get(
            "RFI_VIEWER_SCREENSHOT", str(cls.state / "message-viewer.png")
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/task028_message_viewer_browser.mjs"),
                base,
                message_key,
                screenshot,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise AssertionError(
                "rendered message-viewer proof failed:\n" + result.stdout + result.stderr
            )
        cls.proof = json.loads(result.stdout)
        cls.raw_size = len(raw)
        cls.screenshot = Path(screenshot)
        cls.initial_screenshot = cls.screenshot.with_name(
            cls.screenshot.stem + "-initial" + cls.screenshot.suffix
        )
        if proof_path := os.environ.get("RFI_VIEWER_PROOF_JSON"):
            Path(proof_path).write_text(json.dumps(cls.proof, indent=2) + "\n")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temporary.cleanup()

    def test_long_headers_are_separate_and_body_is_immediately_reachable(self) -> None:
        initial = self.proof["initial"]
        self.assertTrue(initial["headerCollapsed"])
        self.assertTrue(initial["headerContainsLast"])
        self.assertTrue(initial["bodyContainsStart"])
        self.assertTrue(initial["bodyContainsEnd"])
        self.assertTrue(initial["sectionsDistinct"])
        self.assertEqual(initial["rawBytes"], self.raw_size)
        self.assertEqual(initial["bodyTabIndex"], 0)
        self.assertEqual(initial["bodyRole"], "region")

    def test_wheel_and_keyboard_scroll_only_the_message_body(self) -> None:
        self.assertGreater(self.proof["wheelScrollTop"], 0)
        self.assertGreater(self.proof["keyboardScrollTop"], self.proof["wheelScrollTop"])

    def test_desktop_and_narrow_viewports_retain_a_scrolling_body_region(self) -> None:
        for name in ("desktop", "mobile"):
            geometry = self.proof[name]
            self.assertTrue(geometry["visible"], name)
            self.assertEqual(geometry["overflowY"], "auto", name)
            self.assertGreater(geometry["clientHeight"], 80, name)
            self.assertGreater(geometry["scrollHeight"], geometry["clientHeight"], name)
            self.assertGreaterEqual(geometry["bodyTop"], geometry["previewTop"] - 1, name)
            self.assertLessEqual(geometry["bodyBottom"], geometry["previewBottom"] + 1, name)
        self.assertTrue(self.screenshot.is_file())
        self.assertTrue(self.initial_screenshot.is_file())


if __name__ == "__main__":
    unittest.main()
