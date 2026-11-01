# Sports mapping

Garmin labels every activity with a type key (`activityType.typeKey` in the API answer, next to `typeId` and
`parentTypeId`). The pipeline maps each key to one of 16 categories, and the metrics work on categories.

Categories: `running`, `cycling`, `swimming`, `strength`, `cardio_gym`, `mind_body` (yoga, pilates, mobility,
meditation), `hiking_walking`, `climbing`, `winter_sports`, `water_sports`, `diving`, `team_sports`,
`racket_sports`, `golf`, `motorsports`, `other`.

## The profile database

[`garmin_context/data/activity_profiles.csv`](../garmin_context/data/activity_profiles.csv) has 180 rows. It combines
three sources:

- **Garmin's article** [Activity Profile Options on Garmin Wearables](https://support.garmin.com/en-GB/?faq=g9VOolzNBr08b7mfclmxt7)
  (read on 1 Nov 2026): 133 profile names and the groups Garmin lists them under. It gives display names, not API keys.
- **GarminDB's `Sport` enum** ([`garmin_connect_enums.py`](https://github.com/tcgoetz/GarminDB/blob/master/garmindb/garmin_connect_enums.py),
  community code, not official Garmin documentation): API type keys with their numeric ids. 131 keys come from here.
- **The author's own activities** (three years): 15 keys seen in real payloads, with their `typeId`.

| Column | Meaning |
|---|---|
| `profile` | The profile name as Garmin's article spells it (including its typo "Pickelball"). Blank for keys the article has no profile for. |
| `garmin_group` | The group(s) the article lists the profile under. Blank when it gives none. |
| `category` | The category this repo uses. I assigned it from Garmin's group and the name. |
| `type_key` | The API `typeKey`. Blank where no key is known. |
| `type_id` | Garmin's numeric id for the type, when known. |
| `key_source` | `author-data` (seen in the author's activities) or `garmindb-enum` (listed there). |

How much to trust the keys: for 13 of the author's 15 keys, the name and id also match GarminDB's list, which
supports the list. Two differ: the author's `yoga` has id 163, which GarminDB calls `yoga_gym`, and `pilates` (160)
is missing there. The author's data wins for those. A `garmindb-enum` key has not been seen in the author's data,
and pairing a key with an article profile (for example `mountain_biking` with "MTB") is by name.

## How a type key is matched

1. Your `[sports]` overrides in `config.toml`.
2. A row whose `type_key` equals the key (`key`).
3. A profile row without a `type_key` whose name in snake_case equals the key (`name`), for example
   `tempo_training`.
4. The activity's `parentTypeId`, for six parent groups seen in real payloads: 1 running, 2 cycling, 26 swimming,
   165 winter sports, 206 team sports, 219 racket sports (`parent`). This catches new sub-types of those groups.
5. `other`, with one warning per run: `Unknown activity type 'x' counted as 'other'`.

## Filling in and updating the database

Run `python -m garmin_context types` after `fetch`. It lists every type key in `data/activities.json` with its count,
its category and how it was matched (`key`, `name`, `parent`, `override` or `UNKNOWN`). For a key that is `UNKNOWN` (or only matched by `name` or `parent`):

- Find its row in the CSV (or add one) and put the key in `type_key`, its id in `type_id`, and set `key_source` to where you saw it.
- Fix `category` if the assignment is wrong for you.
- Keep one row per profile and one row per `type_key`; a row needs a profile or a type key. The tests check this.

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
