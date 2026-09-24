"""旗标 → 策略（唯一读环境变量的地方）。

`HOROSA_JEV`            off | shadow | enforce（缺省 off = 零字节变化）
`HOROSA_JEV_API_KEY`    TypeSafe key（回退 `TYPESAFE_API_KEY`）；调用时读，永不入日志/信封/生成配置
`HOROSA_JEV_SCOPE`      meta | snapshot（一档只发脱敏问题文本；二档才允许导出快照文本，S4/S5 需要）
`HOROSA_JEV_SURFACES`   逗号列表，缺省 dispatch,extract,zhancat
`HOROSA_JEV_MODEL`      缺省钉版 jev-1.13.0（`jev-latest` 会漂，只允许在 shadow 下用）
`HOROSA_JEV_BASE_URL`   缺省 https://api.typesafe.ai（非 https 直接判无效）
`HOROSA_JEV_TIMEOUT_MS` 单次 HTTP 超时，缺省 3000
`HOROSA_JEV_LEDGER`     1/0，缺省 1（本地 jsonl 账本）

配置不合法不是「尽量跑」而是**整体关闭 + 问题进 doctor**：错一个字母就把用户文本发到别处，比不发糟得多。
`enforce` 另需 `contracts/jev_thresholds.json` 里该面已晋升（`promoted: true`）且模型 id 一致；否则该面
退到 shadow——阈值只认在自家标注集上测出来的数（AGENTS §4 决策层法则）。
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from horosa_skill.contracts_locator import contract_path
from typing import Any

MODES = ("off", "shadow", "enforce")
SCOPES = ("meta", "snapshot")
KNOWN_SURFACES = ("dispatch", "extract", "zhancat", "faithfulness", "hecan", "memory")
DEFAULT_SURFACES = ("dispatch", "extract", "zhancat")
SNAPSHOT_SURFACES = frozenset({"faithfulness", "hecan"})
DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_TIMEOUT_MS = 3000
# 影子期起点，不是结论：晋升后以 contracts/jev_thresholds.json 为准。
SURFACE_TAU_DEFAULTS: dict[str, float] = {
    "dispatch": 0.70,
    "extract": 0.90,
    "zhancat": 0.70,
    "faithfulness": 0.70,
    "hecan": 0.70,
    "memory": 0.70,
}
THRESHOLDS_PATH = contract_path("jev_thresholds.json")  # 源码树 / wheel 内副本（contracts_locator，v0.40.0 P1）
KEY_ENV = "HOROSA_JEV_API_KEY"
KEY_ENV_FALLBACK = "TYPESAFE_API_KEY"


@dataclass(frozen=True)
class Policy:
    mode: str
    scope: str
    surfaces: frozenset[str]
    model: str
    base_url: str
    timeout_s: float
    ledger: bool
    key_present: bool
    requested_mode: str
    problems: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    def surface_enabled(self, surface: str) -> bool:
        if not self.enabled or surface not in self.surfaces:
            return False
        if surface in SNAPSHOT_SURFACES and self.scope != "snapshot":
            return False
        return True

    def doctor_view(self, thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """doctor / status 用：绝不含 key 的值。"""
        lock = thresholds if isinstance(thresholds, Mapping) else None
        promoted = sorted(
            name for name, entry in ((lock or {}).get("surfaces") or {}).items()
            if isinstance(entry, Mapping) and entry.get("promoted") is True
        )
        return {
            "provider": "typesafe_jev",
            "mode": self.mode,
            "requested_mode": self.requested_mode,
            "scope": self.scope,
            "surfaces": sorted(self.surfaces),
            "model": self.model,
            "base_url": self.base_url,
            "timeout_ms": int(self.timeout_s * 1000),
            "ledger": self.ledger,
            "key_present": self.key_present,
            "thresholds_lock": {
                "present": lock is not None,
                "model": (lock or {}).get("model"),
                "promoted_surfaces": promoted,
            },
            "problems": list(self.problems),
            "data_leaves_machine": self.enabled,
        }


def read_api_key(env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    for name in (KEY_ENV, KEY_ENV_FALLBACK):
        value = source.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _lower(value: str | None, default: str) -> str:
    text = (value or "").strip().lower()
    return text or default


def load_policy(env: Mapping[str, str] | None = None) -> Policy:
    source = os.environ if env is None else env
    problems: list[str] = []
    requested = _lower(source.get("HOROSA_JEV"), "off")
    mode = requested
    if mode not in MODES:
        problems.append(f"HOROSA_JEV={requested!r} is not one of {'/'.join(MODES)}; decision layer kept OFF")
        mode = "off"
    scope = _lower(source.get("HOROSA_JEV_SCOPE"), "meta")
    if scope not in SCOPES:
        problems.append(f"HOROSA_JEV_SCOPE={scope!r} is not one of {'/'.join(SCOPES)}; decision layer kept OFF")
        scope = "meta"
        mode = "off"
    raw_surfaces = source.get("HOROSA_JEV_SURFACES")
    if raw_surfaces is None or not raw_surfaces.strip():
        surfaces = set(DEFAULT_SURFACES)
    else:
        surfaces = {part.strip().lower() for part in raw_surfaces.split(",") if part.strip()}
        unknown = sorted(surfaces - set(KNOWN_SURFACES))
        if unknown:
            problems.append(f"HOROSA_JEV_SURFACES has unknown surface(s) {unknown}; decision layer kept OFF")
            mode = "off"
        surfaces &= set(KNOWN_SURFACES)
    model = (source.get("HOROSA_JEV_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if model == "jev-latest" and mode == "enforce":
        problems.append("HOROSA_JEV_MODEL=jev-latest cannot be enforced (alias drifts); running as shadow")
        mode = "shadow"
    base_url = (source.get("HOROSA_JEV_BASE_URL") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    try:
        from horosa_skill.decisions.jev_http import validate_base_url

        base_url = validate_base_url(base_url)
    except Exception as exc:  # noqa: BLE001 - 配置错误整体关闭并进 doctor
        problems.append(f"{exc}; decision layer kept OFF")
        mode = "off"
    raw_timeout = (source.get("HOROSA_JEV_TIMEOUT_MS") or "").strip()
    timeout_ms = DEFAULT_TIMEOUT_MS
    if raw_timeout:
        try:
            timeout_ms = max(200, min(30000, int(raw_timeout)))
        except ValueError:
            problems.append(f"HOROSA_JEV_TIMEOUT_MS={raw_timeout!r} is not an integer; using {DEFAULT_TIMEOUT_MS}")
    ledger = _lower(source.get("HOROSA_JEV_LEDGER"), "1") not in {"0", "false", "no", "off"}
    key_present = read_api_key(source) is not None
    if mode != "off" and not key_present:
        problems.append("HOROSA_JEV is on but no API key is set (HOROSA_JEV_API_KEY / TYPESAFE_API_KEY); decision layer kept OFF")
        mode = "off"
    return Policy(
        mode=mode,
        scope=scope,
        surfaces=frozenset(surfaces),
        model=model,
        base_url=base_url,
        timeout_s=timeout_ms / 1000.0,
        ledger=ledger,
        key_present=key_present,
        requested_mode=requested,
        problems=tuple(problems),
    )


def load_thresholds(path: Path | None = None) -> dict[str, Any] | None:
    target = Path(path) if path is not None else THRESHOLDS_PATH
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def resolve_tau(surface: str, thresholds: Mapping[str, Any] | None) -> tuple[float, str]:
    """(τ, 来源)。晋升锁里的数优先；否则影子期缺省。"""
    entry = ((thresholds or {}).get("surfaces") or {}).get(surface)
    if isinstance(entry, Mapping):
        try:
            return float(entry["tau"]), "thresholds_lock"
        except (KeyError, TypeError, ValueError):
            pass
    return SURFACE_TAU_DEFAULTS.get(surface, 0.7), "shadow_default"


def enforce_allowed(policy: Policy, surface: str, thresholds: Mapping[str, Any] | None) -> tuple[bool, str]:
    """`enforce` 生效条件：锁在、模型一致、该面 promoted。否则退 shadow 并说明为什么。"""
    if policy.mode != "enforce":
        return False, f"mode={policy.mode}"
    if not thresholds:
        return False, "no thresholds lock (contracts/jev_thresholds.json)"
    if thresholds.get("model") != policy.model:
        return False, f"thresholds lock is for model {thresholds.get('model')!r}, running {policy.model!r}"
    entry = (thresholds.get("surfaces") or {}).get(surface)
    if not isinstance(entry, Mapping) or entry.get("promoted") is not True:
        return False, f"surface {surface!r} not promoted in thresholds lock"
    return True, "promoted"
