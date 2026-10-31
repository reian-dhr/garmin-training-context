"""Write synthetic Garmin-shaped data to examples/sample_data/. Not real data: every value comes from a formula.

Run from the repo root: python examples/make_sample_data.py
"""
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "sample_data"
END = date(2026, 10, 29)  # a Thursday
DAYS = 90

# weekday -> (activity type, name, km, minutes, load)
WEEK = {
    0: ("running", "Easy run", 6.0, 36, 45),
    2: ("strength_training", "Strength", 0, 55, 60),
    4: ("cycling", "Ride", 22.0, 60, 50),
    5: ("running", "Long run", 12.0, 75, 95),
    6: ("strength_training", "Strength", 0, 50, 55),
}
EXTRA = {  # day offset from the start -> one-off activity
    9: ("soccer", "Five-a-side", 0, 60, 70), 23: ("lap_swimming", "Pool swim", 1.5, 40, 40),
    37: ("paddelball", "Padel", 0, 75, 65), 51: ("hiking", "Hike", 14.0, 240, 150),
    64: ("walking", "Walk", 5.0, 70, 15), 78: ("trail_running", "Trail run", 10.0, 70, 90),
}
SPIKE = {  # extra sessions in the last week, so the sample shows a warning flag
    END - timedelta(days=5): ("running", "Hard intervals", 8.0, 50, 140),
    END - timedelta(days=2): ("hiking", "Hill hike", 12.0, 200, 170),
}


def activity(day, spec):
    kind, name, km, minutes, load = spec
    return {"activityName": name, "startTimeLocal": f"{day} 07:30:00", "activityType": {"typeKey": kind},
            "distance": km * 1000, "duration": minutes * 60.0, "averageHR": 135 + load // 10,
            "activityTrainingLoad": load, "trainingEffectLabel": "AEROBIC_BASE"}


def main():
    start = END - timedelta(days=DAYS - 1)
    days = [start + timedelta(days=i) for i in range(DAYS)]
    acts = []
    for i, d in enumerate(days):
        if d.weekday() in WEEK and d not in SPIKE:
            acts.append(activity(d, WEEK[d.weekday()]))
        if i in EXTRA:
            acts.append(activity(d, EXTRA[i]))
        if d in SPIKE:
            acts.append(activity(d, SPIKE[d]))
    low = {END - timedelta(days=n) for n in range(3)}  # HRV under the baseline for the last 3 nights
    OUT.mkdir(exist_ok=True)
    files = {
        "activities": acts,
        "dailies": [{"data": [{"calendarDate": d.isoformat(),
                               "heartRate": {"restingValue": 56 if d in low else 51 + d.day % 3},
                               "bodyBattery": {"maxValue": 82, "minValue": 24}} for d in days]}],
        "hrv": [{"hrvSummaries": [{"calendarDate": d.isoformat(), "lastNightAvg": 52 if d in low else 68 + d.day % 5,
                                   "baseline": {"balancedLow": 60, "balancedUpper": 85}, "status": "BALANCED"}
                                  for d in days]}],
        "sleep": [{"calendarDate": d.isoformat(), "sleepTimeSeconds": 7.4 * 3600,
                   "sleepScores": {"overall": {"value": 74 + d.day % 9}}} for d in days],
        "body_battery": [],
    }
    for name, rows in files.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
