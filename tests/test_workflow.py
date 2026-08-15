from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_expected_triggers_and_actions(self):
        content = (ROOT / ".github" / "workflows" / "monitor.yml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        self.assertIn("workflow_dispatch:", content)
        self.assertIn('cron: "13 22 * * *"', content)
        self.assertIn('cron: "17 4 * * *"', content)
        self.assertIn('cron: "23 12 * * *"', content)
        self.assertNotIn("push:", content)
        self.assertEqual(parsed["jobs"]["build"]["permissions"]["contents"], "write")
        self.assertIn("actions/upload-pages-artifact@v3", content)
        self.assertIn("actions/deploy-pages@v4", content)
        self.assertIn("secrets.GEMINI_API_KEY", content)
        self.assertIn("cancel-in-progress: false", content)


if __name__ == "__main__":
    unittest.main()
