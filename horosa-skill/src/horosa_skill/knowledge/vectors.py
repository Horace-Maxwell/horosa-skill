"""自备知识库的可选向量检索：BAAI/bge-small-zh-v1.5（int8 ONNX，24 MB）+ onnxruntime，与 BM25 做倒数排名融合。

为什么可选（2026-10 调研，docs/LESSONS.md v0.45.1-dev）：
- 术数笔记的查询多是术语（命宫、伤官见官），双字 BM25 已经够准；向量补的是**换了说法**的查询
  （「身弱不能担财」↔「财多身弱，富屋贫人」：BM25 一个字都对不上，bge 排第一）。
- 依赖重：onnxruntime + tokenizers + numpy 装好约 128 MB，模型另 24 MB——放在 `horosa-skill[vectors]` 里，
  默认安装不变。三个包在 macOS arm64 / Windows x64 / Windows ARM64 都有 cp312 轮子；fastembed 不用（它的
  py-rust-stemmers 没有 win_arm64 轮子）。
- 模型只在用户明确要时才下（`horosa-skill knowledge index --vectors`）：钉 Hugging Face 的提交号 + sha256，
  校验不过不用。也可以把两份文件放进 `HOROSA_EMBED_MODEL_DIR` 指的目录（离线机器）。

任何一环缺了（没装依赖、没下模型、`HOROSA_KNOWLEDGE_VECTORS=0`）都只是退回纯 BM25，不报错。
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

MODEL_NAME = "bge-small-zh-v1.5-int8"
MODEL_REPO = "Xenova/bge-small-zh-v1.5"
MODEL_COMMIT = "75c43b069aac4d136ba6bc1122f995fedcfd2781"
MODEL_FILES = {
    "onnx/model_int8.onnx": "b9837c19ce154ff0726d398ee77abbc03a7faf0476c6f93016c84e531be7ebb5",
    "tokenizer.json": "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26",
}
DIMENSIONS = 512
# bge 中文版的检索指令：只加在**查询**前，文档不加（模型卡的用法）。
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
MIN_COSINE = 0.5  # 只靠向量进来的候选要过这条线（bge 相关句约 0.6+，无关约 0.3–0.4），免得什么都「有点像」
MAX_TOKENS = 512


def enabled_by_env() -> bool:
    return os.environ.get("HOROSA_KNOWLEDGE_VECTORS", "1").strip().lower() not in {"0", "false", "off"}


def deps_available() -> bool:
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError:
        return False
    return True


def model_dir(settings: Any) -> Path:
    explicit = os.environ.get("HOROSA_EMBED_MODEL_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    from horosa_skill.knowledge.user import state_dir

    return state_dir(settings) / "models" / MODEL_NAME


_VERIFIED: dict[str, tuple[int, int]] = {}  # 文件 → 校验通过时的 (大小, mtime)；同一进程不重复算 24 MB 的哈希
_VERIFIED_LOCK = threading.Lock()


def _file_ok(path: Path, sha256: str) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    stamp = (stat.st_size, stat.st_mtime_ns)
    with _VERIFIED_LOCK:
        if _VERIFIED.get(str(path)) == stamp:
            return True
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != sha256:
        return False
    with _VERIFIED_LOCK:
        _VERIFIED[str(path)] = stamp
    return True


def model_ready(settings: Any) -> bool:
    folder = model_dir(settings)
    return all(_file_ok(folder / name, sha) for name, sha in MODEL_FILES.items())


def ready(settings: Any) -> bool:
    return enabled_by_env() and deps_available() and model_ready(settings)


def status(settings: Any) -> dict[str, Any]:
    folder = model_dir(settings)
    return {
        "model": MODEL_NAME,
        "enabled_by_env": enabled_by_env(),
        "deps_installed": deps_available(),
        "model_present": model_ready(settings),
        "model_dir": str(folder),
        "how_to_enable": "uv tool install 'horosa-skill[vectors]'（或 pip install onnxruntime tokenizers numpy），"
                         "再运行 `horosa-skill knowledge index --vectors` 下载并校验模型（24 MB）。",
    }


def download(settings: Any, *, timeout: float = 120.0) -> dict[str, Any]:
    """按钉死的提交号下载两份文件，sha256 对上才落盘（临时文件 → 原子替换）。已就绪就不下。"""
    import httpx

    folder = model_dir(settings)
    fetched = []
    for name, sha in MODEL_FILES.items():
        target = folder / name
        if _file_ok(target, sha):
            continue
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_COMMIT}/{name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".horosa-", suffix=".part")
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as handle, httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
                response.raise_for_status()
                for block in response.iter_bytes(1 << 20):
                    handle.write(block)
                    digest.update(block)
            if digest.hexdigest() != sha:
                raise ValueError(f"{name} 的 sha256 对不上（{digest.hexdigest()} ≠ {sha}），已丢弃")
            os.replace(tmp, target)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        fetched.append(name)
    return {"downloaded": fetched, **status(settings)}


class Embedder:
    """bge-small-zh：CLS 池化 + L2 归一（模型卡的用法）。一个模型目录一个实例，线程安全（onnxruntime 会话可并发 run）。"""

    def __init__(self, folder: Path) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_truncation(MAX_TOKENS)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        self._session = ort.InferenceSession(str(folder / "onnx" / "model_int8.onnx"), options,
                                             providers=["CPUExecutionProvider"])
        self._inputs = {item.name for item in self._session.get_inputs()}

    def embed(self, texts: list[str], *, query: bool = False, batch: int = 16) -> Any:
        import numpy as np

        out = []
        for start in range(0, len(texts), batch):
            chunk = [(QUERY_PREFIX + t) if query else t for t in texts[start:start + batch]]
            encoded = self._tokenizer.encode_batch(chunk)
            feed = {"input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
                    "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64)}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
            vectors = self._session.run(None, feed)[0][:, 0]
            out.append(vectors / np.linalg.norm(vectors, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32) if out else np.zeros((0, DIMENSIONS), dtype=np.float32)


_EMBEDDERS: dict[str, Any] = {}
_EMBEDDERS_LOCK = threading.Lock()


def embedder(settings: Any) -> Any:
    """测试替身从这里换（monkeypatch `embedder`）。调用方先确认 ready()。"""
    folder = str(model_dir(settings))
    with _EMBEDDERS_LOCK:
        if folder not in _EMBEDDERS:
            _EMBEDDERS[folder] = Embedder(Path(folder))
        return _EMBEDDERS[folder]
