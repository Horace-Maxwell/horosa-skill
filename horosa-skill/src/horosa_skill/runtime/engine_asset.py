"""JS 引擎独立资产（engine-only）：没有离线 runtime 的机器也有本地 JS 引擎（v0.50.0-dev，E-02）。

🔴 为什么：JS 引擎（horosa-core-js）此前只随 darwin-arm64 / win32-x64 两个 runtime 归档发出去。Linux、Intel Mac、Docker、
pip / wheel 网关安装、以及没跑 `install` 的人都没有它 —— 八字 / 紫微 / 奇门 / 太乙 / 金口诀 / 六壬 / 河洛 / 参评等技法一律
`js_engine.cli_missing`，六爻失败，盘图与塔罗悄悄降级。引擎本身是纯 JS + 四个生产 npm 包，与平台无关，所以每个发布另附一份
`horosa-core-js-v<ver>.tar.gz`（`scripts/build_core_js_asset.py`），清单顶层 `core_js` 条目记它的 url / sha256 / size / node 下限。

装在哪：`<runtime 根>/core-js/horosa-core-js/`（引擎目录）+ `<runtime 根>/core-js/install.json`（来历：版本、sha256、来源、时间）。
不碰 `current/`：离线 runtime 与它互不覆盖，`_candidate_engine_roots` 的顺序是 HOROSA_CORE_JS_ROOT → 已装 runtime → 本资产 → 源码树。
换入是同卷两次改名（`core-js` → `core-js.previous`，暂存 → `core-js`），失败回滚；`uninstall --engine-only` 只删这两个目录。

Node 不随资产走（每个平台一个二进制，这正是要躲开的东西）：用 HOROSA_NODE_BIN / PATH 上的 node，下限与 horosa-core-js
`engines.node` 锁步（`engine.node_runtime.NODE_FLOOR`）。找不到或太旧时引擎照装，结果里明说要装什么。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError, bilingual

# contracts/release_platforms.json 的 core_js 段（wheel 不带 contracts/，在这里抄一份；tests/test_engine_asset_install.py 锁步）。
ENGINE_ASSET_MANIFEST_KEY = "core_js"
ENGINE_ASSET_ROOT = "horosa-core-js"
ENGINE_ASSET_SINCE = "0.50.0"
ENGINE_ASSET_TEMPLATE = "horosa-core-js-v{version}.tar.gz"
ENGINE_ASSET_REQUIRED_ENTRIES = ("bin/cli.mjs", "package.json", "src/tools/index.js", "dist/app-charts.cjs")

ENGINE_DIRNAME = "core-js"            # <runtime 根>/core-js/
ENGINE_PREVIOUS_DIRNAME = "core-js.previous"
ENGINE_RECORD_NAME = "install.json"
ENGINE_LOCK_NAME = ".core-js-install.lock"
ENGINE_LOCK_OWNER = "engine-install"


def engine_dir(runtime_root: Path) -> Path:
    return Path(runtime_root) / ENGINE_DIRNAME


def installed_engine_root(runtime_root: Path) -> Path | None:
    """已装的 engine-only 引擎目录；没装 / 装坏了（没有来历记录或没有 cli.mjs）返回 None。每次 JS 调用都走这里：只 stat 两次。"""
    base = engine_dir(runtime_root)
    root = base / ENGINE_ASSET_ROOT
    if (base / ENGINE_RECORD_NAME).is_file() and (root / "bin" / "cli.mjs").is_file():
        return root
    return None


def read_record(runtime_root: Path) -> dict[str, Any] | None:
    try:
        record = json.loads((engine_dir(runtime_root) / ENGINE_RECORD_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def engine_paths(runtime_root: Path) -> list[Path]:
    """本资产在 runtime 根下占用的全部路径（卸载只删这些）。"""
    return [engine_dir(runtime_root), Path(runtime_root) / ENGINE_PREVIOUS_DIRNAME]


def manifest_has_engine_asset(manifest: dict[str, Any] | None) -> bool:
    entry = (manifest or {}).get(ENGINE_ASSET_MANIFEST_KEY)
    return isinstance(entry, dict) and bool(str(entry.get("url") or "").strip())


def engine_only_command() -> str:
    from horosa_skill.runtime.hints import cli_command

    return cli_command("install --engine-only")


class EngineAssetMixin:
    """HorosaRuntimeManager 的 engine-only 安装 / 卸载（复用它的清单读取、镜像下载、断点续传、摘要校验、安全解包）。"""

    def install_engine_only(
        self,
        *,
        archive: str | None = None,
        manifest_url: str | None = None,
        force: bool = False,
        progress: Any | None = None,
        sha256: str | None = None,
        manifest_data: dict[str, Any] | None = None,
        manifest_location: str | None = None,
        reason: str = "requested",
        platform_name: str | None = None,
        warnings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """装 JS 引擎独立资产。`reason`：requested（`install --engine-only`）/ no_payload_for_platform（本平台没有 runtime 归档）。"""
        from horosa_skill.runtime import manager as _manager

        install_warnings: list[dict[str, Any]] = list(warnings or [])
        self._require_writable_runtime_root()
        pinned = self._normalize_sha256_pin(sha256)
        self._sweep_install_temps()
        self._last_download = None
        entry: dict[str, Any] = {}
        location = manifest_location
        if archive is not None:
            source = archive
            expected = pinned
        else:
            location = location or manifest_url or self.settings.runtime_manifest_url or self.settings.default_runtime_manifest_url
            if manifest_data is None:
                manifest_data = self._read_json_location(location)
            raw_entry = manifest_data.get(ENGINE_ASSET_MANIFEST_KEY)
            if not isinstance(raw_entry, dict) or not str(raw_entry.get("url") or "").strip():
                raise self._engine_asset_missing_error(manifest_data, location, platform_name)
            entry = raw_entry
            source = str(entry["url"]).strip()
            listed = str(entry.get("sha256") or "").strip().lower() or None
            if pinned and listed and listed != pinned:
                raise RuntimeValidationError(
                    bilingual(
                        "`--sha256` 给的摘要与发布清单里 JS 引擎资产的 sha256 不一致。",
                        "The `--sha256` digest differs from the one the release manifest lists for the JS engine asset.",
                    ),
                    code="runtime.install_sha256_mismatch",
                    details={"expected_sha256": pinned, "manifest_sha256": listed, "manifest_url": location, "asset": "core_js"},
                )
            expected = listed or pinned
            if not expected:
                self._refuse_or_note_unverified(location, source, "core_js", install_warnings)
            record = read_record(self.runtime_root)
            if (not force and expected and record and str(record.get("sha256") or "").lower() == expected.lower()
                    and installed_engine_root(self.runtime_root) is not None):
                return self._engine_result(changed=False, record=record, reason=reason, platform_name=platform_name,
                                           warnings=install_warnings, skipped_download=True)

        # 峰值 ≈ 归档 + 解开的树 + 旧版：按 4 倍估（manager 的同一个预检）；大小不明时按 50 MB 估（真资产约 7 MB）。
        size = entry.get("size") if isinstance(entry.get("size"), int) else 50_000_000
        self._require_install_disk_space({"size": size})
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=_manager._INSTALL_TEMP_PREFIX, dir=self.runtime_root) as temp_raw:
            temp_dir = Path(temp_raw)
            (temp_dir / _manager.INSTALL_TEMP_OWNER).write_text(str(os.getpid()), encoding="utf-8")
            archive_path = self._materialize_archive(source, temp_dir, progress=progress, expected_sha256=expected)
            verified_by_download = bool((self._last_download or {}).get("sha256_verified"))
            actual = expected.lower() if expected and verified_by_download else _manager._sha256_file(archive_path).lower()
            if expected and actual != expected.lower():
                raise RuntimeValidationError(
                    bilingual("JS 引擎资产的 sha256 与期望不符，没有安装。", "The JS engine asset fails its sha256 check; nothing was installed."),
                    code="runtime.install_sha256_mismatch",
                    details={"archive": str(archive_path), "expected_sha256": expected.lower(), "actual_sha256": actual},
                )
            extract_dir = temp_dir / _manager._INSTALL_EXTRACT_DIRNAME
            extract_dir.mkdir()
            self._extract_archive(archive_path, extract_dir)
            package = self._validate_engine_tree(extract_dir, archive_path, entry)
            stage = temp_dir / "stage"
            stage.mkdir()
            (extract_dir / ENGINE_ASSET_ROOT).replace(stage / ENGINE_ASSET_ROOT)
            record = {
                "schema": 1,
                "kind": "horosa-core-js",
                "version": package.get("version"),
                "node_floor": (package.get("engines") or {}).get("node"),
                "sha256": actual,
                "sha256_verified": bool(expected),
                "source": (self._last_download or {}).get("url") or source,
                "manifest_url": location,
                "manifest_version": (manifest_data or {}).get("version"),
                "reason": reason,
                "installed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            (stage / ENGINE_RECORD_NAME).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._swap_in_engine(stage)
        return self._engine_result(changed=True, record=record, reason=reason, platform_name=platform_name,
                                   warnings=install_warnings, skipped_download=False)

    # ---- 校验 / 换入 / 结果 -------------------------------------------------------------------------------------------

    def _validate_engine_tree(self, extract_dir: Path, archive_path: Path, entry: dict[str, Any]) -> dict[str, Any]:
        top = sorted(child.name for child in extract_dir.iterdir())
        root = extract_dir / ENGINE_ASSET_ROOT
        problems: list[str] = []
        if top != [ENGINE_ASSET_ROOT]:
            problems.append(f"top level must be exactly {ENGINE_ASSET_ROOT}/, found {top[:5]}")
        package: dict[str, Any] = {}
        if root.is_dir():
            try:
                loaded = json.loads((root / "package.json").read_text(encoding="utf-8"))
                package = loaded if isinstance(loaded, dict) else {}
            except (OSError, ValueError):
                package = {}
            missing = [rel for rel in ENGINE_ASSET_REQUIRED_ENTRIES if not (root / rel).is_file()]
            missing += [f"node_modules/{dep}/package.json" for dep in sorted(package.get("dependencies") or {})
                        if not (root / "node_modules" / dep / "package.json").is_file()]
            if missing:
                problems.append("missing " + ", ".join(missing))
            if package and package.get("name") != ENGINE_ASSET_ROOT:
                problems.append(f"package.json names {package.get('name')!r}")
            wanted = entry.get("version")
            if wanted and package.get("version") != wanted:
                problems.append(f"package.json version {package.get('version')!r} != manifest {wanted!r}")
        if problems:
            raise RuntimeValidationError(
                bilingual(
                    f"这不是一份可用的 JS 引擎资产（{archive_path.name}）：{'；'.join(problems)}。已装的东西没有被动过。",
                    f"This is not a usable JS engine asset ({archive_path.name}): {'; '.join(problems)}. Nothing installed was touched.",
                ),
                code="runtime.engine_asset_invalid",
                details={"archive": str(archive_path), "problems": problems,
                         "expected": f"{ENGINE_ASSET_TEMPLATE.format(version='<version>')} from a release >= {ENGINE_ASSET_SINCE}"},
            )
        return package

    def _swap_in_engine(self, stage: Path) -> None:
        """同卷两次改名换入；中途失败把旧的挪回来。一把锁挡住两个同时进行的 engine 安装。"""
        from horosa_skill.runtime import manager as _manager
        from horosa_skill.runtime.pidlock import describe_lock, release as release_lock, try_pid_lock

        target = engine_dir(self.runtime_root)
        previous = self.runtime_root / ENGINE_PREVIOUS_DIRNAME
        lock_path = self.runtime_root / ENGINE_LOCK_NAME
        if not try_pid_lock(lock_path, stale_after_seconds=900.0, owner=ENGINE_LOCK_OWNER):
            raise RuntimeInstallError(
                bilingual("另一个进程正在安装 JS 引擎资产，这次没有动它。", "Another process is installing the JS engine asset; it was left alone."),
                code="runtime.engine_install_in_progress",
                details={"lock": str(lock_path), "holder": describe_lock(lock_path)},
            )
        try:
            if not target.exists() and previous.is_dir() and installed_engine_root_of(previous):
                previous.replace(target)  # 上次崩在两次改名之间：先把好副本挪回来
            if previous.exists():
                _manager._rmtree_force(previous)
            if target.exists():
                target.replace(previous)
            try:
                stage.replace(target)
            except OSError:
                if previous.exists() and not target.exists():
                    previous.replace(target)
                raise
            if previous.exists():
                try:
                    _manager._rmtree_force(previous)
                except OSError:
                    pass  # Windows 上被占用：留给下一次安装 / 卸载清
        finally:
            release_lock(lock_path)

    def _engine_result(self, *, changed: bool, record: dict[str, Any], reason: str, platform_name: str | None,
                       warnings: list[dict[str, Any]], skipped_download: bool) -> dict[str, Any]:
        from horosa_skill.engine import node_runtime
        from horosa_skill.runtime.manager import _contextualize

        node = node_runtime.resolve_node(self.settings, self.load_installed_manifest()).as_dict()
        result_warnings = list(warnings)
        if reason == "no_payload_for_platform":
            result_warnings.append({
                "code": "runtime.engine_only_installed",
                "message": bilingual(
                    f"本机平台（{platform_name}）没有离线 runtime 归档，只装了 JS 引擎：本地 JS 技法（八字、六爻、大六壬、河洛、参评、"
                    "一掌经、塔罗、黄历等）可用；要 Java / chart 服务算的技法（紫微、西占、奇门 / 太乙 / 金口诀、神数等）还得走网关模式——"
                    "设 HOROSA_SERVER_ROOT 与 HOROSA_CHART_SERVER_ROOT 指向一台装了 runtime 的机器。",
                    f"This platform ({platform_name}) has no offline runtime archive, so only the JS engine was installed: the local "
                    "JS techniques (BaZi, Liuyao, Liuren, Heluo, Canping, Yizhangjing, tarot, almanac …) work; techniques computed by "
                    "the Java / chart services (Ziwei, Western charts, Qimen / Taiyi / Jinkou, Shenshu …) still need gateway mode: "
                    "point HOROSA_SERVER_ROOT and HOROSA_CHART_SERVER_ROOT at a machine that runs the runtime.",
                ),
                "platform": platform_name,
            })
        if node["problem"] in {"not_found", "too_old", "node_bin_missing"}:
            code = "js_engine.node_too_old" if node["problem"] == "too_old" else (
                "js_engine.node_bin_missing" if node["problem"] == "node_bin_missing" else "js_engine.node_unavailable")
            found = f"找到的是 {node['version']}（{node['path']}）" if node["problem"] == "too_old" else "没有找到可用的 node"
            found_en = f"found {node['version']} ({node['path']})" if node["problem"] == "too_old" else "no usable node was found"
            result_warnings.append({
                "code": code,
                "message": bilingual(
                    f"JS 引擎已装好，但它要 Node.js {node['required']}，{found}。装一个够新的 Node.js（nodejs.org 的 LTS，或系统包管理器 / "
                    "nvm），让 `node` 在 PATH 上，或设 HOROSA_NODE_BIN 指向它；装好后不用重装引擎。",
                    f"The JS engine is installed, but it needs Node.js {node['required']} and {found_en}. Install a recent Node.js "
                    "(an LTS from nodejs.org, your package manager or nvm) so `node` is on PATH, or set HOROSA_NODE_BIN to it; the "
                    "engine does not need reinstalling afterwards.",
                ),
                "node": node,
            })
        root = engine_dir(self.runtime_root) / ENGINE_ASSET_ROOT
        return {
            "ok": True,
            "installed": True,
            "mode": "engine_only",
            "reason": reason,
            "changed": changed,
            "skipped_download": skipped_download,
            "platform": platform_name,
            "version": record.get("version"),
            "engine": {
                "root": str(root),
                "version": record.get("version"),
                "sha256": record.get("sha256"),
                "sha256_verified": record.get("sha256_verified"),
                "source": record.get("source"),
                "installed_at": record.get("installed_at"),
            },
            "node": node,
            "ready": node["ok"],
            "warnings": result_warnings,
            "runtime_root": str(self.runtime_root),
            "download": self._last_download,
            "next_action": _contextualize(bilingual(
                "接下来：`horosa-skill doctor` 看 js_engine 一节（应为 ready），再 `horosa-skill selfcheck`。",
                "Next: `horosa-skill doctor` and read its js_engine section (should be ready), then `horosa-skill selfcheck`.",
            )) if node["ok"] else bilingual(
                "引擎已就位，先装好 Node.js（见 warnings），再跑 `horosa-skill doctor`。",
                "The engine is in place; install Node.js first (see warnings), then run `horosa-skill doctor`.",
            ),
        }

    def _engine_asset_missing_error(self, manifest: dict[str, Any], location: str | None,
                                    platform_name: str | None) -> RuntimeInstallError:
        version = manifest.get("version")
        return RuntimeInstallError(
            bilingual(
                f"这份发布清单（{version or '版本不明'}）没有 JS 引擎独立资产（`core_js`，{ENGINE_ASSET_SINCE} 起每个发布都带）。"
                f"换一份 {ENGINE_ASSET_SINCE} 及以后的清单（`--manifest-url`），或设 HOROSA_CORE_JS_ROOT 指向一份 horosa-core-js 目录。",
                f"This release manifest ({version or 'unknown version'}) has no standalone JS engine asset (`core_js`, shipped with every "
                f"release from {ENGINE_ASSET_SINCE} on). Use a manifest of {ENGINE_ASSET_SINCE} or later (`--manifest-url`), or set "
                "HOROSA_CORE_JS_ROOT to a horosa-core-js directory.",
            ),
            code="runtime.engine_asset_missing",
            details={"manifest_url": location, "manifest_version": version, "since": ENGINE_ASSET_SINCE,
                     "platform": platform_name, "manifest_keys": sorted(k for k in manifest if isinstance(k, str))},
        )

    # ---- 卸载 / 状态 ----------------------------------------------------------------------------------------------------

    def uninstall_engine_only(self, *, yes: bool = False) -> dict[str, Any]:
        """只删 engine-only 资产（`core-js/` 与可能残留的 `core-js.previous/`）；离线 runtime、数据目录一概不动。默认 dry-run。"""
        from horosa_skill.runtime import purge

        plan = [str(path) for path in engine_paths(self.runtime_root) if path.exists() or path.is_symlink()]
        if not yes:
            return {"ok": True, "dry_run": True, "mode": "engine_only", "would_remove": plan,
                    "next_action": bilingual("确认后加 --yes 执行（只删 JS 引擎资产）。", "Add --yes to remove (the JS engine asset only).")}
        removed: list[str] = []
        for text in plan:
            try:
                purge.remove_owned(Path(text))
            except OSError as exc:
                raise RuntimeInstallError(
                    bilingual(f"删不掉 {text}：{exc}", f"Failed to remove {text}: {exc}"),
                    code="runtime.uninstall_failed",
                    details={"path": text, "removed_so_far": removed},
                ) from exc
            removed.append(text)
        return {"ok": True, "dry_run": False, "mode": "engine_only", "removed": removed}

    def engine_asset_status(self) -> dict[str, Any]:
        root = installed_engine_root(self.runtime_root)
        record = read_record(self.runtime_root) or {}
        return {
            "installed": root is not None,
            "root": str(root) if root else None,
            "version": record.get("version"),
            "sha256": record.get("sha256"),
            "installed_at": record.get("installed_at"),
            "source": record.get("source"),
        }


def installed_engine_root_of(base: Path) -> bool:
    return (base / ENGINE_RECORD_NAME).is_file() and (base / ENGINE_ASSET_ROOT / "bin" / "cli.mjs").is_file()


__all__ = [
    "ENGINE_ASSET_MANIFEST_KEY", "ENGINE_ASSET_REQUIRED_ENTRIES", "ENGINE_ASSET_ROOT", "ENGINE_ASSET_SINCE", "ENGINE_ASSET_TEMPLATE",
    "ENGINE_DIRNAME", "EngineAssetMixin", "engine_dir", "engine_only_command", "engine_paths", "installed_engine_root",
    "manifest_has_engine_asset", "read_record",
]
