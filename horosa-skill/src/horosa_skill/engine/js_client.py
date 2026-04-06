from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from horosa_skill.config import Settings
from horosa_skill.errors import ToolTransportError
from horosa_skill.runtime import HorosaRuntimeManager


class HorosaJsEngineClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_manager = HorosaRuntimeManager(settings)

    def run(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        node_bin = self._resolve_node_binary()
        engine_root = self._resolve_engine_root()
        cli_path = engine_root / "bin" / "cli.mjs"
        if not cli_path.is_file():
            raise ToolTransportError(
                "horosa-core-js CLI entry is missing.",
                code="js_engine.cli_missing",
                details={"path": str(cli_path)},
            )

        completed = subprocess.run(
            [str(node_bin), str(cli_path), "run", tool_name],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=str(engine_root),
            timeout=self.settings.js_engine_timeout_seconds,
        )
        try:
            parsed = json.loads(completed.stdout or "{}")
        except ValueError as exc:
            raise ToolTransportError(
                "horosa-core-js returned invalid JSON.",
                code="js_engine.invalid_json",
                details={
                    "tool": tool_name,
                    "stdout": (completed.stdout or "")[-2000:],
                    "stderr": (completed.stderr or "")[-2000:],
                },
            ) from exc

        if completed.returncode != 0 or parsed.get("ok") is not True:
            error_obj = parsed.get("error") if isinstance(parsed, dict) else None
            raise ToolTransportError(
                "horosa-core-js execution failed.",
                code="js_engine.execution_failed",
                details={
                    "tool": tool_name,
                    "returncode": completed.returncode,
                    "stdout": (completed.stdout or "")[-2000:],
                    "stderr": (completed.stderr or "")[-2000:],
                    "error": error_obj or {},
                },
            )

        if not isinstance(parsed, dict):
            raise ToolTransportError(
                "horosa-core-js returned an invalid result shape.",
                code="js_engine.invalid_shape",
                details={"tool": tool_name},
            )
        parsed.pop("ok", None)
        return parsed

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
        env_override = os.environ.get("HOROSA_CORE_JS_ROOT")
        if env_override:
            candidate = Path(env_override).expanduser().resolve()
            if candidate.is_dir():
                return candidate

        manifest = self.runtime_manager.load_installed_manifest()
        if manifest and isinstance(manifest.get("artifacts"), dict):
            relative = manifest["artifacts"].get("horosa_core_js_root")
            if isinstance(relative, str) and relative.strip():
                candidate = self.settings.runtime_current_dir / relative
                if candidate.is_dir():
                    return candidate

        return Path(__file__).resolve().parents[3] / "horosa-core-js"
