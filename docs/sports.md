# Sports mapping

Garmin labels every activity with a type key (`activityType.typeKey` in the API answer, next to `typeId` and
`parentTypeId`). The pipeline maps each key to one of nine categories, and the metrics work on categories.

| Category | Type keys mapped by default |
|---|---|
| `running` | `running`, `trail_running`, `treadmill_running` |
| `cycling` | `cycling`, `indoor_cycling` |
| `swimming` | `lap_swimming`, `open_water_swimming` |
| `strength` | `strength_training` |
| `hiking_walking` | `hiking`, `walking` |
| `winter_sports` | `resort_skiing` |
| `team_sports` | `soccer` |
| `racket_sports` | `paddelball` (Garmin's spelling of padel) |
| `other` | everything else, including `yoga` and `pilates` |

Where the keys come from: they are the 15 distinct type keys in three years of the author's own Garmin
activities (394 runs, 40 strength sessions, 21 hikes, and a handful of the rest). Only keys seen there are in the
default table. Garmin has many more types; the pipeline does not guess their keys.

## Unknown types and overrides

A type that is not in the table counts as `other` and the run prints one warning per type:

```
Unknown activity type 'kite_surfing' counted as 'other'. Add it under [sports] in config.toml.
```

Add it, or move a known type, in `config.toml`:

```toml
[sports]
kite_surfing = "other"
yoga = "strength"
mountain_biking = "cycling"
```

Your entries win over the defaults. A value that is not one of the nine categories stops the run with a message
listing the valid ones.

## How categories feed the metrics

- **Load** is Garmin's own `activityTrainingLoad` for each activity, summed. It does not depend on the sport, so
  every category is treated the same way. No sport-specific weighting is applied.
- **Run km** counts distance from `running` activities only.
- **Strength sessions** count `strength` activities against `gym_target`.
- **Distance** is shown for `running` and `hiking_walking`; **pace** for `running` only. Cycling and swimming
  distance is not shown yet.
- The example dashboard page draws four series (Running, Strength, Hiking, Other), so in the `weekly` and
  `activities` datasets `hiking_walking` is called Hiking and every other category is Other. `context.md` uses
  the full category names.
