# Operations

> 读者：运维 / 用户支持。何时读：install / doctor / serve / run 运维操作时。

## 目标

这份文档面向维护者，描述 Horosa Skill 的安装、运行、发布、校验和排障路径。

## 本地运行

1. 进入 [`horosa-skill`](../horosa-skill)
2. 运行 `uv sync --dev`
3. 运行 `uv run horosa-skill install`
4. 运行 `uv run horosa-skill doctor`
5. 运行 `uv run horosa-skill serve`

## 本机门禁（push 前）

本机只认一条镜像 CI 的命令；「顺手跑几把守卫」不算数（v0.39.0 前夜 28 处单语 raise 就是这么漏到 CI 的）：

```bash
cd horosa-skill
uv run python scripts/run_ci_gates.py        # 解析 ci.yml test job 的 24 个 `uv run …` 步骤，按 CI 形状（空 runtime 根 + 两个不可达 *_SERVER_ROOT）本机跑一遍
(cd horosa-core-js && npm test)              # loadcheck（全量 import）+ selfcheck（值级金标）+ handcopy（手抄表审计）
```

它跳过的只有两步「runner 专用」的零安装 wheel 检查（push 后看 CI）。🔴 **别 `for g in scripts/verify_*.py` 裸跑**：
`verify_runtime_live.py` 是会下载 730 MB runtime 并起服务的真机 lane，`verify_matrix_digests.py` 需要 publish job 的输入。

## 发布前检查（preflight）

**打 tag 之前必须先跑这一条**（AGENTS §7 强制；它把跨树校验一并跑完，成功会重写 `contracts/upstream_provenance.json`，
那个 diff 就是「跨树核对真发生过」的 git 证据）：

```bash
HOROSA_SOURCE_ROOT=<Horosa-Public checkout> uv run python scripts/preflight_release.py
```

它按顺序断言：git 身份 + `origin/main` 无滞留 → HEAD 的 ci.yml 结论为 success → **上游 pin 在上游公开远端上**（v0.40.0 起；
先 `git -C <Horosa-Public> fetch origin`）→ `verify_upstream_sync --require-upstream --write-state` → `verify_export_section_baseline
--source upstream` → `verify_vendor_runtime_sources` → `verify_export_contract_mirror` → `verify_technique_provenance` →
`verify_docs_sync`（含四把文档制度守卫）→ `verify_builder_parity` → `verify_runtime_scripts`（启动器补丁在当前上游树上仍打得上）→
`verify_no_stray_runtime_dirs`。任一红 = 不打 tag。

## 上游版本升级（re-vendor）Runbook

上游星阙出新版时按此顺序，缺一步就会出现「同步了却没同步」（LESSONS v0.40.0 两大条的七个形态）：

```bash
export HOROSA_SOURCE_ROOT=/path/to/Horosa-Public                # 只读；唯一参照源
git -C "$HOROSA_SOURCE_ROOT" status --porcelain                # 只允许非 vendored 路径的 WIP；vendored 子树必须干净
PIN=$(python3 -c 'import json;print(json.load(open("horosa-skill/contracts/upstream_provenance.json"))["upstream_git_sha"])')
git -C "$HOROSA_SOURCE_ROOT" branch --contains "$PIN"          # 为空 = 上游改写了历史：逐文件核旧内容是否保留，别信 diff 的文件数
bash horosa-skill/scripts/sync_vendored_runtime_sources.sh      # 重灌 vendor/runtime-source（引擎 / jar / dist-file / 启动脚本）；末尾的 upstream-sync 红是预期
cd horosa-skill; SRC="$HOROSA_SOURCE_ROOT/Horosa-Web/astrostudyui/src"
uv run python scripts/revendor_core_js.py "$SRC" --from-manifest --check    # 工单：verbatim 会自动重渲染；curated / bespoke 要人工复核
uv run python scripts/revendor_core_js.py "$SRC" --from-manifest            # 新上游 import 解析不到 → 在 vendor_manifest.json 加条目或 import_redirect，再跑
#   bespoke / curated：对上游 diff 逐 hunk 落改动，然后 --restamp <vendor/rel.js>；只有确认 diff 与 skill 无关时才直接 restamp
(cd horosa-core-js && npm test)
uv run python scripts/verify_export_contract_mirror.py            # aiExport 版本变了：推进 MIRRORED_UPSTREAM_AIEXPORT_VERSION、回填新段
uv run python scripts/verify_export_section_baseline.py --source upstream --require-upstream
uv run python scripts/gen_knowledge_packs.py && uv run python scripts/gen_bazi_pithy_pack.py
node scripts/build_hover_knowledge_bundle.mjs && uv run python scripts/build_knowledge_index.py
uv run python scripts/gen_technique_provenance.py && uv run python scripts/gen_technique_provenance.py --check
uv run python scripts/verify_upstream_sync.py --require-upstream --write-state   # 全绿才写 provenance
uv run python scripts/run_ci_gates.py                                            # 再做下面的 live 验证
```

