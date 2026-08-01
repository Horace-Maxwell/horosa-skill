# 经验台账（LESSONS — append-only ledger）

> **读者**：维护者 / 在本仓改代码或发版的任何 agent。**何时读**：需要某条现行规则的历史来龙去脉、或按
> 「问题记录协议 v2」（见 [`AGENTS.md`](../AGENTS.md) §2）落一条新教训时。
>
> 本文件是**只增不删**的编年台账：每条教训的原文永久保存在这里；「现行真相」的蒸馏版规则住在
> [`AGENTS.md`](../AGENTS.md) 对应主题章节。两者分工：查历史 → 这里；照着干 → `AGENTS.md`。
> 新条目**加在「台账正文」最上方**，标题格式 `### vX.Y.Z / YYYY-MM — 主题`，正文保持
> 症状 → 根因 → 守卫 三要素。
>
> 注：v0.15.0–v0.19.0 各轮的教训当时直接蒸馏进了 `AGENTS.md` 主题章节与 `CHANGELOG.md`
> （如 v0.17 引擎升级 / 名人库、v0.18 pin-forward 复发、法奇门对宫表订正、安装回滚加固），
> 未单列编年节；自本台账建立起，新教训一律在此落原文。

## 索引

| 时代 | 条目 | 一句话 |
| --- | --- | --- |
| v0.14.0 (2026-06) | 古典占星 [古典]/[古典格局] | endpoint 必须登记 `_PYTHON_CHART_ENDPOINTS`；段补≠新工具；离线/live 覆盖分层 |
| v0.13.0 (2026-06) | 4 未同步 AI 技法 + 太乙/八字段口径 | 审计先查自家排除项；`EXPORT_TECHNIQUES` 才是权威清单；请求型 builder 归 Python |
| v0.12.0 (2026-06) | 主限法 v12 核5收敛 + faRelatedPeople | vendor 源=Horosa-Public；params 回显≠引擎值；live 必打 vendored 实例；pdSyncRev 心跳 |
| ↳ 附录 | 主限法 v12 同步清单（历史核对参照） | 显示窗/Vertex/钥匙修真/pdYears 3000/golden v266 |
| v0.11.0 (2026-06) | 星阙 v2.6.3→v2.6.5 parity | 恒星黄道透传；JS 闭包提取三陷阱；政余诚实局限；离线契约禁裸「无」 |
| v0.10.0 (2026-06) | 星阙 v2.5.4/v2.6.x parity | PD 参数走 perchart；依赖闭包是头号陷阱；法奇门外科式接入；live 服务让测试真跑 |
| v0.9.2 (2026-05) | 加固审计 | f-string None 陷阱；禁静默回退；runtime 瘦身实测；preset 是超集 |
| v0.9.0→v0.9.1 (2026-05) | 神数家族 14 路全上 | kentang 路由坑；`Result.snapshot` 嵌套；kinastro 只 vendor 引擎；中立 CWD 验证 |
| ≈v0.8.x | v2.5.0 推运(7)+卜卦/择日 | JS-vendor vs Python-port 决策树的来历与四个坑 |
| ≈v0.7.x | v2.4.0 西占 4 件 | backend-predict 模式；本命增补 JS算/Python排；mundane 复合盘；runtime-source 重同步 |
| v0.10.0–v0.18.0 | 发布完整性编年（缺半/repack/pin-forward 全史） | 三种失效模式的完整案例史；现行法则见 `AGENTS.md` §7 |
| Windows 发布侧 | 独立台账（本文下节） | 三失效模式/逐版本 win 半边史/横切教训（维护者视角） |
| upstream v2.2.1 | AI-analysis SSE Issue #8 | 只影响星阙桌面端 chat 流，不影响 skill 计算路径 |

---

## Windows 发布侧台账（维护者视角 · 原文收编）

Windows 侧离线 runtime 发布的逐版本经验台账。这里是**为什么**与**踩过的坑**的叙事视角；
可执行的操作细节（命令、脚本、闸门）在 [`AGENTS.md`](../AGENTS.md) 的对应条目与
[`OFFLINE_RUNTIME_RELEASES.md`](./OFFLINE_RUNTIME_RELEASES.md)、
[`WINDOWS_RELEASE_BUILD_PROMPT.md`](./WINDOWS_RELEASE_BUILD_PROMPT.md)。名词见 [`GLOSSARY.md`](./GLOSSARY.md)。

## 背景：为什么有 Windows 侧台账

离线 runtime 分 darwin-arm64 与 win32-x64 两个平台构建。**Windows 半边在一台真实 Windows
机器上离线构建**（要 embed Python + JDK17 + Node + astropy + 引擎 + core-js），不进 CI。mac 侧发布
新版时，win 半边常常缺席或滞后——这台台账记录了它的每一次形态与修法。

## 主线：`latest` 的 Windows 半边完整性（三种失败模式）

| 模式 | 表现 | 守卫 | install | 探测 |
| --- | --- | --- | --- | --- |
| **无 manifest** | `runtime-manifest.json` 直接 404 | — | **两平台都坏** | 手查 |
| **darwin-only** | manifest 只列 `darwin-arm64`，无 win zip | **红**（v0.13.0 起自动抓） | Windows 找不到 `win32-x64` / zip 404 | 守卫红 或 `sync --check` |
| **pin-forward** | manifest 列 win32 但**指向旧版 zip** | **绿**（URL 能解析、sha 匹配） | 不坏，但装到**滞后 N 版**的旧运行时 | 只有 `sync_windows_release.py --check` 抓得到 |

**pin-forward 是最隐蔽的**：守卫只查“存在 + 可解析”，查不出版本不匹配。唯一可靠探测是
`sync_windows_release.py --check`——它找版本专属的 `horosa-runtime-win32-x64-vX.Y.Z.zip`
资产，pin-forward 下该资产缺失即报 `[GAP]`。**把 `--check` 的 GAP 当权威，不管守卫什么颜色。**

## 逐版本

| 版本 | Windows 侧发生了什么 | 教训 |
| --- | --- | --- |
| v0.7.0 | 构建脚本用了 `rsync`（Windows 没有） | 改 `shutil.copytree`，让同一个 builder 跨平台可跑。 |
| v0.9.1 | 补 14 个神数引擎 | 神数族（5 独立 + 9 kinastro）要全量 vendor。 |
| v0.10.0 | `latest` 无 manifest → 两平台 install 全坏；且 mac builder 有 shaozi 生成 + plotly 剥离两步，Windows builder 没有 → 会出占位邵子条文且 zip 大 40MB，**却仍通过 verify** | 加 builder 间步骤对齐；`verify` 的 `REQUIRED_ENTRIES` 是两 builder 必须满足的跨平台契约。**动一个 builder 就 grep 另一个 + 两份 REQUIRED_ENTRIES。** |
| v0.12.0 | 启动器加固；建立两道 CI 闸 | PID 归属须用 `[System.IO.Path]::GetFullPath` 规范化后比对（否则 `..\` 未规范化→永不匹配→stop 静默空转、漏杀进程）；java 加 `-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8`（Temurin 17 pre-JEP-400 CJK 乱码）；端口占用快速失败 + 300s 就绪闸。新增 `release-completeness.yml` + `verify_builder_parity.py`。 |
| v0.13.0 | 第一个被守卫**自动抓到**的 darwin-only | 从此靠那道红勾，不再靠手工发现。 |
| v0.14.0 | 造出 `sync_windows_release.py` 一键补齐 | 把手工的“构建→下 darwin→双 manifest+校验和→verify→上传”封装成幂等、安全（无 `--upload` 不做不可逆动作）的一条命令。 |
| v0.15.0 | 天文地占/塔罗两新技法 | 新技法可能带**新后端端点**（`/geomancy/reading`）——源树 astropy 须够新，否则新端点 404 而 verify（只查文件在不在）照过。 |
| v0.16.1 | mac **首次自发全双平台**（重封包 v0.16.0 win zip + 改内嵌 manifest）；但 `export_registry_version` 6→7 只改了 mac builder | 重封包合法的前提是发布 diff **无 payload 层改动**（core-js/引擎/wheels/启动器）；用 HTTP range 读已发布 zip 的内嵌 manifest 可免下 800MB 核验。**数字常量会漂移**：子串级 parity 看不见 6 vs 7，遂给 `verify_builder_parity.py` 加了 `schema_version`/`runtime_layout_version`/`export_registry_version` 交叉核对。 |
| v0.17.0 | pin-forward 模式开始；一掌经/占星地图/名人库 + 引擎全面升级 | 新增 `/location/acg` 端点 + `astrodata-aa.sqlite.gz`（约 50MB，在 `dist-file/astrodata/`）——**源树新鲜度成真风险**，须从当前 Windows 工作区重灌 vendor 并原生验证新端点返回真数据。 |
| v0.18.0 | pin-forward（钉 v0.16.1） | 验证 install 落盘时踩过假警报：真运行时根在 `AppData\Local\Horosa\runtime\current`，别错查了旧的 `.horosa\runtime\current`。 |
| v0.19.0 | 名人库中文化 + 法奇门对宫订正 | 名人库靠 astrodata sqlite 的 `name_zh` 列（07-07 源树已含 5.9 万行）；对宫订正在 `DunJiaFaCalc.js`（JS，随 repo）——原生验证可用 sha 对齐“bundle 里的 JS == repo 的 JS”。 |
| v0.20.0 | pin-forward **基线前移**（钉到上一个真 zip 而非冻结 v0.16.1）；黄历/六壬七政 | 滞后从多版降到约一版；黄历依赖 java 端 `/nongli/time` + `/jieqi/year`，直接裸 POST 会因 payload 归一化差异 500，须走 skill 自己的 `_call_remote` 归一化路径验证。 |
| v0.21.0 | 安装链增强（断点续传/多镜像/进度/uninstall/upgrade/selfcheck） | 新 install UX 往 stdout 打**进度/引导文案，不再是纯 JSON**——脚本化判定改用 `doctor`（仍是干净 JSON）或从混合输出提取末尾 JSON 块的 `asset.sha256`。“版本短路”被 `--force` 绕过，`install --archive --force` 仍做真安装。 |
| v0.23.0 | darwin-only 复发；vendor 缺 v3.5.x 新顶层件（kin_year_domain/ifa_odu/prepareruntime）+ jar 落后须从当前 Windows workspace 重灌；首建死于 Temurin `releases/latest` 半发布窗口（jdk-17.0.20-ga 无 win 二进制）→ JDK 改走 Adoptium API；kintaiyi game_theory/scipy 吓人 traceback 定性为两平台一致良性噪音 | JDK 解析必须 asset-existence-aware；重灌后必跑 `verify_vendor_runtime_sources.py` + `verify_export_contract_mirror.py`；吓人 traceback 先对照 mac 半边定性再动手；无 Mongo 机器 live 验证按「chart 半边绿 + 占时路径 java 500 属预期」判读。 |

## 横切教训

- **构建/验证 parity 是唯一防回归的锚**：`verify_runtime_release.py` 的 `REQUIRED_ENTRIES` +
  `verify_builder_parity.py`（步骤子串 + 数字常量）。改任一 builder，同一提交内对齐另一个。
- **源树新鲜度**：技法多在 repo 层（core-js/service.py），随 checkout 走；但**新后端端点/新数据文件**
  （astropy 端点、astrodata sqlite）来自外部 Windows 工作区。跳版前核工作区 astropy/dist-file 的 mtime
  是否新于目标发布，并原生验证新端点返回真数据。
- **环境坑**：PowerShell 5.1 以 cp1252 读无 BOM 的 `.ps1`（毁 CJK 字面量）→ 用 `pwsh`；Python stdout
  cp1252 遇 CJK 崩 → `PYTHONUTF8=1`；`gh api --jq .tag_name` 返回裸标量不是 JSON。
- **原生验证优先走真生产路径**：`install --archive <zip> --force` → `doctor`（结构）→ 启动加固启动器 →
  直接压测 chart 端点（ken×3 + 神数 + geomancy/acg 各 `rc=0`/真数据）+ 查无乱码。
- **不碰 mac 层**：Windows 侧只补 Windows 半边与 Windows 侧工具/文档；不改 mac 的发布自动化。

---

## 台账正文（新条目加在最上方）

### v0.25.0-dev / 2026-08 — 段级欠账回填（批 1 起）

- **印占 53 段：verbatim vendor 胜过 Python 移植。** 上游 `buildJyotishSnapshotLines`（IndiaChart.js:479，
  578 行）是**纯格式化**函数——读后端已算好的 `chartObj.jyotish`（30 个子树）产 51 个具名段。闭包极小
  （只依赖 7 行 `gfmTable`，`PCN` 是块内局部量，零 AstroConst 依赖），逐字 vendor 后真盘一次跑通 57 段。
  若手抄成 Python 是 600 行抄写面，任一措辞漂移都会与桌面端不一致。**判据**：纯格式化 + 小闭包 = vendor；
  只有需要发 HTTP 或依赖 Python 侧数据时才移植。
- **`js_client.run()` 已解包 envelope 的 `data`**，返回的就是 runner 结果对象。照 `_attach_natal_extras`
  的样子写成 `js.get("data")` 会恒为 None → 段静默不出（本轮踩了一次，表现为「挂载了但段数没变」）。
- **上游用占位段名登记动态段族**：印占 11 个 `座运·<变体>` 在 preset 里是单个 `座运·X`（同 horary 的
  `专题深化·X`）。折叠规则加进 `map_legacy_section_title`，否则实产段全成 unknown。
- **段名折叠方向要跟上游走**：canping/heluo 早期把上游长名（`大运·歲運`/`先天卦·元堂爻辞`）折叠成短名，
  而上游 preset 现已正式声明长名 → 反转映射（canonical=长名，短名留作向后兼容）。
- **主限法语义变更（v3.6.0）**：`pdSyncRev` v12→**v15**，方位法从「核 5 + legacy」开放到全谱 13 法，
  **placidus 已是真方位法、不再回退 core_alchabitius**（实测 114 行 vs 64 行）。原测试断言「两法逐位
  一致」在新引擎下必红，而且方向危险——引擎真回退时它反而会绿。已改为「都产真行集且彼此不同」。
- **整文件重 vendor 会抹掉手工加的 `export`。** 上游把 `normalizeBackendPan` 一类叠加函数留作模块私有
  （组件内部自用），skill 的 headless 工具层却要 import 它——旧 vendored 副本是人手加的 export，一次
  全文件重 vendor 就把它抹了，症状是 `SyntaxError: does not provide an export named …`（太乙栽过）。
  `revendor_core_js.py` 现按「skill tools 谁在 import 它」反查自动补 export，不写死函数名清单。
- **vendor 树布局 ≠ 上游 src 布局**：上游 `../../utils/baziLunarLocal` 在 vendor 树里是 `../bazi/…`。
  重 vendor 器按 basename 自动重定位；**找不到唯一匹配就大声报 UNRESOLVED**，绝不留坏 import——
  留着的话模块加载直接失败，而那比「load 过但真盘崩」还早一步，必须显式暴露给人决定补 vendor 还是写 shim。
- **剥 `fetch*Pan` 会留下孤儿 import**（`cachedKentangFetch` 等网络层助手），同样让模块加载失败；
  按「符号是否仍被引用」判定删除，不按文件名黑名单。
- **本命增补段的门控本就该覆盖整个 chart 家族**：`_attach_natal_extras` 只开给 `{chart, mundane}`，
  而上游给 13 宫/希腊化盘也出 12分度/主宰星链/寿命格局 —— 放开门控即得 3 段（chart13/hellen_chart）。
- **上游有行内段头写法：`[段名] 正文` 同行**（演禽演法五段就是），而 skill 的导出解析器要求
  **段头独占一行**——同行写法会被整体误解析成一个空标题段，于是「文本里明明有这些段、却全部报
  missing」。修法是在 JS 侧只在段头后断行（`/^(\[[^\]]+\])[ \t]+/gm` → `$1\n`），正文逐字不动，
  快照仍与上游同源。**排查判据**：段出现在 `sections` 里但同时出现在 `missing` 里 = 解析形态问题，
  不是缺 builder。
- **preset / optional 之外还有第三态**：上游 `AI_EXPORT_DEFAULT_OFF_SECTIONS` 的语义是「登记进
  preset（可勾、勾了永久尊重），但用户未自定义时默认不导出」——doctrine 型大段（判语库/古籍全文）
  专用。skill 侧并入 optional（对解析器同义：缺席不算漏）并在契约里单列 `default_off_sections`。
  **注意上游的 migration union 也排除这些段**，否则升级会把它们硬并进已自定义用户的选择 = 变相默认开。
- **抽 AstroConst 子集做 shim 有两条边界规则**（都踩过）：① 块的终点是「下一个顶层 `export const`」
  而非分号——上游多数常量**不带结尾分号**，按分号切会把后续所有声明卷进来（`Identifier already
  declared`）；② 必须保持**上游原序**，`LIST_URANIAN` 这类聚合常量引用了排在其后的符号，重排即
  `ReferenceError: before initialization`。宁可逐值抽取也不手写猜值——这类表以 AstroConst.* 为键。
- **重 vendor 一个技法要按「上游文件清单」而不是本地清单**：按本地 `ls` 拼参数会漏掉上游**新增**的
  文件（tarot 的 `openingOfKey.js`/`reversalModes.js` 就这样被漏了），随后重 vendor 报「0 个文件变化」
  却依旧运行失败——同名文件也可能不同源。判据：报 0 变化但功能仍缺 = 清单取错了，不是已同源。
- **shell 里 `cd` 到上游树后不要再跑仓内脚本**：相对路径会解析到上游目录（本轮出现过
  `can't open .../Horosa-Public/.../scripts/revendor_core_js.py`）。命令一律从包根起。
