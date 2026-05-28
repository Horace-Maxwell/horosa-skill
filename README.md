**简体中文** | [English](./README_EN.md)

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>把星阙 / Horosa 变成任何 AI 都能本地调用的离线玄学能力层。</strong></p>
  <p>下载仓库，安装一次离线 runtime，然后让 Claude、Codex、Open WebUI、OpenClaw 等 AI 在你的机器上直接调用真实算法、读取完整 AI 导出协议、输出稳定结构化结果，并把每次分析沉淀为可检索的本地记录。</p>

  <p><a href="https://github.com/Horace-Maxwell/horosa-skill"><img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" /></a>&nbsp;<a href="https://github.com/Horace-Maxwell/horosa-skill/releases"><img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" /></a>&nbsp;<a href="./README_EN.md"><img src="https://img.shields.io/badge/Read%20in-English-0f766e?style=for-the-badge" alt="Read in English" /></a></p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=flat-square" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=flat-square" alt="Release" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=flat-square" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=flat-square" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=flat-square" alt="SQLite and JSON" />
  </p>

  <p><a href="./LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square" alt="License" /></a>&nbsp;<a href="./CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square" alt="Contributing" /></a>&nbsp;<a href="./SECURITY.md"><img src="https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square" alt="Security" /></a></p>

  <p><a href="./SUPPORT.md"><img src="https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square" alt="Support" /></a>&nbsp;<a href="./CITATION.cff"><img src="https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square" alt="Citation" /></a>&nbsp;<a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/Changelog-Updates-f59e0b?style=flat-square" alt="Changelog" /></a></p>
</div>

## 文档入口

