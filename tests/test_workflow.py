from pathlib import Path
import unittest



ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_expected_triggers_and_actions(self):
        content = (ROOT / ".github" / "workflows" / "monitor.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn('cron: "*/5 * * * *"', content)
        self.assertIn("MONITOR_SCHEDULED", content)
        self.assertNotIn("push:", content)
        self.assertIn("contents: write", content)
        self.assertIn("actions/upload-pages-artifact@v3", content)
        self.assertIn("actions/deploy-pages@v4", content)
        self.assertIn("secrets.GEMINI_API_KEY", content)
        self.assertIn("cancel-in-progress: false", content)


if __name__ == "__main__":
    unittest.main()
