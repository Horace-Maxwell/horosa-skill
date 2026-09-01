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
| v0.34.0 (2026-09) | 上游 v3.10.0 择日十技法同步 | 闭包按停止节点算；抽壳要机械化；解析器盲区造假债务；兜底分类=待确认 |
| v0.33.1 (2026-09) | issue #15 家族全清剿 | presence 级断言对值失明；跨边界不改键；静默降级会上移；schema 描述不是愿望清单 |
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

### v0.34.0 / 2026-09-01 — 同步上游 v3.10.0 择日十技法：抽壳、解析器盲区、与「假债务」

上游一次发了 182 文件 / +25k 行的择日大版本（8 个新技法键）。同步过程本身踩出四条。

- 🔴 **依赖闭包要按「已 vendored 即停止节点」算，否则数字会吓人。** 天真闭包把整个 React 壳
  （amap 地图 / D3 / xq-ui / request.js）都拉进来，六壬那支报 69 个新文件；把已 vendored 的文件
  当停止节点重算后是 5 个。**先算对再决策** —— 按 69 那个数字很容易误判成「这支做不了」。

- 🔴 **上游把纯逻辑和 React 放同一个文件时，剥壳要机械化，不要手抄。** `LiuRengMain.js` 6436 行，
  1–4553 纯逻辑、4554 起 `class … extends Component`，20 个纯 export 全在前半。仓里此前手抄过
  其中三个函数进 `liurengRefContext.js` —— 而上游的 `buildSanChuanData` 早已多出第 4 个参数
  `castOverride`，手抄那份还是三参。**手抄件会静默落后于上游**。改为 `truncate_before` 按正则
  锚点整头 vendored（锚点而非行号：行号随上游编辑漂移，锚点找不到会报错而不是悄悄剪错）。

- 🔴 **截断必须跑在孤儿 import 清理之前。** 孤儿判据是「符号在正文里还用不用」，而截断正是改变
  正文的那一步。放后面的话，React 尾部专用的 16 个 import 在判定时还“在用”，于是全部留下 ——
  模块引用了 vendor 树里根本不存在的路径，加载即炸，**而 re-vendor 那一步看起来是成功的**。
  同族：`_IMPORT_STMT` 不吃行尾注释（`import {...} from '…'; // [观象P1]`）时，stub 报 not found、
  import 原样留下，症状一模一样。

- 🔴 **解析器盲区会造出「假债务」，比漏检更坏。** 上游同一个文件里 spread 有两种写法：
  `...AI_EXPORT_PRESET_SECTIONS.qimen`（v3.7.1）与 `...(AI_EXPORT_PRESET_SECTIONS.bazi || [])`
  （v3.10.0）。只认第一种时，八个新键的基底段全被 export-section 守卫报成「skill 多出来的段」
  （bazizeri +11、sanshizeri +50…）。**这种噪声会诱使人去 `--update-baseline`**，把一条本该常绿的
  检查一次性腌成永久噪声。判据：报出来的债务，要先问「它和某个已入账的基底债务是不是同一笔」——
  本轮七键是解析器的错，第八键（qizhengzeri 缺 3 段）才是 `guolao` 既有债务的真继承。

- 🔴 **execution 标错会让整个 runner 被绕过。** 给 `qizhengzeri`/`indiazeri` 在 registry 上挂了
  endpoint + `execution="remote"`，通用远端路径抢先接管 → 自写的按月分段与快照合成一次都没跑，
  而工具**返回 ok=true**、只是 hit_count 恒 None。tianxing 一直是 `execution="local"` + runner 自己
  打端点，照抄它即可。同一形状：`export_snapshot` 恒 None 是因为忘了把新键加进
  `AI_EXPORT_TECHNIQUES`（有 preset 却不在这张表 → parse 抛 Unknown technique，而调用方 `except
  ValueError: return None` 把它吞成 None）。

- 🔴 **算源分类落到兜底 = 不诚实的披露。** provenance 生成器按显式名单分类，新工具落到兜底
  `local_data`（「不起盘：读本地离线库」）—— 而它们确实铸盘，只是盘不是搜索算的。正确类是
  `composite`（两条腿算权不同，`compute_sources` 逐项写明）。**兜底类别永远要当成「待人工确认」，
  不是「默认正确」。**

### v0.33.1 / 2026-09-01 — issue #15 不是一个 bug，是一个**家族**：边界改键 + presence 级绿灯