- 工程运维：[`docs/OPERATIONS.md`](./docs/OPERATIONS.md)
- 评测体系：[`docs/EVALUATION.md`](./docs/EVALUATION.md)
- 架构设计：[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- 数据契约：[`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md)
- 输入契约：[`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md)
- MCP 元数据：[`server.json`](./server.json)
- Agent 使用 Skill：[`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md)
- Agent 仓库规则：[`AGENTS.md`](./AGENTS.md)

## 最新稳定基线

当前公开版本：`Horosa Skill 0.7.0`

这一版的核心变化是**把奇门遁甲、太乙神数、金口诀（以及三式合一中的奇门 + 太乙）统一到星阙的 `ken` 计算后端**。`kinqimen` / `kintaiyi` / `kinjinkou` 三个引擎挂载在本地 Python chart 服务上，独占盘面计算权；headless JS 层不再自己起盘，而是把 ken 返回结果通过星阙的 `normalizeKinqimenData` / `normalizeBackendPan` / `normalizeKinjinkouData` 重新格式化成 `aiExport.js` 的 section 结构。结果是：Skill 的盘面与星阙桌面端走**同一套后端、逐值同源**，对外导出仍然是稳定的星阙式 `export_snapshot` / `export_format` contract。三个引擎已随离线 runtime 一起打包，macOS / Windows 均可断网运行。

在此之前确立、并在本版继续生效的硬性协议是“AI 不能乱补参数”：只要技法会受时间、地点、时区、性别、事项、宫制、历法、起局方式等设置影响，agent 在用户没有确认前就不能继续调用。工具会返回结构化阻断结果，并给出可直接转发给用户的追问文本。

本机完整实测结果：

| 检查项 | 结果 |
| --- | --- |
| 可调用工具 | `42 / 42` |
| 奇门 / 太乙 / 金口 / 三式合一 计算后端 | 统一走 `ken`（`kinqimen` / `kintaiyi` / `kinjinkou`），盘面与星阙桌面端同源 |
| 统摄法 / 十年大运 | headless 实现与星阙逐值对齐（京房八宫五行；`Math.round` / `Math.ceil` 一致；对照星阙 `decennials.test.js` 金标） |
| 未确认参数时强制追问 | `32` 个技法工具触发 `must_ask_user=true` |
| 安全豁免工具 | `7` 个 registry / knowledge / parser 类工具直接可读 |
| 全工具调用 | `42 / 42 ok=true` |
| 本地 memory 写入 | `42 / 42` |
| memory query / show | `42 / 42` |
| report JSON artifact | `42 / 42` |
| 星阙式导出结构 | 业务技法均带 `export_snapshot` / `export_format` |
| 工程测试 | `164 / 164 pass`（含 ken 后端实时集成测试） |
| GitHub CI | Linux/macOS 单测 + Windows OpenClaw smoke 通过 |
| Release runtime | macOS / Windows `v0.7.0` assets（含 ken 引擎）已打包并校验 |

关于 `solarreturn`、`lunarreturn`、`solararc`、`givenyear`、`profection`、`pd`、`pdchart`、`zr` 这批推运工具：当前版本已经复核为可用，不应再被 agent 标记为“Java `/predict/*` 不可用”。如果某个客户端仍然这样回答，优先检查它是否在使用旧 runtime、是否绕过 MCP 直接手算、是否没有运行 `doctor` / `openclaw-check --full`。

更重要的是：这些工具现在有明确输入契约。返照/推运类不是只给本命资料就能严肃调用，必须同时确认目标时间、目标地点/时区或主限方法。完整字段表见 [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md)，CLI 和 MCP 也会通过 `tool list`、`horosa_agent_guidance`、tool docstring 暴露同一份 contract。

完整本地输入输出审计产物示例：

- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs_full.json`
- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs.jsonl`
- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs_summary.md`
- `HOROSA_IO_AUDIT_*/predictive_tools_full_export_sections.md`

这些文件不会自动提交进 Git；它们用于你在本机复核每个工具的输入、输出、memory、report 和 preflight 行为。

审计推运类工具时不要只看短预览。`solarreturn`、`lunarreturn`、`solararc`、`givenyear`、`profection`、`pd`、`pdchart`、`zr` 等工具的星阙式正文通常先写本命盘，再写返照盘、推运盘、流年盘或主限表格；如果只截取前 1200 字，可能只看到本命盘。正确做法是打开完整 artifact，按 `export_format.sections` 或 `predictive_tools_full_export_sections.md` 检查每个 section。详细说明见 [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md)。

## Agent 硬性调用规则

这是接入 Cursor、OpenClaw、Claude、Codex、Open WebUI 时最重要的规则。

Agent 在调用技法前如果不确定用户设置，应先查：

```bash
uv run horosa-skill agent guidance --tool liureng_gods --intent "当前时间起大六壬"
```

同名 MCP 工具是 `horosa_agent_guidance`，用于告诉 AI 哪些字段必须先问用户、哪些星阙默认值可以在用户接受后使用。

计算工具和 `horosa_dispatch` 现在有硬性门禁：Agent 没有先确认设置时会收到 `agent_guidance.required`，需要在用户确认后传入 `agent_confirmed_settings: true`，或在用户明确接受默认值后传入 `defaults_accepted: true`。如果返回里有 `details.agent_recovery.prompt_to_user`，AI 客户端必须停止调用并把这段问题发给用户确认，不能绕过或自行补参。

标准流程：

1. 用户说出需求，例如“帮我用当前时间起一个大六壬盘”。
2. Agent 先判断参数是否足够；不够就调用 `horosa_agent_guidance` 或直接询问用户。
3. 用户明确回答时间、地点、事项、默认值是否接受。
4. Agent 再调用真实技法工具，并传入 `agent_confirmed_settings: true` 与 `clarification_notes`。
5. 工具返回结果后，Agent 用 `export_snapshot` / `export_format` 做解释，而不是自己手算。

错误示例：

```json
{
  "date": "2026-05-18",
  "time": "13:14:00"
}
```

这会被拦截，因为缺少用户确认、地点、时区、事项等关键上下文。

正确示例：

```json
{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：用 2026-05-18 13:14:00，America/Los_Angeles，旧金山，事项为当前工作决策。",
  "date": "2026-05-18",
  "time": "13:14:00",
  "zone": "-07:00",
  "lat": "37n46",
  "lon": "122w25",
  "gpsLat": 37.7667,
  "gpsLon": -122.4167,
  "after23NewDay": false
}
```

如果用户说“按星阙默认继续”，可以改用：

```json
{
  "defaults_accepted": true,
  "clarification_notes": "用户明确接受星阙默认设置。"
}
```

但 agent 不能替用户擅自写 `defaults_accepted: true`。

## 项目定位

星阙本身已经有完整的本地算法、星历、导出设置和多技法体系。`Horosa Skill` 做的不是“再造一个简化版占算器”，而是把这些能力整理成一个适合 GitHub 分发、适合 AI 调用、适合长期本地管理的产品化接口层。

这个仓库现在按 `GNU AGPL-3.0-only` 公开发布。根目录 [LICENSE](./LICENSE) 是整个仓库的对外许可证文本；子项目 `horosa-skill/` 里的 Python / JS 包元数据也会同步声明同一许可证，方便包管理器和 MCP 生态读取。

它解决的是五件事：

- 让用户从 GitHub 直接获取项目，并通过 GitHub Releases 安装完整离线 runtime。
- 让 AI 通过 `MCP` 或 `JSON-first CLI` 调用真正的星阙方法，而不是调用一层松散 prompt。
- 让每个技法的输出都变成高机器可读、稳定 section 化的“星阙 AI 导出完全体”文档。
- 让每次工具调用、用户问题、AI 最终回答、结构化摘要都落到本地，可回看、可检索、可复用。
- 让仓库保持轻量、清晰、可维护，而不是把大体积 runtime 和开发缓存全部塞进 Git 历史。

如果你的目标是：

- “别人 clone 这个仓库后，就能让自己的 AI 在本机直接调用星阙”
- “调用结果不是杂乱文本，而是稳定 JSON + 星阙式导出快照”
- “每次问卜、起盘、推运都能自动写成本地知识记录”

这个仓库就是围绕这个目标设计的。

## 致谢：内置的开源术数引擎（ken）

奇门遁甲 / 太乙神数 / 金口诀（以及三式合一中的奇门 + 太乙）的盘面，由 **[kentang2017](https://github.com/kentang2017)** 开源的三个 Python 引擎计算。星阙在后端接入了这套引擎，Horosa Skill 复用同一计算路径并将其随离线 runtime 一起分发。在此向作者致谢：

- **kinqimen**（奇门遁甲）— MIT License — <https://github.com/kentang2017/kinqimen>
- **kintaiyi**（太乙神数）— MIT License — <https://github.com/kentang2017/kintaiyi>
- **kinjinkou**（金口诀）— MIT License — <https://github.com/kentang2017/kinjinkou>

这三个引擎依据其各自的 MIT 许可证使用；完整的版权声明与许可证文本随离线 runtime 一并打包在 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE`，分发时一并保留。

许可证归属说明：上面三个 `ken` 引擎是**第三方 MIT** 组件（作者 kentang2017）。本仓库其余的术数实现——统摄法（`tongshefa.js`）、十年大运（`engine/decennials.py`）、以及奇门/太乙/金口/大六壬/星盘等的 `aiExport.js` 格式化与 headless 适配——均为**星阙自有算法**，按本仓库根目录的 `GNU AGPL-3.0-only` 授权；其中统摄法与十年大运是星阙前端引擎（`astrostudyui`）的 headless 移植，已与星阙逐值对齐（京房八宫五行 / `Math.round` 等）。传统术数体系本身（京房八宫、希腊十年星限等）属公共知识，不构成第三方版权。

## 现在它已经能做什么

### 一句话能力总览

| 能力层 | 当前已经实现的内容 | 对使用者意味着什么 |
| --- | --- | --- |
| 离线 runtime | 通过 GitHub Releases 安装 macOS / Windows 完整 runtime | 安装后可断网运行，不依赖远程算法服务 |
| AI 调用接口 | `MCP server` + `JSON-first CLI` + `ask / dispatch` | Claude、Codex、Open WebUI、OpenClaw 都能接 |
| 技法执行 | `42` 个可调用工具，覆盖星盘、推运、术数、导出协议与悬浮知识读取 | 不是 demo，而是可直接使用的多技法本地能力面 |
| 输出协议 | 每个技法返回统一 envelope，并附带 `export_snapshot` / `export_format` | 机器和人都能稳定消费，不需要猜字段 |
| 知识读取 | 内置星阙 hover 知识 bundle，可按需读取星盘 / 六壬 / 奇门悬浮内容 | 不只是算，还能把“解释层”交给 AI 随时调用 |
| 数据管理 | SQLite + JSON artifacts + run manifest + AI answer write-back | 一次调用就是一条可追溯记录 |
| 观测与排障 | 本地 JSONL trace、`trace_id/group_id`、artifact/run 对齐 | 能定位“哪次调度、哪个工具、哪条记录”出了问题 |
| 评测体系 | `run_full_self_check` + `HorosaBench` benchmark | 不只是“能跑”，而是能持续验证选工具、导出和知识质量 |
| 发布策略 | 轻仓库 + 重 Release | GitHub 页面专业、清楚，不拖慢协作 |

### 功能卖点

- 真离线：算法、星历、导出协议、知识读取都在本机完成，不依赖云端算命 API。
- 真 AI 接口：不是 prompt 拼接，而是明确 schema、明确工具、明确结构化输出。
- 真长期可管：每次调用都会留下 run 记录、artifact、manifest、AI 最终回答。
- 真星阙一致性：输出不是随意摘要，而是按星阙 app 的 AI 导出完全体和 hover 文档风格清洗。
- 真 GitHub-first：公开仓库保持清爽，runtime 放 Releases，用户体验接近成熟产品仓库。

### 当前可直接调用的技法与工具

#### 导出协议、调度与知识层

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `export_registry` | 星阙 AI 导出协议注册表 | 返回所有 technique、section、设置项、可选导出块的机器可读总表 |
| `export_parse` | 星阙 AI 导出正文解析器 | 把星阙风格导出文本重新解析成稳定 JSON 分段 |
| `horosa_dispatch` | 总调度器 | 接收自然语言意图并自动分派到对应技法 |
| `knowledge_registry` | 悬浮知识目录 | 列出当前内置的星盘 / 六壬 / 奇门知识域与可读 key |
| `knowledge_read` | 悬浮知识读取器 | 读取星阙 app 悬浮窗口中的完整说明文档并落库 |

#### 核心星盘与派生星盘

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `chart` | 标准星盘 | 生成基础西洋星盘与完整 AI 导出正文 |
| `chart13` | 13 宫扩展盘 | 生成 `chart13` 形态的星盘输出 |
| `hellen_chart` | 希腊星盘 | 生成希腊占星取向的星盘导出 |
| `guolao_chart` | 七政四余盘 | 生成七政四余 / 果老法盘面 |
| `india_chart` | 印度盘 | 生成印度占星盘面 |
| `relative` | 合盘 / 关系盘 | 生成双人关系、合盘、relative 输出 |
| `germany` | 量化盘 / 中点盘 | 生成中点结构与量化分析输出 |

#### 推运、返照与时运系统

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `solarreturn` | 太阳返照 | 计算太阳返照盘 |
| `lunarreturn` | 月亮返照 | 计算月返盘 |
| `solararc` | 太阳弧推运 | 计算太阳弧推运结果 |
| `givenyear` | 指定年推运 | 按指定年份生成推运输出 |
| `profection` | 小限 / 年运推限 | 计算 profection |
| `pd` | 本初方向 / 主限 | 计算 primary directions |
| `pdchart` | 主限盘 | 生成可读的主限盘面 |
| `zr` | 黄道释放 | 计算 zodiacal release |
| `firdaria` | 法达星限 | 生成法达星限结构与时间轴 |
| `decennials` | 十年大运 / 十年星限 | 生成 decennials 时间分层输出 |

推运类工具的关键输入和正确输出不能省略：

| 工具 | 调用前必须确认 | 输出必须包含 |
| --- | --- | --- |
| `solarreturn` / `lunarreturn` | 本命资料 + 返照目标时间 `datetime` + 返照地点/时区 `dirLat` / `dirLon` / `dirZone` | 本命盘 + 返照盘 + 返照盘相位 |
| `givenyear` | 本命资料 + 指定年/目标时间 `datetime` + 流年地点/时区 `dir*` | 本命盘 + 流年盘 + 流年盘相位 |
| `solararc` / `profection` | 本命资料 + 推运目标时间 `datetime` + `dirZone` | 本命盘 + 推运盘 + 推运盘相位 |
| `pd` | 本命资料 + `pdtype` + `pdMethod` + `pdTimeKey` + `pdaspects` | 主限设置 + 真实主限表格 |
| `pdchart` | 本命资料 + 目标时间 `datetime` + `dirZone` + 主限方法字段 | 本命盘 + 主限法盘星体表格 + 主限相位 |
| `zr` / `firdaria` / `decennials` | 本命资料 + 是否接受星阙默认时间轴设置 | 对应时间轴/层级表 |

如果这些字段不完整，Agent 应先追问用户，或调用 `horosa_agent_guidance` 获取可直接转发的追问文本，不能自行补参。

#### 中文术数主干

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `ziwei_birth` | 紫微斗数命盘 | 生成紫微命盘 |
| `ziwei_rules` | 紫微规则库 | 返回紫微规则与结构信息 |
| `bazi_birth` | 八字命盘 | 生成四柱八字命盘 |
| `bazi_direct` | 八字直断 | 生成八字直断输出 |
| `liureng_gods` | 大六壬起课 | 生成大六壬四课三传与神煞结构 |
| `liureng_runyear` | 大六壬行年 | 生成六壬行年 / 年运输出 |
| `qimen` | 奇门遁甲 | 由 ken（`kinqimen`）起盘，生成奇门盘、宫位细节与演卦 |
| `taiyi` | 太乙神数 | 由 ken（`kintaiyi`）起盘，生成太乙盘与十六宫标记 |
| `jinkou` | 金口诀 | 由 ken（`kinjinkou`）起盘，生成金口诀盘面与速览结果 |

#### Phase 2 本地技法

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `tongshefa` | 统摄法 | 生成统摄法卦象、六爻、潜藏、亲和关系 |
| `canping` | 邵子参评数 / 金锁银匙 | 四柱起数、年纳音定部、本命 / 大运歲運条文（本地 in-process，依赖打包的 `lunar-javascript`） |
| `heluo` | 河洛理数 | 天地数起先天 / 后天卦与元堂、命运篇、大限·岁运（含元堂爻辞；本地 in-process） |
| `harmonic` | 调波盘 | 本命黄经×调波数取调波位置、同频合相（后端 `/astroextra/harmonic`） |
| `sanshiunited` | 三式合一 | 聚合 ken 的奇门 + 太乙与大六壬并统一导出 |
| `suzhan` | 宿占 / 宿盘 | 生成宿占结构与宿曜信息 |
| `sixyao` | 六爻 / 易卦 | 生成本卦、之卦、爻变、问题导向输出 |
| `otherbu` | 西洋游戏 / 占星骰子 | 生成星骰与对应解读结构 |

#### 节气、农历与卦义辅助

| 工具 ID | 中文名称 | 作用 |
| --- | --- | --- |
| `jieqi_year` | 全年节气盘 | 生成全年节气节点与节气相关结构 |
| `nongli_time` | 农历换算 | 生成农历时间、干支等基础信息 |
| `gua_desc` | 卦义说明 | 查询卦名与卦辞等基础释义 |
| `gua_meiyi` | 梅易卦义 | 查询梅花易数取向的卦义说明 |

### 已完成机器建模的星阙 AI 导出协议

除了“能算”，这个仓库还把星阙的 AI 导出协议整理成机器可读的 registry surface。下面这些 `technique` 域都已经建模，并能被导出 / 解析 / 回放：

| technique ID | 中文对应 | 说明 |
| --- | --- | --- |
| `astrochart` | 标准星盘导出 | 标准西占星盘完整导出 |
| `astrochart_like` | 类星盘导出 | 与标准星盘接近的盘型 |
| `indiachart` | 印度盘导出 | 印占相关盘型 |
| `relative` | 合盘导出 | 关系盘 / 双人盘 |
| `primarydirect` | 主限导出 | primary directions 结果 |
| `primarydirchart` | 主限盘导出 | 主限盘视图 |
| `zodialrelease` | 黄道释放导出 | zodiacal release |
| `firdaria` | 法达星限导出 | 法达时间轴 |
| `decennials` | 十年星限导出 | decennials 时间层级 |
| `solarreturn` | 太阳返照导出 | solar return |
| `lunarreturn` | 月返导出 | lunar return |
| `solararc` | 太阳弧导出 | solar arc 推运 |
| `givenyear` | 指定年导出 | 指定年份分析 |
| `profection` | 小限导出 | profection |
| `bazi` | 八字导出 | 四柱八字相关输出 |
| `ziwei` | 紫微导出 | 紫微斗数相关输出 |
| `suzhan` | 宿占导出 | 宿盘 / 宿曜结构 |
| `sixyao` | 六爻导出 | 易卦 / 六爻输出 |
| `tongshefa` | 统摄法导出 | 统摄法结构 |
| `canping` | 邵子参评数导出 | 起盘、本命、大运（歲運条文） |
| `heluo` | 河洛理数导出 | 起命、先天卦、后天卦、命运篇、大限 |
| `liureng` | 大六壬导出 | 四课、三传、神煞、大格、小局 |
| `jinkou` | 金口诀导出 | 金口诀结构化正文 |
| `qimen` | 奇门导出 | 奇门盘型、八宫、九宫方盘、演卦 |
| `taiyi` | 太乙导出 | 太乙盘与宫位标记 |
| `sanshiunited` | 三式合一导出 | 三式聚合结果 |
| `guolao` | 七政四余导出 | 七政四余盘 |
| `germany` | 量化盘导出 | 中点与量化分析 |
| `jieqi` | 节气主导出 | 节气盘主结构 |
| `jieqi_meta` | 节气元信息导出 | 节气基础元数据 |
| `jieqi_chunfen` | 春分导出 | 春分节气域 |
| `jieqi_xiazhi` | 夏至导出 | 夏至节气域 |
| `jieqi_qiufen` | 秋分导出 | 秋分节气域 |
| `jieqi_dongzhi` | 冬至导出 | 冬至节气域 |
| `otherbu` | 占星骰子导出 | 西洋游戏 / 骰子输出 |
| `generic` | 通用导出 | 农历时间等通用型结果 |

### 明确排除项

- `fengshui`

## 星阙悬浮知识库也已经接进来了

现在这个仓库不只会“算”，也能在需要的时候直接读取星阙 app 里的 hover / popover 知识内容，而且这些内容已经打包进 repo 内的本地 bundle，不再依赖原 app 源目录。

当前已接入：

- 星盘悬浮：`planet`、`sign`、`house`、`lot`、`aspect`
- 大六壬悬浮：`shen`、`house`
- 奇门遁甲悬浮：`stem`、`door`、`star`、`god`

这意味着 AI 或用户现在可以在想看的时候直接调：

- 星盘里行星、星座、宫位、相位、lots 的完整 hover 文本
- 大六壬里地支神与将盘组合的 hover 文本
- 奇门里天干、八门、九星、八神的 hover 文本

而且这些读取结果也会和别的工具一样被落库、检索、回看。

## 对 AI 来说，这个仓库最重要的不是“算”，而是“稳定可消费”

每个工具调用最终都会返回统一 envelope：

```json
{
  "ok": true,
  "tool": "qimen",
  "version": "0.7.0",
  "input_normalized": {},
  "data": {},
  "summary": [],
  "warnings": [],
  "memory_ref": {},
  "error": null
}
```

对于已经接入星阙导出协议的技法，还会额外带：

- `data.export_snapshot`
- `data.export_format`
- `data.export_snapshot.snapshot_text`
- `data.export_snapshot.sections`
- `data.export_snapshot.selected_sections`

这意味着：

- AI 不需要自己从自由文本里乱猜结构。
- 同一个技法连续多次调用，都会得到同一套格式化 contract。
- `horosa_dispatch` 的汇总层也显式带每个子结果的 export contract。
- 最终落库到 JSON artifact 后，结构不会丢失。

## 数据管理已经不是“把结果存一下”，而是完整本地记录系统

本地数据默认写到：

- macOS / Linux：`~/.horosa-skill/`
- Windows：`%APPDATA%/HorosaSkill/`

每一次 run 会沉淀这些内容：

- run 元信息
- tool call 记录
- entity 索引
- JSON artifact
- `run manifest`
- 原始 `query_text`
- 用户问题 `user_question`
- AI 最终回答 `ai_answer_text`
- 可选结构化回答 `ai_answer_structured`

现在支持的典型管理动作：

- `memory query`
  按 tool、entity、run_id 查询历史记录
- `memory show <run_id>`
  精确回看某一次完整调用
- `memory answer --stdin`
  把 AI 最终回答回写到已有记录

这让它不只是“工具层”，而是“工具层 + 可追溯知识库”。

## 快速开始

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
uv run horosa-skill serve
```

默认 MCP 地址：

```text
http://127.0.0.1:8765/mcp
```

如果你要给 Claude Desktop 这类 stdio 客户端使用：

```bash
cd horosa-skill
uv run horosa-skill serve --transport stdio
```

## 最短可用路径

### 1. 安装并验证离线 runtime

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
```

如果你主要是接 OpenClaw / mcporter，现在可以直接生成当前仓库绝对路径版配置：

```bash
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

`openclaw-setup` 会同时写两份配置：

- `~/.openclaw/workspace/config/mcporter.json`：用于 `openclaw-check` / mcporter smoke。
- `~/.openclaw/openclaw.json` 的 `mcp.servers.horosa`：用于 OpenClaw agent 原生挂载 `horosa_*` MCP tools。

如果 `openclaw-check` 通过、`openclaw mcp list` 能看到 `horosa`、或真实会话里已经出现 `horosa__...` 工具，但 agent trace 里还是 `clientToolCount: 0`，这个字段只能视为旧 trajectory 统计噪音，不能当成“Horosa 未挂载”的依据。请重启 OpenClaw 或开启新的 agent session；不要让 agent 退回 Shell / Python 手算。

如果 agent 用过少参数直接试跑奇门 / 太乙 / 六爻，导致 `/nongli/time` 返回 `200001 param error`，先让 agent 通过 `horosa_agent_guidance` 补问日期、时间、时区、经纬度与默认设置；Horosa Skill 也会自动对 Java 日期接口重试星阙兼容格式，避免把后端格式错误误判为算法不可用。

时区既可以传 `+08:00` / `-07:00` 这样的固定 offset，也可以传 `America/Los_Angeles`、`Asia/Shanghai` 这样的 IANA 名称。Horosa Skill 会按起盘日期和时间先转换成后端稳定接受的 offset，例如 `2026-05-18 13:14 America/Los_Angeles` 会进入后端前归一化为 `-07:00`。

### 2. 让调度器自动选技法

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：使用示例出生资料，地点上海，时区 +08:00，按星阙默认技法参数。",
  "query":"请综合奇门、六壬和星盘分析当前状态",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### 3. 回看某一条完整记录

```bash
uv run horosa-skill memory show <run_id>
```

### 4. 把 AI 最终回答写回这条记录

```bash
echo '{
  "run_id":"<run_id>",
  "user_question":"我接下来事业走势如何？",
  "ai_answer":"先稳后升，宜先整理资源再扩张。",
  "ai_answer_structured":{"trend":"up_later"}
}' | uv run horosa-skill memory answer --stdin
```

## 典型调用方式

### 查看完整导出 registry

```bash
cd horosa-skill
uv run horosa-skill export registry
```

### 把星阙导出正文解析成结构化 JSON

```bash
echo '{
  "technique":"qimen",
  "content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容\n\n[演卦]\n演卦内容"
}' | uv run horosa-skill export parse --stdin
```

### 直接调用某个工具

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：示例星盘使用上海、+08:00、整宫/回归黄道等星阙默认设置。",
  "date":"1990-01-01",
  "time":"12:00",
  "zone":"+08:00",
  "lat":"31n14",
  "lon":"121e28",
  "gpsLat":31.2333,
  "gpsLon":121.4667
}' \
  | uv run horosa-skill tool run chart --stdin
```

