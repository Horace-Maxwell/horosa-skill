// lunar-javascript 只缓存**一个** LunarYear（lunar.js `_CACHE_YEAR`），而一次构造要按天文级数重算 31 个节气（`eLon`）。
// 太乙择时每个小时都经 calcTaiyi → buildBaziCore → buildSmallDirection 逐年排一遍约百年的流年表，单格缓存每次都被挤掉：v0.47.2-dev 实测一周窗口 90% 的时间耗在 lunar.js、63% 在 eLon，
// 约 0.25 秒 / 小时，超过约 9 天就撞 60 秒引擎墙钟。LunarYear 是年份的纯函数、库本身就共享实例，所以多留几年不改变任何结果
// （tests/test_lunar_year_cache.py：全部技法的引擎输出修前修后逐字节对比）。不改库、不改 vendored 上游：
// 库内所有调用都走 `LunarYear.fromYear` 这个公开属性，在这里包一层即可。
import { LunarYear } from 'lunar-javascript';

// 必须大于一次横扫的年数：buildSmallDirection 每起一盘就逐年排一遍约百年的流年表，LRU 容量小于它时每次都在用到之前被挤掉，命中率恒为 0
// （第一版写 32，实测一点没快）。进程只活一次工具调用，每年几 KB，占用有界。
const MAX_YEARS = 1024;
const cache = new Map();
const fromYearUncached = LunarYear.fromYear;

LunarYear.fromYear = function fromYear(lunarYear) {
  const hit = cache.get(lunarYear);
  if (hit !== undefined) {
    cache.delete(lunarYear);
    cache.set(lunarYear, hit);
    return hit;
  }
  const built = fromYearUncached.call(LunarYear, lunarYear);
  if (cache.size >= MAX_YEARS) cache.delete(cache.keys().next().value);
  cache.set(lunarYear, built);
  return built;
};
