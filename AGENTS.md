# Horosa Skill — Agent Rules

These rules are for Codex, Cursor, Claude (incl. Claude Code), OpenClaw, Open WebUI, and any agent
connected to this repository or its MCP server.

**本文件只记「现行真相」（current truth），按主题组织。** 逐版本教训原文在
[`docs/LESSONS.md`](./docs/LESSONS.md)（只增台账）；领域名词在 [`docs/GLOSSARY.md`](./docs/GLOSSARY.md)；
Claude Code 的薄入口是根 [`CLAUDE.md`](./CLAUDE.md)（与本文 §0 路由一致）。

目录：§0 定向路由 · §1 铁律 · §2 🔴问题记录协议 v2 · §3 AI 客户端行为（指针） · §4 计算模型 ·
§5 新增技法/re-vendor · §6 打包不变量 · §7 发布协议 · §8 本地验证与症状速查 · §9 Stability invariants ·
§10 上游镜像注记 · §11 MIT 义务 · §12 经验台账

---

## 0. 30 秒定向与路由

Horosa Skill 把星阙（Horosa）的 **110 个**术数/占星技法打包成 local-first 的 **MCP server + CLI**：
算法跑在本机离线 runtime（Java 聚合层 `:9999` + Python chart 服务 `:8899`（含 ken/kentang 引擎）+
bundled Node headless 引擎 `horosa-core-js`），每个技法输出统一 envelope + 星阙式
`export_snapshot`/`export_format`；仓库保持轻量，重 runtime 走 GitHub Releases 分发。
本仓是星阙的**下游**（sync 方向：星阙 → skill，永不反向）。

| 你要做什么 | 去哪里 |
| --- | --- |
| 作为 AI 客户端调用技法 / 出报告 / 解释结果 | [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md)（客户端行为唯一策略源）+ 其 `references/` |
| 理解仓库结构与一次调用的完整链路 | [`docs/REPO_LAYOUT.md`](./docs/REPO_LAYOUT.md) · [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) |
| 改代码 / 新增技法 / re-vendor 引擎 | 本文 §4–§5 + [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md) |
| 打包 runtime / 发版 / 修发布事故 | 本文 §6–§7 + [`docs/OFFLINE_RUNTIME_RELEASES.md`](./docs/OFFLINE_RUNTIME_RELEASES.md) + [`docs/WINDOWS_RELEASE_BUILD_PROMPT.md`](./docs/WINDOWS_RELEASE_BUILD_PROMPT.md) |
| 本地验证 / 按症状排障 | 本文 §8（含症状速查表） |
| 查某条规则的历史来龙去脉 | [`docs/LESSONS.md`](./docs/LESSONS.md) |
| 查名词（ken/kentang/命盘·事盘/pin-forward…） | [`docs/GLOSSARY.md`](./docs/GLOSSARY.md) |

## 1. 铁律（六条，违者必出事故）

1. **禁手算**：任何星阙技法结果一律走 Horosa MCP/CLI 工具，禁止用 Python/JS/shell/网搜公式重造
   （手算会绕过输入归一化、真太阳时、星阙默认值、runtime 各层、导出契约与 memory——细则见 SKILL.md）。
2. **先问后调**：会改变结果的设置缺失时先问用户；运行时闸门 `agent_guidance.required` 会强制拦截（细则见 SKILL.md）。
3. **vendor/参照唯一来源 = 开源仓 Horosa-Public**（`HOROSA_SOURCE_ROOT=/Users/horacedong/Desktop/Horosa-Public`，
   sync 脚本默认根不对，必须显式传）。上游星阙工作树**只读**；skill 仓的教训**永不**写进上游树。
4. **🔴 问题记录协议 v2**（§2）：踩坑必记——台账原文 + 蒸馏规则 + CHANGELOG + 机器守卫，四件套同一 change 完成。
5. **发布不信绿灯**：release-completeness guard 绿 ≠ 完整（pin-forward 模式下它必绿）；
   `sync_windows_release.py --check` 的 `[GAP]` 才是权威（§7）。
6. **文档同步交给 CI**：`scripts/verify_docs_sync.py` 强制版本号锁步 × 工具全覆盖 × 链接有效 ×
   SKILL frontmatter × 无冲突标记。改文档/发版时跑它，别靠肉眼。

## 2. 🔴 MANDATORY：问题记录协议 v2（every session, read this）

**This is an enforced rule, not advice.** 任何 agent/维护者在本仓踩到问题、gotcha、意外行为、错误假设，
或修掉一个 bug，必须在**同一个 change** 里完成四件事，工作才算完成——no exception is too small; if it bit
you, it will bite the next agent：

1. **台账落原文**：在 [`docs/LESSONS.md`](./docs/LESSONS.md)「台账正文」最上方加一条
   （`### vX.Y.Z / YYYY-MM — 主题`），写清 **symptom → root cause → fix/guard**，让下一个 agent 秒认。
2. **蒸馏进现行规则**：把「今后应该怎么做」写进本文对应主题章节（§4–§10），**替换**被取代的旧文本——
   本文不做叠层叙事（不留「以前 X 现在改成 Y」），历史归台账。教训影响 AI **客户端**调用方式
   （payload 字段 / 闸门 / section 契约）时，同步 [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md)
   及其 `references/`。两文档永不互相矛盾。
3. **CHANGELOG**：任何代码/行为/构建/CI 变化在 `CHANGELOG.md` `[Unreleased]` 加条目。
4. **机器守卫**：凡脚本或 CI 能断言的，加代码级 guard（`verify_*` 检查 / CI step / schema 约束 /
   `require_path`）——对可断言的问题，只写文档**不算完成**。

**Self-audit gate（每次发布 + 每次 "check for bugs"）**：重读本文各主题章节，确认每条仍成立、本轮所学已按
四件套落盘。未记录的复发问题按回归对待。
**Compaction gate（每次发布）**：本文任何章节若出现矛盾、被取代文本或明显超长（>~80 行），当场归并——
叙事移去台账，留下规则。（v1 协议只增不减，曾把本文喂到 900+ 行；v2 用这道门保持可读。）
**Scope rule**：所有教训只进本仓（`AGENTS.md` / `docs/LESSONS.md` / `SKILL.md`）；**never** 写进上游星阙树。

## 3. AI 客户端行为（属主 = SKILL.md，本节只留一行版）

客户端行为规则的**唯一策略源**是 [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md)
（分册：`references/{payloads,late-zi,predictive,chinese-methods,reports,troubleshooting}.md`）。速查：

- 禁手算 / 禁 `Exec` / 禁网搜公式；只从返回的 `export_snapshot.export_text` + `export_format.sections` +
  `summary` 解释，缺什么就说本地未返回该段，不发明依赖。
- 结果敏感设置缺失 → 先问（给具体选项）；用户说「当前时间」可直接取本地时间；只有用户明说
  「默认 / 按星阙 / 快速起盘 / 你来决定」才可用默认并声明用了默认。
- 闸门协议：被 `agent_guidance.required` 或 `*.invalid_payload` + `details.agent_recovery` 拦下 → 用
  `agent_recovery.prompt_to_user` 问用户；答后带 `agent_confirmed_settings: true`（接受默认则
  `defaults_accepted: true`）+ `clarification_notes`；**绝不自己置 true 蒙混**，不换工具绕行。
- 大六壬默认 `guirengType: 2`（星占法贵人）；0/1 需用户明说或既有案例指定。
- 预测类光有本命数据不够：必须有目标 `datetime` / `dirZone` / `dirLat` / `dirLon` / PD 方法设置
  （逐工具契约表：`references/predictive.md`）。
- 禁幻觉依赖：没有当前 `doctor` / `openclaw-check` 证据，永不说「需要 MongoDB / 7897 / 星阙桌面端 / 远程库」。
- **每次给出结论后附技法尾注**：把 `data.technique_card`（技法/口径/算源/段落健康度/版本链）原样转述，
  不得改写或省略口径行；`matches_declaration: false` 必须明说。要文件调 `horosa_technique_report`
  （`run_id` 单次 / `group_id` 整场，后者另检出跨技法口径冲突）。它与咨询报告是两种文档，不混。
- **没有 MCP 的 agent 走同一契约**（v0.38.0 B5）：SKILL.md「Shell-only agents (no MCP)」——`tool run --input/--output`
  文件（Windows PowerShell 5.1 管道会重编码）、退出码 0 = 信封已写（看 `ok`）/ 2 = 起跑前被拒（stderr JSON `code`），闸门
  `agent_guidance.required` 在 stderr；两节里每条命令由 `tests/test_skill_shell_contract.py` 对到 Click 命令树。四家客户端
  先读的薄镜像（`GEMINI.md` / `.github/copilot-instructions.md` / `.windsurf/rules/` / `.clinerules/`，各 ≤ 30 行）只许
  指针 + 闸门 + 读盘 + `setup --client`，`verify_docs_sync.check_agent_mirrors` 锁；不加 Roo（不在 Works-with 矩阵）。
- **引教义必带出处**（v0.28.0）：口径/流派/方法论先 `knowledge_read`（31 域，逐条 citation 落到
  上游组件文件），没有的按通则推理并明说无出处；多技法互证走 `horosa_hecan`——它产**模板**不产
  终稿，分歧必须披露不许平均（铁律在模板 instructions 里，不靠自觉）。

## 4. 计算模型铁律（compute model）

**ken 是唯一算权，JS 只格式化。** `qimen` / `taiyi` / `jinkou`（及 `sanshiunited` 的奇门+太乙腿）由星阙
**ken 后端**（`kinqimen` / `kintaiyi` / `kinjinkou`，挂在 chart 服务 `:8899` 的 `/qimen/pan` ·
`/taiyi/pan` · `/jinkou/pan`）计算，与星阙桌面端逐值同源。`service.py::_run_{qimen,taiyi,jinkou}_tool`
先取 JS 脚手架前置（qimen 要 nongli+jieqi，jinkou 要 liureng），`_call_remote` 打 ken 端点，再把
`ken_response` 交给 `js_client.run(...)`；`horosa-core-js` 的 `tools/{qimen,taiyi,jinkou}.js` 用星阙的
`normalizeKinqimenData` / `normalizeBackendPan` / `normalizeKinjinkouData` 把 ken 响应叠到本地脚手架，
`build*SnapshotText` 产出 `export_snapshot` 段。JS 本地脚手架只在 `ken_response` 缺失/畸形时兜底
（graceful，非正常路径）。健康结果带 `pan.source == "kinqimen"/"kintaiyi"`、`jinkou.source == "kinjinkou"`。
**例外 = 上游同判据的本地路由（v0.40.0 起）**：上游 `isQimenLocalRoute`（非时家/转盘、飞盘/混合、报数、七组本地口径任一非缺省）
走本地 `calcDunJia`，金口诀五项流派任一非缺省走本地 `buildJinKouData`——这是上游**本来的**算法选择，不是回退：
runner 不打 ken、`data.route.local=true`、`compute_sources` 标 `local_route_calcDunJia` / `local_route_buildJinKouData`
（`technique_provenance.json` 已声明）。Python 与 JS 路由判定不一致即 `tool.qimen_route_check_failed`；ken 失败被静默回退
的老形态仍由 `_require_ken_pan` 抓（那条路径不带 local_route_* 标记）。

**⚠️ ken 端点失败也回 HTTP 200 — 只认 `source`，永不信状态码。** chart 服务的 `web{qimen,taiyi,jinkou}srv.py`
把一切异常包成 `{"ResultCode": -1/1, "Result": "<engine> ... failed"}`（字符串 `Result`）照样 200 返回；
`_call_remote` 不 raise、`_unwrap_result` 原样放行，转给 JS 后 formatter guard（`ken.selected || ken.raw`）
为假 → **静默回退本地旧引擎 = 错结果无报错**。守卫：`service.py::_require_ken_pan` 在每次 ken
`_call_remote` 后断言 `ken_response.get("source") == engine`，否则 raise `tool.ken_compute_failed`。
**新增 ken-backed 技法必须同样调 `_require_ken_pan`。**
🔴 **同族第二例（v0.26.0）：`/electionscan/scan`。** 它把失败包成
`{"ResultCode": -1, "Result": {"err": …}}`，而 `HorosaPlainJsonClient` 只看**顶层** `err` → 不加守卫时
`span_too_large`/`invalid_conditions` 会**静默退化成「零命中」**：一个看起来完全合理的空结果。
守卫 = `service.py::_require_electionscan_ok`。凡「200 也回失败信封」的端点，一律照此办理。
同类静默失败还有一种形状：**传错数据结构不报错、只是匹配不到**——`scanQimen` 吃的是**编译后**的条件树
（`{type:'all', conditions}`），传 UI 树（`{kind:'group', joiner, children}`）安静地产出零命中。
真机跑一遍才能发现，离线桩不会。
回归测试：
`tests/test_service.py::test_qimen_fails_loudly_when_ken_returns_failure_envelope`（连带要求 ken 端点的
测试 fake 返回带正确 `source` 的 body，见 `FakeClient`）。

**端点注册法则：任何打 chart 服务的 `_call_remote(endpoint)` 必须把 endpoint 加进
`service.py::_PYTHON_CHART_ENDPOINTS`。** chart 服务族 = `/chart` · `/predict/*` · `/astroextra/*` ·
`/india/*` · `/germany/*` · `/jieqi/*` · `/*/pan`（ken + 14 神数）等。漏登记 → 请求落到 Java `:9999`
通路（500，或读 `_java_runtime_ready` 触发二次探针，直接打挂 `test_service_*runtime*`）。判据：进了该 set
才复用 `_chart_runtime_ready` 缓存、首调后不再探针。

**工具算源普查**（决定改哪一层）：

- **ken-fed**：qimen / taiyi / jinkou（+ sanshiunited 两腿）——ken 算，JS 排版。
- **原生·非 ken 数算**：canping（邵子参评数）/ heluo（河洛理数）——在 `horosa-core-js` 进程内经 vendored
  bazi 链（`src/vendor/bazi/` → npm `lunar-javascript`）起四柱，再自行起数/起卦 + 条文查表；不打 chart 服务。
  canping / heluo / yizhangjing 的 `timeAlg` 缺省 **0**（真太阳时，经度+均时差；`1` = 钟表时）、日界缺省 1/1——v0.40.0 更正：
  星阙页面的 `fieldVal(f,'timeAlg',1)` 读的是**恒被预置为 0** 的全局字段（models/astro.js:375-377、newChartSeeds.js:43），
  字面 1 的兜底从不触发；无头路径 `record.timeAlg ?? 0`（aiAnalysisContext.js:603）与挂载齿轮缺省 0 同口径。
  找缺省要追字段的**种子**，不是 getter 的兜底值（此前据兜底值写成缺省 1，钟表时出盘多个版本）。
- **backend predict/astroextra 型**：harmonic / agepoint / distributions / jaynesprog / vedicprog /
  planetaryarc 等——Python `_call_remote` + Python snapshot builder。
- **三式合一（v0.40.0 起）**：Python 只取数（一份三式 nongli + 展示真太阳时 + `/chart` hsys 1 + 奇门/太乙 runner），
  整段快照由 vendored 上游 `buildSanShiUnitedSnapshotText`（`tools/sanshiUnited.js` 按上游 `performRecalcByNongli` 装配）产出；
  六壬层用 SanShiUnitedMain 自带三函数、占时取奇门盘时柱（随 `timeAlg`），不再另起 `/liureng/gods` 子盘。
- **复合型**：mundane（`/jieqi/year` seedOnly 求入宫时刻 → 该时刻 `/chart`，输入是 年+入宫节气+地点；上游 v3.11
  右栏 25 张卡由 Python 取数后喂 JS `tools/mundaneCards.js` 调 vendored 卡 builder，3 张需 UI 状态的登记为可选段）、
  sanshiunited、extrareturns（Python 循环逐体拉 `/astroextra/planetreturn` 拼段）。**请求型 builder 一律归
  Python——JS 层不发 HTTP。**
- **纯 headless JS**：tongshefa（无 ken 引擎）。headless 对齐：卦的五行取**京房本宫**
  （`HEXAGRAM_PALACE_ELEM` 镜像星阙 `GuaConst.js Gua64[i].house.elem`），非上卦——32/64 卦两者不同；
  `hexElem(hex)` 用于 `left_elem`/`right_elem`/`main_relation`；aiExport 契约只有 本卦/六爻/潜藏/亲和 四段，
  星阙的 najia/六合/升降 UI 细节**故意**不进导出。
- **Python port**：`engine/decennials.py`（十年大运，星阙 `utils/decennials.js` 的移植）——JS `Math.round`
  是 half-up，Python `round` 是银行家舍入；每个 JS `Math.round` 用 `_js_round`（=`floor(x+0.5)`），L1 计数用
  `math.ceil`；动周期数学必对星阙 `decennials.test.js` 金标（`tests/test_decennials.py`）。
- **frontend-读数型 Python 移植**：planetaryages（读 `chart.objects`+`params.birth`）/ yearsystem129
  （`/chart` 需 `predictive` 真值才出 `predictives.yearsystem129`）/ persiandirected 等——读已算好的 chart
  对象再排版。**镜像上游文字用 `predictive_text`（上游单字名表 AstroTxtMsg + AstroMsg 回落），不用 `_astro_msg`**
  （后者是全名表，v0.40.0 前这几路因此印「太阳/子嗣点」）。persiandirected 应期日期原有的「≤1 天」偏差已消：
  根因是 moment `add(x,'days')` 把小数天四舍五入到整天，移植成 `timedelta(days=float)`；现按 `js_round` 取整天。

**恒星黄道/岁差标注**：`ASTRO_MSG` 不许硬编码岁差名——西占读 `chart.siderealAyanamsa`、印占读
`chart.siderealModeKey`+`ayanamsaValue`（**字段名不同**）；`chart.zodiacal` 是本地化字符串（"恒星黄道"），
不许 `== 1` 判断；nakshatras 在 `response.chart.nakshatras`，非顶层。

🔴 **`execution` 不是算源（v0.27.0）。** `ToolDefinition.execution`（`local`/`remote`）说的是「runner
在哪跑」，**不是**「谁算的」——`qimen` 是 `execution="local"` 而整盘由 ken 后端算。算源的唯一机读来源是
`contracts/technique_provenance.json`（七分类逐工具声明，本节这份普查的机读版），由
`verify_technique_provenance.py` 守：**新增技法不声明算源即红**；声明 `ken_backed` 的必须真调过
`_require_ken_pan`（反之亦然）；算盘端点必须已在 `_PYTHON_CHART_ENDPOINTS`。
**运行期实测优先于声明**：`data.technique_card` 以 `pan.source` / `jinkou.source` / `compute_sources`
为准，与声明不符时标 `matches_declaration: false`——ken 端点失败也回 200，静默回退正是这个形状。

