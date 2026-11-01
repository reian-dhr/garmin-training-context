# Sports mapping

Garmin labels every activity with a type key (`activityType.typeKey` in the API answer, next to `typeId` and
`parentTypeId`). The pipeline maps each key to one of 16 categories, and the metrics work on categories.

Categories: `running`, `cycling`, `swimming`, `strength`, `cardio_gym`, `mind_body` (yoga, pilates, mobility,
meditation), `hiking_walking`, `climbing`, `winter_sports`, `water_sports`, `diving`, `team_sports`,
`racket_sports`, `golf`, `motorsports`, `other`.

## The profile database

[`garmin_context/data/activity_profiles.csv`](../garmin_context/data/activity_profiles.csv) has one row per activity
profile in Garmin's support article [Activity Profile Options on Garmin Wearables](https://support.garmin.com/en-GB/?faq=g9VOolzNBr08b7mfclmxt7)
(133 profiles, read on 1 Nov 2026).

| Column | Meaning |
|---|---|
| `profile` | The profile name as Garmin's article spells it (including its typo "Pickelball"). |
| `garmin_group` | The group(s) the article says the profile is listed under, for example `Team Sports`. Blank when the article gives none. |
| `category` | The category this repo uses. I assigned it from Garmin's group and the profile name. |
| `type_key` | The API `typeKey`, only when it has been seen in real data. Blank otherwise. |
| `key_source` | Where the `type_key` came from. `author-data` means it appeared in the author's own activities. |

The article lists display names, not API type keys, so most rows have no `type_key` yet. Fifteen are filled in
(`running`, `trail_running`, `treadmill_running`, `cycling`, `indoor_cycling`, `lap_swimming`, `open_water_swimming`,
`strength_training`, `hiking`, `walking`, `resort_skiing`, `soccer`, `paddelball`, `yoga`, `pilates`), taken from
three years of the author's activities. Which profile produced which key is paired by name.

## How a type key is matched

1. Your `[sports]` overrides in `config.toml`.
2. A row whose `type_key` equals the key (verified).
3. A row without a `type_key` whose profile name in snake_case equals the key, for example `badminton` or
   `ice_hockey`. This is a name match, not a verified key: Garmin's real key may be spelled differently, in which
   case the type falls through to the next step.
4. `other`, with one warning per run: `Unknown activity type 'x' counted as 'other'`.

## Filling in and updating the database

Run `python -m garmin_context types` after `fetch`. It lists every type key in `data/activities.json` with its count,
its category and how it was matched (`verified`, `name`, `override` or `UNKNOWN`). For a key that is `name` or
`UNKNOWN`:

- Find its row in the CSV (or add one) and put the key in `type_key`, with `key_source` set to where you saw it.
- Fix `category` if the assignment is wrong for you.
- Keep one row per profile and one row per `type_key`; the tests check both.

For a one-off change on your machine only, use `[sports]` in `config.toml` instead:

```toml
[sports]
kite_surfing = "water_sports"
yoga = "strength"
```

## How categories feed the metrics

- **Load** is Garmin's own `activityTrainingLoad` for each activity, summed. It does not depend on the sport, so
  every category is treated the same way. No sport-specific weighting is applied.
- **Run km** counts distance from `running` activities only.
- **Strength sessions** count `strength` activities against `gym_target`.
- **Distance** is shown for `running` and `hiking_walking`; **pace** for `running` only.
- The example dashboard page draws four series (Running, Strength, Hiking, Other), so in the `weekly` and
  `activities` datasets `hiking_walking` is called Hiking and every other category is Other. `context.md` uses
  the full category names.
