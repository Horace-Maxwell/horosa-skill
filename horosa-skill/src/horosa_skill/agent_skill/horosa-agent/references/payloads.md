# Building payloads by hand

> Reader: an AI client. Read when you build a technique payload yourself. Basics (date / time / place /
> zone / gender / profile) are in [`../SKILL.md`](../SKILL.md) §3; this sheet is the detail.
> The authoritative per-technique contract is `horosa_agent_guidance {"tool_name": "<key>"}` →
> `input_contract.example_payload` (live-tested), `ask_if_missing`, `safe_defaults`, `options_keys`.

## Where fields go

- MCP: fields at the top level of the tool call. A `request` object is merged in too (same key in both with
  different values → the `request` value wins and `warnings` says so). Wrapper objects such as `payload` /
  `arguments` are unpacked.
- Accepted aliases (renamed, noted in `warnings`): `timezone` / `tz` → `zone`, `latitude` → `lat`,
  `longitude` / `lng` → `lon`, `sex` → `gender`, `house_system` → `hsys`.
- An argument no setting reads is **named in `warnings`** with the closest real name ("did you mean …"). It is
  not an error, but it changed nothing: fix the name and rerun if it mattered.
- `tools/list` advertises only the common fields of each tool. Long-tail knobs (`orbSystem`, `termsVariant`,
  `extraBodies`, 紫微传本键, 神数 `options` …) are accepted at the top level by name; their lists are in
  `options_keys`.

## Event payload (cast techniques: 奇门 / 六壬 / 金口诀 / 太乙 / 六爻 / 塔罗 …)

`date` / `time` = the moment of the question, `place` = where the user is, `question` = the user's words.

```call
horosa_cn_liureng_gods {"date": "2026-11-12", "time": "16:40", "place": "上海", "question": "能否成事", "defaults_accepted": true, "clarification_notes": "用户接受星阙默认（星占法贵人）"}
```

## Birth payload (本命盘 / 八字 / 紫微 / 神数 …)

```call
horosa_astro_chart {"date": "1988-03-14", "time": "18:45", "place": "Chicago, IL", "name": "Ann", "hsys": 3, "zodiacal": 0, "agent_confirmed_settings": true, "clarification_notes": "User chose Placidus houses and the tropical zodiac"}
```

Without a place name: `"zone": "+08:00", "lat": "31n13", "lon": "121e28"` (or decimal `31.22` / `121.47`;
`gpsLat` / `gpsLon` are decimal degrees). Never estimate coordinates or historical offsets from memory.

## Field formats and refusals

| Field | Read | Refused (code) |
| --- | --- | --- |
| `date` | `1990-05-03`, `1990/5/3`, `1990.5.3`, `19900503`, `1990年5月3日`; BCE `-0500-03-21` (or the unsigned date + `ad: -1`) | `03/05/1990` (`tool.ambiguous_date`, both readings in `options`), `1990-02-30` (`tool.invalid_date`), 农历 (`tool.lunar_date_unsupported`) |
| `time` | `08:00`, `08:00:00`, `0830`, `8点半`, `上午8点`, `8:30 PM` | `辰时` (`tool.time_is_shichen`), `不详` / `unknown` (`tool.time_unknown`), `25:00` (`tool.invalid_time`) |
| `zone` | `+08:00`, `8`, `-5`, `5.5`, `UTC+8`, `东八区`, `E8` / `W5`, `北京时间`, IANA `Asia/Shanghai` | `480` (minutes? → `tool.invalid_zone`, fix it yourself), `CST` / `EST` / `IST` (several meanings → ask), DST gap / overlap with an IANA name (`tool.zone_ambiguous`) |
| `lat` / `lon` | `31n13` / `121e28` (degrees + minutes), `31.22`, `31°13′N`, `北纬31.22` | `40n75` (minutes ≥ 60), out of range, swapped (`tool.invalid_coordinate`) |
| `gender` | `男` / `女`, `1` / `0`, `乾造` / `坤造`, `male` / `female`, `先生` / `小姐` | anything else (`tool.invalid_gender`); missing where required (`tool.missing_gender` / gate fact) |
| flags | JSON `true` | `"true"`, `1`, `"yes"` (`tool.confirmation_flag_not_boolean`) |

