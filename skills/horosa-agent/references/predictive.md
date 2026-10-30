# Predictive astrology contracts

> 读者：AI 客户端。何时读：调用 推运/返照/时运/主限 类工具前。策略总纲：[`../SKILL.md`](../SKILL.md)。

**Do not call predictive tools with natal data alone.** Minimum real-call contracts:

| Tool | Required beyond birth data | Output must include |
| --- | --- | --- |
| `solarreturn` / `lunarreturn` | `datetime` + `dirZone` + `dirLat` + `dirLon` | natal chart + return chart + return aspects |
| `givenyear` | `datetime` + `dirZone` + `dirLat` + `dirLon` | natal chart + given-year chart + aspects |
| `solararc` / `profection` | `datetime` + `dirZone` | natal chart + progressed/profection chart + aspects |
| `pd` | `pdtype` + `pdMethod` + `pdTimeKey` + `pdaspects` | real primary-direction table rows |
| `pdchart` | `datetime` + `dirZone` + PD method settings | primary-direction chart table + aspects |
| `zr` / `firdaria` / `decennials` | confirmed/default timeline settings | timeline rows |
| `agepoint` / `distributions` / `triplicityrulers` / `keypoints` / `lunationphase` / `extrareturns` and the v2.5.0 progressions | confirmed/default method settings (ask when result-changing) | technique table/sections |
| `ephemeris` (星历) | `startDate` + `endDate` (window ≤ 732 days; longer windows are truncated and say so) | ingress / station / lunation / eclipse tables + transits to natal (`includeTransits`, `eclipseTimeMode`) |
| `returntimeline` (回归轴) | `startYear` + `count` (1–40) | yearly solar/lunar return table |
| `prenatalsyzygy` (产前朔望) | birth data only | the prenatal new/full moon, its degree and chart |
| `prog` (回归黄道二次推运) | `targetDate` (default = today, like 星阙) + optional `targetTime` / `minorVariant` | secondary / tertiary / minor progression tables; sidereal → use `vedicprog` |

**Upstream defaults the tools mirror (v0.40.0)** — ask only if the user cares, otherwise say the default was used:

- `jaynesprog` / `vedicprog` / `prog`: `targetDate` = today; `minorVariant` = `synodic` (朔望月/年; `sidereal` / `engine` also).
- `planetaryarc`: `datetime` = tomorrow at this time; `arcSource` = Moon.
- `persiandirected`: `rateKey` = persian (1°/年; `prophected` / `naibod`), `direction` = direct, `maxYears` = 90.
- `zr`: `basePoint` = Pars Fortuna; output depth `aiMode` (`l1_all` default … `l4_in_l3`, with `aiL1Idx`–`aiL3Idx`).
- `profection`: [小限摘要] grain `profGrain` y/m/d, start `profStart` asc/sect/fortune/moon/mc.
- `balbillus`: `startPlanet` Sun, `yearType` solar, `mode` nearest. `keypoints`: `mode` soul (Moon) / body (Asc).
- `triplicityrulers`: `system` follows the chart's triplicity, `division` thirds, `lifespan` 75.
- `solarreturn` / `lunarreturn`: default target = this year's birthday.
- chart family: `lifespanMethod` (ptolemy default / alcabitius / dorotheus) for [寿命格局].
- 星阙's AI mount can also scan a datetime *range* (`datetimeEnd` / `scanStep`, one segment per point); the skill does
  not implement that yet — call the tool once per target date.

The same contracts are exposed through `uv run horosa-skill tool list`,
`uv run horosa-skill agent guidance --tool <tool>`, MCP `horosa_agent_guidance`, and tool docstrings.
Use before any predictive call:

```bash
uv run horosa-skill agent guidance --tool solarreturn
uv run horosa-skill tool list
```

If the user asks “看今年运势” without target year/date and location, ask for the missing values. Do
not silently use the current date or the birth location unless the user accepts that default.

## Primary directions (`pd` / `pdchart`) engine surface — 星阙 v3.13.0 parity

- **Direction type `pdtype`** (integer): `0` In Zodiaco (default) / `1` In Mundo / `4` Field Plane. `2`/`3` are
  backend-internal term-distribution values and are rejected.
- **Two orthogonal axes**: `pdProjection` (arc algorithm, 14: `ptolemy` default / `placidus` / `regiomontanus` /
  `campanus` / `topocentric` / `zodiacal` / `ra_direct` / `in_zodiaco_lon` / `in_zodiaco_abs` / `horosa_legacy` /
  `placidus_under_pole` / `morinus` / `horizontal` / `koch`) × `pdFrame` (chart houses, 12, only moves cusps).
  The legacy single key `pdMethod` (13 named combinations) only decides what you did not pass explicitly; when you
  pass `pdProjection`, [主限法设置] drops the 「推运方法」 line (the two axis lines say it).
- **38 time keys** `pdTimeKey`, incl. per-chart Simmonite / 生日黄经日行 / Kepler / Brahe, dynamic
  TrueSolarArc / VanDam / SymbolicSolarArc, Ascendant-arc / Vertical-arc timing, and `*Classic` variants (the
  traditional programs' mean-obliquity / day-after-birth / truncated constants).
- **Settings registry** (10 keys, all default-off = upstream default request): `pdGeometry` improved/classic (only
  some direction × arc combinations differ — the arc line then reads 「（改进）/（经典）」), `pdAspectSide`,
  `pdTradConverse`, `pdIgnoreSigLat`, `pdIgnorePromLat`, `pdLunarParallax`, `pdTruePosition`,
  `pdSolarArcRegressive`, `pdYearDays`, `pdPromAspectLat`. Every value is echoed as one line in [主限法设置];
  `pdchart` echoes 日期年长 (it changes how the chosen moment maps to an arc). Values the upstream panel cannot
  express are rejected, not silently defaulted.
- **Honest baseline notes**: In Mundo / Field Plane combinations without a dedicated kernel are labelled
  「（世界主限下走核内基线）」/「（Field Plane 下走核内基线）」 — several choices can produce identical rows.
- Row ids: fixed-star promissors are `FS_<star>_0|180` / `FSD_<star>_θ` (dexter) / `FSS_<star>_θ` (sinister) and
  render as 「恒星 X的θ度右/左相位处」. In Mundo the engine adds axis significators 下降 / 天底 / 宿命点 (Vertex) /
  反宿命点 (Antivertex); under the default `pdMethod=core_alchabitius` display rule only core bodies are kept (upstream
  same), so pick another method to see those rows.
- `pdchart` [主限法盘设置]: 弧算法（主限法表用）/ 盘面宫制（外圈宫头）/ 度数换算 / 向运方向 / 日期年长 / 当前Arc —
  the outer ring is the whole sky advanced along RA by the arc, so only `pdFrame` changes it.
- `pdYears` up to **3000** with per-revolution recurrence rows (same promissor/significator pair at
  arc + 360°×n). Term (界) promissor row id = `T_<ruler>_<sign-name>`.
