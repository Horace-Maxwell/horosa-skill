from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from pathlib import Path


REQUIRED_ENTRIES = {
    "darwin-arm64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.sh",
        "runtime-payload/Horosa-Web/stop_horosa_local.sh",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        # ken engines back /qimen/pan · /taiyi/pan · /jinkou/pan — without these the chart
        # service mounts no ken endpoints and qimen/taiyi/jinkou fail at runtime.
        "runtime-payload/Horosa-Web/vendor/kinqimen/",
        "runtime-payload/Horosa-Web/vendor/kintaiyi/",
        "runtime-payload/Horosa-Web/vendor/kinjinkou/",
        # v3.5.0 全年份域 shared module — 16 ken/神数 engines lazily import it; missing → BC/远期 500s.
        "runtime-payload/Horosa-Web/vendor/kin_year_domain.py",
        # v3.5.1 地占大改版 data — the ifa/numbers/vedic geomancy engines read these; real file, not empty dir.
        "runtime-payload/Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
        # v3.10.0 择日十技法 — the qizheng/india election-scan engines behind /qizhengelectionscan/* and
        # /indiaelectionscan/*. aiExport stayed at v56 when they landed (只加键纪律), so version equality
        # passed on a stale tree; a real engine file is the freshness marker (same pattern as ifa_odu.json).
        "runtime-payload/Horosa-Web/astropy/astrostudy/qizheng_election_scan.py",
        "runtime-payload/Horosa-Web/astropy/astrostudy/india_election_scan.py",
        # v0.32.0 xuanshi 玄史知识库 backing SQLites — /xuanshi/* endpoints read both; editorial
        # degrades SILENTLY to {} when absent, so only this entry (real files, not empty dirs)
        # keeps a stripped/mispackaged archive from shipping green.
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/public_data.sqlite",
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/editorial.sqlite",
        # 5 standalone 神数 engines back /wangji/pan · /wuzhao/pan · /taixuan/pan · /jingjue/pan ·
        # /shenyishu/pan — without these the kentang mount skips them and the 神数 tools fail offline.
        "runtime-payload/Horosa-Web/vendor/kinwangji/",
        "runtime-payload/Horosa-Web/vendor/kinwuzhao/",
        "runtime-payload/Horosa-Web/vendor/taixuanshifa/",
        "runtime-payload/Horosa-Web/vendor/jingjue/",
        "runtime-payload/Horosa-Web/vendor/shenyishu/",
        # kinastro engine backs the 9 kinastro-* 神数 (/shaozi/pan … /qizhengkin/pan).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/",
        # 邵子神数 verse JSON, generated from the CSV at package time (without it 邵子 emits placeholders).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/shaozi/data/shaozi_tiaowen_6144.json",
        "runtime-payload/runtime/mac/python/bin/python3",
        "runtime-payload/runtime/mac/java/bin/java",
        "runtime-payload/runtime/mac/node/bin/node",
        "runtime-payload/runtime/mac/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
        # canping/heluo compute pillars via the vendored bazi chain → lunar-javascript; without the
        # bundled npm package those tools throw "Cannot find package 'lunar-javascript'" at runtime.
        "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
    ],
    "win32-x64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.ps1",
        "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        # ken engines back /qimen/pan · /taiyi/pan · /jinkou/pan (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinqimen/",
        "runtime-payload/Horosa-Web/vendor/kintaiyi/",
        "runtime-payload/Horosa-Web/vendor/kinjinkou/",
        # v3.5.0 全年份域 shared module — 16 ken/神数 engines lazily import it; missing → BC/远期 500s.
        "runtime-payload/Horosa-Web/vendor/kin_year_domain.py",
        # v3.5.1 地占大改版 data — the ifa/numbers/vedic geomancy engines read these; real file, not empty dir.
        "runtime-payload/Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
        # v3.10.0 择日十技法 — the qizheng/india election-scan engines behind /qizhengelectionscan/* and
        # /indiaelectionscan/*. aiExport stayed at v56 when they landed (只加键纪律), so version equality
        # passed on a stale tree; a real engine file is the freshness marker (same pattern as ifa_odu.json).
        "runtime-payload/Horosa-Web/astropy/astrostudy/qizheng_election_scan.py",
        "runtime-payload/Horosa-Web/astropy/astrostudy/india_election_scan.py",
        # v0.32.0 xuanshi 玄史知识库 backing SQLites — /xuanshi/* endpoints read both; editorial
        # degrades SILENTLY to {} when absent, so only this entry (real files, not empty dirs)
        # keeps a stripped/mispackaged archive from shipping green.
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/public_data.sqlite",
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/editorial.sqlite",
        # 5 standalone 神数 engines (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinwangji/",
        "runtime-payload/Horosa-Web/vendor/kinwuzhao/",
        "runtime-payload/Horosa-Web/vendor/taixuanshifa/",
        "runtime-payload/Horosa-Web/vendor/jingjue/",
        "runtime-payload/Horosa-Web/vendor/shenyishu/",
        # kinastro engine backs the 9 kinastro-* 神数 (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/",
        # 邵子神数 verse JSON, generated from the CSV at package time (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/shaozi/data/shaozi_tiaowen_6144.json",
        "runtime-payload/runtime/windows/python/python.exe",
        "runtime-payload/runtime/windows/java/bin/java.exe",
        "runtime-payload/runtime/windows/node/node.exe",
        "runtime-payload/runtime/windows/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
        # canping/heluo need the bundled lunar-javascript (see darwin note).
        "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
    ],
    "linux-x64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.sh",
        "runtime-payload/Horosa-Web/stop_horosa_local.sh",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        # ken engines back /qimen/pan · /taiyi/pan · /jinkou/pan (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinqimen/",
        "runtime-payload/Horosa-Web/vendor/kintaiyi/",
        "runtime-payload/Horosa-Web/vendor/kinjinkou/",
        # v3.5.0 全年份域 shared module — 16 ken/神数 engines lazily import it; missing → BC/远期 500s.
        "runtime-payload/Horosa-Web/vendor/kin_year_domain.py",
        # v3.5.1 地占大改版 data — the ifa/numbers/vedic geomancy engines read these; real file, not empty dir.
        "runtime-payload/Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
        # v3.10.0 择日十技法 — the qizheng/india election-scan engines behind /qizhengelectionscan/* and
        # /indiaelectionscan/*. aiExport stayed at v56 when they landed (只加键纪律), so version equality
        # passed on a stale tree; a real engine file is the freshness marker (same pattern as ifa_odu.json).
        "runtime-payload/Horosa-Web/astropy/astrostudy/qizheng_election_scan.py",
        "runtime-payload/Horosa-Web/astropy/astrostudy/india_election_scan.py",
        # v0.32.0 xuanshi 玄史知识库 backing SQLites — /xuanshi/* endpoints read both; editorial
        # degrades SILENTLY to {} when absent, so only this entry (real files, not empty dirs)
        # keeps a stripped/mispackaged archive from shipping green.
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/public_data.sqlite",
        "runtime-payload/Horosa-Web/astropy/astrostudy/xuanshi/data/editorial.sqlite",
        # 5 standalone 神数 engines (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinwangji/",
        "runtime-payload/Horosa-Web/vendor/kinwuzhao/",
        "runtime-payload/Horosa-Web/vendor/taixuanshifa/",
        "runtime-payload/Horosa-Web/vendor/jingjue/",
        "runtime-payload/Horosa-Web/vendor/shenyishu/",
        # kinastro engine backs the 9 kinastro-* 神数 (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/",
        # 邵子神数 verse JSON, generated from the CSV at package time (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinastro/astro/shaozi/data/shaozi_tiaowen_6144.json",
        "runtime-payload/runtime/linux/python/bin/python3",
        "runtime-payload/runtime/linux/java/bin/java",
        "runtime-payload/runtime/linux/node/bin/node",
        "runtime-payload/runtime/linux/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
        # canping/heluo need the bundled lunar-javascript (see darwin note).
        "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
    ],
}