上游新增的**用户可见口径**（新设置 / 新段 / 缺省变化）逐条进 schema / guidance / 技法卡 / CHANGELOG（v3.11.2 的 `southMonth` 是样板）。

## Live 验证 Runbook（发布前必做）

**永远打本仓的 vendored 实例，不打默认端口 `:8899` / `:9999`**（那可能是维护者开着的星阙桌面端，且来源不可考）：

```bash
bash horosa-skill/scripts/start_vendored_instance.sh --with-java     # chart @ 8877 + java @ 9977；就绪判据 kentang prewarm … failed=0
cd horosa-skill
export HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:8877 HOROSA_SERVER_ROOT=http://127.0.0.1:9977
# HOROSA_RUNTIME_ROOT 必须是空目录：已装的旧载荷会顶替 JS 引擎与「契约够不够新」判定
HOROSA_RUNTIME_ROOT=$(mktemp -d) HOROSA_SKILL_DATA_DIR=$(mktemp -d) uv run pytest -q -rs -p no:cacheprovider      # 0 failed；skip 只许环境类理由
HOROSA_RUNTIME_ROOT=$(mktemp -d) HOROSA_SKILL_DATA_DIR=$(mktemp -d) uv run python scripts/section_harness.py      # N tools run; clean=N
bash horosa-skill/scripts/stop_vendored_instance.sh                  # 只按 pidfile 停 8877/9977；绝不 pkill -f
```

ken 技法（奇门 / 太乙 / 金口 / 三式合一）由 chart 服务上的 ken 后端算（`/qimen/pan` `/taiyi/pan` `/jinkou/pan`），`horosa-core-js`
只重排成 aiExport 段——它们的验收就在上面这套 live 里（每技法段齐、`missing_selected_sections == []`、`unknown_detected_sections == []`）。

## Runtime Release Runbook（托管流水线）

Runtime release 采用「轻仓库 + 重 release 资产」模式；v0.38.0 起全部在托管流水线上完成，维护机只做 darwin 种子。

```bash
# 0. 前提：main 已推送且 ci.yml 绿；上游 pin 已在上游公开远端；版本已 bump（python scripts/bump_version.py X.Y.Z → uv lock → run_ci_gates）
HOROSA_SOURCE_ROOT=… uv run python scripts/preflight_release.py           # 全绿；若重写了 provenance 就提交它
git tag vX.Y.Z && git push origin vX.Y.Z
bash horosa-skill/scripts/publish_release.sh --draft --dispatch           # seed / .mcpb / wheel / SBOM 上 DRAFT；dispatch release-runtime.yml
#    → 派生 Windows 半 → assemble（双平台清单钉 tag + size、SHA256SUMS、SBOM、attestation）→ runtime-matrix 三台真机（真下载 + 九客户端 + HTTP 握手）
git add server.json && git commit -m "chore(release): pin mcpb sha" && git push   # mcpb sha 必须来自这一次 --draft 构建（打包不可复现）
python horosa-skill/scripts/sync_windows_release.py --check --tag vX.Y.Z --draft   # 必须 [OK]；[GAP] 才是权威
gh workflow run release-runtime.yml -f version=X.Y.Z -f publish=true -f run_matrix=true -f arm_nonblocking=false -f dry_run=false
#    publish job：三条 lane 装的归档 sha == draft 资产 digest → --check → 翻 latest → dispatch completeness + release 模式矩阵
python horosa-skill/scripts/sync_windows_release.py --check              # 公开 latest [OK]
gh release view vX.Y.Z --json assets                                     # 两个归档 + manifest + SHA256SUMS + sbom + mcpb + whl
```

