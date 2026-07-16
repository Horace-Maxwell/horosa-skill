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
