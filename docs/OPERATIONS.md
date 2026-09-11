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

## 发布前检查

**打 tag 之前必须先跑这一条**（AGENTS §7 标为强制；它把跨树校验一并跑完，成功会重写
`contracts/upstream_provenance.json`，那个 diff 就是「跨树核对真发生过」的 git 证据）：

```bash
HOROSA_SOURCE_ROOT=<Horosa-Public checkout> uv run python scripts/preflight_release.py
```

它内部已含 verify_upstream_sync（`--require-upstream`）/ verify_export_section_baseline
（`--source upstream`）/ verify_vendor_runtime_sources / verify_export_contract_mirror /
verify_docs_sync / verify_builder_parity。此外单独跑：

- `uv run pytest -q`
- `cd horosa-core-js && npm test`（loadcheck 全量 import 冒烟 + selfcheck golden）
- `uv run python scripts/verify_readme_links.py`
- `uv run python scripts/verify_server_json.py`
- `uv run python scripts/build_knowledge_index.py --check`
- `uv run python scripts/run_benchmark.py --skip-runtime`

## ken 技法验证（奇门 / 太乙 / 金口 / 三式合一）

这些技法由 **ken 后端**（`kinqimen`/`kintaiyi`/`kinjinkou`）在 Python chart 服务上计算（`/qimen/pan`、
`/taiyi/pan`、`/jinkou/pan`），`horosa-core-js` 只负责把 ken 响应重排成 `aiExport.js` 分段。验证需要 chart
服务在线（`:8899`，以及 Java `:9999`）：

1. 起后端：在 Horosa-Web 下 `HOROSA_SKIP_UI_BUILD=1 ./start_horosa_local.sh`（mac）/ `start_horosa_local.ps1`（Win）。
2. 确认监听：`:9999`（Java）+ `:8899`（chart/ken）。
3. `uv run pytest -q`：`tests/test_local_js_tools.py` 里 qimen/taiyi/jinkou/sanshiunited 为集成测试，后端不在时自动 skip；
   `tongshefa` 始终执行。
4. 验收标准：每个技法产出其 aiExport.js 分段（奇门：起盘信息/盘型/盘面要素/奇门演卦/八宫详解/九宫方盘；
   太乙：起盘信息/太乙盘/十六宫标记；金口：起盘信息/金口诀速览/金口诀四位/四位神煞），且 export 契约干净
   （无 missing/unknown 分段）。

离线运行时必须打包 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}` 及其依赖（bidict/numpy/kerykeion/ephem/
pendulum）——见 [`OFFLINE_RUNTIME_RELEASES.md`](./OFFLINE_RUNTIME_RELEASES.md)。

## Runtime Release

Runtime release 采用“轻仓库 + 重 release 资产”模式。

**v0.38.0 起的发布流（A5）**：维护机 `bash horosa-skill/scripts/publish_release.sh --draft --dispatch`（seed + .mcpb + wheel +
SBOM 上 draft，触发 `release-runtime.yml`）→ 托管 runner 从 seed 派生 Windows 半、装双平台清单（钉 tag + size）、SHA256SUMS、
SBOM、provenance attestation、`runtime-matrix.yml` 三台真机验证 → `python horosa-skill/scripts/sync_windows_release.py --check
--tag vX.Y.Z --draft` 报 `[OK]` → `gh workflow run release-runtime.yml -f version=X.Y.Z -f publish=true` 转公开 latest →
`--check` 公开 latest。清单只在两平台齐了才上 release，「缺半」窗口不再存在。

- 构建脚本（seed）：[`package_runtime_payload.sh`](./../horosa-skill/scripts/package_runtime_payload.sh)（经 `publish_release.sh`）；
  Windows 半：[`build_runtime_release_windows.py --seed`](./../horosa-skill/scripts/build_runtime_release_windows.py)（流水线）；
  旧的 [`build_runtime_release.sh`](./../horosa-skill/scripts/build_runtime_release.sh) 仍可本地双平台构建（vendor 模式后手）
- 输出目录：`horosa-skill/dist/runtime/`
- 必要资产：
  - `horosa-runtime-darwin-arm64-v<version>.tar.gz`
  - `horosa-runtime-win32-x64-v<version>.zip`
  - `runtime-manifest.json`
  - `SHA256SUMS.txt`
  - `horosa-skill-sbom.json`
  - `horosa_skill-<version>-py3-none-any.whl`（零安装资产：`uvx --from <URL> horosa-skill …` 免 git、免 PyPI；发布脚本步骤 [5/8]
    `uv build --wheel` 产出，`release-completeness.yml` 断言在场并真跑 `--version`；v0.38.0 起）
  - `horosa-skill-<version>.mcpb`（Claude Desktop 一键安装包；`horosa-skill/scripts/build_mcpb.sh`
    做 validate → pack → sha256。`server.json` 的 mcpb package 直指这个 URL，缺了它注册表那条记录 404。
    断言在 `release-completeness.yml`）

### 没有 payload 变化的发布：重打，不重建

一次发布若**不含 payload-affecting 变化**（引擎 / core-js / 启动器包内容都没动，改动全在 Python 包
或安装侧补丁），仍然必须换掉资产文件名与**嵌入清单里的版本**
（`verify_runtime_release.py::_assert_payload_manifest` 要求嵌入版本 == 发布清单版本）。

Windows 半边尤其只能重打：它的构建输入（`vendor/runtime-source/runtime/windows`、`prepareruntime`）
**只存在于 Windows 构建机上**，mac 上无从重建。

```bash
cd horosa-skill
gh release download v<old> -p 'horosa-runtime-win32-x64-v<old>.zip'
uv run python scripts/repack_release_assets.py \
    --source horosa-runtime-win32-x64-v<old>.zip \
    --out    horosa-runtime-win32-x64-v<new>.zip \
    --version <new>
uv run python scripts/verify_runtime_release.py --manifest <新清单> \
    --windows-archive horosa-runtime-win32-x64-v<new>.zip
```

重打只改 `runtime-payload/runtime-manifest.json` 的版本字段，其余条目**按条目原样搬运**——
`.ps1` 的 UTF-8 BOM 必须原封不动（丢了 BOM → PowerShell 5.1 按 ANSI 解码 → 启动器不可用，
v0.25.1 的坑）。守卫：`tests/test_repack_release_assets.py`。

🔴 **绝不要在资产不齐时打 tag。** `releases/latest/download/runtime-manifest.json` 是安装路径的
唯一入口；一个没有资产的新 tag 会让 `latest` 指向它，于是**每一次新安装都 404**——
这正是本仓「缺半」台账反复记的那个失败模式。

## Provenance / Attestation

v0.38.0 A5 起 attestation 由 `release-runtime.yml` 的 `assemble` job 对两份归档 + 清单 + SHA256SUMS 做
（`actions/attest-build-provenance@v2`，dry run 不做）：`gh attestation verify horosa-runtime-win32-x64-vX.Y.Z.zip
--repo Horace-Maxwell/horosa-skill`。**≤ v0.37.0 的资产没有 attestation**——旧 `release.yml` 是 `runs-on: self-hosted`
而本仓从未注册过 self-hosted runner（v0.9.2→v0.25.0 的 20 次 tag 触发全部排队 24h 后被取消，零 step 执行；
实测 v0.26.0 的 manifest 查 attestation 404），该 workflow 已删除。对旧版本别照着跑 verify 再去怀疑资产。

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
