import { buildLocalJieqiYearSeed } from '../vendor/utils/localNongliAdapter.js';
import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { dateKeyOfStr } from '../vendor/bazi/dateStrSafe.js';
import {
  buildDunJiaSnapshotText,
  calcDunJia,
  normalizeKinqimenData,
  isQimenLocalRoute,
  qimenLocalOnlyOverrides,
} from '../vendor/dunjia/DunJiaCalc.js';

// 上游 DunJiaMain（:1765）`parseInt(flds.date.value.format('YYYY'), 10)`：DateTime 的 ad × year（带符号显示年）。
// 旧 slice(0, 4) 把公元前 '-0500-03-21' 切成 -50、五位年 '10000-…' 切成 1000 → 节气种子年键全错。
// Python 侧 _run_qimen_tool 按同一口径取年拉 jieqi_year_prev/current，两边年键必须一致。
function inferYear(fields) {
  return parseInt(fields.date.value.format('YYYY'), 10);
}

// 后端 jieqi24 → 节气种子。上游 v3.12.0 删掉了 DunJiaCalc.buildJieqiYearSeed，同一转换收进网络模块
// utils/preciseCalcBridge.js 的 fetchPreciseJieqiSeed（:459-476，不 vendor：它自带 request）。这里逐字照它：
// 日期键走 dateKeyOfStr（带符号年份，公元前 / 五位年不误读）、节气名原样、日干支先认 dayGanzhi / dayGanZhi 再回落四柱日柱。
function safeText(v, d = '') {
  return v === undefined || v === null ? d : `${v}`;
}
function seedDateKey(time) {
  const txt = safeText(time);
  if (!txt) {
    return '';
  }
  return dateKeyOfStr(txt.split(' ')[0] || '');
}
function seedDayGanzhi(entry) {
  if (entry && entry.dayGanzhi) {
    return safeText(entry.dayGanzhi);
  }
  if (entry && entry.dayGanZhi) {
    return safeText(entry.dayGanZhi);
  }
  const bazi = entry && entry.bazi ? entry.bazi : null;
  const four = bazi && bazi.fourColumns ? bazi.fourColumns : null;
  const day = four && four.day ? four.day : null;
  return safeText((day && (day.ganzi || day.ganZhi)) || '');
}
export function jieqiSeedFromYearResult(yearRes) {
  if (!yearRes || !Array.isArray(yearRes.jieqi24)) {
    return null;
  }
  const seed = {};
  yearRes.jieqi24.forEach((entry) => {
    const term = safeText(entry && entry.jieqi);
    if (!term) {
      return;
    }
    const time = safeText(entry && entry.time);
    seed[term] = {
      term,
      time,
      dateKey: seedDateKey(time),
      dayGanzhi: seedDayGanzhi(entry),
    };
  });
  return Object.keys(seed).length ? seed : null;
}

function buildYearSeed(result, year, zone) {
  const raw = unwrapResultEnvelope(result);
  if (raw && typeof raw === 'object' && Array.isArray(raw.jieqi24) && raw.jieqi24.length > 0) {
    const seed = jieqiSeedFromYearResult(raw);
    if (seed) {
      return seed;
    }
  }
  return buildLocalJieqiYearSeed(year, zone);
}

export function runQimen(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const fields = makeFields(normalized);
  const nongli = unwrapNamedObject(normalized.nongli, 'nongli') || null;
  const year = inferYear(fields);
  const options = normalized.options || {};
  const seeds = {
    [year - 1]: buildYearSeed(normalized.jieqi_year_prev, year - 1, normalized.zone),
    [year]: buildYearSeed(normalized.jieqi_year_current, year, normalized.zone),
  };
  // 日家/金函腊月过冬至需次年至日（上游 jieqiSeedYears：y-1,y,y+1）；Python 只在这两家时拉次年种子。
  if (normalized.jieqi_year_next) {
    seeds[year + 1] = buildYearSeed(normalized.jieqi_year_next, year + 1, normalized.zone);
  }
  const context = {
    ...(normalized.context || {}),
    year,
    displaySolarTime: normalized.context?.displaySolarTime ?? (nongli ? nongli.birth || '' : ''),
    jieqiYearSeeds: seeds,
  };
  const fallback = calcDunJia(fields, nongli, options, context);
  if (!fallback) {
    throw new Error('Qimen calculation returned no result.');
  }
  // 路由单源 = vendored isQimenLocalRoute（上游 DunJiaMain.getResolvedPan 同判据）：本地家/飞盘/混合/报数/
  // 七组本地口径 → 本地 calcDunJia 就是成品盘；其余由 ken（kinqimen）算盘、叠到本地脚手架上出 aiExport 段。
  // Python 先按同一判据决定打不打 ken，这里把结论回报（route），两边不一致由 Python 报 tool.qimen_route_check_failed。
  const localRoute = isQimenLocalRoute(options);
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  const hasKen = !!(ken && typeof ken === 'object' && (ken.selected || ken.raw));
  if (localRoute && hasKen) {
    throw new Error(`qimen route drift: isQimenLocalRoute=true (${qimenLocalOnlyOverrides(options).join(',') || 'paiPanType/school/qijuMethod'}) but a ken_response was supplied`);
  }
  const pan = !localRoute && hasKen
    ? normalizeKinqimenData(ken, fallback, options, nongli)
    : fallback;
  // 法奇门「相关人员」生年干：Python 侧已归一化为 [{name, yearGan}]；按上游四同步语义
  // stamp 到 pan（显式数组为准；缺省不 stamp → computeProtect 不出「生年干·」行）。
  if (Array.isArray(payload.faRelatedPeople)) {
    pan.faRelatedPeople = payload.faRelatedPeople;
  }
  return {
    tool: 'qimen',
    technique: 'qimen',
    input_normalized: normalized,
    data: pan,
    route: { local: localRoute, overrides: qimenLocalOnlyOverrides(options) },
    snapshot_text: buildDunJiaSnapshotText(pan),
  };
}
