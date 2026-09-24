# 晚子时 / 日界 two-switch spec (canonical)

> 读者：AI 客户端（也是维护者/测试的自检基准——本文件是这套矩阵的唯一属主）。
> 何时读：输入时间落在 `[23:00, 24:00)`，或用户提到 晚子时/子时/23点/24点。
> 维护者侧的线穿状态与上游根因：[`AGENTS.md`](../../../AGENTS.md) §10。

> **✅ STATUS (as of skill v0.40.0): fully threaded, defaults = 星阙 (1, 1).** Nothing hard-codes
> `after23NewDay=0` any more: when a switch is absent it is **not sent**, so Java / ken / Python engines apply
> their default 1 (= 星阙 default). Local-engine paths (bazi on the vendored lunar engine, ziwei on ZiweiCalc)
> receive an explicit 1/1, because the local engine reads a missing key as "no shift". jinkou forwards both
> switches to ken. `jieqi_year` ignores `after23NewDay` (upstream Java hard-codes it); `lateZiHourUseNextDay`
> still reaches it.

For ANY hour-23 input (`time` ∈ `23:00:00`–`23:59:59`), the four pillars depend on **two independent
settings**. Treat them as separate flags — the user may have set one or both globally in 星阙 desktop,
and predictive runs must mirror what the user sees on screen.

| Field | Values | Default | Effect at `hour == 23` |
|---|---|---|---|
| `after23NewDay` | `1` / `0` | `1` | `1` = “23点算第二天” → day pillar advances to next day. `0` = “24点算第二天” → day pillar stays today. |
| `lateZiHourUseNextDay` | `1` / `0` | `1` | `1` = “晚子时按次日日柱计算” → hour stem 起 from next-day day stem. `0` = “晚子时按当日柱计算” → hour stem 起 from today's day stem. |

**Outside of `hour == 23`, both flags are no-ops.** They change nothing in `[00:00, 23:00)` — don't
ask about them unless the time is actually in that window.

## Self-check matrix — `2026-05-27 23:30:00`, direct-time mode

| `after23NewDay` | `lateZiHourUseNextDay` | 日柱 | 时柱 |
|---|---|---|---|
| 1 (default) | 1 (default) | 壬寅 | 庚子 |
| 1 | 0 | 壬寅 | **戊子** |
| 0 | 1 | 辛丑 | 庚子 |
| 0 | 0 | 辛丑 | **戊子** |

The two switches are **fully independent** (upstream `utils/dayBoundary.js:47-57`, aligned 2026-09-18 across the
local lunar engine, Java `BaZiHelper` and the Python engines): `lateZiHourUseNextDay=0` always starts the hour stem
from the **clock day's** stem (辛 → 戊子), even when `after23NewDay=1` has already advanced the day pillar.

If a tool returns four pillars that don't match this matrix for that fixture, the runtime is stale
(predates upstream v2.2.1) — tell the user to re-install the runtime release; do not blame the
technique, and do not patch around it.

## How to ask the user

- If the user mentions 晚子时 / 子时 / 23 点 / 24 点, ask which mode before calling. Options:
  - 日柱开关：「23点算第二天 (默认)」 / 「24点算第二天」
  - 时柱开关：「晚子时按次日日柱计算 (默认)」 / 「晚子时按当日柱计算」
- If a stored case/memory contains either field, reuse it and cite the saved run.
- If the user says 「默认 / 按星阙 / 你来决定」, use `after23NewDay: 1` + `lateZiHourUseNextDay: 1`
  and mention that defaults were used.

## Payload + explanation rules

- The flags belong on every chart-flow payload (`chart`, `bazi_birth`, `bazi_direct`, `ziwei_birth`,
  `liureng_gods`, `liureng_runyear`, `qimen`, `taiyi`, `jinkou`, `sanshiunited`, `canping`, `heluo`,
  `nongli_time`, `jieqi_year`). Tools that don't read them ignore them harmlessly — but tools that DO
  read them silently pick `1`/`1` if absent, which can disagree with the user's 星阙 desktop settings.
- **Always quote the active rule back.** The export snapshot carries a leading
  `排盘规则: 日柱开关【…】+ 时柱开关【…】。本盘四柱按此规则计算。` line — mirror it in your
  interpretation/report so the user can verify the convention. Never strip it.
- **`canping` / `heluo` exception**: their upstream `buildSnapshotText` does not emit the 排盘规则 line
  (the skill keeps the snapshot byte-identical to 星阙), so the active flags are echoed in the
  tool's `input_normalized` (`after23NewDay` / `lateZiHourUseNextDay`) instead — read them from there.