- **回填铁律的实操顺序**：先 live 跑出**实产段名**，再拿它与上游 preset 做三向差（都有 → 进 preset；
  上游有实产无 → preset+optional 双登记；实产有上游无 → 查是 skill 自有基础段还是占位名族）。
  绝不能照抄上游 preset 了事——那会造出死条目，让每次真实导出都报 missing。


### v0.24.0 / 2026-07-31 — 守卫「结构性失明」+ MCP 面三处静默破损

- **守卫全绿却漏掉 8 个上游版本：同源校验必须比对上游 HEAD，不能比对自己的 vendored 拷贝。**
  症状：`verify_export_contract_mirror.py` 与 `verify_vendor_runtime_sources.py` 全绿，而上游已 v50、
  skill 镜像仍 48。根因：前者读 `vendor/runtime-source/...aiExport.js`（本地 vendored），后者用
  `MIN_AIEXPORT_SETTINGS_VERSION = 48` 的**下界**断言 —— 两棵 vendor 树都 gitignore，没人 re-sync
  就永远自洽；`horosa-core-js/src/vendor`（受 git 跟踪）更是**零守卫**。守卫：新增
  `scripts/verify_upstream_sync.py`（`HOROSA_SOURCE_ROOT` 定位上游 → aiExport 版本恒等 + 哨兵文件
  sha256 + core-js 按 basename 逐文件比对；无上游树时输出 `{"skipped":true}` + `::notice` 而**不装绿**，
  `--require-upstream` 在 release 链硬失败）；下界断言改为与 registry 常量**恒等**。首跑即抓出
  112 个 core-js 文件漂移 + 4 个哨兵漂移（含 `perpredict.py`/`perchart.py` —— 正是主限法 13 法白名单所在）。
- **键级对齐 ≠ 段级对齐：v0.23.0 的「整版对齐 v48」是虚账。** 实测 skill 653 段 vs 上游 v48 的 843 段。
  原 mirror 守卫自述 "Deliberately NOT a per-section diff"，于是 180 段欠账藏在全绿背后。守卫：新增
  `scripts/verify_export_section_baseline.py` + 受 git 跟踪的 `contracts/export_section_debt.json`
  **棘轮**（新增欠账 fail；还清了也 fail 并提示 `--update-baseline` 收紧，使欠账只减不增、每次回填在
  git 里可见）。重同步到 v50 后真实欠账 = **314 段 / 51 多余 / 8 缺键，跨 62 技法**（印占 53 段最大）。
  同时把 `MIRRORED_UPSTREAM_AIEXPORT_VERSION` 的语义写死在注释里：**它表示「对账基准版本」，不表示
  「该版段全有了」**——两个数字必须一起读。
- **`__signature__` 漏设 = 工具静默不可调用（P0）。** `horosa_tool_run` 只设了 `__doc__`/`__annotations__`
  没设 `__signature__` → FastMCP 内省 `**kwargs` 生成 `{"kwargs":{"type":"string"},"required":["kwargs"]}`，
  而它是 `HOROSA_MCP_COMPACT=1` 下抵达全部技法的**唯一**通道。连带 bug：`request` 存在时
  `_merge_mcp_arguments` 整体改用 request 作载荷，把兄弟参数 `tool_name` 丢了。测试之所以没抓到，是因为
  `test_mcp_server.py` **从不走 `srv.call_tool`**（直接调 service 层）——守卫：新增 `tests/test_mcp_contract.py`
  按「客户端真正看到什么」断言（list_tools 每个工具有描述/title/无 `kwargs` 参数/无残留 `$ref`；
  call_tool 跑通闸门/成功/畸形/request 通道/数字经纬度五路）。
- **`__signature__` 优先级高于 `__annotations__` → structured output 全线失效。** 9 处
  `__annotations__ = {"return": ToolEnvelope}` 是死代码，91 个工具 `outputSchema` 全 None；讽刺的是唯一
  拿到 outputSchema 的恰是那个坏掉的 `horosa_tool_run`（因为它没有 `__signature__`）。修法：签名带
  `return_annotation`。**但开启前必须先统一错误载荷**——出参被 server+client 两侧校验，而闸门返回的是
  5 键裸 dict，声明 outputSchema 后会被打成协议级 ToolError，**整个澄清闸当场报废**（实测复现）。
  故先给 `ToolEnvelope`/`DispatchEnvelope` 加可选顶层镜像 `code/message/details`、把闸门/elicit/校验
  三条错误路径全部转成合规信封，再接 `return_annotation`；且因 claude-code#25081（带 outputSchema 时
  工具列表静默消失，stale-closed 未确认修复）**默认关闭**，`HOROSA_OUTPUT_SCHEMA=1` 显式开启。
- **FastMCP 注册时 `validate_input=False`——广告 schema 与实际校验解耦，这是解开死结的钥匙。**
  据此把签名改成「广告保真、校验放松」：字段描述/枚举/`[required]` 标记照登，但全部 `default=None` +
  `Annotated[Any, WithJsonSchema(...)]` → MCP 层零必填。一次修好三处：文档承诺的 `request={…}` 逃生通道
  此前**永远走不到**（必填字段先被 arg model 拒）、`{"lat": 39.9}`（模型极高频）在归一化之前就被拒、
  以及两者都绕过 `agent_recovery` 回裸 pydantic 错误。**坑**：把 property 摘出来单独广告时 `#/$defs/…`
  解析不到根，且模型间存在自引用（嵌套 BirthInput）——`WithJsonSchema` 里残留 `$ref` 会让 pydantic
  `KeyError` 到整个服务器起不来。内联必须「遇环/超深/缺失一律降级为无约束对象，绝不留下 `$ref`」。
- **仓库搬家后 `.venv/bin/*` 的 shebang 仍指旧路径** → `uv run pytest` 静默回退到全局 pytest（旧依赖，
  报 `mcp.types 无 Icon`），而 `uv run python -m pytest` 正常。判据：直接跑 `.venv/bin/pytest` 报
  `bad interpreter`。修法 = §8 标准 venv 重建。
- **log4j 的 `${env:HOME:-${sys:user.home}}` 带默认值形态未被替换** → 日志按**字面量目录名**落在启动
  CWD，在用户工作目录里留下一个名字诡异的目录，且没人知道日志在哪。`_rewrite_runtime_log4j` 原来只处理
  `${env:HOME}` 一种写法，现两种都归位。
