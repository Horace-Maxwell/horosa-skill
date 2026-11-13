# Technique notes (which tool, which inputs)

> Reader: an AI client. Read when you choose between similar techniques or need a technique's special inputs.
> The key list is in [`../SKILL.md`](../SKILL.md) §13. Per-technique contracts: `horosa_agent_guidance {"tool_name": "<key>"}`.

## Western

| Want | Tool and inputs |
| --- | --- |
| Natal chart | `chart` (13-house `chart13`, 12th-harmonic / Dwadasamsa `chart12`, Hellenistic `hellen_chart`). `chart` and `relocation` carry [古典] + [古典格局]; `india_chart` / `mundane` carry [古典] only. `india_chart` also carries [Yoga 判定表] (111 rules, improved + classic columns), [印占补充表] and [穿界时刻] (ingress table from `transitDate`; `indiaTransitPlanet` / `indiaTransitKind` / `indiaTransitDays` pick the planet, event and span). |
| Derived charts | `draconic` (`draconicHouses`: `whole` default / `shift`), `relocation` (needs `relocLat` / `relocLon`), `harmonic` (whole number 1–360). |
| Transformed chart | `transformchart`: `transformKind` picks one of 33 transforms (default `inverted`; Chinese names accepted). Only the options that transform uses take effect — `transformVariant` (`improved` default / `classic`) for `inverted` / `sunRise` / `novien` / `nodeHouses`; `transformPlanet` (default `Moon`) for `superimposed` / `planetCentered` (Sun = heliocentric) / `persona`; `transformShift` for `superimposed`; `transformHouse` (1–12) for `epoch`. An option the transform does not use is ignored and listed in `data.params_ignored` with a warning. Output = the whole transformed chart + [变换盘] (before / after longitudes, modern house rulers, golden-section points); no [可能性], no [古典格局]. `persona` / `epoch` cast another moment (written in [变换盘]); an epoch chart at high latitude may have no solution (`tool.transformchart_empty`). Full table: `horosa_agent_guidance(tool_name="transformchart")`. |
| Zodiac systems | `zodiacsystems`: `zodiacVersion` picks one of 19 zodiacs (default `z13a`, 13 signs version A; `z13*` 13-sign, `z14` 14-sign, `z12a`–`z12g` unequal 12-segment). Longitudes do not change, only the division: one [黄道制] section with each point's segment in that version, its true IAU constellation (points off the zodiac are marked), galactic zodiac, last / next constellation change and 13 houses. No chart body. House system and tropical / sidereal do not change the result. |
| Relationship 合盘 | `relative` with `inner` and `outer` (each: date / time / place or zone+lat+lon); `relative` 0–4 picks the chart type (0 比较盘 default). Both people need a birth time. Every type also carries [八重合] (Ashtakoota, sidereal Moon match out of 36): the groom side is `ashtakootaMaleSide` (`inner` / `outer`) or, without it, the two `gender` values — unknown or same gender → chart A; the section's first lines say which side was used. |
| Midpoints / Uranian | `germany` (`rectifyEvents` → [校时预览]; `mpCoord` ra / decl → [中点坐标]). |
| Babylonian | `babylon` (no houses / aspects / Asc by design). [天象实算] is computed for the birth moment and place (three paths, ziqpu star clock, goal-year lookups, planetary phenomena and visibility); it has no settings of its own. |
| Mundane | `mundane` (year + 入宫节气 + place; `mundaneType`, `mundaneRuleset`). `mundaneType: "cycles"` adds [世运周期表] (`cycleTable` picks one of 14 tables; each table reads only its own options) and [Barbault 聚散指数] (`bbSet`, `bbHarm` 1–12). An option that does not apply to the chosen table is reported in `warnings`. |
| Astrocartography | `acg` (`clickLat` / `clickLon` adds the spot analysis). `eclipse` `prenatal` / `postnatal` (+ `eclipseFilter` `central`) adds the nearest solar eclipse's path; `climes` `klimata` / `parallels` (+ `climesObliquity`) adds the latitude bands. Both are off by default. |
| Planet cycles | `planet_cycles` (no natal chart; the planet pair and year range are asked). |
| Birth-time rectification | `india_rectify` (needs dated life events; returns ranked evidence — the user decides). |
| Horary 卜卦 | `horary`: `category` (question type) and `school` are asked; an unknown `category` is refused with `tool.invalid_option` (no fallback to a general question). The chart is cast with the school's house system / terms / triplicity. |
| Judge one candidate moment | `election` (`topicId` — unknown values refused with `tool.invalid_option`; pass `natal` to add [本命合参]). 七政 version: `qizhengelection` (action pan / eclipses / azimuthsearch). |
| Celebrity data | `astrodata` (read-only, no gate). |