### 直接读取星阙悬浮知识

```bash
echo '{"domain":"astro","category":"planet","key":"Sun"}' \
  | uv run horosa-skill knowledge read --stdin
```

```bash
echo '{"domain":"liureng","category":"shen","key":"子"}' \
  | uv run horosa-skill knowledge read --stdin
```

```bash
echo '{"domain":"qimen","category":"door","key":"休门"}' \
  | uv run horosa-skill knowledge read --stdin
```

### 直接运行 Phase 2 本地技法

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：统摄法四象参数由用户指定。",
  "taiyin":"巽",
  "taiyang":"坤",
  "shaoyang":"震",
  "shaoyin":"震"
}' \
  | uv run horosa-skill tool run tongshefa --stdin
```

### 运行统一调度器

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：使用示例出生资料，按星阙默认调度设置综合奇门、六壬和星盘。",
  "query":"请综合奇门、六壬和星盘做当前状态分析",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill dispatch --stdin
```

## 当前支持的 AI 客户端

- [Claude Desktop 配置示例](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex 配置示例](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI 接入说明](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw 接入说明](./horosa-skill/examples/clients/openclaw-mcp.md)

对 OpenClaw / mcporter，推荐优先使用下面这条生成器命令，减少手改 JSON 和路径出错：