- **生态基准变了（2026-07-31 核实）**：MCP **2026-07-28 规范已发布**、python-sdk **v2.0.0 已上 PyPI**
  （v2 是破坏性重写，钉 `mcp[cli]>=1.28.1,<2` 不迁）；本仓**未使用** logging/roots/sampling 三项废弃 API，
  且 `_maybe_elicit_gate` 本就在 `service.run_tool` 之前 → 天然满足 v2 的「工具函数会被整体重放」要求。
  **Claude Code 的工具搜索已默认开启**，83 工具的上下文膨胀在该客户端已由平台解决，ROI 重心移到
  server `instructions`（此前只用了 164/2048 字节）与 `_meta["anthropic/alwaysLoad"]` 入口标记；
  Cursor 仍有较紧工具数上限 → 新增 `HOROSA_TOOLSETS` 分组白名单（registry 的 domain 天然可用）。
  **官方 Registry 可不发 PyPI 上架**：`registryType: "mcpb"` + GitHub Release 的 .mcpb + `fileSha256`，
  正好绕开 horosa-core-js 在 wheel 之外的分发归属难题（`registryType: "github"` **不是**合法通道）。

### v0.23.0+ / 2026-07-22 — issue #14：Java 后端被环境杀死时全盘卡死 → chart-only 降级 + 诊断透传

- **症状**（用户报告，Windows 11 + Clash Verge/安全软件）：`selfcheck` 挂死、`doctor` 只报
  `services:not_running` 不说原因；Java(:9999) 启动即静默退出、无自身日志。**根因（环境层）**：jar 的
  `AIAnalysisProxyService` bean 构造期 `new HttpClient()` → `Selector.open()` → JDK-17 `PipeImpl`
  在 Windows 上**硬编码优先 AF_UNIX** 做内部 loopback（`PipeImpl(sp)` 写死 `this(sp,true,false)`），
  且 **connect 失败无 TCP 回退**（只有 bind 失败才回退）——代理/VPN/安全软件的 WFP 过滤拦
  `UnixDomainSockets.connect0` 即整跳崩；报告者机器连 java.exe 的 TCP loopback 也被拦（WFP 驻留内核，
  停服务不够、需禁用+重启），Java 侧无解。**根因（我们的放大器）**：manager 就绪门要求 8899+9999 双活；
  chart-up/java-down 触发 partial-recovery 把**健康的 chart 也停掉**重试，二次同败后 raise——只需 :8899
  的三式/神数/地占等全被连坐；Java 崩溃栈无处可看（log4j appender 随进程死，doctor 不读启动器捕获的 std 流）。
- **fix/guard（同一 change 全落）**：① 启动器降级门（Windows 模板 + `manager._run_start_command`
  **锁步**）：java 进程死 → 秒级 exit 0 降级 + marker `java backend process exited` + java 日志尾进
  stdout；java 慢 → 窗尽头 exit 0 降级；chart 死 → 照旧 throw。实测损坏 jar 场景 **5s** 降级退出
  （旧行为 300s throw + 全锁）。② manager 接受 chart-only 为降级成功：`runtime.start_degraded_chart_only`
  warning + runtime_state `degraded_chart_only`；见 marker 时等待截短 ≤20s；degraded ready **不再**触发
  破坏性 stop+retry。③ doctor 分半报 `services:{java_backend,chart}_not_running`，java 死时附
  `java_diagnostics`（读最新 `.horosa-local-logs/*/astrostudyboot.std{err,out}.log` 提取
  `Application run failed`/`Caused by:` 链，best-effort 永不 crash doctor）。④ selfcheck：`nongli_time`
  （java 面）失败自动回退 chart 侧 `wangji` 探针——降级机器上 ok=true + `degraded: chart_only` +
  定向 next_action，不再挂死。⑤ README×2 排障：受限网络 assets-API 安装法（github.com:443 不通时）+
  WFP 干扰判据。回归测试：`test_runtime_manager.py` 降级三测（`_run_start_command` 降级判定 /
  start 不破坏性重试 / doctor 摘录）+ 分半 issue 命名测。

### v0.23.0+ / 2026-07-22 — Temurin「releases/latest」半发布窗口打空 JDK 下载（Windows 补建时踩中）

- **症状**：v0.23.0 Windows 半边补建时 `build_runtime_release_windows.py` 第一步即死：
  `could not resolve Temurin asset for OpenJDK17U-jdk_x64_windows_hotspot_.zip`。**根因**：builder 从
  GitHub `temurin17-binaries/releases/latest` 按资产名匹配下载 JDK；GitHub 的 `releases/latest` 按
  **tag 提交日期**取，Adoptium 刚打 GA tag（jdk-17.0.20-ga）而平台二进制尚未传完的窗口内，该 release
  资产为空/不全 → 匹配空手。且其 `/releases` 列表顺序按 release 对象创建时间（老版本重发会插队到最前，
  实测 2023 年的 17.0.9+9.1 排第一），「遍历列表取第一个含资产的」同样不可靠。linux builder 同模式同病。
  **fix/guard**：两个下载 JDK 的 builder（win/linux）改走 Adoptium 官方分发 API
  `api.adoptium.net/v3/binary/latest/17/ga/<os>/x64/jdk/hotspot/normal/eclipse`（307 只指向**已存在**的
  最新 GA 二进制，`download()` 的 `curl -fL` 跟随重定向；实测解析到 17.0.19+10、正确跳过无资产的
  17.0.20）；`verify_builder_parity.py` 新增断言：JDK-downloading builders（win/linux）必含 Adoptium
  API URL、禁再引用 `temurin17-binaries/releases/latest`；mac builder 不下载 JDK（vendored
  runtime/mac/java）豁免。
- **kintaiyi `game_theory` 的 scipy 缺失是两平台一致的良性 prewarm 噪音**：symptom = bundled chart 服务
  启动日志出现 `prewarm_kentang_modules → kintaiyi/game_theory.py → ModuleNotFoundError: No module named
  'scipy'` 整段 traceback，看似 taiyi 引擎坏了。root cause = 上游 kintaiyi 新增 **opt-in** 博弈论模块
  （`pan(..., enable_game_theory=False)` 默认关、`if enable_game_theory` 内懒 import），scipy 既不在 ken
  依赖集（§6 只有 bidict/numpy/kerykeion/ephem/pendulum）也不在**任何**平台 bundle 内——实测 v0.23.0
  darwin tar 同样含 `game_theory.py` 且无 scipy，两平台行为一致；skill 调用面永不置 True。判据 =
  `/taiyi/pan` 返 `ResultCode 0 + source kintaiyi` 即健康，该 traceback 无需处置；**勿为它加 scipy**
  （~40MB，瘦身红线，服务于永不触发的功能）。守卫：CI 起不了 runtime（§7），无廉价断言点，按 §8 症状表
  + 本条documentation 处置。顺带观察：darwin tar 混入 `._game_theory.py`（AppleDouble，inert，
  mac 侧滤网漏网，无碍）。

### v0.23.0 / 2026-07 — 全面重同步至上游 v3.5.1（全年份域 + 地占大改 + 六爻扩充 + 5 新技法）

- **导出契约三层脱节收口（40<44<48 → 48）+ mirror 守卫**：`MIRRORED_UPSTREAM_AIEXPORT_VERSION` 40→48、
  `AI_EXPORT_SETTINGS_VERSION` 10→11（5 新技法 + geomancy/primarydirect 对齐）。新守卫
  `verify_export_contract_mirror.py`：①版本锁步——vendored aiExport 的 `AI_EXPORT_SETTINGS_VERSION` 必须
  == skill `MIRRORED_UPSTREAM_AIEXPORT_VERSION`（堵「同步旧树」与「改一个忘改另一个」）；②技法键覆盖——
  每个 skill 导出键须在 vendored 上游 `AI_EXPORT_TECHNIQUES` 内，或走 `KEY_ALIAS`（wangji↔huangji、
  acg↔locastro 键名分叉）/`DIVERGENCE_WHITELIST`（astrodata skill-only、generic、astrochart_like）。
  jieqi 分点子键经 JIEQI_SPLIT_TECHNIQUES spread 入上游，按字符串字面识别。守卫需 vendored 树 → 跑在
  self-hosted release runner（release.yml），非 GitHub CI（后者无 vendored 树）。**逐技法对齐、非整版盲抄**：
  skill-extra 段（起卦信息）、UI-only 死段（主限天球）、收缩契约由白名单显式豁免。

- **`kin_year_domain.py` 同步漏拷（sync 脚本枚举陷阱）**：symptom = 从上游 v3.5.0+ 重同步
  `vendor/runtime-source` 后，每个 ken/神数 引擎在**首个域外（BC/远期）请求**上 500。root cause =
  上游 v3.5.0「全年份域」把域外四柱回退逻辑抽成**顶层共享模块**
  `Horosa-Web/vendor/kin_year_domain.py`，被 16 个引擎 `config.py`/`jieqi.py`/`shenyishu.py` 懒
  `from kin_year_domain import solar_term_name/extreme_pillars`。`sync_vendored_runtime_sources.sh`
  的 require+rsync 清单**逐引擎目录枚举**，漏了这个**平级的顶层单文件** → 重同步静默丢弃它，域内请求
  照常、域外静默炸。guard = sync 脚本显式拷 `kin_year_domain.py`（+ 其兄弟 `test_month_pillar_boundary.py`）；
  `verify_vendor_runtime_sources.py` REQUIRED_PATHS 断言该文件 + geomancy `data/ifa_odu.json` + xuanshi
  `public_data.sqlite` 真文件，并加**内容断言 vendored aiExport `AI_EXPORT_SETTINGS_VERSION >= 48`**
  （通用拦「同步了旧树」，堵住三层版本脱节 skill<vendored<上游 的静默复发）。教训 = 上游把子逻辑上提为
  vendor 根级共享件时，逐目录枚举的 sync 清单必须同步补顶层单文件。
- **kentang registry 已懒挂载 → raw-vendor hard-fail 警告过时**：AGENTS §5/§8 旧警告「raw vendor 直接起
  chart 服务时 registry 列了未 vendor 引擎会 hard-fail（graceful patch 只在打包 staged 拷贝）」在
  vendored v44 与上游 v48 都已不成立——`astropy/websrv/kentang/registry.py` 现用 `_LazyMountedService`
  （默认 `HOROSA_KENTANG_LAZY=1`）：缺引擎只在**首请求**时响亮 500 + 下次重试，启动不炸。18 个 mount 的
  引擎全在 vendored 集合内。影响 live 验证法：不能再靠「启动即知」，改为**启动后逐 mount 打真请求**强制加载。
  （按 §2 compaction 蒸馏进 AGENTS §5/§8。）
- **v3.3.6「有情/无情」purity 是 UI-only，不进 AI 导出链（防后人重查）**：上游 astroPatternOverview.js 的
  purity 只被 `AstroInfo.js` 消费；`astroAiSnapshot.js::buildPatternOverviewLines` 与 [古典] 接纳/互容行
  **都不渲染 purity**。故 skill 镜像导出契约**无需移植 purity**。真正落后的是 pre-v44 的一处快照可见细节：
  [古典] 正/邪接纳行缺 FIX-15 `（拒绝）` 标（supplier 在 beneficiary 座为 exile/fall = 凶接纳）——已补
  `_reception_reject_mark`（镜像 astroAiSnapshot.isReject）。
- **geomancy v3.5.1 地占大改版接入**：`_build_geomancy_snapshot_text` 对齐上游 v48 builder —— [判定] 补
  首母中止/sikidy 三道校验+列比对/hakata 四片盘；[解读技法] 补 points_parity 取样域/黄道宫三方/数量+判官之数；
  新增 [转宫派生]/[定局落星·甲乙]；十二宫·图形入宫 与 十六图形 改 **markdown 表**（印度派多支名/曜两列）。
  ifa（西非同族）为**结构对照模式、不产占断**：schema 白名单 8 家占断传本、明确拒绝 ifa
  （`tool.geomancy_structural_only_unsupported` + 文化声明），换来 判定/十二宫/十六图形 可作**必出段**的强契约；
  [图形释义]（doctrine 默认关）与 [边界声明]（ifa）skill 不产，仅进 preset 作 export_parse 识别面（同 fengshui）。
- **primarydirect 段名对齐**：上游 v48 判 `主/界限法设置|表格` 为死名、真名 `主限法设置|表格`；skill builder/
  preset/report-payload-map 同步改真名，旧名走 `map_legacy_section_title`。UI-only 新段
  `主限天球·当前动画所指`（3D 动画所指）headless 不产，**故意不进 preset**（§5 UI-only 段过滤）。
