import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject } from '../shared/unpack.js';
import { buildTaiyiSnapshotText, calcTaiyi } from '../vendor/taiyi/TaiYiCalc.js';

export function runTaiyi(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const fields = makeFields(normalized);
  const nongli = unwrapNamedObject(normalized.nongli, 'nongli') || null;
  const pan = calcTaiyi(fields, nongli, normalized.options || {});
  if (!pan) {
    throw new Error('Taiyi calculation returned no result.');
  }
  return {
    tool: 'taiyi',
    technique: 'taiyi',
    input_normalized: normalized,
    data: pan,
    snapshot_text: buildTaiyiSnapshotText(pan),
  };
}
