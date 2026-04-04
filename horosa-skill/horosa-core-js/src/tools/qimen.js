import { buildLocalJieqiYearSeed } from '../shared/localNongliAdapter.js';
import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { buildJieqiYearSeed, buildDunJiaSnapshotText, calcDunJia } from '../vendor/dunjia/DunJiaCalc.js';

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
  const pan = calcDunJia(fields, nongli, normalized.options || {}, context);
  if (!pan) {
    throw new Error('Qimen calculation returned no result.');
  }
  return {
    tool: 'qimen',
    technique: 'qimen',
    input_normalized: normalized,
    data: pan,
    snapshot_text: buildDunJiaSnapshotText(pan),
  };
}