- **live 0-skip 需 Mongo：干净机器只能验 chart 半边**：vendored chart 服务（`:8896`）**完全独立**，
  geomancy/predict/astroextra/ken-formatter 全可验；但 Java 聚合层（`:9996`）的 app 注册在 Mongo 里，
  无 Mongo 时 `/nongli/time`·`/bazi/birth`·`/ziwei/birth`·`/liureng/*` 一律返 `ResultCode 9999
  "no.register.app.in.sys"`（不是启动慢、是缺注册）。连带 qimen/taiyi/jinkou（需 `/nongli/time` 脚手架）
  与 5 新技法的**占时**路径在无 Mongo 机器上跑不了 live。判据 = 这类 500/9999 全落在 java 端点、chart 端点
  全绿 → 环境限制而非代码问题；这些路径的离线覆盖 = FakeClient 全形状 `/nongli/time` 桩 + FakeJsClient +
  node golden，占时派生纯 Python 亦离线可测。完整 0-skip 留给带 Mongo/Redis 的发布机。
- **core-js 重 vendor（baziLunarLocal 全年份域守卫 + gua 六爻大扩充）**：
  ① `baziLunarLocal.js` 重拷带入 v3.5.0 **全年份域守卫**——`lunarDomainGuard.isLunarJsYearReliable`（AD1~9999
  外 lunar-js 节气静默错位 → 月柱错，比崩溃更危险，故域外 throw 让上层走后端星历）+ `dateStrSafe.parseDateParts`
  （`'-7040-07-19'` 裸 split 撕成 NaN 年）两个新 import-free 兄弟依赖随拷；公共 export 面不变（canping/heluo/
  yizhangjing/zhengchuan 链零改）。
  ② **gua 六爻整子树重 vendor**：14 引擎模块 + 6 data（tianjiDoctrine 9581 行纯数据）统一 sed 变换
  （`./X`→`./X.js`、`../../utils/helper`→`./guaHelper`、`../../utils/safeStorage`→`./safeStorage` no-op shim）。
  新增 liuyaoDuanJue/GuFa/YingQi/ShenShaEx 引擎 → `analyzeLiuyao` 新出 `duanJue`/`yingqi` 等键（旧键全保留=
  向后兼容）；`tools/liuyao.js` 把「断诀命中」（金锁玉关/随官入墓/随金伏…命中项，**空 render 过滤**）+「应期」
  折进已有 [断卦结构]（optional）段，不新增段名、契约零变。closure 干净（引擎只 import 兄弟+data+2 shim，
  无 React/canvas）；golden + analyzeLiuyao real-chain 验证。
  ③ **本轮 core-js 已完成 = bazi + gua**；ken formatter（DunJia/JinKou/TaiYi 各 4~23 行极端年 clockTime/BC-safe
  显示微漂）、tarot engine（cardSchema/reportText/verdict 微漂）、tongshefa 三十二观、calendar 4→14 段（黄历
  四页签，需审 fengshui/zeri.js headless）**列为后续专项**——ken 引擎全年份域已由 Phase 0 runtime 重同步覆盖，
  这些是极端年显示 polish 与能力增补，非在域正确性缺口，留待专项验证 pass。

### v0.22.0 / 2026-07-16 — parity lint 常量交叉扩到全部 manifest-stamping 脚本（Windows 侧）

- **症状**：`export_registry_version` 在 linux builder + 两个 scaffold 曾滞留 6 而 mac/win 已到 10
  （上一条台账已记），CI 全绿放行。**根因**：`verify_builder_parity.py` 的
  `SHARED_MANIFEST_CONSTANTS` 交叉只读 mac/win 两个文件——第三平台 builder 与 scaffold 不在射程。
- **守卫（本条完成上条教训的机器守卫件）**：lint 新增 `CONSTANT_STAMPERS` 清单
  （mac/win/linux 三 builder + windows/linux 两 scaffold），三常量
  （`schema_version`/`runtime_layout_version`/`export_registry_version`）N 路交叉断言；
  清单中不存在的文件跳过（容忍 repo 演进），存在但缺常量 = 错。已 mutation 验证：
  临时把 `scaffold_windows_runtime.py` 改 6 → FAIL 并点名 `Windows scaffold=[6]`，还原 → PASS。
- 注：协议第 3 件（CHANGELOG）不可执行——本仓当前不存在 `CHANGELOG.md`（文档重构后未保留），
  §2 协议文本与树的这一处不一致留待 mac 侧裁定。

### v0.21.0+ / 2026-07-16 — MCP 面顶级化 + 三方审计（上游基线/用户路径/前沿调研）

- **上游同步基线纠偏**：上游 Horosa-Public 实际已到 **v3.4.0 / aiExport v48**（UPGRADE_LOG 最新条目在文件**顶部**，
  用 tail 看会误读旧版本）；skill 导出契约整版镜像 ≈ **v40** + 零散摘取 v44 个别段（拼接式而非整版对齐）。
  约 20+ 技法有段级缺口；一档必同步清单（indiachart ~40 Jyotish 段、guolao 四段、星运族×12 起盘信息、
  tongshefa/jinkou/tieban 计算层、sanshi 紫微四化、horary/election/relative/ziwei 补段、taiyi「起盘」段
  ——旧「kintaiyi 不产此段」判定已过期（上游 `webtaiyisrv.py:306` 现由后端产）、qimen 八宫克应、
  zhengchuan 新技法）与二/三档全表见本轮审计 agent 报告（要点已录入本条）；`wangji` vs 上游导出键
  `huangji` 存在**键名分叉**（外部 huangji 导出 parse 不识别，需 alias）。守卫：`exports/registry.py`
  新增机读常量 `MIRRORED_UPSTREAM_AIEXPORT_VERSION = 40`，整批同步后必须更新。
- **构建常量三平台漂移**：`export_registry_version` win builder=10 而 **linux builder + 两个 scaffold=6**
  （verify_builder_parity 只交叉 mac/win，linux/scaffold 不在其射程）。已统一为 10；教训 = 新增第三平台
  builder/scaffold 时，`SHARED_MANIFEST_CONSTANTS` 类常量的锁步检查范围要同步扩。
- **venv shebang 陷阱（仓库搬家后必踩）**：仓从 `Downloads/` 移到 `Desktop/` 后，`.venv/bin/*` console-script
  的 shebang 仍指旧绝对路径 → `uv run pytest` 静默回退到**全局** pytest（环境里是旧 mcp，无 Icon）报
  `module 'mcp.types' has no attribute 'Icon'`，而 `uv run python -m pytest` 正常。症状 = 直接执行
  `.venv/bin/pytest` 报 `bad interpreter: …旧路径…`。修复 = AGENTS §8 标准 venv 重建。
- **MCP 面升级（服务器侧）**：78+8 工具全量 **tool annotations**（口径：全部 openWorldHint=False；
  查询类 readOnly+idempotent；计算类 readOnly=False/destructive=False/idempotent=False——会追加本地 run 行，
  如实标注）；**elicitation 双轨澄清闸**（客户端有能力→原生表单：按默认一跳闭环 / 补充设置→备注回带给
  agent 不代答参数；无能力/异常→逐字节回落旧 agent_recovery 错误往返；`HOROSA_MCP_ELICIT=0` 总闸）；
  **3 prompts**（quick_cast/annual_fortune/export_report → Claude Code 斜杠命令）+ **2 resources**
  （技法目录/导出注册表）；server icons + website_url；compact/dispatch/factory 路径补 pydantic
  `ValidationError` → `build_validation_recovery` 兜底。**实测澄清**：动态 `__annotations__` 并未激活
  FastMCP structured output（`outputSchema: False`）——此前审计担心的「错误分支违约」不存在；structured
  output 保持未来 opt-in（Claude Code 曾有带 outputSchema 掉工具的事故，开启前必须实测 `tools/list`）。
- **registry 合规**：`server.json` 按官方 2025-12-11 schema 重写（reverse-DNS name `io.github.horace-maxwell/
  horosa-skill`、`homepage`→`websiteUrl`、非 schema 字段收进 `_meta`、`$schema` 钉 static URL、transport
  对象化）；`verify_server_json.py` 从「字段存在性」升级为**严格 schema 结构断言**。README 的 Changelog
  徽章链接 gitignored 的 CHANGELOG.md（公开仓 404）→ 已删（EN），docs-sync 加「README 禁引用 CHANGELOG.md」
  守卫。CITATION.cff 在 v0.20/v0.21 又双叒停在 0.19.0（checker 未进 CI 前的积欠）→ 已修，CI 已有守卫。
- **接入面**：`client config` 新增 **cursor / vscode** 格式（输出官方 install deep link / `vscode:mcp/install`
  链接 + `code --add-mcp`，真实路径注入）；`--write` 改为 **mcpServers 按键合并**（原来整文件覆盖会清掉用户
  已有的其他 MCP server）；新增 **Claude Code plugin/marketplace 三件套**（`.claude-plugin/{plugin,marketplace}.json`
  + 根 `.mcp.json` 用 `${CLAUDE_PLUGIN_ROOT}`，`/plugin marketplace add Horace-Maxwell/horosa-skill` 一步接入）；
  SKILL.md frontmatter 补 agentskills.io 规范字段（license/compatibility/metadata.version，随版本锁步进
  docs-sync）；README×2 补 Cursor/VS Code/Plugin 行与 `calendar_month`（v0.20 新工具漏档 EN/SKILL）。
  依赖钉板 `mcp[cli]>=1.27,<2`（SDK v2 于 2026-07-27 发稳定版、7-28 新规范废弃 sampling/roots/logging——
  本仓未用，迁移窗口 12 个月）。
- **前沿调研结论存档（2026-07-15 逐页核实）**：elicitation Claude Code≥2.1.76/Cursor/VS Code 已支持（Claude
  Desktop/Codex/OpenWebUI 未支持→双轨必要）；llms.txt 有实证证据不值得做（97% 无人读取，Google 明确不用）；
  MCPB(.mcpb) 可给 Claude Desktop 一键安装（uv 型 manifest，待打包）；MCP Registry 发布需 PyPI 包 +
  `mcp-publisher login github`（PyPI README 放 `mcp-name:` 行验证）；MCP Apps 扩展值得盯（Claude Code 尚未支持，
  支持后可做盘面可视化）。

### 开源栈上不可得的段 —— 明确排除项台账（回填时先查这里，别当缺口重查一遍）

判据统一是：**上游 builder 依赖的数据在开源 Horosa-Public 栈上取不到**（后端无该路由 / 依赖 canvas
渲染 / 依赖交互点位），而不是「本仓还没写」。每条都附可复核的证据，下次审计直接引用。

- **`guolao` 的 `[虚实]` / `[本命化曜]` / `[流年流曜]`（3 段）** —— 三者读 `moiraRules.weakSolid`
  与 `moiraRules.yearStars`，该对象来自后端 **`/qizheng/moira`**（上游 `services/qizheng.js:10`
  `fetchMoiraQizhengRules`）。开源 astropy 的 `websrv/` 只挂了 `webqizhengelectionsrv` 与
  `webqizhengkinsrv`，**没有这条路由**（仓内 vendored 实例实测 POST `/qizheng/moira` → 500）；
  上游的本地回退 `buildLocalMoiraRules` 只产 `houses/patterns/godHits`，不产这两个字段。
  → 同批的 `[星曜庙旺与星点动态]` **可得**（纯表查询、只吃 `/chart` 响应），已于 v0.25 补上；
  别因为「guolao 还欠 4 段」就以为整批同因。
  这也顺带裁掉了历史矛盾：registry 里「headless 未移植」的旧注释与 LESSONS 早期「已 DONE」的
  记录互斥 —— 实际是 `政余格局` 早已 DONE（走 vendored Moira DSL），欠的是另外三段且不可得。

- **`primarydirect` 的 `[主限天球·当前动画所指]`** —— 段名即语义：它指的是 3D 天球**动画当前所指**，
  没有动画就没有「所指」。UI-only，不进 preset。

