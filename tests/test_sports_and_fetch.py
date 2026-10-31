"""Tests for the activity-type mapping, the retry logic and the synthetic demo."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import requests
from garmin_personal_api.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from garmin_context import fetch, metrics  # noqa: E402
from garmin_context.sports import CATEGORIES, DEFAULT_TYPES, Sports  # noqa: E402


class SportsTest(unittest.TestCase):
    def test_known_type(self):
        self.assertEqual(Sports().category("trail_running"), "running")

    def test_types_from_the_authors_data(self):
        s = Sports()
        self.assertEqual(s.category("soccer"), "team_sports")
        self.assertEqual(s.category("paddelball"), "racket_sports")
        self.assertEqual(s.category("resort_skiing"), "winter_sports")

    def test_unknown_type_is_other_and_logged_once(self):
        s = Sports()
        with self.assertLogs("garmin_context.sports", "WARNING") as logs:
            self.assertEqual(s.category("kite_surfing"), "other")
            self.assertEqual(s.category("kite_surfing"), "other")
        self.assertEqual(len(logs.output), 1)

    def test_override_wins_and_bad_category_is_rejected(self):
        self.assertEqual(Sports({"yoga": "strength"}).category("yoga"), "strength")
        with self.assertRaises(SystemExit):
            Sports({"yoga": "mindfulness"})

    def test_defaults_only_use_real_categories(self):
        self.assertTrue(set(DEFAULT_TYPES.values()) <= set(CATEGORIES))


class RetryTest(unittest.TestCase):
    def http(self, status):
        return HttpError(status_code=status, method="GET", url="https://example.test", response_text="")

    def test_retries_temporary_errors_then_succeeds(self):
        answers, waits = [self.http(503), requests.ConnectionError(), "ok"], []

        def flaky():
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        self.assertEqual(fetch.call(flaky, sleep=waits.append), "ok")
        self.assertEqual(waits, [2, 4])

    def test_gives_up_after_max_attempts(self):
        def always():
            raise self.http(429)
        waits = []
        with self.assertRaises(SystemExit) as e:
            fetch.call(always, sleep=waits.append)
        self.assertIn("4 attempts", str(e.exception))
        self.assertEqual(len(waits), fetch.MAX_ATTEMPTS - 1)

    def test_rejected_key_fails_at_once_with_readme_pointer(self):
        def denied():
            raise self.http(401)
        waits = []
        with self.assertRaises(SystemExit) as e:
            fetch.call(denied, sleep=waits.append)
        self.assertIn("README", str(e.exception))
        self.assertEqual(waits, [])


class DemoTest(unittest.TestCase):
    def test_sample_data_builds_and_shows_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            metrics.main(data_dir=ROOT / "examples" / "sample_data", out_dir=out, now=metrics.DEMO_NOW)
            text = (out / "context.md").read_text()
            self.assertIn("Load spike", text)


if __name__ == "__main__":
    unittest.main()