def _archive_entries(path: Path) -> set[str]:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return {member.name for member in archive.getmembers()}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    raise SystemExit(f"unsupported archive type: {path}")


def _read_archive_text(path: Path, entry_name: str) -> str:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            member = archive.getmember(entry_name)
            file_obj = archive.extractfile(member)
            if file_obj is None:
                raise SystemExit(f"{path.name} has unreadable entry: {entry_name}")
            return file_obj.read().decode("utf-8")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return archive.read(entry_name).decode("utf-8")
    raise SystemExit(f"unsupported archive type: {path}")


# v0.38.1 A3：doctor 的 Windows 长路径余量按 manager.PAYLOAD_LONGEST_ENTRY_CHARS 估算。该常量写 200 时
# 比 v0.38.0 实测的 179 高出 21 —— 默认根 `C:\\Users\\<user>\\AppData\\Local\\Horosa\\runtime` 被误报「装不下」。
# 这里双向锁：① 每个归档的最长条目 ≤ 常量（低估 = install 会撞 MAX_PATH 而 doctor 没预警）；
# ② 常量 − darwin 归档实测 ≤ MAX_OVERESTIMATE_CHARS（高估 = doctor 把装得下的机器报成 ok:false）。
# 常量按 darwin 载荷定义（Windows 树约短 7），所以 ② 只在给了 darwin 归档时执行；Windows 只做 ①。
MAX_OVERESTIMATE_CHARS = 8
_MANAGER_PY = Path(__file__).resolve().parents[1] / "src" / "horosa_skill" / "runtime" / "manager.py"


