# Input payload defaults

> 读者：AI 客户端。何时读：构造技法调用载荷时。策略总纲：[`../SKILL.md`](../SKILL.md)。

## Event-based Chinese methods (奇门/六壬/金口/太乙/六爻…)

```json
{
  "date": "2028-04-06",
  "time": "09:33:00",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "gpsLat": 31.2167,
  "gpsLon": 121.4667,
  "ad": 1,
  "after23NewDay": false
}
```

## Birth-based methods (本命盘/八字/紫微/神数…)

Include as much as possible:

```json
{
  "date": "1995-06-03",
  "time": "05:30:00",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "gpsLat": 31.2167,
  "gpsLon": 121.4667,
  "ad": 1,
  "name": "User",
  "pos": "Shanghai"
}
```

## Field notes

- **Coordinates**: compact form `31n13` / `121e28` parses as 度+分 (121°28′), NOT scientific notation;
  `gpsLat` / `gpsLon` are decimal degrees. Provide both when you have them.
- **Timezone**: `zone` / `timezone` accept `+08:00`; `Z` / `UTC` / `GMT` normalize to `+00:00`; IANA
  zone names convert using the chart date (DST-correct).
- **Gender**: include `gender` for gender-sensitive tools (Ziwei, Bazi direct/luck flow, LiuReng
  runyear, 演禽/策天/七政四余·张果, gendered reports).
- **Bazi/Ziwei timing options**: include `timeAlg`, `after23NewDay`, `lateZiHourUseNextDay`, and
  direct/luck-flow options when the user asks about timing. `timeAlg` default is `1` (clock time);
  `timeAlg: 0` means 真太阳时 (the only value that triggers the longitude + equation-of-time
  correction).
- **Hour-23 inputs**: the two independent day-boundary switches change the pillars — canonical spec
  and how to ask: [`late-zi.md`](./late-zi.md).
- **神数 (14 tools)**: inputs use `date` (YYYY-MM-DD) + `time` (HH:mm:ss) strings like every other
  technique (the skill splits them into engine y/m/d/h/m internally), plus 晚子时 switches and an
  `options` passthrough for engine-specific overrides (e.g. wuzhao mode/number).
  `cetian` / `qizhengkin` / `xianqin` also take `gender` + place.
- **Predictive tools**: natal data alone is NOT enough — target `datetime`, `dirZone`, `dirLat`,
  `dirLon`, PD method settings per [`predictive.md`](./predictive.md).
- Unknown extra fields are accepted (`extra="allow"`) and forwarded where meaningful; tools that don't
  read a flag ignore it harmlessly.
