#!/usr/bin/env python3
"""publish 前的字节一致性闸（v0.38.1 R5）：三台真机装的归档 == draft 上的资产。

每条 lane 把它实际安装的归档 sha256 写进 lane-report.json（`installed_archive_sha256`，来自 install 结果里的
asset.sha256 —— 安装器解包前已用它校验过文件）。draft 资产的 sha 由 GitHub 自己算（`assets[].digest`，
`sha256:…`），拿不到 digest 时退到 SHA256SUMS.txt。任何一条 lane 缺证据、或与资产不一致 → 不许翻公开。

stdlib-only；接在 release-runtime.yml 的 publish job。负向对照见 tests/test_verify_matrix_digests.py。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


def parse_digests(text: str) -> dict[str, str]:
    """`<name> sha256:<hex>` 每行一条（`gh api … --jq '.assets[] | "\\(.name) \\(.digest // "")"'`）。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("sha256:"):
            out[parts[0]] = parts[1].removeprefix("sha256:").lower()
    return out


def parse_sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            out[parts[1].lstrip("*")] = parts[0].lower()
    return out


def lane_evidence(lanes_dir: Path) -> list[dict[str, object]]:
    lanes: list[dict[str, object]] = []
    for report_path in sorted(lanes_dir.rglob("lane-report.json")):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            lanes.append({"path": str(report_path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        lanes.append({
            "path": str(report_path),
            "lane": report_path.parent.name,
            "ok": report.get("ok"),
            "name": report.get("installed_archive_name"),
            "sha256": (report.get("installed_archive_sha256") or "").lower() or None,
        })
    return lanes


def check(lanes: list[dict[str, object]], digests: dict[str, str], sums: dict[str, str], *, expect_lanes: int) -> list[str]:
    problems: list[str] = []
    if len(lanes) < expect_lanes:
        problems.append(f"expected evidence from {expect_lanes} lanes, found {len(lanes)} lane-report.json")
    for lane in lanes:
        if lane.get("error"):
            problems.append(f"{lane['path']}: {lane['error']}")
            continue
        if lane.get("ok") is not True:
            problems.append(f"{lane.get('lane')}: lane-report says ok={lane.get('ok')}")
        name, sha = lane.get("name"), lane.get("sha256")
        if not name or not sha:
            problems.append(f"{lane.get('lane')}: no installed_archive_name / installed_archive_sha256 recorded")
            continue
        published = digests.get(str(name)) or sums.get(str(name))
        if not published:
            problems.append(f"{lane.get('lane')}: {name} has neither an asset digest nor a SHA256SUMS line on the release")
        elif published != sha:
            problems.append(f"{lane.get('lane')}: installed {name} sha256 {sha[:12]}… != published {published[:12]}… (the matrix did not test the bytes being published)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lanes", required=True, help="directory containing the downloaded runtime-matrix-* artifacts")
    ap.add_argument("--digests", required=True, help="file of `<asset name> sha256:<hex>` lines from the release API")
    ap.add_argument("--sums", default=None, help="SHA256SUMS.txt (fallback when an asset has no digest)")
    ap.add_argument("--expect-lanes", type=int, default=3)
    args = ap.parse_args(argv)
    lanes = lane_evidence(Path(args.lanes))
    digests = parse_digests(Path(args.digests).read_text(encoding="utf-8")) if Path(args.digests).is_file() else {}
    sums = parse_sums(Path(args.sums).read_text(encoding="utf-8")) if args.sums and Path(args.sums).is_file() else {}
    problems = check(lanes, digests, sums, expect_lanes=args.expect_lanes)
    if problems:
        print("matrix-digests FAILED — the release is not proven on the bytes being published:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1
    for lane in lanes:
        print(f"matrix-digests OK: {lane.get('lane')} installed {lane.get('name')} = {str(lane.get('sha256'))[:12]}… (matches the release asset)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