def payload_longest_entry_limit(manager_py: Path = _MANAGER_PY) -> int:
    """从源码正则读 PAYLOAD_LONGEST_ENTRY_CHARS（脚本可能在没装包的 python3 下跑：publish_release.sh / build_runtime_release.sh）。"""
    match = re.search(r"^PAYLOAD_LONGEST_ENTRY_CHARS\s*=\s*(\d+)", manager_py.read_text(encoding="utf-8"), re.M)
    if not match:
        raise SystemExit(f"PAYLOAD_LONGEST_ENTRY_CHARS not found in {manager_py}")
    return int(match.group(1))


def longest_entry(entries: set[str]) -> tuple[int, str]:
    if not entries:
        return 0, ""
    name = max(entries, key=len)
    return len(name), name


def check_entry_lengths(
    measured: dict[str, tuple[int, str]], limit: int, *, max_overestimate: int = MAX_OVERESTIMATE_CHARS
) -> list[str]:
    """`measured` = {platform_key: (longest_len, entry)}；返回违规说明（空 = 通过）。纯函数，便于负向对照。"""
    problems: list[str] = []
    for platform_key, (length, name) in measured.items():
        if length > limit:
            problems.append(
                f"{platform_key}: longest entry is {length} chars > PAYLOAD_LONGEST_ENTRY_CHARS={limit} "
                f"(doctor would under-estimate the Windows path headroom): {name}"
            )
    darwin = measured.get("darwin-arm64")
    if darwin is not None and limit - darwin[0] > max_overestimate:
        problems.append(
            f"darwin-arm64: PAYLOAD_LONGEST_ENTRY_CHARS={limit} over-estimates the measured {darwin[0]} by "
            f"{limit - darwin[0]} chars (> {max_overestimate}); lower the constant in runtime/manager.py "
            "so doctor stops reporting installable roots as too long"
        )
    return problems


def _assert_entries(path: Path, platform_key: str) -> None:
    entries = _archive_entries(path)
    missing: list[str] = []
    for required in REQUIRED_ENTRIES[platform_key]:
        if required.endswith("/"):
            # Require a real file strictly INSIDE the directory, not merely a directory-marker entry.
            if not any(
                entry.startswith(required) and len(entry) > len(required) and not entry.endswith("/")
                for entry in entries
            ):
                missing.append(required)
        elif required not in entries:
            missing.append(required)
    if missing:
        raise SystemExit(f"{path.name} is missing required entries:\n- " + "\n- ".join(missing))


def _assert_payload_manifest(path: Path, platform_key: str, expected_version: str) -> None:
    raw = _read_archive_text(path, "runtime-payload/runtime-manifest.json")
    try:
        payload_manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.name} contains invalid runtime-payload/runtime-manifest.json: {exc}") from exc
    version = payload_manifest.get("version")
    payload_version = payload_manifest.get("runtime_payload_version", version)
    platform = payload_manifest.get("platform")
    errors: list[str] = []
    if version != expected_version:
        errors.append(f"version={version!r} expected {expected_version!r}")
    if payload_version != expected_version:
        errors.append(f"runtime_payload_version={payload_version!r} expected {expected_version!r}")
    if platform != platform_key:
        errors.append(f"platform={platform!r} expected {platform_key!r}")
    if errors:
        raise SystemExit(f"{path.name} has stale or mismatched embedded runtime manifest: " + "; ".join(errors))


def _read_archive_bytes(path: Path, entry_name: str) -> bytes:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            file_obj = archive.extractfile(archive.getmember(entry_name))
            if file_obj is None:
                raise SystemExit(f"{path.name} has unreadable entry: {entry_name}")
            return file_obj.read()
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return archive.read(entry_name)
    raise SystemExit(f"unsupported archive type: {path}")