```bash
cd horosa-skill
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
```

## Release 与 runtime 策略

这个仓库故意拆成三层：

| 层 | 放在哪里 | 作用 |
| --- | --- | --- |
| 公开仓库层 | GitHub repo | 代码、文档、CLI、MCP、测试、示例、打包脚本 |
| 维护者本地打包输入层 | `vendor/runtime-source/` | 构建离线 runtime release 所需的大体积输入 |
| 最终用户运行层 | `~/.horosa/runtime/current` 或 `%LOCALAPPDATA%/Horosa/runtime/current` | 用户安装后真实执行算法的本地 runtime |

这样可以同时满足：

- GitHub 页面足够干净
- Release 资产足够完整
- 本地运行足够离线
- 维护者打包流程不依赖外部兄弟目录

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | 核心 Python 包、CLI、MCP server、tests、examples、release scripts |
| [`docs/`](./docs) | runtime 规范、算法覆盖矩阵、Release 文档、维护文档 |
| [`vendor/`](./vendor) | 本地 runtime 打包输入区 |

建议顺手看的文档：

- [Repo Layout](./docs/REPO_LAYOUT.md)
- [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md)
- [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md)
- [Algorithm Coverage](./docs/ALGORITHM_COVERAGE.md)
- [Vendored Runtime Sources](./vendor/README.md)

