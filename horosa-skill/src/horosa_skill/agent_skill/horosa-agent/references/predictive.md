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

## Primary directions (`pd` / `pdchart`) engine surface — 星阙 v2.6.6 PD v12 parity

- **5 verified methods**: `core_alchabitius` / `meridian` / `porphyry` / `equal_ecliptic` /
  `equal_hour_circle`. Unknown method values fall back to `core_alchabitius` **inside the engine**,
  while the response `params` echo your original input — the snapshot honestly labels such rows
  「未核验，引擎回退 Alcabitius 半弧法」; keep that labeling.
- **22 time keys**, incl. per-chart true-computed Simmonite/Kepler/Brahe and dynamic
  TrueSolarArc/SymbolicSolarArc.
- **Vertex significator rows** (`N_Vertex_0`, In-Zodiaco only; 宿命点).
- `pdYears` up to **3000** with per-revolution recurrence rows (same promissor/significator pair at
  arc + 360°×n).
- Term (界) promissor row id = `T_<ruler>_<sign-name>`.
- Mundane (In-Mundo) planet-pair rows are notably richer than pre-v12 — that is an upstream fix, not
  a regression.