外部贡献者 [zeno17z](https://github.com/Horace-Maxwell/horosa-skill/pull/16) 报了一个具体错误：八字格局段
把 正财格 判成 正官格。根因是 `baziGeju.js` 写 `hour:` 而三个引擎一律读 `time` —— 时柱静默缺席，
取格/五行力量/盲派整批错，而输出照常自信。顺着这个形状全树对抗性扫描（43 个 JS tool、44 个
`js_client.run` 调用点、78 个 Input class）之后，同族活体 **4 个 P0 + 10 个 P1**，外加 36 处无错误码的
静默空返回与 15 个 schema 撒谎的死旋钮。

- 🔴 **presence 级断言对值回归结构性失明。** 「段在 `section_titles_detected` 里」≠「段里的值是对的」。
  六层防线全绿而 bug 照样出货：loadcheck 只扫 `src/vendor/` 不扫 `src/tools/`；selfcheck 对
  baziGeju 零覆盖；vendor manifest 只管引擎不管调用方；离线 fake **手编答案**（引擎从不运行）；
  live 测试 presence-only 且 `@requires_runtime` 在 CI 里 skip；golden fixture 里压根没这三个段。
  `src/tools/` 是整棵 JS 树里**唯一没有任何静态守卫**的部分 —— 而所有改键都发生在那里。
  守卫 = `verify_js_boundary_contracts.py`（死键向 + 锚定向）+ `verify_value_goldens.py`（值级金标棘轮，
  AGENTS §5 第 12 步）。接上一条 :1139 的下一阶：那条讲「桩比真实响应更简单」，这条讲「断言比真实
  结论更浅」。

- 🔴 **跨边界不改键。** 上游原样透传是唯一被证明安全的形状。本轮五例全是同一句话的反例：
  `hour`↔`time`（#15）、`minute`↔`ke`（铁板，96 局塌成 12）、`lunarMonth`/`lunarDay` 在手却不转发
  （参评，起运岁恒 1、九个大运整体平移）、`params: response` 指向 /chart 信封而非起盘时刻（果老
  moira，`isDay` 恒真 → 夜生盘拿天贵而非玉贵）、裸 `gender` 经 `Number('女')`=NaN 判男（神数正传，
  女命大定死限年错）。**判据统一为一句**：「改这个参数，结果必须变」—— 每条修复都配了这样的
  值级金标 + 负向对照（把 bug 改回去，金标必须红）。

- 🔴 **静默降级会沿调用链上移。** #15 的修复给 JS 侧加了结构化错误，而 Python 侧
  `_attach_bazi_geju` 只读 `snapshot_text` —— `data.error` 无人看，四段消失依旧零信号。
  **修一层不等于修一条链**：错误信号每上一层都要有人接。守卫 = `verify_silent_returns.py` 棘轮。

- 🔴 **selfcheck 的 harness 自己也犯同一个病。** `check()` 只 `fn()` 不看返回值 → async 断言体的失败
  变成 unhandled rejection，打印 `ok`、退出码 0、CI 全绿，断言其实根本没验。写这一条时它正好吃掉了
  我自己刚写的 canping 金标里的一处笔误。**给 harness 也要做负向对照。**

- 🔴 **schema 描述不是愿望清单。** `ElectionInput` 的注释一边引着正确出处（"上游 electionParams.js 的
  13 键"），一边列着 11 个与那 13 键**零重合**的发明名字；`HoraryInput` 的 `receptionMode`/
  `almutenScheme` 在任何引擎词表里都不存在。它们被描述、被文档化、三个版本一次都没生效 ——
  agent 照描述传参、读到自信输出，永远学不到那个旋钮被忽略了。
  修法不是一删了事：`lotsSet`/`considerationsMode` 是**真词表**里的名字，真正的病是
  `horaryJudgeOpts(school)` 只喂了四层口径链的第 1 层、`runElection(chart, topicId)` 干脆把 `opts`
  整个丢了 —— 46 + 13 个真参数结构上不可达。**接线时把白名单锚到引擎自带的词表**
  （`HORARY_PARAM_BY_KEY` / `ELECTION_PARAM_BY_KEY` / `BABYLON_SCHEMES`），不手抄会漂移的清单；
  认不出的键回执在 `data.params_ignored`，不静默吞。发明的名字整批删。
  守卫 = `verify_schema_knob_wiring.py`。

- 🔴 **新守卫也要做负向对照，否则它只是更贵的装饰。** `verify_js_boundary_contracts.py` 第一版能抓
  铁板的 `minute`，却抓不到 #15 自己的 `hour` —— 因为 #15 的字面量不在调用处，而在上一行的
  `const four = {…}`，采集器只扫内联实参。**「守卫跑绿了」和「守卫能抓到它声称防的那个 bug」是两件事**；
  后者必须用真 bug 注回去验证。同理，第一版生成器每次 regen 都会把手写豁免块冲掉，而 regen 恰恰是
  修完调用点后的常规动作 —— 等于豁免永远活不过一次修复。

- 🔴 **上游删掉的东西，下游也要跟着删。** `zuoShan` 上游已判定是「双重幽灵」（无流派声明 needs、
  快照 builder 全文不消费）并删除，skill 侧还在 schema/service/JS 三处带着它，白白打散 memo 缓存。
  同理 babylon 的 `era`/`scheme`：流派只当**标签**传，judge 层的 `dodecaVariant`/`cubitDeg` 一个没传，
  于是无论选哪档十二分恒 B，而 [起盘信息] 行照常打出所选档名。

- 🔴 **fork 首次贡献者的 PR，workflow 需维护者手动批准**（`action_required`），否则 CI 永远 pending，
  看起来像「贡献者的代码跑不过」。另：本仓 Dependency graph 未开启，`dependency-review` 在**每个** PR
  上都红，与 PR 内容无关 —— 判断 CI 时要先分清「这条红是不是每个 PR 都红」。

### v0.33.0+ / 2026-08-29 — codex TOML 裸插值：Windows 路径的反斜杠打穿整个 config（main 连红两次）

- **症状**：v0.33.0 发布 commit 起 main 上 `CI` 连红两次——`windows-smoke` 里
  `tests/test_client_config.py` 三条全炸：`tomllib.TOMLDecodeError: Unescaped '\' in a string`
  + 两条 `--write` exit 1；Linux `test` job 与 CodeQL 恒绿。不只是测试红：Windows 用户跑
  `client config --format codex` 拿到的 `toml_stdio` 就是**非法 TOML**，`--write` 也因 tomlkit
  解析失败而拒绝写入——新功能在 Windows 上整个不可用。
- **根因**：`cli.py` 的 codex 片段里 `command = \"{stdio_command[0]}\"` 是**裸 f-string 插值**进
  TOML 基本字符串；Windows 的 `C:\Users\…` 反斜杠在 TOML 里是转义引导符 → 整文件不可解析。
  同块的 `args`/`cwd` 都走了 `json.dumps`（JSON 转义 ⊂ TOML 基本字符串转义，天然兼容），
  唯独 `command` 手写引号。mac/Linux 路径无反斜杠 → 维护机与 Linux CI 恒绿，windows-smoke
  是唯一能红的地方（v0.25.0「维护机形状 ≠ CI 形状”教训的路径分隔符变体）。
- **修复**：`command` 改走 `json.dumps`，与 args/cwd 同惯用法（一行 + 注释）。全仓 sweep 确认
  无兄弟病灶（其余 client 格式全是 dict→`json.dumps`）。真机抽验：本机 `C:\Users\…` 路径下
  `toml_stdio`/`toml_http` 均可被 tomllib round-trip。
- **守卫**：既有 `tests/test_client_config.py`（v0.33.0 III-6 新增）就是逮住它的那把——CI 红得
  完全正确，说明"五格式零测试"补的这层真在工作；无需新守卫，修代码即可。
- **法则（蒸馏进 AGENTS §9）**：凡把路径/用户值序列化进配置文本（TOML/JSON/YAML/deep-link），
  一律走该格式的序列化器（`json.dumps` / tomlkit / `quote`），**禁裸 f-string 插值**——
  「本地能解析」不算证据，Windows 反斜杠路径才是判据。

### v0.33.0 / 2026-08 — 功能大扩容（93→97）+ 成熟度升级：四个现场踩坑 + 一批排除判定

本轮双主线（收割未接入端点 + Codex 标尺工程成熟度）落地：tianxing explainAt、qizhengelection、
india_rectify、planet_cycles、jieqi_birth、persiandirected 指定日期盘、extrareturns 年表、acg 落点/
事件、cetian 判词库、wangji 心易三法、geomancy 十六卦目录、古典参数 30 键 typed 化、/healthz 探针、
SQLite 分类恢复、env 旗标 warn-and-ignore、澄清闸策略即数据、记忆点用记账/prune、hermetic 评测、
codex --write 拆雷、.agents/skills 镜像。现场教训四条：

1. 🔴 **`TOOL_EXPORT_TECHNIQUE_MAP` 漏登记 = bench 静默不覆盖。** 症状：批 I 四个新工具功能全绿
   （契约 missing/unknown 空、live 实产），bench 生成 case 却只 +1。根因：README 承诺的「新增技法
   自动获得用例」由 `generate_tool_cases()` 兑现，它遍历的是 `TOOL_EXPORT_TECHNIQUE_MAP`——而新
   runner 都自己调 `_augment_export_payload`，不经过这张表也一切正常，于是没有任何信号提示入表。
   守卫：`test_every_business_tool_is_in_export_technique_map`（工具 − 表 = 显式非业务四件）；
   §5 布线清单 +第 12 步。
2. **exports registry 同字典重复键第二次踩**（v13 首踩 cetian/astrochart_like，本轮 extrareturns 条件
   段被后写键静默覆盖）。两个新事实：①旧守卫只扫**顶层 `ast.Assign`**，本可抓到却因我用 `-k` 分批跑
   测试而没被触发——守卫只在全量套件里兜底，**每批提交前必须全量跑 offline**（本轮全批照做后再未漏）；
   ②守卫本体已扩 `ast.walk` 全量（嵌套 dict/AnnAssign 位置同防）。另附带：用 regex 从「提及目标字典名
   的注释」处起段做文本编辑，会把条目插进后面**任意**同名键的字典——锚定真赋值行，改完必跑
   `test_export_tools` 全量。
3. **`_unwrap_result` 连剥小写 `result` 键。** `/wangji/xinyi` 返回 `{method, result:{卦面}, sections}`，
   经 `_call_remote` 后 `sections` 整个消失——unwrap 循环对 `Result`/`result` 都剥（至多 4 层）。新端点
   接入时凡响应含这两个键名，先想清剥壳后拿到的是什么；runner 按剥后形状消费（离线桩发全信封，
   两侧形状一致）。
4. **测试期望值不等于真值。** selfcheck 金标里我手写的 `08未51`（处女镜像地支）与 `摩羯`（2020 木土
   大合相落宫）都是错的，渲染器是对的（处女↔巳；合相在宝瓶 0°29′）——金标的期望值必须从权威来源
   （上游表/天文事实）核过再写，测试红先怀疑期望值。

**排除判定入册**（主线 I 收割时逐端点核）：`/predict/pd3d`、`/chart3d/state`、`/planetarium/*` ——
3D/实景渲染场景数据（three.js 场景态/贴图坐标），无文本语义，UI-only 排除，与 fengshui 同性质；
`/jdn/*`、`/calc/*` —— 儒略日/角度换算器，价值低，defer（不计缺口，将来要做随手可加）。
`/qizheng/moira` 排除维持（qizhengelection 的升殿失垣列因此如实不产，见工具 guidance）。

### v0.32.0 玄史知识库接入 —— runtime 里躺了 66MB 只读库，skill 层零调用

- **上游能力不只在导出面。** `/xuanshi/*` 26 个只读端点（7900+ 玄学事件 / 27000+ 史书天象 / 人物图 /
  编辑层）随 runtime 分发已久（editorial.sqlite 66MB 就在 astropy/astrostudy/xuanshi/data/、服务挂载表
  里一直有 /xuanshi），但它不在 aiExport 导出面上，所以段级/镜像守卫**永远不会报它**——「上游有什么
  我们没接」的普查必须包含 websrv 端点清单 vs `_PYTHON_CHART_ENDPOINTS` 的差集，不能只看导出键。
- **jsonpickle 直吐的端点可能返回裸数组**（/xuanshi/search、timeline 下钻等）。`_call_remote` 的
  dict 硬约束会把它判成 `transport.invalid_result_shape`——放行必须**按端点前缀圈死**（仅 /xuanshi/*
  包成 {items: […]}），其余端点维持硬约束，形状漂移要炸出来。
- **端点登记守卫只认 `_call_remote("字面量")`。** 分发表形态（action → 端点全路径存表、调用处传变量）
  的字面量在表里不在调用点——守卫要加一条对应的采集规则（本轮给 test_endpoint_registry 加了
  `/xuanshi/[a-z_]+` 字面量扫描），否则 26 个端点全被判成死项。
- 新工具布线在本仓已是**九件套**：schema + ToolDefinition + runner/分派 + 端点白名单 + 导出注册
  （skill-only 键还要进 mirror 白名单）+ guidance（含 PREFLIGHT_EXEMPT，检索类工具无出生盘闸）+
  router 关键词 + technique_provenance 条目 + 样例载荷/FakeClient 桩。bench case 与 server
  instructions 计数由锁步守卫自动拦，文档计数由 docs-sync 拦（本轮它逐处点名了 banner.svg /
  CLAUDE.md / AGENTS.md / 徽章 / 自检行 / 导出技法数 / bench 数——共 12 处，一处不落）。

### v0.31.0 重同步 v3.9.5 —— 版本常量锁步被证伪 + 三种 require 形态 + caller 旧于依赖

- **🔴 `AI_EXPORT_SETTINGS_VERSION` 锁步不可信。** 上游 v3.9.5 给 `horary` 导出段 19 → 28（+9 段），
  **版本常量原地不动仍是 56**。后果：`verify_export_contract_mirror.py`（只比版本号 + key 集合，且只读
  vendored 镜像）全绿穿透；`verify_export_section_baseline.py` 默认 `--source vendored` 也绿——那是拿
  自己的旧镜像对账，同义反复。**权威判据只有两个**：`verify_upstream_sync.py --require-upstream`
  （sentinel sha256）与段级棘轮的 `--source upstream --require-upstream` 形态（`preflight_release.py`
  在跑的就是它）。日常手跑判断同步健康，必须用后一形态，裸跑默认参数会在这类失败上恒绿。
- **上游 require 有三种形态，逐形态踩齐才算修完**：①语句形 `const {X} = require('…')`（v0.25 已处理）
  ②**表达式形** `require('./x').prop`（ZiWeiHelper 的 `require('./ziweiOptions').ZWEngineOptions.kuiYue`，
  语句正则抓不到，ESM 运行到即 ReferenceError；改写=hoist 成命名空间 import + 表达式处换别名。该规则
  顺带抓出 dignities.js / hellenisticData.js 两处同病）③同符号 require **多次**（topicModule 的
  DIR_BY_ELEMENT ×2）→ hoist 队列内也要去重，否则 `Identifier already declared`。另一坑同族：hoist 的
  **插入点必须按完整语句匹配**——按单行匹配时多行 `import {…\n…} from` 块的首行也命中，「最后一条
  import 之后」会落进块中间把它劈成两截（lifespanEngine 实测 SyntaxError）。
- **「caller 旧于 vendored 依赖」是手工抽取件的专属漂移形态。** 本轮 `ZiWeiHelper.js`/`ziweiOptions.js`
  机械重灌后已是新版（effLayerSihuaGan / xiaoxianClockwise / 各流派开关全在），但手工抽取的 caller
  （zwLuckItems 4 函数 / ziweiExtras.formatLuckLayerLines / JinKouSnapshot.buildJinKouSnapshotText）
  还是旧文本——能力在场但不可达，其中 `birthYearOf` 缺 `ganzhiYearBase` 是 v3.9.4 修的**真值错误**
  （流年归属可能错年）。规矩：每轮重灌 vendor 树后，把 `contracts/vendor_manifest.json` 里 mode 为
  bespoke/curated 的条目**逐一与上游现函数对文本**，机械 `--from-manifest` 不覆盖它们。
- **上游后端的「param error」可能是本仓载荷的锅**：`/chart` 的 params 回显块无守卫读 `data['hsys']`
  （上游前端恒发 hsys，从他们视角没毛病）。`HoraryInput` v0.24 typed 化时把 hsys 覆写成 None 默认
  （「随流派档」），归一化剥掉 None → 缺键 KeyError。此前一直误判为「vendored 实例拒绝载荷、改前即
  如此」并绕道 JS 层直验——**其实是真 bug，线上任何 python chart 后端上 horary 全挂**。修=调用侧补
  PerChart 默认 0。教训：typed 化把父类有默认值的字段改成 None 默认时，要查每个直调后端的工具是否
  依赖那个默认值。
- **saturnExalt20 已删档**（上游 2026-08-18 拍板：degree 位全仓零消费者=真死开关，
  `push_request_exalt_variants` 签名 2→1 参）。本仓 typed 字段同步删除；`nodeExaltation` 保留。

### v0.28.0 / 2026-08-17 — v3.9.2/v3.9.3 同步轮的四条 + 首个「AI 层」批次的三条

**同步侧（缺口小了，说明守卫在做功；坑换了形态）。**

1. **上游在你同步时还在动。** v3.9.2 同步做到一半，上游又发 v3.9.3 + 两个 commit——`--write-state`
   记录点必须追 HEAD 而不是停在「我开工时的版本」，否则 provenance 一写完就是陈旧的。
2. **skill-only 键的 lost 检查会自锁。** 上游把 `generic` 从 preset 键降为运行时兜底后，check 1b 的
   lost 方向红 → `--write-state` 拒写 → recorded 永含旧键 → 永远红。修：lost 集减去 mirror 守卫的
   DIVERGENCE_WHITELIST（skill-only 键从来不镜像上游，撤它不构成 retirement），降为 notice。
3. **「聚合导出子源标签」是新段形态。** calendar 的 农历/老黄历/日子馆 三段是整行【X】来源分界、
   非内容段（上游 [E-6]）——必须进 preset（否则用户自定义段时标签行被过滤删除），但 body 为空是
   正常形态。别按内容段的「空即缺」直觉处理。
4. **评测器必须对任意信封形状稳健。** bench 评测器踩 `{"technique": None}` 的 `None.get` 连崩两轮
   ——失败信封的 data 可以带 export_snapshot=None。评测器崩 = 整轮 bench 白跑，比单 case 红严重
   得多；一律 `(x or {})` 边界。

**AI 层批次（B1/B2/B3——「会算」之上的第一层）。**

5. **HelpDoc 是被埋没的知识资产。** 上游 30+ 份方法论手册（每个设置的取值与差别、流派分歧、
   算法口径）只活在桌面端帮助页里——正是 AI 解读最缺的口径知识。收割成知识包（21 域/177 条，
   逐条带 组件文件+tab+上游版本 出处），`knowledge_read` 通用分支零代码扩域。
   生成器幂等纪律：generated_at 取上游 commit 时间，不取 now()。
6. **忠实性校验可以完全确定性。** 导出契约是机读真值 → 「AI 是否编造盘面」不需要 LLM 判官：
   槽位断言（四柱/落座/身宫/三传）逐值比对，裸值断言对快照词元全集查存在性。词元切分要取
   CJK 连续串的**全部 2-4 字子串**——贪婪切词会把「食神制杀」吃掉「食神」。
7. **合参的护栏在模板里，不在提示里。** `horosa_hecan` 产模板不产终稿：结论槽必须留白
   （预填即伪造）、证据是指针不是全文（响应不背 N 份快照）、「分歧必须披露不许平均」写进
   synthesis_contract.instructions 而不是靠 SKILL.md 的自觉。

### v0.27.0+ / 2026-08-13 — 发布后制度化批次：口头注意点不收进机器，下一轮还会原样再犯

**背景。** v0.27.0 发布过程里暴露了五件「说过、但没有任何机制拦」的事，当场逐件收进机器。
横切法则：**对话里的注意点 = 还没发生的复发**——能写成断言/脚本的，当场写；只能写成文档的，
问一句「哪个 runner 会读到它」。

1. **live 曾打到默认端口上的另一棵树。** 审计中途从默认 `:8899` 的服务读过段名，事后靠 lsof
   才发现那个实例根本不是本仓的树（来源、版本全不可知），数据当场弃用重推。旧规则「live 必须打
   vendored 实例」只是 §8 的文字。守卫：① live 门禁改为**只认显式 env**——
   `HOROSA_CHART_SERVER_ROOT`/`HOROSA_SERVER_ROOT` 未设一律 skip，且短路在探针左侧，
   **连 TCP 都不碰默认端口**；② 起法收进 `scripts/start_vendored_instance.sh`
   （三段 PYTHONPATH + 内嵌解释器 + failed=0 判据 + 不达标自动回收），停法
   `stop_vendored_instance.sh` 只按 pidfile PID。回归：`test_guard_wiring.py` 断言短路形状与两纪律。
2. **git 身份没配，发布 commit 作者串成 `…@主机名.local`。** git 只在 commit 那一刻才猜，全程无
   提示，GitHub 不归属任何账号，要 amend 才能救。守卫：`preflight_release.py::identity_problems`
   （纯函数，直接测），name/email 未配或 email 以 `.local` 结尾 → 阻断。
3. **main 滞留只有文档没有闸。** v0.27.0 写进了 §7 文字；本批把它变成 preflight 的
   `git_gate_failures()`：fetch 后 `HEAD..origin/main` 非空 → 阻断（离线 fetch 失败只警告）。
   **该闸首跑当天就抓到构建机补 Windows 半边时推的一个 commit** —— 不是假想敌。
4. **SBOM 生成器一直在仓里，发布时却漏传了。** `generate_sbom.py` 不在任何发布脚本的调用链上，
   v0.27.0 首发的资产列表少了它，靠人对比 v0.26.1 才发现（「守卫挂在什么都不跑的地方」的资产版）。
   守卫：mac 半边发布收进 `scripts/publish_darwin_release.sh`（SBOM 是显式步骤；无 `--publish`
   不上传）；`release-completeness.yml` 新增 SBOM 资产断言。发布步骤从此只允许以脚本形态存在。
5. **算源生成器躺在 scratchpad（会随会话蒸发）。** 契约可再生 ⇒ 生成器必须入仓：
   `scripts/gen_technique_provenance.py`（仓内相对路径，输出与在册契约逐字节幂等）。
   §5 布线清单补第 11 步「算源声明」。
6. **附带小坑：`json.dumps` 重写 package-lock 会把非 ASCII 转义成 `\uXXXX`**，下次 `npm install`
   按 npm 规范写回真 UTF-8，凭空造一个与版本无关的噪音 diff。规则（§7）：lock 只许字符串替换
   两处版本串，禁整文件 json 往返。

### v0.27.0 / 2026-08-13 — 目录 mtime 判源树新旧会误判（Windows 侧补半）

- **症状**：v0.27.0（上游 v3.9.1 全量同步，92 工具）以 **darwin-only** 发布，守卫自发布起连红三次。
  Windows 侧补半时按当时 AGENTS 的规则「核 astropy / dist-file mtime 新于目标版」判源树新鲜度——
  workspace 的 `astropy/` 顶层 mtime 停在 **07-03**，比 08-13 的目标版旧一个月，按该规则应判「源树陈旧、
  不能构建」。
- **根因**：目录 mtime 只在**直接子项增删**时更新，嵌套深处的文件更新不冒泡到顶层目录。该 astropy 树
  实际已是上游 v3.9.1（`vendor/kin_year_domain.py`、`astropy/astrostudy/geomancy/data/ifa_odu.json` 俱在，
  `electionscan`/`chart12`/`ephemeris`/`draconic` 四个新端点都 grep 得到）。**规则本身是错的**，
  照做会白白拒掉一次可行的构建、或反过来给陈旧树发绿灯（mtime 可被无关操作 touch 新）。
- **守卫/现行规则**：AGENTS §7 改为**按内容判**三条判据（本版新增的 `require_path`/`REQUIRED_ENTRIES`
  目标文件是否存在 → 新端点名是否 grep 得到 `astropy/websrv` → 构建后 native-verify 这些端点是否回真数据），
  明确「不看目录 mtime」。机器守卫侧本已覆盖大半：builder 的 `require_path` 拦缺文件、
  `verify_runtime_release.py` 的 `REQUIRED_ENTRIES` 拦缺 payload 项（本版新增
  `kin_year_domain.py` + `ifa_odu.json` 两项即由它把关）；端点级新鲜度无法静态断言，由 native-verify 兜底。
- **本轮验证留痕**：BC −500 与 2400 年 qimen 均 `rc=0`（缺 `kin_year_domain.py` 会 500）；
  geomancy 响应体从旧版 ~86KB 涨到 **210KB**（`ifa_odu.json` 生效，v3.5.1 地占大改版）；
  `/astroextra/ephemeris`、`/astroextra/draconic` 回真数据；两个启动器带 UTF-8 BOM 通过新 zip 级 BOM 闸。
- 注：协议第 3 件（CHANGELOG）仍不可执行——树内无 `CHANGELOG.md`（同前条）。

### v0.27.0 / 2026-08-13 — 落后上游 4 个 release 而四把守卫全绿：盲区在「根级文件」和「单向键差」

**症状。** 例行「还有什么没同步」审计，结果不是零星缺口：本仓 vendored 树停在上游 `f8275b3`(v3.7.3)，
而上游 HEAD 是 `44a1c9b`(v3.9.1)，中间 381 文件 / +220,597 行；导出契约上游已 v55、本仓镜像基线写 50；
多了一个**整技法** `lingqi`（灵棋经）和 **56 个新段**。CI 全绿，四把守卫也全绿。

**根因（三个互相独立的盲区，任何一个单独存在都足以让这次同步继续隐形）。**

1. 🔴 **`verify_upstream_sync` check 2b 静默丢掉所有「上游新增的根级文件」。**
   `vendored_tops = {n.split("/",1)[0] for n in vendored_files}` 对根级文件 `foo.py` 求出的 top 就是
   文件名自己，于是上游新增的根级文件永远匹配不上任何已 vendor 的顶层目录 → 整类丢弃；配套的
   「新增顶层目录」检查又要求 `"/" in n`，两头都漏。实测让 **6 个引擎模块 / 5,512 行**
   （`cetian_yiyu{,_data,_texts}.py`、`wuzhao_{classics,duanci,leizhan}.py`）对**所有**守卫隐形。
   这正是 check 2b 当初要堵的那一类失效（v0.26.0 的 `kintaiyi/jieqi.py`），只是高了一个目录层级——
   **堵漏时要问「同样的错还能在别的层级上犯一次吗」**。
2. **`verify_export_contract_mirror` 是单向的。** 它只断言 `skill_keys ⊆ upstream_keys`，所以只能抓
   改名/删除，**结构上抓不到新增技法**——哪怕 vendored 树是全新的，`lingqi` 也永远不会让它变红。
3. **两条跨树闸在 CI 上是零断言。** `ci.yml` 调它们时不带 `--require-upstream` / `--source upstream`
   （因为 GitHub runner 上既没有 gitignored 的 vendored 树也没有上游 checkout）。这本身是诚实的设计，
   但意味着「PR 全绿」对跨树漂移**什么都没说**——真闸只在维护机的 `preflight_release.py` 里。

**另外三条本轮现场踩到的。**

- **`--require-upstream --write-state` 自锁**：provenance 陈旧时 check 4 先 raise，而写记录的代码块在
  raise 之后 —— 那句「re-record with --write-state」在它自己的参数组合下永远做不到。而 preflight 用的
  正是这个组合，也就是说「刚重同步到新上游」这个**最常见**的发布前状态必然卡住。
- **无上游时那句 `state current`**：它只知道「常量自上次核对以来没动过」，却印成「当前」。落后 4 个
  release 时它照样这么印。能断言什么就只说什么。
- **`SKILL_ONLY_KEYS` 写错一个键 = 一个永久盲区**：`astrochart_like` 被列为 skill-only 而上游确有该
  preset，于是它的 `占星地图` 缺失**从未被任何一版欠账计入**。
- **Python 字典重复字面量键静默吞掉前一份**：给 v13 补段时在 `AI_EXPORT_OPTIONAL_SECTIONS` 里为
  `cetian`/`astrochart_like` 各写了第二个同名键，解释器不报错，前一份 list 直接消失，症状是
  「明明加了 optional 段，missing 里还在报」。

**守卫。** ① check 2b 拆出 `missing_upstream_files()`，按每棵树的**同步口径**（`whole` 整棵 rsync /
`per-dir` 逐目录+点名根级文件）分别判缺失，根级文件不再被丢；kinastro 专属排除也从全局收窄到单树。
② mirror 守卫补 `upstream_keys − skill_keys` 反向检查 + `UPSTREAM_ONLY_LEDGER`（要跳过必须写理由）。
③ 新增 `tests/test_guard_wiring.py`：**每个 `verify_*.py` 都必须被某个 runner 调用**——它当场抓到了
本轮新写的 `verify_technique_provenance.py` 还没挂进 CI/preflight。④ staleness 在 `--write-state`
在场时降级为 notice。⑤ FAIL 输出带总数 + `--full`，截断不再掩盖规模（56 条和 16 条曾长得一模一样）。
⑥ registry 重复键守卫进 `tests/test_export_tools.py`。

### v0.27.0 / 2026-08-13 — `execution` 不是算源：技法依据卡要是照它写，会系统性说错「谁算的」

**症状。** 要给每次输出附一张「这盘怎么来的」卡片时，发现代码里唯一能机读的算源线索是
`ToolDefinition.execution`（`local`/`remote`），而 AGENTS §4 的「工具算源普查」只是**散文**。

**根因。** `execution` 说的是「runner 在哪跑」，不是「谁算的」：`qimen` 是 `execution="local"`，
整盘却由 ken 后端算（JS 只格式化）。照它写卡片，会给 3 个 ken 技法、14 个神数技法**一致地印错**。

**守卫。** `contracts/technique_provenance.json`（七分类逐工具声明）+ `verify_technique_provenance.py`：
覆盖率（新增技法不声明算源即红，补上 §5 布线清单缺的一环）× ken 一致性（声明 ken 的必须真调过
`_require_ken_pan`，反之亦然）× 算盘端点必须已登记 `_PYTHON_CHART_ENDPOINTS`。
**运行期实测优先于声明**：卡片以 `pan.source`/`compute_sources` 为准，与声明不符时标
`matches_declaration: false` —— ken 端点失败也回 HTTP 200，静默回退本地脚手架正是这个形状。

### v0.27.0 / 2026-08-13 — 一台机器的修复可以无声滞留：`main` 没有 upstream tracking

**症状。** 另一台机器把「9999 不是 no.register.app 的同义词」修复推到了 `origin/main`，本地 `main`
落后一个 commit 一周多，无人察觉。

**根因。** `git config branch.main.remote` / `.merge` 都是空的 —— 没有 upstream tracking，
`git status` 永远不显示 `behind 1`，只显示一句干净的 `## main`。

**守卫。** `git branch -u origin/main`；发布前检查加一条「`git log main..origin/main` 必须为空」。

### v0.26.1+ / 2026-08-06 — 反误诊的提示自己成了误诊源：9999 不是 no.register.app 的同义词

- **背景**：v0.26.1 为终结「HTTP 500 一句话看不出所以然」，给 `HorosaApiClient` 加了
  `_JAVA_RESULT_CODE_HINTS`，把 `200001`→参数错误、`9999`→「app 注册没读到（在 MongoDB 里）」。
  方向完全正确，**但 9999 的映射按码值硬贴**。
- **症状（Windows 构建机实测取证）**：同一台机器上，缺 `lat` 触发的上游字符串越界回的是
  `{"ResultCode": 9999, "Result": "begin 1, end 3, length 1"}`——**不是** mac 侧看到的 200001。
  于是错误消息变成「ResultCode 9999 (no.register.app) = app 注册没读到（注册信息在 MongoDB 里）」，
  一个**参数 bug 被指去查 Mongo**。这正是本仓连着两轮在清的那类误诊，只是这次躲在「反误诊工具」里。
- **根因**：`9999` 是 Java 聚合层的**通用失败码**，`no.register.app` 只是它的其中一种 `Result`。
  按码值建映射 = 把「一种成因」当成「该码的定义」。
- **fix/guard**：`9999` 必须再读 `Result` 原文——含 `no.register.app` 才给注册/Mongo 提示，否则给
  中性提示（显式否掉「9999 == 注册问题」这个等式 + 指向 `Result` 原文 + 提醒先核 lon/lat 齐全）。
  回归 `test_generic_9999_is_not_labelled_a_mongo_problem`：断言中性分支不出现 MongoDB、显式含
  「不等于」、并指向 Result 与 lat。
- **法则**：**错误码→成因的映射，凡该码可承载多种成因，必须按消息二次判别，认不出就保持中性。**
  替用户断案的诊断比没有诊断更贵——没有诊断只是不知道，错误诊断会把人送去错误的方向排查几小时。
  （同源教训：上一条「4 条 live 红被误判成无 Mongo」；两轮都栽在「把一种成因当定义」。）

### v0.26.1 / 2026-08-05 — 「守卫全绿 + 测试全绿」的 v0.26.0 里躺着 16 个 bug

v0.26.0 发布时七把守卫全绿、320 测试全过。发布**之后**做了一轮三路对抗性复审，查出 16 个真 bug，
其中 5 类会让用户直接拿到错答案。**发布前跑一遍全绿 ≠ 没 bug** —— 复审要当成发布流程的一环，
而不是出事之后才做的事。

- 🔴 **「时好时坏」几乎总是缓存，不是环境。** 五个占时工具（xiaoliuren/feigong/xiaochengtu/guice/
  zhengchuan）用 `payload.get("lat")` 取值而 schema 把 `lat` 列为可选 → 把 `lat: null` 发给要求
  lon+lat 均非空的 `/nongli/time` → `200001 param error`（表现为一句无信息量的 HTTP 500）。
  对照 qimen/taiyi 用 `payload["lat"]`（必填），从来不犯。
  **它之所以被误诊成「本机无 Mongo」整整一个版本**：Java 的农历按**年**缓存，任何一次带 lat 的请求
  都会焐热该年，此后同年无 lat 请求全部成功。决定性实验 = 同一 commit 下先对 1998 年发一次带 lat 的
  请求，两个原本红的测试立刻转绿。**诊断这类问题务必换冷年份**，否则你在测一个自己刚焐热的缓存。
  守卫 = `service.py::_require_cast_geo`；另把 Java 的 200001/9999 翻译成人能读的诊断
  （`engine/client.py::_java_result_code_hint`）——此前 `HorosaApiClient.call` 从不看 ResultCode。

- 🔴 **schema 声明了却没接线的字段，比没有更糟。** `TianxingInput` 继承 `BirthInput`，12 个古典口径
  字段是顶层带描述的（agent 照 schema 传完全正确），而 `_run_tianxing_tool` 只读 `payload["options"]`
  → 顶层写法被**静默丢弃**，用默认口径跑出不同结果、零报错。`siderealAyanamsa` 更糟：它不进请求
  （后端回落 Lahiri），却照样印在 `[起盘信息]` 里 —— **输出主动声称了一个没被使用的设置**。
  `precision` 则是纯死旋钮。判据很简单：**改这个参数，结果必须变**。实测 combustOrb 3 vs 17 现在
  给出明显不同的区间（修前完全一样）。

- 🔴 **只读 `snapshot_text` 不看 `data.ok`，会把失败伪造成一份正常导出。** tianxing.js 失败时返回
  `{data:{ok:false}, snapshot_text:''}`；Python 拿到 None → `_augment_export_payload` 回落
  `format_source: "generated_template"` → 产出一份拿 payload YAML 填出来的四段假导出，而 SKILL.md
  要求 agent **只依据 export_text 解读**。stitch 那侧的 `or []` 同理把失败变成「零命中」。
  凡是 JS 侧带 `ok` 的返回，一律走统一的检查入口（`_tianxing_js`）。

- 🔴 **`x is not None` 当守卫用 = 解析失败即放行。** `_day_span` 解析不出来就返回 None，而
  `if span is not None and span > max` 让 `'2026-08-05T00:00'` 这类形状**跳过整个上限**——JS 侧
  wallToMs 却能解析它们，于是超长窗口一路跑到超时。倒置窗口得负数，`负数 > max` 恒 False 同样溜过。
  **解析失败必须报错**。另外 tianxing 此前压根没接窗口上限（真正按段发 HTTP 的是它），5 年窗口
  = 60 次串行扫描，>66 年时 `splitByMonth` 的 800 段 guard 耗尽会**丢掉最后一段**却仍报成完整搜索。

- 🔴 **materialize 一批 regex match 再拿旧偏移切新字符串 = 毁文件。** `revendor_core_js.py` 三处犯这个：
  两个孤儿 namespace import 就能把整个模块体切没（实测 `export function f` 消失）；两条
  `export {…};` 产出 `export {export { q };` 语法错误；第 2 个及以后的孤儿具名 import 静默残留
  （实测 JinKouCalc/TaiYiCalc 里就留着两条）。**边扫边改必须每轮重新搜索**（`_rewrite_inline_requires`
  一开始就是对的，另三处照抄它即可）。同处还有 `"default" in match.group(0)` 的子串误判——
  名单里出现 `defaultRules` 就把具名导出清单翻成 `export default`，所有 `import { x }` 全崩。
  **head 要由「匹配到哪个 pattern」决定，不是子串。** vendor 树是 git 跟踪的，这些会直接进仓。

- **「几处一致」不等于「数字是真的」。** README 五处齐刷刷写 320/63，CI 实测 318/65 —— 一致性守卫
  全绿。一致性只能抓「改了一处忘了另一处」。真值那一半要能**够到源头**：现在断言
  offline + live-skipped == `pytest --collect-only` 的收集总数（静态可得，秒级）。
  同族的还有 README 宣称「Linux / macOS 单测」而仓里**零 macOS runner**，以及公开 README 从不提
  「CI 不覆盖跨树上游校验」（AGENTS 和 ci.yml 注释都诚实，只有面向用户的那份不是）。

- **测试门只探 TCP = 半死的后端会让该跳的测试跑起来然后红。** `_server_up` 只 connect，Java
  「在听但每条业务路由都 500」照样 `RUNTIME_UP=True`。且四个打 `/nongli/time`（走 Java）的测试
  标成了 `@requires_chart`。现在 Java 侧改成功能探针，且探 `/nongli/time` 而不是 `/common/time`
  —— 后者正是那条「其余全死它还绿」的路由。⚠️ 顺序要紧：先修 lat bug 再改门，否则功能探针本身
  会焐热年缓存、把 bug 盖住。

- **文档里一条起服务命令，能让人把真 bug 误判成环境问题一整轮。** `horosa-dev/SKILL.md` 的
  PYTHONPATH 少了 `Horosa-Web/vendor`（ken 与神数引擎都在那儿）且用裸 `python`（缺 9 个只装在内嵌
  解释器里的依赖）。照它起服务，taiyi/jinkou/sanshiunited/wangji/taixuan/chunzi 全挂不上，
  症状看着就是「这些技法坏了」。**判据 = 启动日志 `kentang prewarm ready (loaded=18, failed=0)`。**
  经验：**当「环境问题」开始解释越来越多的失败时，先怀疑自己的复现命令。**

### v0.26.0+ / 2026-08-05 — 守卫都对，却一条都不在 Windows 构建路径上（vendor 陈旧可静默出货）

- **症状**：v0.26.0 补 Windows 半边前例行跑守卫，`verify_export_contract_mirror.py` 报
  `tianxing`/`qimenzeri` 不在 vendored 上游键表——本机 `vendor/runtime-source` 停在 08-01，
  而 v0.26.0 的引擎树已对齐上游 v3.7.x（含**会改变既有输出**的六壬三传勘正）。
  **若照常构建**：Windows 用户拿到的引擎落后一整轮同步，且 `verify_runtime_release.py` 只查
  文件在不在、照样全绿放行。
- **根因（两层）**：① `vendor/runtime-source` 是 **gitignored 本地构建输入**——`git pull` 到发布
  commit 不会刷新它，仓库层面看不出陈旧；② 两把新鲜度守卫**只挂在 `release.yml`**，而 Windows 半边
  恰恰是唯一**不走 CI**、在本机 off-CI 构建的产物——**守卫没长在会踩的那条路上等于没有守卫**。
  连带确认上一条台账的「只加键纪律」在这里同样致命：`verify_vendor_runtime_sources.py` 的
  `AI_EXPORT_SETTINGS_VERSION == 50` 恒等**在陈旧树上照样绿**（上游加键不 bump 版本），
  唯一能判红的是 mirror 的**逐键覆盖**——所以两把必须都跑，缺一个就漏。
- **guard**：`sync_windows_release.py` 新增 `preflight_vendor_sources()`，在**调用 builder 之前**
  依次跑两把守卫，任一红即 `SystemExit` 并给出重灌指引（拒绝构建，而不是构建完再说）。
  回归 `tests/test_sync_windows_release.py`：两把都被调用 / 任一红都拒绝 / **preflight 必须早于
  builder**（顺序断言——闸开在 builder 之后等于没开）。
- **法则**：新增任何「只在 CI 跑」的守卫时，问一句**这条路径 CI 走得到吗**；Windows/离线 runtime
  这类 off-CI 产物必须在其**本机入口脚本**里复跑同一把守卫。

- 🔴 **那 4 条 live 红被误判成「本机无 Mongo」整整几个版本——实测是另一回事。**
  台账/交接口径一直说：本机 live 全套必有 4 红（`xiaoliuren` / `feigong` / `zhengchuan`×2），因为无
  Mongo 时 Java 侧一律 `no.register.app.in.sys`，「环境限制而非代码问题」。**本轮逐一实测推翻**：
  ① 经 skill 正规路径（`_call_remote`，带 app 注册归一化）打 Java **是通的**——`doctor issues: []`、
  两端点 reachable、382 条 live 用例通过，其中大量走 Java；② 这 4 条报的是
  `ResultCode 9999 / "begin 1, end 3, length 1"`（上游 `substring(1,3)` 打在长度 1 的串上），
  **与 `no.register.app.in.sys` 是两个完全不同的错**；③ 实测矩阵定位触发条件是「**日期 × 缺 `lat`**」
  的组合，不是单一因素：
  | 载荷 | 结果 |
  | --- | --- |
  | `2028-04-06` + 仅 lon | ok |
  | `2028-04-06` + lon&lat | ok |
  | `2026-05-20` + 仅 lon | **500 / begin 1, end 3, length 1** |
  | `2026-05-20` + lon&lat | ok |
  给这 4 条测试的载荷补上 `lat` 即全绿。**结论**：这不是 Mongo/环境问题，是上游对某些
  「日期+无纬度」组合的输入处理崩溃，skill 侧原样透传成不透明 HTTP 500。
  **未决**：上游真因需在有上游源码的机器上定位（本仓对上游只读）；skill 侧该「先问 lat」还是
  「转结构化错误」待定，故本轮**只纠正判据、不改代码**。
  **法则**：「已知非回归」这类豁免必须挂在**可复现的判据**上（此处 = 错误串 + 复现矩阵），
  不能挂在测试名单上——名单会把后来的真 bug 一起豁免掉。裸 HTTP 探针在本机不可用
  （无 Mongo 注册，任何形状都回 `no.register.app.in.sys`），**判据一律取 skill 正规路径的结果**。

- 🔴 **五个 stamper 可以「一致地错」——N 路互证够不到源头常量**（同轮补 Windows 半边时发现）。
  **症状**：装完新构建的 v0.26.0 runtime，内嵌 manifest 写 `export_registry_version: 11`，而
  v0.26.0 的择日提交已把 `AI_EXPORT_SETTINGS_VERSION` 11→12。**根因**：`verify_builder_parity.py`
  的 `SHARED_MANIFEST_CONSTANTS` 只做 **stamper 之间**的 N 路交叉断言——五个 stamper 全停在 11 时
  它们彼此完全一致，守卫必绿。这是 v0.16.1（mac 单边 6→7）那条教训的**镜像面**：当年怕的是「有人漏
  bump 一个」，这次是「**没人 bump 任何一个**」，同一把守卫对后者天然失明。
  **实证**：v0.22.0~v0.25.0 两数恒等（10=10、11=11×3），v0.26.0 首次分叉。
  **guard**：`ANCHORED_CONSTANTS` —— `export_registry_version` 锚定到
  `exports/registry.py::AI_EXPORT_SETTINGS_VERSION`（源码解析），五个 stamper 必须同时等于它。
  加完先跑一遍**确认它对本次真漂移判红**（五个都报 lagging），再 bump 到 12 转绿；
  `tests/test_verify_builder_parity.py` 用假 registry 常量钉死锚定生效。
  **法则**：交叉断言只证明「彼此一致」；凡有**源码里的权威常量**，守卫必须锚到它，否则一致地错=绿。
  **本次处置**：v0.26.0 的 darwin 半边已发布且 stamp 11，故 Windows 半边**照 11 出货**（同版内两平台
  一致优先——该字段无运行时消费方，只是元数据）；stamper 已改 12，v0.27.0 起两边都对。

### v0.26.0 / 2026-08-04 — 上游 v3.7.x 同步：三个**机制**缺口比内容缺口更贵

本轮真正的发现不是「少了两个技法」，而是**四把守卫全绿的情况下少了两个技法**。内容一天补完，
机制缺口不堵会以同样的形状再来一次。

- 🔴 **上游会「只加技法键、不动版本闸」——版本恒等永远测不出新技法。**
  上游 `aiExport.js:306` 把纪律写死了：「新技法键只加键、两把版本闸恒不动——老用户本无自定义走
  preset 全量」。那是针对 localStorage **迁移闸**的正确纪律，但下游拿版本号当「上游有没有变」的
  探针就此失效：`tianxing`(v3.7.0) 与 `qimenzeri`(v3.7.1) 都在 `AI_EXPORT_SETTINGS_VERSION = 50`
  不变的情况下到货。
  → 唯一可能的信号是**技法键集合差分**。`verify_upstream_sync.py` 新增 check 1b，把上游 preset 键集
  与 `contracts/upstream_provenance.json` 记录的键集相比，报「upstream gained N technique key(s): …」。
  两个方向的基线**不同**：gained 要并上「skill 已登记的键」（登记即已处理，让检查在登记后自愈），
  lost 只能对着 recorded（skill 合法持有 `acg`/`astrodata`/`wangji` 这些上游无对应的键，并进去必误报）。

- 🔴 **`_upstream_preset.py` 看不见对象字面量之外的 preset 条目 —— 20 段整键隐形。**
  上游 `AI_EXPORT_PRESET_SECTIONS.qimenzeri = [...AI_EXPORT_PRESET_SECTIONS.qimen, …]`
  写在字面量**闭合之后**（aiExport.js:735）。`_object_block` 只做花括号匹配，于是整个 `qimenzeri`
  从未进入解析结果——段级欠账棘轮一边报「0 absent keys」，一边漏着一个 20 段的技法。
  这是该 docstring 已记的两个陷阱（注释里引段名 / `...JIEQI_SETTING_PRESETS` spread）的**同族第三个**。
  → 补一趟成员赋值扫描，且必须跑在字面量+spread 之后（它的 spread 要对着已解析的 `qimen` 求值），
  token 按**源码顺序**走，spread 段与字面段才能正确交织。`tests/test_upstream_preset_parser.py` 钉死。

- 🔴 **`revendor_core_js.py` 的落地路径靠猜，会分叉出重复树。**
  它按上游父目录名推断 vendor 子目录，但本树是按技法分目录的：`utils/balbillus.js` 的真身在
  `vendor/astroextra/`。实测不带 `--vendor-subdir` 驱动全树，会造出 `vendor/utils/balbillus.js`
  与真身并存，且 relocate 还会把别的文件的 import 指回**新造的那棵**。
  → `contracts/vendor_manifest.json`：显式 upstream↔vendor 路径对 + 声明式偏离（`stub_import` /
  `import_redirect`），三种 mode（verbatim / curated / bespoke）各有可断言的判据。此后
  `--from-manifest --check` 全树 `unchanged` 就是「已同步」的机械结论，不再靠考古。

- 🔴 **`--write-state` 在守卫失败时照写 —— 把失败洗成一条持久的「已核对」声明。**
  写入在 `:145`、失败 raise 在 `:162`。本轮实测复现：sync 脚本跑完守卫 FAIL，`vendor_sync_state.json`
  仍被写成「最近一次核对过的上游状态」。**红着写比不写更糟**——没有记录只是不知道，错误记录是被骗。
  → 写入移到 raise 之后，并由 `tests/test_verify_upstream_sync.py` 断言源码顺序。

- **裸 sha256 对未变换的上游比对，注定永远红。** vendored 文件个个带 headless 变换，raw 比对报 133/257
  漂移，其中大半是变换本身。**永远红的检查等于没有检查**——人会学会略过它。
  → check 3 改用 manifest 作 oracle：按声明的偏离重渲染上游，再比对。可达到的绿才是有意义的绿。

- **中文措辞躲过了英文正则。** `verify_docs_sync` 只认 `badge/tools-(\d+)-`；中文 README 用
  `badge/技法-83-`，于是在注册表已到 89 时陈旧了整整一个版本，**同一行的 `alt="89 tools"` 就在旁边**。
  同类漏网还有 `manifest.json`、`banner.svg`、以及**发给每个 MCP 客户端**的 `_SERVER_INSTRUCTIONS`
  （两处 83，此前无任何守卫读它）。旧闸报 0 处，新闸一次报出 16 处。
  → 教训不是「数字写错了」，而是**守卫的覆盖面被措辞的偶然决定**。计数检查一律做成语言无关，
  并对「同一行 badge 与 alt 自相矛盾」单独设断言——那种自相矛盾任何时候都是 bug。

- **上游工作树是活的。** 本轮进行中上游连提交两次（`afdac78` → `8fe5771` 二十八宿六处算法勘误
  → `23aa38e`），中途还出现过未提交的 WIP。守卫按**磁盘文件**比对，于是别人的未提交编辑会读成
  「上游漂移」，而照着 re-vendor 等于把**未评审的半成品**打进发布物；provenance 记的又是 commit，
  脏树让那条记录自相矛盾。→ 新增 check 0：脏树在本地只提示，`--require-upstream`（发布链）判红。

- **「已 vendored」≠「是当前的」。** `qimenzeri` 依赖的 `DunJiaCalc`/`DunJiaBaGongRules`/`baziLunarLocal`
  三个文件都在树里，但都是旧版，缺的正是新模块要 import 的符号。查依赖要查**具体符号**，不是查文件在不在。

- **`gua/liuyaoTianshi.js` 从未 vendor —— `liuyaoFacade.js` 一直 import 着一个不存在的模块。**
  上游 v3.6.0「六爻天时占法五家」，本仓漏了整整一个文件。同类：`taiyi/core/taiyiSchool.js` 的
  `../../../utils/dateStrSafe.js` 是死链，只因无人 import 才没炸。两者都是 `loadcheck.mjs`（新增，
  `import()` 全部 264 个 vendored 模块）当场抓到的。**AGENTS §5 说得对：load 过 ≠ 真盘不崩——
  但 load 不过一定崩，而这一层此前完全没有。**

- **`selfcheck.mjs` 断言的是形状不是值 —— 三传重排能静默通过。** 六壬只断言
  `sanChuanBranches.length === 3`。上游 v3.7.1 两处勘正（#46 八专/遥克判定序、#62 伏吟末传子卯互刑）
  恰好改的就是三传。
  → **穷举分桶把「是不是回归」从判断题变成计数题**：60 日干支 × 12 月将 × 12 时 = 8640 课全跑，
  新旧差分 336 条，三传变 120 / 仅课名 216；伏吟桶恰为 **丁卯/己卯/辛卯** 三日（上游自述
  「全域仅此 3/720 课变」），非伏吟桶恰为 **己未/庚申/甲寅** 三个八专日，上游点名的
  「甲寅日戌将丑时/午时」2/2 命中，**桶外 0 条**。桶闭合即证明「改动恰好是上游那两处修复」。
  ⚠️ 上游自述当年「并用金标锁死」了**错**答案——这个文件上「golden 变了」不构成回归证据。
  → 两个具名课式已值级钉进 `selfcheck.mjs`。

- **一次 re-vendor 抹掉两处蓄意偏离，都是被测试当场抓到的。**
  ① `tarot/engine/shuffle.js` 上游 v3.7.x 把 sha256 从 `node:crypto` 换成 `node-forge`，整棵
  `tarot/engine` 因缺包加载失败（loadcheck 抓到）→ 改用 `stub_import` 提供 forge 形状的 shim，
  上游函数体保持逐字。② `zhengchuanTiebanLocal.js` 的**动态** `import('./x.json')` 也需要
  `with { type: 'json' }`，而变换的正则只覆盖静态 import（selfcheck 抓到——loadcheck 抓不到，
  因为那是懒加载路径）。后者是通用规则，已并入 `transform()`。
  → 蓄意偏离必须**声明**（manifest）或**机械化**（transform），写在文件里的偏离下一次重 vendor 必被抹掉。

- **`_reexport_required` 只认 `export function`，不认尾部 `export { … }` 清单。** 上游给
  `baziLunarLocal` 的 `buildFlowDays/buildFlowHours` 补了尾部清单，于是自动补 export 变成
  "Duplicate export"，模块整个加载不了。loadcheck 抓到。

- **两个同名 `AstroConst.js` 是一个真陷阱。** `src/constants/`（151 行共享 shim，**有** `SignsProp`/
  `LIST_SIGNS`）与 `src/vendor/constants/`（32 行 Uranian 子集，**没有**）。上游写
  `'../constants/AstroConst'`，在 vendor 树里恰好解析到**后者**，relocate 因此认为无需重指——
  `SignsProp` 静默变 `undefined`，`buildTriplicityPeriods` 真机抛 `reading 'Gemini'`。
  → 三个 astroextra 文件 + `tianxingSnapshot` 都用 `import_redirect` 钉死到共享 shim。

- **条件树用 passthrough，不建模。** 上游两套条件表共 60+ 类，各自 `params` 形状/`validate`/`compile`
  都不同。在 skill 侧重编一遍 = 造第二份真值源，上游一加条件类就烂。让 vendored `compileTree`/
  `compileQimenTree` 跑各叶子自己的 `validate`，错误信息还是本地化的。可发现性放 `agent_guidance`。

- **`scanQimen` 吃的是编译后的树，不是 UI 树。** UI 树 `{kind:'group', joiner, children}` 供快照渲染，
  编译树 `{type:'all', conditions}` 供求值。传错**不会报错**——它安静地匹配不到任何东西，
  产出一个看起来完全合理的「零命中」。真机实测 0 命中才发现（同窗同条件正解是 11 命中）。

- **零命中不是缺段。** 两个新技法的段头都是**无条件 push**，零命中时上游写的是「时间段内无满足条件的
  时辰。」这类真话。所以它们**不进** `AI_EXPORT_OPTIONAL_SECTIONS`——登记成 optional 等于拿一个真实的
  回归探测器（builder 哪天不产该段了）换零收益。判据是**读 builder 源码**，不是猜「搜索可能没结果」。

- **`/electionscan/scan` 属「HTTP 200 带失败信封」家族。** 失败包成
  `{"ResultCode": -1, "Result": {"err": …}}`，而 `HorosaPlainJsonClient` 只看顶层 `err` → 不加守卫
  时 `span_too_large` 会**静默退化成零命中**。新增 `_require_electionscan_ok`，与 `_require_ken_pan` 同族。

- 🔴 **第四个机制缺口：点哨兵永远覆盖不全整棵引擎树（同批复盘时才发现）。**
  以为 v3.7.x 已经同步干净，再审一遍才发现 `vendor/kintaiyi/src/kintaiyi/jieqi.py`
  **卡在有 bug 的首版**：`datetime.datetime(year,…)` 只支持公元 1–9999，而太乙服务的是全年份域
  （前 12999 ~ 16799），域外直接 `ValueError` —— 上游自己的注释写着这会「炸掉整个 taiyi/pan
  （kentang 极端年矩阵三例转红）」，它已改为全程走 `ephem.Date`。
  漏掉的原因很具体：**7 个哨兵一个都不在 ken 引擎目录内部**（`vendor/` 下唯一那个
  `kin_year_domain.py` 是根级共享件），而 `verify_vendor_runtime_sources` 只查
  `REQUIRED_PATHS` 是否**存在**、不查内容。于是「引擎文件在、但是旧的」这一整类漂移无人看管。
  → 新增 check 2b **整棵子树逐文件比对**（`Horosa-Web/vendor` ken 引擎 / `astropy/astrostudy` /
  `astropy/websrv`），三个方向都报：内容改了、vendored 有而上游没了、上游有而 vendored 缺。
  两条实现纪律：① **比对口径必须等于同步口径**——排除集要逐条对齐 sync 脚本的 RSYNC_FILTERS 与
  kinastro 裁剪，否则守卫会对着「本就故意没拷」的文件恒红（README.md / .github 就这么先红了一轮）；
  ② 「上游有而 vendored 缺」只在**已 vendor 的顶层目录内部**判，根级杂项不算欠账，
  但上游**整个新增的顶层目录**单独报一行——那才是「新引擎/新能力」的信号。
  已做负向对照：故意改脏 jieqi.py，守卫精确报出该文件；还原即绿。不是空绿。

- **一次「已经同步完了」之后再审一遍是值的。** 本条就是在宣布 v3.7.x 同步完成、三个提交都落地
  之后，重跑同一套审计发现的。守卫全绿只等于「守卫覆盖到的部分是绿的」——覆盖面本身要被质疑。

- **上游 UI 层改动不必跟。** 同批 `ZeriMain/DunJiaMain/SanShiUnitedMain/models/astro/perfFlags`
  五个文件共 +75 行，全是 `requestIdleCallback` 预挂载 / `forceRender` / kill-switch 之类的
  响应性改造，零引擎逻辑（逐行核过），且五个文件本仓一个都没 vendor（都是 React 页面壳）。
  判据：本仓 vendor 的是**引擎**（DunJiaCalc / sanshi/core/*），不是页面壳。

- **契约版本该不该跟着上游不动？不。** 上游那个数是 localStorage 迁移闸（新键无存档，迁移本就是
  no-op）；skill 这个数是**内容版本**，进每个信封的 `settings_used.version`，是下游判断「段目录变了」
  的依据。24 个新段正是该事件，故 11 → 12（仓内先例：v8 三技法入册、v11 五技法入册）。
  `MIRRORED_UPSTREAM_AIEXPORT_VERSION` 保持 50——上游数字确实没动。两个数字语义不同，别「修」成一致。

### v0.25.1+ / 2026-08 — 被指定为「唯一能做真」的那条发布闸，20 次里一次都没跑过

**症状**：v0.25.1 发完复查，发现 `Release Runtime`（`release.yml`）那次 run 卡在 `queued`。翻历史：
**从 v0.9.2（2026-06）到 v0.25.0，20 次 tag 触发的 run 全部 `cancelled`**。抽查 v0.25.0 那次：
created `08/01 17:08:57` → updated `08/02 17:09:04`，正好 24 小时，`build-release` job
`conclusion=cancelled`、**一个 step 都没执行**。

**根因**：`release.yml` 是 `runs-on: self-hosted`，而 `gh api repos/.../actions/runners` 回
`total_count: 0`——仓库**从来没有注册过 self-hosted runner**。于是每次推 tag 都排队到 GitHub 的
24h 上限被自动取消。而这条流水线**独占**着三样东西：① `verify_upstream_sync.py --require-upstream`
② `verify_export_section_baseline.py --source upstream --require-upstream` ③ SBOM + 构建 provenance
attestation。`ci.yml` 里虽然也调前两个脚本，但**不带 `--require-upstream`**，GitHub runner 上没有上游
checkout，脚本自报 `{"skipped": true}` 直接放行（那个 step 名字本身就写着 "skipped without an upstream
checkout"）。两处合起来 = **「vendored 树 vs 上游 HEAD」这一类漂移在任何自动化环境里都从未被断言过**，
而 runs 页面上显示得像有覆盖。

**同一次排查里还揪出第二个空转的**：`verify_export_section_baseline.py` 的 docstring 白纸黑字写着
vendored 模式 "works with no upstream checkout, e.g. GitHub CI"，ci.yml 的注释也跟着说「基线本身的
自洽在这里就能红」——**两句都是假的**。它读的 `vendor/runtime-source` 是 **gitignored** 的，CI 全新
checkout 上根本没有，实测输出 `::notice::export-section-baseline skipped`。于是段级欠账棘轮
（「只减不增」那道）在 CI 里同样零断言。**注释写「这里能红」不等于真会红——要去 run 的注解里看。**

旁证：`contracts/vendor_sync_state.json` 至今记着
`skill_mirrored_version: 48`（v0.24.0 手工跑时写的），而 registry 常量从 v0.25.0 起已是 **50**——
那个专门用来「避免 vendored 树静默落后」的文件，自己静默落后了两个版本。

这是 v0.24.0「守卫结构性失明」的**第四例**，也是最讽刺的一例：为了堵住失明而新建的守卫，本身从不执行。
前三例是守卫射程不够（比对自己的 vendored 拷贝 / 只比键不比段 / 正则只认英文标签），这一例是**守卫压根
没运行**——比射程不够更难发现，因为射程可以读代码看出来，「有没有真跑」只能去翻 runs 历史。

**守卫/法则**：

- **判一个守卫是否有效，先问「它上一次真跑是什么时候」，再问「它断言了什么」。** `runs-on: self-hosted`
  + 零注册 runner = 永久排队后取消，颜色是灰的不是红的，谁都不会注意。
- `release.yml` 去掉 `push: tags` 触发，改为**仅 `workflow_dispatch`**——宁可明确没有，也不要一条看起来
  在跑、实际每次都被取消的流水线。
- 跨树两闸落地为**本机 pre-tag 步骤** `scripts/preflight_release.py`（须 `HOROSA_SOURCE_ROOT` 指向
  Horosa-Public，否则直接拒绝运行），写进 AGENTS §7 发布协议。成功会重写
  `vendor_sync_state.json`，**该 diff 即「跨树核对真发生过」的 git 证据**。
  （v0.26.0 起该文件已被 `contracts/upstream_provenance.json` 取代——超集，另记上游 commit /
  应用版本 / preset 键集 / core-js 树摘要；`tests/test_verify_upstream_sync.py` 断言旧文件必须不存在。）
- `verify_upstream_sync.py` 在无上游树时**不再纯 skip**：改为断言 state 里的 `skill_mirrored_version`
  是否仍等于 registry 常量，落后就打 `::warning`（当前就在报 48 vs 50）。CI 保持绿（避免 v0.25.0 那种
  带红上 main），但漂移从此在每次 run 里可见，而不是无声无息。
- `verify_export_section_baseline.py` 同样不再纯 skip：无 aiExport 源时改为断言**基线 vs 仓内 registry
  自洽**（`_assert_baseline_coherent`——基线里的键必须都还在 `AI_EXPORT_PRESET_SECTIONS` 里），抓
  「技法改名/删了而基线还留着旧键」。已用反向测试确认它**真会红**（往基线塞一个不存在的键 → FAIL）。
  docstring 与 ci.yml 里那两句不实描述一并改掉。
- **`::warning::` 是单行命令**：消息里带 `\n` 会被 GitHub 在第一个换行处截断，注解结尾留个悬空冒号
  （第一版就是这样，补救命令整条没进注解）。补救指令必须写在同一行。

### v0.25.1 / 2026-08 — 第一次真跑全套 live：7 红里 4 个是本机无 Mongo、2 个是真段缺陷、1 个是隔离没做全

**症状**：在 v0.25.0 runtime（独立 root `rt-verify`，心跳 `pdSyncRev = pd_method_sync_v15` 与当前 rev 一致）
上跑全套 `uv run pytest` → **7 failed / 332 passed / 1 skipped**；而同一棵树在服务未起时是
**278 passed / 62 skipped / 0 failed**。更迷惑的是 `doctor` 同时报 `status: ready` + 双端点 reachable。

**根因分三类（别混为一谈）**：

1. **4 条死在 `/nongli/time`** ：`xiaoliuren` / `feigong` / `zhengchuan_tieban` / `zhengchuan_dading`。

   > 🔴 **本条的归因在 v0.26.1 被推翻，保留原文供对照。** 当时判为「Java 聚合层的 app 注册在 Mongo 里，
   > 本机无 Mongo → 这一族路由恒 9999（`no.register.app.in.sys.forapp`）」。v0.26.1 复审实测：**Mongo
   > 在跑**、日志里**零** `no.register.app`、真实错误码是 **`200001 param error`**。真因是**本仓的产品
   > bug**：这五个占时工具（还有无测试覆盖的 `xiaochengtu`/`guice`）用 `payload.get("lat")` 取值，而
   > schema 把 `lat` 列为可选 → 把 **`lat: null`** 发给要求 lon+lat 均非空的 `/nongli/time`。
   > 对照 `qimen`/`taiyi` 用的是 `payload["lat"]`（必填），所以它们从来不犯。
   >
   > **为什么会误诊成环境问题**：Java 的农历结果按**年**缓存。任何一次带 lat 的请求都会把该年焐热，
   > 此后同年的无 lat 请求**全部成功**。于是它表现为「有时好有时坏、换台机器就好了」。决定性实验：
   > 同一 commit 下先对 1998 年发一次带 lat 的请求，两个原本红的 zhengchuan 测试立刻转绿。
   > **诊断这类「时好时坏」务必换一个冷年份**，否则你在测一个已经被自己焐热的缓存。
   > 修复见 `service.py::_require_cast_geo`（缺 lon/lat 提前报结构化错误，不再把 null 发出去）。

   下面这段关于 doctor / selfcheck 的结论**仍然成立**，与归因无关：**`doctor` 探的是 `/common/time`，根本不碰这族路由——
   所以 `status: ready` 不构成「Java 侧技法可用」的证据。`selfcheck` 更迷惑：它的 `compute` 步骤
   报 `tool: nongli_time, ok: true`，但那是 issue #14 加的 **chart 侧回退探针**在答题——同一时刻
   直接 POST `/nongli/time` 仍是 500 / 9999（v0.25.1 装完新 runtime 实测）。
   **doctor 绿 + selfcheck 绿 都不等于这族路由活着。**
2. **2 条是 v0.25.0 段级回填留下的「陈旧断言」，不是产品缺陷**——第一直觉判成段缺陷是错的，
   判据是**去 preset 里查这个段名到底还在不在**：
   - **`taiyi`**：断言写 `assert "[起盘]" not in snapshot`（"no doubled 起盘"）。但上游 v50 起
     `起盘` 已是**注册在 taiyi preset 里的正式透传段**，与 builder 的 `[起盘信息]` 并存是对的。
     旧断言编码的是 v50 之前「后端 起盘 段被丢弃」的行为。
   - **`acg`**：断言写 `assert "[行星线经度]" in snapshot`。但该旧段名在 v50 已**并入单段
     `占星地图`**（`registry.map_legacy_section_title` 里就写着这条映射），preset 里只有 `占星地图`。
   两者都是「registry 改了、live 断言没跟着改」，而 live 测试**进不了 CI**，于是无人发现。
3. **1 条是隔离没做全**：`test_error_paths_return_a_conformant_envelope`——v0.25.0 之后新加的 autouse
   fixture 把 `HOROSA_RUNTIME_ROOT` 钉到空目录，本意是与 CI 同形；但**默认端口上有活服务**时它照样失败，
   因为只钉了 runtime root、没钉 service endpoint，请求照样打通 → 本该失败的错误路径成功了
   （`assert True is False`）。CI（无服务）绿、维护机（服务在）红，正是 v0.25.0 那条教训的**镜像**。

**法则/守卫**：

- **「live 全绿」在无 Mongo 的机器上不可达**——干净 Windows 机的最强信号只有 chart 半边。README 的测试数
  因此改按**离线 CI 形状**标注（278 passed / 62 skipped），不再声称一个没人真验过的 `N / N pass`。
- **改 export preset / 段名映射时，必须同步 grep live 测试里的段名断言**。段级回填（v0.25.0 那种
  216→7 的大批量）只跑得动 CI 里的离线契约；`@requires_runtime` 的段名断言在 CI 里恒 skip，
  改错了要等下一次有人真起服务才炸。判据永远是 **preset 里有没有这个段名**，不是凭印象说「重复/缺失」。
- 想把 `requires_*` 测试真正钉成 CI 形状，**必须同时把 service root 指到不可达地址**——只钉 runtime root
  不够（本条是 `HOROSA_RUNTIME_ROOT=<空目录>` 复现法的补丁：那招只在服务也没起时成立）。
- 判 Java 侧是否真可用，别看 `doctor`，直接打 `/nongli/time` 看是不是 `ResultCode 9999`。

### v0.25.1 / 2026-08 — 中文首页的数字漂了两代，因为守卫的徽章正则只认英文标签

**症状**：`verify_docs_sync.py` 全程绿，而 `README.md`（中文首页 = 默认落地页）上：徽章写
`技法-83`（同一行的 `alt` 却写着 "89 tools"）、验收表写 `可调用工具 83 / 83`、`已建模 63 个导出
technique`；测试数四处写 `326` 而 `README_EN.md` 的代码块写 `315`；`📦 Release runtime` 行还写着
「Windows (x64) 由构建机补传（补传前 win 用户拿到上一版 runtime）」——而 v0.25.0 的 Windows 半边
早在 2026-08-02 就已补齐，`sync_windows_release.py --check` 判定 in-sync。即：中文首页在劝退
Windows 用户，并把工具数少报了 6 个。

**根因**：`check_tool_coverage()` 的徽章正则是 `badge/tools-(\d+)-`，只能匹配 EN 侧的
`badge/tools-89-`；zh 侧标签是中文的 `badge/技法-83-`，**整个漏出守卫射程**。于是 83→89 那次 bump
只有被守卫盯着的 EN 侧被迫改对，中文首页无人拦。同源问题一串：验收表的 `可调用工具 N / N` 与
`已建模 N 个导出 technique` 都是 registry 的纯函数，却从来没人断言。测试数更糟——它**无法从代码静态
推出**，于是五处提及各写各的，分叉成 326×7 + 315×1 谁也没发现。这是 v0.24.0「守卫结构性失明」的第三例：
守卫不是不存在，是**射程比它自称的窄**。

**守卫**：① 徽章正则拓宽为 `badge/(?:tools|技法)-(\d+)-`；② 新增 zh/EN 两侧「可调用工具 N / N」行
断言 == `len(TOOL_DEFINITIONS)`；③ 新增「已建模 N 个导出 technique」断言 == `len(AI_EXPORT_TECHNIQUES)`；
④ 测试数不可静态推导 → 新增 `check_test_count_consistency()`，只守「两份 README 的所有提及必须是同一个
数」，首跑即抓出 315/326 分叉；⑤ `本地 memory / report 83 / 83` 这类**既推不出、也没有测试覆盖的手测
计数**直接改写成结构性陈述（「每次技法调用写 1 条 run 记录 + 1 份 JSON artifact」），不再留一个会腐烂
的数字。

**法则**：README 里的每个数字，要么**能从代码断言**（那就当场加断言），要么**改写成不含数字的结构性
陈述**——绝不留「只能靠人记得更新」的计数。双语文档的守卫正则**必须覆盖两种语言的标签**，只写英文
pattern 等于只守了一半。

### v0.25.0+ / 2026-08 — 一个 em dash 打死整个 Windows runtime（无 BOM 的 .ps1 + PowerShell 认花引号）

- **症状**：v0.25.0 Windows 半边刚建完，装进独立 runtime root 跑 `selfcheck` → `runtime.start_failed`，
  stderr 是启动器自己的 **4 个 parse error**：`Missing closing '}' in statement block`、
  `Unexpected token 'chartpy:'`、`The string is missing the terminator: "`——启动器**一行都没跑**就死，
  Java/chart 双半边全不起。zip 里文件一个不少、`verify_runtime_release.py` 全绿。
- **根因链**：① runtime manager 用 `powershell`（**Windows PowerShell 5.1**，见
  `manager._platform_command`）跑 `.ps1`；② 5.1 对**无 BOM** 的 `.ps1` 按**系统 ANSI 代码页**解码
  （本机 ACP=1252）；③ UTF-8 的 `—`(U+2014, `E2 80 94`) 于是解成 `â` `€` + **U+201D**；
  ④ PowerShell 词法分析器**把 U+201D 当字符串定界符**——`Write-Host "…without them — it may…"` 的字符串
  就地截断，后半行变成代码，级联炸穿整个文件。
- **为什么以前没炸**：`—` 早就在这两个模板里（v0.12.0 加固时进的注释），但**都在注释行**——注释到行尾
  为止，混进一个花引号也无所谓。issue #14（`3706c94`）把降级提示写进了一个 **`Write-Host` 字符串字面量**，
  这是第一次让非 ASCII 落进可执行的字符串里；而那之后**第一次 Windows 构建**就是本次 v0.25.0 补建。
  实证：同一文件去掉 BOM + 把 `—` 放回字符串 → 4 errors；去掉 BOM 但字符串里用 ASCII `-` → parse OK。
- **修复**：两个模板改为 **UTF-8 with BOM**（正解，连注释里的 `格局/神煞` 也不再 mojibake）+ 那条
  `Write-Host` 里的 `—` 换成 ASCII `-`（第二层：BOM 万一被工具剥掉也不会炸成 parse error）。
  `manager._apply_runtime_overrides` 与 builder 都是 `shutil.copy2`，BOM 逐字节随行。
- **守卫**（三层）：① `tests/test_runtime_launcher_templates.py`——BOM 断言 + 「非 ASCII 只许出现在注释行」
  （到处跑，含 Linux CI）；② 同文件里 Windows-only 用 `powershell`
  `[Parser]::ParseFile` **真解析**，CI 的 `windows-smoke` job 会执行；③ 发布闸
  `verify_runtime_release.py::_assert_windows_launchers_are_bom_encoded`——直接读 zip 里那两个 `.ps1`
  的前三字节，上传前拦住（配套 fake-zip 正反测试）。
- **横切教训**：`verify_runtime_release.py` 查的是「文件在不在」，查不出「文件能不能跑」。**跨引擎升级版的
  Windows 补建必须真装真跑**（AGENTS §7 的 native-verify 一步不能省）——这次正是靠它逮住的，否则上传的
  就是一颗谁也起不来的 runtime，而所有绿灯都会说没问题。

### v0.25.0+ / 2026-08 — 维护机装着 runtime，把「其实要 runtime」的线材契约测试藏到了 CI 才炸

- **症状**：v0.25.0 发布 commit 的门禁本地 254 passed 全绿，push 后 main 上 `CI` 的 `test` 与
  `windows-smoke` **两个 job 同时红**——`tests/test_mcp_contract.py` 的
  `test_numeric_coordinates_reach_normalization_instead_of_being_rejected` 与
  `test_request_escape_hatch_works_over_the_wire` 断言 `ok is True`，实收
  `error.code == runtime.not_installed`。两平台同一原因，红了一整天没人发现（发布当天没人再看 CI）。
- **根因**：这两条是**线材契约**测试（考 MCP 面广告的 schema / 归一化 / `request` 逃生通道），却用
  「算成功」当判据 → 走 `call_tool` 一路真算。维护机装着离线 runtime，所以本地恒绿；CI runner 上没有
  runtime，`_require_runtime` 直接抛 `runtime.not_installed`。**「本地全绿」在这类测试上不构成证据——
  维护机与 CI 的形状不同**，而 CI 是唯一无 runtime 的环境。
- **顺带挖出的第二个真 bug**：`ToolEnvelope` 的顶层镜像三键（`code`/`message`/`details`，
  `schemas/common.py` 明写「使既有按 code/message/details 读的调用方零改动」）**只在 MCP 面构造的错误
  信封上填**（闸门 / pydantic 校验），`service.run_tool` 自己构造的错误信封一个都没填 → 最常见的失败
  （`runtime.not_installed` / `tool.ken_compute_failed` / `transport.*` / `tool.internal_error`）在顶层
  `code` 上读到 `None`。既有测试只覆盖闸门那条路径，所以「信封契约」看起来是有守卫的。
- **守卫**：① `test_mcp_contract.py` 加 autouse fixture 把 `HOROSA_RUNTIME_ROOT` 钉到空临时目录——
  整个文件**一律在「runtime 未安装」形状下跑**，维护机与 CI 同形，此类依赖当场暴露（新写的线材测试
  再想偷偷依赖 runtime 也会本地就红）；② 两条测试改为断言真正要考的东西（`input_normalized` 里
  数字经纬度已被吸收成 `39n54`/`116e24`；逃生通道的内层字段确实到了归一化），并共用
  `_assert_passed_the_mcp_surface`（只否掉 `tool.invalid_payload` / `agent_guidance.required` 两个
  「归一化之前就被打回」的 code），与本机有没有 runtime 解耦；③ `run_tool` 两条错误路径 + dispatch
  解析失败路径补齐镜像三键，`test_error_paths_return_a_conformant_envelope` 扩到闸门**之后**的失败
  信封，逐键断言 `顶层 == error.*`。
- **可复现判据**（没有 CI 也能在维护机上验）：`HOROSA_RUNTIME_ROOT=<空目录> uv run pytest` —— 这条
  等价于 CI 的形状；发版前值得跑一遍。

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

**另有一类不是「取不到」，而是「上游自己就不当它是可导出技法」——同样别当缺口重查（v0.26.0 记）：**

- **kentang 服务 `qizhengelection`（七政四余择日）与 `xuanshi`（玄学史）** —— 两者都在上游
  `integrations/kentang/serviceRoot.js` 的 21 个服务里，本仓无对应工具。判据：**两者都不在
  `aiExport.js` 的 `AI_EXPORT_TECHNIQUES` / `AI_EXPORT_PRESET_SECTIONS` 里**（grep 零命中）——
  即上游自身没把它们登记为 AI 可导出技法，没有 preset 段表，也就不存在「缺段」。
  `xuanshi` 是 ECharts 驱动的史料检索/地图页（`XuanShiCelestial/XuanShiMap`），非排盘技法；
  其 SQLite 数据仍在 `REQUIRED_PATHS` 里（打包需要），**有数据 ≠ 有技法**，别据此判缺口。
  → 沿用 AGENTS §5 审计前置的老结论：**权威清单是 `aiExport.js` 的技法表，不是服务注册表、
  也不是组件目录**。「上游有 engine/服务 ≠ 可进公开 skill」。

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