**知识包（v0.28.0 起，v0.35.0 收紧）**：方法论手册域由 `scripts/gen_knowledge_packs.py` 从上游 HelpDoc 收割
（27 域/236 条，逐条带出处；幂等 = generated_at 取上游 commit 时间；**正文读上游 HEAD blob、不读工作区**，
出处与正文同源）；store 按 schema `horosa.knowledge.helpdoc.v1` 自动发现，**新增域零代码**。
**上游每一册 `*HelpDoc.js` 要么进 `HELPDOC_DOMAINS`、要么进 `EXCLUDED_HELPDOCS`（仅 fengshui，政策性排除），
第三种状态生成器直接 FAIL**——同步新技法时把它的手册一并收进来（v0.35.0 之前六册已上架技法的手册三个版本
没收）。上游改 HelpDoc 后重跑生成器即同步；hover 三域（astro/liureng/qimen）保持专用渲染分支不动。
**修生成的东西，就修生成器**：hover 三包的 `source` 曾在 v0.38.1 A16 手改产物成相对路径，生成器照写绝对路径，
v0.40.0 重跑即复发；现在 `build_hover_knowledge_bundle.mjs` 写相对上游根的 posix 路径 + 上游提交时间（同 commit 重跑逐字节一致）。

**同步守卫三层（缺一层就会静默漂）**：① `verify_upstream_sync.py` = vendored ↔ **上游 HEAD**
（版本恒等 + 哨兵 sha256 + core-js 逐文件；无上游树时 skipped 而非绿，release 链用 `--require-upstream`）；
② `verify_export_contract_mirror.py` = skill 常量 ↔ vendored（版本 + 技法键）；
③ `verify_export_section_baseline.py` = **段级欠账棘轮**，基线在 `contracts/export_section_debt.json`
（受 git 跟踪，新增欠账 fail、还清也 fail 提示 `--update-baseline`）。
**`MIRRORED_UPSTREAM_AIEXPORT_VERSION` 只表示「对账基准版本」，不表示「该版段全有了」**——键级对齐
不等于段级对齐（v0.23.0 曾据此宣称整版对齐而实欠 180 段）。两个数字必须一起读。

🔴 **版本恒等测不出新技法（v0.26.0）。** 上游明文纪律是「新技法键只加键、两把版本闸恒不动」
（`aiExport.js:306`）——`tianxing`/`qimenzeri` 都在 v50 不变时到货。唯一可能的信号是
`verify_upstream_sync.py` 的 **check 1b 技法键集合差分**（对着 `contracts/upstream_provenance.json`）。
两个方向基线不同：gained 并上「skill 已登记的键」（登记即已处理，检查自愈），lost 只对 recorded
（skill 合法持有 `acg`/`astrodata`/`wangji` 等上游无对应键）。
另两条同批教训：**上游 preset 条目可能在对象字面量之外**（后置 `AI_EXPORT_PRESET_SECTIONS.<key> = [...]`，
`_upstream_preset.py` 必须扫成员赋值，且跑在 spread 解析之后）；**provenance 只在全绿时写**
（红着写等于把失败洗成持久的「已核对」声明——v0.25.0 就这么发出去过）。

🔴 **四条会反复咬人的写法（v0.26.1 一次性踩齐）。**
① **`x is not None` 当守卫 = 解析失败即放行**（`_day_span` 让 `'…T00:00'` 跳过整个上限）——解析失败必须报错。
② **只读 payload 的某个子字段，不看顶层同名字段** —— schema 声明为顶层的东西 agent 一定会传顶层，
静默丢弃比报错糟得多。判据：**改这个参数，结果必须变**。
③ **只读 `snapshot_text` 不看 `data.ok`** —— 失败会回落 `generated_template`，产出一份假导出。
④ **materialize 一批 regex match 再拿旧偏移切新字符串 = 毁文件**（revendor 三处），边扫边改必须每轮重搜。
🔴 **「时好时坏」先怀疑缓存，别归因环境。** Java 农历按**年**缓存，一次带 lat 的请求焐热该年后，
同年的坏请求全都成功 —— 这让一个真 bug（占时传 `lat: null`）被当成「本机无 Mongo」整整一个版本。
诊断务必换冷年份。同理：**当「环境问题」开始解释越来越多的失败时，先怀疑自己的复现命令**
（少一段 PYTHONPATH 就能让 taiyi/jinkou/sanshiunited/wangji/taixuan/chunzi 一起红）。

🔴 **守卫的盲区比缺口更贵（v0.27.0，落后上游 4 个 release 而四把守卫全绿）。** 三条现行纪律：
① **「上游有 vendored 无」必须按每棵树的同步口径判**——`SENTINEL_TREES` 现在带 `copy` 语义
（`whole` 整棵 rsync / `per-dir` 逐目录 + 点名根级文件）。旧实现用 `split("/",1)[0]` 求 top，对根级文件
等于文件名自己，于是**上游新增的根级文件整类被丢**（实测漏掉 6 个引擎模块 / 5,512 行）。
**堵一个漏洞时要问：同样的错能不能在别的层级上再犯一次。**
② **键集比对必须双向**：`verify_export_contract_mirror` 只断言 `skill ⊆ upstream` 时，结构上抓不到
**新增技法**（哪怕 vendored 树是全新的）。反向差已补，要跳过必须写进 `UPSTREAM_ONLY_LEDGER` 并给理由。
③ **每个 `verify_*.py` 都必须被某个 runner 调用**（`tests/test_guard_wiring.py`）——挂不进 CI 的
（需要 vendored 树/上游 checkout 的）就必须挂进 `preflight_release.py`，否则它只是装饰。
配套：`--require-upstream --write-state` 不再自锁（staleness 是 `--write-state` 自身的补救动作）；
无上游时印 `state unverified since …` 而非 `state current`；FAIL 输出带总数 + `--full`。

⚠️ **Python 字典重复字面量键静默保留最后一个**——registry 的段表按主题分组、同一技法的条目散落几百行，
给某族补段时极易在别处再写一个同名键，前一份 list 直接消失（症状：「明明加了 optional 段，missing 还在报」）。
守卫 = `tests/test_export_tools.py::test_registry_tables_have_no_duplicate_keys`。

🔴 **点哨兵覆盖不全整棵引擎树（v0.26.0）。** 7 个哨兵一个都不在 ken 引擎目录内部，
`verify_vendor_runtime_sources` 又只查 REQUIRED_PATHS **是否存在**——于是「引擎文件在、但是旧的」
整类漂移无人看管，`kintaiyi/jieqi.py` 的全年份域修复（域外 ValueError 炸 taiyi/pan）就这么卡了一版。
守卫 = `verify_upstream_sync.py` 的 **check 2b 子树逐文件比对**（`Horosa-Web/vendor` 逐引擎目录 /
**整棵** `Horosa-Web/astropy` / **整棵** `Horosa-Web/flatlib-ctrad2`），三向都报。三条纪律：**比对口径必须
等于同步口径**（排除集逐条对齐 sync 脚本，否则对着故意没拷的文件恒红）；**守卫树集合 == sync 脚本整棵
rsync 的树集合**——加一条整棵 rsync 就加一棵树（v0.35.0 之前 flatlib 整棵拷却不比、astropy 只比两个子树，
tests/resources/根级文件全在盲区，v3.9.3 的 flatlib 三文件漂移零信号；
`test_every_tree_the_sync_script_rsyncs_wholesale_is_a_sentinel_tree` 锁步）；「上游有而 vendored 缺」只在
已 vendor 的顶层目录内部判，上游**整个新增的顶层目录**单独报一行（那是新引擎/新能力的信号）。
配套：审计权威清单是 `aiExport.js` 的技法表，**不是 kentang 服务注册表**——`qizhengelection`/
`xuanshi` 是服务不是导出技法，已进排除台账（有数据 ≠ 有技法）。

🔴 **vendor 树一律用 manifest 驱动，禁裸路径（v0.26.0）。** `revendor_core_js.py` 按上游父目录名
猜落点，对本树是错的（`utils/balbillus.js` 真身在 `vendor/astroextra/`），裸驱动会**分叉出重复树**
且 relocate 把 import 指回新造的那棵。唯一入口 = `contracts/vendor_manifest.json` +
`--from-manifest [--only 前缀]`；「还有什么没同步」= `--check` 全树 `unchanged`。
蓄意偏离必须**声明**（manifest 的 `stub_import`/`import_redirect`）或**机械化**（进 `transform()`）——
写在文件里的偏离，下一次重 vendor 必被抹掉（本轮 shuffle.js 的 node-forge 替换、
zhengchuan 的动态 JSON import 属性，都是这么被抹掉又被测试抓回来的）。
⚠️ 树里有**两个** `AstroConst.js`：`src/constants/`（151 行共享 shim，有 `SignsProp`/`LIST_SIGNS`）与
`src/vendor/constants/`（32 行 Uranian 子集，没有）。上游的 `'../constants/AstroConst'` 在 vendor 树里
恰好解析到后者 → 静默 `undefined`。一律 `import_redirect` 钉死。
⚠️ 「已 vendored」≠「是当前的」——查依赖要查新模块 import 的**具体符号**，不是查文件在不在。

**MCP 服务器面法则**（`surfaces/mcp_server.py`）：全部工具带 **tool annotations**（口径：openWorldHint
一律 False（local-first）；查询类 readOnly+idempotent=True；技法计算类 readOnly=False、destructive=False、
idempotent=False——默认写一条本地 run 记录，必须如实标注，目录审核会核）；澄清闸走 **elicitation 双轨**
（客户端声明能力→原生表单，「按星阙默认」一跳闭环、「补充设置」只回带备注**绝不代答术数参数**；
无能力/任何异常→逐字节回落 `agent_guidance.required` 错误往返；`HOROSA_MCP_ELICIT=0` 关闭）；
**签名即契约**：每个 MCP 工具**必须**显式设 `__signature__`——漏设会让 FastMCP 内省 `**kwargs` 造出一个
名叫 `kwargs` 的必填 string 参数，工具静默不可调用（`horosa_tool_run` 栽过，且它是 compact 模式的唯一
通道）。`__signature__` 优先级**高于** `__annotations__`：返回类型只能写在签名的 `return_annotation` 里，
写 `__annotations__` 是死代码。签名口径是「**广告保真、校验放松**」（FastMCP 注册时
`validate_input=False`，广告与校验解耦）：字段描述/枚举/`[required]` 标记照登，但一律 `default=None` +
`Annotated[Any, WithJsonSchema(...)]`，MCP 层零必填——否则 `request={…}` 逃生通道走不到、数字经纬度在
归一化前被拒、且都绕过 `agent_recovery`。内联 `$defs` 时**绝不能残留 `$ref`**（模型自引用会让 pydantic
构不出 arg model，服务器起不来）。

**决策层法则（v0.39.0，`src/horosa_skill/decisions/`，可选云端 TypeSafe Jev）**：本仓唯一会把用户文本送出本机的路径，
六条硬规则各有守卫：① `HOROSA_JEV=off`（缺省）= **零字节变化**——不建对象、不读 key、信封/卡片/instructions 逐字节等于
今天（`tests/test_decisions_service.py` 影子不变性）；② **代码持有权限，模型只供证据**：确定性路由是权威（S1 只在
`dispatch.no_matching_tool` 时可采纳兜底）、澄清门只接受「原话明说 + 词表证据 + conf≥τ」三钥齐的抽取（S2，永不替用户选
默认，铁律 2 不动）、S3 门类分错只多一段向导；③ 失败一律**关闭式**回确定性路径并经 `_degrade` 进 `envelope.warnings`
（三连败熔断 60 s，一窗一报）；④ 每次真调用自陈：`technique_card.decisions[]` / `DispatchEnvelope.decision_layer` /
开启时 instructions 改口（两态 ≤2048 字节由测试锁）；⑤ 数据边界：一档 `meta` 只送**本地脱敏**后的问题文本（日期/时刻/
坐标/地名/号码→占位符），二档 `snapshot` 才许导出快照且只给 S4/S5；出生数据永不以原值离机；key 只在调用时读、
永不入日志/异常/信封/生成配置；⑥ 阈值只认自家中文标注集测出的数——`enforce` 需 `contracts/jev_thresholds.json`
该面 `promoted` 且模型 id 一致，否则退 shadow；钉版 `jev-1.13.0`，`jev-latest` 只许影子，返回 id 不符本轮降影子。
问题构造点唯一（`decisions/surfaces/*`：instructions 英文为主（≤30% CJK，允许中文线索词）、选项键 ASCII、必带弃权项
——去掉弃权项时第三方评测准确率 0.95→0.00）。**每个面的整个决策块**（构造 + 调用 + 采纳）都在 `_decision_guard` 里，
护栏画在面的边界而不是网络 I/O 周围（v0.39.0 台账）。
新包的 raise 信息一律「中文 / English」字面双语：`verify_error_recovery.py` 棘轮按文件计数、`tests/test_decisions_governance.py` 对 `decisions/` 零容忍——v0.39.0 发布前 CI 因 28 处单语 raise 红过一次，本机全绿；push 前只认 `run_ci_gates.py`（§6 第 0 条）。
**评测与晋升协议**（`decisions/eval.py` + `scripts/jev_eval.py`）：金标集 `contracts/jev_eval/*.jsonl` 由
`scripts/gen_jev_eval_sets.py` 人工标注生成；真调用只在 `measure`，原始响应录进 `cache.jsonl`，`compile`/`check` 零调用回放；
τ 在训练集扫、留出集过**预注册闸** `PROMOTION_GATES`（改数字 = 改代码 + 留痕），全过才在 `contracts/jev_thresholds.json`
写 `promoted: true`；发版前 `jev_eval check`（数据集 sha / 模型 id / 回放闸）。首轮：dispatch τ 0.54 与 zhancat τ 0.86 晋升，
extract 因 ECE 0.104 > 0.10 未晋升（精度 1.0、填错 0）——闸差一点也是不过，别调数字凑。二档 S4 只读意见走
`service.faithfulness_opinion`，永不改 `report.ok`。

**错误也必须是信封**：技法/dispatch/tool_run 的错误路径返回 `ToolEnvelope`（含顶层 `code/message/details`
镜像），不是裸 dict——出参被 server+client 两侧校验，一旦声明 outputSchema，裸 dict 会被打成协议级
ToolError，**澄清闸当场报废**。structured output 由 `HOROSA_OUTPUT_SCHEMA=1` **显式开启，默认关**
（claude-code#25081：带 outputSchema 时工具列表静默消失，至今 stale-closed 未确认修复）；开启前须在真实
客户端 `/mcp` 确认工具计数不掉。依赖钉 `mcp[cli]>=1.28.1,<2`（SDK v2 是破坏性重写，单独跟踪）；
不新增依赖 sampling/roots/logging（2026-07-28 规范起废弃，本仓未使用）。elicit 必须在任何副作用之前
（v2 会重放整个工具函数）。

**Node 地板 ≥ 20.10**：数算 JSON 走 `import X from './x.json' with { type: 'json' }`；`src/tools/index.js`
顶层 import 使旧 Node **语法级**炸掉整个模块图（qimen/taiyi/jinkou/tongshefa 全挂，不只数算）。bundled
runtime 带 Node 22；`package.json` 声明 `engines.node >=20.10.0`；新加 raw-node JSON import 继续用
`with`（不用废弃的 `assert`）。

## 5. 新增技法 / re-vendor（集成决策树 + 布线清单）

**同步健康的权威判据（v0.31.0 教训）**：`AI_EXPORT_SETTINGS_VERSION` 锁步**不可信**——上游可以加段
不 bump 版本（v3.9.5 给 horary +9 段、常量原地 56）。判断是否漂移只认两个：
`verify_upstream_sync.py --require-upstream`（sentinel sha256）与
`verify_export_section_baseline.py --source upstream --require-upstream`（段级、preflight 同款）；
裸跑默认参数在这类失败上**恒绿**。手工件（curated 子集 / 声明了 `derived_from` 的 bespoke 抽出件）不走
流水线，靠 `vendor_manifest.json` 里的**源 sha 戳**看守：上游源一动，`--from-manifest` 与
`verify_upstream_sync` check 3 即红，逐一与上游现函数对过文本后
`revendor_core_js.py <src> --restamp <条目>` 才灭（v3.9.4 六亲两格就是在没有这条边时静默滞留了四轮）。
「caller 旧于 vendored 依赖」是它们的专属漂移形态。

**四分决策树**（新技法先归类，再动手）：

1. **后端已有 `/predict/*` · `/astroextra/*` 端点** → Python：`_call_remote` + Python snapshot builder；
   端点进 `_PYTHON_CHART_ENDPOINTS`。（端点是新版 runtime 才有 → 先 `sync_vendored_runtime_sources.sh`
   重同步 `vendor/runtime-source`；live 星阙实例先于 bundled runtime 可用是正常现象。）
2. **前端逻辑但只读已算好的 chart 数据** → Python 移植（复用 `_astro_msg` 等）。
3. **前端算法重 / 重推导风险高**（如 balbillus 247 行递归削减）→ **verbatim vendor JS**，import 指向
   shim/stub（如 `progConst.js` 仅 7 经典行星 + `LIST_SIGNS` + `AstroTxtMsg`，避免 vendor 1128 行
   AstroConst）；经 JS tool 按 `technique` → builder map 分发（`progextra` 模式）。
4. **整棵纯逻辑子树**（卜卦/择日 divination ~3200 行，无 React/antd、只有相对 import）→ 整树 vendor +
   一把正则给所有相对 import 补 `.js`（Node ESM 要显式扩展名）；薄 JS tool 调 `runHorary`/`runElection`；
   Python 铸 **traditional** chart（`tradition:1, predictive:0`）并把**整个** `/chart` 响应作为
   `payload.chart` 传入——`buildFacts(result)` 读 `result.chart.objects`/`result.objectMap`/`result.aspects`，
   只传 `chart.objects` 会崩。

**vendoring 变换规则**：

- **ken formatter 再同步**（dunjia/taiyi/jinkou）：拷星阙**全文件**，只做 headless 变换 = 兄弟 import 补
  `.js`；删 3 个后端 import（`request` / `{ServerRoot,ResultKey}` / `{buildKentangEndpoint}`）；**只**删
  `fetch*Pan` 网络 helper；**保留** `normalize*` 叠加函数。后端返回的「整段 sections」不许旧习惯性丢弃
  （taiyi 13 段解读曾被 `sections: undefined` 整体丢掉）——排查法：抓 `js_client.run` 实收的
  `ken_response` grep 段名，再决定透传还是重 vendor builder；透传段按「条件段双登记」处理。
- **数算 verbatim vendor**（canping/heluo）：整体照搬，仅两处改动 = 兄弟 import 指向 vendored 拷贝 +
  JSON import attribute（漏了 raw Node 报 `needs an import attribute of type: json`）。静态 / 动态相对 import 的 `.js` 与
  JSON 属性都由 transform 机械补齐（动态形态 v0.40.0 起；懒加载路径漏补时 loadcheck 恒绿、调用才空）。
- **闭包提取三陷阱**（六壬毕法/占断向导、政余格局这类纯模块级闭包，零 `this.`/React）：
  ① **常量引用与函数引用分开清点**——漏 `JiaZiList` / `ERFAN_SU_TO_BRANCH` 这类 module-level const →
  静默 `ReferenceError` 被 try/catch 吞掉 → 结果 null 无报错；② `SZConst.js` 在模块加载期读
  `localStorage` → **硬编码 no-op shim**（Node 25 实验性全局 localStorage 无 flag 会 throw，别探测
  `globalThis.localStorage`）；③ `AstroText.js` 的名称表用 `AstroConst.*` 常量做键 → shim 必须补齐闭包
  查到的每个 planet/node/point（含 `SignsProp` 这类表——v0.11/v0.13 两轮都栽在这）。draw-only import
  （GraphHelper/helper/LRShenJiangDoc）用 no-op stub 替换。vendor 后必须 `node -e "import('...')"`
  load-check **加**真数据整链跑（load 过 ≠ 真盘不崩；追 refCtx/三传是否真的非 null）。
