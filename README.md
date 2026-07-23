<div align="center">

<img src="./docs/assets/banner.svg" alt="Horosa Skill — 把星阙 83 个术数 / 占星技法做成任何 AI 都能本地调用的 MCP server 与 CLI" width="880" />

# 🔮 Horosa Skill

**把星阙（Horosa）的 83 个真实术数 / 占星技法，做成任何 AI 都能本地调用的 MCP server 与 CLI。**<br/>
**A local-first MCP server & CLI that exposes 83 real astrology / metaphysics techniques from Horosa (星阙) to any AI client.**

简体中文 · [English](./README_EN.md)

<p>
  <a href="https://github.com/Horace-Maxwell/horosa-skill/releases/latest"><img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=for-the-badge&color=1d4ed8&label=%E4%B8%8B%E8%BD%BD" alt="Release" /></a>
  <img src="https://img.shields.io/badge/技法-83-1d4ed8?style=for-the-badge" alt="83 tools" />
  <img src="https://img.shields.io/badge/测试-315_passed-16a34a?style=for-the-badge" alt="315 passed" />
  <img src="https://img.shields.io/badge/runtime-offline_first-0f766e?style=for-the-badge" alt="offline" />
</p>

<p>
  <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" />
  <img src="https://img.shields.io/badge/CLI-JSON_first-111827?style=flat-square" />
  <img src="https://img.shields.io/badge/macOS_(arm64)_|_Windows_(x64)-111827?style=flat-square" />
  <img src="https://img.shields.io/badge/storage-SQLite_+_JSON-111827?style=flat-square" />
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square" /></a>
</p>

</div>

---

| ✨ | ✨ | ✨ |
|:--|:--|:--|
| 🌌 **83 技法一次装齐** | ⚡ **算法本机跑 · 断网可用** | 🧠 **为 AI 稳定消费而设计** |
| 🛡️ **AI 不许乱补参数** | 🗄️ **每次调用自动落成知识库** | 📄 **一键出 Word / PDF 报告** |
| 🔁 **断点续传 · 版本短路装** | 🀄 **中西术数 + 全 14 路神数** | 🔓 **免费 · 开源 · AGPL** |

克隆仓库、安装一次离线 runtime，Claude Code / Claude Desktop / Codex / Open WebUI / OpenClaw 等客户端即可通过 **MCP** 或 **JSON-first CLI** 直接调用真实的星阙方法：西洋本命 / 推运 / 卜卦 / 择日，八字 / 紫微 / 大六壬 / 奇门 / 太乙 / 金口诀 / 三式合一，六爻 / 塔罗 / 天文地占 / 小六壬 / 飞宫小奇门 / 小成图 / 皇极轨策 / 神数正传，以及全 14 路神数。

算法在本机运行，断网可用；每个技法返回统一 envelope 与星阙式导出结构；每次调用自动落成可检索的本地记录。**与星阙桌面端共用同一套后端、逐值同源。**

```
   🖥️  AI 客户端   Claude Code · Claude Desktop · Codex · Open WebUI · OpenClaw
        │
        │  MCP  /  JSON-first CLI
        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  🔮 Horosa Skill   本地进程 · 83 工具 · 澄清闸 · 统一 envelope │
   │  自然语言调度 · 逐技法直调 · 报告渲染 · 本地记忆检索           │
   └──────────────────────────────────────────────────────────────┘
        │  全部在本机 · 断网可用
        ▼
   ⚙️ 离线 runtime         🧩 headless JS 引擎     💾 本地存储
   Java+Python 星历        horosa-core-js          SQLite 全文索引
   ken / kentang 引擎      aiExport 结构化          + JSON artifact 归档
```

> [!NOTE]
> 它不是又造一个简化占算器，而是把星阙已有的本地算法、星历与导出协议，整理成一层**适合 GitHub 分发、适合 AI 调用、适合长期本地管理**的接口。桌面端算出来是什么，这里就是什么。

