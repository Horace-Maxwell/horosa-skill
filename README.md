**简体中文** | [English](./README_EN.md)

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>把星阙 / Horosa 变成任何 AI 都能本地调用的离线玄学能力层。</strong></p>
  <p>克隆仓库、安装一次离线 runtime，就能让 Claude、Codex、Open WebUI、OpenClaw 等 AI 在你自己的机器上直接调用 <strong>68 个</strong>真实技法——西洋本命 / 推运 / 卜卦 / 择日、八字 / 紫微 / 大六壬 / 三式合一、以及 <strong>全 14 路神数</strong>——读取完整的星阙式 AI 导出协议，输出稳定结构化结果，并把每次分析沉淀为可检索的本地记录。断网可用，与星阙桌面端逐值同源。</p>

  <p><a href="https://github.com/Horace-Maxwell/horosa-skill"><img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" /></a>&nbsp;<a href="https://github.com/Horace-Maxwell/horosa-skill/releases"><img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" /></a>&nbsp;<a href="./README_EN.md"><img src="https://img.shields.io/badge/Read%20in-English-0f766e?style=for-the-badge" alt="Read in English" /></a></p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=flat-square" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=flat-square" alt="Release" />
    <img src="https://img.shields.io/badge/tools-68-1d4ed8?style=flat-square" alt="68 tools" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=flat-square" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=flat-square" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=flat-square" alt="SQLite and JSON" />
  </p>

  <p><a href="./LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square" alt="License" /></a>&nbsp;<a href="./CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square" alt="Contributing" /></a>&nbsp;<a href="./SECURITY.md"><img src="https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square" alt="Security" /></a>&nbsp;<a href="./SUPPORT.md"><img src="https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square" alt="Support" /></a>&nbsp;<a href="./CITATION.cff"><img src="https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square" alt="Citation" /></a>&nbsp;<a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/Changelog-Updates-f59e0b?style=flat-square" alt="Changelog" /></a></p>
</div>

---

## 一句话

星阙本身已经有完整的本地算法、星历、导出设置和多技法体系。**Horosa Skill 不是再造一个简化占算器**，而是把这些能力整理成一个适合 GitHub 分发、适合 AI 调用、适合长期本地管理的产品化接口层：算法在本机跑、输出是稳定 JSON + 星阙式导出快照、每次调用都自动写成可检索的本地知识记录。

它解决五件事：

- **取得即用** — 从 GitHub clone，再从 GitHub Releases 安装完整离线 runtime，安装后断网运行。
- **真 AI 接口** — 通过 `MCP` 或 `JSON-first CLI` 调用真正的星阙方法，而不是一层松散 prompt。
- **稳定可消费** — 每个技法都输出统一 envelope + 星阙式 `export_snapshot` / `export_format`，机器和人都不用猜字段。
- **长期可管** — 一次调用 = 一条可追溯记录（run / artifact / manifest / AI 最终回答）。
- **轻仓库** — 代码、文档、CLI、MCP、测试进 Git；大体积 runtime 进 Releases。