要点：`publish=true` 必须带 `run_matrix=true`（resolve 直接 fail）；tag 只在 release 仍是 draft 时允许重指；每周一 04:23Z 的 schedule
矩阵拿 main 打公开 latest（lane pytest 预算按主机：Windows 2700 s / macOS 1500 s，pytest.log 流式落盘）；
`release-completeness.yml` 每 6 小时校资产（SBOM / mcpb 解包 + sha / wheel 零安装 / 清单 min_os / digest vs SHA256SUMS）。
Windows 半边由 `build_runtime_release_windows.py --seed` 在 windows-latest 上派生；`build_runtime_release.sh`（vendor 模式双平台本地构建）
只是 v0.38.0 之前的历史路径，需要 Windows 侧构建输入，别在 mac 上照着跑。

- 必要资产：`horosa-runtime-darwin-arm64-v<version>.tar.gz`、`horosa-runtime-win32-x64-v<version>.zip`、`runtime-manifest.json`、
  `SHA256SUMS.txt`、`horosa-skill-sbom.json`、`horosa_skill-<version>-py3-none-any.whl`（零安装：`uvx --from <URL> horosa-skill …`）、
  `horosa-skill-<version>.mcpb`（Claude Desktop 一键包；`server.json` 的 mcpb package 直指它）。

### 矩阵 lane 红了怎么看

```bash
gh run list --workflow runtime-matrix.yml --limit 5                     # 或 release-runtime.yml；gh run list --commit 要完整 SHA
gh run download <run-id> -n runtime-matrix-win32-x64 -D /tmp/lane      # darwin-arm64 | win32-x64 | win32-arm64
python3 -c 'import json;r=json.load(open("/tmp/lane/lane-report.json"));print(r["ok"],r.get("installed_archive_sha256"),r.get("download"));[print(k,v.get("ok"),v.get("seconds"),v.get("problems")) for k,v in r["steps"].items()]'
tail -40 /tmp/lane/pytest.log                                            # 超时也有尾巴（v0.40.0 起）
```

- **只有 Windows 红、mac 绿，chart 类全是 `tool.backend_param_error`**：先在 lane 的 chart 日志里找 `KeyError: 'Chiron'`——那是
  「C 库状态线程本地」类问题（Swiss Ephemeris 在 Windows 上按线程存星历路径，AGENTS §8 / §9.3；v0.40.0 draft 就是这条）。
  要在 Windows 上复现，用一次性诊断分支：workflow 只读 draft 资产（`gh release download vX.Y.Z -p 'horosa-runtime-win32-x64-*.zip'`，
  需要 `contents: write` 才看得见 draft），按启动器 bootstrap 的方式自己 `sys.path.insert`（内嵌 Python 带 `._pth`，不认
  `PYTHONPATH`），绝不整段打印环境变量；查完删分支。不碰 main / tag / draft。

- 每周巡检（`runtime-matrix.yml` cron，周一 04:23Z）已有真机 schedule 运行史：2026-09-14、09-21 三 lane 全绿；09-28 两条 Windows lane 在
  pytest 1500 s 处超时（预算已按主机改 nt 2700 + 流式 `pytest.log`，v0.40.0 的 draft 矩阵首次验证）。查：`gh run list --workflow runtime-matrix.yml --event schedule`。

### 历史：没有 payload 变化的发布「重打，不重建」（≤ v0.37.0）

v0.38.0 前 Windows 半边只能在 Windows 构建机上重打（`repack_release_assets.py`，`.ps1` 的 UTF-8 BOM 必须原封不动，守卫
`tests/test_repack_release_assets.py`）。托管派生之后每次发布都从 darwin 种子重新派生 Windows 半，这条路径只在托管流水线不可用时作后手。

🔴 **绝不要在资产不齐时打 tag。** `releases/latest/download/runtime-manifest.json` 是安装路径的唯一入口；一个没有资产的新 tag 会让
`latest` 指向它，于是每一次新安装都 404——这正是「缺半」台账反复记的失败模式（托管流水线的 digest 闸 + `--check` 就是为它而设）。

## Provenance / Attestation

v0.38.0 起 attestation 由 `release-runtime.yml` 的 `assemble` job 对两份归档 + 清单 + SHA256SUMS 做（v0.38.0 实测
`gh attestation verify runtime-manifest.json --repo Horace-Maxwell/horosa-skill` exit 0）
（`actions/attest-build-provenance@v3`，dry run 不做）：`gh attestation verify horosa-runtime-win32-x64-vX.Y.Z.zip
--repo Horace-Maxwell/horosa-skill`。**≤ v0.37.0 的资产没有 attestation**——旧 `release.yml` 是 `runs-on: self-hosted`
而本仓从未注册过 self-hosted runner（v0.9.2→v0.25.0 的 20 次 tag 触发全部排队 24h 后被取消，零 step 执行；
实测 v0.26.0 的 manifest 查 attestation 404），该 workflow 已删除。对旧版本别照着跑 verify 再去怀疑资产。

