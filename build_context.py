"""Turn data/*.json into context.md (training summary for Claude) and dash/*.json (the Training Dashboard's datasets).

All numbers and flags are computed here so no reader has to eyeball raw data.
"""
import json
from datetime import datetime, timedelta

from config import GYM_TARGET, ROOT, SPORT_NAMES, TZ
from garmin_summary import summarize

SPORTS = (*dict.fromkeys(SPORT_NAMES.values()), "Other")
DATASETS = ("summary", "weekly", "daily", "activities")


def sport(t):
    return SPORT_NAMES.get(t, "Other")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def r1(x):
    return None if x is None else round(x, 1)


def fmt(x, d=0, unit=""):
    return "–" if x is None else f"{x:.{d}f}{unit}"


def pace(p):
    """Minutes per km as m:ss, e.g. 5.85 -> '5:51'."""
    if not p:
        return None
    m, s = divmod(round(p * 60), 60)
    return f"{m}:{s:02d}"


def window(acts, start, end):
    """Activities with start <= date < end (ISO dates)."""
    return [a for a in acts if start <= a["date"][:10] < end]


def block(acts):
    by = {}
    for a in acts:
        by[sport(a["type"])] = by.get(sport(a["type"]), 0) + 1
    return {
        "load": round(sum(a["load"] for a in acts)),
        "sessions": len(acts),
        "by_sport": by,
        "run_km": round(sum(a["km"] for a in acts if a["type"] == "running"), 1),
        "strength": sum(1 for a in acts if a["type"] == "strength_training"),
    }


def streak(days, pred):
    """Consecutive most-recent days (skipping days with no value) where pred holds."""
    n = 0
    for d in reversed(days):
        v = pred(d)
        if v is None:
            continue
        if not v:
            break
        n += 1
    return n