- **stub 审计**（v0.40.0）：`stub_import` 之后，被 stub 掉的 import 绑定若仍被保留代码引用、且 stub 自身没定义同名
  绑定，`revendor --check` 即报 ⚠（`_stubbed_names_still_used`）——`LiuRengMain.js` 把 `ChuangChart` stub 成空，
  `buildSanChuanData` 的 `new ChuangChart` 抛 ReferenceError 被 try/catch 吞成 null，六壬择时对任何条件零命中。
  真不可达的引用（UI 草稿恢复链里的 `DateTime`）用「stub 定义同名、调到即抛明确错误」的类声明出来，不留空 stub。
- **curated 常量文件**（如 `vendor/liureng/LRConst.js`）：上游全文件 import 了 headless 不存在的路径时，
  **只追加新增的纯常量**，不整文件重 vendor；条目必须带 `upstream_sha256`，上游改了该文件就把子集里的每个
  值重新对一遍再 `--restamp`。**bespoke 抽出件同理声明 `derived_from`**（抽自哪份上游文件）——不声明它就
  对上游漂移永远失明（`zwLuckItems.js` 的干支年基准修正曾靠人读 release note 才补上）。
  **sha 看守不比内容**：`--restamp` 只证明「有人看过这一版上游」，不证明改动进了副本（v0.40.0：`SZConst.js`
  restamp 在 0604fa41 却仍是上游早已改掉的「魏」）。所以**能表达成「上游全文件 + 声明式 deviation」的手工件一律改
  verbatim**（truncate_before / stub_import / replace_text / import_redirect，`_reexport_required` 自动补调用方要的
  export）——`suzhan/SZConst.js`、`tongshefa/TongSheFaCore.js` 即此例；curated/bespoke 只留给真正的子集与重写件。
- **家族共享的隐藏旋钮放 mixin，不进 `BirthInput`**：广告层以「不在 BirthInput」判定子类自有字段，塞进 BirthInput 的键会把各子类
  已广告的同名键静默踢出 tools/list（v0.40.0 `after23NewDay` 事故，见 LESSONS）；用 `_ChartDayBoundaryKnobs` 一类 mixin + `ADVERTISE_HIDDEN`。
- **vendored JSON 数据与 `.js` 同等登记**：`horosa-core-js/src/vendor/**` 下每个 `.js` / `.json` 都必须在
  `vendor_manifest.json` 有条目（verbatim 对 JSON 即逐字节比对上游）；`test_every_vendored_js_and_json_file_is_in_the_manifest`
  守。v0.40.0 前 32 份 JSON 只登记 1 份，上游 v3.11.0 改 `hellenisticData.json` 日/月中年（39.5→69.5/66.5）零信号滞留。
  Python 侧若手抄了同一张表（如 `predictive_text.PLANETARY_YEARS`），测试要与 vendored JSON 互锚。
- **重同步 `vendor/runtime-source`**：`sync_vendored_runtime_sources.sh` + 显式 `HOROSA_SOURCE_ROOT`
  （对上游 READ-ONLY）。**顶层共享件必须显式补**：上游把子逻辑上提为 vendor 根级单文件时（如
  v3.5.0 全年份域的 `Horosa-Web/vendor/kin_year_domain.py`，被 16 个 ken/神数 引擎懒 import），逐引擎
  目录枚举的 sync 清单会漏它 → 重同步后**域外（BC/远期）请求静默 500**。守卫 =
  `verify_vendor_runtime_sources.py` 断言该文件 + vendored aiExport `AI_EXPORT_SETTINGS_VERSION >= 48`。
  raw vendor 起 chart 服务**不再 hard-fail**：`kentang/registry.py` 现用 `_LazyMountedService`
  （默认 `HOROSA_KENTANG_LAZY=1`），缺引擎只在首请求时响亮 500 + 下次重试；18 个 mount 引擎均在
  vendored 集内，无需再手打 graceful-kentang-mount 补丁（打包脚本仍对 staged 拷贝保留该分支以防旧树）。

**布线清单**（每个新技法照单走完）：

1. `schemas/tools.py` 输入模型（神数用 split 年月日时分 + `options` passthrough 的 `ShenShuInput` 模式；
   `BirthInput` `extra="allow"`，声明字段主要为 discoverability + guidance）。
2. `service.py` `_run_*_tool` runner；远端端点进 `_PYTHON_CHART_ENDPOINTS`；ken-backed 加 `_require_ken_pan`。
3. `engine/registry.py` TOOL_DEFINITIONS 注册；`router.py` 分派词做互斥检查（**卜卦含「卦」字**：梅易/卦
   分支必须排除 卜卦/horary/起卦/占问 短语，否则「卜卦问婚姻」误路由 `gua_desc`——同类新词照此办理）。
4. 导出契约：`exports/registry.py` preset **逐工具**对齐 builder 实际产段（权威清单 = `aiExport.js` 的
   `EXPORT_TECHNIQUES` + `EXPORT_PRESET_SECTIONS`，不是组件目录；照抄会多列 UI-only 死条目、漏列真产段）。
5. **条件段双登记**：可能不出现的段**同时**进 preset（出现时不算 unknown）**和** `AI_EXPORT_OPTIONAL_SECTIONS`
   （缺席时不算 missing）——单进 optional 不够（`exports/parser.py:130`）。段名不一致走
   `map_legacy_section_title`，快照 byte-identical，不改 vendored builder。
   **按 spread 派生的键（择日十技法 `<x>zeri` = 基底段表 + 择时三段）optional 集必须与段表一起从
   基底继承**（`ZERI_DERIVED_KEYS` 一处定义、两处循环）——只继承段表会把基底的条件段升格成派生键的
   必出段，离线全绿、live 才报缺段（v0.34.0+ 台账）。
6. 离线 fakes：`FakeClient`（HTTP 桩，覆盖新端点）+ `FakeJsClient`（新 JS tool handler）返回**真内容**
   —— 禁裸 `无` 段、禁 `generated_template` 回退；段头从真 preset 取而**不手抄**（手抄段头是「桩比真实
   响应更简单」的亚型，段头一改桩就悄悄对不上而测试照绿）。桩管形状，值级真相归 selfcheck 金标。
7. 测试三层：离线契约（全技法可调、export clean）+ live `@requires_chart`/`@requires_runtime` + golden/
   export-fixture。kinastro-9 无 live 测试 → 离线 + in-process srv（**中立 CWD** 跑，别 `cd $HW`——
   本地 `astropy/__init__.py` 会 shadow PyPI astropy）。
8. 版本与文档：§7 版本 bump 全覆盖；README×2 全景表加行 + SKILL.md 工具路由加意图行
   （CI `verify_docs_sync.py` 因缺行而红）；「段补到既有工具 ≠ 新工具」——工具数徽章不动，测试数照更。
9. **勿静默回退**：解析失败一律 raise 结构化错误，不许换默认值蒙混；快照失败 log + `snapshot_error`，
   不许裸 `except: pass`。同族陷阱：`f"{response.get('x')}"` 键缺失时产出字面 `"None"`（6 字符真值串）——
   先判空再格式化，`f"{... or ''}"` 只有显式 `or ''` 才安全。
10. **算源声明**：`contracts/technique_provenance.json` **只由** `scripts/gen_technique_provenance.py` 生成
    （契约 == 生成器输出，`--check` + `test_technique_provenance_generator.py` 守；别手改契约——经 helper 间接调用的
    证据写 `EXTRA_EVIDENCE`、逐工具说明写 `NOTE_OVERRIDES`，v0.40.0 前手改的条目重跑即丢）。
    `verify_technique_provenance.py` 不声明即红；ken-backed 必须真调 `_require_ken_pan`。技法依据卡按它标注「这盘是谁算的」。
11. **入 `TOOL_EXPORT_TECHNIQUE_MAP`**（v0.33.0 教训）：bench 的「新增技法自动获得用例」只覆盖这张表，
    runner 自己 `_augment_export_payload` 不经过它 → 功能全绿、bench 静默不覆盖。守卫
    `test_every_business_tool_is_in_export_technique_map`（工具 − 表 = 显式非业务清单）已锁死；
    新工具照样入表，别等守卫红。

12. **值级金标 + 边界纪律**（v0.33.1 · issue #15 家族，原文见 LESSONS）：**跨边界不改键**（原样透传是
    唯一被证明安全的形状；改键必在 `contracts/js_boundary_contracts.json` 留豁免与理由）。**每个本地 JS
    技法至少一条值级金标** —— 钉具体算出值而非段头/行数，期望值带权威来源注释，并附**负向对照**（把
    bug 改回去，金标必须红）；棘轮 `contracts/value_golden_debt.json`。参数接线**锚到引擎自带的词表**
    （`HORARY_PARAM_BY_KEY` / `ELECTION_PARAM_BY_KEY` / `BABYLON_SCHEMES`），不手抄会漂移的清单；认不出的
    键回执 `data.params_ignored`。**错误信号每上一层都要有人接**（JS 结构化错误 → Python enricher →
    `_warnings`）。统一判据：「改这个参数，结果必须变」。守卫 `verify_js_boundary_contracts.py` /
    `verify_value_goldens.py` / `verify_silent_returns.py` / `verify_schema_knob_wiring.py`——
    每把都要用**真 bug 注回去**验过：「守卫跑绿」≠「守卫抓得到它声称防的那个 bug」。

13. **re-vendor 抽壳纪律**（v0.34.0 · 上游把纯逻辑与 React 放同一文件时）：依赖闭包**按「已 vendored
    即停止节点」算**（天真闭包会把整个 UI 壳拉进来，数字差一个数量级，容易误判成「这支做不了」）；
    剥壳用 `truncate_before` 的**正则锚点**而非手抄（手抄件会静默落后 —— 仓里手抄的
    `buildSanChuanData` 比上游少一个参数）；截断必须跑在孤儿 import 清理**之前**（孤儿判据是
    「符号还用不用」，截断正是改变正文那一步；放后面则 UI 专用 import 全留下 → 加载即炸，
    而 re-vendor 看起来成功）。新技法接线后必查三处易漏：registry 的 `execution`
    （标 remote 会让通用远端路径抢先接管、runner 一次都不跑而工具照回 ok=true）、
    `AI_EXPORT_TECHNIQUES`（有 preset 不在表里 → parse 抛 Unknown 被吞成 export_snapshot=None）、
    provenance 分类（**兜底类别永远是「待人工确认」，不是「默认正确」**）。守卫报出的债务先问
    「是不是某笔已入账基底债务的继承」——解析器盲区造出的**假债务**会诱使人 `--update-baseline`，
    把常绿检查一次腌成永久噪声。

14. **手册随技法走**（v0.35.0）：上游每个技法页都有一册 `components/help/<X>HelpDoc.js`；技法上架的同一
    change 里把它加进 `gen_knowledge_packs.py::HELPDOC_DOMAINS` 并重跑生成器提交包——生成器对「既未收割
    也未明文排除」的手册 FAIL，`test_whitelist_and_packs_on_disk_are_the_same_set` 锁白名单与产物同步。

15. **新客户端 / 新传输的布线**（v0.37.0）：广告层默认**可移植**（每属性恰一个标量 type、array 必带
    items、无 `default/title/x-*`、不写 `additionalProperties: true`）—— 严格客户端见到违例是拒**整张
    工具表**，症状是「这个 server 在某某客户端里一个工具都没有」，不是「某个参数不好使」。
    每次 service 调用必须**卸载到工作线程**（FastMCP 1.x 不替你做，`async def` 里直接调同步体
    = 整个事件循环被占住）。分段循环必须 `_progress_tick`（既报进度也是取消检查点）。
    `maxSpanDays` 是**上限**不是旋钮，只能调低。新增客户端格式时同批更新 README×2 的
    Works-with 矩阵（`verify_docs_sync.check_client_matrix` 锁），并在 `client check` 的
    `_CLIENT_CONFIG_PATHS` 里登记它的配置文件位置。

16. **新客户端 = 三件套（v0.38.1 B2）**：① `CLIENT_PLACEHOLDER_WHITELIST` 里登记它**真的会展开**的 `${…}` 变量（按它的官方文档，
    不按别家的），`client check` 只放行这一表；② `_client_config_locations` 的路径表（全局 + 项目级，按 `_project_root()` 而非裸 CWD；
    Windows / macOS / Linux 三形状 + 它自己的覆盖变量如 `CODEX_HOME`）；③ 它的 per-server 超时 / 环境转发规则写进生成器**并**写进
    `client check`（Codex `startup_timeout_sec`/`tool_timeout_sec` + env 表两个绝对根；Cline / Zed `timeout`（秒））；同时加进
    `verify_runtime_live.CLIENTS`（九家全部在真机 lane 上 `setup` 一遍）与 README×2 矩阵行。配置文件允许注释的客户端（Zed / VS Code）
    走 `jsonc.upsert_server_entry`，绝不整文件重排。

**审计前置**（补「未同步技法」缺口前）：先 grep 仓内**明确排除项**（`fengshui`：canvas + 户型图上传 +
交互点位驱动，无 birth/time 输入，无法 headless——是政策性排除不是缺口），再确认候选的
`buildXxxSnapshotText` 是纯 `chart/data→text`（无 canvas/DOM/上传/点击依赖），过了 headless-readiness
闸再动手。上游有 engine 文件 ≠ 可进公开 skill。

## 6. 打包不变量（offline runtime packaging — 每条都咬过人）

- **运行期要读的仓内数据文件必须随 wheel / MCPB 走，代码不许假定源码树布局（v0.40.0 审计 P1）**：`parents[3] / "contracts"` 在 wheel 安装后指向 site-packages 的父目录，Jev enforce 因此在 v0.39.0 出货版里永不生效、技法算源恒「未标注」。三件套：pyproject `force-include` 进包内副本（`horosa_skill/contracts/`）、`horosa_skill/contracts_locator.py` 先源码树后包内副本、`scripts/verify_wheel_contents.REQUIRED_ENTRIES` 锁条目；MCPB 的 `.mcpbignore` 写 `/contracts/*` 再反选文件（父目录整体忽略时反选无效）；Dockerfile 要 COPY force-include 的源路径（`tests/test_dockerfile_matches_wheel_includes.py` 守）。
- **排除集四处同加，SQLite 日志侧车不是源文件**（v0.35.0）：`*.sqlite-wal/-shm/-journal` 是上游进程打开库
  留下的运行期文件，git 不跟踪、磁盘上有；sync 脚本 RSYNC_FILTERS、`verify_upstream_sync` TREE_EXCLUDE_SUFFIXES、
  `package_runtime_payload.sh` 与 windows/linux builder 的 `rsync_copy` 排除集**必须同时**列出它们——只在
  一处排除，剩下三处要么对着干净树恒红、要么把侧车打进包（首版 v0.35.0 darwin 包就带过一对）。
  以后排除集加任何一项，都在这四处同加。跨树比对/preflight 的输入一律用上游 **HEAD 的干净 checkout**。
- **flatlib 必须活过 strip**：`package_runtime_payload.sh` 保留 `flatlib-ctrad2/flatlib` 拷贝行，
  否则 bundled chart 服务 `ModuleNotFoundError: No module named 'flatlib'`。
- **python-strip 先 `-prune` `site-packages`** 再删 `test`/`tests` 目录：删了 `site-packages/astropy/tests`
  → kintaiyi `import astropy` 失败 → `/taiyi/pan` 挂载被**静默**跳过。
- **ken 依赖随包**：chart 服务在基础依赖外要 `bidict`(kinqimen)、`numpy`/`kerykeion`/`ephem`(kintaiyi)、
  `pendulum`(kinjinkou)；mac 内嵌 Python 已带，Windows `runtime/windows/bundle/wheels` 必须含。
- **`lunar-javascript` 随包**：两个 builder 都先在 `horosa-core-js` 跑 `npm install --omit=dev` 再拷贝
  （core-js 拷贝不排除 node_modules）；`verify_runtime_release.py` 两平台都必查
  `horosa-core-js/node_modules/lunar-javascript/package.json`。缺了 → canping/heluo 运行时才炸、其余照常
  启动（静默失败，只有 verifier 拦得住）。CI 同理：非 `@requires_runtime` 的 JS 测试要求 CI 先
  `npm ci --omit=dev`——新增此类测试时确认 CI 装齐了它的 node 依赖。
- **Windows `PYTHONPATH` 必含 `Horosa-Web/vendor`**（`start_horosa_local.ps1`）让 `import kinqimen/…`
  解析；两个 builder 都 bundle `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`。
- **graceful kentang mount**：打包脚本 patch **staged** `kentang/registry.py`，跳过未 bundle 的引擎
  （`_load_service` 裸 `__import__`，缺引擎会 hard-fail 整个 chart 服务）。
- **verifier 查真文件**：`verify_runtime_release.py` 的目录性要求（`swefiles/`、`astropy/`、`vendor/kin*/`）
  必须有严格位于其内的真实文件才 pass——空目录条目不算（手工 zip 曾以空 `swefiles/` 蒙混过关）。
- **Windows builder 禁 POSIX-only 二进制**：in-payload 拷贝用
  `shutil.copytree(src, dst/src.name, ignore=ignore_patterns(*excludes), dirs_exist_ok=True)`；
  不许 `rsync`/`cp`/`tar` 回潮（`rsync_copy()` 曾让 Windows builder 第一步 `FileNotFoundError` 死掉）；
  `download()` 用 `curl`（Win10/11 自带）。
- **下载缓存跨重建保留，但必须「按解析后的 URL 键控 + `.part` 落地」**：win/linux builder 开头只清
  `PAYLOAD_ROOT`（旧代码清整个 `BUILD_ROOT`，连 `downloads/` 一起删 → 每次重建重下 JDK 180MB + Node +
  CPython，改个启动器模板也要等一小时）。缓存一旦长存，原先靠「每次删掉」白拿的两条性质必须补上：
  ① `download()` 写 `<dest>.url` sidecar，**只有 URL 完全相同才复用**——固定文件名会把首次下到的
  JDK/Node 永久钉死；② 先下到 `<dest>.part` 再 `replace`，中断的 curl 不会留下截断文件冒充缓存命中。
  故 `latest_temurin_jdk_url()` 要**解析重定向**返回带版本号的真实 URL（API URL 跨 GA 恒定，不可作缓存键）。
  回归：`tests/test_builder_download_cache.py`。
- **Windows 启动器只许用 `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` 起，禁 `DETACHED_PROCESS`**：
  DETACHED 让子进程完全没有控制台，`powershell -File` 的主机拿不到控制台就 exit 0 且不写一个字节 ——
  启动器从未运行，manager 只看到「已退出且未就绪」报 `runtime.start_timeout`，且 `launcher.log` 空、
  无任何诊断（v0.37.0+ 台账，真机隔离实验）。「活过父进程」在 Windows 上本就免费。
  guard = `test_windows_launcher_spawn_never_uses_detached_process`。
  **推论**：改进程创建方式 / 启动器调用方式，CI 的 windows-smoke 验不到（它没装离线 runtime，走不到
  spawn 这一步）—— 必须在装了 runtime 的 Windows 机器上真起一次。
