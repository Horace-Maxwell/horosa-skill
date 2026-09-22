# Evaluation

> 读者：维护者。何时读：跑/改 HorosaBench 评测、忠实性校验与自检方法时。

## 评测体系

Horosa Skill 现在有三层评测：

- 工程自检：确保每个工具能调用、能输出、能落库、能检索
- HorosaBench：确保调度、导出协议和知识读取质量达到稳定基线
- 盘面事实忠实性（faithfulness）：确保 AI 解读没有**编造/说反盘面事实**——确定性校验，非 LLM 打分

## HorosaBench

数据集 = 手写 case + **注册表生成 case**（`generate_tool_cases()`，与 92 工具锁步——新增技法
没有 bench case 直接红）：

- 手写部分：[`horosa_bench.json`](./../horosa-skill/src/horosa_skill/benchmark/data/horosa_bench.json)
- 生成部分：`src/horosa_skill/benchmark/runner.py`（按 `TOOL_EXPORT_TECHNIQUE_MAP` + 导出 preset 断言
  期望 technique 键、必出段、禁 generated_template、format_source == snapshot_parser）

覆盖维度：

- 自然语言问法 -> 应选工具
- 工具输出 -> 必须出现的 technique / section / fragment
- 知识读取 -> 必须命中的 hover 内容
- runtime 依赖与否 -> 可做 CI 的 local-only smoke

## 盘面事实忠实性（faithfulness，v0.28.0 起）

实现：`src/horosa_skill/benchmark/faithfulness.py`。两步：

1. `extract_facts(envelope)` 从已存 envelope 抽**机读真值**；
2. `verify_answer(answer_text, facts)` 识别答案中的事实型断言，逐条判
   `supported / invented / contradicted`；`ok` = 零 invented 且零 contradicted。

已覆盖断言族（逐版扩）：

| 族 | 真值来源 | 版本 |
| --- | --- | --- |
| 四柱干支（槽位化） | `bazi.fourColumns` | v1 |
| 西占行星落座 | `chart.objects`（EN→CN 正名） | v1 |
| 紫微身宫 | `houses[].isBody` | v1 |
| 大六壬三传 | 快照 `三传：` 行 | v1 |
| 裸干支词元兜底 | 快照 CJK 2–4 字子串全集 | v1 |
| 紫微十四主星落宫（含流派宫名别名归一） | `houses[].starsMain` | v2 |
| 六爻本卦/之卦名（缩略互含）+ 动爻位 | 快照 `本卦：/之卦：` 行 + `lines[].change` | v2 |
| 塔罗牌名正逆（钱币/星币两写法归一，78 牌词表） | 快照 `[逐牌详解]` 表行 | v2 |
| 奇门值符星 / 值使门 / 星门落宫 | 快照 `值符：/值使：` 行 + 九宫行（`坎一宫：…`） | v3 |
| 择日命中区间（推荐日期必须落在命中区间内；有命中却说「无命中」判红） | `data.intervals[].startDate/endDate` | v3 |
| 推运时段边界（行星 ↔ 年/年月必须出现在该行星的表行） | 快照推运表格（法达/大运/主限… 任何带日期的表行） | v3 |

**族门槛**：v2 各族只在该族真值存在时才判——合参一答多盘时不拿八字盘的空真值红一段紫微话。

对抗用例（tests/test_faithfulness.py 钉死）：喂错盘（wrong-chart swap）必须整片判红；
诱导复述（「我月亮在天蝎对吧」/「我抽到的月亮是逆位吧」）必须 contradicted；
纯解读语（不引具体盘面值）不许扣分；技法名短语（「从六爻动向看」）不许误判成爻位断言。

```bash
uv run horosa-skill benchmark faithfulness --run-id <run_id> --answer-file answer.txt
```

## 决策层评测与晋升（v0.39.0 起，可选云端 TypeSafe Jev）

决策层（`HOROSA_JEV`，缺省 off）只有**在自家中文金标集上测过并过闸**的面才允许改行为；机制与数字都在仓里：

| 项 | 位置 |
| --- | --- |
| 金标集 | `contracts/jev_eval/{routing,extract,zhancat}.jsonl`（人工标注，`scripts/gen_jev_eval_sets.py` 生成；routing 允许 `accept` 多解与 `expect: null` 弃权，含注入与非术数样本） |
| 录制 / 回放 | `scripts/jev_eval.py measure`（唯一真调用，原始响应录进 `contracts/jev_eval/cache.jsonl`）→ `compile` / `check` 零调用回放，解析走线上同一套 `parse_answers` |
| 切分 | 按 `group` 哈希稳定 70/30，同组改写落同侧（改写一致性不泄漏进留出集） |
| τ 选择 | 训练集扫 0.50–0.99，满足精度目标者取处理率平台期（−2 pt）内最大的 τ |
| 预注册闸 | `PROMOTION_GATES`：留出集 n≥30 · 采纳判定精度≥0.95（routing 看无匹配子集）· conf-ECE≤0.10 · 升级率≤0.15 · 改写「都对率」≥0.90 · extract 填错率=0 |
| 输出 | `contracts/jev_thresholds.json`（模型 / 数据集 sha / 逐面 τ、promoted、证据）+ `contracts/jev_eval/report.json` |
| 漂移 | `scripts/jev_eval.py check`：数据集 sha 变 / 模型 id 变 / 回放不过闸 → 非零退出；线上返回模型 id ≠ 钉版则该轮降影子 |

首轮（2026-09-22，jev-1.13.0，1012 次调用，$0.03，p50 170–220 ms，两次录制零翻转）：dispatch τ 0.54 晋升（无匹配子集采纳精度
1.0，处理率 0.79，ECE 0.087；确定性关键词路由自身 0.975）；zhancat τ 0.86 晋升（采纳精度 1.0，处理率 0.92，ECE 0.025）；
extract 未晋升——精度 1.0、填错 0、改写一致 1.0，但 ECE 0.104（欠自信）差 0.004 于闸。**差一点也是不过**：闸是预注册的，
改数字要改代码并留痕。二档 `snapshot` 的 S4 只读意见（`benchmark faithfulness` 的 `model_opinion`）永不改确定性判定。

## 运行方式

```bash
uv run horosa-skill benchmark run
uv run horosa-skill benchmark run --skip-runtime
uv run python scripts/run_full_self_check.py --rounds 2
```

## 当前指标

- `cases_passed / cases_executed`
- `pass_rate`
- dispatch `selection_ok`
- export `required_sections_ok`
- export `required_fragments_ok`
- knowledge `required_fragments_ok`
- faithfulness：`claims_total / supported / invented / contradicted / faithfulness_ratio`

## 已知盲区

- benchmark 目前仍以 golden corpus 为主，还不是公开 leaderboard
- 忠实性校验只判**事实断言**，不判解读质量；断言族逐版扩，未覆盖族的断言不计入
- Windows runtime 的进程级实机验证需要 Windows runner
- `fengshui` 仍然刻意排除在当前主线之外
