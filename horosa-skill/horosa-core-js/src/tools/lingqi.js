// 灵棋经（上游 v3.9.0）：无后端引擎，纯前端古法起卦 + 七段快照。
// 掷十二棋（上4/中4/下4）→ counts[上,中,下] → 六十四卦查表 → [起盘信息]/[棋势]/[卦象]/[繇辞]/
// [诸家注]/[课断]/[断诗] 七段恒出（段头恒定，注家开关只影响段内行——上游 parityAll 双向哨兵口径）。
//
// 🔴 确定性：headless **只**走占时种子（`resolveLingqiSeed('time_seed', …)` → `t-<int>`），
//    与 geomancy / tarot 的「以起卦时刻确定性起卦」同款。上游的 random 档读 `window.crypto`，
//    headless 无 window 会落到 `Math.random()` —— 那会让同一时刻两次调用得到不同卦，
//    既违背古法「不可再擲」，也让 golden/回归测试无从写起。故此处不暴露 random 档。
// 🔴 卦是冻结值：调用方给了 `counts` 就照它复排，绝不重掷（读档/事盘纪律）。
import { buildLingqiSnapshotText } from '../vendor/lingqi/lingqiSnapshot.js';
import { castLingqi, resolveLingqiSeed, isWuDay } from '../vendor/lingqi/core/lingqiCast.js';

// 上游 computeTimeSeed 读的是 antd/dayjs 的 `{ value: { format(fmt) } }`；headless 侧用等价 shim 喂它，
// 而不是在这边另写一份取种逻辑——种子算法留在 vendored 文件里，才不会两边悄悄分叉。
function fieldsFor({ year, month, day, hour, minute }) {
  const pad = (n, width) => `${n}`.padStart(width, '0');
  const format = (fmt) => ({
    YYYY: pad(year, 4),
    MM: pad(month, 2),
    DD: pad(day, 2),
    HH: pad(hour, 2),
    mm: pad(minute, 2),
  }[fmt] || '');
  return { date: { value: { format } }, time: { value: { format } } };
}

function normalizedCounts(raw) {
  if (!Array.isArray(raw) || raw.length !== 3) { return null; }
  const out = raw.map((value) => {
    const n = Math.floor(Number(value));
    return Number.isFinite(n) ? Math.min(4, Math.max(0, n)) : null;
  });
  return out.every((n) => n !== null) ? out : null;
}

export function runLingqi(payload) {
  try {
    const p = payload && typeof payload === 'object' ? payload : {};
    const parts = {
      year: Number(p.year), month: Number(p.month), day: Number(p.day),
      hour: Number(p.hour), minute: Number(p.minute),
    };
    if (!Object.values(parts).every((n) => Number.isFinite(n))) {
      return { snapshot_text: '' };
    }
    const fields = fieldsFor(parts);
    const seed = resolveLingqiSeed('time_seed', null, fields);
    // 冻结优先：调用方带 counts（读档/重算）就复排，否则按占时种子掷一次。
    const counts = normalizedCounts(p.counts) || castLingqi(seed).counts;

    const zhuVisible = {};
    ['yan', 'he', 'chen', 'liu', 'ke', 'shi'].forEach((key) => {
      const value = p.zhuVisible && p.zhuVisible[key];
      if (value !== undefined && value !== null && value !== '') {
        zhuVisible[key] = (value === 1 || value === '1' || value === true);
      }
    });

    const snapshotText = buildLingqiSnapshotText({
      counts,
      question: p.question || '',
      category: p.category || 'general',
      zhuVisible,
      // 六戊日提示：日干由 Python 侧经 /nongli/time 归一后传入（引擎自带 dayGanZi 兜底口径）。
      wuDay: isWuDay(p.nongli || (p.dayGanZi ? { dayGanZi: p.dayGanZi } : null)),
      timeLines: Array.isArray(p.timeLines) ? p.timeLines : [],
    });
    if (!snapshotText || !snapshotText.trim()) {
      return { snapshot_text: '' };
    }
    return { snapshot_text: snapshotText, counts, seed };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