- **JDK 下载走 Adoptium API，禁 GitHub `releases/latest`**：temurin17-binaries 的 `releases/latest` 按
  tag 提交日期取，GA 刚打 tag 的窗口内平台二进制可能还没传完（jdk-17.0.20-ga 曾使 win/linux builder
  空手），`/releases` 列表顺序亦不可靠（老版本重发插队到最前）。下载 JDK 的 builder 一律用
  `api.adoptium.net/v3/binary/latest/17/ga/<os>/x64/jdk/hotspot/normal/eclipse`（只指向已存在的最新 GA
  二进制，`curl -fL` 跟随 307）；guard = `verify_builder_parity.py` 断言 win/linux builder 含该 URL 且
  不再引用 `temurin17-binaries/releases/latest`。
- **kinastro 只 vendor 引擎**：`vendor/kinastro` 带 `--exclude=tools`（26MB cities 地理库对干支神数无用）
  + `--exclude={ui,frontend,docs,wiki,examples,tests,…}` → ~31MB；`ensure_kinastro_path()` 上 `sys.path`
  使 `import astro.shaozi` 解析（streamlit 已在 bundled site-packages，`@cache_data` 无 runtime 警告无害）。
- **runtime 瘦身红线**：`pyarrow`(119M)/`pandas`(40M) 是 astropy 依赖（kintaiyi 要 `astropy.units`）
  **不可删**；streamlit 被 `kinastro/astro/*` 全线 import 不可删；**只有 `plotly`(40M) 可安全 strip**
  （streamlit-only + 懒加载，headless 不触发；已验 streamlit import + cetian 快照 + astropy.units 全 OK）。
- **Windows 启动器（`runtime_templates/windows/{start,stop}_horosa_local.ps1`）保住这些加固**：
  PID-ownership 检查（期望 exe 路径必须 `[System.IO.Path]::GetFullPath(...)` 归一再比——`$RuntimeRoot`
  含字面 `..` 而 `Get-Process .Path` 是 OS 归一化的，raw `-ieq` **永不相等** → stop 变 no-op 还删 pid 文件
  → 进程泄漏；改这俩脚本后必测 stop 真杀掉双进程）、端口冲突 ~2s 快败、stale/already-running 标记
  （manager 键控的 `pid files already exist`）、**降级就绪门（issue #14）**：双活 → exit 0；chart 活 +
  java **进程已死** → 秒级 exit 0 降级并打 marker `java backend process exited` + java 日志尾（manager 靠
  该 marker 把等待截短到 ≤20s）；chart 活 + java 慢 → 300s 窗尽头 exit 0 降级（java 之后可能自愈，doctor
  会转绿）；chart 不活 → throw（真失败）。该契约与 `manager._run_start_command` 的 chart-only 降级判定
  **锁步——改一边必改另一边**。Java 带
  `-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8`（Temurin 17 pre-JEP-400，OS 代码页会 mojibake CJK jar 表）。
- **两个 `.ps1` 模板必须存成 UTF-8 with BOM，且非 ASCII 只许出现在注释行。** manager 用
  `powershell`（Windows PowerShell **5.1**）跑它们，5.1 对无 BOM 的 `.ps1` 按系统 ANSI 代码页解码：
  UTF-8 的 `—`(U+2014) 在 CP1252 下末字节解成 **U+201D**，而 PowerShell 词法分析器**认花引号作字符串
  定界符** → 字符串截断 → parse error → 启动器未跑先死（`runtime.start_failed`，v0.25.0 补建实炸）。
  注释里的非 ASCII 无害，字符串字面量里的致命。守卫三层：
  `tests/test_runtime_launcher_templates.py`（BOM + 非注释行纯 ASCII，全平台；Windows 上再用
  `[Parser]::ParseFile` 真解析，CI `windows-smoke` 跑）+ 发布闸
  `verify_runtime_release.py::_assert_windows_launchers_are_bom_encoded`（直接验 zip 里的前三字节）。
  **wheel 里的副本另守**：v0.36.0 起 wheel 用户（`uvx --from <wheel> horosa-skill`）的启动器来自 wheel 内 force-include 的副本
  （`horosa_skill/runtime/templates/windows/`），`scripts/verify_wheel_contents.py` 断言该副本前三字节仍是
  BOM——源码树的测试管不到 hatch 打包这一步。
- **Windows 启动器的三条网络/路径不变量（v0.38.0 B1）**：① `Start-Process -ArgumentList` 不替你加引号——每个路径元素写成
  `('"{0}"' -f $Var)`，`--key=value` 旗标保持裸；② Java 行必须带 `--server.address=127.0.0.1`（Spring Boot 默认 0.0.0.0 =
  防火墙弹窗 + 局域网暴露；上游 mac 启动器已钉，守卫同时盯两端）；③ 写进 Python bootstrap 的路径用 `$(ConvertTo-Json $X -Compress)`
  （JSON 字面量 ⊂ Python 字面量），不用 `r"$X"`。守卫 `scripts/verify_runtime_scripts.py::audit_windows_launcher`（`--self-test`
  四种坏法必红）+ `tests/test_runtime_launcher_templates.py`（`C:\Users\张 三\…` 真渲染）。改模板先想「用户名带空格会怎样」。
- **launcher「假失败」已收敛（issue #14 降级门之后）**：无 Mongo/Redis 机器上 Java 连库重试可超就绪窗——
  现在 chart 就绪即 exit 0（java 慢 = 降级 marker，之后自愈则 `doctor` 转绿）。launcher 仍 throw = chart
  半边真没起来，按真失败排查（看 astropy.stderr 日志），不再有「throw 但其实都起来了」的假阳。
- **邵子 `完整条文`「條文待補充」是上游忠实回退**（该 id 方案不在 6144 条 CSV 覆盖内），mac/win 一致；
  别造假条文；粗 grep `條文待補充` 会假阳——验 `基础条文` 是真条文即可。`gen_shaozi_tiaowen.py` 必须
  `newline="\n"` 写 LF（保两平台构建字节可复现）。

- **清单要自证：URL 钉 tag、带 size；平台集只写在 `contracts/release_platforms.json`（v0.38.0 A3）。** `generate_release_manifest.py
  --url-base …/releases/download/v<ver>` 出的清单光靠自己就能判 pin-forward；`verify_runtime_release.py --expect-platforms` 断言键集恰好
  相等、`size` 等于真实字节数；`release-completeness.yml` 与 `sync_windows_release.py --check`（可 `--tag vX --draft`）都按契约的
  `since` 门逐平台判、缺项点名成 `[GAP: …]`（wheel 自 0.38.0 起必需）；README×2 平台表每个契约项一行，`verify_docs_sync.check_platform_table` 锁。
- **Windows 半边 = 从 darwin 种子派生，不再有「构建机专属输入」（v0.38.0 A2）。** `build_runtime_release_windows.py --seed <darwin tar.gz>`
  在任何主机（含 GitHub `windows-latest`）产出 win32-x64 载荷；`vendor/runtime-source/runtime/windows` 与 `prepareruntime` 不再是
  发布输入（`verify_vendor_runtime_sources.py` 不再要求，preflight 那一闸回到硬闸）。vendor 模式保留为构建机回退。
- **托管派生（seed + derive）的四条不变量（v0.38.0 A1）**：① 只从通过 `verify_runtime_release` 闸的 darwin-arm64 种子派生
  （`runtime_seed.verify_seed` 复用 REQUIRED_ENTRIES + 内嵌清单检查）；② 依赖集 = `contracts/runtime_python_lock.json`——种子的
  dist 集逐名逐版（pure 逐字节复制、native 同版本重拉或在目标 runner 从 sdist 编：pyswisseph / sxtwl 没有 cp312 Windows wheel），
  不跑解析器、不加包，scipy/plotly 进锁即红（`verify_runtime_python_lock.py`）；③ 派生清单只继承种子的版本/注册表常量，绝不自己
  stamp `export_registry_version`；④ 每个原生二进制（python/java/node/numpy）解包后过 `assert_binary_arch`——x64 载荷里出现种子的
  arm64 二进制必红。第三方工具链只从 `contracts/runtime_toolchain.json` 取钉死的 URL + sha（jlink 模块表也在那里），构建里不解析
  `latest`。
- **Dockerfile 与 wheel 的输入清单必须同步。** pyproject `force-include` 每加一个源路径，`horosa-skill/Dockerfile` 就得多一条 `COPY`，
  否则镜像里 `uv pip install .` 直接失败（v0.38.0 B0 抓到 `scripts/runtime_templates/windows` 漏拷；守卫
  `tests/test_dockerfile_matches_wheel_includes.py`）。

## 7. 发布协议（release law）

- **版本 bump 全覆盖**：发 vX.Y.Z 同一 commit bump 全部——`pyproject.toml`、
  `src/horosa_skill/__init__.py.__version__`（CLI `--version`）、`server.json`（×2）、`CITATION.cff`、
  **`horosa-core-js/package.json` 与 `package-lock.json`（含 `packages[""].version`，两处）**——
  core-js 随每个 runtime payload 分发、自带版本号，此前完全在锁步检查之外，v0.26.0 就漏了 lock
  （package.json 0.26.0 / lock 0.25.1，直到某次构建的 `npm install` 改写才暴露）——
  `README.md`/`README_EN.md` 的「当前公开版本」行（工具数/测试数一并更新）。bump 后 `git grep -n "<OLD>"`
  只应剩合法历史引用（CHANGELOG、台账、Windows 交接文档）。`docs/DATA_CONTRACTS.md` 的
  `tool envelope: <ver>` 是**独立** schema 版本，不跟包版本连动。CI 守卫：`verify_docs_sync.py`。
  ⚠️ **lock 只许字符串替换两处版本串，禁 `json.dumps` 整文件重写**——Python 默认把非 ASCII 转义成
  `\uXXXX`，下次 `npm install` 又按 npm 规范写回真 UTF-8，凭空造一个与版本无关的噪音 diff
  （v0.27.0 实踩）。
- **README 里的数字只有两种合法形态**：能从代码断言的（工具数、导出 technique 数）→ 当场在
  `verify_docs_sync.py` 里加断言；推不出又没测试覆盖的手测计数（如「memory / report N / N」）→ 改写成
  **不含数字的结构性陈述**。绝不留「只能靠人记得更新」的计数。测试数属第三类（要真跑才知道），故只守
  「两份 README 所有提及必须同一个数」（`check_test_count_consistency`）。**双语文档的守卫正则必须覆盖
  两种语言的标签**——徽章正则曾只写 `badge/tools-`，中文首页的 `badge/技法-` 整个漏出射程，工具数在
  83 上停了两代而 CI 全绿（v0.25.1，台账有原文）。
- **两个 runtime builder 永远锁步**：mac `package_runtime_payload.sh` 每一步都要有
  `build_runtime_release_windows.py` 对应步；`verify_runtime_release.py` 的 REQUIRED_ENTRIES 两平台对称
  （v0.10.0 曾 mac 侧加 shaozi 条文生成 + 验证项而 Windows 侧漏，win 构建会静默出占位条文还照样过验）。
  数字常量（`schema_version` / `runtime_layout_version` / `export_registry_version`）由
  `verify_builder_parity.py` 对**全部 manifest-stamping 脚本**（mac/win/linux 三 builder +
  windows/linux 两 scaffold，`CONSTANT_STAMPERS` 清单）N 路交叉断言；**且 `export_registry_version`
  另行锚定到源头常量** `exports/registry.py::AI_EXPORT_SETTINGS_VERSION`（`ANCHORED_CONSTANTS`）——
  N 路互证只证明「彼此一致」，五个 stamper 可以一致地错（v0.26.0 就是：registry 11→12，五个 stamper
  全留在 11，守卫照绿）。**改 registry 版本常量 = 同一 change 里 bump 全部 stamper**（CI 常跑；v0.16.1 曾 mac 单边
  bump 6→7、v0.22.0 前 linux+scaffold 曾滞留 6，均为该检查射程外时的漏网）。
  改一个 builder / 加一个必需 artifact = 同一 change 里 grep 另一个 builder + 两份 REQUIRED_ENTRIES；
  **新增 manifest-stamping 脚本 = 同一 change 里进 `CONSTANT_STAMPERS`**。
- **git 身份与 origin 滞留由 preflight 机器闸拦，不再靠人记**（v0.27.0+，两条都真实咬过）：
  `preflight_release.py` 现在先跑 `git_gate_failures()`——① `user.name`/`user.email` 未配或 email 是
  `…@主机名.local` 占位串（git 只在 commit 那刻才猜，作者串错了 GitHub 不归属任何账号）→ 阻断；
  ② fetch 后 `HEAD..origin/main` 非空（另一台机器的工作会被本次发布落下；此闸首跑当天就抓到
  构建机推的一个 commit）→ 阻断，离线 fetch 失败只警告。`git branch -u origin/main` 保持配置。
- **推送之后看 CI 结论；发布前 CI 必须绿（v0.38.0 教训：主干红了 19 个 commit 没人看）。** 本机全量门禁绿只证明「在维护机上绿」；
  `preflight_release.py` 的 CI 闸用 `gh run list --commit <HEAD>` 取 ci.yml 结论，非 success（红 / 未跑 / 进行中）即阻断，
  `publish_release.sh --draft` 同样先查。写新守卫时按三种 runner 的形状各想一遍：路径分隔符（`Path.as_posix()`）、行尾
  （Windows checkout 可能是 CRLF，守卫读 git 索引 blob 而不是工作树；`.gitattributes` 是仓库策略必须跟踪，曾被当本地配置 ignore 了
  一整年）、宿主 OS 决定的默认值（假归档要显式写全路径）、
  系统工具输出差异（托管 macOS 的 netstat 把别人的监听 socket 打成 CLOSED）。
- **发布 = draft → 托管派生 → 真机矩阵 → [OK] 才转公开（v0.38.0 A5）。** 维护机只做 seed：`scripts/publish_release.sh`
  （payload → darwin manifest（本地校验用）→ **SBOM** → MCPB → **wheel** → SHA256SUMS → verify；`--draft` 把 seed / .mcpb /
  wheel / SBOM 放上 **draft** release，**永不上清单、永不建公开 release**；`--dispatch` 触发 `release-runtime.yml`）。
  流水线：`resolve`（draft 上有 seed）→ `build-windows`（windows-latest `build_runtime_release_windows.py --seed`）→
  `assemble`（`verify_runtime_python_lock --seed`、双平台清单钉 tag + size、`verify_runtime_release --expect-platforms`、
  SHA256SUMS、SBOM、上 draft、`attest-build-provenance`）→ `matrix`（`runtime-matrix.yml` 三台真机装→起→四引擎→
  ——三 lane **都阻断**，含 windows-11-arm（dry run #4 全绿后转阻断；`arm_nonblocking=true` 只是单次逃生口）→
  `setup` 四客户端→live pytest→停）→ `publish`（`sync_windows_release.py --check --tag vX --draft` 必 `[OK]` →
  `gh release edit --draft=false --latest` → `gh workflow run release-completeness.yml`（GITHUB_TOKEN 产生的 release 事件不触发任何
  workflow，completeness / publish-pypi 都得由 publish job 显式 dispatch）→ 再 `--check` 公开 latest）。**清单只在两平台齐了才上到 release**——「缺半」
  窗口从根上消灭；`dry_run=true` 以公开资产为 seed 走完全程不上传（流水线自己的验收）。形状锁
  `tests/test_release_pipeline_shape.py`（只手动触发 / 不 `gh release create` / publish 必 needs matrix / draft 不带清单）。
- **publish 必须与 matrix 同字节，且矩阵必须真下载（v0.38.1 R1/R5）。** `publish=true` 没有 `run_matrix=true` 在 resolve 直接 fail；
  publish job 不接受 skipped 的 matrix；翻公开前 `verify_matrix_digests.py` 把三条 lane 的 `installed_archive_sha256` 与 draft 资产的
  GitHub `digest`（退路 SHA256SUMS.txt）逐一比对。release / dispatch / schedule 模式的 lane 一律通过**公开清单 URL** 安装（安装器自己的
  下载链），lane-report 必须带 `download.bytes > 0`——「lane 传了 file:// 就以为验过下载」是 v0.38.1 复审抓到的盲区。翻公开后
  publish job 再 dispatch 一次 release 模式矩阵。
- **publish job 的每一步都要先在真 draft 上跑过（v0.38.1 发布期）。** draft 对 `GET releases/tags/<tag>` 返回 **404**——draft 期的一切
  API 读取走列表端点（`releases?per_page=100` + `--paginate` + `select(.tag_name == …)`）；completeness 里仍用 `releases/tags` 是对的，它只读已公开的 latest。
  job 级 `permissions:` **整块替换** workflow 级：publish job 翻公开后的 `gh workflow run`（completeness + release 模式矩阵）需要 `actions: write`
  ——v0.38.0 公开时这两步还不存在，它们第一次真跑就是 v0.38.1（这次两条后续 run 的 triggering actor 都是 `github-actions[bot]`，路径已证）。
  `test_release_pipeline_shape.py::test_publish_requires_the_matrix_and_the_same_bytes` 锁两条。**tag 只在 release 仍是 draft 时允许重指**
  （draft 矩阵抓到产品缺陷 → 修 → 删 tag 重打 → seed / .mcpb / wheel 从新 commit 重建，`server.json` 的 mcpb sha 回填来自同一次 `--draft`）；公开后永不移动。
- **schedule 首跑要观察（v0.38.1 R2）。** GitHub 的整点 cron 槽会延迟或丢弃（2026-09-14 的 03:00 槽 5.5 h 后才跑），矩阵 cron 放在
  `23 4 * * 1`，`release-completeness.yml`（6 小时一次、稳定）的 `weekly-matrix-kick` 在 6 天无矩阵运行时 dispatch 一次。README 平台表
  写「每周巡检」之前，先观察到一次 `schedule` 事件的 release 模式矩阵跑绿。
- **发布步骤只允许以脚本形态存在**（v0.27.0：SBOM 生成器一直在仓里、却因发布流程是手打清单而漏传）：
  维护机半边一律走 `scripts/publish_release.sh`（步骤见上；无参数是安全默认，只构建校验）。资产契约由
  `release-completeness.yml` 断言（manifest 双平台 + 两包可达 + **SBOM 在场** + **`.mcpb` 在场**）。
  `.mcpb` 是 Claude Desktop 的一键安装包（`scripts/build_mcpb.sh`：validate → pack → sha256），
  它的 sha 要回填进 `server.json` 的 mcpb package —— 那条 URL 必须指向**当前**版本的 tag，且 sha 必须来自**真正上传的那一次**
  `--draft` 构建（mcpb 打包不可复现；v0.38.0 首发漂过一次，`release-completeness.yml` 现在把发布上的 mcpb sha 与 main 的
  server.json 对齐），
  否则升级后客户端装到的还是旧包（`verify_server_json.py` 逐个 package 查，不只查第一个）。
  Windows 半边由流水线派生；构建机 vendor 模式 `sync_windows_release.py --upload` 只是托管路径不可用时的后手，
  判据始终是 `--check` 的 `[GAP]`/`[OK]`。
