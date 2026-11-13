"""JS 引擎用哪个 Node、哪个引擎目录：解析一次，带来源与版本，doctor 与每次调用同一个答案。

🔴 为什么（v0.50.0-dev，E-11 / C-19 / E-02）：
  · `HOROSA_NODE_BIN` 指向不存在的文件时旧实现**悄悄**回落到 runtime 自带 node / PATH 上的 node —— 用户以为在用
    自己指定的那个，排查时谁也想不到；现在是 `js_engine.node_bin_missing`，点名变量。
  · Node 低于 horosa-core-js 的下限（package.json `engines.node`，import attributes 要 ≥ 20.10）时，带 JSON import 的模块
    一加载就 SyntaxError（当时 `tools/index.js` 静态 import 全部模块，于是**所有** JS 技法）报 `js_engine.execution_failed`、`details.error = {}`，原因只在
    `details.debug.stderr` 里；现在先读版本，低了直接 `js_engine.node_too_old`（找到的 / 要求的 / 怎么修）。
  · doctor 只探 runtime 自带的 node，可真正被用的可能是 PATH 上的另一个；现在 doctor 报的就是这里解析出的那一个。

缓存：版本按（路径、mtime、大小）缓存 —— 每个进程每个二进制只 spawn 一次 `node --version`；已装清单按（路径、mtime、
大小）缓存 —— 此前每次 JS 调用读 3 遍、解析 3 遍（C-20）。换了 node / 重装了 runtime，键变了就重新读。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from horosa_skill.winproc import NO_WINDOW

# horosa-core-js/package.json 的 `engines.node`（tests/test_node_runtime.py 锁步：改了那边这里要跟）。
NODE_FLOOR: tuple[int, int, int] = (20, 10, 0)
NODE_FLOOR_TEXT = ">=20.10.0"
_VERSION_PROBE_TIMEOUT_SECONDS = 5.0
_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")

_lock = threading.Lock()
_version_cache: dict[tuple[str, int, int], str | None] = {}
_manifest_cache: dict[str, tuple[tuple[int, int], dict[str, Any] | None]] = {}


@dataclass(frozen=True)
class NodeChoice:
    path: Path
    source: str                 # env:HOROSA_NODE_BIN / runtime / PATH
    version: str | None         # `node --version` 的输出（v22.11.0）；None = 读不到
    problem: str | None         # None / node_bin_missing / not_found / too_old

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "source": self.source,
            "version": self.version,
            "required": NODE_FLOOR_TEXT,
            "ok": self.problem is None,
            "problem": self.problem,
        }


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    match = _VERSION_RE.search(text or "")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def version_is_too_old(version: str | None) -> bool:
    parsed = parse_version(version)
    return parsed is not None and parsed < NODE_FLOOR  # 读不到版本 = 不知道，不拦（让真正的调用去报它的错）


def probe_version(path: Path) -> str | None:
    """`node --version`，按文件身份缓存。任何失败都是 None —— 这只是诊断，不能自己变成故障。

    用 Popen 而不是 subprocess.run：测试替身常把 `subprocess.run` 整个换掉，版本探针不该吃到那些替身。
    """
    resolved = _which(path)
    if resolved is None:
        return None
    try:
        stat = resolved.stat()
    except OSError:
        return None
    key = (str(resolved), stat.st_mtime_ns, stat.st_size)
    with _lock:
        if key in _version_cache:
            return _version_cache[key]
    version: str | None = None
    try:
        with subprocess.Popen(
            [str(resolved), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        ) as proc:
            try:
                out, _err = proc.communicate(timeout=_VERSION_PROBE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                out = ""
            if proc.returncode == 0 and parse_version(out):
                version = out.strip().splitlines()[0][:40]
    except OSError:
        version = None
    with _lock:
        _version_cache[key] = version
    return version


def installed_manifest(manager: Any) -> dict[str, Any] | None:
    """已装 runtime 的清单，按（路径、mtime、大小）缓存：每次 JS 调用此前要读 3 遍、解析 3 遍（C-20）。"""
    manifest_path = Path(manager.current_dir) / "runtime-manifest.json"
    try:
        stat = manifest_path.stat()
    except OSError:
        return manager.load_installed_manifest()  # 没有清单文件：不缓存，交给 manager（它自己会答 None）
    stamp = (stat.st_mtime_ns, stat.st_size)
    key = str(manifest_path)
    with _lock:
        cached = _manifest_cache.get(key)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    manifest = manager.load_installed_manifest()
    with _lock:
        _manifest_cache[key] = (stamp, manifest)
    return manifest


def resolve_node(settings: Any, manifest: dict[str, Any] | None) -> NodeChoice:
    """HOROSA_NODE_BIN → 已装 runtime 自带 → PATH。设了 HOROSA_NODE_BIN 却找不到 = 问题，不往下回落。"""
    env_override = (os.environ.get("HOROSA_NODE_BIN") or "").strip()
    if env_override:
        candidate = Path(env_override).expanduser()
        if not candidate.is_file():
            return NodeChoice(candidate, "env:HOROSA_NODE_BIN", None, "node_bin_missing")
        return _with_version(candidate.resolve(), "env:HOROSA_NODE_BIN")
    if manifest and isinstance(manifest.get("runtimes"), dict):
        node_relative = manifest["runtimes"].get("node")
        if isinstance(node_relative, str) and node_relative.strip():
            candidate = Path(settings.runtime_current_dir) / node_relative
            if candidate.is_file():
                return _with_version(candidate, "runtime")
    on_path = shutil.which("node")
    if on_path is None:
        return NodeChoice(Path("node"), "PATH", None, "not_found")
    return _with_version(Path(on_path), "PATH")


def engine_floor_from_package(engine_root: Path) -> str | None:
    """引擎目录里 package.json 写的 `engines.node`（lock-step 测试与 doctor 用）。"""
    try:
        data = json.loads((engine_root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    engines = data.get("engines") if isinstance(data, dict) else None
    value = engines.get("node") if isinstance(engines, dict) else None
    return value if isinstance(value, str) else None


def stderr_summary(stderr: str | None) -> str | None:
    """失败时 stderr 里最能说明问题的一行：第一条 `XxxError: …`，没有就第一条非空行。"""
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    for line in lines:
        if re.match(r"^(?:[A-Za-z_$][\w$]*)?(?:Error|Exception)\b", line):
            return line[:300]
    return lines[0][:300] if lines else None


def _with_version(path: Path, source: str) -> NodeChoice:
    version = probe_version(path)
    return NodeChoice(path, source, version, "too_old" if version_is_too_old(version) else None)


def _which(path: Path) -> Path | None:
    if path.is_file():
        return path
    if path.parent == Path("."):
        found = shutil.which(str(path))
        return Path(found) if found else None
    return None


def clear_caches() -> None:
    with _lock:
        _version_cache.clear()
        _manifest_cache.clear()


__all__ = [
    "NODE_FLOOR", "NODE_FLOOR_TEXT", "NodeChoice", "clear_caches", "engine_floor_from_package", "installed_manifest",
    "parse_version", "probe_version", "resolve_node", "stderr_summary", "version_is_too_old",
]
