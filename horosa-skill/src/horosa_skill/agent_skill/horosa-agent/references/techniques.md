# Technique notes (which tool, which inputs)

> Reader: an AI client. Read when you choose between similar techniques or need a technique's special inputs.
> The key list is in [`../SKILL.md`](../SKILL.md) §13. Per-technique contracts: `horosa_agent_guidance {"tool_name": "<key>"}`.

## Western

| Want | Tool and inputs |
| --- | --- |
| Natal chart | `chart` (13-house `chart13`, 12th-harmonic / Dwadasamsa `chart12`, Hellenistic `hellen_chart`). `chart` and `relocation` carry [古典] + [古典格局]; `india_chart` / `mundane` carry [古典] only. |
| Derived charts | `draconic` (`draconicHouses`: `whole` default / `shift`), `relocation` (needs `relocLat` / `relocLon`), `harmonic` (whole number 1–360). |
| Relationship 合盘 | `relative` with `inner` and `outer` (each: date / time / place or zone+lat+lon); `relative` 0–4 picks the chart type (0 比较盘 default). Both people need a birth time. |
| Midpoints / Uranian | `germany` (`rectifyEvents` → [校时预览]; `mpCoord` ra / decl → [中点坐标]). |
| Babylonian | `babylon` (no houses / aspects / Asc by design). |
| Mundane | `mundane` (year + 入宫节气 + place; `mundaneType`, `mundaneRuleset`). |
| Astrocartography | `acg` (`clickLat` / `clickLon` adds the spot analysis). |
| Planet cycles | `planet_cycles` (no natal chart; the planet pair and year range are asked). |
| Birth-time rectification | `india_rectify` (needs dated life events; returns ranked evidence — the user decides). |
| Horary 卜卦 | `horary`: `category` (question type) and `school` are asked; an unknown `category` is refused with `tool.invalid_option` (no fallback to a general question). The chart is cast with the school's house system / terms / triplicity. |
| Judge one candidate moment | `election` (`topicId` — unknown values refused with `tool.invalid_option`; pass `natal` to add [本命合参]). 七政 version: `qizhengelection` (action pan / eclipses / azimuthsearch). |
| Celebrity data | `astrodata` (read-only, no gate). |

Predictive techniques: [`predictive.md`](./predictive.md). `sunriseMode` (`center` default / `apparent`) applies to
the Western charts and 七政.

## 择日 window search

`tianxing` (Western; `explainAt` judges one moment leaf by leaf), `qimenzeri`, `huanglizeri` (day grain), `bazizeri`,
`taiyizeri`, `ziweizeri` (needs gender), `liurengzeri`, `sanshizeri` (conditions may span the three 式), `qizhengzeri`,
`indiazeri` (Muhurta). All take `startDate` / `endDate` (`maxSpanDays` caps the window, 366 by default; split longer windows) + a `conditions` tree
+ a base `date` / `time` / place. Condition types and their meaning: `horosa_agent_guidance {"tool_name": …}` →
`condition_types` (generated from the engine's own table). Polarity and `condition_echo`: SKILL.md §8. Hit intervals
carry `pick` (a boundary-safe moment): cast a chart for a hit with `pick`, not `start`. Zero hits still return the
sections and say no period matched — that is not a missing section.

## Chinese

| Want | Tool and inputs |
| --- | --- |
| 八字 | `bazi_birth` (chart), `bazi_direct` (大运流年). Both need gender. `tianyiSchool` `xieji` default / `ziping`; `southMonth` for southern births. `bazi_inverse {"pillars": ["甲子", "丙寅", "戊辰", "庚申"], "fromYear": …, "count": 1–10}` returns candidate birth times (they repeat every 60 years: the user picks). |
| 紫微斗数 | `ziwei_birth` (22 传本 keys + `sihuaSchool`; `period`), `ziwei_rules` (rules library). |
| 七政四余 | `guolao_chart` (`guolaoLifeMode`, `guolaoBodyMode`, `planetaryHourMethod`, `moiraTransitDate`; 宿度制 `doubingSu28`). [相位] here is 七政 aspects (會 / 衝 / 刑 / 合 / 半合), not Western ones. [虚实] / [本命化曜] / [流年流曜] come from the Java rules layer and are absent (with a warning) when it is down. |
| 河洛 / 邵子参评数 / 一掌经 | `heluo`, `canping`, `yizhangjing` (all need gender; AD 1–9999). |
| 宿占 | `suzhan` (Western classical keys have no effect, as in 星阙). |
| Calendar | `huangli` (one day), `tongshu` (needs `school`; the five schools can disagree on the same day; keys such as `sanyuanliexiu`, `sanyuan`), `calendar_month`, `nongli_time`, `jieqi_year`, `jieqi_birth`. |
| 卦义 | `gua_desc` (hexagram text by name), `gua_meiyi` (梅花 reading by trigrams). |
| Casting | `qimen`, `liureng_gods`, `taiyi`, `jinkou` (`options.timeBasis` `direct` default / `trueSolar`), `sanshiunited`, `sixyao`, `xiaoliuren`, `feigong`, `xiaochengtu`, `guice`, `lingqi`, `tongshefa`, `geomancy`, `tarot` — see [`chinese-methods.md`](./chinese-methods.md). |
| 神数 | `zhengchuan` + the 14 神数 tools — see [`chinese-methods.md`](./chinese-methods.md). |

**Frozen casts.** For 小六壬 / 飞宫 / 小成图 / 皇极轨策 / 灵棋 / 神数正传, the cast (课 / 局 / 卦) is fixed once made:
changing the school or reading switches only re-reads it. A new cast = a new question.

## Reference tools (no chart, no gate)

`knowledge_read` / `knowledge_registry` (bundled manuals; `{"query": …}` searches every domain), `xuanshi` (玄史:
`action` search / events / event / figures / timeline …, detail actions take an `id` such as `fig-laozi`),
`export_registry` / `export_parse` (the export protocol), `otherbu` (astrology dice). 八字 sayings: `knowledge_read
{"domain": "bazi_pithy", "category": "三字诀", "key": "甲"}`. These carry no technique card.
