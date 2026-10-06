#!/usr/bin/env python3
"""Bump the package version everywhere it is pinned — the 15-file checklist as code (v0.40.0 doc-currency institution).

`scripts/verify_docs_sync.py` (check_versions / check_pinned_install_commands / check_root_manifest_version) is the JUDGE that
every site agrees; this script is the HAND that performs the bump so the file list lives in exactly one place instead of in
each maintainer's memory. History lines ("as of v0.39.0", "v0.39.0 起", "Since v0.39.0") are deliberately left alone.

    python scripts/bump_version.py 0.41.0            # rewrite every site from the current version to 0.41.0
    python scripts/bump_version.py --check           # exit 1 when any site disagrees with pyproject (no writes)

After a bump: `uv lock` (refreshes uv.lock's own version line), `npm --prefix horosa-core-js install --package-lock-only`
is NOT needed (package-lock.json is rewritten here), then `python scripts/verify_docs_sync.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "horosa-skill"

# Every file that carries the package version. Keep in lockstep with verify_docs_sync.check_versions.
SITES: tuple[str, ...] = (
    "horosa-skill/pyproject.toml",
    "horosa-skill/src/horosa_skill/__init__.py",
    "horosa-skill/uv.lock",
    "horosa-skill/manifest.json",
    "horosa-skill/horosa-core-js/package.json",
    "horosa-skill/horosa-core-js/package-lock.json",
    "horosa-skill/contracts/upstream_provenance.json",
    "server.json",
    "CITATION.cff",
    ".claude-plugin/plugin.json",
    "README.md",
    "README_EN.md",
    "skills/horosa-agent/SKILL.md",
    "docs/INSTALL_RESTRICTED_NETWORK.md",
    "docs/runtime-manifest.example.json",
    "docs/runtime-payload-manifest.example.json",
)
# Lines that mention an OLD version as history and must not be rewritten.
HISTORY_MARKERS = ("as of v", " 起", "Since v", "自 v", "v0.27.0–")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def current_version() -> str:
    m = re.search(r'^version = "([^"]+)"', (PKG / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert m, "pyproject.toml: version line not found"
    return m.group(1)


def _is_history(line: str, old: str) -> bool:
    return any(marker in line for marker in HISTORY_MARKERS) and f"v{old}" in line


def _lock_scoped(path: Path, text: str, old: str, new: str) -> str:
    """uv.lock / package-lock.json: only the horosa-skill / horosa-core-js package's own version lines."""
    if path.name == "uv.lock":
        return re.sub(r'(\[\[package\]\]\nname = "horosa-skill"\nversion = )"' + re.escape(old) + '"', r'\1"' + new + '"', text)
    if path.name == "package-lock.json":
        return text.replace(f'"version": "{old}"', f'"version": "{new}"')
    return text


# 代码站点只有一行是版本本身；其余行里的版本号都是历史（如 pyproject 注释「# v0.40.0 P1：运行期契约此前不在 wheel 里」，
# 不含任何 HISTORY_MARKERS，v0.40.1 的 bump 把它改成了 v0.40.1）。这两个文件只改版本赋值行。
_VERSION_LINE = {
    "pyproject.toml": 'version = "{v}"',
    "__init__.py": '__version__ = "{v}"',
}


def rewrite(text: str, path: Path, old: str, new: str) -> tuple[str, int]:
    if path.name in ("uv.lock", "package-lock.json"):
        out = _lock_scoped(path, text, old, new)
        return out, (1 if out != text else 0)
    if path.name in _VERSION_LINE:
        before, after = _VERSION_LINE[path.name].format(v=old), _VERSION_LINE[path.name].format(v=new)
        lines = text.split("\n")
        hits = [i for i, line in enumerate(lines) if line == before]
        for i in hits:
            lines[i] = after
        return "\n".join(lines), len(hits)
    lines = text.split("\n")
    changed = 0
    for i, line in enumerate(lines):
        if old in line and not _is_history(line, old):
            lines[i] = line.replace(old, new)
            changed += 1
    return "\n".join(lines), changed


def disagreeing_sites(version: str) -> list[str]:
    out: list[str] = []
    for rel in SITES:
        path = ROOT / rel
        if not path.is_file():
            out.append(f"{rel}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        if path.name == "uv.lock":
            ok = f'name = "horosa-skill"\nversion = "{version}"' in text
        elif path.name == "package-lock.json":
            ok = f'"version": "{version}"' in text
        elif path.name == "upstream_provenance.json":
            ok = f'"upstream_checked_at_package_version": "{version}"' in text
        else:
            ok = version in text
        if not ok:
            out.append(f"{rel}: does not carry {version}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("new_version", nargs="?", help="target version, e.g. 0.41.0")
    ap.add_argument("--check", action="store_true", help="only verify every site carries the pyproject version")
    args = ap.parse_args(argv)
    old = current_version()
    if args.check or not args.new_version:
        bad = disagreeing_sites(old)
        if bad:
            print("bump-version: sites disagreeing with pyproject " + old + ":\n  - " + "\n  - ".join(bad))
            return 1
        print(f"bump-version: ok ({len(SITES)} sites carry {old})")
        return 0
    new = args.new_version
    if not VERSION_RE.match(new):
        print(f"bump-version: {new!r} is not X.Y.Z", file=sys.stderr)
        return 2
    total = 0
    for rel in SITES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        out, n = rewrite(text, path, old, new)
        if n:
            path.write_text(out, encoding="utf-8")
            total += n
            print(f"{rel}: {n} line(s)")
    print(f"bump-version: {old} → {new} ({total} lines across {len(SITES)} sites); now run `uv lock` and scripts/verify_docs_sync.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