## 当前状态

已完成：

- GitHub-first 离线 runtime 安装链
- 奇门 / 太乙 / 金口 / 三式合一统一走星阙 `ken` 后端（`kinqimen` / `kintaiyi` / `kinjinkou`），盘面与星阙桌面端同源
- macOS / Windows `v0.7.0` runtime release 资产（已随包内置 ken 引擎）
- 本地 MCP server 与 JSON-first CLI
- 完整星阙 AI 导出 registry 与 parser
- 42 个可调用工具的结构化稳定输出
- 32 个需确认设置的技法工具强制 agent 追问用户
- 7 个安全读取类工具明确豁免 preflight
- 星盘 / 六壬 / 奇门悬浮知识库的本地 bundle 化与按需读取
- `dispatch` 汇总层 export contract
- SQLite + JSON artifact + run manifest 数据管理
- AI answer 回写与检索链路
- 从 GitHub fresh clone / GitHub Release 重新安装 runtime 的实测闭环
- GitHub CI 中的 Windows OpenClaw smoke 验证

如果你需要的是一个“把星阙变成 AI 可调用基础设施”的仓库，而不是一堆分散脚本，这个 repo 现在已经是按这个方向搭好的。

## 快速验真清单

如果你想在第一次 clone 之后快速确认“这不是空壳仓库”，可以直接按这组最小检查走：

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
uv run pytest -q
uv run python scripts/run_benchmark.py
uv run python scripts/run_full_self_check.py --rounds 1
```

你应该重点看这几类信号：

- `doctor` 能确认 runtime 已安装，并在服务启动后给出 `issues: []`
- `pytest` 能通过当前工程测试
- `HorosaBench` 能验证调度、导出 parity、知识读取
- `run_full_self_check` 能验证全部工具的调用、导出、落库、检索和 dispatch 汇总层

如果你是第一次评估这个仓库，这组命令比“随便跑一个 tool”更能说明项目是否真的完整。

## Release 完整性与 provenance

这个仓库现在不只是“能打包 runtime”，还补上了可验证的 release 侧元数据与追溯链：

- 运行时资产来自 GitHub Releases，而不是直接塞进 Git 历史
- 仓库提供 `server.json`，方便 MCP 生态识别与收录
- 仓库提供 SBOM 生成脚本，用于导出依赖与 runtime manifest 的机器可读清单
- trace、artifact、run manifest、knowledge bundle、export snapshot 都已经带版本或 provenance 信息
- release / benchmark / self-check / README / `server.json` 都已经进入工程校验链

建议配套阅读：

- 运维说明：[`docs/OPERATIONS.md`](./docs/OPERATIONS.md)
- 评测体系：[`docs/EVALUATION.md`](./docs/EVALUATION.md)
- 数据契约：[`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md)
- MCP 元数据：[`server.json`](./server.json)

