# 中式技法 notes (大六壬 / 奇门 / 金口 / 三式 / 数算 / 六爻 / 神数)

> 读者：AI 客户端。何时读：调用中式技法前，或解释其结果时。策略总纲：[`../SKILL.md`](../SKILL.md)。

## 大六壬 defaults

- Xingque-compatible default: `guirengType: 2`（星占法贵人）. Only use `guirengType: 0`
  （六壬法贵人）or `1`（遁甲法贵人）when the user explicitly requests that noble-person system or an
  existing saved case specifies it.
- Ask about 贵人体系 / 昼夜贵人 only if the user does not accept Xingque defaults.
- Exports include 四课、三传、旬日、神煞、概览 plus the 解读层 (常用神煞 / 毕法 / 占断向导 — the
  占断向导 section appears only when `zhanCategory` ∈ {hunyin/taichan/jibing/caiyun/…}).

## Current-time casting (“用当前时间起一个大六壬盘” and similar)

1. Read the current local date, time, and timezone.
2. Include location/longitude/latitude if the user or client environment provides them.
3. Call the tool (`liureng_gods` / `horosa_cn_liureng_gods`; same flow for qimen/jinkou/…).
4. Explain only from the returned sections.
5. Never replace the tool call with an ad-hoc calendar script for 干支/天盘/四课/三传.

## 奇门遁甲 — 法奇门 overlay sections

The qimen snapshot ends with 8 法奇门 sections:
`[六害总览] [化解方案] [八门化气大阵] [用神分论] [财富七要] [事业七要] [恋爱姻缘] [孤辰寡宿]`.
These are computed by the **JS formatting layer** (`DunJiaFaCalc`/`DunJiaFaDoc`) on top of the
kinqimen pan — they are not a backend feature gap; `pan.source == "kinqimen"` still holds. The
`[八门化气大阵]` section may include per-person 「生年干·姓名」 rows when the payload carries
`faRelatedPeople` (skill normalizes `{name, birth}` → year stem by 立春 boundary). 八神 display is
normalized `勾→虎 / 雀→玄`.

## 三式合一 / 统摄法

- `sanshiunited` composes ken-computed 奇门 + 太乙 with the 大六壬 leg — expect all three parts.
- `tongshefa` export contract is exactly 本卦/六爻/潜藏/亲和 (najia/六合/升降 UI detail is
  intentionally out of scope).

## 数算 (canping / heluo)

- Computed fully in-process (vendored bazi chain + `lunar-javascript`) — no chart-service round trip.
- `timeAlg` default `1` (clock time); `0` = 真太阳时 (triggers longitude + EoT correction).
- 邵子 canping: `基础条文` is a real verse; `完整条文` may show the engine's `【条文待補充】`
  fallback — that is upstream-faithful (the id scheme isn't covered by the 6144-verse CSV), identical
  on macOS/Windows. Don't call it a bug and don't invent verses; the accurate 流年 table lives in
  `data.canping.series`.

## 六爻 (sixyao)

- With explicit `lines` (manual 摇卦), they take priority.
- Without `lines` (`[]`/`null`/absent), the tool casts **by time** (梅花易数): 上卦=(年+月+日支)%8,
  下卦=+时支%8, 动爻=%6 — different cast moments give different hexagrams, same input is
  deterministic. Ask for 起卦方式 when the user has a preference.

## 神数 (14 tools)

- Split-field input (`year`/`month`/`day`/`hour`/`minute`), 晚子时 switches forwarded, `options`
  passthrough for engine-specific overrides (e.g. wuzhao mode/number); `cetian`/`qizhengkin`/`xianqin`
  also take `gender` + place.
- Some presets have conditional sections (tieban/chunzi/cetian may emit fewer than the full preset
  for a given input) — a few `missing_selected_sections` on real exports is expected there, like
  election.
