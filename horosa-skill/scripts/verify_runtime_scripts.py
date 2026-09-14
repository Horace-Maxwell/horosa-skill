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

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
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


_WIN_JAVA_START = re.compile(r"^\$JavaProc = Start-Process .*$", re.M)
_WIN_PY_START = re.compile(r"^\$PyProc = Start-Process .*$", re.M)
_WIN_RAW_EMBED = re.compile(r'r"\$[A-Za-z_]+"')
_WIN_BARE_ARGLIST = re.compile(r"-ArgumentList @\(\$")
_WIN_JAR_ARG = re.compile(r"^\$JarArg = '(?P<value>[^']+)'\s*$", re.M)


def audit_windows_launcher(text: str) -> list[str]:
    """Windows 启动器模板的不变量（v0.38.0 B1；纯函数，供 --self-test 注入坏样本）。

    1. Java 必须钉 --server.address=127.0.0.1（Spring Boot 默认 0.0.0.0：防火墙弹窗 + 局域网暴露；mac 启动器早就钉了）。
    2. Start-Process -ArgumentList 不会替你加引号：路径元素（bootstrap .py、jar）必须自己带引号，否则
       `C:\\Users\\John Doe\\…` 断成两段，chart 与 Java 都起不来。
    3. Python bootstrap 里的路径必须是 JSON 字面量（$(ConvertTo-Json … -Compress)），raw 字符串 r"$X"
       遇尾反斜杠/引号即碎。
    4. Java 的 -jar 参数必须是相对 $Root 的纯 ASCII 单引号字面量 `$JarArg`（v0.38.1）：JDK 17 的 Windows 启动器经 ANSI
       代码页读命令行，绝对路径里代码页表示不了的字符（en-US 机器上的中文）变成 `?`，Java 后端起不来、只剩 chart。
    """
    errors: list[str] = []
    java = _WIN_JAVA_START.search(text)
    if not java:
        errors.append("Windows 启动器找不到 `$JavaProc = Start-Process` 行")
    else:
        if "--server.address=127.0.0.1" not in java.group(0):
            errors.append("Windows 启动器起 Java 没钉 --server.address=127.0.0.1（默认 0.0.0.0：防火墙弹窗 + 局域网暴露）")
        if "('\"{0}\"' -f $JarArg)" not in java.group(0):
            errors.append(
                "Windows 启动器的 -jar 参数必须是带引号的相对 $JarArg（-ArgumentList 不会替你引号，用户名带空格即断成两段；"
                "绝对 $JarPath 经 JDK 17 启动器的 ANSI 代码页转换，中文目录名会变成 ? → Unable to access jarfile）"
            )
    py = _WIN_PY_START.search(text)
    if not py:
        errors.append("Windows 启动器找不到 `$PyProc = Start-Process` 行")
    elif "('\"{0}\"' -f $PyBootstrapPath)" not in py.group(0):
        errors.append("Windows 启动器的 Python bootstrap 路径没带引号（用户名带空格即断成两段）")
    code = "\n".join(_noncomment_lines(text))  # comments may legitimately quote the bad forms
    jar_arg = _WIN_JAR_ARG.search(code)
    if not jar_arg:
        errors.append("Windows 启动器没有单引号字面量 `$JarArg = '..\\runtime\\windows\\bundle\\astrostudyboot.jar'`（相对、纯 ASCII 的 jar 参数）")
    else:
        value = jar_arg.group("value")
        if not value.isascii() or "$" in value or re.match(r"^(?:[A-Za-z]:|\\\\|/)", value) or not value.startswith(".."):
            errors.append(f"Windows 启动器的 $JarArg 必须是相对 $Root、纯 ASCII、无插值的路径，实际是 {value!r}")
    if _WIN_BARE_ARGLIST.search(code):
        errors.append("Windows 启动器仍有裸的 `-ArgumentList @($…)` 路径元素")
    raw = _WIN_RAW_EMBED.search(code)
    if raw:
        errors.append(f"bootstrap 用 raw 字符串嵌路径（{raw.group(0)}）：尾反斜杠/引号即碎，必须 $(ConvertTo-Json … -Compress)")
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

        upstream_text = UPSTREAM_START.read_text(encoding="utf-8")
        if "--server.address=127.0.0.1" not in upstream_text:
            errors.append(
                "上游 mac 启动器起 Java 不再钉 --server.address=127.0.0.1 —— 两端启动器必须都绑回环，"
                "否则 mac 也会暴露到局域网（v0.38.0 B1 起 Windows 模板已钉）"
            )

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
        win = WINDOWS_START.read_text(encoding="utf-8-sig")
        block = win[win.find("already in use") - 600 : win.find("already in use") + 200] if "already in use" in win else ""
        if block and "Stop-Process" in block:
            errors.append("Windows 启动器的端口冲突分支出现 Stop-Process —— 它的纪律是**拒绝**而非 kill")
        errors.extend(audit_windows_launcher(win))
        notes.append("Windows 启动器：端口冲突分支仍是拒绝而非 kill；Java 钉回环、路径参数带引号、bootstrap 路径 JSON 转义")

    if errors:
        print("runtime-scripts guard FAILED —— 误杀纪律被破坏：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("runtime-scripts OK: " + "；".join(notes))
    return 0


def _windows_self_test_cases() -> tuple[str, dict[str, str]]:
    good = WINDOWS_START.read_text(encoding="utf-8-sig")
    cases = {
        "Windows: Java 不钉回环": good.replace('"--server.address=127.0.0.1", ', "", 1),
        "Windows: -jar 路径去引号": good.replace("('\"{0}\"' -f $JarArg)", "$JarArg", 1),
        "Windows: -jar 回到绝对 $JarPath（ANSI 代码页吞中文）": good.replace("('\"{0}\"' -f $JarArg)", "('\"{0}\"' -f $JarPath)", 1),
        "Windows: $JarArg 变成插值的绝对路径": good.replace(
            "$JarArg = '..\\runtime\\windows\\bundle\\astrostudyboot.jar'", '$JarArg = "$RuntimeRoot\\bundle\\astrostudyboot.jar"', 1),
        "Windows: bootstrap 路径去引号": good.replace("('\"{0}\"' -f $PyBootstrapPath)", "@($PyBootstrapPath)", 1),
        "Windows: bootstrap 回到 raw 字符串": good.replace("$(ConvertTo-Json $ChartEntry -Compress)", 'r"$ChartEntry"', 1),
    }
    for name, text in cases.items():
        assert text != good, f"self-test case did not change the template: {name}"
    return good, cases


def _self_test() -> int:
    """负向对照：守卫要抓的每一种坏法，都必须真的让它红。"""
    failures: list[str] = []
    win_good, win_cases = _windows_self_test_cases()
    if audit_windows_launcher(win_good):
        failures.append(f"Windows 基准样本本身就红：{audit_windows_launcher(win_good)}")
    for name, text in win_cases.items():
        if not audit_windows_launcher(text):
            failures.append(f"负向对照未被抓到：{name}")
    if not UPSTREAM_START.is_file():
        if failures:
            print("runtime-scripts self-test FAILED:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)
            return 1
        print(f"runtime-scripts self-test OK（仅 Windows 模板，上游树缺席）: {len(win_cases)} 种坏法全部被抓到")
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
    print(f"runtime-scripts self-test OK: 基准绿，{len(cases) + len(win_cases)} 种坏法全部被抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
