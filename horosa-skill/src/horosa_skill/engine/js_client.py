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
from horosa_skill.errors import ToolTransportError
from horosa_skill.runtime import HorosaRuntimeManager

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
            raise ToolTransportError(
                "horosa-core-js CLI entry is missing.",
                code="js_engine.cli_missing",
                details={"path": str(cli_path)},
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
                    "error": error_obj or {},
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
        node_bin = self._resolve_node_binary()
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

    def _resolve_node_binary(self) -> Path:
        env_override = os.environ.get("HOROSA_NODE_BIN")
        if env_override:
            candidate = Path(env_override).expanduser().resolve()
            if candidate.is_file():
                return candidate

        manifest = self.runtime_manager.load_installed_manifest()
        if manifest and isinstance(manifest.get("runtimes"), dict):
            node_relative = manifest["runtimes"].get("node")
            if isinstance(node_relative, str) and node_relative.strip():
                candidate = self.settings.runtime_current_dir / node_relative
                if candidate.is_file():
                    return candidate

        return Path("node")

    def _resolve_engine_root(self) -> Path:
        return self._candidate_engine_roots()[0]

    def _candidate_engine_roots(self) -> list[Path]:
        candidates: list[Path] = []

        env_override = os.environ.get("HOROSA_CORE_JS_ROOT")
        if env_override:
            candidate = Path(env_override).expanduser().resolve()
            if candidate.is_dir():
                candidates.append(candidate)

        manifest = self.runtime_manager.load_installed_manifest()
        if manifest and isinstance(manifest.get("artifacts"), dict):
            relative = manifest["artifacts"].get("horosa_core_js_root")
            if isinstance(relative, str) and relative.strip():
                candidate = self.settings.runtime_current_dir / relative
                if candidate.is_dir():
                    candidates.append(candidate)

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
