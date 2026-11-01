"""Pull your own training data from Garmin's Personal API into data/*.json.

Reads GARMIN_PERSONAL_API_KEY from the environment or .env.local. Uses Garmin's official client (see pyproject.toml).
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator
from garmin_personal_api.errors import GarminPersonalApiError, HttpError

from .config import ROOT, TZ

log = logging.getLogger(__name__)

DATA = ROOT / "data"
DAYS = 90
KEY_HELP = "see 'Getting a Garmin Personal API key' in the README"
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BASE_DELAY = 2  # seconds, doubled after each failed attempt


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
    raise SystemExit(f"GARMIN_PERSONAL_API_KEY not set (env var or .env.local): {KEY_HELP}")


def call(fn, *args, sleep=time.sleep, **kwargs):
    """Run one API call, retrying network errors and temporary server errors with exponential backoff.

    The client's HttpError carries the status code but not the response headers, so Retry-After is not
    available and the same backoff is used for HTTP 429.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except HttpError as e:
            if e.status_code in (401, 403):
                raise SystemExit(f"Garmin rejected the API key or token (HTTP {e.status_code}). The key may have "
                                 f"expired, been deleted or been copied wrongly: {KEY_HELP}") from None
            if e.status_code not in RETRY_STATUS:
                raise SystemExit(f"Garmin returned HTTP {e.status_code} for {e.method} {e.url}") from None
            problem = f"HTTP {e.status_code}"
        except (requests.ConnectionError, requests.Timeout) as e:
            problem = type(e).__name__
        if attempt == MAX_ATTEMPTS:
            raise SystemExit(f"Garmin API still failing after {MAX_ATTEMPTS} attempts ({problem}). Try again later.")
        delay = BASE_DELAY * 2 ** (attempt - 1)
        log.warning("%s, retrying in %ss (attempt %s of %s)", problem, delay, attempt, MAX_ATTEMPTS)
        sleep(delay)


def windows(start, end, size):
    """Split [start, end] into chunks no longer than Garmin's per-call limit."""
    while start <= end:
        stop = min(start + timedelta(days=size - 1), end)
        yield start, stop
        start = stop + timedelta(days=1)


def collect(fn, start, end, size):
    out = []
    for a, b in windows(start, end, size):
        res = call(fn, a.isoformat(), b.isoformat())
        out.extend(res if isinstance(res, list) else [res])
    return out


def main():
    # With timezone = "auto" the local date is not known yet, so ask up to tomorrow in UTC (Garmin accepts it).
    end = datetime.now(TZ).date() if TZ else datetime.now(timezone.utc).date() + timedelta(days=1)
    start = end - timedelta(days=DAYS - 1)
    DATA.mkdir(exist_ok=True)

    try:
        with PersonalApiAuthenticator() as auth:
            token = call(auth.obtain_token, load_key())
    except GarminPersonalApiError as e:
        raise SystemExit(f"Could not get an access token: {e}. {KEY_HELP}") from None

    with GarminPersonalApiClient(token.access_token) as c:
        activities, offset = [], 0
        while True:
            page = call(c.search_activities, start=offset, limit=50,
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
    if not activities:
        print(f"Warning: no activities in the last {DAYS} days. Check that your watch has synced to Garmin Connect.")
