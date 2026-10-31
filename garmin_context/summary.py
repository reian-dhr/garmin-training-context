"""Shape raw Garmin Personal API responses (data/*.json from fetch.py) into activities, weeks and days.

Only the fields the dashboard needs are kept - no GPS, no profile info.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import SPORTS, TZ

WEEKS = 13


def today():
    return datetime.now(TZ).date()


def week_start(d):
    d = date.fromisoformat(str(d)[:10])
    return d - timedelta(days=d.weekday())


def load(data_dir, name):
    return json.loads((Path(data_dir) / f"{name}.json").read_text())


def summarize(data_dir, on):
    """Activities (oldest first), the last WEEKS Monday-to-Sunday weeks up to `on` (empty weeks included), and days."""
    acts = load(data_dir, "activities")
    dailies = load(data_dir, "dailies")[0]["data"]
    hrv = load(data_dir, "hrv")[0]["hrvSummaries"]
    sleep = load(data_dir, "sleep")

    activities = sorted(
        (
            {
                "date": a["startTimeLocal"],
                "name": a.get("activityName"),
                "type": a["activityType"]["typeKey"],
                "category": SPORTS.category(a["activityType"]["typeKey"]),
                "km": round((a.get("distance") or 0) / 1000, 2),
                "min": round((a.get("duration") or 0) / 60, 1),
                "avgHR": a.get("averageHR"),
                "load": round(a.get("activityTrainingLoad") or 0, 1),
                "label": a.get("trainingEffectLabel"),
                "pace": (a["duration"] / 60) / (a["distance"] / 1000)
                if SPORTS.category(a["activityType"]["typeKey"]) == "running" and a.get("distance") and a.get("duration") else None,
            }
            for a in acts
        ),
        key=lambda a: a["date"],
    )

    weekly = defaultdict(lambda: defaultdict(float))
    for a in activities:
        w = weekly[week_start(a["date"])]
        w[a["category"]] += a["load"]
        if a["category"] == "running":
            w["_runKm"] += a["km"]
    monday = week_start(on)
    weeks = []
    for k in range(WEEKS - 1, -1, -1):
        start = monday - timedelta(days=7 * k)
        v = dict(weekly.get(start, {}))
        weeks.append({"week": start.isoformat(), "runKm": round(v.pop("_runKm", 0), 1),
                      "load": {t: round(x) for t, x in v.items()}})

    days = []
    by_hrv = {h["calendarDate"]: h for h in hrv}
    by_sleep = {s["calendarDate"]: s for s in sleep}
    for d in sorted(dailies, key=lambda d: d["calendarDate"]):
        day = d["calendarDate"]
        h, s = by_hrv.get(day, {}), by_sleep.get(day, {})
        overall = (s.get("sleepScores") or {}).get("overall") or {}
        days.append({
            "date": day,
            "rhr": (d.get("heartRate") or {}).get("restingValue"),
            "bbMax": (d.get("bodyBattery") or {}).get("maxValue"),
            "bbMin": (d.get("bodyBattery") or {}).get("minValue"),
            "hrv": h.get("lastNightAvg"),
            "hrvLow": (h.get("baseline") or {}).get("balancedLow"),
            "hrvHigh": (h.get("baseline") or {}).get("balancedUpper"),
            "hrvStatus": h.get("status"),
            "sleepH": round(s["sleepTimeSeconds"] / 3600, 2) if s.get("sleepTimeSeconds") else None,
            "sleepScore": overall.get("value"),
        })

    return {"activities": activities, "weeks": weeks, "days": days}
