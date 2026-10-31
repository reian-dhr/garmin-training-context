"""Settings, read from config.toml if it exists, otherwise the defaults below.

Copy config.example.toml to config.toml to change them.
"""
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent

DEFAULTS = {
    "timezone": "UTC",
    "gym_target": 3,
    # Garmin activity type key -> sport name. Anything else is counted as "Other".
    "sports": {"running": "Running", "strength_training": "Strength", "hiking": "Hiking"},
}

_file = ROOT / "config.toml"
_user = tomllib.loads(_file.read_text()) if _file.exists() else {}
SETTINGS = {**DEFAULTS, **_user}

TZ = ZoneInfo(SETTINGS["timezone"])
GYM_TARGET = SETTINGS["gym_target"]
SPORT_NAMES = SETTINGS["sports"]