- **`fengshui` 的 `[风水·玄空六法]` / `[风水·命理派]` / `[风水·综合罗经]`（3 段）** —— 整个 fengshui
  技法本就是仓内**早已明文的排除项**（canvas + 户型图上传 + 交互点位驱动，`new FengShuiEngine(canvas,…)`，
  无 birth/time 输入；SKILL.md 与 README×2 都写了「明确排除·风水未完成 headless 化」）。这三段只是该
  排除面下新增的页签，不改变结论。**别因为「上游 preset 里有」就重新当缺口查一遍**——这已是第四轮踩它。

- **从上游 React 文件抽纯函数：闭包必须连 `const` 箭头助手一起走，且别整份 vendor。** 本轮四个
  「功能缺口」段全部落地，路上踩了三次同一形态的坑：
  1. 只按 `function` 声明做传递闭包 → 漏掉 `const luckHouseName = …` 这类箭头助手，症状是段**恒空**
     而不报错（我的 wrapper 有静默 catch）；
  2. 漏掉跨文件的**别名导入**（`houseName as luckHouseName`），同样恒空；
  3. 图省事整份 vendor `ZWLuckPanel.js` → 把 JSX 带进来，Node 直接 `Unexpected token '<'`。
  做法：闭包同时扫 `function` 与 `const … =>`，从**目标函数**反向传递求闭包，只搬闭包内的东西；
  调试期先把静默 catch 换成打印，否则「段恒空」这个症状指向不了任何具体原因。

- 对比一条**看起来像**排除项、实际不是的：`jieqi` 的 `[X3D盘]` 曾被我判为 3D 渲染而搁置，
  读码后发现上游 astro3d 页签走的是 `buildAstroSnapshotContent(one, flds, {headerless:true})`
  —— 与 `[X星盘]` 逐字同一份文本。**「名字里有 3D」不等于不可 headless**，一律以 builder 实际取数为准。

### v0.25.0 段级回填（上游 v50，216 → 141 段）— 四条会反复咬人的坑

- **🔴 上游前端源不在 `vendor/runtime-source`。** 该树的 `astrostudyui/src/` 只镜像了 `utils/`（供 aiExport
  对账），**只有 1 个文件**；`components/` 与 `divination/` 整个不在。在那棵树上 grep 段头会得到「上游根本
  没有这段」的**错误结论**。真身在 `Horosa-Public/Horosa-Web/astrostudyui/src`（12712 文件）。
  判据：`find <树>/astrostudyui/src -type f | wc -l` —— 个位数就是镜像树，别在上面找 builder。

- **🔴 桩比真实响应「更简单」＝ 把 bug 盖住。** 本轮抓到两处同一形态，都是线上真坏、离线恒绿：
  1. `/astroextra/harmonic` 真实响应把整个 chart-wrap 放在 `chart` 键下（比通用段构建器预期深一层），
     调波盘 14 段全是占位存根；FakeClient 的桩**根本没有 chart 字段**。
  2. `/predict/*` 的交叉相位是 `chart.aspects` **数组**；FakeClient 在**顶层**塞了本命形状的 aspects，
     于是推运族 5 键的 `[相位]` 段在真机上只有三个空子标题、零条相位，而测试还断言着 `"标准相位" in text`
     —— 等于在断言 bug 的产物。
  **规则**：写桩时以真实响应的**嵌套层级与容器类型**为准，宁可繁琐；桩每简化一层，就等于给自己关掉一层守卫。
  改完桩顺手加反向断言（如 `assert "标准相位" not in text`）锁住方向。

- **段在 `sections` 里 ≠ 真的产出了。** 导出层会给 preset 里没产出的段注入占位存根
  （「本次本地计算结果未返回「X」细项…」）。看产出要看 **`section_titles_detected`**；`sections` 含存根。
  「某段同时出现在 `sections` 和 `missing_selected_sections`」是这个信号的典型形态。

- **工具自带 `snapshot_text` 会短路自动渲染器。** 统一出口是 `if not snapshot_text:` 才调
  `_auto_snapshot_text_for_tool`。工具里回填一份「只含自家几段」的文本，会把整套通用盘面段挡在门外
  （调波盘就是这么丢了 12 段）。要合并通用段 + 技法段，就**不要**在 `_run_*_tool` 里回填。

- **`revendor_core_js.py` 的落点默认值会丢嵌套层级。** 旧实现取 `Path(rel).parent.name`，于是
  `divination/data/x.js` 落到 `vendor/data/`，与既有的 `vendor/divination/data/` 形成**同名重复树**，
  且 relocate 还会把 import 指回旧树 —— 同一模块两份、改一份不生效。已改为「vendor 里存在完整相对父
  路径就用它」。

- **从上游 React 文件抽函数，记得扫模块级 const。** 抽 `buildJinKouSnapshotText` 时漏了 `MD_DASH`，
  运行期才炸。做法：抽完用正则把上游所有 `^const X =` 与新文件里已定义的符号做差集，一次补齐。

- **往 registry 插条目时，正则必须锚定字典起点。** `"liureng":` 在 PRESET 与 OPTIONAL 两个字典里都有，
  `re.search` 命中第一个 → optional 条目被插进了 PRESET（重复键被后一条覆盖，行为无害但语义错、且
  下次读代码会误判）。先 `t.index("AI_EXPORT_OPTIONAL_SECTIONS = {")` 再在其后找锚点。

- **上游把一族盘按「哪个页面出的」拆成独立导出键**（`aiExport.js` 的 `ASTRO_LIKE_EXPORT_KEYS`：
  astrochart_like / hellenastro / dwadasamsa / harmonic / draconic / relocation / locastro）。段单同构，
  所以 `locastro`(=本仓 acg) 这种「看起来是独立技法」的键，导出其实是 **astrochart 全套盘段 + 尾部地图段**。
  判据：技法在该常量里 → 它的 builder 应复用通用盘面渲染器，而不是自建几段线表。

### v0.14.0 sync lessons (古典占星 [古典] + [古典格局] 补到 chart 家族 — vendor 源 = Horosa-Public, 72 工具不变)

- **新增任何到 chart 服务的 `_call_remote(endpoint)` 必须把 endpoint 加进 `_PYTHON_CHART_ENDPOINTS`。** `[古典格局]` 经
  `_attach_classical_analysis` 调 `/astroextra/analysis`；最初漏登记该 endpoint → `use_chart_server=False` 落到 **Java** 通路，
  读 `_java_runtime_ready`（仍 False）→ 二次探针 + 二次 `start_local_services`，直接打挂 `test_service_*runtime*`（`started==1`/`probe_calls==1`）。
  判据：chart 服务族（`/chart`·`/predict/*`·`/astroextra/*`·`/*/pan`…）一律进该 set，才会复用 `_chart_runtime_ready` 缓存、首调后不再探针。
- **段补到「既有工具」≠ 新工具**：古典两段挂在 chart 家族导出上，工具数仍 72。版本仍要全量 bump（pyproject/uv.lock/__init__/
  package.json+lock/server.json/README×2/JSON 例），但 badge/句子/全景标题的 **72 不动**；测试数 260→263 要同步。
- **`_attach_*` 增补走「gated + try/except graceful + 顶层 stash」**：`_CLASSICAL_ANALYSIS_TOOLS={chart,chart13,hellen_chart}`
  控制 `[古典格局]` 只挂本命三盘；india/mundane 走 `_build_astro_snapshot_text` 自带 `[古典]`（来自 `/chart` objects），但不挂
  `[古典格局]`——preset 必须**逐工具对齐**（astrochart/astrochart_like 双段；indiachart/mundane 仅 `[古典]`），否则挂不上的段进 preset 会成「死条目」。
- **离线 vs live 覆盖分层**：`[古典]` 的 Melothesia 段离线即出（FakeClient objects 带 `sign`），但**逐曜古典状态/围攻/围绕**需富集
  per-object 字段（outOfBounds/phase/joy/mansion…），仅 live 出；故离线测试断言 stub 驱动的 `[古典格局]` + Melothesia，富集 `[古典]`
  交 live 测试 + export-fixture（用真 live 快照 `astrochart_classical_live_snapshot.txt` 锁解析契约）。FakeClient 要加 `/astroextra/analysis` 桩。


### v0.13.0 sync lessons (4 未同步 AI 技法 + 太乙/八字 段口径 — vendor 源 = Horosa-Public, 68→72)

- **审计前先查自家「明确排除项」+ 过 headless-readiness 闸。** 第三轮把 `fengshui` 误当可补缺口——它是 canvas +
  户型图上传 + 交互点位驱动（`new FengShuiEngine(canvas,…)`，无 birth/time 输入），无法 headless；仓内 SKILL.md/README×2
  早有「明确排除·风水未完成 headless 化」政策。教训：上游有 engine 文件 ≠ 可进公开 skill；每个候选先 grep 排除政策，
  再确认其 `buildXxxSnapshotText` 是纯 `chart/data→text`（无 canvas/DOM/上传/点击依赖）。
- **AI-export 技法的权威清单 = `aiExport.js` 的 `EXPORT_TECHNIQUES` + `EXPORT_PRESET_SECTIONS`**（不是组件目录）。本轮
  4 个缺口（triplicityrulers/keypoints/lunationphase/extrareturns）都在该表里却无 skill 工具。`utils/triplicityRulers.js`
  用 `AstroConst.SignsProp` → shim 必须补该表（v0.11 闭合教训复发点：load 过、真盘崩）。
- **请求型 builder（如 extrareturns 逐体拉 `/astroextra/planetreturn`）不能塞进 headless JS**（JS 层不发 HTTP）——
  后端调用放 Python（`_run_*_tool` 循环 `_call_remote`），JS 只做纯格式化；或直接 Python 拼段（extrareturns 即此）。
- **后端「整段 sections」可能被旧 vendor 层 strip 掉**：太乙的 13 段解读 kintaiyi 后端本就返回（top-level `sections`），
  但 `tools/taiyi.js` 历史上 `sections: undefined` 整体丢弃。排查法：抓 `js_client.run` 实际收到的 `ken_response`，
  grep `sections`/段名，再决定是「透传」还是「重 vendor builder」。条件出现的段：**同时进 preset（present 不 unknown）
  + optional（absent 不 missing）**——单进 optional 不够（parser 的 unknown 只减 preset，见 `exports/parser.py:130`）。
- **CI 起不了后端**：GitHub Linux runner 无 Linux 运行时（Linux PR 已拒；运行时 macOS/Windows-only + gitignore）。
  别造「boot runtime」假 job；CI 网 = offline FakeClient 契约 + export-fixture 契约，全套 live 在本机 vendored 实例发布前跑。
- **`04caa37`（Windows v0.12.0）带来的两道闸**：`release-completeness.yml`（发布后查 latest 是否双平台——darwin-only latest
  过渡期必红=预期信号）+ `verify_builder_parity.py`（mac/win builder 锁步 + REQUIRED_ENTRIES 对称）。新技法是 horosa-core-js
  内的 JS+Python（随包带入，不改 payload/REQUIRED_ENTRIES），故 parity 不受影响——但发布前要跑 `verify_builder_parity.py`。


### v0.12.0 sync lessons (主限法 v12 核5收敛 + 排盘修正批 + faRelatedPeople — vendor 源 = Horosa-Public)

- **vendor 源 = 开源仓 Horosa-Public**（`HOROSA_SOURCE_ROOT=/Users/horacedong/Desktop/Horosa-Public`；
  sync 脚本默认根是 Desktop、其下无 Horosa-Web，必须显式传）。Public 的 PD 引擎天然就是核5+legacy 白名单
  （perchart 白名单 ↔ `_PD_METHOD_REGISTRY` 6 键锁步），v12 核 kernel 完整（Vertex/多圈/每盘钥匙/显示窗）。
  同步后核法：vendored astropy 与 Horosa-Public 逐文件 `diff -q` 全同 + `PD_SYNC_REV==pd_method_sync_v12`
  + golden v266 在位。**同步与核对一律以 Horosa-Public 为唯一来源。**
- **`/predict/pd` 的 params 回显是原样输入，不是引擎解析值**：送 `placidus` 回显仍 `placidus`，但引擎内已
  回退 core_alchabitius（行集与显式 core 逐位一致，live 测试钉死）。skill 快照对白名单外键如实标注
  「未核验，引擎回退 Alcabitius 半弧法」，不静默换标签。
