"""太乙 / 三式合一择时的性能回归（v0.47.2-dev，Windows 原生复验）。

每扫一个小时，calcTaiyi → buildBaziCore → buildSmallDirection 都逐年排一遍约百年的流年表；lunar-javascript 只缓存一个 LunarYear、构造一次要重算
31 个节气，于是一周窗口要 30 秒（90% 在 lunar.js），超过约 9 天撞 60 秒墙钟。`src/shared/lunarYearCache.js` 把缓存撑到大于一次横扫。
不比耗时（CI 上不稳），比「第二遍横扫拿到的是不是同一批对象」：第一版容量 32，小于百年横扫，LRU 命中率恒为 0——实测一点没快，而「有缓存」的
断言照样能绿，所以这里按真实横扫的长度断言。修前修后全部技法引擎输出逐字节相同由 2026-11-05 本机重放验证（台账）。
"""

from __future__ import annotations

import json
from pathlib import Path

from node_esm import run_node_esm

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"

_SWEEP = """
const { LunarYear } = await import('lunar-javascript');
await import(process.argv[1]);
const years = Array.from({ length: 150 }, (_, i) => 1900 + i);
const first = years.map((y) => LunarYear.fromYear(y));
const second = years.map((y) => LunarYear.fromYear(y));
console.log(JSON.stringify({
  hits: first.filter((item, i) => item === second[i]).length,
  right_year: first.every((item, i) => item.getYear() === years[i]),
  terms: first[100].getJieQiJulianDays().length,
}));
"""


def test_a_century_sweep_is_served_from_the_cache_through_the_engine_entry_point() -> None:
    """走 tools/index.js（引擎真实入口）：既锁「缓存装上了」，也锁「容量大于一次横扫」。"""
    out = json.loads(run_node_esm(_SWEEP, CORE_JS / "src" / "tools" / "index.js", cwd=CORE_JS))
    assert out == {"hits": 150, "right_year": True, "terms": 31}


def test_cached_year_matches_a_fresh_library_computation() -> None:
    script = """
const lunar = await import('lunar-javascript');
const { LunarYear } = lunar;
const fresh = LunarYear.fromYear;
const freshDays = (y) => JSON.stringify(fresh(y).getJieQiJulianDays());
const before = [1900, 1969, 2026, 2028].map(freshDays);
await import(process.argv[1]);
const after = [1900, 1969, 2026, 2028].map((y) => JSON.stringify(LunarYear.fromYear(y).getJieQiJulianDays()));
console.log(JSON.stringify({ same: before.every((value, i) => value === after[i]) }));
"""
    assert json.loads(run_node_esm(script, CORE_JS / "src" / "shared" / "lunarYearCache.js", cwd=CORE_JS)) == {"same": True}
