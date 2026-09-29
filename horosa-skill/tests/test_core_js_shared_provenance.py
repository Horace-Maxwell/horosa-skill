"""`horosa-core-js/src/shared/` 只许放上游没有对应物的 skill 自写件（v0.40.0 复审第七例）。

`src/shared/localNongliAdapter.js` 是 v0.9（e75ce07）的自写近似公式，与上游 `utils/localNongliAdapter.js` 同名同职能却不在 manifest 里——
manifest 全集守卫只看 vendor 树，revendor 的路径推断还把上游 import 「relocate」到它身上，于是 2026 立春差 6 小时的种子躲了 4 个月。
规则：shared 里每个文件都要在 allowlist 里写明「为什么上游没有」，且 basename 不得与 manifest 里任何上游文件相同。
负向对照：把 `localNongliAdapter.js` 放回 shared → 与 manifest 的 `utils/localNongliAdapter.js` 同名 → 红。
"""
from __future__ import annotations

import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SHARED = PKG_ROOT / "horosa-core-js" / "src" / "shared"
MANIFEST = PKG_ROOT / "contracts" / "vendor_manifest.json"

# basename → 为什么它是自写件而不是 vendor（上游没有同职能文件）
ALLOWLIST: dict[str, str] = {
    "fields.js": "skill 自写：JS 工具入参归一（日期 / 时间串校验、fields 对象构造）——上游对应逻辑散在各 React 输入组件里，无独立纯函数模块",
    "unpack.js": "skill 自写：Result / ResultKey 信封拆包（unwrapResultEnvelope 等）——上游散落在各 request 调用点，无独立模块",
}


def _manifest_upstream_basenames() -> set[str]:
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    return {Path(v["upstream"]).name for v in files.values() if v.get("upstream")}


def shared_violations(shared_names: list[str], upstream_basenames: set[str], allowlist: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name in sorted(shared_names):
        if name not in allowlist:
            problems.append(f"{name}: not in ALLOWLIST — either vendor the upstream file or write down why upstream has no counterpart")
        if name in upstream_basenames:
            problems.append(f"{name}: an upstream file with this basename is in the vendor manifest — a hand-written twin here will shadow it")
    return problems


def test_shared_dir_holds_only_allowlisted_skill_authored_modules() -> None:
    names = [p.name for p in SHARED.glob("*.js")]
    assert names, "src/shared vanished?"
    assert shared_violations(names, _manifest_upstream_basenames(), ALLOWLIST) == []


def test_guard_catches_a_hand_written_twin_of_a_vendored_upstream_file() -> None:
    upstream = _manifest_upstream_basenames()
    assert "localNongliAdapter.js" in upstream, "the upstream jieqi-seed module must be vendored (v0.40.0)"
    problems = shared_violations(["localNongliAdapter.js", "unpack.js"], upstream, ALLOWLIST)
    assert any("localNongliAdapter.js" in p and "shadow" in p for p in problems), problems
    assert not any(p.startswith("unpack.js") for p in problems)
