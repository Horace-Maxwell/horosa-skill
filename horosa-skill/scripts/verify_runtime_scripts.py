#!/usr/bin/env python3
"""运行时启动/停止脚本的**误杀纪律**必须成立，且补丁器的锚点必须还对得上上游。

背景：上游 macOS 启动器的 `reclaim_stale_port` 按**命令行子串**（`webchartsrv` / `astrostudyboot`）
`kill -9` 端口持有者，注释还写着「绝不误杀第三方」——但星阙桌面端跑的正是这两个镜像，所以
那句判断不成立。`stop_horosa_local.sh` 有 `grep -Fq "${ROOT}"` 守卫、Windows 启动器是**拒绝**
而非 kill，唯独 mac 的 start 没跟上。AGENTS §8 早就把这条定成了维护者纪律，却没落到产品里。

修复走安装/启动时补丁（`manager._patch_mac_launcher`），所以这把守卫验的是**补丁后的结果**：

1. 补丁器跑在上游脚本上之后，`reclaim_stale_port` 里的每个 `kill -9` 前面都有 `horosa_owns_pid`；
2. `-Dhorosa.runtime.root=` 的出现次数 == `-Dhorosa.runtime.owner=`（exploded 模式下 java 的
   argv 里没有 ROOT，只能靠这个显式标记判归属，漏一个就有一条判不出来的启动路径）；
3. 补丁后的脚本 `bash -n` 通过（补丁把脚本改坏 = 运行时起不来，比误杀更早暴露但同样致命）；
4. 上游 `stop_horosa_local.sh` 仍带 ROOT 守卫（漂移警报：上游若哪天删了它，这里先响）；
5. start/stop 脚本非注释行里没有 `pkill` / `killall`（AGENTS §8「绝不按进程名杀」）。

`--self-test` 跑负向对照：把守卫要抓的东西一个个注回去，每个都必须让它变红。
上游树缺席（CI 上 vendor/runtime-source 是 gitignored 的本地构建输入）时跳过 1–3，只跑 5。
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
REPO_ROOT = PKG_ROOT.parent

UPSTREAM_START = REPO_ROOT / "vendor/runtime-source/Horosa-Web/start_horosa_local.sh"
UPSTREAM_STOP = REPO_ROOT / "vendor/runtime-source/Horosa-Web/stop_horosa_local.sh"
WINDOWS_START = SCRIPTS / "runtime_templates/windows/start_horosa_local.ps1"

_COMMENT = re.compile(r"^\s*#")


def _patcher():
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.config import Settings
    from horosa_skill.runtime.manager import HorosaRuntimeManager

    return HorosaRuntimeManager(Settings(runtime_root=Path(tempfile.mkdtemp())))


def _noncomment_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not _COMMENT.match(line)]


def audit_patched_launcher(text: str) -> list[str]:
    """补丁后的 mac 启动器必须满足的不变量（纯函数，供测试注入坏样本）。"""
    errors: list[str] = []

    # 1. reclaim_stale_port 函数体内，每个 kill -9 之前都要有 horosa_owns_pid
    start = text.find("reclaim_stale_port() {")
    if start >= 0:
        body = text[start : text.find("\n}\n", start) + 3 or len(text)]
        for match in re.finditer(r"kill -9", body):
            before = body[: match.start()]
            if "horosa_owns_pid" not in before:
                errors.append(
                    "reclaim_stale_port 里有一个 kill -9 前面没有 horosa_owns_pid 守卫 —— "
                    "这正是会杀掉用户星阙桌面端的那条路径"
                )
                break

    # 2. root 标记与 owner 标记一一对应
    owners = text.count("-Dhorosa.runtime.owner=")
    roots = text.count('-Dhorosa.runtime.root="${ROOT}"')
    if owners and roots != owners:
        errors.append(
            f"-Dhorosa.runtime.root 标记 {roots} 个 ≠ -Dhorosa.runtime.owner {owners} 个 —— "
            "少标的那条 JVM 启动路径在 exploded 模式下判不出归属"
        )

    # 5. 不许按进程名杀
    for line in _noncomment_lines(text):
        if re.search(r"\b(pkill|killall)\b", line):
            errors.append(f"出现按进程名杀的调用（AGENTS §8 禁）：{line.strip()[:80]}")
            break
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true", help="跑负向对照：每种坏法都必须被抓到")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    errors: list[str] = []
    notes: list[str] = []

    if UPSTREAM_START.is_file():
        tmp = Path(tempfile.mkdtemp()) / "start_horosa_local.sh"
        shutil.copy2(UPSTREAM_START, tmp)
        try:
            applied = _patcher()._patch_mac_launcher(tmp)
        except Exception as exc:  # noqa: BLE001 - 锚点漂移要报出来，不能吞
            print(f"runtime-scripts guard FAILED: 补丁器在上游脚本上失败：{exc}", file=sys.stderr)
            return 1
        if applied:
            errors.extend(audit_patched_launcher(tmp.read_text(encoding="utf-8")))
            probe = subprocess.run(["bash", "-n", str(tmp)], capture_output=True, text=True)
            if probe.returncode != 0:
                errors.append(f"补丁后的启动器 bash -n 不通过：{probe.stderr.strip()[:200]}")
            notes.append("mac 启动器：补丁已验（守卫在 kill 之前、root 标记齐、语法有效）")
        else:
            notes.append("mac 启动器：这版上游无 kill 路径（如 v0.36.0 随包那版），无需补丁")

        if UPSTREAM_STOP.is_file():
            stop_text = UPSTREAM_STOP.read_text(encoding="utf-8")
            if 'grep -Fq "${ROOT}"' not in stop_text:
                errors.append(
                    "上游 stop_horosa_local.sh 不再带 `grep -Fq \"${ROOT}\"` 守卫 —— "
                    "停止路径也会开始误杀，补丁器需要同步扩到 stop"
                )
            errors.extend(e for e in audit_patched_launcher(stop_text) if "pkill" in e or "killall" in e)
            notes.append("stop 脚本：ROOT 守卫仍在")
    else:
        notes.append("上游树缺席（vendor/runtime-source 是本地构建输入），跳过启动器检查")

    if WINDOWS_START.is_file():
        win = WINDOWS_START.read_text(encoding="utf-8")
        block = win[win.find("already in use") - 600 : win.find("already in use") + 200] if "already in use" in win else ""
        if block and "Stop-Process" in block:
            errors.append("Windows 启动器的端口冲突分支出现 Stop-Process —— 它的纪律是**拒绝**而非 kill")
        notes.append("Windows 启动器：端口冲突分支仍是拒绝而非 kill")

    if errors:
        print("runtime-scripts guard FAILED —— 误杀纪律被破坏：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("runtime-scripts OK: " + "；".join(notes))
    return 0


def _self_test() -> int:
    """负向对照：守卫要抓的每一种坏法，都必须真的让它红。"""
    if not UPSTREAM_START.is_file():
        print("self-test 跳过：上游树缺席", file=sys.stderr)
        return 0
    tmp = Path(tempfile.mkdtemp()) / "s.sh"
    shutil.copy2(UPSTREAM_START, tmp)
    _patcher()._patch_mac_launcher(tmp)
    good = tmp.read_text(encoding="utf-8")

    cases = {
        "去掉 kill 前的守卫": good.replace(
            '        horosa_owns_pid "${pid}" || { diag_log "port ${port}: ${tag} pid=${pid} is NOT ours; refusing to kill"; continue; }\n',
            "",
        ),
        "少一个 root 标记": good.replace('-Dhorosa.runtime.root="${ROOT}"', "", 1),
        "改用 pkill": good.replace('kill -9 "${pid}"', 'pkill -9 -f "${tag}"', 1),
    }
    failures = []
    if audit_patched_launcher(good):
        failures.append(f"基准样本本身就红：{audit_patched_launcher(good)}")
    for name, text in cases.items():
        if not audit_patched_launcher(text):
            failures.append(f"负向对照未被抓到：{name}")
    if failures:
        print("runtime-scripts self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"runtime-scripts self-test OK: 基准绿，{len(cases)} 种坏法全部被抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