- **发 tag 前必须在有上游 checkout 的机器上跑 `scripts/preflight_release.py`**（`HOROSA_SOURCE_ROOT`
  指向 Horosa-Public）。跨树两闸（`verify_upstream_sync --require-upstream`、
  `verify_export_section_baseline --source upstream --require-upstream`）**只有那里能做真**——
  `ci.yml` 里的同名 step 不带 `--require-upstream`，无上游 checkout 时自报 skipped。
  `release.yml` 曾挂在 `push: tags` 上号称覆盖这两闸，但仓库注册的 self-hosted runner 数是 **0**，
  v0.9.2→v0.25.0 的 **20 次 tag 触发全部排队 24h 后被自动 cancelled，零 step 执行**；该 workflow
  现已改为**仅 `workflow_dispatch`**，不再制造「看起来在跑」的假覆盖。preflight 成功会重写
  `contracts/upstream_provenance.json`（v0.26.0 起取代 vendor_sync_state.json，超集：另记上游 commit /
  应用版本 / preset 键集 / core-js 树摘要），**该 diff 就是跨树核对真发生过的 git 证据，随发布一起提交**。
  没跑 preflight 时，`verify_upstream_sync.py`（CI 里那次）会打 `::warning` 指出
  state 里的 `skill_mirrored_version` 已落后于 registry 常量——**看到这条 warning 就说明镜像在无跨树
  核对的情况下前进过**（v0.25.0/v0.25.1 就是这个状态：state 记 48、常量已 50）。
- **发布完整性三失效模式**（完整案例史：[`docs/LESSONS.md`](./docs/LESSONS.md)「发布完整性编年」）：
  1. **缺半**：`latest` 只有 darwin 半（v0.10.0–v0.16.0 每个 minor 都犯过；v0.10.0 连 manifest 都没有，
     双平台 install 全断）→ `release-completeness.yml`（release/schedule/dispatch 事件）会红，信它。
  2. **repack**：mac 侧重打 win zip 只换 embedded manifest（v0.16.1 首次双平台完整 latest 即此法）——
     仅当 release diff **无 payload-affecting 变化**（horosa-core-js / vendored 引擎 / wheels / launchers；
     skill 层 Python/docs 无妨）才合法；新版本出现可疑同尺寸 win zip 时，range-read 校 embedded manifest
     的 version + `export_registry_version` + 该 diff 条件后再信。
  3. **pin-forward（最隐蔽）**：新版 manifest 列了 `win32-x64` 但指向**上一版** zip（v0.17.0/v0.18.0 均
     钉回 v0.16.1）——guard 绿、install 不炸、sha 也对，Windows 用户静默拿到落后 N 版的 runtime。
     **检测**：`sync_windows_release.py --check` 找版本专属 `horosa-runtime-win32-x64-vX.Y.Z.zip`，
     缺 → `[GAP]`（**权威，无视 guard 颜色**）。
- **修复一律**：Windows 构建机 `git pull` 到发布 commit → `python scripts/sync_windows_release.py`
  （默认 build+verify 无副作用；`--upload` 才执行 构建→拉 darwin→双平台 manifest+SHA256SUMS→
  `verify_runtime_release.py`→上传 全链；幂等，已同步则 no-op exit 0）。
  **`git pull` 刷不到 vendor**：`vendor/runtime-source` 是 gitignored 本地构建输入，跳版必先从当前
  Windows workspace 重灌，否则打出落后一轮同步的引擎而 `verify_runtime_release.py`（只查文件在不在）
  照样绿。闸已内建：`sync_windows_release.py` 的 `preflight_vendor_sources()` 在 builder 之前跑
  `verify_vendor_runtime_sources.py` **和** `verify_export_contract_mirror.py`，任一红即拒绝构建
  （两把都要——上游「只加键纪律」下版本恒等在陈旧树上照样绿，只有 mirror 的逐键覆盖判得出）。
  **且每个上游新子树都要有真文件标记**：三把验证器（vendor 源 `REQUIRED_PATHS` / 发布归档
  `REQUIRED_ENTRIES` / parity `REQUIRED_ON_BOTH`）各点名一个该子树独有的文件（v3.5.1=`ifa_odu.json`、
  v0.32.0=xuanshi sqlite、v3.10.0=`astrostudy/{qizheng,india}_election_scan.py`）——没有标记的子树，
  陈旧树在版本恒等下照样绿（v0.34.0 补 Windows 半边时实测）。
  **推论**：新增只挂 CI 的守卫时，先问这条路径 CI 走不走得到；Windows/离线 runtime 是 off-CI 产物，
  必须在其本机入口脚本里复跑同一把守卫。发布通常已是 `latest`，补传即恢复
  Windows install（无需 flip）。pin-forward 跨「引擎升级」版（如 v0.17 新增 `/location/acg` 占星地图、
  `/astroextra/relative`、名人库 `astrodata-aa.sqlite.gz` ~50MB）时：先从**当前** Windows workspace 重灌
  `vendor/runtime-source`，再 native-verify 新端点回真数据才打包。
  **判源树新旧一律按内容，不看目录 mtime**：目录 mtime 只在直接子项增删时变，嵌套更新不冒泡——
  v0.27.0 那次 workspace 的 `astropy/` 顶层 mtime 停在 07-03（比 08-13 的目标版旧一个月），内容却已是
  上游 v3.9.1。判据用三样：① 本版新增的 `require_path`/`REQUIRED_ENTRIES` 目标文件在不在
  （如 `vendor/kin_year_domain.py`、`geomancy/data/ifa_odu.json`）；② 新端点名 grep 得到
  `astropy/websrv`（如 `electionscan`/`chart12`/`ephemeris`/`draconic`）；③ 构建后 native-verify 这些端点
  回真数据。缺任一 → 源树真陈旧，先重同步 workspace。
- **首诊命令**：`gh release view vX.Y.Z --json assets`（应见 darwin tar.gz + win32 zip +
  runtime-manifest.json + SHA256SUMS.txt）+ 确认 `releases/latest/download/runtime-manifest.json` 同时含
  `darwin-arm64` 与 `win32-x64`。
- **托管 runner 可以起 runtime——但只在 `release-runtime.yml` / `runtime-matrix.yml`，绝不在逐 push 的 `ci.yml`**
  （v0.38.0 A5 改写；此前的「CI 起不了 runtime」写于只有 Linux runner 的时代）。`ci.yml` 仍是离线 FakeClient 契约 +
  export-fixture 契约 + core-js JS golden，别在它里面造「boot runtime」job；真机证据来自矩阵三 lane
  （macos-latest / windows-latest / windows-11-arm，`scripts/verify_runtime_live.py`：chart-only 降级在任何 lane 都算失败，
  live pytest 的闸门 skip 理由不得出现）。**维护者本机 live 全套仍是 tag 前闸**（§8），矩阵是发布前的第二道、每周一次的第三道。
- **合并后查冲突标记**：每次 fetch/ff 后 `git grep -nE '^(<<<<<<<|=======|>>>>>>>)'`（v0.11.0 曾把
  `>>>>>>> <sha>` 留上 main）；`verify_docs_sync.py` 在 CI 里也查。

## 8. 本地验证与排障

- **tests/ 里起 node 的子进程必须 `encoding="utf-8"`（v0.40.0 首推 windows-smoke 红）**：`text=True` 在 Windows 按控制台代码页解，CJK 金标 JSON 直接 UnicodeDecodeError；`tests/test_subprocess_encoding.py` 的 node 扫描守着（负向对照），本机 macOS 复现不了，只有 Windows job 抓得到。
- **工作流 / 文档里的计数必须有真值文件（v0.40.0 首推 CI 红）**：ci.yml 的 stdio 探针工具数从 `contracts/mcp_list_budget.json` 读（`full_tools` / `compact_tools`），README 客户端表的「全量 N」由 `verify_docs_sync.check_full_surface_counts` 对同一契约锁；`run_ci_gates.py` 不跑「wheel 真起 stdio」两步，推之前核它们的断言值。
**验证流程**：

0. **push 前跑 `uv run python scripts/run_ci_gates.py`**——它解析 `.github/workflows/ci.yml` 的 `test` job，把同样的
   `uv run …` 门禁（pytest + 全部 verify_* + knowledge index + benchmark smoke）按 CI 形状在本机跑一遍。只跑 pytest +
   docs-sync 不算数（v0.38.0：主干红了 19 个 commit，本机每次都「全绿」）；push 之后再看 `gh run list` 的结论。
   🔴 **不要 `for g in scripts/verify_*.py` 裸跑全部脚本**（v0.38.1 发布后本机误跑过一次）：`verify_runtime_live.py` 是**真 lane**（下载 ~730 MB、
   起服务），`verify_matrix_digests.py` 需要 publish job 的输入。门禁的本机镜像只有 `run_ci_gates.py`；本机跑 lane 要显式传参、自己决定。
1. venv 坏了先修（miniconda symlink 触 macOS library-validation on `pydantic_core`）：
   `uv venv --clear --python-preference only-managed --python 3.12 && uv sync`（uv-managed CPython 无
   library-validation）。
2. **live 验证必须打本仓 vendored 引擎实例，不是默认端口上恰好在跑的东西**——默认 `:8899`/`:9999` 上的
   常驻服务不保证与 vendored 引擎同版本，甚至可能**根本不是本仓的树**（v0.27.0 审计当天实测过一次，
   靠 lsof 偶然发现；从它读回的任何值都不可信）。两道制度化（v0.27.0+）：
   ① **起法只走脚本** `scripts/start_vendored_instance.sh`（封装三段
   `PYTHONPATH=<vendor>/Horosa-Web/{flatlib-ctrad2,astropy,vendor}` + **内嵌解释器**
   `runtime/mac/python/bin/python3` + 非默认端口 + 就绪判据 `kentang prewarm ready … failed=0`，
   不达标自动回收不留半死实例；`--with-java` 连 Java 一起起；打印可直接粘贴的 env 行）。
   停 = `stop_vendored_instance.sh`，只按 pidfile 的 PID。
   🔴 手打的历史坑仍然成立：少 `Horosa-Web/vendor` 那段 → ken/神数引擎全挂不上，
   taiyi/jinkou/sanshiunited/wangji/taixuan/chunzi 一起红，症状像「这些技法坏了」；裸 `python` → 缺
   9 个只装在内嵌 python 里的依赖。v0.26.0 整轮误判正是栽在手打命令上——所以起法收进了脚本。
   ② **live 门禁只认显式点名的实例**：`HOROSA_CHART_SERVER_ROOT`/`HOROSA_SERVER_ROOT` 未设时
   live 测试一律 skip 并给出起法指引，**连 TCP 都不去碰默认端口**（对来源不明的栈连「在不在听」
   都不该问）。java 只起半边时把 `HOROSA_SERVER_ROOT` 显式指向不可达地址，别留空。
3. **防陈旧闸**：chart 心跳 `GET /` 回显 `pdSyncRev`，断言 == 当前 rev（当前 `pd_method_sync_v15`，见 tests 的 PD_SYNC_REV 常量）再信
   结果——陈旧引擎会把未知时间钥匙**静默按 Ptolemy 算**。钥匙分叉探针用每盘真算的 Kepler，别用 Kündig
   （静态标度 1.0 与 Ptolemy 同日期，探不出分叉）。**kentang 懒挂载**：`registry.py` 用
   `_LazyMountedService`（`HOROSA_KENTANG_LAZY=1`），缺引擎/坏引擎不再启动即炸，改为**首请求**才 500 —
   所以启动后必须**逐 mount 打一次真请求**（至少 `/geomancy/reading` `/taiyi/pan` `/shaozi/pan` +
   任一新端点）强制加载，确认无 `KentangServiceLoadError`，替代旧「启动即知」信号。
4. `uv run pytest`：`@requires_runtime` / `@requires_chart` 集成测试在服务 down 时 **skip**——带 skip 的
   全绿**不是完整验证**；服务全起时 0 skipped 才是最强信号。验收 = 各技法产出 aiExport 段 + 干净导出契约
   （`missing_selected_sections == []` 且 `unknown_detected_sections == []`；election 等条件段技法按
   optional 白名单放宽）。**反向陷阱：维护机装着 runtime，会让「其实依赖 runtime」的离线测试恒绿，
   只有 CI（唯一无 runtime 的环境）才炸**——离线/线材契约测试**禁以「算成功」为判据**（那是
   `@requires_runtime` 的活）；`tests/test_mcp_contract.py` 已用 autouse fixture 把 `HOROSA_RUNTIME_ROOT`
   钉到空目录强制与 CI 同形，发版前另跑一遍 `HOROSA_RUNTIME_ROOT=<空目录> uv run pytest` 复现该形状。
   **并行 agent（worktree 隔离）建在当前目录所在的仓**：派发前先 `cd` 回本仓（v0.40.0 一次因 cwd 在上游源码树里，worktree 被建进只读的
   Horosa-Public）；agent 规则首条是 LOCATION CHECK（toplevel 不在本仓 `.claude/worktrees/` 下即停手）。
   **live 复验同样要钉 JS 引擎**：只把两个后端 URL 指到 vendored 实例时，JS 技法走的是**已装 runtime 的旧 core-js**
   （解析顺序 `HOROSA_CORE_JS_ROOT` → 已装 runtime → 本仓），测的根本不是本仓代码（v0.40.0 据此误报过 jinkou/qimen
   缺段）。`tests/conftest.py` 已为 pytest 会话钉 `HOROSA_CORE_JS_ROOT=本仓`；手工脚本 / harness 自己钉（或 `HOROSA_RUNTIME_ROOT=<空目录>`）。
   **⚠️ 只钉 runtime root 不够**：默认端口上若有活服务，请求照样打通，本该失败的错误路径会成功
   （`test_error_paths_return_a_conformant_envelope` 实测在服务起着时红）——要真与 CI 同形，
   **必须同时把 `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` 指到不可达地址**。
5. **Java 侧是否可用，判据取「skill 正规路径」，不是裸 HTTP**（2026-08-05 实测纠正）：
   **裸 `curl`/`httpx` 打 `/nongli/time` 任何载荷形状都回
   `{"ResultCode":9999,"Result":"no.register.app.in.sys.forapp"}`——包括那些经 skill 调用完全成功的
   载荷**，所以裸探针会把好路由误判成坏的，不可作判据。原因是裸探针没带 `ClientApp`/`Signature` 头：
   注册表是 jar 内 classpath 的 `data/rsakey.json`（`RequestHeaderInterceptor` 核 ClientApp + SHA-256 签名），
   **与 Mongo 无关**（v0.36.0 收尾实锤，本机 Mongo 里根本没有注册表）。`_call_remote` 带 app 注册归一化，经它
   （或 `service.run_tool`）打才作数：实测本机 `doctor issues: []` + live 382 条通过，其中大量走 Java。
   `doctor` 只探 `/common/time`、`selfcheck` 的 compute 步骤有 issue #14 的 chart 侧回退，
   两者仍不足以证明 Java 族技法可用——**要证就跑一条真 Java 技法**（如
   `service.run_tool("nongli_time", {...带 lat...})`）。
   **`ResultCode 9999` 是通用失败码、不是 `no.register.app` 的同义词**——必读 `Result` 原文再定性：
   `no.register.app.in.sys` = 注册/环境；`begin 1, end 3, length 1`（或 mac 侧看到的 `200001`）
   = 请求缺 `lat` 的上游输入处理崩溃，与 Mongo 无关；`Timed out … waiting to connect … mongodb.host`
   = **实例起法错**（裸 `java -jar` 用 jar 内写死的 `mongodb.host`），不是「本机无 Mongo」——按上游桌面模式起
   （`--mongodb.ip=127.0.0.1` + `HOROSA_DESKTOP_MONGO_OPTIONAL=1` + `HOROSA_MONGO_FALLBACK_DIR` + `needtranslog=false`，
   `start_vendored_instance.sh --with-java` 已内置）后无 Mongo/Redis 也全 Java 族真数据（v0.36.0 收尾实锤，
   本 Mac 首次 0-skip 全量 live 678 绿）。`_java_result_code_hint` 已按此三分判别，
   认不出的 9999 只给中性提示（v0.26.1+ 台账）。
   **缺 lat 的失败会「时好时坏」**：Java 农历结果按**年**缓存，任何一次带 lat 的请求会焐热该年，
   此后同年无 lat 请求全部成功——复现必须换**冷年份**（v0.26.1 已给五个占时工具加
   `tool.<name>_cast_geo_required` 前置闸，缺谁报谁）。
6. **`pkill` 法则**：bundled 与 live 星阙都跑 `webchartsrv.py`——`pkill -f webchartsrv.py` 会连星阙
   `:8899` 一起杀。按端口/PID 停；stop 脚本已按 runtime root 限定 kill 范围，保持住。

**症状速查表**：

