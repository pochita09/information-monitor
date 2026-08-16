import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import schedule


class ScheduleTests(unittest.TestCase):
    def test_runs_once_in_the_grace_window(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(schedule, "STATE_FILE", Path(directory) / "schedule.json"):
            now = datetime(2026, 8, 16, 7, 17, tzinfo=timezone(timedelta(hours=9)))
            slot = schedule.due_slot(["07:13"], now)
            self.assertIsNotNone(slot)
            schedule.complete_slot(slot)
            self.assertIsNone(schedule.due_slot(["07:13"], now))

    def test_skips_outside_grace_window(self):
        now = datetime(2026, 8, 16, 7, 30, tzinfo=timezone(timedelta(hours=9)))
        self.assertIsNone(schedule.due_slot(["07:13"], now))
