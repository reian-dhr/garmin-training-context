"""Settings, read from config.toml in the working directory if it exists, otherwise the defaults below."""
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .sports import Sports

ROOT = Path.cwd()

DEFAULTS = {"timezone": "UTC", "gym_target": 3, "sports": {}}

_file = ROOT / "config.toml"
SETTINGS = {**DEFAULTS, **(tomllib.loads(_file.read_text()) if _file.exists() else {})}

try:
    TZ = ZoneInfo(SETTINGS["timezone"])
except ZoneInfoNotFoundError:
    raise SystemExit(f"config.toml: timezone {SETTINGS['timezone']!r} is not an IANA time zone name "
                     "(for example Europe/Paris)")
GYM_TARGET = SETTINGS["gym_target"]
SPORTS = Sports(SETTINGS["sports"])
