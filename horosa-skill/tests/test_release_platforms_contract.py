"""contracts/release_platforms.json (v0.38.0 A1): the one place that says which payloads ship and what
other hosts do. A4 locks the installer's constants to it; release-completeness / sync_windows_release read it."""

from __future__ import annotations

import json
import re
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_shipped_platforms_are_the_two_we_publish() -> None:
    assert set(CONTRACT["platforms"]) == {"darwin-arm64", "win32-x64"}
    for key, entry in CONTRACT["platforms"].items():
        assert _SEMVER.match(entry["since"]), key
        assert "{version}" in entry["asset"] and entry["archive_type"] in {"tar.gz", "zip"}
        assert key in entry["asset"]


def test_aliases_point_at_a_shipped_platform_with_evidence() -> None:
    assert CONTRACT["aliases"]["win32-arm64"]["installs"] == "win32-x64"
    assert CONTRACT["aliases"]["win32-arm64"]["mode"] == "x64-emulation"
    assert "runner-probe" in CONTRACT["aliases"]["win32-arm64"]["evidence"]
    for alias, entry in CONTRACT["aliases"].items():
        assert entry["installs"] in CONTRACT["platforms"], alias


def test_unsupported_platforms_carry_a_reason_and_are_not_also_shipped() -> None:
    assert {"darwin-x64", "linux-x64"} <= set(CONTRACT["unsupported"])
    for key, reason in CONTRACT["unsupported"].items():
        assert key not in CONTRACT["platforms"] and key not in CONTRACT["aliases"]
        assert "gateway" in reason.lower()