| 症状 | 根因 | 处置 |
| --- | --- | --- |
| qimen/taiyi/jinkou `source: null` 或结果与星阙不一致 | 安装的 runtime pre-ken，`js_client` 落到本地脚手架 | 重装匹配 runtime；开发用 `HOROSA_CORE_JS_ROOT="$PWD/horosa-core-js"`（解析顺序：env → installed manifest → 包内 bundled） |
| HTTP 200 但 `ResultCode -1/1`、`Result` 是字符串 | ken 引擎异常被包成 200 信封 | `_require_ken_pan` 会拦 → `tool.ken_compute_failed`；查 `:8899` 日志 |
| `agent_guidance.required` / `details.agent_recovery` | 澄清闸生效（设计行为） | 按 SKILL.md：用 `prompt_to_user` 问用户，答后 `agent_confirmed_settings: true` |
| 神数探针看似空 snapshot | 读了顶层键，真身嵌在 `Result.snapshot` | 读 `Result.snapshot` / `Result.source`（skill 的 `_call_remote` 会解包 `Result`） |
| `Cannot find package 'lunar-javascript'` | `horosa-core-js` 未装 npm 依赖 | `npm ci --omit=dev`；打包/CI 已内置该步 |
| `needs an import attribute of type: json` / 全 JS 工具集体语法炸 | PATH 上 Node < 20.10 | 用 bundled Node 22（`engines` 已声明地板） |
| pytest 全绿但 `requires_*` 全 skip | 本地服务没起 | 起 vendored 实例（上面第 2 步）再跑 |
| 本地 pytest 全绿，CI 上离线测试红在 `runtime.not_installed` | 维护机装着离线 runtime，测试其实一路真算；CI 是唯一无 runtime 的环境 | 该测试要么进 `@requires_runtime`，要么改成不以「算成功」为判据；`HOROSA_RUNTIME_ROOT=<空目录> uv run pytest` 复现 CI 形状（§8 验证流程 4） |
| `pydantic_core` dylib/签名报错 | miniconda symlink venv 触 library-validation | `uv venv --clear --python-preference only-managed --python 3.12 && uv sync` |
| `uv run pytest` 报缺新 API（如 `mcp.types` 无 `Icon`）而 `python -m pytest` 正常 | 仓库搬家后 `.venv/bin/*` shebang 仍指旧路径 → 静默回退全局 pytest（旧依赖环境） | 同上重建 venv；判据 = 直接跑 `.venv/bin/pytest` 报 `bad interpreter` |
| 新时间钥匙/新参数结果与 Ptolemy/默认完全一致 | 长驻旧 chart 进程静默吞新键 | 心跳核 `pdSyncRev`；重启 vendored 实例 |
| `/predict/pd` params 回显 = 你送的白名单外值 | 回显是原样输入，引擎内已回退 core_alchabitius | 快照如实标注「未核验，引擎回退 Alcabitius 半弧法」，不静默换标签 |
| Windows 启动器超时 throw 但服务随后可用 | Java 连 Mongo/Redis 重试超 readiness 窗 | 忽略 throw，poll `doctor` / 双端点几分钟 |
| `runtime.start_failed`，stderr 是启动器**自己的** parse error（`Missing closing '}'` / `string is missing the terminator`） | `.ps1` 无 BOM → Windows PowerShell 5.1 按 ANSI 解码，非 ASCII 字符变 U+201D 被当成字符串定界符 | 模板存成 UTF-8 with BOM + 字符串字面量纯 ASCII（§6）；`uv run pytest tests/test_runtime_launcher_templates.py` 定案 |
| release guard 绿但 Windows 用户拿到旧功能 | pin-forward（manifest 指旧 zip） | `sync_windows_release.py --check` 定案 → §7 修复流 |
| 仓里冒出 `${env:HOME:-${sys:user.home}}/.horosa-logs/…` 目录 | dev 启动器裸跑未补丁的 vendored jar，log4j 的 basedir 没展开 | 已修（`extract_log4j_config.py` + `-Dlog4j2.configurationFile`）；`-Dbasedir=` 覆盖不了它。守卫 `verify_no_stray_runtime_dirs.py` |
| 结果段缺失，客户端想报「缺依赖」 | 幻觉依赖风险 | 按 SKILL.md：说本地未返回该段，跑 `doctor` / `openclaw-check`，不发明 MongoDB/7897 |
| chart 启动日志整段 traceback：`kintaiyi/game_theory.py … No module named 'scipy'` | prewarm 碰到 opt-in 博弈论子模块（默认关、懒 import）；scipy 两平台 bundle 均无（mac 同样） | 良性，无需处置；判据 = `/taiyi/pan` 回 `ResultCode 0 + source kintaiyi`；勿为此加 scipy（瘦身红线） |
| `doctor` 报 `services:java_backend_not_running` / runtime_state `degraded_chart_only` | Java 后端死或被拦（Windows 常见 = 代理/VPN/安全软件 WFP 拦 JDK-17 AF_UNIX loopback，jar 在 Spring bean 构造期秒退且自身日志为空） | 降级模式设计行为：chart 侧技法照常可用；`doctor.java_diagnostics` 有启动器捕获的崩溃摘录；用户侧处置 = 禁用干扰软件并重启（issue #14） |
| Java 族技法（nongli / bazi / ziwei / liureng）报 HTTP 500 | **9999 是通用码，先读 `Result` 原文**：`no.register.app.in.sys.forapp` = 请求没带/没签对 `ClientApp`（注册表在 jar 内 `data/rsakey.json`，与 Mongo 无关）；`begin 1, end 3, length 1` / `200001` = 请求缺 `lat` 的上游崩溃（按**年**缓存，故时好时坏——复现要换冷年份）；`Timed out … mongodb.host` = 实例裸 `-jar` 起的，jar 内写死的 Mongo 主机名解析不到 | 裸 HTTP 探针恒回第一种、不可作判据；一律用 `service.run_tool` 正规路径复现（§8 验证流程 5）；第三种改用 `start_vendored_instance.sh --with-java`（桌面模式，无 Mongo 也全族可用） |
| 第一次调某个技法就超时（Codex 60s / 其它客户端各自默认），而 runtime 其实正常 | 首次启动含解压 + CDS 训练（300–900 s） | 已改为有界启动：超预算回 `runtime.starting` + `retry_after_seconds`，**重试同一个调用**即可；`HOROSA_RUNTIME_CALL_WAIT_SECONDS` 调预算；`runtime status` 看启动器日志 |
| Clash / VPN 下「无法连接本地后端」而服务健康 | 回环探测走了用户代理 | 已内建绕代理（`loopback_httpx_client`）；自己 curl 排查时设 `NO_PROXY=127.0.0.1,localhost` |
| 用户的星阙桌面端被本工具关掉 | 旧 stop 按端口动手，不问归属 | 已修：只停**强证据**属于自己的（nonce / 命令行含 runtime 根 / 我方 pid）；守卫 `verify_runtime_scripts.py` + `tests/test_runtime_ports_identity.py` |
| `runtime.port_conflict_foreign` / `_unknown_holder` | 8899/9999 被别的进程占着，本工具**不会**代为终止 | 关掉报错里点名的进程，或 `HOROSA_PORTS=auto` 自动挑空闲口；确知是 Horosa 后端时 `HOROSA_RUNTIME_TRUST_PORTS=1` |
| doctor 报「端口被 另一份星阙实例（horosa-chart / horosa-backend；pid … `…\HorosaDesktop\embedded-runtime\…`——很可能是你开着的星阙桌面端…）占着」（`identity.nonce_mismatch`） | 星阙桌面端（或另一个 runtime 根）占着默认 8899/9999：它说的是星阙协议，但 nonce 不是本工具这一份，所以本工具既不采用、也不代为终止。装了桌面端的用户的默认形状 | 不想关桌面端：`HOROSA_PORTS=auto` 让本工具换端口；想直接用桌面端的引擎：设 `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` 指向它（外部模式）；或关掉它再重试。v0.39.0 前 doctor 把这种情况误报成「一个查不出身份的进程」并叫人关掉它（台账 v0.39.0） |
| 某个客户端里 horosa 一个工具都没有 / 装了却不出现 | 配置写错（占位符未展开、缺 `--transport stdio`、目录搬了、`uvx horosa-skill` 指着未开通的 PyPI、Codex 默认 10/60 s 超时） | `uv run horosa-skill client check`（读它**实际写着什么**）→ 按 `fix_command` 重生成 |
| 容器里连不上而宿主 curl 正常 / `421 Misdirected Request` | Host 头不在 DNS-rebinding 白名单 | `host.docker.internal` 已默认放行；自定义域名加 `HOROSA_MCP_ALLOWED_HOSTS` |
| 维护机上 `test_error_paths_return_a_conformant_envelope` 红、CI 绿 | 默认端口上有活服务，只钉 `HOROSA_RUNTIME_ROOT` 拦不住，本该失败的路径成功了 | 同时把 `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` 指到不可达地址（§8 验证流程 4） |
| Windows 首次启动弹防火墙 / `doctor` 报 `listener:not_loopback_only` | 旧模板起 Java 没钉 `--server.address=127.0.0.1`，绑在 0.0.0.0 | 升级 horosa-skill 后 `runtime restart` 重套模板（每次 start 都会重拷 `.ps1`）；`doctor.listener_scope` 应变为 `loopback_only: true` |
| Windows 用户名带空格（`C:\Users\John Doe`）时 chart/Java 都起不来，`.horosa-local-logs` 里 python 报找不到文件 | 旧模板 `-ArgumentList` 路径元素没引号，被拆成两段 | 升级后 `runtime restart`；判据 = `tests/test_runtime_launcher_templates.py` 的引号断言（v0.38.0 B1） |
| Codex 里 horosa 一堆报错 / 首轮看不到工具 | 多半是 `startup_timeout_sec`/`tool_timeout_sec` 没写（Codex 默认 10 s/60 s，冷启动与择日扫描都超） | `horosa-skill client check --client codex`（v0.38.0 起缺省也报 `codex_*_timeout_missing`）；重跑 `client config --format codex --write ~/.codex/config.toml` |
| 矩阵 lane / 自己写的脚本把 live 闸门跑成 `java_routes_dead`，而 Java 明明活着 | `HOROSA_SERVER_ROOT` 被设成 doctor `endpoints[*].url`（带 `/common/time` 探测路径） | 只取 scheme://host:port（`verify_runtime_live.origin_of`）；闸门探的是 `<root>/nongli/time` |
| 改了端口（`HOROSA_PORTS=auto` / `HOROSA_LOCAL_*_PORT`）后 `runtime stop` 退出 0 却 `ok: false`、状态 `stop_requested`、端口仍在听 | 停脚本按端口命名的 pid 文件找进程，此前拿的是裸 os.environ（找默认端口的文件） | v0.38.0 起 start/stop 共用 `_launcher_env()`；升级后 `runtime stop` 即生效；残留进程按 PID 停（`lsof -nP -iTCP:<port> -sTCP:LISTEN`，永不 `pkill -f`） |
| `doctor` 报 `quarantine:runtime_binaries` / macOS 首次起 runtime 失败且无日志 | 浏览器下载的归档解出的 python / java / node 带 `com.apple.quarantine`，Gatekeeper 首次执行拦下 | 跑报告 `quarantine.fix` 给的 `xattr -dr com.apple.quarantine <current>`，再 `runtime restart`（只报不改，v0.38.0 B6） |
| 看不懂 doctor 的码 / agent 把 issue 码原样甩给用户 | 码是给脚本的 | `doctor --explain`（stderr 6–10 行人话，stdout 仍纯 JSON）；报告 `advice[]` 每码一句 `user_summary` + `next_action`（码表 `cli._DOCTOR_ADVICE` 与 `manager.DOCTOR_ISSUE_CODES` 锁步） |
| Windows 装到 OneDrive / 长用户名下 `runtime.install_long_path` | 最深载荷条目近 200 字符 + 安装临时目录 | `doctor.windows.headroom_chars`（按 `.hi-XXXXXXXX/x/` 前缀估，v0.38.0 起比旧 `.horosa-install-…/extract/` 多约 20 字符）为负即会拒：`HOROSA_RUNTIME_ROOT=C:\horosa` 或 `LongPathsEnabled=1` |
| 慢网 / 企业代理下 `runtime.install_download_failed` | 每块 1 MiB 之间的读超时 120 s、每镜像 3 次 | `HOROSA_RUNTIME_DOWNLOAD_TIMEOUT_SECONDS` / `HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS`；`doctor --probe-network` 看哪个镜像通（默认 doctor 零外网请求） |
| `setup` 在第 1 步 `network_probe` 就失败（5 s 内，`setup.network_unreachable`） | 清单 URL 经所有镜像都取不到（github.com:443 不通 / 代理拦 HEAD） | 失败包 `details.next_action` 给三条路：`HOROSA_RUNTIME_MIRROR=<前缀>`、`--archive <本地归档>`、`--no-probe-network` 跳过预检；`retry_command` 已带后者（v0.38.0 B4） |
| `setup` 在 `stdio_probe` 失败（`setup.stdio_probe_failed`） | 客户端将要执行的那条命令起不来 server：命令路径不对、uvx 首跑下载失败、工具数与工具面不符 | 看失败包 `details.command` 与 `details.stderr_tail`；uvx 形态可先手跑 `uvx --refresh --from <wheel URL> horosa-skill --version`；checkout 内改 `--launcher uv`（v0.38.0 B4） |
| Windows：`setup`（或 lane 的客户端步骤）在 `stdio_probe` 失败，失败包带 `details.diagnosis.cause = windows_file_in_use`（stderr 尾巴是 `failed to remove file …\Scripts\horosa-skill.exe … (os error 32)`） | 另一个已挂着的 horosa MCP 会话（`uv run … serve`）占着 venv 里的 exe / 已加载的 .pyd；客户端那条 `uv run` 要先把 venv 同步到当前版本（`git pull` 换过版本号就会触发），删不掉被占文件，server 未启动即退出。macOS/Linux 可替换运行中的文件，不会遇到 | 关掉（或重启）挂着 horosa 的会话再重跑；终端里的 `uv run` 可临时 `UV_NO_SYNC=1`（依赖未变时安全）；维护机复验一律在**独立 git worktree**（自有 venv）里跑门禁与 lane，别和本机开着的 MCP 会话抢同一个 venv（v0.39.0 台账） |
| `setup --client claude-code` 只打印了命令没注册（`config_mode: printed`） | `claude` 不在 PATH（GUI 装的 Claude Code 没把 CLI 放进 shell PATH） | 复制 `steps.config.command` 到有 `claude` 的终端执行，或 `--scope project` 写当前项目的 `.mcp.json`（v0.38.0 B4） |
| Windows ARM（骁龙本）上 `install` 成功但结果带 `runtime.platform_emulated`、`doctor` 报 `emulated: true` | 不是故障：本机没有原生载荷，自动装了 win32-x64 载荷走 Windows 11 x64 仿真（v0.38.0 A4） | 正常使用；冷启动更慢，矩阵里 `HOROSA_RUNTIME_START_TIMEOUT_SECONDS=900`；若报 `install_missing_platform` 说明清单连 win32-x64 都缺，先查发布完整性 |
| Apple Silicon 上 `install` 报 `install_missing_platform`，`platform` 却是 `darwin-x64` | 宿主 Python 是 x86_64（Rosetta 下的旧 Homebrew / conda），旧 `_platform_key()` 照抄 `platform.machine()` | v0.38.0 起 `sysctl.proc_translated` 判出真芯片给 arm64 载荷（载荷自带解释器，宿主架构无关）；`doctor.arch.emulated: true` 只是提示 |
| `install` 报 `runtime.install_os_too_old` | 载荷声明的 `min_os`（派生 Windows 载荷 = 10.0.17763，即 Windows 10 1809）高于本机 | 升级系统或网关模式；`details.host_os` / `min_os` 已给出两边版本 |
| 终端里 `uvx …` 能跑，Claude Desktop / Cursor 里却起不来（file not found） | GUI 客户端在 Windows 上不继承 shell PATH，配置里写的是裸 `uvx` | 重跑 `client config`（v0.38.0 起写绝对路径）；`client check` 报 `command_not_on_path` 即此症 |
| Windows smoke 绿，但 step 里某条命令其实失败了 | GitHub `pwsh` 多行 `run:` 只拿**最后一条**命令的退出码当结果（v0.38.0 前 `tool run --output` 这个不存在的参数在此安静失败了几十轮） | 每个 pwsh 多行块首行 `$PSNativeCommandUseErrorActionPreference = $true`（`tests/test_ci_workflow_shape.py` 守）；关键产物要 `Test-Path` + 断言 `.ok` |
| Windows 上 Java 后端起不来（`java_diagnostics`：`Unable to access jarfile …??…` / `could not find java.dll`），或 chart 族大量报 `tool.backend_param_error` 而 chart 服务 stderr 是 `KeyError: 'Chiron'`；install 报 `runtime.path_not_ascii`；doctor 报 `windows:runtime_root_not_ascii` | runtime 根含非 ASCII 字符（中文用户名下的默认根即是）：随包 JDK 17 的 java.exe 用 `GetCommandLineA` / `GetModuleFileNameA`，pyswisseph 把 UTF-8 星历路径交给 C `fopen`（Windows 按 ANSI 解）——中文系统上的中文用户名同样中招 | `setx HOROSA_RUNTIME_ROOT C:\horosa`（纯英文路径），新开终端并重启 AI 客户端后重装；0.38.1 起 install 在下载前就拒并给出这条修法 |
| Windows 上用户名带中文 / 重音，健康机器却报 `port_conflict_foreign` / `stop_refused_foreign` | v0.38.1 前 PowerShell 的命令行输出按 UTF-8 解，而 Windows PowerShell 5.1 往管道写的是 OEM 代码页（cp437 / cp936），路径子串永不相等 | 升级到 0.38.1：映像路径（ctypes）是首选证据，PowerShell 只搬 base64 字节；`doctor.endpoints[].identity.evidence` 应见 `process.image_under_runtime_root` |
| `doctor` / `runtime status` 在 Windows 上跑几十秒到几分钟，MCP 客户端直接掐掉 | 探针各自超时相加（两端口 × 两地址族 netstat + 每个持有者一次 PowerShell）没人管总量 | 0.38.1 起 doctor 25 s / status 15 s 硬顶，`report.budget.skipped` 列出被预算挡住的探针；仍慢看 `budget.timings` |
| `install` / `upgrade` 报 `runtime.install_refused_running_foreign`，`--force` 也不行 | 端口上跑着不是本工具起的星阙服务，且**证明不了它的文件在别的根**（查不到持有者 / 持有者住在本根下 / 只有 app 标记的旧载荷）；升级不砍陌生人是不变量。持有者全在别的根（桌面端 / 另一 runtime root）时**不再拒**：放行 + `runtime.install_ports_held_elsewhere` 警告（v0.38.1 复审） | 关掉那个服务，或 `HOROSA_PORTS=auto` 换端口后再装；只是自家旧服务在跑时升级会自动停 → 换 → 起（结果 `stopped_before_swap` / `restarted`） |
| `runtime stop` 报 `runtime.stop_refused_clients_attached` | 另一个 MCP 客户端会话（Claude Code / Cursor 的 stdio server）仍挂在这份 runtime 上 | 关掉那些会话；确认要停就 `runtime stop --force`；只想重启用 `runtime restart`（客户端自动重连） |
| Zed / VS Code 的 `setup` / `client config --write` 报「不是合法 JSON」 | 配置文件带注释 / 尾逗号（JSONC） | 0.38.1 起走 `jsonc.upsert_server_entry` 文本级插入（注释保留、只动 horosa 条目、写完回读）；仍红说明括号不配对 |
| 终端里 doctor ready，Codex 里技法全报 `runtime.not_installed` | Codex 不转发 shell 环境，server 用另一套 runtime 根 | `client check --client codex` 报 `codex_env_roots_missing`；重跑 `client config --format codex --write`（env 表写两个绝对根）；`setup` 的 stdio 探针读 `horosa://runtime/status` 直接报 `setup.stdio_probe_runtime_mismatch` |
| doctor warning `runtime:payload_outdated` | 已装载荷落后于最后一次看到的发布清单，或 `export_registry_version` 低于本包期望（本机 0.3.0 / 6 < 14 一直被报 ready） | 按 warning 的 `fix` 跑对应上下文的 `upgrade` 命令；`doctor --probe-network` 刷新版本缓存 |
| 维护机上 `test_runtime_manager.py` 全绿、CI 上四条红在 `runtime.port_conflict_unknown_holder` | v0.37.0 起只 stub `_service_status` 的用例会拿那个 URL **真的**跑归属判定：维护机 9999/8899 上跑着真 runtime → ours；CI 上没人监听 → unknown | 本机复现要连**归属**一起伪装：autouse fixture 把 `identity.probe_identity` 打成返回 None、`listener_pids` 打成返回 `[]`，`pytest -p <plugin>` 挂上去。`_managed_mode` 已内置 classify_endpoint 桩 |
| `client openclaw-setup` / `openclaw-check` 在 Linux / Intel Mac 上打出 `NameError: name 'details' is not defined` | v0.38.1 错误格式化的 `runtime.platform_unsupported` 分支读了未定义的名字（只在不发载荷的平台可达，没有测试走过） | main 已修（随下一版）；在那之前照网关模式配置 `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT`，`doctor --explain` 给同样的出路；`verify_undefined_names.py` 守住同类 |
| OpenClaw smoke / `client openclaw-setup` 报 `client.command_timeout` | 看 `details`：`phase: npx_install` = npx 首次下载 mcporter 超时；`output_complete: true` = 结果已完整打印但进程没退出（进程树里有子进程拖住管道）；两者都不是 = 调用本身没回来 | `npm i -g mcporter`（或 `HOROSA_MCPORTER_BIN`）；`MCPORTER_DEBUG_HANG=1` 重跑看 mcporter 在等哪个句柄，清掉残留 `horosa-skill serve --transport stdio`；其余先 `doctor` |

