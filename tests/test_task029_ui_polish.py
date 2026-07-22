"""Focused static regression evidence for the scoped TASK-029 UI polish."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Task029UiPolishCase(unittest.TestCase):
    def test_summary_prioritizes_health_coverage_and_latest_acquisition(self) -> None:
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()

        self.assertIn('id="summary-health"', html)
        self.assertIn('id="summary-coverage"', html)
        self.assertIn("Current through", html)
        self.assertIn('id="last-acquisition"', html)
        self.assertIn("Last acquisition summary", html)
        self.assertIn("Direct messages", html)
        self.assertIn("Context messages", html)
        self.assertNotIn("Derived from contiguous complete repository coverage", html)

    def test_retained_evidence_is_collapsed_without_losing_scroll_contract(self) -> None:
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()

        self.assertIn('<details id="outcome" class="panel hidden">', html)
        self.assertIn("removeAttribute('open')", html)
        self.assertIn("max-height:360px;overflow:auto", html)
        self.assertIn('tabindex="0" role="region"', html)
        self.assertIn("Lore /all fallback", html)

    def test_stream_cards_expose_selected_health_and_coverage_hierarchy(self) -> None:
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()

        self.assertIn("selected-label", html)
        self.assertIn('aria-current="true"', html)
        self.assertIn("card-health", html)
        self.assertIn("Repository coverage through", html)
        self.assertIn("Fetch up to date", html)

    def test_policy_limited_context_is_not_worded_as_incomplete_acquisition(self) -> None:
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()

        self.assertIn("deeper replies were intentionally outside this acquisition policy", html)
        self.assertIn("stopped before completing the configured context policy", html)


if __name__ == "__main__":
    unittest.main()
