"""Tests for the Garmin training-context pipeline, on synthetic data shaped like the Personal API's answers.

Run: .venv/bin/python -m unittest discover -s tests -v
"""
import json
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from garmin_context import fetch, metrics  # noqa: E402
from garmin_context.metrics import DATASETS, compute, pace, streak  # noqa: E402
from garmin_context.summary import summarize, week_start  # noqa: E402

TODAY = date(2026, 10, 29)  # a Thursday
NOW = datetime(2026, 10, 29, 8, 30, tzinfo=timezone.utc)


def activity(day, kind="running", km=5.0, minutes=30, load=40, hr=140, label="AEROBIC_BASE", name=None):
    return {
        "activityName": name or kind.title(), "startTimeLocal": f"{day} 07:30:00",
        "activityType": {"typeKey": kind}, "distance": km * 1000 if km else 0.0, "duration": minutes * 60.0,
        "averageHR": hr, "activityTrainingLoad": load, "trainingEffectLabel": label,
        "startLatitude": 48.85, "startLongitude": 2.29, "ownerFullName": "Someone",  # must never reach outputs
    }


def write_fixture(folder, acts, days=90, hrv=lambda i: 70, rhr=lambda i: 50, sleep=lambda i: 80):
    start = TODAY - timedelta(days=days - 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    (folder / "activities.json").write_text(json.dumps(acts))
    (folder / "dailies.json").write_text(json.dumps([{"data": [
        {"calendarDate": d, "heartRate": {"restingValue": rhr(i)}, "bodyBattery": {"maxValue": 80, "minValue": 20}}
        for i, d in enumerate(dates)]}]))
    (folder / "hrv.json").write_text(json.dumps([{"hrvSummaries": [
        {"calendarDate": d, "lastNightAvg": hrv(i), "baseline": {"balancedLow": 60, "balancedUpper": 90}, "status": "BALANCED"}
        for i, d in enumerate(dates)]}]))
    (folder / "sleep.json").write_text(json.dumps([
        {"calendarDate": d, "sleepTimeSeconds": 7.5 * 3600, "sleepScores": {"overall": {"value": sleep(i)}}}
        for i, d in enumerate(dates)]))


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_compute(self, acts, **kw):
        write_fixture(self.dir, acts, **kw)
        return compute(summarize(self.dir, TODAY), NOW)

    def steady_weeks(self, load=40):
        """Two runs a week for 8 weeks before this one, plus a strength session this week."""
        acts = []
        for w in range(1, 9):
            mon = week_start(TODAY) - timedelta(days=7 * w)
            acts += [activity(mon + timedelta(days=1), load=load), activity(mon + timedelta(days=3), load=load)]
        acts.append(activity(TODAY - timedelta(days=1), "strength_training", km=0, minutes=50, load=60, label="ANAEROBIC_CAPACITY"))
        return acts

    # --- shaping -------------------------------------------------------------------------------

    def test_weekly_has_13_weeks_including_empty_ones(self):
        acts = [activity(TODAY - timedelta(days=60)), activity(TODAY)]  # nothing in between
        _, _, ds = self.run_compute(acts)
        weeks = ds["weekly"]
        self.assertEqual(len(weeks), 13)
        self.assertEqual(weeks[-1]["week"], week_start(TODAY).isoformat())
        mondays = [date.fromisoformat(w["week"]) for w in weeks]
        self.assertTrue(all(b - a == timedelta(days=7) for a, b in zip(mondays, mondays[1:])))
        self.assertEqual(sum(1 for w in weeks if w["total"] == 0), 11)

    def test_weekly_totals_add_up_by_sport(self):
        acts = [activity(TODAY, load=40), activity(TODAY, "strength_training", km=0, load=30),
                activity(TODAY, "paddelball", km=0.2, load=20), activity(TODAY, "hiking", km=8, load=10)]
        _, _, ds = self.run_compute(acts)
        w = ds["weekly"][-1]
        self.assertEqual((w["Running"], w["Strength"], w["Other"], w["Hiking"]), (40, 30, 20, 10))
        self.assertEqual(w["total"], 100)
        self.assertEqual(w["runKm"], 5.0)

    def test_activities_newest_first_capped_and_without_personal_fields(self):
        acts = [activity(TODAY - timedelta(days=i)) for i in range(40)]
        _, _, ds = self.run_compute(acts)
        rows = ds["activities"]
        self.assertEqual(len(rows), 30)
        self.assertEqual(rows[0]["start"][:10], TODAY.isoformat())
        self.assertEqual([r["start"] for r in rows], sorted((r["start"] for r in rows), reverse=True))
        blob = json.dumps(ds)
        for leaked in ("48.85", "Latitude", "Someone"):
            self.assertNotIn(leaked, blob)

    def test_distance_only_for_runs_and_hikes(self):
        acts = [activity(TODAY, "paddelball", km=0.2, load=20), activity(TODAY, "hiking", km=8.04, load=10)]
        _, _, ds = self.run_compute(acts)
        by_sport = {r["sport"]: r for r in ds["activities"]}
        self.assertIsNone(by_sport["Other"]["km"])
        self.assertIsNone(by_sport["Other"]["pace"])
        self.assertEqual(by_sport["Hiking"]["km"], 8.0)

    # --- formatting ----------------------------------------------------------------------------

    def test_pace_never_shows_60_seconds(self):
        self.assertEqual(pace(5.85), "5:51")
        self.assertEqual(pace(5.999), "6:00")
        self.assertIsNone(pace(None))

    def test_streak_skips_missing_days(self):
        days = [{"v": 1}, {"v": None}, {"v": 0}, {"v": None}, {"v": 0}]
        self.assertEqual(streak(days, lambda d: None if d["v"] is None else d["v"] == 0), 2)

    # --- flags and headline figures ------------------------------------------------------------

    def test_quiet_week_has_no_flags(self):
        _, flags, ds = self.run_compute(self.steady_weeks())
        self.assertEqual(flags, [])
        self.assertEqual(ds["summary"][0]["flagsText"], "No warning flags")
        self.assertEqual(ds["summary"][0]["strengthWeek"], 1)

    def test_load_spike_flag(self):
        acts = self.steady_weeks() + [activity(TODAY - timedelta(days=d), load=150) for d in range(3)]
        _, flags, ds = self.run_compute(acts)
        self.assertTrue(any(f.startswith("Load spike") for f in flags), flags)
        s = ds["summary"][0]
        self.assertEqual(s["loadDeltaPct"], round((s["load7"] / s["load4wkAvg"] - 1) * 100))

    def test_recovery_flags(self):
        _, flags, _ = self.run_compute(
            self.steady_weeks(),
            hrv=lambda i: 50 if i >= 87 else 70,      # last 3 nights below the 60 ms baseline
            rhr=lambda i: 58 if i == 89 else 50,      # today 8 bpm above the 28-day average
            sleep=lambda i: 55 if i >= 88 else 80)    # last 2 nights under 60
        self.assertIn("HRV below baseline 3 nights running", flags)
        self.assertTrue(any(f.startswith("Resting HR 58 bpm") for f in flags), flags)
        self.assertIn("Sleep score under 60 for 2 nights running", flags)

    def test_context_mentions_today_and_flags(self):
        lines, _, ds = self.run_compute(self.steady_weeks())
        text = "\n".join(lines)
        self.assertIn("- Updated: Thu 29 Oct 2026 08:30 (UTC)", text)
        self.assertIn("no activity synced yet", text)
        self.assertEqual(ds["summary"][0]["contextMd"], text)

    def test_empty_account_still_builds(self):
        _, flags, ds = self.run_compute([])
        self.assertEqual(ds["activities"], [])
        self.assertEqual(len(ds["weekly"]), 13)
        self.assertIsNone(ds["summary"][0]["loadDeltaPct"])

    # --- the dashboard page and the files the sync uploads -------------------------------------

    def test_every_field_the_page_shows_exists_in_its_dataset(self):
        _, _, ds = self.run_compute(self.steady_weeks())
        page = (ROOT / "examples" / "dashboard_page.html").read_text()
        marks = re.findall(r'data-source="(\w+)" data-field="(\w+)"', page)
        self.assertGreater(len(marks), 15)
        for source, field in marks:
            self.assertIn(field, ds[source][0], f"{source}.{field} is shown on the page but missing from the data")
        table_fields = re.findall(r'<th[^>]*data-field="(\w+)"', page)
        self.assertEqual(set(table_fields), set(ds["activities"][0]))
        for source in set(re.findall(r'data-source="([\w ]+)"', page)):
            for ident in source.split():
                self.assertIn(ident, DATASETS)

    def test_main_writes_context_and_four_dataset_files(self):
        write_fixture(self.dir, self.steady_weeks())
        metrics.main(data_dir=self.dir, out_dir=self.dir)
        self.assertTrue((self.dir / "context.md").read_text().startswith("# Garmin training context"))
        for name in DATASETS:
            rows = json.loads((self.dir / "dash" / f"{name}.json").read_text())
            self.assertIsInstance(rows, list)
            self.assertTrue(rows, name)


class FetchTest(unittest.TestCase):
    def test_windows_respect_garmin_limits(self):
        start, end = date(2026, 8, 1), date(2026, 10, 29)
        for size in (28, 180):
            chunks = list(fetch.windows(start, end, size))
            self.assertEqual(chunks[0][0], start)
            self.assertEqual(chunks[-1][1], end)
            self.assertTrue(all((b - a).days + 1 <= size for a, b in chunks))
            self.assertTrue(all(n[0] - p[1] == timedelta(days=1) for p, n in zip(chunks, chunks[1:])))


if __name__ == "__main__":
    unittest.main()
