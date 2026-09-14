#!/usr/bin/env python3
"""仓里不许出现 Java runtime 留下的「字面量占位符」目录。

症状长这样（v0.37.0 清理时实见三处：仓根、horosa-skill/、vendor/runtime-source/）：

    ./${env:HOME:-${sys:user.home}}/.horosa-logs/astrostudyboot/2026/09/04/info/info.log

成因：jar 内 `BOOT-INF/classes/log4j2.xml` 把 basedir 写成
`${env:HOME:-${sys:user.home}}/.horosa-logs/astrostudyboot`。log4j 不展开这个**带默认值**的写法，
于是把整串当字面量目录名，日志落进启动时 CWD 下一个名字诡异的目录 —— 谁也不知道日志去哪了，
而 `git status` 里那个目录名还会把 shell 的 glob 搞疯。

**已装 runtime 早就修好了**（`manager._rewrite_runtime_log4j` 在安装时补丁 jar）。漏网的是
开发用的 `scripts/start_vendored_instance.sh`：它直接跑未补丁的 vendored jar。
v0.37.0 给它接上 `extract_log4j_config.py` + `-Dlog4j2.configurationFile`
（`-Dbasedir=` 覆盖不了 —— <Property> 在配置里已定义，系统属性只在未定义时兜底）。

这把守卫盯的是**复发**：任何时候仓里冒出这种目录，或 dev 启动器丢掉了那个 -D 参数，就红。
stdlib-only；接 preflight（CI 不起 Java，扫目录仍然有效）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PKG_ROOT.parent
SCAN_ROOTS = [REPO_ROOT, PKG_ROOT, REPO_ROOT / "vendor" / "runtime-source"]
SKIP_DIRS = {".git", ".venv", "node_modules", "build", "dist", "__pycache__", ".horosa-cache"}

# 目录名里出现这些片段 = 占位符没被展开
STRAY_MARKERS = ("${env:HOME", "${sys:user.home}", "${env:USERPROFILE", "${workspaceFolder", "${user_config", "${CLAUDE_P")
STRAY_DIR_NAMES = {".horosa-logs"}

LAUNCHER = PKG_ROOT / "scripts" / "start_vendored_instance.sh"
HELPER = PKG_ROOT / "scripts" / "extract_log4j_config.py"


def scan_for_stray_dirs() -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            name = path.name
            hit = any(marker in name for marker in STRAY_MARKERS)
            # `.horosa-logs` 直接落在仓里（而不是在 HOME 下）同样是跑偏了
            hit = hit or (name in STRAY_DIR_NAMES and path.is_dir())
            if hit:
                key = str(path)
                if key not in seen:
                    seen.add(key)
                    found.append(str(path.relative_to(REPO_ROOT)))
    return sorted(found)


def audit_dev_launcher() -> list[str]:
    """dev 启动器必须给未补丁的 jar 指一份改写过的 log4j 配置。"""
    problems: list[str] = []
    if not LAUNCHER.is_file():
        return [f"missing {LAUNCHER.relative_to(REPO_ROOT)}"]
    text = LAUNCHER.read_text(encoding="utf-8")
    if not HELPER.is_file():
        problems.append(f"missing {HELPER.relative_to(REPO_ROOT)} (the log4j rewrite helper)")
    if "log4j2.configurationFile" not in text:
        problems.append(
            "start_vendored_instance.sh must pass -Dlog4j2.configurationFile=<rewritten config>; "
            "without it the unpatched jar writes logs into a literal ${env:HOME…} directory in the CWD"
        )
    if re.search(r"-Dbasedir=", text):
        problems.append(
            "-Dbasedir= cannot override log4j's basedir here: <Property name=\"basedir\"> is already "
            "defined inside the config, and system properties only fill in undefined ones. "
            "Rewrite the config file instead."
        )
    # jar 必须带着改写过的配置起，而不是裸 -jar
    for match in re.finditer(r'nohup\s+"\$\{JAVA_BIN\}"(.*?)-jar', text, flags=re.DOTALL):
        if "LOG4J_OPT" not in match.group(1):
            problems.append("the java launch line does not carry ${LOG4J_OPT}")
    return problems


def main() -> int:
    stray = scan_for_stray_dirs()
    problems = audit_dev_launcher()
    if stray:
        problems.insert(0, "stray runtime log directories in the repo: " + ", ".join(stray[:8]))
    if problems:
        print("no-stray-runtime-dirs: FAIL")
        for item in problems:
            print(f"  - {item}")
        if stray:
            print("  fix: rm -r the directories above, then re-run the dev launcher (it is patched now)")
        return 1
    print("no-stray-runtime-dirs: ok (no literal-placeholder log dirs; dev launcher rewrites log4j)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
