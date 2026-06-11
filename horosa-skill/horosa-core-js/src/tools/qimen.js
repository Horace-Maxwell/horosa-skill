import { buildLocalJieqiYearSeed } from '../shared/localNongliAdapter.js';
import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { buildJieqiYearSeed, buildDunJiaSnapshotText, calcDunJia, normalizeKinqimenData } from '../vendor/dunjia/DunJiaCalc.js';

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
  const context = {
    ...(normalized.context || {}),
    year,
    displaySolarTime: normalized.context?.displaySolarTime ?? (nongli ? nongli.birth || '' : ''),
    jieqiYearSeeds: {
      [year - 1]: buildYearSeed(normalized.jieqi_year_prev, year - 1, normalized.zone),
      [year]: buildYearSeed(normalized.jieqi_year_current, year, normalized.zone),
    },
  };
  const fallback = calcDunJia(fields, nongli, normalized.options || {}, context);
  if (!fallback) {
    throw new Error('Qimen calculation returned no result.');
  }
  // ken is the sole compute authority: overlay the kinqimen backend response onto the
  // local scaffold so buildDunJiaSnapshotText still emits 星阙 aiExport.js sections.
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  const pan = ken && typeof ken === 'object' && (ken.selected || ken.raw)
    ? normalizeKinqimenData(ken, fallback, normalized.options || {}, nongli)
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
    snapshot_text: buildDunJiaSnapshotText(pan),
  };
}