- **live 验证必须打 skill 自己 vendored 的引擎实例，不是 :8899/:9999 上恰好在跑的东西**——默认端口上
  常驻的服务不保证与 vendored 引擎同版本（陈旧实例会掩盖白名单/钥匙问题）。本轮把 tests 的
  gate+`make_service` 从写死 `:8899/:9999` 改为尊重 `HOROSA_CHART_SERVER_ROOT`/`HOROSA_SERVER_ROOT`
  （此前 env 覆盖静默无效，一次「带覆盖的全绿」实际测的是默认端口上的旧实例）。
  起 vendored 实例：chart 要 `PYTHONPATH=<vendor>/Horosa-Web/astropy`
  + `HOROSA_CHART_PORT`（脚本只自动解析 flatlib，不解析自身包根）；java 用 vendored
  `runtime/mac/java/bin/java -jar runtime/mac/bundle/astrostudyboot.jar --server.port=… --astrosrv=…`
  （root 500 = 正常无路由）。
- **防陈旧进程门已制度化为 live 测试**：chart 心跳 `GET /` 回显 `pdSyncRev`，断言 ==`pd_method_sync_v12`
  再信任结果（v12 注记坑#6：陈旧引擎把未知时间钥匙静默按 Ptolemy 算）。**钥匙分叉探针别用 Kündig**（静态
  标度 1.0 与 Ptolemy 同日期）——用每盘真算的 Kepler（live：321/321 行日期分叉）。
- **pd 表行是列表不是字典**：`[arc, prom, sig, type, date]`；3000 年多圈 = 同 (prom,sig) 弧 +360°×n
  （live 实测 168 组复发对，max arc 2995.5°）。宿命点行 id `N_Vertex_0` 仅 In-Zodiaco；skill 侧
  `ASTRO_TEXT_MAP["Vertex"]="宿命点"`（主短两表都要）。
- **faRelatedPeople 透传**：vendored `computeProtect` 吃 `pan.faRelatedPeople=[{name, yearGan}]`（显式数组
  为准，缺省不出行）。skill 在 Python 侧把 `{name, birth}` 经 `/nongli/time` 的 `yearJieqi`（立春界）归一化
  为年干（1991-02-03 → 庚，立春前归前一年，live 钉死），JS 保持上游 verbatim 只 stamp。上游的
  `birthToYearGan` 依赖 lunar-javascript，skill 不引这个依赖——走自家 nongli 后端同口径。
- **排盘修正批随重同步自动带入**（日返/月返种子、合盘/组合盘归一化、恒星跨0°、围攻 orb、均时差等，上游
  pytest 60 + golden byte-perfect 已验）；skill 结构断言型测试全绿，无需改动。
- 界 (term) promissor row id = `T_<ruler>_<sign-name>`（非经度）；上游 dial 的 `_PD_CHART_METHOD_HSYS`
  只在 skill 暴露 dial 时才相关（目前只暴露 PD 表）。


> ↓ 附录：v0.12.0 当轮的同步清单原文（自述「留作历史核对参照」）。

## 主限法 v12 批(upstream 星阙 v2.6.6 — ✅ 已于 v0.12.0 同步完成,vendor 源=Horosa-Public)

> 下面 7 条是当时的同步清单,留作历史核对参照;实际执行结论与坑见上方「v0.12.0 sync lessons」节
> (全部逐条核到:核5白名单/22钥匙/Vertex/3000多圈/golden v266/pdSyncRev 心跳门/钥匙分叉 live 测试)。

1. **显示窗口径换了**:行星对显示窗 = 「弧 pre-norm 原值 |Δ| < 107.5」单参数判据(`_passesCoreDisplayWindow`),旧三分支 λ 窗 + EPS 已删。世俗(In-Mundo)核旧窗符号错配修复 → **In-Mundo 行星对行显著增多是修复非回归**,skill 的 golden/selfcheck 若按旧行数断言会假红。
2. **宿命点(Vertex)应星新增**(仅黄道向运;世俗核不出):行 id `N_Vertex_0`,闭式直算。snapshot/导出段如列方向行,新应星会出现。
3. **时间钥匙修真**:Simmonite/Kepler/Brahe 由常数改**每盘真算**(本命太阳日速);新增 `Kündig`(静态 1.0)与 `SymbolicSolarArc`(动态,逐弧查星历)。同步时 `STATIC_TIME_KEY_SCALES` 集合与 `PER_CHART_TIME_KEY_FALLBACK` 一起带。
4. **pdYears 上限 360→3000**:`perchart.py` 夹断 3000;`perpredict._extendCorePdRecurrences` 统一旧「180+ 互补行」与多圈复发(基弧+360m)。≤360 逐位等价旧式;skill 侧若有 pdYears 校验/文档要同步上限。
5. **golden 改名** `golden_alcabitius_ptolemy_v266.ndjson.gz`(v253 删),manifest 同步;`PD_SYNC_REV = pd_method_sync_v12`(helper.py/webchartsrv.py + 前端 + Java 4 控制器——skill 只 vendor Python 也要带 rev,响应 params.pdSyncRev 会回显)。
6. **坑·陈旧 Python 进程静默吞新钥匙**:长驻 webchartsrv 不重启时,新动态钥匙会**静默按 Ptolemy 算日期**(未知 key 不报错走默认 scale)。skill 打包运行时若复用旧进程同坑;验证法 = 直接 POST 对比 Ptolemy vs 新键日期是否分叉。
7. 同步自检建议:vendored 引擎跑 `pdYears=3000` 应出多圈行(同 (prom,sig) 链上 arc+360k、日期逐圈递增);`pdYears=100` 行集与 v2.6.5 vendor 比对 — 仅显示窗/宿命点差异属预期。


### v0.11.0 sync lessons (Xingque v2.6.3→v2.6.5 parity + 2 v0.10.0 deferrals — no new tools, still 68)

- **Sidereal ayanāṃśa is pure Python passthrough.** `perchart.py` reads `data.get('siderealAyanamsa')` and emits
  `chart.siderealAyanamsa` + `chart.nakshatras` (sidereal only). `BirthInput` has `extra="allow"` so the param already
  flows via `model_dump(exclude_none=True)`; declaring it is for discoverability + guidance only. **Real bug fixed:** the
  skill's `ASTRO_MSG["Sidereal"]` was hardcoded `恒星黄道，岁差:Lahiri` → mislabelled Raman/Fagan charts; de-hardcode it,
  read the ayanāṃśa from `chart.siderealAyanamsa` (西占) / `chart.siderealModeKey`+`ayanamsaValue` (印占, **different field
  names**), and put the real name on its own line. `chart.zodiacal` is a *localized string* ("恒星黄道"), not an int — don't
  gate on `== 1`. Nakshatras read from `response.chart.nakshatras`, NOT top-level.
- **India is Python (`/india/chart` in `_PYTHON_CHART_ENDPOINTS`), reads `indiaHsys`/`indiaAyanamsa`** (aliases hsys/ayanamsa/
  siderealMode). Golden = ayanāṃśa *differences* are stable astronomical constants (Raman−Lahiri Sun lon = +1.446°,
  Lahiri−Fagan = +0.88°) — robust without pinning fragile absolute lon.
- **JS vendor dependency-closure is the whole game (六壬毕法 D + 政余格局 E).** Both are pure module-level closures
  (zero `this.`/React) — extract by transitive-call analysis, but **CONST refs are caught separately from function refs**
  (missing `JiaZiList`/`ERFAN_SU_TO_BRANCH` → silent `ReferenceError` swallowed by try/catch → null result). The 六壬 三传
  engine is a plain `ChuangChart` class — vendor it with draw-only imports (GraphHelper/helper/LRShenJiangDoc) replaced by
  no-op stubs (only `genCuangs` runs). `SZConst.js` reads `localStorage` at *module load* → **hardcode a no-op shim** (node
  25's experimental global `localStorage` throws without `--localstorage-file`; don't probe `globalThis.localStorage`).
  `AstroText.js` keys its maps on `AstroConst.*` constants → extend the `constants/AstroConst.js` shim with every planet/
  node/point the closure looks up, or the lookups return `undefined`-keyed.
- **政余格局 honest limitation:** 七政神煞 (官/福/疾/天贵/玉贵/岁驾) come from a *separate* kinastro qizheng engine
  (`fetchKinastroQizheng`) the western-`/chart` guolao path never calls → `guolaoGods` absent → god-dependent patterns
  can't fire (chart-object ones do). The 神煞 section was already empty for the same reason. `能接多少接多少、跑不通如实标出`.
- **紫微 P0–P2 data is all in the jar response** (re-synced): top-level `patterns` (命中格局: name/category/duanyi/broken),
  `houses[].starsOthersGood/Bad/Small` (杂曜), `direction`/`smallDirection` (大限/小限). Just surface it in
  `_build_ziwei_snapshot_text`. 来因宫 + rich 流曜运限 are frontend-only (ZiWeiHelper) → not in the response, honestly skipped.
- **Offline contract (`test_all_callable_techniques...`) forbids bare `无` sections.** Any new JS-fed or jar-fed section
  needs a `FakeJsClient`/`FakeClient` handler returning real content (guolao_moira; `/ziwei/{birth,rules}` patterns), AND
  the section in both preset + `AI_EXPORT_OPTIONAL_SECTIONS` (conditional → no false `missing`).


### v0.10.0 sync lessons (Xingque v2.5.4/v2.6.x parity — no new tools, still 68)

- **PD full-house params flow through `PerChart`, not the web layer.** `webpredictsrv.py:pd()` is just
  `PerChart(data) → getPredict() → getPrimaryDirection()`; `perchart.py` reads `pdMethod/pdDirect/pdAntiscia/...`
  from the request, `perpredict.py` reads them via `getattr(self.perchart, ...)`. So A only needed schema fields
  + a vendor re-sync (`input_normalized` is `model_dump(exclude_none=True)` → unset params fall back to the
  upstream defaults: direct/converse on, antiscia/terms off). Don't grep the web srv for the param — grep `perchart.py`.
