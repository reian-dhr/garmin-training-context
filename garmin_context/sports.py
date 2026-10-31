"""Map Garmin activity types (activityType.typeKey) to the categories the metrics use."""
import logging

log = logging.getLogger(__name__)

LABELS = {
    "running": "Running",
    "cycling": "Cycling",
    "swimming": "Swimming",
    "strength": "Strength",
    "hiking_walking": "Hiking and walking",
    "winter_sports": "Winter sports",
    "team_sports": "Team sports",
    "racket_sports": "Racket sports",
    "other": "Other",
}
CATEGORIES = tuple(LABELS)

# Every key below appeared in the author's own Garmin data (three years of activities).
DEFAULT_TYPES = {
    "running": "running",
    "trail_running": "running",
    "treadmill_running": "running",
    "cycling": "cycling",
    "indoor_cycling": "cycling",
    "lap_swimming": "swimming",
    "open_water_swimming": "swimming",
    "strength_training": "strength",
    "hiking": "hiking_walking",
    "walking": "hiking_walking",
    "resort_skiing": "winter_sports",
    "soccer": "team_sports",
    "paddelball": "racket_sports",
}

# The example dashboard page draws four series: Running, Strength, Hiking and Other.
DASHBOARD_COLUMNS = ("Running", "Strength", "Hiking", "Other")
_DASHBOARD = {"running": "Running", "strength": "Strength", "hiking_walking": "Hiking"}


def dashboard_column(category):
    return _DASHBOARD.get(category, "Other")


class Sports:
    """Activity type -> category, with the user's overrides on top of DEFAULT_TYPES."""

    def __init__(self, overrides=None):
        for type_key, cat in (overrides or {}).items():
            if cat not in CATEGORIES:
                raise SystemExit(f"config.toml: [sports] {type_key} = {cat!r} is not a category. "
                                 f"Use one of: {', '.join(CATEGORIES)}")
        self.mapping = {**DEFAULT_TYPES, **(overrides or {})}
        self._warned = set()

    def category(self, type_key):
        cat = self.mapping.get(type_key)
        if cat is None:
            if type_key not in self._warned:
                self._warned.add(type_key)
                log.warning("Unknown activity type %r counted as 'other'. Add it under [sports] in config.toml.",
                            type_key)
            return "other"
        return cat
