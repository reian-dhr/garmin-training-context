"""Tests for the activity-type mapping, the retry logic and the synthetic demo."""
import json
import sys
import tempfile
import unittest
from datetime import timedelta, timezone
from pathlib import Path

import requests
from garmin_personal_api.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from garmin_context import fetch, metrics, summary  # noqa: E402
from garmin_context.sports import CATEGORIES, Sports, load_profiles  # noqa: E402


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

    def test_profile_database_is_consistent(self):
        rows = load_profiles()
        self.assertGreater(len(rows), 100)
        self.assertTrue(all(r["category"] in CATEGORIES for r in rows))
        keys = [r["type_key"] for r in rows if r["type_key"]]
        self.assertEqual(len(keys), len(set(keys)), "a type_key is listed twice")
        names = [r["profile"] for r in rows if r["profile"]]
        self.assertEqual(len(names), len(set(names)), "a profile is listed twice")
        self.assertTrue(all(r["key_source"] for r in rows if r["type_key"]), "every type_key needs a key_source")
        self.assertTrue(all(r["profile"] or r["type_key"] for r in rows), "a row needs a profile or a type_key")

    def test_known_key_beats_name_match_and_name_match_works(self):
        s = Sports()
        self.assertEqual(s.match("trail_running"), ("running", "key"))
        self.assertEqual(s.match("badminton"), ("racket_sports", "key"))
        self.assertEqual(s.match("yoga"), ("mind_body", "key"))
        self.assertEqual(s.match("kite_surfing"), ("other", None))
        # a profile without a known key still matches when its snake_case name is the key
        self.assertEqual(s.match("tempo_training"), ("other", "name"))

    def test_parent_group_is_the_fallback_for_unseen_types(self):
        s = Sports()
        self.assertEqual(s.match("brand_new_ski_type", 165), ("winter_sports", "parent"))
        self.assertEqual(s.match("brand_new_type", 12345), ("other", None))
        self.assertEqual(s.match("trail_running", 165)[1], "key")

    def test_override_beats_database(self):
        self.assertEqual(Sports({"badminton": "cardio_gym"}).match("badminton"), ("cardio_gym", "override"))


class TimezoneTest(unittest.TestCase):
    def write(self, folder, sleep=(), acts=()):
        (folder / "sleep.json").write_text(json.dumps(list(sleep)))
        (folder / "activities.json").write_text(json.dumps(list(acts)))

    def test_offset_follows_the_newest_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # Paris (+1h) sleep on 28 Oct, then a London (+0h) activity on 30 Oct
            self.write(d, sleep=[{"sleepEndTimestampGMT": 1793170000000, "sleepEndTimestampLocal": 1793173600000}],
                       acts=[{"startTimeGMT": "2026-10-30 08:00:00", "startTimeLocal": "2026-10-30 08:00:00"}])
            self.assertEqual(summary.detect_offset(d), 0)

    def test_sleep_wins_when_it_is_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.write(d, sleep=[{"sleepEndTimestampGMT": 1793400000000, "sleepEndTimestampLocal": 1793403600000}],
                       acts=[{"startTimeGMT": "2026-10-28 08:00:00", "startTimeLocal": "2026-10-28 08:00:00"}])
            self.assertEqual(summary.detect_offset(d), 3600)

    def test_no_records_gives_none_and_utc(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp))
            self.assertIsNone(summary.detect_offset(Path(tmp)))
            with self.assertLogs("garmin_context.summary", "WARNING"):
                self.assertEqual(summary.resolve_tz(Path(tmp)), timezone.utc)

    def test_label(self):
        self.assertEqual(summary.tz_label(timezone(timedelta(hours=1))), "UTC+01:00")
        self.assertEqual(summary.tz_label(timezone.utc), "UTC")


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