## MCP / AI 客户端接入建议

如果你是把 Horosa Skill 接给 AI，而不是把它当成普通 CLI 工具，推荐按这个顺序来理解：

1. 先 `install + doctor`
2. 再用 `stdio MCP` 接 Claude、Codex、Open WebUI、OpenClaw
3. 如果某个客户端只能吃 HTTP / OpenAPI，再加一层 bridge

推荐这样分工：

- `horosa_dispatch`：自然语言入口
- 原子 `tool run`：确定性脚本与调试
- `knowledge_read`：读取星阙悬浮知识
- `memory answer`：把 AI 最终回答回写到同一次记录

也就是说，这个仓库同时提供：

- 算法层
- 导出层
- 知识层
- 调度层
- 记录层
- 观测层

## 输出是否和星阙一致

当前 README 里的“星阙一致”指两层含义：

1. **导出结构一致**：业务技法输出会生成星阙式 `export_snapshot.export_text`，再由 `snapshot_parser` 解析成 `export_format`。完整自检会逐项确认 selected sections 没有缺失、没有未知 section。
2. **算法路径一致**：Skill 不允许 agent 自己用 shell、Python 小脚本或联网搜索手算玄学盘。大六壬、奇门、三式合一、星盘等都必须走 Horosa Skill 本地 runtime / headless engine。其中奇门、太乙、金口诀（以及三式合一里的奇门 + 太乙）由星阙的 `ken` 后端（`kinqimen` / `kintaiyi` / `kinjinkou`）独占计算，与星阙桌面端同源，JS 层只负责把 ken 结果重排成 `aiExport.js` 的 section。

