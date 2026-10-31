"""Pull your own training data from Garmin's Personal API into data/*.json.

Reads GARMIN_PERSONAL_API_KEY from the environment or .env.local. Uses Garmin's official client (see requirements.txt).
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from config import ROOT, TZ
from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

DATA = ROOT / "data"
DAYS = 90


def load_key():
    """Environment variable first (cloud runs), then .env.local (laptop)."""
    if os.environ.get("GARMIN_PERSONAL_API_KEY"):
        return os.environ["GARMIN_PERSONAL_API_KEY"]
    env_file = ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GARMIN_PERSONAL_API_KEY" and value.strip():
                return value.strip()
    raise SystemExit("GARMIN_PERSONAL_API_KEY not set (env var or .env.local)")


def windows(start, end, size):
    """Split [start, end] into chunks no longer than Garmin's per-call limit."""
    while start <= end:
        stop = min(start + timedelta(days=size - 1), end)
        yield start, stop
        start = stop + timedelta(days=1)


def collect(fn, start, end, size):
    out = []
    for a, b in windows(start, end, size):
        res = fn(a.isoformat(), b.isoformat())
        out.extend(res if isinstance(res, list) else [res])
    return out


def main():
    end = datetime.now(TZ).date()
    start = end - timedelta(days=DAYS - 1)
    DATA.mkdir(exist_ok=True)

    with PersonalApiAuthenticator() as auth:
        token = auth.obtain_token(load_key())

    with GarminPersonalApiClient(token.access_token) as c:
        activities, offset = [], 0
        while True:
            page = c.search_activities(start=offset, limit=50,
                                       start_date=start.isoformat(), end_date=end.isoformat())
            if not page:
                break
            activities.extend(page)
            offset += len(page)

        datasets = {
            "activities": activities,
            # Per-call window limits: dailies/HRV 180d, sleep/body battery 28d
            "dailies": collect(c.get_daily_summaries, start, end, 180),
            "hrv": collect(c.get_daily_hrv_summaries, start, end, 180),
            "sleep": collect(c.get_daily_sleep_summaries, start, end, 28),
            "body_battery": collect(c.get_daily_body_battery, start, end, 28),
        }

    for name, rows in datasets.items():
        (DATA / f"{name}.json").write_text(json.dumps(rows, indent=2, default=str))
        print(f"{name}: {len(rows)} records")


if __name__ == "__main__":
    main()