def compute(s, now):
    """(context.md lines, flags, {dataset id: rows}) from summarize()'s output, as of `now` ({TZ.key})."""
    acts, days = s["activities"], s["days"]
    t = now.date()
    iso = lambda d: d.isoformat()
    monday = t - timedelta(days=t.weekday())

    this_week = block(window(acts, iso(monday), iso(t + timedelta(days=1))))
    last_week = block(window(acts, iso(monday - timedelta(days=7)), iso(monday)))
    prior4 = [block(window(acts, iso(monday - timedelta(days=7 * k)), iso(monday - timedelta(days=7 * (k - 1)))))
              for k in range(1, 5)]
    avg4 = {k: mean([b[k] for b in prior4]) for k in ("load", "sessions", "run_km", "strength")}
    last7 = block(window(acts, iso(t - timedelta(days=6)), iso(t + timedelta(days=1))))

    today_row = next((d for d in days if d["date"] == iso(t)), {})
    rhr28 = mean([d["rhr"] for d in days[-29:-1]])
    latest = lambda key: next((d for d in reversed(days) if d.get(key) is not None), {})
    hrv_day, sleep_day, rhr_day = latest("hrv"), latest("sleepScore"), latest("rhr")
    sleep7 = mean([d["sleepScore"] for d in days[-7:]])

    flags = []
    if avg4["load"] and last7["load"] > 1.3 * avg4["load"]:
        flags.append(f"Load spike: last 7 days {last7['load']} vs 4-wk weekly avg {avg4['load']:.0f} "
                     f"({last7['load'] / avg4['load']:.2f}×)")
    low_hrv = streak(days, lambda d: None if d["hrv"] is None or d["hrvLow"] is None else d["hrv"] < d["hrvLow"])
    if low_hrv >= 3:
        flags.append(f"HRV below baseline {low_hrv} nights running")
    if rhr_day.get("rhr") and rhr28 and rhr_day["rhr"] >= rhr28 + 5:
        flags.append(f"Resting HR {rhr_day['rhr']} bpm, {rhr_day['rhr'] - rhr28:.0f} above 28-day avg")
    bad_sleep = streak(days, lambda d: None if d["sleepScore"] is None else d["sleepScore"] < 60)
    if bad_sleep >= 2:
        flags.append(f"Sleep score under 60 for {bad_sleep} nights running")

    today_acts = [a for a in acts if a["date"][:10] == iso(t)]
    last_act = acts[-1] if acts else None

    def wk(b):
        sports = ", ".join(f"{n} {k}" for k, n in sorted(b["by_sport"].items())) or "none"
        return f"load {b['load']} · {b['sessions']} sessions ({sports}) · run {b['run_km']} km"

    def dist(a):
        return f"{a['km']:.1f} km" if a["km"] and a["type"] in ("running", "hiking") else "–"

    lines = [
        "# Garmin training context",
        "",
        f"- Updated: {now:%a %d %b %Y %H:%M} ({TZ.key})",
        f"- Latest activity: {last_act['date'][:16] if last_act else '–'} · "
        f"latest sleep: {sleep_day.get('date', '–')} · latest HRV: {hrv_day.get('date', '–')}",
        f"- Today ({t:%a %d %b}): "
        + ("; ".join(f"{sport(a['type'])} {a['min']:.0f} min, load {a['load']:.0f}" for a in today_acts)
           if today_acts else "no activity synced yet"),
        "",
        "## Flags",
        *([f"- {f}" for f in flags] or ["- none"]),
        "",
        "## Weeks (Mon–Sun)",
        f"- This week so far: {wk(this_week)} · strength {this_week['strength']}/{GYM_TARGET} target",
        f"- Last week: {wk(last_week)} · strength {last_week['strength']}/{GYM_TARGET} target",
        f"- 4-week avg (before this week): load {fmt(avg4['load'])} · {fmt(avg4['sessions'], 1)} sessions · "
        f"run {fmt(avg4['run_km'], 1)} km · strength {fmt(avg4['strength'], 1)}",
        f"- Last 7 days: {wk(last7)}",
        "",
        "## Recovery",
        f"- HRV ({hrv_day.get('date', '–')}): {fmt(hrv_day.get('hrv'))} ms, baseline "
        f"{fmt(hrv_day.get('hrvLow'))}–{fmt(hrv_day.get('hrvHigh'))}, status "
        f"{(hrv_day.get('hrvStatus') or '–').lower().replace('_', ' ')}",
        f"- Sleep ({sleep_day.get('date', '–')}): score {fmt(sleep_day.get('sleepScore'))}, "
        f"{fmt(sleep_day.get('sleepH'), 1)} h · 7-night avg score {fmt(sleep7)}",
        f"- Resting HR ({rhr_day.get('date', '–')}): {fmt(rhr_day.get('rhr'))} bpm · 28-day avg {fmt(rhr28, 1)}",
        f"- Body Battery today: high {fmt(today_row.get('bbMax'))}, low so far {fmt(today_row.get('bbMin'))}",
        "",
        "## Last 5 activities",
        "| Date | Sport | Name | Time | Distance | Pace | Avg HR | Load | Effect |",
        "|---|---|---|---|---|---|---|---|---|",
        *[
            f"| {a['date'][:16]} | {sport(a['type'])} | {a['name'] or ''} | {a['min']:.0f} min | {dist(a)} | "
            f"{pace(a['pace']) + '/km' if a['pace'] else '–'} | {fmt(a['avgHR'])} | {a['load']:.0f} | "
            f"{(a['label'] or '').lower().replace('_', ' ')} |"
            for a in reversed(acts[-5:])
        ],
    ]

    # Values are stored the way the dashboard shows them, so its marks match their data exactly
    load4 = round(avg4["load"]) if avg4["load"] is not None else None
    datasets = {
        "summary": [{
            "updated": now.isoformat(timespec="minutes"), "updatedLabel": f"{now:%a %d %b, %H:%M}",
            "load7": last7["load"], "load4wkAvg": load4,
            "loadDeltaPct": round((last7["load"] / load4 - 1) * 100) if load4 else None,
            "runKm7": last7["run_km"], "runs7": last7["by_sport"].get("Running", 0),
            "strengthWeek": this_week["strength"], "gymTarget": GYM_TARGET,
            "hrv": hrv_day.get("hrv"), "hrvLow": hrv_day.get("hrvLow"), "hrvHigh": hrv_day.get("hrvHigh"),
            "hrvStatus": (hrv_day.get("hrvStatus") or "").lower().replace("_", " "),
            "rhr": rhr_day.get("rhr"), "rhr28": r1(rhr28),
            "sleepScore": sleep_day.get("sleepScore"), "sleepH": r1(sleep_day.get("sleepH")),
            "sleep7": round(sleep7) if sleep7 is not None else None,
            "flagCount": len(flags), "flagsText": "; ".join(flags) or "No warning flags",
            "contextMd": "\n".join(lines),
        }],
        "weekly": [
            {"week": w["week"], **{n: sum(v for k, v in w["load"].items() if sport(k) == n) for n in SPORTS},
             "total": sum(w["load"].values()), "runKm": w["runKm"]}
            for w in s["weeks"]
        ],
        "daily": [{"date": d["date"], "hrv": d["hrv"], "hrvLow": d["hrvLow"], "hrvHigh": d["hrvHigh"],
                   "rhr": d["rhr"], "sleepScore": d["sleepScore"], "sleepH": r1(d["sleepH"])}
                  for d in days[-90:]],
        "activities": [
            {"start": a["date"][:16], "activity": a["name"] or sport(a["type"]), "sport": sport(a["type"]),
             "minutes": round(a["min"]),
             "km": r1(a["km"]) if a["km"] and a["type"] in ("running", "hiking") else None,
             "pace": pace(a["pace"]),
             "avgHR": round(a["avgHR"]) if a["avgHR"] else None, "load": round(a["load"]),
             "effect": (a["label"] or "").lower().replace("_", " ")}
            for a in reversed(acts[-30:])
        ],
    }
    return lines, flags, datasets


def main(data_dir=ROOT / "data", out_dir=ROOT):
    now = datetime.now(TZ)
    lines, flags, datasets = compute(summarize(data_dir, now.date()), now)
    (out_dir / "context.md").write_text("\n".join(lines) + "\n")
    (out_dir / "dash").mkdir(exist_ok=True)
    for name in DATASETS:
        (out_dir / "dash" / f"{name}.json").write_text(json.dumps(datasets[name], separators=(",", ":")))
    print(f"context.md: {len(flags)} flags · dash/: {len(datasets['weekly'])} weeks, "
          f"{len(datasets['daily'])} days, {len(datasets['activities'])} activities")


if __name__ == "__main__":
    main()