许可证：仓库以 `GNU AGPL-3.0-only` 公开（根目录 [LICENSE](./LICENSE)）。内置的三个第三方 `ken` 引擎按其各自的 MIT 许可证使用（见[致谢](#致谢内置的开源术数引擎-ken)）。

## 文档入口

| 文档 | 内容 |
| --- | --- |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 架构设计 |
| [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md) | 每个工具的输入契约（必填字段） |
| [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) | 输出 / envelope / export 数据契约 |
| [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md) | 推运类导出的逐 section 审计方法 |
| [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) · [`docs/EVALUATION.md`](./docs/EVALUATION.md) | 运维 · 评测体系 |
| [`docs/OFFLINE_RUNTIME_RELEASES.md`](./docs/OFFLINE_RUNTIME_RELEASES.md) | 离线 runtime 打包与发布 |
| [`server.json`](./server.json) · [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md) · [`AGENTS.md`](./AGENTS.md) | MCP 元数据 · Agent 使用 Skill · Agent 仓库规则 |

## 最新稳定基线

**当前公开版本：`Horosa Skill 0.9.2`（68 个可调用工具）。**

这一条发布线把星阙的能力面补到了与桌面端基本对齐：

- **西洋占星全链路** — 本命与派生盘、10 个经典推运/返照/时运、3 个 v2.4.0 西占（年龄推进点 / 界推运 / 世俗入宫盘）、7 个 v2.5.0 推运（赤纬 / 恒星 / 行星弧 / 行星年龄 / Balbillus / 129年系统 / 波斯向运），外加**卜卦（horary）与择日（election）**两套完整判断引擎。
- **中文术数主干** — 八字、紫微、大六壬、奇门、太乙、金口诀、三式合一、统摄法、河洛理数、邵子参评数、调波盘、宿占、六爻。
- **全 14 路神数** — 5 路标准（皇极经世 / 五兆 / 太玄 / 京氏易 / 神乙数）+ 9 路（邵子 / 铁板 / 分经 / 北极 / 南极 / 淳子 / 演禽 / 策天飞星 / 七政四余·张果）。
- **同源后端** — 奇门 / 太乙 / 金口诀（及三式合一里的奇门 + 太乙）走星阙 `ken` 后端（`kinqimen` / `kintaiyi` / `kinjinkou`）独占计算；14 路神数走星阙 chart 服务上挂载的 kentang 引擎；返回结果由 headless JS 层重排成 `aiExport.js` 的 section 结构。**Skill 与星阙桌面端走同一套后端、逐值同源。**

贯穿始终的硬性协议是「**AI 不能乱补参数**」：只要技法会受时间、地点、时区、性别、事项、宫制、历法、起局方式等设置影响，agent 在用户确认前就不能继续调用——工具会返回结构化阻断结果，并给出可直接转发给用户的追问文本。

本机完整实测信号：

| 检查项 | 结果 |
| --- | --- |
| 可调用工具 | `68 / 68 ok=true` |
| 工程测试 | `227 / 227 pass`（含 ken / 神数 后端实时集成测试 + 离线 golden 单测） |
| 未确认参数时强制追问 | `61` 个技法工具触发 `must_ask_user=true` |
| 安全豁免工具 | `7` 个 registry / knowledge / parser 类工具直接可读 |
| 星阙式导出结构 | 每个业务技法均带 `export_snapshot` / `export_format`（已建模 `63` 个导出 technique） |
| 本地 memory / report | `68 / 68` 写入 + `68 / 68` JSON artifact |
| 奇门 / 太乙 / 金口 / 三式 | 统一走 `ken`，与星阙桌面端同源 |
| 统摄法 / 十年大运 | headless 实现与星阙逐值对齐（京房八宫五行；对照星阙 `decennials.test.js` 金标） |
| GitHub CI | Linux/macOS 单测 + horosa-core-js JS golden 自检 + Windows OpenClaw smoke 通过 |
| Release runtime | macOS / Windows `v0.9.x` assets（含 ken + 14 神数引擎）已打包并校验 |

> 关于 `solarreturn` / `lunarreturn` / `solararc` / `givenyear` / `profection` / `pd` / `pdchart` / `zr` 这批推运工具：当前版本已复核可用，不应再被 agent 标记为「Java `/predict/*` 不可用」。若某客户端仍这样回答，优先检查它是否在用旧 runtime、是否绕过 MCP 手算、是否没跑 `doctor` / `openclaw-check --full`。

## 技法全景（68 个工具）

> 所有业务技法都返回统一 envelope，并附带星阙式 `export_snapshot` / `export_format`。带 ⓟ 的工具是会受设置影响、调用前必须先确认参数的技法。

### 西洋占星 · 本命与派生盘

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `chart` ⓟ | 标准星盘 | 基础西洋星盘 + 完整 AI 导出正文（含 12 分度 / 主宰星链 / 寿命格局） |
| `chart13` ⓟ | 13 宫扩展盘 | `chart13` 形态输出 |
| `hellen_chart` ⓟ | 希腊星盘 | 希腊占星取向盘面 |
| `india_chart` ⓟ | 印度盘 | 印度占星盘面 |
| `guolao_chart` ⓟ | 七政四余盘 | 七政四余 / 果老法盘面 |
| `relative` ⓟ | 合盘 / 关系盘 | 双人关系、合盘、relative 输出 |
| `germany` ⓟ | 量化盘 / 中点盘 | 中点结构与量化分析 |

### 西洋占星 · 推运 / 返照 / 时运（20）

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `solarreturn` ⓟ | 太阳返照 | 本命 + 返照盘 + 相位 |
| `lunarreturn` ⓟ | 月亮返照 | 本命 + 月返盘 + 相位 |
| `solararc` ⓟ | 太阳弧推运 | 本命 + 推运盘 + 相位 |
| `givenyear` ⓟ | 指定年推运 | 本命 + 流年盘 + 相位 |
| `profection` ⓟ | 小限 / 年运推限 | profection 时间层 |
| `pd` ⓟ | 本初方向 / 主限 | primary directions 真实表格 |
| `pdchart` ⓟ | 主限盘 | 可读主限盘面 + 相位 |
| `zr` ⓟ | 黄道释放 | zodiacal release 时间轴 |
| `firdaria` ⓟ | 法达星限 | 法达星限结构与时间轴 |
| `decennials` ⓟ | 十年大运 / 十年星限 | decennials 时间分层（headless，与星阙金标对齐） |
| `agepoint` ⓟ | 年龄推进点 / Huber | Koch 宫 6 年一宫的年龄点周期 |
| `distributions` ⓟ | 界推运 / 分配法 | 上升点行经埃及界的分配主时间轴 |
| `mundane` ⓟ | 世俗入宫盘 | 某年某节气精确入宫时刻的世俗盘 |
| `jaynesprog` ⓟ | 赤纬推运 | Jayne 二次推运 + 赤纬平行 / 反平行 |
| `vedicprog` ⓟ | 恒星推运 | 恒星黄道（sidereal）下的二次推运 |
| `planetaryarc` ⓟ | 行星弧 | 整盘按 arcSource 二次弧方向 |
| `planetaryages` ⓟ | 行星年龄 | 托勒密人生七阶 + 当前主运 |
| `yearsystem129` ⓟ | 129年系统 | 七政各管小年的 129 年一轮 |
| `persiandirected` ⓟ | 波斯向运 | 黄经象征向运（1°/年）应期表 |
| `balbillus` ⓟ | Balbillus 129年 | 旺距削减主限 + 递归子限（JS 逐字 vendor，与星阙一致） |

### 西洋占卜 · 卜卦 / 择日

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `horary` ⓟ | 卜卦（horary） | 根本性 / 征象星（14 类问题）/ 完成分析 / 月亮的故事 / 裁决 / 应期方位 / 描述 |
| `election` ⓟ | 择日（electional） | 红线 / 28 类用事规则包 / 评分定级 / 起盘时刻 / 建议 |

### 中文术数主干

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `bazi_birth` ⓟ / `bazi_direct` ⓟ | 八字命盘 / 八字直断 | 四柱命盘 / 直断输出 |
| `ziwei_birth` ⓟ | 紫微斗数命盘 | 紫微命盘（`ziwei_rules` 返回规则库） |
| `liureng_gods` ⓟ / `liureng_runyear` ⓟ | 大六壬起课 / 行年 | 四课三传神煞 / 行年年运 |
| `qimen` ⓟ | 奇门遁甲 | 由 ken（`kinqimen`）起盘，宫位细节 + 演卦 |
| `taiyi` ⓟ | 太乙神数 | 由 ken（`kintaiyi`）起盘，十六宫标记 |
| `jinkou` ⓟ | 金口诀 | 由 ken（`kinjinkou`）起盘，速览结果 |
| `sanshiunited` ⓟ | 三式合一 | 聚合 ken 的奇门 + 太乙与大六壬并统一导出 |

### 本地术数 · 数算 · 占卜

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `tongshefa` ⓟ | 统摄法 | 卦象、六爻、潜藏、亲和（headless，与星阙逐值对齐） |
| `canping` ⓟ | 邵子参评数 / 金锁银匙 | 四柱起数、年纳音定部、本命 / 大运歲運条文（本地 in-process，依赖打包的 `lunar-javascript`） |
| `heluo` ⓟ | 河洛理数 | 先天 / 后天卦与元堂、命运篇、大限·岁运（含元堂爻辞，本地 in-process） |
| `harmonic` ⓟ | 调波盘 | 本命黄经×调波数取调波位置、同频合相 |
| `suzhan` ⓟ | 宿占 / 宿盘 | 宿占结构与宿曜信息 |
| `sixyao` ⓟ | 六爻 / 易卦 | 本卦、之卦、爻变、问题导向输出 |
| `otherbu` ⓟ | 西洋游戏 / 占星骰子 | 星骰与对应解读结构 |

### 神数（全 14 路）

> kentang 引擎挂在星阙 chart 服务上，后端直出 `snapshot`，段头对齐 aiExport preset。`shaozi` / `tieban` / `cetian` / `qizhengkin` / `xianqin` 另带性别（+地点）。

| 工具 ID | 名称 | 引擎 |
| --- | --- | --- |
| `wangji` ⓟ | 皇极经世·心易发微 | 标准 |
| `wuzhao` ⓟ | 五兆 | 标准 |
| `taixuan` ⓟ | 太玄·揲蓍 | 标准 |
| `jingjue` ⓟ | 京氏易·靖瞶 | 标准 |
| `shenyishu` ⓟ | 神乙数 | 标准 |
| `shaozi` ⓟ | 邵子神数 | kinastro |
| `tieban` ⓟ | 铁板神数 | kinastro |
| `fendjing` ⓟ | 分经神数·两头钳 | kinastro |
| `beiji` ⓟ | 北极神数 | kinastro |
| `nanji` ⓟ | 南极神数 | kinastro |
| `chunzi` ⓟ | 淳子神数 | kinastro |
| `xianqin` ⓟ | 演禽 | kinastro |
| `cetian` ⓟ | 策天飞星·紫微 | kinastro |
| `qizhengkin` ⓟ | 七政四余·张果星宗 | kinastro |

### 节气 / 农历 / 卦义 · 协议 / 调度 / 知识

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `jieqi_year` ⓟ / `nongli_time` ⓟ | 全年节气盘 / 农历换算 | 节气节点 / 农历干支 |
| `gua_desc` / `gua_meiyi` | 卦义说明 / 梅易卦义 | 卦名卦辞 / 梅花易数卦义 |
| `export_registry` / `export_parse` | 导出协议注册表 / 正文解析器 | 机器可读导出总表 / 把星阙式导出文本解析回稳定 JSON |
| `horosa_dispatch` | 总调度器 | 接收自然语言意图并自动分派到对应技法 |
| `knowledge_registry` / `knowledge_read` | 悬浮知识目录 / 读取器 | 列出 / 读取星阙 app 内的 hover 知识并落库 |

> **明确排除项**：`fengshui`（风水尚未完成 headless 化，不把未完成能力伪装成可发布功能）。v0.9.0 曾暂缓的 9 路 kinastro-* 神数已在 v0.9.1 全部补齐。

## Agent 硬性调用规则

这是接入 Cursor、OpenClaw、Claude、Codex、Open WebUI 时**最重要**的规则。

Agent 在调用技法前如果不确定用户设置，应先查 `horosa_agent_guidance`（CLI：`uv run horosa-skill agent guidance --tool <tool> --intent "..."`）——它告诉 AI 哪些字段必须先问用户、哪些星阙默认值可以在用户接受后使用。

计算工具与 `horosa_dispatch` 有硬性门禁：Agent 没先确认设置时会收到 `agent_guidance.required`，需在用户确认后传 `agent_confirmed_settings: true`，或在用户明确接受默认值后传 `defaults_accepted: true`。返回里若有 `details.agent_recovery.prompt_to_user`，AI 客户端必须停止调用并把这段问题发给用户确认，不能绕过或自行补参。

标准流程：①用户说出需求 → ②Agent 判断参数是否足够，不够就调 `horosa_agent_guidance` 或直接询问 → ③用户明确回答时间/地点/事项/是否接受默认 → ④Agent 调真实工具并传 `agent_confirmed_settings: true` + `clarification_notes` → ⑤用 `export_snapshot` / `export_format` 解释，而不是自己手算。

❌ 会被拦截（缺确认、地点、时区、事项）：

```json
{ "date": "2026-05-18", "time": "13:14:00" }
```

✅ 正确（含用户确认 + 完整上下文）：

```json
{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：用 2026-05-18 13:14:00，America/Los_Angeles，旧金山，事项为当前工作决策。",
  "date": "2026-05-18", "time": "13:14:00", "zone": "-07:00",
  "lat": "37n46", "lon": "122w25", "gpsLat": 37.7667, "gpsLon": -122.4167,
  "after23NewDay": false
}
```

用户说「按星阙默认继续」时，可改用 `{ "defaults_accepted": true, "clarification_notes": "用户明确接受星阙默认设置。" }`——但 agent **不能替用户擅自**写 `defaults_accepted: true`。

> 时区既可传 `+08:00` / `-07:00` 这样的固定 offset，也可传 `America/Los_Angeles` / `Asia/Shanghai` 这样的 IANA 名称——Horosa Skill 会按起盘日期时间归一化为后端稳定接受的 offset。

## 输出协议：对 AI 来说，重点不是「算」而是「稳定可消费」

每个工具调用都返回统一 envelope：

```json
{
  "ok": true, "tool": "qimen", "version": "0.9.2",
  "input_normalized": {}, "data": {}, "summary": [],
  "warnings": [], "memory_ref": {}, "error": null
}
```

接入星阙导出协议的技法还会额外带 `data.export_snapshot`（含 `.snapshot_text` / `.sections` / `.selected_sections`）与 `data.export_format`。这意味着：AI 不用从自由文本里猜结构；同一技法连续调用得到同一套 contract；`horosa_dispatch` 的汇总层也显式带每个子结果的 export contract；落库到 JSON artifact 后结构不丢。

完整字段表见 [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) 与 [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md)；CLI 与 MCP 也通过 `tool list`、`horosa_agent_guidance`、tool docstring 暴露同一份契约。

## 数据管理：完整本地记录系统

本地数据默认写到 macOS / Linux 的 `~/.horosa-skill/`（Windows：`%APPDATA%/HorosaSkill/`）。每次 run 会沉淀：run 元信息、tool call 记录、entity 索引、JSON artifact、`run manifest`、原始 `query_text`、用户问题 `user_question`、AI 最终回答 `ai_answer_text`、可选结构化回答 `ai_answer_structured`。

典型管理动作：

```bash
uv run horosa-skill memory query                 # 按 tool / entity / run_id 查历史
uv run horosa-skill memory show <run_id>         # 精确回看某次完整调用
echo '{"run_id":"<run_id>","user_question":"...","ai_answer":"...","ai_answer_structured":{}}' \
  | uv run horosa-skill memory answer --stdin    # 把 AI 最终回答回写到记录
```

这让它不只是「工具层」，而是「工具层 + 可追溯知识库」。

## 快速开始

```bash
cd horosa-skill
uv sync
uv run horosa-skill install      # 从 GitHub Release 安装离线 runtime
uv run horosa-skill doctor       # 确认 runtime 就绪（期望 issues: []）
uv run horosa-skill serve        # 启动本地 MCP（默认 http://127.0.0.1:8765/mcp）
```

给 Claude Desktop 这类 stdio 客户端：

```bash
uv run horosa-skill serve --transport stdio
```

### 让调度器自动选技法

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：示例出生资料，上海，+08:00，按星阙默认技法参数。",
  "query":"请综合奇门、六壬和星盘分析当前状态",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### 直接调用某个工具 / 读取悬浮知识 / 解析导出正文

```bash
# 调用工具
echo '{"agent_confirmed_settings":true,"clarification_notes":"示例盘，上海默认设置","date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28","gpsLat":31.2333,"gpsLon":121.4667}' \
  | uv run horosa-skill tool run chart --stdin

# 读取星阙悬浮知识（星盘 / 六壬 / 奇门）
echo '{"domain":"qimen","category":"door","key":"休门"}' | uv run horosa-skill knowledge read --stdin

# 把星阙导出正文解析成结构化 JSON
echo '{"technique":"qimen","content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容"}' | uv run horosa-skill export parse --stdin

# 查看完整导出 registry
uv run horosa-skill export registry
```

> Agent 用过少参数直接试跑奇门 / 太乙 / 六爻、导致 `/nongli/time` 返回 `200001 param error` 时，先让 agent 通过 `horosa_agent_guidance` 补问日期 / 时间 / 时区 / 经纬度与默认设置；Horosa Skill 也会自动对 Java 日期接口重试星阙兼容格式，避免把后端格式错误误判为算法不可用。

## 当前支持的 AI 客户端

- [Claude Desktop 配置示例](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex 配置示例](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI 接入说明](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw 接入说明](./horosa-skill/examples/clients/openclaw-mcp.md)

接 OpenClaw / mcporter 时，推荐用生成器命令减少手改 JSON 和路径出错：

```bash
cd horosa-skill
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

`openclaw-setup` 会同时写 `~/.openclaw/workspace/config/mcporter.json`（供 `openclaw-check` / mcporter smoke）与 `~/.openclaw/openclaw.json` 的 `mcp.servers.horosa`（供 OpenClaw 原生挂载 `horosa_*` 工具）。

> 若 `openclaw-check` 通过、`openclaw mcp list` 能看到 `horosa`、真实会话里已出现 `horosa__...` 工具，但 agent trace 里仍是 `clientToolCount: 0`，这只是旧 trajectory 统计噪音，不能当成「未挂载」；重启 OpenClaw 或开新 session，不要让 agent 退回 Shell / Python 手算。

## 致谢：内置的开源术数引擎（ken）

奇门遁甲 / 太乙神数 / 金口诀（以及三式合一中的奇门 + 太乙）的盘面，由 **[kentang2017](https://github.com/kentang2017)** 开源的三个 Python 引擎计算。星阙在后端接入了这套引擎，Horosa Skill 复用同一计算路径并随离线 runtime 一起分发：

- **kinqimen**（奇门遁甲）— MIT — <https://github.com/kentang2017/kinqimen>
- **kintaiyi**（太乙神数）— MIT — <https://github.com/kentang2017/kintaiyi>
- **kinjinkou**（金口诀）— MIT — <https://github.com/kentang2017/kinjinkou>

完整版权与许可证文本随离线 runtime 打包在 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE`，分发时一并保留。

**许可证归属**：上述三个 `ken` 引擎是第三方 MIT 组件（作者 kentang2017）。本仓库其余术数实现——统摄法、十年大运、以及奇门 / 太乙 / 金口 / 大六壬 / 星盘 / 推运 / 卜卦 / 择日 / 神数等的 `aiExport.js` 格式化与 headless 适配——均为**星阙自有算法**，按根目录 `GNU AGPL-3.0-only` 授权。传统术数体系本身（京房八宫、希腊十年星限等）属公共知识，不构成第三方版权。

## Release 与 runtime 策略

仓库故意拆成三层：

| 层 | 放在哪里 | 作用 |
| --- | --- | --- |
| 公开仓库层 | GitHub repo | 代码、文档、CLI、MCP、测试、示例、打包脚本 |
| 维护者本地打包输入层 | `vendor/runtime-source/` | 构建离线 runtime 所需的大体积输入（不进 Git 历史） |
| 最终用户运行层 | `~/.horosa/runtime/current` / `%LOCALAPPDATA%/Horosa/runtime/current` | 用户安装后真实执行算法的本地 runtime |

这样能同时满足：GitHub 页面干净、Release 资产完整、本地运行离线、维护者打包不依赖外部兄弟目录。配套阅读：[Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md) · [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md) · [Repo Layout](./docs/REPO_LAYOUT.md)。

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | 核心 Python 包、CLI、MCP server、`horosa-core-js`（headless JS 引擎）、tests、examples、release scripts |
| [`docs/`](./docs) | runtime 规范、算法覆盖矩阵、Release 文档、维护文档 |
| [`vendor/`](./vendor) | 本地 runtime 打包输入区 |

## 验真清单

第一次 clone 后，想快速确认「这不是空壳仓库」，按这组最小检查走：

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor                              # 期望 issues: []
uv run pytest -q                                        # 227 passed
uv run python scripts/run_benchmark.py                  # HorosaBench：调度 / 导出 parity / 知识读取
uv run python scripts/run_full_self_check.py --rounds 1 # 全工具调用 / 导出 / 落库 / 检索 / dispatch 汇总
```

完整自检覆盖：每个工具能否调用 → 是否输出统一 envelope → 业务技法是否带 `export_snapshot` / `export_format` → 导出正文能否重新解析 → run 是否写入 memory → `memory show/query` 能否找回 → report JSON/DOCX/PDF 能否生成并登记 artifact → `horosa_dispatch` 汇总层是否保留子工具 export contract → OpenClaw / mcporter 能否看到 MCP 工具并完成 smoke/full check。

> **审计推运 / 神数类工具时不要只看短预览。** 这些工具的星阙式正文通常先写本命盘，再写返照 / 推运 / 流年 / 主限 / 神数表格；只截前 1200 字可能只看到本命盘。正确做法是打开完整 artifact，按 `export_format.sections` 逐 section 检查。详见 [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md)。

## 输出是否和星阙一致

「星阙一致」指两层：

1. **导出结构一致** — 业务技法输出生成星阙式 `export_snapshot.export_text`，再由 `snapshot_parser` 解析成 `export_format`；完整自检会逐项确认 selected sections 无缺失、无未知 section。
2. **算法路径一致** — Skill 不允许 agent 用 shell / Python 小脚本 / 联网搜索手算玄学盘。奇门 / 太乙 / 金口 / 三式合一里的奇门+太乙由 ken 后端独占计算；14 路神数由 chart 服务上挂载的 kentang 引擎计算；卜卦 / 择日 / Balbillus 由逐字 vendor 的星阙前端引擎计算——全部与星阙同源。

> 内容保真已做过逐字节抽检：抽星阙真实前端 builder 对同一盘比对，年龄 / 相位 / 向运星 / 本命对象完全一致；仅波斯向运的「应期日期」因 moment 截断小数日 + JS↔Python 浮点有 ≤1 天偏差，占断上无意义并已记档（见 [`horosa-skill/docs/v091-fidelity-spotcheck.md`](./horosa-skill/docs/v091-fidelity-spotcheck.md)）。若要证明某具体输入与星阙桌面 UI 逐字段一致，应把星阙对同一输入的 golden snapshot 放进 fixtures 做逐字段 diff。

## FAQ / 边界

**为什么 release 不是纯云构建？** 因为完整 runtime 依赖本地维护的 runtime source 与平台运行时。仓库保持轻量是目标，但完整 runtime 仍需可靠的本地打包输入，故采用「轻仓库 + 重 release + 明确校验」策略。

**为什么一直强调 `export_snapshot` / `export_format`？** 因为本项目最核心的价值之一就是「让 AI 稳定消费星阙输出」。没有这层 contract，AI 只能读松散文本，后续检索、比对、回写、研究评测都会变脆。

**为什么同时保留 SQLite 和 JSON？** SQLite 负责结构化索引与查询，JSON artifact 负责长期归档、可携带、可 diff、可审阅。

**`fengshui` 为什么还没进发布面？** 当前目标是「已完整、已 headless、已可离线验证」的能力面。`fengshui` 仍明确排除，不把未完成 headless 化的能力伪装成可发布功能。

**这个仓库最重要的质量信号是什么？** 不是 badge，也不是截图，而是这四件事能否同时成立：tool 真能调用 · 导出真是稳定结构化 · 结果真会落库和回写 · benchmark / self-check 真能持续跑通。