- **JS re-vendor dependency closure is the #1 trap.** The jinkou 解读层 crashed on `LRConst.TaiXuanNum` undefined —
  the curated `vendor/liureng/LRConst.js` (131-line, AstroConst-free) was missing 6 new constants
  (`TaiXuanNum/ZiCong/ZiHai/ZiPo/ZiSangHe/ZiXing`). Do NOT re-vendor the full upstream `LRConst.js` (it `import`s
  `AstroConst` from a path that doesn't exist headless); append only the new pure constants. Always do a
  `node -e "import('...')"` load-check AND a real-data run after vendoring, not just a load-check.
- **qimen 法奇门 = surgical add, not a 2086-line re-vendor.** `DunJiaFaDoc.js` is pure; `DunJiaFaCalc.js` imports
  only `DunJiaFaDoc`. The existing `DunJiaCalc.js` works, so just add `import { buildFaQimenAnalysis }` + the +8-section
  block before its `return`. `buildFaQimenAnalysis(pan)` is compatible with the skill's kinqimen pan (live-verified);
  all 8 法 headers emit when `fa` is truthy. Preset = the builder's actual sections (14: skill has no `九宫与宫内星体`).
- **liureng `毕法/占断向导` — DONE in v0.11.0** (was deferred in v0.10.0): the ~40-field layout context IS assemblable
  headless. `buildLiuRengReferenceContext` + `buildLiuRengLayout`/`buildKeData`/`buildSanChuanData` are pure
  module-level functions (20-fn / ~570-LOC closure, zero `this.`/React) — extracted verbatim into
  `vendor/liureng/liurengRefContext.js`. The 三传 engine is `ChuangChart.genCuangs()` (plain class; vendored with
  the 3 draw-only imports — GraphHelper/helper/LRShenJiangDoc — replaced by no-op stubs since only genCuangs runs).
  Deps: full `LRConst.js` (re-vendored 21→52 exports superset; has GanJiZi/GuiRengs/GanZiWuXing/getGuiZi), `LRPanStyle.js`,
  a 12-LOC `constants/AstroConst.js` shim (LIST_SIGNS + Sun/Moon). Wired in `tools/liureng.js`: `[毕法（已命中）]` always
  (refCtx success), `[占断向导]` only when `payload.zhanCategory` ∈ {hunyin/taichan/jibing/caiyun/…}. Both in the liureng
  preset + `AI_EXPORT_OPTIONAL_SECTIONS["liureng"]` (conditional → no false missing). **坑**: missing a module-level const
  in the closure (JiaZiList/ERFAN_SU_TO_BRANCH) → silent `ReferenceError` caught by try/catch → refCtx null → 毕法 absent;
  and a missing `ChuangChart` import → 三传 null → only non-三传 毕法 fire. Always trace refCtx + sanChuan on a real 盘.
- **guolao `政余格局` — DONE in v0.11.0** (was deferred): `buildLocalMoiraPatterns` (Moira DSL) + its 34-fn/~600-LOC
  pure closure (zero `this.`) extracted verbatim into `vendor/guolao/guolaoMoira.js`; runs via `js_client.run("guolao_moira")`
  in `_run_guolao_chart_tool`, appended as the `[政余格局]` section. Deps chained out: `vendor/suzhan/SZConst.js` (with a
  hardcoded `localStorage` no-op shim — node 25's experimental global localStorage throws without a flag), the real
  `constants/AstroText.js` (name maps) + an extended `constants/AstroConst.js` shim (planets/nodes/points the maps key on),
  and inline `GUOLAO_LIFE_MODE_*` + `getStored*` default stubs (headless has no UI prefs → ASC 命度 / su28=2).
  **Honest limitation** (`能接多少接多少、跑不通如实标出`): the 七政神煞 (官/福/疾/天贵/玉贵/岁驾) come from a *separate*
  kinastro qizheng engine (`fetchKinastroQizheng`), which the skill's western-`/chart`-only guolao path never fetches — so
  `guolaoGods` is absent and the **god-dependent patterns** (八杀朝天/日月拱官/官福失垣/…) can't fire. The **chart-object
  patterns** (孛犯太阳/罗犯太阳/金水相涵/日月失所/命坐两歧/孤月独明) DO fire (golden: 1985-03-21 → 金水相涵 + 孛犯太阳).
  The 神煞 section was already empty for the same reason (pre-existing). Closing it = wiring the qizhengkin gods in (future).
- **Live services make the @requires_* tests run.** When `:8899` (chart/ken) and `:9999` (Java) are up, pytest runs
  the integration tests for real (233 passed, 0 skipped). That validated B/C/A against real Python compute and the
  qimen/jinkou 解读层 against the real ken backend — the best signal available. CI (services down) skips them.


### v0.9.2 hardening lessons (audit pass — tests/robustness/fidelity/runtime)

- **`f"{response.get('snapshot')}"` produces the literal string `"None"` when the key is absent** (a truthy
  6-char string → a garbage "None" export that silently passed). Always guard `raw = response.get("snapshot")`
  then `f"{raw}".strip() if raw else ""`. This bit `_run_shenshu_tool`; the same `f"{...or ''}"` idiom is safe
  only because of the explicit `or ''`.
- **Don't silently fall back in compute runners.** `_split_birth_ymdhm` used to substitute `2025-01-01` on an
  unparseable date (wrong-moment chart, no error). Now it raises `tool.shenshu_bad_date`; `_run_shenshu_tool`
  raises `transport.shenshu_snapshot_unavailable` on a no-snapshot (old-backend) response; horary/election/
  progextra log + attach `snapshot_error` instead of a bare `except: pass`.
- **persiandirected dates differ from 星阙 by ≤1 day** (~40% of rows). Root cause: 星阙's moment
  `add(N,'days')` TRUNCATES the fractional day (JS `Date.setDate` floors), AND `arc % 360` has JS↔Python
  float noise that rounds to the same 2-dp age but flips a day at the integer boundary. Matching the truncation
  made it worse (float noise dominates). The ages/aspects/targets are byte-identical; the ≤1-day 应期 date is
  astrologically negligible and documented (`docs/v091-fidelity-spotcheck.md`). To verify a hand-port's
  fidelity, extract the 星阙 builder's pure functions + run them on the same fixture and diff — but mind
  `moment` (CJS, `createRequire`) and the React-class lines.
- **Runtime-slim reality: `pyarrow`(119M)/`pandas`(40M) are astropy deps, NOT streamlit-only.** kintaiyi needs
  `import astropy.units` → astropy needs pyarrow+pandas. Stripping them breaks taiyi. streamlit is imported
  pervasively across `kinastro/astro/*` (st.markdown ×1817 …) so it can't be stripped without a fragile stub.
  **Only `plotly`(40M) is safely strippable** (streamlit-only + lazily imported for `st.plotly_chart`, never hit
  headless). Verified `import streamlit` + cetian snapshot + `astropy.units` all OK without it.
- **Export presets are a SUPERSET; some sections are 星阙-UI-only or conditional.** `AI_EXPORT_OPTIONAL_SECTIONS`
  (registry) lists sections a preset names but the headless snapshot may not emit (检索/查询 panels, mode/topic
  conditional). The parser excludes them from `missing_selected_sections` so real exports read clean; strict
  techniques keep an empty optional set. Also: a preset copied from `aiExport.js` can MISS sections the backend
  actually emits (qizhengkin 今制宿度/古制宿度) → they surface as `unknown_detected_sections`; add them to the preset.


> ↓ v0.9.0 暂缓、v0.9.1 全部补齐的神数家族整合记录原文。

### 神数 family (14) — ALL SHIPPED (v0.9.1)

The kentang registry (`astropy/websrv/kentang/registry.py`) mounts **14 神数 engines on the chart
service (:8899)**: wangji / wuzhao / taixuan / jingjue / shenyishu (5 standalone engines) + shaozi /
tieban / fendjing / beiji / nanji / chunzi / xianqin / cetian / qizhengkin (9 sharing the **`kinastro`**
engine). Both groups are now integrated — the wiring is identical (backend `snapshot` → export), the
only difference is which engine dir is vendored:

- **Tier 1 — 5 standalone engines: SHIPPED.** `vendor/{kinwangji,kinwuzhao,taixuanshifa,jingjue,shenyishu}`
  (~5.2 MB total). Each `web{key}srv.py` builds a `response["snapshot"]` whose `[小节]` headers already
  match 星阙's `aiExport.js` preset, so the skill needs **no snapshot builder** — just POST `/{key}/pan`
  and export `response.snapshot`. Wiring: one shared `_run_shenshu_tool(payload, key)` + `_split_birth_ymdhm`
  (神数 take split year/month/day/hour/minute, not date/time strings) + a `ShenShuInput` (FlexibleModel:
  date + optional time + 晚子时 switches + an `options` passthrough for engine-specific overrides like
  wuzhao mode/number). **CRITICAL routing gotcha:** kentang mounts only reach :8899 if the endpoint is in
  `_PYTHON_CHART_ENDPOINTS` — otherwise `_call_remote` sends them to the Java :9999 server and they 500.
  Add `/wangji/pan` … `/shenyishu/pan` there (alongside `/qimen/pan`).
- **Tier 2 — 9 kinastro-* engines: SHIPPED (v0.9.1).** All 9 share the `kinastro` engine
  (`from astro.{shaozi,fendjing,chunzi,cetian_ziwei,…} import …`). Same shared `_run_shenshu_tool`;
  cetian/qizhengkin/xianqin also forward `gender` + place. **The v0.9.0 "deferred" call was WRONG:** the
  live :8899 returned `basic`-only data only because the user's *running* app was an older build — the
  current source's `web{key}srv.py` all set `pan["snapshot"] = build_snapshot(pan)`, and the engine
  imports + computes cleanly under the bundled Python. Vendor the **engine only**: `vendor/kinastro`
  with `--exclude=tools` (the 26 MB `tools/cities` geocoding DB is not needed for ganzhi 神数) +
  `--exclude={ui,frontend,docs,wiki,examples,tests,styles,scripts,.streamlit,…}` → ~31 MB (`astro/` is
  32 MB raw). `ensure_kinastro_path()` puts `vendor/kinastro` on `sys.path` so `import astro.shaozi`
  resolves; `streamlit` is a kinastro import but it's already in the bundled site-packages (the
  `@cache_data`-without-runtime warning is harmless). **Validate offline by invoking each
  `web{key}srv` class's `pan()` with a mocked `cherrypy.request` from a NEUTRAL CWD** (NOT `cd $HW`, or
  the local `Horosa-Web/astropy/__init__.py` shadows PyPI astropy → `No module named astropy.units`).
- **The 9 kinastro-* have NO live `@requires_chart` test** — the user's running app is an older build
  without their snapshots, so a live test would red. They're covered by the offline FakeClient contract
  suite (the fake synthesizes a preset-covering snapshot) + the in-process srv validation.
- **Some kinastro presets have conditional sections** (tieban/chunzi/cetian emit fewer than the full
  `aiExport.js` preset for a given input). The FakeClient emits the FULL preset so the offline contract
  is clean; real exports may show a few `missing_selected_sections` — that's expected (like election).
- **NATIVELY CONFIRMED on Windows (v0.9.1 release build).** Booting the bundled `win32-x64` chart service
  and POSTing to each `/{key}/pan`, **all 14 神数 returned `ResultCode 0` with a real `Result.snapshot`** —
  the 5 standalone (`source` `kinwangji`/`kinwuzhao`/`taixuanshifa`/`jingjue`/`shenyishu`) and all 9
  kinastro-* (`source: kinastro`, snapshots 540–6000 chars). So the engine-only kinastro trim (above)
  is sufficient and the "deferred" worry is fully retired on Windows too — not just structurally.
- **Native-probe gotcha: the snapshot is nested at `Result.snapshot`, not top-level.** The raw chart-service
  response is `{ResultCode, Result:{source, engine, snapshot, raw, …}}` (the skill's `_call_remote` unwraps
  `Result` for `_run_shenshu_tool`, which then reads `response["snapshot"]`). If you probe `/{key}/pan` with
  raw HTTP and read a top-level `snapshot`/`engine`, you'll wrongly see "empty" and think the engine failed.
  Read `Result.snapshot` / `Result.source`.


> ↓ ≈skill v0.8.x 时代：上游星阙 v2.5.0 批的整合记录原文。

### v2.5.0 推运 (7) + 卜卦/择日 — JS-vendor vs Python-port decision tree

星阙 v2.5.0 added 7 推运 (jaynesprog / vedicprog / planetaryarc / planetaryages / balbillus /
yearsystem129 / persiandirected) plus the **horary (卜卦)** and **election (择日)** divination engines.
The integration rule that emerged:

- **Backend-computed (has a `/predict/*` or `/astroextra/*` endpoint) → Python.** jaynesprog
  (`/astroextra/jaynesprog`), vedicprog (`/astroextra/progressions` zodiacal=1), planetaryarc
  (`/predict/planetaryarc`) — `_call_remote` + a Python snapshot builder. Add the endpoint to
  `_PYTHON_CHART_ENDPOINTS`. **These 3 endpoints did NOT exist in the v2.4.0 `vendor/runtime-source`** —
  they need the v2.5.0 re-sync (`sync_vendored_runtime_sources.sh`) before the bundled runtime can serve
  them; the LIVE 星阙 app (:8899) already has them, which is why the live `@requires_chart` tests pass
  pre-rebuild.
- **Frontend, reads pre-computed chart data → Python.** planetaryages (reads `chart.objects` +
  `params.birth`), yearsystem129 (reads `predictives.yearsystem129`, which `/chart` only emits when cast
  with `predictive` truthy — `getPredictivesObj`), persiandirected (pure 1°/年 arithmetic off
  `chart.objects`/`houses`/`birth`). Ported to Python reusing `_astro_msg` / `_aspect_label` /
  `_split_degree`.
- **Frontend, algorithm-heavy / risky to re-derive → vendor the JS verbatim.** balbillus (247-line
  129年旺距削减 with recursive sub-periods). Vendored `astrostudyui/src/utils/balbillus.js` →
  `horosa-core-js/src/vendor/astroextra/balbillus.js`, redirecting its `AstroConst`/`AstroText` imports to
  a tiny **`progConst.js` stub** (7 classical planet ids + `LIST_SIGNS` + `AstroTxtMsg` — avoids vendoring
  the 1128-line AstroConst). Needs `moment` (added to `horosa-core-js/package.json`). Dispatched through a
  new **`progextra` JS tool** (`technique` → builder map) called from `_run_progextra_js_tool`.
