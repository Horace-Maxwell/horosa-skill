"""包内钉住的 runtime 摘要（审计 PF-01 第 3 层）：信任根随包走，镜像只送字节。

发布流水线在两个平台的归档都齐了之后（release-runtime.yml 的 assemble），从双平台清单生成
`horosa_skill/data/runtime_pins.json`，再用 tag 的源码重建 wheel 换掉草稿里的那份。所以：
- 从发布页 wheel 装的（uvx / pip）带钉值：清单（不论来自原站还是镜像）里本平台归档 / JS 引擎资产的 sha256 与 size
  必须与钉值一致，否则 `runtime.install_pin_mismatch`，一个字节都不装；
- 清单版本 ≠ 钉值版本（`--manifest-url` 指向别的版本）→ 要 `--sha256` 或显式 `--allow-unpinned`（`runtime.install_unpinned_version`）；
- 源码 checkout / 开发版没有这个文件 → 不钉（照旧按清单的摘要核，PF-01 第 1 层管清单来源）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PINS_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_pins.json"


def load(path: Path | None = None) -> dict[str, Any] | None:
    target = path or PINS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("version") else None


def pins_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """双平台清单 → 钉值（只取 sha256 / size / 文件名，不带 URL：URL 换镜像照样合法，字节不许换）。"""
    def entry(meta: Any) -> dict[str, Any] | None:
        if not isinstance(meta, dict) or not meta.get("sha256"):
            return None
        name = str(meta.get("url") or "").rsplit("/", 1)[-1] or None
        return {"sha256": str(meta["sha256"]).lower(), "size": meta.get("size"), "name": name}

    platforms = {key: pinned for key, meta in (manifest.get("platforms") or {}).items() if (pinned := entry(meta))}
    out: dict[str, Any] = {"version": str(manifest.get("version") or ""), "platforms": platforms}
    core = entry(manifest.get("core_js"))
    if core:
        out["core_js"] = core
    return out


def expected(pins: dict[str, Any] | None, manifest_version: Any, *, platform: str | None = None, core_js: bool = False) -> dict[str, Any] | None:
    """这次要装的东西的钉值；版本不同或没钉这一项 → None。"""
    if not pins or str(pins.get("version")) != str(manifest_version or ""):
        return None
    if core_js:
        return pins.get("core_js") if isinstance(pins.get("core_js"), dict) else None
    entry = (pins.get("platforms") or {}).get(platform or "")
    return entry if isinstance(entry, dict) else None