Predictive techniques: [`predictive.md`](./predictive.md). `sunriseMode` (`center` default / `apparent`) applies to
the Western charts and 七政. Orbs travel with the chart: `orbs` (`{"Sun": 10}`, body id → degrees) and `orbScale` (a
multiplier above 0, default 1) change the aspects of the `horary` and `election` charts — and so the judgment — and of
`tianxing`'s selected-moment chart only (its window search ignores them: each condition carries its own orb). An
unreadable value is refused with `tool.invalid_option`; an id that is not a body of the chart is reported in `warnings`.

## 择日 window search

`tianxing` (Western; `explainAt` judges one moment leaf by leaf), `qimenzeri`, `huanglizeri` (day grain), `bazizeri`,
`taiyizeri`, `ziweizeri` (needs gender), `liurengzeri`, `sanshizeri` (conditions may span the three 式), `qizhengzeri`,
`indiazeri` (Muhurta; its text is the full `india_chart` of the first hit + the three search sections). All take `startDate` / `endDate` (`maxSpanDays` caps the window, 366 by default; split longer windows) + a `conditions` tree
+ a base `date` / `time` / place. Condition types and their meaning: `horosa_agent_guidance {"tool_name": …}` →
`condition_types` (generated from the engine's own table). Polarity and `condition_echo`: SKILL.md §8. Hit intervals
carry `pick` (a boundary-safe moment): cast a chart for a hit with `pick`, not `start`. Zero hits still return the
sections and say no period matched — that is not a missing section.

## Chinese

| Want | Tool and inputs |
| --- | --- |
| 八字 | `bazi_birth` (chart), `bazi_direct` (大运流年). Both need gender. `tianyiSchool` `xieji` default / `ziping`; `southMonth` for southern births. `bazi_inverse {"pillars": ["甲子", "丙寅", "戊辰", "庚申"], "fromYear": …, "count": 1–10}` returns candidate birth times (they repeat every 60 years: the user picks). |
| 紫微斗数 | `ziwei_birth` (22 传本 keys + `sihuaSchool`; `period`), `ziwei_rules` (rules library). |
| 七政四余 | `guolao_chart` (`guolaoLifeMode`, `guolaoBodyMode`, `planetaryHourMethod`, `moiraTransitDate`; 宿度制 `doubingSu28`). [相位] here is 七政 aspects (會 / 衝 / 刑 / 合 / 半合), not Western ones. [虚实] / [本命化曜] / [流年流曜] come from the Java rules layer and are absent (with a warning) when it is down. `ascRaMode` (`improved` true RA, default / `classic` east-point longitude) moves the 上升 on equatorial 宿度制 only (`doubingSu28` 0/1/5/7/8). |
| 河洛 / 邵子参评数 / 一掌经 | `heluo`, `canping`, `yizhangjing` (all need gender; AD 1–9999). |
| 藏历 / 藏占 / 蒙古 Zurkhai / 算命学 / 九星气学 / 洛书流年 / 易卦星盘 | `dongya` — one call returns all seven as sections; ask for any of them with this tool and pick with `response_sections` (e.g. `["九星气学"]`). Needs gender (藏占 year trigram) and the birthplace (the Tibetan day starts at 5 am local mean time; 易卦星盘 reads the natal planets). `flowYear` (1–9999) sets the year for 藏占 / 洛书流年 / 天中杀; without it the current year is used, and the 易卦推运 line follows today. `fenyeVersion` `common` / `fajue`; `ichingMerge` `horizon` / `upper` / `lower`; `hsys` moves the 宫卦. AD 1–9999. |
| 玛雅历 / 十三月亮历 / 人类图 / 灵名字母 | `zhufang` — one call returns all four as sections; pick with `response_sections` (e.g. `["人类图"]`). `mayanCorrelation` `584283` default / `584285` / `584286`; `hdTrueNode` true default / false (mean node); `spiritQuadrant` 1 / 2 / 3; `hsys` moves the 灵名字母 house rulers. Human Design is tropical: `zodiacal: 1` has no effect (a warning says so). If the backend cannot compute a block, that section reads 「未算出」 and a warning names it. BC dates: the two calendars are not cast (the section says so). |
| 宿占 | `suzhan` (`houseStartMode` 0 八字公式 default / 1 ASC; with ASC, `ascRaMode` `improved` default / `classic` picks which ascendant RA sets the 命宫 — the snapshot states it. Western classical keys have no effect, as in 星阙). |
| Calendar | `huangli` (one day), `tongshu` (needs `school`; the five schools can disagree on the same day; keys such as `sanyuanliexiu`, `sanyuan`), `calendar_month`, `nongli_time`, `jieqi_year` (its [X宿盘] sections take `houseStartMode` / `ascRaMode` like `suzhan`), `jieqi_birth` (`useLocalMao` 1 = 卯时 of the birth day instead of the spring-equinox day, `byLon` 1 = solve by ecliptic longitude instead of right ascension; give either and [起盘信息] states the 卯时). |
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