实测信号：

```text
tool_count: 42
failed_tools: []
missing_export_contract_tools: []
ok: true
```

需要注意：如果要证明某个具体输入和当前星阙桌面 UI 的每一个字段逐值一致，应该把星阙 app 对同一输入导出的 golden snapshot 放进 fixtures，再做逐字段 diff。当前仓库已经保证 Skill 侧所有业务技法都产出星阙式 AI 导出结构，并且可以被同一 parser 稳定回读。

## 实测与审计

本仓库推荐用三类验证来判断它是否可靠，而不是只看单次输出：

```bash
cd horosa-skill
uv run pytest -q
uv run python scripts/run_full_self_check.py --rounds 1
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace --full
```

完整自检覆盖：

- 每个工具是否能调用
- 每个工具是否能输出统一 envelope
- 每个业务技法是否带 `export_snapshot` / `export_format`
- 每个导出正文是否能重新解析
- 每次 run 是否写入 memory
- `memory show/query` 是否能找回
- report JSON / DOCX / PDF 是否能生成并登记 artifact
- `horosa_dispatch` 汇总层是否保留子工具 export contract
- OpenClaw / mcporter 是否能看到 MCP 工具并完成 smoke/full check

如果你需要把所有输入输出都保存成审计文件，可以用项目现有 testing payloads 自行跑一轮记录。最近一次本机审计结果为：