## 9. Stability invariants（稳定性不变量 — don't regress these）

A global stability pass hardened these; keep them true when you touch the relevant code:

- **报告类工具的 `output_path` 是不可信输入（v0.40.0 审计 P0）。** MCP 工具的调用方是模型，`output_path` 可能来自提示注入。落盘一律经 `HorosaSkillService._report_output_path`：相对路径按输出目录解析，绝对路径必须在输出目录或 `HOROSA_REPORT_OUTPUT_ROOTS` 白名单根内，越界 `report.output_path_not_allowed` 且不写文件；三个报告工具 `destructiveHint=True`。新加任何「按调用方给的路径写文件」的工具，都走这个闸（守卫 `tests/test_report_output_path_guard.py`）。
- **起与停同源同环境（v0.38.0 A5 真机 lane 首跑抓到）。** 启动器与停脚本的 env 只从 `manager._launcher_env()` 出
  （`HOROSA_SERVER_PORT` / `HOROSA_CHART_PORT` / HOME 族）——上游停脚本按端口命名的 pid 文件找进程，端口不一致 =
  永远停不掉、状态卡 `stop_requested`。守卫 `test_stop_passes_the_same_ports_as_start_to_the_stop_script`；
  生命周期操作只在 stub 上绿过不算数，矩阵 lane 的 stop 步骤要求端口真释放。
- **doctor 的每个码都要有人话，默认零外网请求（v0.38.0 B6）。** issue 码的真值 = `manager.DOCTOR_ISSUE_CODES`（`missing:*` 前缀族），
  warning 码 = `cli._DOCTOR_WARNING_CODES`；`cli._DOCTOR_ADVICE` 逐码给 `user_summary` + `next_action`，报告 `advice[]` 与 `--explain`
  都从它出。`tests/test_doctor_machine_conditions.py` 扫 `doctor()` 源码里新增的 `issues.append("…")` 字面量——不登记必红。
  默认 `doctor` 只打 127.0.0.1（`trust_env=False`），`--probe-network` 才逐镜像 HEAD 清单 URL（负向对照：默认路径上
  `_probe_manifest_url` 被替换成 raise 仍必须绿）。quarantine / 长路径余量 / 仿真进程都只**报**不改：修复命令交给用户。
- **测试 spawn 系统工具用绝对路径；扫真实安装目录的解析器测试要把那层 monkeypatch 掉（v0.38.0 反向「本机绿≠CI绿」）。**
  裸名 `subprocess.run(["bash"/"uv"…])` 在满负载 Windows 上偶发 `WinError 2`（PATH 搜索输给进程 churn + AV 扫描）——
  导入期 `BASH = shutil.which("bash")` 解析一次绝对路径再 spawn，缺席即 `skip`（`tests/test_runtime_launcher_patch.py`）。
  解析器测试（uvx/uv 的 `_windows_*_fallbacks()` 扫 `%LOCALAPPDATA%`/`%APPDATA%`/`%USERPROFILE%`）不 monkeypatch 掉那层，
  测的就是「本机装没装该工具」——维护机装了就红、无 uvx 的 ubuntu `test` 才绿，**托管 windows-latest lane 同样会红**
  （`test_resolve_uvx_command_derives_from_the_uv_sibling`）。这是横切教训 #7 的镜像；`scripts/run_ci_gates.py` 是把它
  提前到本机的 meta-guard。**复验时一次只跑一套重活**（两套 pytest / lane 并发 = 自造 flake），且**别在本 session 的 MCP
  server 还占着 `.venv\Scripts\horosa-skill.exe` 时跑真 `uv run` 用例**（`uv sync` 删不掉被占的 exe → `test_stdio_probe_*` 假红）。
- **`setup` 的七步顺序与失败包是契约（v0.38.0 B4）。** `network_probe → install → config → doctor → client_check → stdio_probe →
  next_steps`，顺序冻结在 `tests/test_cli_output_contract.py::test_setup_public_keys`；失败包只走 stderr、退出码 2，键
  `step / code / config_untouched / backup_path / retry_command / steps`，**第 3 步之前失败保证 `config_untouched: true`**
  （`tests/test_setup_command.py` 负向：装失败时预置配置逐字节相等）。`doctor` / `client check` 与 `setup` 永远共用
  `_doctor_report` / `_client_check_report`（不许各写一套判定）；`stdio_probe` 必须真 spawn 配置里那条命令（进程内
  `create_mcp_server` 证明不了客户端能起它）；`_build_client_config_payload` 只在 `uv` 启动器与 mcporter/openclaw 形态下解析
  checkout——wheel 装出来的包旁边没有 pyproject.toml，uvx 形态必须能在没有 checkout 的机器上生成配置（ci.yml wheel 步骤锁）。
- **平台策略只有一处真值、两处镜像，回退只许公告着做（v0.38.0 A4）。** 真值 = `contracts/release_platforms.json`；镜像 =
  `manager.SUPPORTED_PAYLOAD_PLATFORMS` / `PLATFORM_FALLBACKS`（wheel 不带 contracts）与 README×2 平台表，各有锁步测试。
  `install()` 走回退必须返回 `platform_fallback{requested, installed, mode}` + `warnings[runtime.platform_emulated]`（含版本短路那条
  返回），doctor 必须给 `host_platform / payload_platform / emulated / arch`；**darwin-x64 永不回退到 arm64**（Rosetta 反向不成立，
  `test_intel_mac_is_refused_even_when_an_arm64_payload_exists` 是负向对照）；平台键看芯片不看宿主 Python（Rosetta 下的 x86_64
  Python 仍拿 arm64 载荷）；载荷或清单声明的 `min_os` 必须在下载前、解压后各查一次（`runtime.install_os_too_old`）。
- **导出段只存 body，引擎对象只在 `data.<key>` 存一份。** `export_snapshot.sections[*]` 形状固定为
  `{index, raw_title, title, included, body}`（envelope 0.8.0）；`_pick_section_data` 对未识别段返回
  `None`，绝不兜底整份 `response_data`（v0.36.0：qimen 5 MB / india_chart 101 MB 的来历）。守卫：
  `tests/test_response_budget.py`（引擎对象恰出现一次 + 信封字节按内容封顶）——加段/加数据键前先跑它。
- **降级必须让调用方看见。** 富化/子引擎/可选后端失败一律 `_degrade(fmt, *args[, note=])`（日志 +
  当前 `run_tool` 的收集器 → `envelope.warnings`，嵌套调用冒泡）；预设段缺席自动进 warnings + summary
  （「结果不完整：预设 N 段中 M 段未产出」），dispatch 汇总一行。包内裸 `logger.warning(` 基线 **0**
  （`scripts/verify_silent_degrades.py`；启动期通知用 `logger.log(WARNING)` 并注明无调用方）。MCP
  elicitation 每个出口写 `details.elicitation.status`，纯函数 `_apply_gate_decision` 可离线测（v0.36.0）。
- **`tools/*.js` 只准引用 vendor 常量，不准抄。** 顶层字面量若与所 import 的 vendor 模块导出同名（规范化）
  或深相等，`npm test` 的 `test/handcopy.mjs` 即红（v0.36.0：liureng.js 曾抄 24 张 LRConst 表，vendor 修了
  六亲、消费点仍旧值）。改 vendor 真值时，金标打在**工具输出**（消费点）上，不只打在那张表上。
- **声明旋钮 = 交付翻转金标。** 每个新 schema 字段在 `selfcheck.mjs` 至少一条「改它结果必变」+ 一条「写错
  键名结果不变」的负向对照。`js_boundary_contracts` 的子串 oracle 对「同模块另一函数恰有同名参数」的死键
  失明（v0.36.0 heluo `step2`），只当第一道网；生成器已认默认导入与 `opts: local` 嵌套，regen 后仍要翻转验证。
- **启动是异步、幂等、跨进程互斥的。** `start_local_services(wait_seconds=)` 最多阻塞预算秒，
  超出即 `{"starting": True, retry_after_seconds}` → 工具层的 `runtime.starting`。跨进程锁
  （`runtime/pidlock.py`）的持有者写成**启动器自己的 pid**，锁的寿命恰等于一次启动；加锁后的每一条
  出口都在 `finally` 里释放（不释放会让一个长命的 serve 把后续所有启动永久挡死）。
- **绝不采用身份不符的服务栈，也绝不终止不属于自己的进程。** 「HTTP 200」不是身份证明：
  归属判定走 `runtime/identity.py` 的三级证据（`/horosaIdentity` 的 app 标记 + 启动 nonce → 监听
  进程命令行含 runtime 根 → 我方注册表 pid 存活）。`ours` 才用它，**强证据**才允许停/重启它
  （只有 app 标记 = 可能是用户自己开着的桌面端）。查不到持有者 ≠ 端口空着。
  握手已下结论的 foreign 分支（nonce 不符 / 别的 app）同样要**点名**持有者（`identity._name_holders_cheaply`：Windows 只走 ctypes 映像，
  不起 PowerShell），报错措辞按证据**实际证明了什么**来——星阙标记说「另一份星阙实例」，只有什么都没证明时才说「查不出身份」
  （`_doctor_summary`；v0.39.0 台账）。
- **状态文件原子写。** `runtime-state.json` 走 tmp + `os.replace`（`runtime/registry.py`）；
  一次 `write_text` 会让并发读者读到半个 JSON → 判成「没在跑」→ 再起一次。整份覆盖时保留
  别的进程写进来的长寿字段（`launch_nonce` / `clients` / `launcher` / `service_pids` / `ports`）。
- **pid 存活判定在 Windows 上走 ctypes `OpenProcess`，永远不调 `os.kill`。** Windows 的 `os.kill`
  没有信号 0 语义 —— 对任何非 CTRL 信号它直接 `TerminateProcess`，也就是会把目标**杀掉**而不是探测。
- **就绪分后端，重启有冷却。** Java 挂/chart 健康时，`start_local_services` 在冷却期
  （`runtime_java_retry_cooldown_seconds`，默认 120s）内返回 `{degraded, skipped_restart}`，**绝不** stop 健康的
  chart 服务；`_call_remote` 对 Java 端点冷却期内快速失败 `runtime.java_backend_unavailable`，chart 端点不受
  影响。新增「探针失败就重启」的路径前先读管理器的降级状态（v0.36.0）。
- **一个键要么在 schema 上，要么它不存在。** MCP 扁平面按广告签名丢未声明的顶层键（FastMCP arg_model），
  CLI/tool_run/dispatch 不丢——服务读、文档写、样例带而 schema 没声明的键，MCP 用户会静默拿到另一张盘
  （PR #17 性别、神数五支性别/地点、`showPdBounds`……共 63 例）。守卫 `tests/test_mcp_flat_surface_keys.py`
  （样例载荷原始键 ⊆ 广告签名）；反向由 `verify_schema_knob_wiring` 管。枚举参数的描述与表锁步
  （`test_house_system_docs.py`：hsys 1=Alcabitus、3=Placidus）。
- **MCP schema 两层：签名求全、广告求准。** `__signature__`（校验层）永远声明全模型字段——瘦它 = 静默丢键；
  `tools/list` 的瘦身只在注册后重写 `Tool.parameters`（`surfaces/mcp_schema.py`：域核心 + 推运目标 + 工具自有
  字段 + 闸门三键 + `request`）。硬预算全量 ≤256 KB / 精简 ≤30 KB（`verify_mcp_list_budget.py` 棘轮只降不升）；
  加字段/加描述前先量。enum 只进广告层且与表锁步（v0.36.0）。
- **能算 ≠ 能被找到。** 新技法必须同时带：`engine/synonyms.py` 一条（键集与 TOOL_DEFINITIONS 锁步）、
  `engine/router.py` 一条规则（或进 `ROUTING_EXEMPT`）、`contracts/router_corpus.json` 至少一句语料
  （`verify_router_corpus.py` 的 `min_pass` 只升不降）。择日搜索族词面含基底技法名，基底规则一律
  `and not is_zeri`。`HOROSA_TOOLSETS` 未知 token 告警丢弃、全空回落全量，过滤生效即注册 `horosa_tool_run`。
- **工具自有的结果敏感项，闸门必须点名问到。** 族策略（ASTRO_BIRTH/SHENSHU/PREDICTIVE）只是底座；有自有旋钮
  的工具用工厂出专属策略（`_progression_target_policy`）。闸问题要么带 `options`（可枚举者并行 `values`，
  表单答案只写回这些值），要么字段进 `FREE_TEXT_GATE_FIELDS`；`tests/test_gate_policies.py` 守。
  加旋钮 = 加问题 + `sensitive_settings.json` 自测 + live 翻转测试（v0.36.0）。
- **错误码是接口。** 每个 `code="…"` 必须经 `errors.classify_code` 落到恢复规则（精确表 → 基础设施前缀 →
  `*_missing_*`/`*invalid*`（修入参）/`*_failed`/`*_unavailable`（重试再体检）后缀），`verify_error_recovery.py`
  硬红；文案用 `errors.bilingual(zh, en)`，非双语计数只降不升。service 与 MCP 两条错误路径都走
  `recovery_for`（agent_recovery.kind/prompt_to_user/next_action + details.hint）（v0.36.0）。
- **排除上游能力前先在上游源码确认它挂在哪一层。** `/qizheng/moira` 是 Java 聚合层路由，曾因 Python chart
  服务 500 被记成「不存在」两个版本（v0.36.0 C1 接活）。「某服务 500」≠「路由不存在」；台账「维持排除」条目
  必须写判据。Java 端可选富化一律经 `_call_remote` + `_degrade`，段列 optional。
- **校验族按「最常调 × 最易编」排优先级；评测器必须有 bench 入口。** faithfulness v3 = 11 族（四柱/落座/身宫/
  三传/紫微主星/卦名动爻/塔罗/奇门值符值使九宫/择日命中区间/推运时段边界/词元兜底），每族至少三条对抗测试；
  HorosaBench `faithfulness` 类 case 跑工具→抽真值→判答案（`expect_ok`/`expect_min_flagged`）。新技法上架时
  若其结果有可抽的机读真值，同批加族或加 case（v0.36.0）。
- **发布三件：darwin 资产 + PyPI + Windows 半。** `publish-pypi.yml` 随 Release published 自动跑（trusted publishing，
  一次性 pending publisher 见 docs/OFFLINE_RUNTIME_RELEASES.md）；`verify_wheel_contents.py` 守「uvx 装出来的东西」
  （知识包/bench/闸表/Windows 启动模板/入口点；core-js 不进 wheel、随 runtime）；`server.json` 只登记 pypi 条目，
  与 pyproject name/version 锁步、禁 TBD（v0.36.0）。
- **宫主/宫神星只从 `astro_rulers.py` 取。** 它是上游 `wholeSignRulers.js` 的移植（夹具与断言照抄上游 jest），
  Python 面不许再各自算宫主（上游 #79 双实现漂移）；段内子块（[主宰星链] 尾块「◆ 整宫制宫主表(wholeSignRulers)」）
  段级棘轮看不见，加子块要配逐字夹具测试。上游 v57 把当前分宫制宫神星表迁出成独立段 [分宫制宫神星表]（行星力量/角续果
  口径，非主宰依据；分宫制即整宫制时折叠为一句说明），v0.40.0 已随 v58 同步（`astro_rulers.build_house_system_ruler_section_lines`）；
  名称一律上游单字表（日/月…），v56 旧移植印全名（月亮）而测试也断言错值。
- **Java 实例只按上游桌面模式起，「live 需 Mongo」不再是合法理由。** jar 内 `conf/properties/cache/*.properties`
  把 Mongo 主机写死为 `mongodb.host`；裸 `java -jar` = 每个碰库请求 30s 超时后 9999，被当成环境限制记了十个版本。
  起法四件（`--mongodb.ip=127.0.0.1`、`HOROSA_DESKTOP_MONGO_OPTIONAL=1`、`HOROSA_MONGO_FALLBACK_DIR`、
  `needtranslog=false`）由 `start_vendored_instance.sh --with-java` 内置、`test_guard_wiring` 守；app 注册在 jar 内
  `data/rsakey.json`，与 Mongo 无关。发版前的 live 判据从此是 **0-skip 全量**（本 Mac v0.36.0 收尾 678 绿），
  `MONGO_PORT=<空端口>` 可模拟干净机器（走文件回退）。
- **闸门问什么，以 live「改参数结果必变」为准，不以代码转发了什么为准。** 演禽（xianqin）转发了 lat/lon，引擎却不读
  （上海↔乌鲁木齐逐字节相同）——问地点就是假闸门。给工具挂结果敏感项前先翻转一次；不敏感的项用**反向** live
  断言钉住（`test_xianqin_ignores_place_so_its_gate_must_not_ask_for_it`），上游哪天读了它会先红（v0.36.0 收尾）。
- **零安装 = wheel 资产 + 镜像前缀 + 钉版本锁。** 每个 Release 附 `horosa_skill-<ver>-py3-none-any.whl`（发布脚本
  [5/8] `uv build --wheel`；`release-completeness.yml` 对 ≥ 0.38.0 断言在场并真跑 `uvx --from <URL> horosa-skill --version`）；
  `HOROSA_RUNTIME_MIRROR` 由 `runtime/mirrors.py` 统一改写清单/归档/wheel 三种 URL；`client config --launcher uvx-wheel`
  是免 git、免 PyPI 的推荐零安装启动器（`uvx-git` 需要 git + github.com 直连）。文档/`server.json`/examples 里
  钉版本的 `@v<x>#` / `/v<x>/…whl` / `/v<x>/…mcpb` 由 `verify_docs_sync.check_pinned_install_commands` 锁死；
  受限网络的三条路成文于 `docs/INSTALL_RESTRICTED_NETWORK.md`（v0.38.0 B3）。
- **写用户的客户端配置 = 只动自己的键、先备份、原子替换、认不出形状就拒绝；命令一律绝对路径。** `_merge_client_config`
  按产物根键（`mcpServers`/`servers`/`context_servers`；codex 走 tomlkit）只 upsert `<root>[<server_name>]`，写前 `.horosa-bak`，
  临时文件 + `os.replace`，非对象/非法 JSON 或没有 server 块的说明产物一律拒写（v0.38.0 B2：此前 vscode/zed/claude-code 的
  `--write` 会把用户整个 settings.json 覆盖成 payload）。`uv`/`uvx` 启动器都经 `client_tools.resolve_*_command` 写绝对路径——GUI
  客户端在 Windows 上不继承 shell PATH；`client check` 的 `command_not_on_path` 守。配置路径用 `_client_config_locations`
  （按 os 与 `%APPDATA%`/`~/Library`/`~/.config` 算），不写死 POSIX 表。Codex 审计「没写超时」与「写太短」都报。