# 发布闸：Windows 启动器必须带 UTF-8 BOM。runtime manager 用 `powershell`（Windows PowerShell 5.1）
# 跑它，5.1 对无 BOM 的 .ps1 按系统 ANSI 代码页解码——UTF-8 的 `—`(U+2014) 在 CP1252 下末字节 0x94
# 解成 U+201D，而 PowerShell 词法分析器**认它作字符串定界符** → 字符串截断 → parse error → 启动器
# 未跑先死（runtime.start_failed，整个 Windows runtime 起不来）。模板侧守卫见
# tests/test_runtime_launcher_templates.py；这条是 zip 里的最终形态守卫。
_WINDOWS_BOM_REQUIRED = (
    "runtime-payload/Horosa-Web/start_horosa_local.ps1",
    "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
)


def _assert_windows_launchers_are_bom_encoded(path: Path) -> None:
    offenders: list[str] = []
    for entry in _WINDOWS_BOM_REQUIRED:
        if not _read_archive_bytes(path, entry).startswith(b"\xef\xbb\xbf"):
            offenders.append(entry)
    if offenders:
        raise SystemExit(
            f"{path.name}: Windows launcher(s) lack a UTF-8 BOM — Windows PowerShell 5.1 will decode them "
            "as ANSI and a single non-ASCII char can break the parse (runtime.start_failed):\n- "
            + "\n- ".join(offenders)
        )


# 🔴 arch gate (v0.38.0 A2): a payload derived from the darwin-arm64 seed must carry x64 binaries for
# win32-x64 — copying the seed's java/node/python by mistake would pass every entry check above and fail
# only on the user's machine. Read the headers of the three runtimes + numpy's extension.
_NATIVE_ARCH = {
    "win32-x64": ("x86_64", (
        "runtime-payload/runtime/windows/python/python.exe",
        "runtime-payload/runtime/windows/java/bin/java.exe",
        "runtime-payload/runtime/windows/node/node.exe",
    ), "runtime-payload/runtime/windows/python/Lib/site-packages/numpy/_core/_multiarray_umath"),
    "darwin-arm64": ("arm64", (
        "runtime-payload/runtime/mac/java/bin/java",
        "runtime-payload/runtime/mac/node/bin/node",
    ), "runtime-payload/runtime/mac/python/lib/"),
}