```json
{
  "version": "0.7.0",
  "tool_count": 42,
  "records_count": 42,
  "errors_count": 0,
  "preflight_blocked_count": 32,
  "preflight_exempt_ok_count": 7,
  "all_outputs_ok": true,
  "all_memory_saved": true,
  "all_reports_generated": true
}
```

推运类工具的审计需要额外看完整 section，而不是只看正文前缀。完整推运 section 检查会确认：

- `solarreturn` / `lunarreturn` 包含本命盘、返照盘和返照盘相位。
- `givenyear` 包含本命盘、流年盘和流年盘相位。
- `solararc` / `profection` 包含本命盘、推运盘和推运盘相位。
- `pd` / `pdchart` 包含真实主限表格、主限法盘表格、相位和说明。
- `zr` / `firdaria` / `decennials` 包含对应时间轴或表格。

参见 [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md)。

## 这套仓库当前最适合谁

它最适合四类人：

- 普通使用者：想让自己的 AI 在本机直接调用星阙方法
- 高级用户：想把每次分析沉淀成可检索本地记录
- 维护者：想要一个轻仓库 + 重 release 的长期发布结构
- 研究者：想研究 tool routing、导出协议、知识读取与 process-level evaluation

如果你是研究导向用户，最值得继续看的入口是：

- [`docs/EVALUATION.md`](./docs/EVALUATION.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md)

## FAQ / 边界说明

### 为什么 release workflow 不是完全 GitHub-hosted 的纯云构建？

因为这个项目的完整 runtime 依赖本地维护的 runtime source、平台运行时和打包资产。仓库保持轻量是目标，但完整 runtime 仍需要可靠的本地打包输入，所以 release 侧采用“轻仓库 + 重 release + 明确校验”的策略。

### 为什么 README 一直强调 `export_snapshot` 和 `export_format`？

因为这个项目最核心的价值之一就是“让 AI 稳定消费星阙输出”。如果没有这层 contract，AI 只能读松散文本，后续检索、比对、回写、研究评测都会变脆。

### 为什么同时保留 SQLite 和 JSON？

因为两者职责不同：

- SQLite 负责结构化索引与查询
- JSON artifact 负责长期归档、可携带、可 diff、可审阅

### 为什么 `fengshui` 还没有进当前发布面？

因为当前目标是“已经完整、已经 headless、已经可离线验证”的能力面。`fengshui` 目前仍明确排除，不把未完成 headless 化的能力伪装成可发布功能。

### 这个仓库最重要的质量信号是什么？

不是 badge，也不是截图，而是这四件事能不能同时成立：

- tool 真能调用
- 导出真是稳定结构化
- 结果真会落库和回写
- benchmark / self-check 真能持续跑通