- **卜卦/择日 = vendor the whole `divination/` tree.** It's ~3200 lines of **pure logic with only relative
  imports** (no React/antd). Copy the entire `astrostudyui/src/divination/` into
  `horosa-core-js/src/vendor/divination/` (this also re-syncs the v0.8.0 lifespan subset to upstream), then
  **add `.js` to every relative import** (Node ESM needs explicit extensions; a one-shot regex over
  `from '…'` does it — 22 files). Two thin JS tools `horary.js` / `election.js` call
  `runHorary(chartResp, category)`+`buildHorarySnapshot` / `runElection(chartResp, topicId)`+
  `buildElectionSnapshot`. Python `_run_horary_tool` / `_run_election_tool` cast a **traditional**
  (`tradition:1`, `predictive:0`) chart at the question/candidate moment, pass the `/chart` response as
  `payload.chart`, and read back the JS-resolved `category`/`topicId` (the engine falls back unknown →
  `general`/`marriage`).

Gotchas that bit us here:
- **`buildFacts(result)` wants the full `/chart` response** (it reads `result.chart.objects`, `result.objectMap`,
  `result.aspects`, …), so pass the whole response object as `chart`, not just `chart.objects`.
- **election preset has dead/conditional sections.** 星阙's `aiExport.js` election preset lists `应期`
  (its builder **never** emits it) and `用事专属` (only when the topic rule-pack produced items). We mirror the
  preset for fidelity, but `_assert_clean_export` (which requires `missing_selected_sections == []`) is too
  strict for election — assert `missing ⊆ {用事专属, 应期}` instead. horary's 9 sections are all reliably
  emitted (描述 is technically conditional but present for normal charts), so horary keeps strict clean-export.
- **Router: 卜卦 also contains the generic 卦.** The 梅花易数/卦 branch (`["梅易","卦","gua"]`) must exclude
  horary phrasing (`卜卦/horary/起卦/占问`) or `卜卦问婚姻` mis-routes to `gua_desc`.
- **Offline test fakes must cover the new JS tools.** `FakeJsClient.run` needs `progextra` (balbillus snapshot),
  `horary`, `election` handlers, and `FakeClient` `/chart` needs `predictives.yearsystem129`, or the offline
  export-contract suite falls back to `generated_template` and fails.


> ↓ ≈skill v0.7.x 时代：上游星阙 v2.4.0 批的整合记录原文。

### v2.4.0 西占 (Western) techniques — agepoint / distributions / mundane / natal extras

These are 星阙 v2.4.0 additions; integrating them required **re-vendoring `vendor/runtime-source` from
星阙 v2.4.0** (the bundled chart service then carries `/predict/agepoint`, `/predict/dist`,
`/astroextra/greatconj`, and the enriched `/chart`). Patterns:

- **`agepoint` / `distributions` are simple backend predict tools** (like harmonic): `_call_remote`
  (`/predict/agepoint` → `{agepoint:{points:[…]}}`; `/predict/dist` → `{dist:[…]}`) + a Python snapshot
  builder (`_build_agepoint_snapshot_text` / `_build_distributions_snapshot_text`, ports of 星阙's frontend
  builders). Both endpoints are in `_PYTHON_CHART_ENDPOINTS`. Each has a single-section export contract.
- **本命增补 (12分度 / 主宰星链 / 寿命格局) is JS-computed, Python-formatted.** 星阙 computes these in the
  frontend (`astroAiSnapshot.js`), reading the chart object. The skill vendored the needed 星阙
  `divination/` engine subtree into `horosa-core-js/src/vendor/divination/` (chartFacts + the Ptolemy
  **lifespan** engine + `data/{signs,dignities,planets,houseMeanings}` + `engine/utils` — a clean 8-file
  closure, no npm deps) and wrote `src/vendor/astroextra/natalExtras.js` + the `astroextra` JS tool that
  return **structured** data (dodeca pairs / dispositor chains / the runLifespan res). `service.py`'s
  `_attach_natal_extras` (only for `chart` + `mundane`) calls it via `js_client`, and
  `_build_natal_extra_sections` formats the 3 sections with `_astro_msg` — so the JS does compute, Python
  does the Chinese formatting (no `AstroText`/`whichTerm` vendored). They are inserted into the astrochart
  snapshot before `可能性`; the `astrochart` preset gained the 3 sections.
- **`mundane` (世俗入宫盘) is a composite** local tool: `/jieqi/year` (seedOnly, `jieqis:[term]`) → find
  the `jieqi24` entry whose `jieqi==term` → its `time` is the precise ingress moment → `/chart` at that
  instant → `_attach_natal_extras('mundane', …)` → prepend a `[世俗入宫]` head to the astrochart snapshot.
  Input is **year + 入宫节气 + place** (date/time are derived, not user input).
- **Re-vendoring `vendor/runtime-source` (the skill's copy) is allowed and READ-ONLY on 星阙.**
  `sync_vendored_runtime_sources.sh` with `HOROSA_SOURCE_ROOT=<星阙 tree>` does it. After it, re-apply the
  graceful-kentang-mount patch to the vendor's `astropy/websrv/kentang/registry.py` if you run the chart
  service directly from `vendor/` (the **build** scripts patch the staged copy automatically; the raw
  vendor hard-fails on `mount_kentang_services` because the kentang registry lists engines like `kinwangji`
  that the skill doesn't vendor).


### 发布完整性编年（v0.10.0–v0.18.0）— 原文

> ↓ 原为 AGENTS.md 打包 gotcha 大 bullet；现行「三失效模式 + 检测 + 修复」法则已蒸馏进 `AGENTS.md` §7，这里保存完整案例史。

- **A new release published as `latest` is repeatedly missing its Windows half — ALWAYS check the release
  manifest first. The CI guard now catches this automatically.** The mac side has shipped this incomplete on
  **every minor since v0.10.0**: v0.10.0 had **no** `runtime-manifest.json` at all (`releases/latest/download/runtime-manifest.json`
  404 → `install` broke on BOTH platforms); v0.11.0 through **v0.16.0** shipped a **darwin-only** manifest +
  no win32 zip (mac installs, **Windows** install finds no `win32-x64` entry / 404s the zip). **Auto-caught
  since v0.13.0**: `release-completeness.yml` fires on the release event and fails, exactly as designed —
  so rely on that red check instead of noticing by hand (it flagged v0.14.0/v0.15.0/v0.16.0 too).
  **v0.16.1 (2026-07-01) broke the streak: the first mac-shipped COMPLETE dual-platform `latest`.** The mac
  side repacked the Windows-built v0.16.0 zip with a corrected embedded manifest (version 0.16.1 +
  `export_registry_version` 7 — confirmed by range-reading the published zip; sizes differed from the
  v0.16.0 archives by only ~50 bytes) and the guard went green on the release event with zero Windows-side
  action. A repack like this is only valid when the release diff has **no payload-affecting changes**
  (horosa-core-js source, vendored engines, wheels, launchers — skill-layer Python/docs are fine); when a
  suspiciously same-size win zip appears on a new release, verify the embedded manifest (version +
  `export_registry_version`) and that diff condition before trusting it.
  **v0.17.0 / v0.18.0 introduced a THIRD, stealthier mode — "pin-forward":** the new release's manifest
  lists `win32-x64` but points it at the *previous* version's win zip (v0.17.0/v0.18.0 both pinned
  `.../download/v0.16.1/horosa-runtime-win32-x64-v0.16.1.zip`). **The guard stays GREEN and `install` does
  NOT break** — both platforms are present, the URL resolves 200, and the sha matches — but Windows users
  silently get a runtime **N versions stale** (missing every feature since the pinned version). The guard
  can't catch this (it only checks presence + resolvability, not version match). **`sync_windows_release.py
  --check` IS the reliable detector**: it looks for the version-specific `horosa-runtime-win32-x64-vX.Y.Z.zip`
  asset, which is absent under pin-forward, so it reports `[GAP]` even while the guard is green. Treat a
  `--check` GAP as authoritative regardless of guard colour; the remediation (build + upload the real win
  zip, re-pointing the manifest) is identical. **Freshness caveat for these jumps:** v0.17.0 was an "引擎全面
  升级" that added real chart-service endpoints (`/location/acg` 占星地图, `/astroextra/relative`) and new
  bundled data (`astrostudyui/dist-file/astrodata/astrodata-aa.sqlite.gz` for 名人库, ~50 MB) — a pin-forward
  jump can span such changes, so re-populate `vendor/runtime-source` from the **current** Windows workspace
  (check astropy / dist-file mtimes are newer than the target release) and native-verify the new endpoints
  return real data before shipping. The Windows runtime is built off-repo on a Windows box, so a mac-only
  release publish leaves it out. **First diagnostic when
  "check sync" / a new version appears:** `gh release view vX.Y.Z --json assets` (expect darwin tar.gz +
  win32 zip + runtime-manifest.json + SHA256SUMS.txt) and confirm
  `releases/latest/download/runtime-manifest.json` has **both** `darwin-arm64` and `win32-x64` platforms.
  If the win half is missing: build it, regenerate the **dual-platform** manifest + SHA256SUMS, and upload —
  the release is usually already `latest`, so the upload alone (no flip) restores Windows `install`.
  **Automated since v0.12.0:** `.github/workflows/release-completeness.yml` (schedule + dispatch + release
  events) fails if the published `latest` lacks either platform / an archive 404s, and
  `scripts/verify_builder_parity.py` (CI `test` job) fails if the two builders or the verifier contract
  drift. If either alarms, the fix is this same build-the-Windows-half flow.
  **One-command remediation (v0.14.0):** on the Windows build box, `python scripts/sync_windows_release.py`
  detects whether the current `latest` is missing its Windows half and (when run with `--upload`) runs the
  whole build → download-darwin → dual-platform manifest + SHA256SUMS → `verify_runtime_release.py` →
  upload pipeline. Safe by default (no `--upload` = build + verify only, no irreversible action), idempotent
  (no-op + exit 0 when already in sync), and it gates the upload behind `verify_runtime_release.py`. It
  reads the version from `pyproject.toml`, so `git pull` to the release commit first. This is the canonical
  way to clear a `release-completeness` red — prefer it over doing the steps by hand. **Battle-tested
  end-to-end on v0.16.0 (2026-07-01):** re-populate `vendor/runtime-source` from the Windows workspace,
  build, native-verify (chart `:8899` compute — the new `/geomancy/reading` + `/astroextra/*` mundane
  endpoints returned real data, confirming the source tree was fresh), then the sync tool packaged +
  uploaded and the guard went green + a public `install --force` matched the sha.


> ↓ 上游星阙 v2.2.1 的 SSE 陷阱原文；不影响 skill 计算路径，仅供替用户排障星阙桌面端时参考。

### Bonus upstream trap (v2.2.1) — AI-analysis SSE Issue #8

The skill talks to its own ken backend, not 星阙's `chat/stream` SSE proxy, so this does NOT affect
skill compute paths. It's documented here because if a user ever debugs 星阙 desktop and asks "why did
my Ollama chat just go silent and then die", the answer is upstream:

- **Catch block in `AIAnalysisProxyService.chatStream` used to swallow the first-cause exception**:
  `sendEvent` inside catch rethrew `ClientAbortException` as `RuntimeException`, killing the
  `ai-analysis-chat-stream` thread, and the original Ollama error went only into a
  `safeErrorMessage(...)` SSE frame that never reached the client. Upstream fix: `QueueLog.error(...)`
  first, then nested try around `sendEvent` + `completeWithError`.
- **The three `stream***` methods used to send zero bytes until the first delta**: with a local Ollama
  TTFT of 10–60 s, browsers/Chromium/middleware time the SSE socket out as idle. Upstream fix: each
  stream method is now wrapped in `withHeartbeat`, which emits `: keep-alive` every 15 s.

If a skill user reports flaky 星阙 AI streaming, point them at upstream v2.2.1 and the
`release_preflight.sh` sentinel `[7]` that gates both lines (`QueueLog.error(AppLoggers.ErrorLogger` and
`keep-alive`) in `AIAnalysisProxyService.java`.
