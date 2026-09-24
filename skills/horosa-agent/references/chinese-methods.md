# 中式技法 notes (大六壬 / 奇门 / 金口 / 三式 / 数算 / 六爻 / 神数)

> 读者：AI 客户端。何时读：调用中式技法前，或解释其结果时。策略总纲：[`../SKILL.md`](../SKILL.md)。

## 大六壬 defaults

- Xingque-compatible default: `guirengType: 2`（星占法贵人）. Only use `guirengType: 0`
  （六壬法贵人）or `1`（遁甲法贵人）when the user explicitly requests that noble-person system or an
  existing saved case specifies it.
- Ask about 贵人体系 / 昼夜贵人 only if the user does not accept Xingque defaults. 贵人 3（甲戊兼牛羊）/ 4（干合阳阴贵）
  are available too (v0.40.0).
- 起课 runs on the vendored 星阙 `LiuRengMain` engine: all **26 起课法** (`options.castMethod`, default `zheng`
  正时正将; `xuanshi` needs `xuanShiZhi`, `yanshu`/`baoshu` need `yanShuNum`), 换将 (`yueJiangMethod`), 分昼夜
  (`fenZhouYe`), 涉害 (`seHaiMethod`/`seHaiBoundary`/`shiRuKe`), 阴阳系, 年神序, 土旺衰, 十二长生五行 and `options.timeAlg`
  (0 = 真太阳时, default) — full list in `horosa_agent_guidance(tool_name="liureng_gods")` → `options_keys`.
  Unrecognised values fail with `tool.liureng_invalid_option` instead of silently falling back.
- `liureng_runyear`: `date`/`time` = the querent's birth, `guaDate`/`guaTime` = the casting moment.
- Exports mirror the upstream snapshot builder (tables, 起课法/换将/分昼夜 lines, [十二长生]/[大格]/[小局]/[参考]/[概览]) plus
  the 解读层 (常用神煞 / 毕法 / 占断向导 — the 占断向导 section appears only when `zhanCategory` ∈
  {hunyin/taichan/jibing/caiyun/…}); [三传] carries 递生递克 and the per-传 空/禄/马 badges.

## Current-time casting (“用当前时间起一个大六壬盘” and similar)

1. Read the current local date, time, and timezone.
2. Include location/longitude/latitude if the user or client environment provides them.
3. Call the tool (`liureng_gods` / `horosa_cn_liureng_gods`; same flow for qimen/jinkou/…).
4. Explain only from the returned sections.
5. Never replace the tool call with an ad-hoc calendar script for 干支/天盘/四课/三传.

## 奇门遁甲 — defaults and routing (v0.40.0)

- 起局法 default = **置闰** (`qijuMethod: zhirun`, 星阙 `DunJiaMain` DEFAULT_OPTIONS); `chaibu` 拆补 / `maoshan` 茅山 /
  `wurun` 无闰 / `shuzi` 阴盘报数 (needs `shuziReportNumber`). `timeAlg` 0 = 真太阳时 (default): ken casts from the
  true-solar date parts, so 九宫 and 时柱 agree.
- Routing mirrors upstream `isQimenLocalRoute`: 非时家 (`paiPanType` ∉ {3,5}), 飞盘/混合, 报数, or any of the seven
  local-only settings non-default → the pan is computed by the local `calcDunJia` engine (not ken). The result says so:
  `data.route.local = true`, `compute_sources.pan = local_route_calcDunJia`. This is upstream's own choice, not a fallback.
- 金口诀 routes the same way: all five 流派/盘法 keys default → ken; any non-default → local `buildJinKouData`
  (`compute_sources.jinkou = local_route_buildJinKouData`; `timeBasis` then has no effect and a warning says so).
  地分 defaults to **auto = 占时支**; 贵人 default 0; 十二长生五行 default = day-stem element.
- 太乙: six 流派 axes via `options.school` (`jishen`/`wenchang`/`keJianChen`/`sanji`/`youshen`/`shijiCoord`), `timeBasis`
  `direct` (default) / `trueSolar` — the 四柱 follow the chosen basis, like upstream.

## 奇门遁甲 — 法奇门 overlay sections

The qimen snapshot ends with 8 法奇门 sections:
`[六害总览] [化解方案] [八门化气大阵] [用神分论] [财富七要] [事业七要] [恋爱姻缘] [孤辰寡宿]`.
These are computed by the **JS formatting layer** (`DunJiaFaCalc`/`DunJiaFaDoc`) on top of the
kinqimen pan — they are not a backend feature gap; `pan.source == "kinqimen"` still holds. The
`[八门化气大阵]` section may include per-person 「生年干·姓名」 rows when the payload carries
`faRelatedPeople` (skill normalizes `{name, birth}` → year stem by 立春 boundary). 八神 display is
normalized `勾→虎 / 雀→玄`.

## 三式合一 / 统摄法

- `sanshiunited` composes 奇门 + 太乙 with the 大六壬 leg — expect all three parts. Per-leg settings: `qimen_options` /
  `taiyi_options` (or top-level `taiyiTimeBasis`) / `liureng_options` (castMethod locked to `zheng`, as upstream).
- `tongshefa` export contract is exactly 本卦/六爻/潜藏/亲和 (najia/六合/升降 UI detail is
  intentionally out of scope).