## 文档实时更新制度（v0.40.0 起，AGENTS.md §2 协议 v3）

文档不是「有空再补」的东西：每次改动都由守卫裁定文档有没有跟上。

| 事件 | 你要做的 | 谁在看 |
| --- | --- | --- |
| 踩坑 / 修 bug | LESSONS 原文 + 索引行；AGENTS 蒸馏；CHANGELOG；守卫 | `verify_docs_sync.py::check_lessons_distilled` |
| 新增 / 删除一份指导性文档 | `docs/DOC_MAP.md` 加/删行 | `check_doc_map` |
| 改 30 秒摘要（薄镜像内容） | 改 `horosa-skill/scripts/gen_agent_mirrors.py` 模板 → `python scripts/gen_agent_mirrors.py` | `check_agent_mirrors_generated` |
| 任何第三方事实变了（客户端路径 / 超时 / 预算 / SDK / CI 运行时） | `horosa-skill/contracts/third_party_facts.json`：改 `fact`、更新 `verified_on`、修 `affects` 里的代码与文档 | `check_third_party_facts`（CI 警告）+ `.github/workflows/docs-currency.yml`（每周一严格，开 issue） |
| 发版 | `python scripts/bump_version.py X.Y.Z` → `uv lock` → `verify_docs_sync.py` | `check_versions` / `bump_version.py --check` |
| 多会话接力 | 复制 `docs/templates/HANDOFF_TEMPLATE.md` 为仓根 `HANDOFF-<主题>.local.md`（gitignored）；开始先读、结束前更新 | 人工（协议 v3 第 5 条） |

复核一条第三方事实的最小动作：打开 `source_url` → 与 `fact` 逐句对 → 变了就改代码与文档、没变也把 `verified_on` 改成今天。
账本里的 `max_age_days` 是 120：过了这个天数，CI 会在 docs-sync 步骤打 `::warning`，周一的 docs-currency 会把它开成 issue。

## 故障处理

- `doctor` 显示 `runtime.manifest_invalid`
  - 检查 `~/.horosa/runtime/current/runtime-manifest.json`
- `services:not_running`
  - 先运行 `horosa-skill stop`
  - 再运行 `horosa-skill serve`
- benchmark 只想跑无 runtime 部分
  - 运行 `uv run horosa-skill benchmark run --skip-runtime`
- `uv run` / `pytest` 报 `pydantic_core` 的 `.so` `library load disallowed by system policy`
  - `.venv` 指向了 miniconda（带 library validation）。重建为 uv 自管 CPython：
    `uv venv --clear --python-preference only-managed --python 3.12 && uv sync`
- 奇门/太乙/金口报 `transport.connection_error` 或返回空盘
  - chart 服务（`:8899`）未起或未挂载 ken。确认后端在线，且 `import kinqimen/kintaiyi/kinjinkou` 能成功
    （`vendor` 在 PYTHONPATH 上）。
- Windows 上 `install` 报 `runtime.path_not_ascii` / doctor 报 `windows:runtime_root_not_ascii`
  - runtime 根必须纯 ASCII：`HOROSA_RUNTIME_ROOT=C:\horosa` 后重装（随包 JDK 与 Swiss Ephemeris 按 ANSI 读路径；自动迁移未做）
- 报告工具报 `report.output_path_not_allowed`
  - `output_path` 是不可信输入：只能落在输出目录或 `HOROSA_REPORT_OUTPUT_ROOTS` 白名单根内（提示注入防线，不是 bug）
- 工具返回 `runtime.starting`（带 `retry_after_seconds`）
  - 后端仍在冷启动；按给定秒数重试。首启与 Windows ARM 仿真慢，`HOROSA_RUNTIME_START_TIMEOUT_SECONDS` 缺省已按仿真放大
- Jev（`HOROSA_JEV*`，默认关）
  - `horosa-skill jev status` 看开关 / scope / surfaces，`jev events` 看决策台账；`HOROSA_JEV_API_KEY` 永不打印、不进任何配置文件或报告
