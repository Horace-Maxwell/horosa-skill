import { buildLocalJieqiYearSeed } from '../shared/localNongliAdapter.js';
import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import {
  buildJieqiYearSeed,
  buildDunJiaSnapshotText,
  calcDunJia,
  normalizeKinqimenData,
  isQimenLocalRoute,
  qimenLocalOnlyOverrides,
} from '../vendor/dunjia/DunJiaCalc.js';

function inferYear(dateText) {
  return parseInt(`${dateText}`.slice(0, 4), 10);
}

function buildYearSeed(result, year, zone) {
  const raw = unwrapResultEnvelope(result);
  if (raw && typeof raw === 'object' && Array.isArray(raw.jieqi24) && raw.jieqi24.length > 0) {
    return buildJieqiYearSeed(raw);
  }
  return buildLocalJieqiYearSeed(year, zone);
}

export function runQimen(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const fields = makeFields(normalized);
  const nongli = unwrapNamedObject(normalized.nongli, 'nongli') || null;
  const year = inferYear(normalized.date);
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
