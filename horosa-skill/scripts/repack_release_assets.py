#!/usr/bin/env python3
"""Repack a previously published runtime archive under a new release version.

**何时用**：一次发布**不含 payload-affecting 变化**（引擎、core-js、启动器包内容都没动，改动全在
Python 包或安装侧补丁）时，重新构建一份字节相同的载荷既慢又需要那台平台专用的构建机。
Windows 半边尤其如此 —— 它的构建输入（`vendor/runtime-source/runtime/windows`、`prepareruntime`）
**只存在于 Windows 构建机上**，mac 上根本无从构建。

**它做什么**：把归档里唯一一处带版本号的文件 —— `runtime-payload/runtime-manifest.json` 的
`version` / `runtime_payload_version` —— 改写成新版本，**其余字节一律原样搬运**。
`verify_runtime_release.py::_assert_payload_manifest` 要求嵌入的清单版本等于发布清单版本，
所以这一处非改不可；而 `_assert_entries` 与 `_assert_windows_launchers_are_bom_encoded`
要求别的条目（含 .ps1 的 UTF-8 BOM）分毫不动，所以这里按条目原样复制，绝不重新编码。

**它不做什么**：不碰引擎、不碰 core-js、不重新打包目录树。真有 payload 变化时**不要**用它 ——
用平台各自的 builder 重建。

用法：
    uv run python scripts/repack_release_assets.py \\
        --source horosa-runtime-win32-x64-v0.36.0.zip \\
        --out    horosa-runtime-win32-x64-v0.37.0.zip \\
        --version 0.37.0
之后照常跑 `verify_runtime_release.py --windows-archive <out> --manifest <新清单>`。
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

PAYLOAD_MANIFEST = "runtime-payload/runtime-manifest.json"


def _rewritten_manifest(raw: bytes, version: str) -> bytes:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{PAYLOAD_MANIFEST} is not a JSON object")
    data["version"] = version
    if "runtime_payload_version" in data:
        data["runtime_payload_version"] = version
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def repack_zip(source: Path, out: Path, version: str) -> int:
    seen = 0
    with zipfile.ZipFile(source) as src:
        if PAYLOAD_MANIFEST not in src.namelist():
            raise SystemExit(f"{source.name} has no {PAYLOAD_MANIFEST}")
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                payload = src.read(info.filename)
                if info.filename == PAYLOAD_MANIFEST:
                    payload = _rewritten_manifest(payload, version)
                    # 长度变了 → 必须用新的 ZipInfo，但保留原有的时间戳与外部属性（权限位）。
                    new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    new_info.external_attr = info.external_attr
                    new_info.compress_type = info.compress_type
                    dst.writestr(new_info, payload)
                else:
                    dst.writestr(info, payload)
                seen += 1
    return seen


def repack_tar(source: Path, out: Path, version: str) -> int:
    seen = 0
    with tarfile.open(source, "r:gz") as src, tarfile.open(out, "w:gz") as dst:
        members = src.getmembers()
        if not any(m.name == PAYLOAD_MANIFEST for m in members):
            raise SystemExit(f"{source.name} has no {PAYLOAD_MANIFEST}")
        for member in members:
            if member.name == PAYLOAD_MANIFEST:
                handle = src.extractfile(member)
                if handle is None:
                    raise SystemExit(f"cannot read {PAYLOAD_MANIFEST} from {source.name}")
                payload = _rewritten_manifest(handle.read(), version)
                info = tarfile.TarInfo(member.name)
                info.size = len(payload)
                info.mode, info.mtime = member.mode, member.mtime
                info.uid, info.gid = member.uid, member.gid
                info.uname, info.gname = member.uname, member.gname
                dst.addfile(info, io.BytesIO(payload))
            else:
                # 目录/符号链接没有数据流；extractfile 对它们返回 None。
                dst.addfile(member, src.extractfile(member) if member.isreg() else None)
            seen += 1
    return seen


def main() -> int:
    # 🔴 Windows 控制台默认 cp1252：脚本自己的输出里出现任何非 ASCII 字符（一个 `→` 就够）
    # 会抛 UnicodeEncodeError 并让脚本 exit 1 —— 发布脚本因此在最后一步「打印成功信息」时失败。
    # 这与 v0.25.1 的 `.ps1` BOM 是同一族：Windows 的默认编码不是 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="已发布的归档（.zip / .tar.gz）")
    parser.add_argument("--out", required=True, help="输出归档路径")
    parser.add_argument("--version", required=True, help="新的发布版本，例如 0.37.0")
    args = parser.parse_args()

    source, out = Path(args.source).expanduser(), Path(args.out).expanduser()
    if not source.is_file():
        raise SystemExit(f"source archive not found: {source}")
    if out.exists():
        raise SystemExit(f"refusing to overwrite an existing archive: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    tmp = out.with_suffix(out.suffix + ".partial")
    try:
        name = source.name.lower()
        if name.endswith(".zip"):
            count = repack_zip(source, tmp, args.version)
        elif name.endswith((".tar.gz", ".tgz")):
            count = repack_tar(source, tmp, args.version)
        else:
            raise SystemExit(f"unsupported archive type: {source.name}")
        tmp.replace(out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    print(f"repacked {count} entries -> {out} (embedded manifest version = {args.version})")
    print("next: uv run python scripts/verify_runtime_release.py --manifest <release manifest> "
          f"--{'windows' if out.name.endswith('.zip') else 'darwin'}-archive {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
