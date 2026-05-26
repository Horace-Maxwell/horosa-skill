import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { buildTaiyiSnapshotText, calcTaiyi, normalizeBackendPan } from '../vendor/taiyi/TaiYiCalc.js';

export function runTaiyi(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const fields = makeFields(normalized);
  const nongli = unwrapNamedObject(normalized.nongli, 'nongli') || null;
  // ken (kintaiyi) is the compute authority; normalizeBackendPan reformats it into the
  // pan shape buildTaiyiSnapshotText expects (星阙 aiExport.js sections). Local calcTaiyi
  // is only a fallback when no ken response is supplied.
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  const pan = ken && typeof ken === 'object' && (ken.raw || ken.kook || ken.palace16)
    ? normalizeBackendPan(ken, normalized.options || {}, nongli)
    : calcTaiyi(fields, nongli, normalized.options || {});
  if (!pan) {
    throw new Error('Taiyi calculation returned no result.');
  }
  return {
    tool: 'taiyi',
    technique: 'taiyi',
    input_normalized: normalized,
    data: pan,
    // 星阙 aiExport for taiyi is 起盘信息/太乙盘/十六宫标记 only; drop ken's in-app detail
    // `sections` from the snapshot (kept in `data`) so the export contract stays clean.
    snapshot_text: buildTaiyiSnapshotText({ ...pan, sections: undefined }),
  };
}
