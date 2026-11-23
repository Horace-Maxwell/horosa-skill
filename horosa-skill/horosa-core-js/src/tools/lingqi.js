// 灵棋经（上游 v3.9.0）：无后端引擎，纯前端古法起卦 + 七段快照。
// 掷十二棋（上4/中4/下4）→ counts[上,中,下] → 六十四卦查表 → [起盘信息]/[棋势]/[卦象]/[繇辞]/
// [诸家注]/[课断]/[断诗] 七段恒出（段头恒定，注家开关只影响段内行——上游 parityAll 双向哨兵口径）。
//
// 起卦（v3.15.0 起同上游页面缺省 seedMode 'random'）：三档与上游 resolveLingqiSeed 同名同义——
//    random（缺省）= 当场取系统随机记录 tr1-…（vendored trueRandom.js：Node crypto，取不到就报错、绝不退回伪随机），
//    time_seed = 占时种子 `t-<int>`（同刻同卦），seed 显式 = 手动档（整数串 / 上次回传的 tr1- 记录，原样重开）。
//    回传 seed + counts：传回 seed 或 counts 都能重开同一卦。
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
    const frozen = normalizedCounts(p.counts);
    const explicitSeed = p.seed !== undefined && p.seed !== null && `${p.seed}`.trim() !== '' ? `${p.seed}`.trim() : null;
    const seedMode = explicitSeed ? 'manual' : (p.seedMode === 'time_seed' ? 'time_seed' : 'random');
    // 冻结优先：调用方带 counts（读档/重算）就复排、不取种子；否则按所选档取种子掷一次。
    const seed = frozen ? null : resolveLingqiSeed(seedMode, explicitSeed, fields);
    const counts = frozen || castLingqi(seed).counts;

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
    return { snapshot_text: snapshotText, counts, seed, seed_mode: frozen ? 'counts' : seedMode };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
