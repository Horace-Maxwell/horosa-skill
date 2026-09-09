#!/usr/bin/env python3
"""MCPB bundle 的结构与内容契约。

两个**实际踩过**的坑决定了这把守卫的形状（v0.37.0 首次打包时各犯一次）：

1. **`.mcpbignore` 是 gitignore 语义，不带前导 `/` 的模式在任意层级匹配。**
   写 `vendor/` 的本意是排掉包根那棵 187 MB 的上游只读源树，实际会连
   `src/horosa_skill/**/vendor/` 一起排掉。包照样打得出来、装得上，然后走 vendored 代码的
   技法在用户机器上失效 —— 而 `mcpb validate` 只看 manifest schema，不看内容。

2. **排掉 `scripts/` 会让包在宿主机上构建失败。** pyproject 的 wheel `force-include` 把
   `scripts/runtime_templates/windows` 装进包；那个目录不在 bundle 里时，宿主执行
   `uv run --directory <bundle>` 在 hatchling 里直接报错。同样是「装得上、一跑就炸」。

所以除了 schema，这里断言 **bundle 里必须留下什么**（按 .mcpbignore 规则实算一遍）。
stdlib-only；有 npx 时顺带跑官方 validate。接 ci.yml。
"""
from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PKG_ROOT.parent
MANIFEST = PKG_ROOT / "manifest.json"
MCPBIGNORE = PKG_ROOT / ".mcpbignore"

# bundle 里必须存在的路径（相对包根）。每一条都对应一个「少了它就装得上、一跑就炸」的失败。
REQUIRED_IN_BUNDLE = [
    "pyproject.toml",                            # server.type=uv 靠它解析依赖，必须在 bundle 根
    "manifest.json",
    "src/horosa_skill/__init__.py",
    "src/horosa_skill/surfaces/mcp_server.py",   # server.entry_point
    "src/horosa_skill/surfaces/cli.py",
    "src/horosa_skill/knowledge/data",           # 知识库 JSON（wheel include 里逐条列着）
    "src/horosa_skill/data",
    "scripts/runtime_templates/windows",         # wheel force-include 的来源，缺它宿主构建失败
]


# 这些**本来就该**在任意层级匹配：编译产物与本机残留，哪一层出现都不该进包。
RECURSIVE_BY_DESIGN = frozenset({"__pycache__/", "*.egg-info/", "runs/", "*.pyc", ".coverage", "*.mcpb"})


def load_ignore_patterns() -> list[str]:
    if not MCPBIGNORE.is_file():
        return []
    out: list[str] = []
    for raw in MCPBIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """gitignore 风格判定（够用的子集：锚定 `/x`、任意层级 `x`、目录 `x/`、glob）。"""
    parts = rel_path.split("/")
    ignored = False
    for pattern in patterns:
        negate = pattern.startswith("!")
        body = pattern[1:] if negate else pattern
        anchored = body.startswith("/")
        body = body.lstrip("/")
        is_dir_pattern = body.endswith("/")
        body = body.rstrip("/")
        if anchored:
            hit = fnmatch.fnmatch(rel_path, body) or rel_path.startswith(body + "/")
        else:
            hit = any(fnmatch.fnmatch(part, body) for part in parts)
            if is_dir_pattern:
                hit = any(fnmatch.fnmatch(part, body) for part in parts[:-1]) or hit
        if hit:
            ignored = not negate
    return ignored


def bundle_content_errors() -> list[str]:
    patterns = load_ignore_patterns()
    problems: list[str] = []
    for required in REQUIRED_IN_BUNDLE:
        source = PKG_ROOT / required
        if not source.exists():
            problems.append(f"required bundle path does not exist in the source tree: {required}")
            continue
        if is_ignored(required, patterns):
            problems.append(
                f".mcpbignore excludes {required!r}, which the bundle needs at runtime "
                "(the package installs but fails on the user's machine)"
            )
    return problems


def manifest_errors() -> list[str]:
    problems: list[str] = []
    if not MANIFEST.is_file():
        return [f"missing {MANIFEST.relative_to(REPO_ROOT)}"]
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"manifest.json is not valid JSON: {exc}"]

    if not (MANIFEST.parent / "pyproject.toml").is_file():
        problems.append(
            "manifest.json must sit next to pyproject.toml — MCPB's `server.type: \"uv\"` runs "
            "`uv run --directory <bundle root>` and needs the project file there"
        )

    server = manifest.get("server") or {}
    config = server.get("mcp_config") or {}
    args = [str(a) for a in (config.get("args") or [])]
    if server.get("type") != "uv":
        problems.append(f"server.type must be 'uv', got {server.get('type')!r}")
    entry = str(server.get("entry_point") or "")
    if not entry or not (MANIFEST.parent / entry).is_file():
        problems.append(f"server.entry_point does not exist: {entry!r}")
    elif "if __name__" not in (MANIFEST.parent / entry).read_text(encoding="utf-8"):
        problems.append(f'{entry} has no `if __name__ == "__main__"` — entry_point must be runnable')
    if "${__dirname}" not in args:
        problems.append("mcp_config.args must pass ${__dirname} as --directory (the bundle root)")
    for token in ("${__dirname}/horosa-skill", "${__dirname}/src"):
        if token in args:
            problems.append(f"stale bundle-relative path in args: {token}")
    if "--transport" not in args or "stdio" not in args:
        problems.append("mcp_config.args must include --transport stdio")

    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    if match and manifest.get("version") != match.group(1):
        problems.append(f"manifest version {manifest.get('version')!r} != package version {match.group(1)!r}")

    declared = set((manifest.get("user_config") or {}).keys())
    blob = json.dumps(config, ensure_ascii=False)
    used = set(re.findall(r"\$\{user_config\.([A-Za-z0-9_]+)\}", blob))
    for name in sorted(used - declared):
        problems.append(f"mcp_config references undeclared user_config.{name}")
    for name in sorted(declared - used):
        problems.append(f"user_config.{name} is declared but never used by mcp_config")
    return problems


def unanchored_pattern_errors() -> list[str]:
    problems: list[str] = []
    if not MCPBIGNORE.is_file():
        return ["missing .mcpbignore — the bundle would carry vendor/ (187 MB) and build/"]
    for pattern in load_ignore_patterns():
        if pattern in RECURSIVE_BY_DESIGN:
            continue
        if pattern.endswith("/") and not pattern.startswith(("/", "!")):
            problems.append(
                f".mcpbignore pattern {pattern!r} is unanchored: it also matches nested directories "
                f"(e.g. src/horosa_skill/**/{pattern}). Write it as /{pattern} to anchor at the bundle root."
            )
    return problems


def validate_with_npx() -> list[str]:
    if not shutil.which("npx"):
        return []
    try:
        result = subprocess.run(
            ["npx", "-y", "@anthropic-ai/mcpb@2", "validate", str(MANIFEST)],
            capture_output=True, text=True, timeout=180, cwd=str(PKG_ROOT), check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"mcpb-manifest: skipping npx validate ({type(exc).__name__}: {exc})")
        return []
    if result.returncode != 0:
        return [f"`mcpb validate` failed:\n{(result.stdout + result.stderr).strip()[:2000]}"]
    return []


def main() -> int:
    problems = manifest_errors() + unanchored_pattern_errors() + bundle_content_errors()
    if not problems:
        problems = validate_with_npx()
    if problems:
        print("mcpb-manifest: FAIL")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"mcpb-manifest: ok (schema + {len(REQUIRED_IN_BUNDLE)} required bundle paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
