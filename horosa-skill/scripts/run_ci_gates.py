#!/usr/bin/env python3
"""Run the SAME gates ci.yml's `test` job runs, locally, before pushing (v0.38.0 lesson: main was red for 19
commits while every local run was "green" — the local ritual was pytest + docs-sync, not the ci.yml list).

Parses `.github/workflows/ci.yml`, takes every `run:` step of the `test` job that invokes `uv run …`
(pytest, verify_* scripts, build_knowledge_index --check, run_benchmark …), and executes it from
horosa-skill/ in CI shape (HOROSA_RUNTIME_ROOT → empty temp dir, both *_SERVER_ROOT unreachable).
Exit 0 only when every step passes. Runner-only steps (`HOME=$(mktemp -d) uvx …`, the wheel-build block) never start
with `uv run`, so `ci_test_steps` leaves them out by shape — no name list to keep in sync.

The test job also checks out the pinned public upstream and points HOROSA_SOURCE_ROOT at it; `ensure_upstream` does the
same here (shallow fetch into `.upstream/horosa-public`, reused while the pin is unchanged). `--no-upstream` skips that
(offline): the export-contract mirror then fails and the [upstream-checkout] tests skip, as they would without it.
"""

from __future__ import annotations

import json
import os
import re
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

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PROVENANCE = PKG_ROOT / "contracts" / "upstream_provenance.json"
# ci.yml 的 test job 把钉住的公开上游取到这里（.gitignore 已忽略 .upstream/）
UPSTREAM_DIR = REPO_ROOT / ".upstream" / "horosa-public"


def ci_test_steps(text: str) -> list[tuple[str, str]]:
    """[(step name, command)] for the `test` job: single-line `run: uv run …` steps, plus multi-line `run: |` blocks whose
    every line is a `uv run …` command (joined with &&). Blocks with any other line are runner glue (wheel build, temp
    dirs) and stay CI-only.

    🔴 2026-10 audit: the old parser skipped every `run: |` block, so `verify_runtime_scripts.py` (+ its --self-test) — a
    two-line step — never ran locally while the docs said the mirror runs every verify_* gate.
    """
    job = re.search(r"^  test:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", text, re.S | re.M)
    if not job:
        raise SystemExit("ci.yml: no `test` job")
    steps: list[tuple[str, str]] = []
    name = ""
    lines = job.group(1).splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- name:"):
            name = stripped[len("- name:"):].strip()
        elif stripped == "run: |":
            indent = len(line) - len(line.lstrip()) + 2
            block = []
            for follow in lines[index + 1:]:
                if follow.strip() and len(follow) - len(follow.lstrip()) < indent:
                    break
                if follow.strip():
                    block.append(follow.strip())
            if block and all(command.startswith("uv run") for command in block):
                steps.append((name, " && ".join(block)))
        elif stripped.startswith("run:"):
            command = stripped[len("run:"):].strip()
            if command.startswith("uv run"):
                steps.append((name, command))
    return steps


# Windows 的 Smart App Control 可能拒绝执行 uv 给新 venv 现生成的 `Scripts\pytest.exe`（trampoline 没有签名也没有云端信誉：
# `Failed to spawn: pytest … (os error 4551)`，同一台机器上时拦时放）。本机镜像在 Windows 上改走等价的模块入口——同一批测试、
# 同一组参数；ci_test_steps 仍原样返回 ci.yml 的命令（镜像的对照面不变）。
_CONSOLE_SCRIPT_MODULES = {"pytest": "pytest"}


def local_command(command: str, *, windows: bool | None = None) -> str:
    """ci.yml 的命令 → 本机实际执行的命令。非 Windows 原样；Windows 上 `uv run <console-script>` 换成 `uv run python -m <module>`。"""
    if not (os.name == "nt" if windows is None else windows):
        return command
    for script, module in _CONSOLE_SCRIPT_MODULES.items():
        prefix = f"uv run {script}"
        if command == prefix or command.startswith(prefix + " "):
            return f"uv run python -m {module}" + command[len(prefix):]
    return command


def ensure_upstream(env: dict[str, str], *, runner=subprocess.run) -> str | None:
    """镜像 ci.yml test job 的「读钉住的公开上游 → 浅取 → 设 HOROSA_SOURCE_ROOT」三步，返回要设的路径。

    v0.51.0 起 export-contract mirror 进了 CI，CI 读的是这份上游；本机没有 vendored 树也没设 HOROSA_SOURCE_ROOT 时，
    镜像那一步恒红、182 条 [upstream-checkout] 对照测试静默跳过（v0.53.1 Windows 复验）。调用方已设 HOROSA_SOURCE_ROOT
    就照用；`.upstream/horosa-public` 已在钉住的提交上就复用；取不到（离线）返回 None，那几步照旧按缺上游处理。
    """
    if env.get("HOROSA_SOURCE_ROOT"):
        return env["HOROSA_SOURCE_ROOT"]
    state = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    repo, sha = state["upstream_repository"], state["upstream_git_sha"]

    def head() -> str:
        # 只认 UPSTREAM_DIR 自己的 .git：目录还不是仓库时 `git -C` 会往上找到本仓
        if not (UPSTREAM_DIR / ".git").exists():
            return ""
        result = runner(["git", "-C", str(UPSTREAM_DIR), "rev-parse", "HEAD"], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    if head() != sha:
        print(f"ci-gates: 浅取钉住的公开上游 {repo}@{sha[:12]} → {UPSTREAM_DIR}（与 ci.yml 同一份）", flush=True)
        UPSTREAM_DIR.mkdir(parents=True, exist_ok=True)
        for command in (
            ["git", "init", "-q"],
            ["git", "-c", "core.longpaths=true", "fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git", sha],
            ["git", "-c", "core.longpaths=true", "checkout", "-q", "--force", "--detach", "FETCH_HEAD"],
        ):
            if runner(command, cwd=UPSTREAM_DIR).returncode != 0:
                break
    if head() != sha:
        print(f"ci-gates: ⚠ 取不到钉住的上游（{repo}@{sha[:12]}）：export-contract mirror 会红、[upstream-checkout] 测试会跳过。"
              "离线就设 HOROSA_SOURCE_ROOT 指向一份该提交的 checkout。", flush=True)
        return None
    return str(UPSTREAM_DIR)


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    no_upstream = "--no-upstream" in args
    only = {arg for arg in args if arg != "--no-upstream"}
    steps = ci_test_steps(CI.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="horosa-ci-shape-") as empty_root:
        env = {
            **os.environ,
            "HOROSA_RUNTIME_ROOT": empty_root,
            "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
            "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
        }
        source_root = None if no_upstream else ensure_upstream(env)
        if source_root:
            env["HOROSA_SOURCE_ROOT"] = source_root
        failed: list[str] = []
        for name, command in steps:
            if only and not any(token in command or token in name for token in only):
                continue
            actual = local_command(command)
            print(f"\n=== {name}\n$ {command}", flush=True)
            if actual != command:
                print(f"  (Windows: 实际执行 `{actual}`——同一批测试，绕开可能被应用控制拦下的 uv trampoline)", flush=True)
            result = subprocess.run(actual, shell=True, cwd=PKG_ROOT, env=env)
            if result.returncode != 0:
                failed.append(name)
                print(f"!!! FAILED: {name}", flush=True)
        print()
        if failed:
            print(f"ci-gates: {len(failed)} of {len(steps)} steps FAILED — {failed}")
            return 1
        print(f"ci-gates: all {len(steps)} ci.yml test-job gates green locally (same commands, CI shape)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
