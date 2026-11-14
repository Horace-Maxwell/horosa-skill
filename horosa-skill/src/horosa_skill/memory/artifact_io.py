"""存档产物的读写口（审计待决项 7：保留与压缩）。

新写的产物存 `*.json.gz`（标准库 gzip、level 6、头里 mtime=0：同样的内容压出同样的字节），读的地方两种后缀都认。manifest 照旧明文
（人要能读）。实测 131 个真实产物 gzip 后剩 18%；1 万条 2.22 GB → 约 0.4 GB。`memory compact` 把旧产物一次压掉，`--decompress` 反过来
（降级到读不了 .json.gz 的旧版本之前先跑它）。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

SUFFIXES = (".json", ".json.gz")
GZIP_LEVEL = 6


def is_json_artifact(path: Path) -> bool:
    return path.name.lower().endswith(SUFFIXES)


def read_text(path: Path) -> str:
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def encode(payload: Any, *, compress: bool) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(data, compresslevel=GZIP_LEVEL, mtime=0) if compress else data


def compressed_name(path: Path) -> Path:
    return path if path.name.endswith(".gz") else path.with_name(path.name + ".gz")


def plain_name(path: Path) -> Path:
    return path.with_name(path.name[:-3]) if path.name.endswith(".gz") else path
