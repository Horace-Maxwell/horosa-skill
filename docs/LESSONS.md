# 逐版本经验台账 / Lessons Ledger

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
