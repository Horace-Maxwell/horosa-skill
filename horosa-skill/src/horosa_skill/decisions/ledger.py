"""本地决策账本（jsonl，只在本机 data_dir）。评测回放、影子期核对、阈值编译都读它。

记的是：面 / 模式 / 请求与返回的模型 id / 状态摘要（sha256 + 前 200 字脱敏预览）/ 紧凑答案 /
延迟 / 是否采纳 / 错误码。**永不**记 key、原始未脱敏文本、导出快照全文。写失败只记 debug 日志，
账本从来不是技法调用失败的理由。
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
LEDGER_FILENAME = "jev_events.jsonl"


class DecisionLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict[str, Any]) -> bool:
        payload = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            with self._lock, self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return True
        except (OSError, TypeError, ValueError):
            logger.debug("decision ledger append failed", exc_info=True)
            return False

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)):]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def count(self) -> int:
        if not self.path.is_file():
            return 0
        try:
            return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            return 0
