"""Map Garmin activity types (activityType.typeKey) to the categories the metrics use.

The mapping comes from data/activity_profiles.csv, one row per activity profile in Garmin's list of profile options.
Lookup order for a type key: your [sports] overrides in config.toml, then rows with a verified type_key, then rows
whose profile name, written in snake_case, equals the key. Anything else is 'other', with one warning per run.
"""
import csv
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

PROFILES_CSV = Path(__file__).parent / "data" / "activity_profiles.csv"

LABELS = {
    "running": "Running",
    "cycling": "Cycling",
    "swimming": "Swimming",
    "strength": "Strength",
    "cardio_gym": "Cardio and gym",
    "mind_body": "Yoga, pilates and mobility",
    "hiking_walking": "Hiking and walking",
    "climbing": "Climbing",
    "winter_sports": "Winter sports",
    "water_sports": "Water sports",
    "diving": "Diving",
    "team_sports": "Team sports",
    "racket_sports": "Racket sports",
    "golf": "Golf",
    "motorsports": "Motorsports",
    "other": "Other",
}
CATEGORIES = tuple(LABELS)

# The example dashboard page draws four series: Running, Strength, Hiking and Other.
DASHBOARD_COLUMNS = ("Running", "Strength", "Hiking", "Other")
_DASHBOARD = {"running": "Running", "strength": "Strength", "hiking_walking": "Hiking"}


def dashboard_column(category):
    return _DASHBOARD.get(category, "Other")


def snake(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_profiles(path=PROFILES_CSV):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["category"] not in CATEGORIES:
            raise ValueError(f"{path.name}: {r['profile']!r} has unknown category {r['category']!r}")
    return rows


def _tables(rows):
    """(verified type_key -> category, snake_case profile name -> category) from the profile rows."""
    verified = {r["type_key"]: r["category"] for r in rows if r["type_key"]}
    by_name = {snake(r["profile"]): r["category"] for r in rows if not r["type_key"]}
    return verified, by_name


class Sports:
    """Activity type -> category: your overrides, then the profile database."""

    def __init__(self, overrides=None, rows=None):
        for type_key, cat in (overrides or {}).items():
            if cat not in CATEGORIES:
                raise SystemExit(f"config.toml: [sports] {type_key} = {cat!r} is not a category. "
                                 f"Use one of: {', '.join(CATEGORIES)}")
        self.overrides = dict(overrides or {})
        self.verified, self.by_name = _tables(load_profiles() if rows is None else rows)
        self._warned = set()

    def match(self, type_key):
        """(category, how) where how is 'override', 'verified', 'name' or None when the type is unknown."""
        for how, table in (("override", self.overrides), ("verified", self.verified), ("name", self.by_name)):
            if type_key in table:
                return table[type_key], how
        return "other", None

    def category(self, type_key):
        cat, how = self.match(type_key)
        if how is None and type_key not in self._warned:
            self._warned.add(type_key)
            log.warning("Unknown activity type %r counted as 'other'. Add it under [sports] in config.toml.",
                        type_key)
        return cat