Each refusal lists one entry per field in `details.agent_recovery.fix_fields` (`field`, `got`, `expected`,
`example`, `options`). `must_ask_user: false` = rewrite it yourself; `true` = ask the user.

**Zone and place together.** `place` without `zone` → the zone in force there on that date. An explicit
`zone` offset is used as given, even when it contradicts the place (the summary says 「时区沿用显式给出的 zone」).
`place` + `lat` / `lon` without `zone` → the zone is found from the coordinates and the date.
Mainland-China places west of Beijing time (`Asia/Urumqi`) are put on Beijing time from 1949-10-01, like 星阙
(`cnUnifiedZone: false` opts out); disclosed in `warnings` and on the technique card.

**BCE dates.** Write `-0500-03-21`, or keep `0500-03-21` with `ad: -1` (rewritten to the same thing). `ad`
takes only `1` / `-1`. 老黄历 / 通书 / 河洛 / 参评 / 一掌经 cover AD 1–9999 only (`tool.date_range_unsupported`).

**Lunar birthday.** Find the Gregorian day with `horosa_cn_calendar_month` (`date` = any day of the Gregorian
month to list; each day carries its 农历 date), then confirm the day with the user:

```call
horosa_cn_calendar_month {"date": "1990-05-01", "zone": "+08:00", "lon": "121e28", "defaults_accepted": true}
```

## Settings with vocabularies

Every enumerated setting (宫制 `hsys`, 黄道 `zodiacal`, 古典口径 keys, 流派 / 传本 / 起局方式, 神数 `options`, horary
`category` / `school`, election `topicId`, 择日 condition params …) is checked against its list. Canonical
values, case variants, Chinese names (`Placidus`, `整宫制`, `真交点`, `托勒密`) and true/false where it means
something are read (noted in `warnings`); anything else is refused with `tool.invalid_option` and the full list
in `details.accepted` (some engines say `details.allowed` / `options`). Pick from that list or ask the user —
never drop the setting silently. 西占 `hsys` indices: `1` = Alcabitus (星阙 default), `0` = Whole Sign,
`3` = Placidus; `options_keys.hsys` has all 25. 印度盘 uses its own house table.

## Casting inputs (manual casts)

A cast the user supplies is used as given or refused — never silently replaced by a time cast. `data.cast_method`
says how the result was cast.

- 六爻 `lines`: six objects bottom to top, coin values `6` 老阴 (moving) / `7` 少阳 / `8` 少阴 / `9` 老阳 (moving),
  e.g. `[{"value": 7}, {"value": 8}, {"value": 9}, {"value": 6}, {"value": 7}, {"value": 8}]`; or `0` / `1` with
  `change`. Or `gua_code`: a hexagram name (`火天大有`, `大有`, Traditional too) or a six-digit code. No `lines`
  and no `gua_code` = cast by the moment.
- 小六壬 `nums` [月, 日, 时]; 灵棋 `counts`; 梅花卦义 `gua_meiyi` takes trigram names / symbols; 小成图 `dayan` needs an
  explicit `seed` or `counts`.

```call
horosa_cn_sixyao {"date": "2026-11-12", "time": "16:40", "place": "上海", "question": "项目能成吗", "gua_code": "火天大有", "defaults_accepted": true, "clarification_notes": "用户摇得火天大有，其余按默认"}
```

## Other notes

- **Hour 23**: two day-boundary switches — [`late-zi.md`](./late-zi.md).
- **Predictive targets** (`datetime`, `year`, `dirZone` …) — [`predictive.md`](./predictive.md).
- **八字 / 紫微 periods**: `period` = `{"liunian": [2026], "liuyue": [3], "liuri": [...], "liushi": [0-11]}`
  (紫微 also `daxian`: the 大限 palace indices); adds the 「多运限·指定时段」 / 「运限」 section.
- **八字 `southMonth`** (`none` default / `chong`): only for southern-hemisphere births; the gate asks only then.
- **神数**: `date` / `time` like every technique plus a typed `options` object (keys in `options_keys`; unknown keys
  come back in `data.params_ignored`).
- **Western chart family**: [古典格局] is attached to `chart` and `relocation` only; `relocation` needs
  `relocLat` / `relocLon` (without them it equals the natal chart).
