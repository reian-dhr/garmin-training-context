"""Shape raw Garmin Personal API responses (data/*.json from fetch.py) into activities, weeks and days.

Only the fields the dashboard needs are kept - no GPS, no profile info.
"""
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import SPORTS, TZ

WEEKS = 13

log = logging.getLogger(__name__)


def category_of(a):
    t = a["activityType"]
    return SPORTS.category(t["typeKey"], t.get("parentTypeId"))


def tz_label(tz):
    """'Europe/Paris' for a named zone, 'UTC+01:00' for a fixed offset."""
    return getattr(tz, "key", None) or tz.tzname(None)


def detect_offset(data_dir):
    """UTC offset in seconds from the newest sleep or activity record, or None if there is none.

    Both carry a local and a GMT time, so their difference is where the watch was at that moment.
    """
    seen = []  # (moment as UTC epoch seconds, offset seconds)
    try:
        for s in load(data_dir, "sleep"):
            gmt, local = s.get("sleepEndTimestampGMT"), s.get("sleepEndTimestampLocal")
            if gmt and local:
                seen.append((gmt / 1000, (local - gmt) / 1000))
        for a in load(data_dir, "activities"):
            gmt = datetime.fromisoformat(a["startTimeGMT"]).replace(tzinfo=timezone.utc)
            local = datetime.fromisoformat(a["startTimeLocal"]).replace(tzinfo=timezone.utc)
            seen.append((gmt.timestamp(), (local - gmt).total_seconds()))
    except (FileNotFoundError, KeyError, ValueError):
        pass
    if not seen:
        return None
    return round(max(seen)[1] / 900) * 900  # whole quarter hours


def resolve_tz(data_dir):
    """The configured zone, or with timezone = "auto" the offset where you were most recently."""
    if TZ is not None:
        return TZ
    offset = detect_offset(data_dir)
    if offset is None:
        log.warning("Could not read a UTC offset from the data, using UTC. Set timezone in config.toml.")
        return timezone.utc
    return timezone(timedelta(seconds=offset))


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
                "category": category_of(a),
                "km": round((a.get("distance") or 0) / 1000, 2),
                "min": round((a.get("duration") or 0) / 60, 1),
                "avgHR": a.get("averageHR"),
                "load": round(a.get("activityTrainingLoad") or 0, 1),
                "label": a.get("trainingEffectLabel"),
                "pace": (a["duration"] / 60) / (a["distance"] / 1000)
                if category_of(a) == "running" and a.get("distance") and a.get("duration") else None,
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
