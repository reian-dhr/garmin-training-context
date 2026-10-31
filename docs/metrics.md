# Metrics and flags

All numbers are computed in `garmin_context/metrics.py` so nothing has to be read off raw data by eye.
Weeks run Monday to Sunday in the configured time zone.

## Windows

- **This week so far**: Monday up to and including today.
- **Last week**: the previous Monday to Sunday.
- **4-week average**: the mean of the four full weeks before this week (load, sessions, run km, strength).
- **Last 7 days**: today and the six days before it.

## Load

Per activity, Garmin's `activityTrainingLoad` (0 if missing). A week's load is the sum over its activities.

## Recovery figures

Taken from the most recent day that has a value:

- HRV: last night's average, Garmin's balanced range (low and upper) and status.
- Sleep: score, hours, and the average score over the last 7 days.
- Resting heart rate: latest value and the mean of the previous 28 days.
- Body Battery: today's high and low so far.

## Warning flags

| Flag | Raised when |
|---|---|
| Load spike | last-7-day load is more than 1.3 times the 4-week average weekly load |
| HRV below baseline | last night's HRV is under the low end of Garmin's balanced range, for 3 or more nights in a row |
| Resting heart rate | the latest value is 5 or more bpm above the mean of the previous 28 days |
| Poor sleep | sleep score under 60 for 2 or more nights in a row |

Days with no value are skipped when counting nights in a row. The thresholds are rules of thumb chosen by the
author, not medical advice. They are constants in `metrics.py`.

## Output files

- `context.md`: the summary above as text (flags, weeks, recovery, last 5 activities).
- `dash/summary.json`: one row of headline figures plus `contextMd`, the same text as `context.md`.
- `dash/weekly.json`: 13 weeks of load by series and run km.
- `dash/daily.json`: up to 90 days of HRV, resting heart rate and sleep.
- `dash/activities.json`: the latest 30 activities, newest first. GPS and profile fields are never copied.

A synthetic example of each is in `examples/sample_output/`.