- **证据的形状不许由偶然决定。** ① CI 里 `shell: pwsh` 的多行 `run:` 块首行必须是 `$PSNativeCommandUseErrorActionPreference = $true`，
  否则只有最后一条命令算数（`tests/test_ci_workflow_shape.py`）；② 计数守卫的覆盖面是正则规则（`COUNT_PROSE_EN` 认 `real|local`），
  不是某句话恰好的措辞；③ 仓里有的文件文档不得否认（`verify_docs_sync.check_docker_claims`），Dockerfile 的 `COPY` 必须盖住
  pyproject force-include 的每个源路径（`tests/test_dockerfile_matches_wheel_includes.py`）。`tool run`/`dispatch`/`ask`/`hecan`
  的 `--output` 是 stdout JSON 之外的**附加**文件出口（Windows 管道会按代码页重编码），stdout 契约不变（v0.38.0 B0）。
- **`run_tool` always returns a `ToolEnvelope`, never lets an unexpected exception escape.** Tool
  execution + snapshot/summary/export post-processing run inside a try that catches `HorosaSkillError`
  **and** a last-resort `except Exception` → `ok=False` / `tool.internal_error`. Only invalid-payload
  `ValidationError`（raised *before* that try）intentionally surfaces as `tool.invalid_payload`. Do not
  add a tool/post-processing path that can raise out of `run_tool` — it would crash the CLI, break the
  MCP session, or abort a whole `dispatch`.
- **错误信封的顶层镜像三键在所有错误路径上一致。** `ToolEnvelope` / `DispatchEnvelope` 的
  `code`/`message`/`details` 是 `error.*` 的向后兼容镜像（给按顶层键读的 CLI / 旧 agent 提示词）。
  MCP 面构造的错误（闸门、pydantic 校验）与 `service.run_tool` / `dispatch` 自己构造的错误
  （`runtime.*` / `transport.*` / `tool.ken_compute_failed` / `tool.internal_error`）**两条路径都要填**——
  只填一边时，调用方恰恰在最常见的失败上读到 `None`。守卫：
  `test_mcp_contract.py::test_error_paths_return_a_conformant_envelope` 同时覆盖闸门与闸门之后的失败。
- **Surfaces never dump a traceback.** CLI file reads（`--ai-report-file` / `--ai-answer-file`）raise
  clean `typer.BadParameter`; the MCP `horosa_report_*` handlers wrap unexpected renderer/IO errors via
  `_mcp_internal_error_payload`; subprocess calls carry timeouts（incl. `openclaw-check --full`, 900s）.
- **路径/用户值进配置文本必须走序列化器，禁裸 f-string 插值。** `client config` 各格式产物
  （TOML/JSON/deep-link）里的 command/args/cwd 一律 `json.dumps`（JSON 转义 ⊂ TOML 基本字符串转义）
  或 `quote`；裸插值在 Windows 上会把 `C:\Users\…` 的反斜杠原样写进 TOML → 整文件不可解析、
  `--write` 拒绝合并（v0.33.0 codex `command` 就这么在 mac/Linux 恒绿、windows-smoke 连红两次）。
  守卫：`tests/test_client_config.py`（windows-smoke 上跑 = 唯一能判红的形状）。
- **`input_normalization` degrades, never crashes.** The date/time regexes are shape-only（they accept
  month `13`, day `45`）, so anything building a `datetime` from them must tolerate `ValueError`（see
  `_combine_date_time`）. IANA-zone→offset conversion uses the *chart date*, not `now()`. `Z`/`UTC`/
  `GMT` → `+00:00`. Compact coords like `121e28` parse as 121°28′（NOT float scientific notation）.
- **Runtime manager:** close file handles before `shutil.rmtree` on the Windows start path; a missing
  local `--archive` raises `RuntimeError`（which `install` catches）, not a raw tarfile error. Never
  kill chart services by process-name — the stop script scopes kills by runtime root path; keep it.
- **`js_client` keeps the transport contract.** Every Node failure becomes a `ToolTransportError`:
  missing/unstartable Node → `js_engine.node_unavailable`, timeout → `js_engine.timeout`. The
  `subprocess.run` call is wrapped — don't let a raw `OSError`/`TimeoutExpired` escape. On the JS side,
  `bin/cli.mjs` always prints a JSON `{ok:...}` envelope to stdout（never a bare stack trace）and
  coerces a `null`/scalar parsed payload to `{}` so tools don't null-deref on `payload.field`.
- **Tracing is best-effort.** `TraceRecorder._write_event` swallows local-write failures（like
  `_emit_otlp`）; a trace write must never crash or mask the traced operation.
- **`evaluation_lock` self-heals.** `acquire_evaluation_lock` reclaims a stale lock（dead PID on POSIX,
  or age threshold when liveness is unknown）but never reclaims a *live* owner. **Never call
  `os.kill(pid, 0)` on Windows** to probe liveness — on Windows `os.kill` maps to `TerminateProcess`,
  it would *kill* the lock owner. `_pid_liveness` returns `unknown` on Windows（→ age-based reclaim）;
  keep it that way.
- **Report rendering is atomic.** `render_report` renders to a temp sibling then `os.replace()`s —
  never write a report format directly to its final `output_path`（a mid-render failure would corrupt it）.
- **install / upgrade 换目录前必停自己的服务，且永不停陌生人的（v0.38.1 R3）。** `install()` 在 `replace(previous)` 之前先
  `endpoint_identities`：全不可达直接换；全部 `started_by_us` → `stop_local_services(ignore_clients=True)` → 换 → `start_local_services()`；
  可达但不是我们起的 → 先问 `identity.holders_outside_runtime_root(port, runtime_root)`：监听者**全部**证明跑在本根之外
  （映像 / 命令行都不在本根下 —— 用户的桌面端、另一个 runtime root）→ 换目录动不到它们的文件，**放行**、不停任何进程、
  记 `runtime.install_ports_held_elsewhere`（`held_by` 点名；next_action = 关那份实例或给本 runtime 换端口再 start）；
  任一证明不了（查不到 / 住在本根下 / 点不出名）→ `runtime.install_refused_running_foreign`，`--force` 不覆盖
  （**永远不把「查不到」当「在别处」**）。原因：旧清单钉着默认端口 + 桌面端占着它们是最常见形状，原来的
  拒绝把用户卡死，且提示的 `HOROSA_PORTS=auto` 对它无效（闸探的是旧清单的端口）——见台账 v0.38.1 / 2026-09-15。
  `tests/test_runtime_manager.py` 锁顺序 `["stop", "swap", "start"]`，并锁「别处 → 放行不 stop」与「部分证明不了 → 仍拒」。
- **子进程文本一律显式解码（v0.38.1 A1/A19）。** `subprocess.run(..., text=True)` 必带 `encoding=`（UTF-8，或 tasklist 的 `oem`）
  + `errors="replace"`；归属证据优先走不经代码页的 ctypes 映像路径；PowerShell 只允许搬 base64 字节。`tests/test_subprocess_encoding.py`
  AST 扫描基线 0。
- **Windows 上 runtime 根必须纯 ASCII，交给 java.exe 的参数一律纯 ASCII（v0.38.1）。** 随包 JDK 17 的 java.exe 用 `GetModuleFileNameA`
  找 java.dll、`GetCommandLineA` 读参数；Swiss Ephemeris（pyswisseph → C `fopen`）拿 UTF-8 路径、Windows 按 ANSI 解——「代码页能表示」
  也不够（「horosa lane é」下 Java 起来了，星历仍打不开）。所以 ① install 在下载前用 `windows_runtime_path_ok`（纯 ASCII）拒绝
  （`runtime.path_not_ascii`），doctor 报 `windows:runtime_root_not_ascii`；② 启动器 jar 参数是相对 `$Root` 的字面量 `$JarArg`
  （`verify_runtime_scripts.audit_windows_launcher` 守）。自动迁移到 ASCII 位置**没做**（ACL / 抢注面，待定）。真机证明：runtime-matrix
  Windows lane 的 `non_ascii_root_refusal` 步骤 + 「horosa lane runtime」根；三轮失败证据见 LESSONS v0.38.1 ⑥。
- **`runtime stop` 不在别的 MCP 客户端脚下抽走服务（v0.38.1 R14）。** 登记表里仍存活的客户端 → `runtime.stop_refused_clients_attached`；
  `--force` 才停；`restart` / 升级换目录 / `uninstall` 走 `ignore_clients=True`（服务马上回来或本来就要删）。死掉的登记不拦。
- **doctor 默认零外网请求，「最新版本」只读缓存（v0.38.1 R4）。** `latest_version` / `freshness` 来自 `<runtime_root>/.latest-manifest-cache.json`
  （每次成功抓取发布清单顺手写）；没有缓存就老实 `null` 并提示 `--probe-network`。过期是 warning，不阻断。
- **stdio server 在客户端关掉 stdin 后 15 s 内退出（v0.38.1 发布后）。** 退出路径上不留非 daemon 线程、不阻塞（runtime 预热线程是 daemon）；
  孤儿 `serve` 会一直登记为 attached client，让 `runtime stop` / 升级拒绝，还会拖住调用方的 stderr 管道（TS SDK 以 inherit 起 server）。
  `tests/test_stdio_server_exit.py`（真子进程、不带 `--skip-runtime-start`、真调一次工具）在 Linux 与 Windows CI 上都跑。
- **未定义名字基线 0（v0.38.1 发布后）。** `scripts/verify_undefined_names.py`（`ruff==0.16.7` 钉死，只选 F821/F822/F823，src/scripts/tests）。
  只在没人跑的平台上可达的分支就是没测过的代码——这类「运行时必崩」错误靠静态检查兜，不靠 pytest 走到。
- **lane 永不碰调用者自己的客户端配置（v0.38.1 发布后）。** 九客户端步骤一律 `--config <work>/client-configs/…`；Claude Code user scope
  步骤用 `Lane.claude_user_scope_env()`（`HOME` / `USERPROFILE` / `CLAUDE_CONFIG_DIR` 指向 `<work>/claude-user-home`）——旧实现继承真 HOME，维护机上
  `claude mcp add --scope user` 写的是真 `~/.claude.json`，清理那句 `claude mcp remove --scope user horosa` 还会删掉维护者原有的条目（托管 runner 没有
  `claude`，矩阵从没暴露）。本机用真 `claude` 验过隔离：add / get / remove 全落在隔离目录，真配置 sha 不变。守卫
  `tests/test_verify_runtime_live.py::test_claude_user_scope_step_never_touches_the_invoking_users_claude_config`。
- **Cross-platform text digests are line-ending independent.** Any sha stamped on one OS and compared on
  another hashes CRLF→LF-normalized bytes: `revendor_core_js._sha256_file`（vendor stamps `upstream_sha256`/
  `derived_sha256`; raw bytes only for non-UTF-8）and `decisions/eval.py::dataset_sha256`（the Jev dataset
  fingerprints locked in `contracts/jev_thresholds.json`）. A raw-bytes digest made the hand-made-drift guard
  permanently red on Windows（v0.35.0+ 台账）and would let a Windows regeneration write a lock no other platform
  can satisfy（v0.39.0 台账）. Don't switch either back to `read_bytes()`; any script that *writes* LF artifacts
  （sources, eval sets, locks, reports）must pass `newline="\n"`
  （`tests/test_decisions_eval.py::test_dataset_sha256_is_line_ending_agnostic`）.

## 10. 上游镜像注记（upstream 星阙 — skill 必须镜像的行为）

**晚子时双开关（upstream v2.2.1+）**：`after23NewDay` 与 `lateZiHourUseNextDay` 两个**独立** flag 只在
`hour == 23` 生效；完整规格、自检矩阵（`2026-05-27 23:30:00` 四象限）与向用户问法的**属主 =
[`skills/horosa-agent/references/late-zi.md`](./skills/horosa-agent/references/late-zi.md)**。维护者要点：

- **状态（as of v0.23.0）**：晚子时双开关（`after23NewDay` 日柱 / `lateZiHourUseNextDay` 时干）**已全链
  穿透**——神数 14 路（`ShenShuInput`）、`bazi_*` / `ziwei_birth` / `liureng_*` / `jinkou` / `qimen` /
  `taiyi` / `sanshiunited` / `jieqi_year` / `nongli_time`（schema 字段 + `service.py` 白名单转发），以及
  v0.23.0 补线的 **`canping` / `heluo`**（`CanPingInput`/`HeLuoInput` schema + `tools/{canping,heluo}.js`
  的 `baziParams` 透传给 `buildLocalBaziResult`）。验证：`references/late-zi.md` 四象限矩阵
  （`2026-05-27 23:30:00` × 两开关），heluo 两开关皆可见（日 辛丑↔壬寅、时干 戊子↔庚子）、canping 只用
  时支故 `lateZiHourUseNextDay` 对其为 no-op（仍 verbatim 转发）；回归 `test_canping_heluo_late_zi_switches_thread`。
- **法则**：所有起中式四柱的 chart-flow payload（`bazi_*`、`ziwei_*`、`liureng_*`、`qimen`、`taiyi`、
  `jinkou`、`sanshiunited`、`canping`、`heluo`、`nongli_time`、`jieqi_year`、Bazi-aware `chart`）两 flag
  一律 **verbatim 转发**到引擎；导出快照带 `排盘规则: 日柱开关【…】+ 时柱开关【…】` 行，tool formatter
  必须保留、报告/AI 解读必须引用回去（strip 掉 = 用户换过开关时静默错解）。
- **缺省（v0.40.0 起）**：日界开关缺省**不发送**（schema 缺省 `None`，不再 `False`——Java 把 JSON `false` 读成 0，曾在
  每次调用里盖掉星阙缺省 1）；走本地引擎的路径（八字 lunar 本地、紫微 ZiweiCalc）显式传 1/1；金口诀两开关都转发 ken；
  `jieqi_year` 的 after23NewDay 上游 Java 写死不读。矩阵 (1,0) 行 = 壬寅 **戊子**（两开关完全独立，上游 dayBoundary.js:47-57）。
- 真后端返回的四柱与矩阵不符 = runtime pre-v2.2.1（让用户重装 runtime），**不许**在 skill 侧打补丁掩盖。
- 上游根因参考（替用户排障星阙侧数值时省几小时）：① Java `ChartController.getParams()` 是**白名单**，
  没 `params.put(...)` 的字段静默丢、默认接管——上游加 chart-flow 字段要审计所有 `getParams()` 型
  controller；② `mvn package` ≠ 活进程更新（`lsof -ti :9999` + `ps -p <PID> -o lstart=` 核进程启动时间
  晚于 jar mtime）；③ `lunar-javascript` 硬编码 `timeGanIndex`，`setSect()` 只移日柱不移时柱——
  `lateZiHourUseNextDay=0` 要前端用 `getDayGanIndexExact2()` 自算时干；④ 三重缓存
  （JVM 内存 + Redis + `.horosa-cache/paramhash/`）——新键自动 miss 但类型变更可能命中旧条目，排障时清
  `redis-cli KEYS "*chart*"` + `.horosa-cache/`；⑤ 前端 `chartMem`（`services/astro.js`）按
  `JSON.stringify(values)` 键控，`requestOptions.cache = false` 强刷；⑥ AI 快照必须带规则行（见上）。
  权威上游文档：`Horosa-Web/docs/global-day-boundary-v2.2.1.md`（在星阙树，非本仓；本节漂移时以上游为准
  同步过来，不从本仓改上游）。

**西占新功能四同步**（上游加占星功能时必查）：新增占星功能默认只渲染成 tab，**不会**自动接入
AI导出 / AI分析 / 命盘事盘储存——漏接 = 用户眼里「不全面/不稳定」。判读类 → 写 `astroAiSnapshot.js`
section builder + `aiExport.js` 段名 + 升 `AI_EXPORT_SETTINGS_VERSION`；预测类 → 写
`buildXxxSnapshotText` + 在 `aiAnalysisContext.regenerateChartTechniqueSnapshot` 加 case；希腊点/阿拉伯点
只要进 `AstroConst.LOTS` 即自动进导出（`buildLotsSection`）；新 chart-calc 参数四点存/取
（`models/user.js` fields + 存档复制、`utils/localcharts.js buildLocalChartRecord`、`models/astro.js`
重建 fields），**铁律：勿连带改坏 pdMethod/主限法**；事盘 module 注册 `utils/localcases.js
CASE_TYPE_OPTIONS`（`state.extra` 已通用存取）；**陷阱：predictHook 只管 UI 实时刷新，AI 分析不遍历
hook、走专用 builder**。全链路清单：`Horosa-Web/docs/西占新功能-AI导出与储存接入清单.md`（星阙树）。

**法奇门叠加层**（qimen 快照 +8 段）：纯前端 JS（`DunJiaFaCalc` / `DunJiaFaDoc`）consume kinqimen 的
`pan` 叠加 `[六害总览][化解方案][八门化气大阵][用神分论][财富七要][事业七要][恋爱姻缘][孤辰寡宿]`——
这是 JS 格式化层、非后端缺失；`pan.source == "kinqimen"` 守恒不变。上游「AI导出 / 导出设置段表 /
AI分析挂载 / 命盘事盘储存」四处走同一 builder + 同一段表——**新增段必同步 builder + 段表两处**。
八神显示已归一 `勾→虎 / 雀→玄`（`DunJiaCalc.buildCells`，盘面/hover/八宫/化解/快照一致）；六害化解口径
以荀爽视频 docx 为准。`[八门化气大阵]` 可含 `faRelatedPeople` 逐人「生年干·姓名」行（**折叠进现有段，
段表不动**）：skill 侧 Python 把 `{name, birth}` 经 `/nongli/time` 的 `yearJieqi`（立春界，1991-02-03 →
庚）归一为年干，JS 保持上游 verbatim 只 stamp `pan.faRelatedPeople`（显式数组为准，缺省不出行；不引
`lunar-javascript` 的 `birthToYearGan`，走自家 nongli 后端同口径）。re-vendor 星阙 JS 时会带入
`DunJiaFaCalc.js` + `DunJiaFaDoc.js` 并改 `DunJiaCalc.js` / `QimenXiangDoc.js` / `aiExport.js` 等
（guarded 增量，占星零回归）。

（上游 AI-analysis **SSE Issue #8** 只影响星阙桌面端 chat 流、不影响 skill 计算路径——原文与处置见
[`docs/LESSONS.md`](./docs/LESSONS.md)。）

## 11. 第三方引擎与 MIT 义务（ken）

ken 引擎开源、**MIT-licensed**，作者 **kentang2017**：
[`kinqimen`](https://github.com/kentang2017/kinqimen) · [`kintaiyi`](https://github.com/kentang2017/kintaiyi)
· [`kinjinkou`](https://github.com/kentang2017/kinjinkou)。MIT 要求版权+许可文本随每次分发：

- **永不 strip** runtime payload 里的 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE`
  （`verify_runtime_release.py` 要求引擎目录在位，LICENSE 随目录走）。
- 致谢在 `README.md` / `README_EN.md`「致谢 / Acknowledgements」+ GitHub release notes；bump / 重 vendor
  引擎时保持 credit 准确。

## 12. 经验台账

逐版本教训**原文**（v2.4.0 批 → v0.14.0 批、发布完整性编年、上游 SSE 陷阱）：
[`docs/LESSONS.md`](./docs/LESSONS.md)。新教训按 §2 协议：台账落原文 + 蒸馏进本文对应章节。
