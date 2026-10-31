# garmin-pipeline-example

A small, personal pipeline that turns my Garmin data into a training summary an AI assistant can plan with. Built for my own workflow and shared as a reference for how such a pipeline can be put together. It is not a product and not a general Garmin connector; existing Garmin MCP servers already cover that.

## What it does

1. `fetch_garmin.py` pulls 90 days of activities, daily summaries, HRV, sleep and Body Battery from Garmin's official Personal API and saves them to `data/*.json`.
2. `garmin_summary.py` reduces those answers to the fields needed. GPS and profile fields are dropped.
3. `build_context.py` computes weekly load, 4-week averages, recovery figures and four warning flags (load spike, HRV below baseline, high resting heart rate, poor sleep). It writes `context.md` and four JSON datasets in `dash/`.
4. On a schedule, a claude.ai cloud routine runs steps 1 to 3 and uploads the datasets to a Dashboard artifact. A second assistant routine reads the summary dataset when it suggests training. The routine prompt is in `examples/garmin_sync_prompt.template.md` and the dashboard page in `examples/dashboard_page.html`.

```
Garmin Personal API -> data/*.json -> dash/*.json + context.md -> dashboard artifact -> assistant
        (fetch)          (summarize)        (metrics, flags)          (scheduled upload)
```

I built it to stop opening three apps to decide whether to train hard or easy, and to try a scheduled agent workflow end to end.

## Setup

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). You need a Garmin Personal API key. I use one; I have not checked how other people can get one.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env.local        # then paste your key
cp config.example.toml config.toml  # optional: time zone, gym target, sport names
.venv/bin/python fetch_garmin.py
.venv/bin/python build_context.py
```

The key is read from `GARMIN_PERSONAL_API_KEY` (environment, then `.env.local`). It is exchanged for a 24-hour bearer token on each run; no password or MFA is involved.

## Check that it worked

```bash
.venv/bin/python -m unittest discover -s tests -v   # 14 tests, synthetic data, no key or network
cat context.md                                      # flags, weeks, recovery, last 5 activities
```

`fetch_garmin.py` prints a record count per dataset. `build_context.py` prints the flag count and dataset sizes.

## Configuration

`config.toml` (optional) sets the time zone, the weekly strength-session target and the mapping from Garmin activity types to sport names. Defaults: UTC, 3 sessions, running / strength / hiking. See `config.example.toml`.

## Known limits

- One pinned client version (`garmin-connect-personal-api-python==1.0.0`). No retry or rate-limit handling.
- Personal API keys expire after a year, so the scheduled run starts failing until the key is replaced.
- The scheduled part relies on claude.ai routines and Dashboard artifacts, which are research-preview features.
- The sport names are fixed to what the example dashboard page expects (Running, Strength, Hiking, Other).
- The flag thresholds (for example 1.3x the 4-week load) are my own rules of thumb, not medical advice.

## Licence

MIT, see `LICENSE`.