def _binary_arches(data: bytes) -> set[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_horosa_runtime_seed_for_verify", Path(__file__).resolve().parent / "runtime_seed.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.binary_arches(data)


def _assert_native_arch(path: Path, platform_key: str) -> None:
    if platform_key not in _NATIVE_ARCH:
        return
    expected, fixed, numpy_prefix = _NATIVE_ARCH[platform_key]
    entries = _archive_entries(path)
    numpy_entry = next(
        (e for e in entries if e.startswith(numpy_prefix) and "numpy/_core/_multiarray_umath" in e and e.endswith((".pyd", ".so"))),
        None,
    )
    targets = [*fixed, *([numpy_entry] if numpy_entry else [])]
    offenders: list[str] = []
    for entry in targets:
        if entry not in entries:
            offenders.append(f"{entry} (missing)")
            continue
        found = _binary_arches(_read_archive_bytes(path, entry)[:4096])
        if expected not in found:
            offenders.append(f"{entry} (built for {sorted(found) or 'not a native binary'})")
    if offenders:
        raise SystemExit(f"{path.name}: native binaries are not {expected} as {platform_key} requires:\n- " + "\n- ".join(offenders))


RECOGNIZED_PLATFORMS = {"darwin-arm64", "win32-x64", "linux-x64"}


def _validate_manifest(path: Path, *, expect_platforms: set[str] | None = None) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        raise SystemExit(f"manifest missing platforms object: {path}")
    # At least one platform must be present; any of darwin-arm64, win32-x64, linux-x64.
    recognized = RECOGNIZED_PLATFORMS
    if not any(k in platforms for k in recognized):
        raise SystemExit(f"manifest must include at least one recognized platform ({', '.join(sorted(recognized))})")
    for key in list(platforms):
        if key not in recognized:
            continue
        item = platforms[key]
        for field in ("url", "sha256", "archive_type"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SystemExit(f"manifest {key}.{field} is missing or empty")
        # optional `size` (bytes, v0.38.0 A3) — when present it must be a positive int
        if "size" in item and (not isinstance(item["size"], int) or isinstance(item["size"], bool) or item["size"] <= 0):
            raise SystemExit(f"manifest {key}.size must be a positive integer byte count, got {item['size']!r}")
    if expect_platforms is not None:
        present = {k for k in platforms if k in recognized}
        if present != set(expect_platforms):
            raise SystemExit(
                f"manifest platform set {sorted(present)} != expected {sorted(expect_platforms)} "
                "(a release must carry every platform it promises — no partial manifests)"
            )
    return data


def _assert_manifest_size(manifest: dict, platform_key: str, archive: Path) -> None:
    """When the manifest records `size`, it must be the archive's real byte count (v0.38.0 A3)."""
    item = (manifest.get("platforms") or {}).get(platform_key) or {}
    size = item.get("size")
    if size is None:
        return
    actual = archive.stat().st_size
    if size != actual:
        raise SystemExit(f"manifest {platform_key}.size={size} but {archive.name} is {actual} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Horosa runtime release archives and manifest.")
    parser.add_argument("--darwin-archive", default=None, help="Path to the macOS (darwin-arm64) runtime archive.")
    parser.add_argument("--windows-archive", default=None, help="Path to the Windows (win32-x64) runtime archive.")
    parser.add_argument("--linux-archive", default=None, help="Path to the Linux (linux-x64) runtime archive.")
    parser.add_argument("--manifest", required=True, help="Path to the release manifest JSON.")
    parser.add_argument("--expect-platforms", default=None,
                        help="Comma-separated platform keys the manifest must contain EXACTLY (e.g. darwin-arm64,win32-x64).")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    expected_set = {p.strip() for p in args.expect_platforms.split(",") if p.strip()} if args.expect_platforms else None
    manifest = _validate_manifest(manifest_path, expect_platforms=expected_set)
    expected_version = str(manifest.get("version") or "")
    if not expected_version:
        raise SystemExit(f"manifest version is missing: {manifest_path}")

    verified_archives: dict[str, str] = {}
    measured_lengths: dict[str, tuple[int, str]] = {}

    if args.darwin_archive:
        darwin_archive = Path(args.darwin_archive).expanduser().resolve()
        _assert_entries(darwin_archive, "darwin-arm64")
        measured_lengths["darwin-arm64"] = longest_entry(_archive_entries(darwin_archive))
        _assert_payload_manifest(darwin_archive, "darwin-arm64", expected_version)
        _assert_native_arch(darwin_archive, "darwin-arm64")
        _assert_manifest_size(manifest, "darwin-arm64", darwin_archive)
        verified_archives["darwin"] = str(darwin_archive)

    if args.windows_archive:
        windows_archive = Path(args.windows_archive).expanduser().resolve()
        _assert_entries(windows_archive, "win32-x64")
        measured_lengths["win32-x64"] = longest_entry(_archive_entries(windows_archive))
        _assert_payload_manifest(windows_archive, "win32-x64", expected_version)
        _assert_windows_launchers_are_bom_encoded(windows_archive)
        _assert_native_arch(windows_archive, "win32-x64")
        _assert_manifest_size(manifest, "win32-x64", windows_archive)
        verified_archives["windows"] = str(windows_archive)

    if args.linux_archive:
        linux_archive = Path(args.linux_archive).expanduser().resolve()
        _assert_entries(linux_archive, "linux-x64")
        measured_lengths["linux-x64"] = longest_entry(_archive_entries(linux_archive))
        _assert_payload_manifest(linux_archive, "linux-x64", expected_version)
        _assert_manifest_size(manifest, "linux-x64", linux_archive)
        verified_archives["linux"] = str(linux_archive)

    if not verified_archives:
        parser.error("At least one archive (darwin, windows, or linux) must be provided.")

    length_limit = payload_longest_entry_limit()
    length_problems = check_entry_lengths(measured_lengths, length_limit)
    if length_problems:
        raise SystemExit("payload entry length gate failed:\n- " + "\n- ".join(length_problems))

    print(
        json.dumps(
            {
                "ok": True,
                "version": manifest.get("version"),
                "verified_archives": verified_archives,
                "manifest": str(manifest_path),
                "payload_longest_entry_chars": {
                    "limit": length_limit,
                    "measured": {k: {"chars": v[0], "entry": v[1]} for k, v in measured_lengths.items()},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
