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
  direct/luck-flow options when the user asks about timing. For 八字 / 紫微 / 奇门 / 太乙 / 农历 the `timeAlg`
  default is `0` = 真太阳时 (longitude + equation-of-time correction, 星阙 default); `1` = 直接时间 (clock face).
  Per-tool defaults are listed in `horosa_agent_guidance(tool_name=…)` → `safe_defaults`.
- **Mainland-China birthplaces west of Beijing time**: `Asia/Urumqi` dates on/after 1949-10-01 are converted to
  Beijing time like 星阙 does (`cnUnifiedZone=false` opts out); the conversion is disclosed in warnings and on the
  technique card.
- **Hour-23 inputs**: the two independent day-boundary switches change the pillars — canonical spec
  and how to ask: [`late-zi.md`](./late-zi.md). The Western chart family (`chart`/`chart13`/`chart12`/`hellen_chart`/
  `harmonic`/`draconic`/`relocation`) accepts them too (hidden knobs; headless default 1/1) and prints the 排盘规则 line.
- **Western chart family (v0.40.0)**: the export text now mirrors 星阙's `buildAstroSnapshotContent` byte-for-byte — GFM tables
  for 宫位宫头 / 星与虚点 / 相位 / 行星 / 希腊点 / 12分度, the [起盘信息] 古典口径 / 命主星 / 日主星·时主星 lines, and
  `strongRecption` defaults to `0` like 星阙 (explicit values win). `relative` and `jieqi_year` [X宿盘] follow the upstream builders.
- **神数 (14 tools)**: inputs use `date` (YYYY-MM-DD) + `time` (HH:mm:ss) strings like every other
  technique (the skill splits them into engine y/m/d/h/m internally), plus 晚子时 switches and a **typed**
  `options` object: each tool accepts exactly the keys listed in
  `horosa_agent_guidance(tool_name=…)` → `options_keys` (types / allowed values mirror the 星阙 engine);
  unknown keys are not forwarded and are echoed back in `data.params_ignored`. The gate asks for gender on
  北极 / 南极 / 蠢子数 and for the time zone on 铁板 / 邵子 / 蠢子数 / 太玄. `cetian` / `qizhengkin` / `xianqin` also take
  `gender` + place.
- **Long option vocabularies** (西占宫制 0–24, 卜卦 20 类 / 7 流派, 择日 37 用事, 七政宿度制 0–8, 印占大运 15 体系 / 6 流派,
  世运规则集, 紫微 22 传本键, 八字盘法键, 三式起局 / 起课法 …) are **not** in `tools/list` (byte budget); read them from
  `horosa_agent_guidance(tool_name=…)` → `options_keys` and pass the keys at the top level by name.
- **Predictive tools**: natal data alone is NOT enough — target `datetime`, `dirZone`, `dirLat`,
  `dirLon`, PD method settings per [`predictive.md`](./predictive.md).
- Unknown extra fields are accepted (`extra="allow"`) and forwarded where meaningful; tools that don't
  read a flag ignore it harmlessly.
