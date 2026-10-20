"""服务层读「现在几点」的唯一出口。

技法缺省（流年 = 今年、返照目标 = 今年生日、当前时点…）都取现在时刻；测试要冻结时间就 patch 本模块的 `datetime`
（tests/test_sync311_newtools.py 的 frozen 夹具）。调用方一律 `_clock.now(...)`、运行时按属性查，别 `from … import now`
——早绑定会绕过 patch。service 包里不许再直接写 `datetime.now(`（tests/test_service_structure.py 锁）。
"""
from __future__ import annotations

from datetime import datetime, tzinfo


def now(tz: tzinfo | None = None) -> datetime:
    return datetime.now(tz)