## 📑 目录

- [✨ 核心特性](#-核心特性)
- [🚀 快速开始](#-快速开始)
- [🔌 接入 AI 客户端](#-接入-ai-客户端)
- [🎯 一次调用的完整流程](#-一次调用的完整流程)
- [🧭 技法总览](#-技法总览)
- [📐 输出契约](#-输出契约)
- [🚦 调用前的澄清闸](#-调用前的澄清闸)
- [📂 本地记忆与报告](#-本地记忆与报告)
- [📦 安装与 runtime 策略](#-安装与-runtime-策略)
- [✅ 质量与验证](#-质量与验证)
- [📚 文档](#-文档)
- [🙏 致谢与许可证](#-致谢与许可证)

## ✨ 核心特性

- 🌌 **83 个真实技法，一次安装，全程离线。** 覆盖西洋占星全链路、中文术数主干、数算与卜法、全 14 路神数；算法在本机运行，不联网、不上传。
- 🧠 **为 AI 消费而设计的稳定契约。** 每次调用返回统一 envelope，接入导出协议的技法附带 `export_snapshot`（段结构化正文）。同一技法连续调用得到同一套字段，落库后结构不丢。
- 🛡️ **调用前的硬性澄清闸。** 只要技法受时间 / 地点 / 时区 / 性别 / 事项 / 宫制 / 历法 / 起局方式影响，agent 在用户确认前会被结构化拦截，并收到可直接转发给用户的追问文本。
- 🪙 **精简的响应体量。** 导出契约单份化，同一份快照不再重复；大盘单次响应体量较早期显著下降。可用 `response_view=titles|sections` 仅取段标题或指定段，完整快照始终已归档。
- ⏳ **主限法可推至 3000 年。** 逐位核验的核5方位法 + 22 项时间钥匙 + In Zodiaco / In Mundo + 宿命点(Vertex)应星 + 映点 / 界作迫星，多圈复发行。
- 🗄️ **完整的本地记录系统。** SQLite 全文检索（trigram，中文子串可命中）+ JSON artifact 归档；按人名 / 技法 / 日期区间 / 全文组合检索，跨会话找回历史。
- 📄 **结构化报告导出。** 一条命令生成 DOCX / PDF / JSON；Markdown 表格渲染为真 Word 表格，含导航大纲、目录、页码与中文字体。
- 🔁 **成熟的安装与升级链。** 断点续传、多镜像回退、实时进度；版本短路（已最新则跳过下载）；`upgrade` / `uninstall` / `selfcheck` / `doctor` 环境体检齐备。
- 🔗 **同源后端。** 奇门 / 太乙 / 金口诀走星阙 `ken` 后端；14 路神数走 chart 服务上挂载的 kentang 引擎；结果由 headless JS 层重排为 `aiExport.js` 段结构。

## 🚀 快速开始

> [!TIP]
> 前置只需 [uv](https://docs.astral.sh/uv/)（`curl -LsSf https://astral.sh/uv/install.sh | sh`）；Python ≥ 3.12 由 uv 自动准备；磁盘预留约 5 GB（runtime 下载约 730 MB、解压后约 2 GB）。

```bash
git clone https://github.com/Horace-Maxwell/horosa-skill.git
cd horosa-skill/horosa-skill
uv sync
uv run horosa-skill install      # 📦 安装离线 runtime（带进度 / 断点续传；已最新则跳过下载）
uv run horosa-skill doctor       # 🩺 环境体检（磁盘 / 端口 / node 实跑探针，期望 issues: []）
uv run horosa-skill selfcheck    # ✅ 活体验证：起一张盘 → 存 → 读回
uv run horosa-skill serve        # 🚀 启动本地 MCP（默认 http://127.0.0.1:8765/mcp）
```

<details>
<summary>🔧 <b>安装排障与升级 / 卸载</b></summary>

| 症状 | 处理 |
| --- | --- |
| `uv: command not found` | 先安装 uv：`curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| 下载缓慢或中断 | 重跑 `install` 会断点续传；或设 `HOROSA_RUNTIME_MIRROR=<镜像前缀>` 走镜像 |
| `github.com:443` 直连不通（但 `api.github.com` 可达） | 走 API 资产直链下载后本地安装：先 `curl -s https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/latest` 找到平台 zip/tar.gz 的 `assets[].id`，再 `curl -L -H "Accept: application/octet-stream" -o runtime.zip https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/assets/<id>`，最后 `uv run horosa-skill install --archive runtime.zip` |
| Java 后端(:9999)未就绪 / `doctor` 报 `services:java_backend_not_running` | 会自动**降级 chart-only** 而不是全盘卡死：三式(奇门/太乙/金口)、神数、地占、塔罗、西占 chart 族照常可用；nongli/bazi/ziwei/liureng 与「占时」起课暂不可用。`doctor` 的 `java_diagnostics` 附捕获的 Java 启动错误，`selfcheck` 会自动改用 chart 侧探针 |
| Windows 上 Java 进程秒退、无任何日志 | 已知诱因：代理/VPN/安全软件的 WFP 过滤会拦 `java.exe` 的 loopback（JDK-17 内部管道优先 AF_UNIX，connect 被拦即崩且无 TCP 回退，见 issue #14）。停掉相关服务通常不够（WFP 过滤驻留内核），需禁用后**重启**再试；期间 chart-only 降级模式可继续用 |
| 磁盘不足 / 端口被占 | `uv run horosa-skill doctor` 逐项体检并给出 `next_action` |
| 升级 | `uv run horosa-skill upgrade`（同版本不重复下载） |
| 卸载 | `uv run horosa-skill uninstall`（默认仅打印将删清单，`--yes` 执行，`--purge-data` 才动用户数据） |

</details>

## 🔌 接入 AI 客户端

一条命令生成**带真实绝对路径**的即用配置，无需手填占位符：

```bash
uv run horosa-skill client config --format claude-code      # 输出 claude mcp add … 命令
uv run horosa-skill client config --format claude-desktop   # Claude Desktop mcpServers 片段
uv run horosa-skill client config --format codex            # Codex config.toml 片段
```

| 客户端 | 接入方式 |
| :-- | :-- |
| 🟣 **Claude Code** | `claude mcp add horosa -- uv run --directory <abs> horosa-skill serve --transport stdio`；见 [接入说明](./horosa-skill/examples/clients/claude-code.md) |
| 🟠 **Claude Desktop** | [配置示例](./horosa-skill/examples/clients/claude_desktop_config.json) 或 `client config --format claude-desktop` |
| 🟡 **Cursor** | 一键安装：`uv run horosa-skill client config --format cursor` 输出官方 deep link（点击即装）与 mcpServers 片段 |
| 🔷 **VS Code** | 一键安装：`uv run horosa-skill client config --format vscode` 输出 `vscode:mcp/install` 链接与 `code --add-mcp` 命令 |
| 🧩 **Claude Code Plugin** | `/plugin marketplace add Horace-Maxwell/horosa-skill` → `/plugin install horosa@horosa-skill`（skill + MCP 一步到位；首次仍需在插件目录跑 `install` 装离线 runtime） |
| 🔵 **Codex** | [配置示例](./horosa-skill/examples/clients/codex-config.toml) 或 `client config --format codex` |
| 🟢 **Open WebUI** | [接入说明](./horosa-skill/examples/clients/openwebui-streamable-http.md) |
| ⚪ **OpenClaw / mcporter** | `uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace` |

> [!TIP]
> 上下文预算受限的客户端可设 `HOROSA_MCP_COMPACT=1`，只暴露约 9 个门面工具（含按名直调的 `horosa_tool_run` 与 83 技法目录索引），澄清闸照常生效。根目录 `server.json` 为 MCP Registry 元数据，普通用户无需手改。

## 🎯 一次调用的完整流程

以「查今年事业，1995-06-03 05:30 上海出生」为例，agent 端的实际序列：

```
1️⃣  澄清闸兜底 —— 缺时区 / 宫制等结果敏感设置时，工具返回追问文本，
    agent 先向用户确认，而非自行补参
2️⃣  起盘       —— 确认后传 agent_confirmed_settings: true 调用技法工具，
    返回统一 envelope，含 memory_ref.run_id 与 data.export_snapshot
3️⃣  读盘       —— 读 export_snapshot.export_text / sections 撰写解读
    （想省 token 可传 response_view: "titles" 只取段标题，完整快照已归档）
4️⃣  出报告     —— report_render 生成 DOCX，传入的 ai_report 自动写回记忆
5️⃣  跨会话找回 —— memory_query 按人名 / 技法 / 日期检索，memory_show 取完整记录
```

> [!NOTE]
> 最短路径为 **2 次工具调用 + 1 次本地分析**：起盘拿到 `run_id`，本地撰写 `ai_report`，再 `report_render` 出 Word 并自动归档。全程算法在本机、AI 只负责解读、结构永不丢。

## 🧭 技法总览

所有业务技法都返回统一 envelope 并附星阙式 `export_snapshot`。带 ⓟ 的工具受设置影响，调用前必须先确认参数。

<details open>
<summary>🌟 <b>西洋占星 · 本命与派生盘（7）</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `chart` ⓟ | 标准星盘 | 基础西洋星盘 + 完整导出正文（12 分度 / 主宰星链 / 寿命格局 / 古典 / 古典格局） |
| `chart13` ⓟ | 13 宫扩展盘 | `chart13` 形态输出 |
| `hellen_chart` ⓟ | 希腊星盘 | 希腊占星取向盘面 |
| `india_chart` ⓟ | 印度盘 | 分宫 4→24 制、岁差 6→47 制 |
| `guolao_chart` ⓟ | 七政四余盘 | 七政四余 / 果老法盘面 |
| `relative` ⓟ | 合盘 / 关系盘 | 双人关系、合盘、关系量化评分 |
| `germany` ⓟ | 量化盘 / 汉堡学派 | 90° 拨盘 + 8 颗 TNP + 中点树 / 相位 / 列表 |

</details>

<details>
<summary>⏳ <b>西洋占星 · 推运 / 返照 / 时运 · 占星地图 / 名人库（24）</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `solarreturn` ⓟ / `lunarreturn` ⓟ | 太阳 / 太阴返照 | 本命 + 返照盘 + 相位 |
| `solararc` ⓟ | 太阳弧推运 | 本命 + 推运盘 + 相位 |
| `givenyear` ⓟ | 指定年推运 | 本命 + 流年盘 + 相位 |
| `profection` ⓟ | 小限 / 年运推限 | profection 时间层 |
| `pd` ⓟ | 本初方向 / 主限 | 逐位核验核5方位法 + 22 项时间钥匙，可推运至 3000 年 |
| `pdchart` ⓟ | 主限盘 | 可读主限盘面 + 相位 |
| `zr` ⓟ | 黄道释放 | zodiacal release 时间轴 |
| `firdaria` ⓟ | 法达星限 | 法达星限结构与时间轴 |
| `decennials` ⓟ | 十年大运 | 与星阙 `decennials.test.js` 金标对齐 |
| `agepoint` ⓟ | 年龄推进点 / Huber | Koch 宫 6 年一宫周期 |
| `distributions` ⓟ | 界推运 / 分配法 | 上升点行经埃及界的分配主时间轴 |
| `mundane` ⓟ | 世俗盘 | 年度入宫盘 + 子盘群（新月 / 满月 / 日月食 / 地区盘 / 行星周期 / 定局 / 分野） |
| `jaynesprog` ⓟ | 赤纬推运 | 二次推运 + 赤纬平行 / 反平行 |
| `vedicprog` ⓟ | 恒星推运 | sidereal 下的二次推运 |
| `planetaryarc` ⓟ | 行星弧 | 整盘按 arcSource 二次弧方向 |
| `planetaryages` ⓟ | 行星年龄 | 托勒密人生七阶 + 当前主运 |
| `yearsystem129` ⓟ | 129 年系统 | 七政各管小年的 129 年一轮 |
| `persiandirected` ⓟ | 波斯向运 | 黄经象征向运（1°/年）应期表 |
| `balbillus` ⓟ | Balbillus 129 年 | 旺距削减主限 + 递归子限 |
| `triplicityrulers` ⓟ | 三分主星推运 | 昼夜换序划分人生阶段 |
| `keypoints` ⓟ | 数字相位推运 | 七星小年数 + 座距按年龄因数激活 |
| `lunationphase` ⓟ | 月相推运 | 次限日月黄经差八相时间轴 |
| `extrareturns` ⓟ | 多重回归 | 土 / 木 / 月交三体返照应期 |
| `acg` ⓟ | 占星地图 | 行星地理投影线（MC/IC / 天顶点 / 偕升带 / 线交点） |
| `astrodata` ⓟ | 名人星盘库 | 数万条 A/AA 级出生数据离线检索（FTS / 分类 / Rodden 评级） |

</details>

<details>
<summary>🔯 <b>西洋占卜 · 卜卦 / 择日（2）</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `horary` ⓟ | 卜卦（horary） | 根本性 / 14 类征象星 / 完成分析 / 月亮的故事 / 裁决 / 应期方位 |
| `election` ⓟ | 择日（electional） | 红线 / 28 类用事规则包 / 评分定级 / 起盘时刻 / 建议 |

</details>

<details>
<summary>☯️ <b>中文术数主干 · 三式合一（9）</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `bazi_birth` ⓟ / `bazi_direct` ⓟ | 八字命盘 / 直断 | 四柱 + 大运 + 神煞 + 五行力量 / 格局 / 盲派结构 |
| `ziwei_birth` ⓟ | 紫微斗数 | 自定义四化 / 流派 / 命中格局（`ziwei_rules` 返回规则库） |
| `liureng_gods` ⓟ / `liureng_runyear` ⓟ | 大六壬起课 / 行年 | 四课三传神煞 / 毕法 100 法 / 占断向导 / 七政 |
| `qimen` ⓟ | 奇门遁甲 | ken（`kinqimen`）起盘 + 法奇门叠加层 + 演卦 |
| `taiyi` ⓟ | 太乙神数 | ken（`kintaiyi`）起盘，十六宫标记 |
| `jinkou` ⓟ | 金口诀 | ken（`kinjinkou`）起盘，20 段解读层 |
| `sanshiunited` ⓟ | 三式合一 | 一页聚合奇门 + 太乙 + 大六壬，统一导出 |

</details>

<details>
<summary>🀄 <b>本地术数 · 数算 · 占卜（10）</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `tongshefa` ⓟ | 统摄法 | 卦象 / 六爻 / 潜藏 / 亲和 |
| `canping` ⓟ | 邵子参评数 / 金锁银匙 | 四柱起数 + 本命 / 大运歲運条文 |
| `heluo` ⓟ | 河洛理数 | 先后天卦 + 元堂爻辞 + 大限岁运断验 |
| `yizhangjing` ⓟ | 一掌经 | 十二支六道 + 十二宫 + 大限流年十二神 + 神煞合参 |
| `zhengchuan` ⓟ | 神数正传 | 铁板 / 邵子 / 大定 / 六亲 / 铁算心易 五流派·四柱起数 + 条文 + 大运死月 |
| `xiaoliuren` ⓟ | 小六壬 | 三数起三传·主流六宫 / 道门九宫 + 生克 + 九神 + 拜解 |
| `feigong` ⓟ | 飞宫小奇门 | 时上起青龙飞九宫 + 主客命宫 + 八门九星 + 流年流月 + 应期 |
| `xiaochengtu` ⓟ | 小成图 | 洛书九宫佈局 + 正旁推 + 四象 + 应期 + 股市研判（五式起卦） |
| `guice` ⓟ | 皇极轨策 | 十二法起卦 + 演数四位 + 卦变断法 + 三要十应 + 元会运世 + 大定 |
| `harmonic` ⓟ | 调波盘 | 黄经 × 调波数取位、同频合相 |
| `suzhan` ⓟ | 宿占 / 宿盘 | 宿占结构与宿曜信息 |
| `sixyao` ⓟ | 六爻 / 易卦 | 本 / 互 / 之 / 错 / 综卦 + 断卦结构 |
| `geomancy` ⓟ | 天文地占 | 4 母卦 → 16 图形 + 十二宫入宫 + 判官 / 见证 |
| `tarot` ⓟ | 塔罗 | 78 牌确定性洗牌 + 牌阵直断 / 细论 / 综合建议 |
| `otherbu` ⓟ | 占星骰子 | 星骰与对应解读结构 |

</details>

<details>
<summary>🔢 <b>神数（全 14 路）</b></summary>

| 工具 ID | 名称 | 引擎 | 工具 ID | 名称 | 引擎 |
| --- | --- | --- | --- | --- | --- |
| `wangji` ⓟ | 皇极经世 | 标准 | `tieban` ⓟ | 铁板神数 | kinastro |
| `wuzhao` ⓟ | 五兆 | 标准 | `fendjing` ⓟ | 分经神数 | kinastro |
| `taixuan` ⓟ | 太玄 | 标准 | `beiji` ⓟ | 北极神数 | kinastro |
| `jingjue` ⓟ | 京氏易 | 标准 | `nanji` ⓟ | 南极神数 | kinastro |
| `shenyishu` ⓟ | 神乙数 | 标准 | `chunzi` ⓟ | 淳子神数 | kinastro |
| `shaozi` ⓟ | 邵子神数 | kinastro | `xianqin` ⓟ | 演禽 | kinastro |
| `cetian` ⓟ | 策天飞星 | kinastro | `qizhengkin` ⓟ | 七政四余·张果 | kinastro |

</details>

<details>
<summary>📅 <b>节气 / 农历 / 黄历 · 协议 / 调度 / 知识</b></summary>

| 工具 ID | 名称 | 说明 |
| --- | --- | --- |
| `jieqi_year` ⓟ / `nongli_time` ⓟ | 全年节气盘 / 农历换算 | 节气节点 / 农历干支 |
| `calendar_month` ⓟ | 黄历 / 万年历 | 整月农历 / 干支 / 节气 / 朔望 + 选中日详情 |
| `gua_desc` / `gua_meiyi` | 卦义 / 梅易卦义 | 卦名卦辞 / 梅花易数卦义 |
| `export_registry` / `export_parse` | 导出协议注册表 / 正文解析器 | 机器可读导出总表 / 把导出文本解析回 JSON |
| `horosa_dispatch` | 总调度器 | 自然语言意图自动分派到对应技法 |
| `knowledge_registry` / `knowledge_read` | 悬浮知识目录 / 读取器 | 列出 / 读取星阙 app 内 hover 知识并落库 |

</details>

> [!NOTE]
> 明确排除项：`fengshui`（风水尚未完成 headless 化，不作为可发布能力）。

## 📐 输出契约

每个工具调用返回统一 envelope：

```json
{
  "ok": true, "tool": "qimen", "version": "0.23.0",
  "input_normalized": {}, "data": {}, "summary": [],
  "warnings": [], "memory_ref": {}, "error": null
}
```

接入导出协议的技法额外带 `data.export_snapshot`，含 `export_text`（段结构化正文）、`sections`（逐段标题 + 正文 + 结构化数据）、`selected_sections`、`provenance` 等。因此 ——

- 🧷 AI 无需从自由文本猜结构；
- 🔁 同一技法连续调用得到同一套契约；
- 🧮 `horosa_dispatch` 汇总层显式带每个子结果的导出契约；
- 💾 落库到 JSON artifact 后结构不丢。

> [!NOTE]
> 自 v0.21.0 起契约单份化，同一份快照不再重复存放；可传 `response_view=titles|sections` 仅返回段标题或段标题 + 正文，完整快照始终已归档，可用 `memory_show(run_id)` 取回。字段全表见 [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) 与 [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md)。

## 🚦 调用前的澄清闸

> [!IMPORTANT]
> 只要技法受时间 / 地点 / 时区 / 性别 / 事项 / 宫制 / 历法 / 起局方式影响，agent 在用户确认前会被拦截，返回 `agent_guidance.required` 与可直接转发给用户的追问文本。**杜绝「AI 自己脑补一个生辰就开算」。**

```jsonc
// ❌ 被拦截：缺确认、地点、时区、事项
{ "date": "2026-05-18", "time": "13:14:00" }

// ✅ 通过：含用户确认 + 完整上下文
{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认：2026-05-18 13:14:00，America/Los_Angeles，旧金山，事项为工作决策。",
  "date": "2026-05-18", "time": "13:14:00", "zone": "-07:00",
  "lat": "37n46", "lon": "122w25"
}
```

标准流程：用户说出需求 → 参数不足则查 `horosa_agent_guidance` 或直接询问 → 用户明确回答 → agent 传 `agent_confirmed_settings: true` + `clarification_notes` 调真实工具 → 用 `export_snapshot` 解释，不自行手算。时区可用 `+08:00` 固定偏移，也可用 `Asia/Shanghai` IANA 名（按起盘日期归一化）。

## 📂 本地记忆与报告

本地数据默认写入 `~/.horosa-skill/`（Windows：`%APPDATA%/HorosaSkill/`）。每次 run 沉淀：run 元信息、tool call 记录、entity 索引、JSON artifact、run manifest、原始 `query_text`、用户问题、AI 最终回答与可选结构化回答。

- 🔎 SQLite 全文检索（trigram，中文子串可命中）+ 热路径索引 + WAL 并发；按人名 / 技法 / 日期区间 / 全文组合检索，支持分页。
- 📄 `report_render` 生成 DOCX / PDF / JSON：Markdown 表格渲染为真 Word 表格（跨页重复表头）、导航大纲、目录、页码、中文字体，异常自动降级保全文。

```bash
uv run horosa-skill memory query                 # 按 tool / entity / run_id / 全文 检索
uv run horosa-skill memory show <run_id>         # 精确回看某次完整调用
```

## 📦 安装与 runtime 策略

仓库分为三层，兼顾「代码仓库轻量、Release 资产完整、本地运行离线」：

| 层 | 位置 | 作用 |
| --- | --- | --- |
| 📂 公开仓库层 | GitHub repo | 代码、文档、CLI、MCP、测试、示例、打包脚本 |
| 📦 打包输入层 | `vendor/runtime-source/` | 构建离线 runtime 的大体积输入（不进 Git 历史） |
| 💻 用户运行层 | `~/.horosa/runtime/current` | 用户安装后本地执行算法的 runtime |

奇门 / 太乙 / 金口诀（及三式合一中的奇门 + 太乙）走星阙 `ken` 后端；14 路神数走 chart 服务上挂载的 kentang 引擎；结果由 headless JS 层重排为 `aiExport.js` 段结构，与星阙桌面端逐值同源。配套阅读：[Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md) · [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md) · [Repo Layout](./docs/REPO_LAYOUT.md)。

## ✅ 质量与验证

| 检查项 | 结果 |
| --- | --- |
| 🧰 可调用工具 | 83 / 83 `ok=true` |
| 🧪 工程测试 | **315 / 315 pass**（ken / 神数后端实时集成 + 离线 golden 单测 + node JS golden） |
| 🛡️ 未确认参数时强制追问 | 67 个技法工具触发 `must_ask_user=true` |
| 📐 星阙式导出结构 | 每个业务技法均带 `export_snapshot`（已建模 63 个导出 technique） |
| 🗄️ 本地 memory / report | 83 / 83 写入 + 83 / 83 JSON artifact |
| 🔄 GitHub CI | Linux / macOS 单测 + JS golden 自检 + Windows OpenClaw smoke |
| 📦 Release runtime | macOS (arm64) `v0.23.0` 已打包并校验；Windows (x64) 由构建机补传（补传前 win 用户拿到上一版 runtime）；其余平台安装时明确报不支持 |

第一次 clone 后确认非空壳的最小验证：

```bash
cd horosa-skill && uv sync && uv run horosa-skill install
uv run horosa-skill doctor                              # 期望 issues: []
uv run pytest -q                                        # 315 passed
uv run python scripts/run_full_self_check.py --rounds 1 # 全工具调用 / 导出 / 落库 / 检索 / dispatch 汇总
```

> [!WARNING]
> 审计推运 / 神数类工具时不要只看短预览——其正文通常先写本命盘再写返照 / 推运 / 流年 / 主限表格，只截前若干字符可能只看到本命盘。应打开完整 artifact，按 `export_snapshot.sections` 逐段检查。详见 [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md)。

## 📚 文档

| 文档 | 内容 |
| --- | --- |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 架构设计 |
| [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md) | 每个工具的输入契约（必填字段） |
| [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) | 输出 / envelope / export 数据契约 |
| [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md) | 推运类导出的逐段审计方法 |
| [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) · [`docs/EVALUATION.md`](./docs/EVALUATION.md) | 运维 · 评测体系 |
| [`docs/OFFLINE_RUNTIME_RELEASES.md`](./docs/OFFLINE_RUNTIME_RELEASES.md) | 离线 runtime 打包与发布 |
| [`docs/LESSONS.md`](./docs/LESSONS.md) · [`docs/GLOSSARY.md`](./docs/GLOSSARY.md) | 逐版本经验台账 · 领域名词表 |
| [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md) · [`AGENTS.md`](./AGENTS.md) | AI 客户端行为策略源 · Agent 总规则与路由 |

## 🙏 致谢与许可证

奇门遁甲 / 太乙神数 / 金口诀（及三式合一中的奇门 + 太乙）的盘面，由 [kentang2017](https://github.com/kentang2017) 开源的三个 Python 引擎计算，随离线 runtime 一起分发：

- ✳️ **kinqimen**（奇门遁甲）— MIT — <https://github.com/kentang2017/kinqimen>
- ✳️ **kintaiyi**（太乙神数）— MIT — <https://github.com/kentang2017/kintaiyi>
- ✳️ **kinjinkou**（金口诀）— MIT — <https://github.com/kentang2017/kinjinkou>

上述三个 `ken` 引擎为第三方 MIT 组件。本仓库其余术数实现——统摄法、十年大运，以及奇门 / 太乙 / 金口 / 大六壬 / 星盘 / 推运 / 卜卦 / 择日 / 神数等的 `aiExport.js` 格式化与 headless 适配——均为星阙自有算法，按根目录 `GNU AGPL-3.0-only` 授权。传统术数体系本身（京房八宫、希腊十年星限等）属公共知识，不构成第三方版权。

<div align="center">

**🔮 玄学工具，本地优先，掌握在你自己手里。**

[![License](https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square)](./LICENSE) [![Security](https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square)](./SECURITY.md) [![Support](https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square)](./SUPPORT.md) [![Contributing](https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square)](./CONTRIBUTING.md) [![Citation](https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square)](./CITATION.cff)

</div>