## 数算 (canping / heluo)

- Computed fully in-process (vendored bazi chain + `lunar-javascript`) — no chart-service round trip.
- `timeAlg` default `0` = 真太阳时 (longitude + EoT correction, 星阙 default); `1` = clock time. Day-boundary switches
  default to 1/1 like every other 中式 tool (v0.40.0; the skill previously defaulted these three 数算 tools to clock time).
- 邵子 canping: `基础条文` is a real verse; `完整条文` may show the engine's `【条文待補充】`
  fallback — that is upstream-faithful (the id scheme isn't covered by the 6144-verse CSV), identical
  on macOS/Windows. Don't call it a bug and don't invent verses; the accurate 流年 table lives in
  `data.canping.series`.

## 六爻 (sixyao)

- With explicit `lines` (manual 摇卦), they take priority; a `gua_code` without `lines` rebuilds the lines from the code.
- Without `lines` (`[]`/`null`/absent), the tool casts **by time** with 星阙's own `buildTimeGua`: 上卦 = (年支序 + 农历月数
  + 农历日数) % 8, 下卦 = + 时支序, 动爻 = % 6, where the 时柱 follows `timeAlg` (0 = 真太阳时, default). Same input is
  deterministic; ask for 起卦方式 when the user has a preference.
- 判读口径: `liuyaoSettings` (the 24 keys of 星阙's 六爻 gear: 流派 / 用神 / 飞伏 / 旬空 / 神煞 / 十六变 / 天时 …; see
  `options_keys`). [断诀命中] and [占类断语] come from 星阙's doctrine library and depend on `askType` and these keys.

## 神数 (14 tools)

- `date`/`time` input (split into engine fields internally), 晚子时 switches forwarded, and a **typed** `options`
  object per tool (keys and allowed values in `horosa_agent_guidance(tool_name=…)` → `options_keys`; unknown keys are
  reported in `data.params_ignored`, never silently forwarded). `cetian`/`qizhengkin`/`xianqin` also take `gender` +
  place. `wangji` (皇极经世) `xinyiMethod` accepts `datetime` (default) / `number` / `direction` / `character` / `none`.
- Display names follow 星阙's technique table: 荆诀 (jingjue), 神易数 (shenyishu), 鬼谷分定经 (fendjing), 蠢子数 (chunzi),
  万化仙禽 (xianqin).
- Some presets have conditional sections (tieban/chunzi/cetian may emit fewer than the full preset
  for a given input) — a few `missing_selected_sections` on real exports is expected there, like
  election.

## 神数正传 + 4 新占卦技法（上游 v3.5.0）

**共通铁律 · 冻结值**：这些技法的「课/局/卦/四柱」一经起出即为**冻结值**——改流派、改用宫、改十开关
只**重排判读**，绝不重起课/局/卦（重起 = 伪造一个用户没见过的盘）。改了起卦输入 = 另占新盘。

- **`zhengchuan` 神数正传**：`school` 五选一——`tieban` 铁板 / `shaozi` 邵子 / `dading` 大定 / `liuqin`
  六亲 / `xinyi` 铁算心易。除 `xinyi`（查询层，只需 item/sound/ke/gong/xqZhi/xqYushu）外，都需生辰
  （date/time/zone[+lon] + gender），四柱走 `/nongli/time` 权威口径（立春界年柱）；铁板/邵子异步载条文
  正文库。流派专属：shaozi `fatherAge`/`motherAge`/`yuan`；liuqin `askHourZhi`/`env`；dading `dadingYear`
  （所推流年，小运/大运/岁君自八字推运表派生，四柱仍以权威柱为准）。段随流派子集出、唯一恒出=起盘信息。
- **`xiaoliuren` 小六壬**：`nums=[月,日,时]` 三正整数显式起课，或按占时（date/time → 农历月/日/时支序）。
  `school` main 主流六宫（无五行生克，[生克]段如实标注）/ dao 道门九宫（含生克与拜解）。6 段严格。
- **`feigong` 飞宫小奇门**：`qiMode` hour 时支（默认，占时）/ manualZhi 选支 / manualNum 数取 / yearZhi 年支，
  + 日干支（占时自 `/nongli/time` 取）。命宫随 `mingAge`/`mingGender`；`koujing` 河魁口径 zheng/yi 两说。7 段严格。
- **`xiaochengtu` 小成图**：`qiguaFa` manual（上/下卦 up/lo + dongYaos）/ number（upNum/loNum + qiguaShu）/
  stock（open/close **字符串保末尾 0**）/ dayan（**须显式 seed 或 counts，禁静默随机**）/ time（占时梅花卦）。
  `yongGong` 用宫 1-9 非5。[股市]段仅 stock 模式出。
- **`guice` 皇极轨策**：`qiguaFa` 十二法（time/baoshu/wushu/shengyin/zizhan/zhangchi/chicun/weiren/ziji/
  dongwu/jingwu/duanfa）+ 各法专属输入；十开关流派（school/yanshuFa/qiguaShu/shuXi/shiFang…）。起卦时刻
  （date/time）供元会运世/时方所需四柱。占事直断/演数/四位 恒出，余段随盘面/开关条件出。
