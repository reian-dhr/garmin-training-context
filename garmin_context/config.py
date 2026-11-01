"""Settings, read from config.toml in the working directory if it exists, otherwise the defaults below.

The default time zone is "auto": the offset is read from your most recent sleep or activity record, so "today" and the
weeks follow where you are. Set an IANA name such as Europe/Paris to pin it.
"""
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .sports import Sports

ROOT = Path.cwd()

DEFAULTS = {"timezone": "auto", "gym_target": 3, "sports": {}}

_file = ROOT / "config.toml"
SETTINGS = {**DEFAULTS, **(tomllib.loads(_file.read_text()) if _file.exists() else {})}

TZ = None  # None means "auto": see summary.resolve_tz
if SETTINGS["timezone"] != "auto":
    try:
        TZ = ZoneInfo(SETTINGS["timezone"])
    except ZoneInfoNotFoundError:
        raise SystemExit(f"config.toml: timezone {SETTINGS['timezone']!r} is not 'auto' or an IANA time zone "
                         "name (for example Europe/Paris)")
GYM_TARGET = SETTINGS["gym_target"]
SPORTS = Sports(SETTINGS["sports"])
