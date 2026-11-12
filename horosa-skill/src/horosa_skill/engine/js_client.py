from __future__ import annotations

import contextlib
import contextvars
import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from horosa_skill.config import Settings
from horosa_skill.engine import node_runtime
from horosa_skill.errors import ToolTransportError, bilingual
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.runtime import engine_asset

# 一次已知要算很久的调用（择时区间扫描，成本随窗口线性涨）把墙钟抬到「至少 N 秒」。走 ContextVar 而不是给 run() 加参数：
# 测试里十几个替身按 run(tool_name, payload) 实现，签名一变全要跟着改。只抬不降——配置的 HOROSA_JS_ENGINE_TIMEOUT_SECONDS 更大时照用配置。
_MIN_TIMEOUT_SECONDS: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "horosa_js_engine_min_timeout", default=None
)


@contextlib.contextmanager
def engine_timeout_at_least(seconds: float) -> Iterator[None]:
    token = _MIN_TIMEOUT_SECONDS.set(seconds)
    try:
        yield
    finally:
        _MIN_TIMEOUT_SECONDS.reset(token)


class HorosaJsEngineClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_manager = HorosaRuntimeManager(settings)

    def run(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        node_bin = self._resolve_node_binary()
        self._require_node_new_enough(node_bin)
        errors: list[dict[str, Any]] = []
        for engine_root in self._candidate_engine_roots():
            try:
                return self._run_with_engine_root(node_bin=node_bin, engine_root=engine_root, tool_name=tool_name, payload=payload)
            except ToolTransportError as exc:
                errors.append({"code": exc.code, "message": str(exc), "details": exc.details})
                error_obj = exc.details.get("error")
                message = error_obj.get("message") if isinstance(error_obj, dict) else ""
                if "Unsupported horosa-core-js tool" not in str(message):
                    raise
        raise ToolTransportError(
            "horosa-core-js execution failed.",
            code="js_engine.execution_failed",
            details={"tool": tool_name, "attempts": errors},
        )

    def _run_with_engine_root(
        self,
        *,
        node_bin: Path,
        engine_root: Path,
        tool_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        cli_path = engine_root / "bin" / "cli.mjs"
        if not cli_path.is_file():
            command = engine_asset.engine_only_command()
            raise ToolTransportError(
                bilingual(
                    "找不到本地 JS 引擎（horosa-core-js）。八字 / 紫微 / 奇门 / 太乙 / 金口诀 / 六壬 / 河洛 / 参评 等技法要用它："
                    f"运行 `{command}`（任何平台，约 7 MB，另需 Node.js ≥ 20.10），或装离线 runtime（自带引擎与 node），"
                    "或设 HOROSA_CORE_JS_ROOT 指向一份 horosa-core-js 目录。",
                    "The local JS engine (horosa-core-js) is missing. BaZi / Ziwei / Qimen / Taiyi / Jinkou / Liuren / Heluo / Canping "
                    f"and others need it: run `{command}` (any OS, about 7 MB; needs Node.js >= 20.10), install the offline runtime "
                    "(it ships the engine and node), or set HOROSA_CORE_JS_ROOT to a horosa-core-js directory.",
                ),
                code="js_engine.cli_missing",
                details={"path": str(cli_path), "searched": self.engine_root_report(), "commands": [command]},
            )

        timeout_seconds = max(self.settings.js_engine_timeout_seconds, _MIN_TIMEOUT_SECONDS.get() or 0.0)
        try:
            completed = subprocess.run(
                [str(node_bin), str(cli_path), "run", tool_name],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=str(engine_root),
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolTransportError(
                "本地 JS 引擎执行超时（horosa-core-js timed out）。",
                code="js_engine.timeout",
                details={
                    "tool": tool_name,
                    "timeout_seconds": timeout_seconds,
                    "node_bin": str(node_bin),
                },
            ) from exc
        except OSError as exc:
            # FileNotFoundError (Node not installed / unresolved), PermissionError, etc. — keep the
            # "every failure is a ToolTransportError" contract so the surface returns a clean error.
            raise ToolTransportError(
                "本地 JS 引擎无法启动：未找到可执行的 Node（可装离线 runtime 自带 node，或设 HOROSA_NODE_BIN）。",
                code="js_engine.node_unavailable",
                details={"tool": tool_name, "node_bin": str(node_bin), "error": str(exc)},
            ) from exc
        stderr_line = node_runtime.stderr_summary(completed.stderr)
        if completed.returncode != 0 and not (completed.stdout or "").strip():
            # 🔴 进程死在输出任何 JSON 之前（加载期 SyntaxError、模块缺失、被杀）：旧实现把空 stdout 当 `{}` 解析，
            # 报出来的是 `error: {}`，原因只躺在 debug.stderr 里（C-19）。这里把 stderr 最能说明问题的那行提到 error 上。
            raise ToolTransportError(
                bilingual(
                    f"本地 JS 引擎没能运行（退出码 {completed.returncode}）：{stderr_line or '没有任何输出'}",
                    f"The local JS engine did not run (exit code {completed.returncode}): {stderr_line or 'no output at all'}",
                ),
                code="js_engine.execution_failed",
                details={
                    "tool": tool_name,
                    "returncode": completed.returncode,
                    "error": {"message": stderr_line or "", "stage": "startup"},
                    "node_bin": str(node_bin),
                    "debug": {"stdout": "", "stderr": (completed.stderr or "")[-500:]},
                },
            )
        try:
            parsed = json.loads(completed.stdout or "{}")
        except ValueError as exc:
            raise ToolTransportError(
                "本地 JS 引擎返回了无效 JSON。",
                code="js_engine.invalid_json",
                details={
                    "tool": tool_name,
                    # 原始输出属调试信息：降级进 debug 并短截断，避免大段堆栈直冲 agent 上下文。
                    "debug": {
                        "stdout": (completed.stdout or "")[-500:],
                        "stderr": (completed.stderr or "")[-500:],
                    },
                },
            ) from exc
        # 形状闸必须先于 .get("ok")：stdout 是 JSON 数组/标量时旧序会抛 AttributeError，破坏「失败一律 ToolTransportError」契约。
        if not isinstance(parsed, dict):
            raise ToolTransportError(
                "horosa-core-js returned an invalid result shape.",
                code="js_engine.invalid_shape",
                details={"tool": tool_name},
            )

        if completed.returncode != 0 or parsed.get("ok") is not True:
            error_obj = parsed.get("error")
            raise ToolTransportError(
                "本地 JS 引擎执行失败。",
                code="js_engine.execution_failed",
                details={
                    "tool": tool_name,
                    "returncode": completed.returncode,
                    "error": error_obj or ({"message": stderr_line} if stderr_line else {}),
                    # 原始输出属调试信息：降级进 debug 并短截断。
                    "debug": {
                        "stdout": (completed.stdout or "")[-500:],
                        "stderr": (completed.stderr or "")[-500:],
                    },
                },
            )

        parsed.pop("ok", None)
        return parsed

    def render_app_charts(self, figures: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Draw report figures with the 星阙 app's own chart code (`horosa-core-js/dist/app-charts.cjs`).

        `figures` = [{kind, data, options}]; returns one {ok, svg, width, height} / {ok: False, error} per figure, or None when
        no engine root carries the bundle (an older installed runtime) or Node cannot run — the caller then keeps its own
        drawing. Never raises: a report must not fail because the nicer picture is unavailable.
        """
        if not figures:
            return []
        roots = [root for root in self._candidate_engine_roots() if (root / "dist" / "app-charts.cjs").is_file()]
        if not roots:
            return None
        try:
            node_bin = self._resolve_node_binary()
            self._require_node_new_enough(node_bin)
        except ToolTransportError:
            return None  # 探针：None 就是答案（没有能用的 node → 调用方保留自己画的图；原因由 doctor 的 js_engine 节报）
        try:
            completed = subprocess.run(
                [str(node_bin), str(roots[0] / "bin" / "cli.mjs"), "render-charts"],
                input=json.dumps({"figures": figures}, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=str(roots[0]),
                timeout=self.settings.js_engine_timeout_seconds,
            )
            parsed = json.loads(completed.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return None
        results = parsed.get("results") if isinstance(parsed, dict) and parsed.get("ok") else None
        if not isinstance(results, list) or len(results) != len(figures):
            return None
        return [result if isinstance(result, dict) else {"ok": False, "error": "malformed"} for result in results]

    def node_choice(self) -> node_runtime.NodeChoice:
        """这次调用会用哪个 Node（含来源、版本、问题）。doctor 读的也是它。"""
        return node_runtime.resolve_node(self.settings, self._installed_manifest())

    def _resolve_node_binary(self) -> Path:
        choice = self.node_choice()
        if choice.problem == "node_bin_missing":
            raise ToolTransportError(
                bilingual(
                    f"HOROSA_NODE_BIN 指向的 {choice.path} 不存在。改成一个真实存在的 node 可执行文件，或删掉这个变量"
                    "（删掉后用离线 runtime 自带的 node，再没有就用 PATH 上的 node）。",
                    f"HOROSA_NODE_BIN points at {choice.path}, which does not exist. Point it at a real node executable or "
                    "unset it (then the offline runtime's bundled node is used, else node on PATH).",
                ),
                code="js_engine.node_bin_missing",
                details={"variable": "HOROSA_NODE_BIN", "path": str(choice.path)},
            )
        return choice.path

    def _require_node_new_enough(self, node_bin: Path) -> None:
        version = node_runtime.probe_version(node_bin)
        if not node_runtime.version_is_too_old(version):
            return
        raise ToolTransportError(
            bilingual(
                f"本地 JS 引擎要 Node {node_runtime.NODE_FLOOR_TEXT}，找到的是 {version}（{node_bin}）。装离线 runtime"
                "（自带合适版本的 node），或把 HOROSA_NODE_BIN 指向一个够新的 node。",
                f"The local JS engine needs Node {node_runtime.NODE_FLOOR_TEXT}, found {version} ({node_bin}). Install the "
                "offline runtime (it ships a suitable node), or point HOROSA_NODE_BIN at a newer node.",
            ),
            code="js_engine.node_too_old",
            details={"node_bin": str(node_bin), "found": version, "required": node_runtime.NODE_FLOOR_TEXT},
        )

    def _installed_manifest(self) -> dict[str, Any] | None:
        return node_runtime.installed_manifest(self.runtime_manager)

    def engine_root_report(self) -> list[dict[str, Any]]:
        """引擎目录的三个来源各自在不在（cli_missing 的 details 与 doctor 用）。"""
        manifest = self._installed_manifest()
        relative = (manifest or {}).get("artifacts", {}).get("horosa_core_js_root") if isinstance((manifest or {}).get("artifacts"), dict) else None
        rows: list[dict[str, Any]] = []
        env_override = os.environ.get("HOROSA_CORE_JS_ROOT")
        rows.append({"source": "env:HOROSA_CORE_JS_ROOT", "path": env_override or None,
                     "present": bool(env_override) and (Path(env_override).expanduser() / "bin" / "cli.mjs").is_file()})
        runtime_root = self.settings.runtime_current_dir / relative if isinstance(relative, str) and relative.strip() else None
        rows.append({"source": "runtime", "path": str(runtime_root) if runtime_root else None,
                     "present": bool(runtime_root) and (runtime_root / "bin" / "cli.mjs").is_file()})
        asset_root = engine_asset.engine_dir(self.settings.runtime_root) / engine_asset.ENGINE_ASSET_ROOT
        rows.append({"source": "engine_asset", "path": str(asset_root),
                     "present": engine_asset.installed_engine_root(self.settings.runtime_root) is not None})
        source_root = Path(__file__).resolve().parents[3] / "horosa-core-js"
        rows.append({"source": "source_checkout", "path": str(source_root), "present": (source_root / "bin" / "cli.mjs").is_file()})
        return rows

    def diagnose(self) -> dict[str, Any]:
        """doctor 的 JS 引擎一节：在不在、为什么、怎么修（E-02 / E-11）。只读：会 spawn 一次 `node --version`（有缓存），不跑技法。"""
        searched = self.engine_root_report()
        engine_root = next((root for root in self._candidate_engine_roots() if (root / "bin" / "cli.mjs").is_file()), None)
        source = None
        if engine_root is not None:
            resolved = str(engine_root.resolve())
            source = next((row["source"] for row in searched if row.get("path") and str(Path(row["path"]).expanduser().resolve()) == resolved), "other")
        node = self.node_choice().as_dict()
        if engine_root is None:
            state = "absent"
        elif node["problem"] == "node_bin_missing":
            state = "node_bin_missing"
        elif node["problem"] == "not_found":
            state = "node_missing"
        elif node["problem"] == "too_old":
            state = "node_too_old"
        else:
            state = "ready"
        command = engine_asset.engine_only_command()
        fixes = {
            "ready": None,
            "absent": bilingual(
                f"运行 `{command}`（任何平台，只装 JS 引擎，约 7 MB；还要 node ≥ 20.10），或装离线 runtime（自带引擎与 node），"
                "或设 HOROSA_CORE_JS_ROOT 指向一份 horosa-core-js 目录。",
                f"Run `{command}` (any OS, the JS engine only, about 7 MB; node >= 20.10 is needed too), install the offline "
                "runtime (it ships the engine and node), or set HOROSA_CORE_JS_ROOT to a horosa-core-js directory.",
            ),
            "node_bin_missing": bilingual(
                f"HOROSA_NODE_BIN 指向的 {node['path']} 不存在：改成真实的 node，或删掉这个变量。",
                f"HOROSA_NODE_BIN points at {node['path']}, which does not exist: point it at a real node or unset it.",
            ),
            "node_missing": bilingual(
                "找不到 node：装 Node.js ≥ 20.10（nodejs.org 的 LTS / 系统包管理器 / nvm）让 `node` 进 PATH，或设 HOROSA_NODE_BIN，"
                "或装离线 runtime（自带 node；只有 darwin-arm64 / win32-x64 有）。",
                "No node found: install Node.js >= 20.10 (an LTS from nodejs.org, your package manager or nvm) so `node` is on "
                "PATH, set HOROSA_NODE_BIN, or install the offline runtime (it ships node; darwin-arm64 / win32-x64 only).",
            ),
            "node_too_old": bilingual(
                f"node {node['version']} 太旧（要 {node['required']}）：装离线 runtime，或把 HOROSA_NODE_BIN 指向更新的 node。",
                f"node {node['version']} is too old (needs {node['required']}): install the offline runtime, or point "
                "HOROSA_NODE_BIN at a newer node.",
            ),
        }
        return {
            "state": state,
            "ok": state == "ready",
            "engine_root": str(engine_root) if engine_root else None,
            "engine_source": source,
            "searched": searched,
            "engine_asset": self.runtime_manager.engine_asset_status(),
            "node": node,
            "affects": bilingual(
                "八字、紫微、奇门、太乙、金口诀、六壬、河洛、参评、六爻等本地 JS 技法，以及地名检索",
                "BaZi, Ziwei, Qimen, Taiyi, Jinkou, Liuren, Heluo, Canping, Liuyao and the other local-JS techniques, plus place search",
            ),
            "fix": fixes[state],
        }

    def _resolve_engine_root(self) -> Path:
        return self._candidate_engine_roots()[0]

    def _candidate_engine_roots(self) -> list[Path]:
        candidates: list[Path] = []

        env_override = os.environ.get("HOROSA_CORE_JS_ROOT")
        if env_override:
            candidate = Path(env_override).expanduser().resolve()
            if candidate.is_dir():
                candidates.append(candidate)

        manifest = self._installed_manifest()
        if manifest and isinstance(manifest.get("artifacts"), dict):
            relative = manifest["artifacts"].get("horosa_core_js_root")
            if isinstance(relative, str) and relative.strip():
                candidate = self.settings.runtime_current_dir / relative
                if candidate.is_dir():
                    candidates.append(candidate)

        # v0.50.0-dev E-02：engine-only 的 JS 引擎资产（`install --engine-only`，或没有 runtime 归档的平台上 `install` 自动装的）。
        asset_root = engine_asset.installed_engine_root(self.settings.runtime_root)
        if asset_root is not None:
            candidates.append(asset_root)

        source_candidate = Path(__file__).resolve().parents[3] / "horosa-core-js"
        if source_candidate.is_dir():
            candidates.append(source_candidate)

        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique or [source_candidate]
