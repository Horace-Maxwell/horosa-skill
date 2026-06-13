// progextra: run a vendored 星阙 progression builder (balbillus / triplicityrulers / keypoints /
// lunationphase) on a chart object. These are pure frontend builders (read the chart, output the
// single-section text); the skill passes the /chart response as payload.chart. Returns { snapshot_text }.
import { buildBalbillusSnapshotText } from '../vendor/astroextra/balbillus.js';
import { buildTriplicityRulersSnapshotText } from '../vendor/astroextra/triplicityRulers.js';
import { buildKeypointsSnapshotText } from '../vendor/astroextra/keypoints120.js';
import { buildLunationPhaseSnapshotText } from '../vendor/astroextra/lunationPhase.js';

const BUILDERS = {
  balbillus: buildBalbillusSnapshotText,
  triplicityrulers: buildTriplicityRulersSnapshotText, // 三分主星推运 (星阙 v2.6.x)
  keypoints: buildKeypointsSnapshotText, // 数字相位推运
  lunationphase: buildLunationPhaseSnapshotText, // 月相推运
};

export function runProgExtra(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const technique = `${input.technique || ''}`;
  const chartObj = input.chart && input.chart.chart ? input.chart : { chart: (input.chart || {}).chart || (input.chart || {}) };
  const builder = BUILDERS[technique];
  if (!builder) {
    return { tool: 'progextra', technique, data: { ok: false, reason: 'unknown_technique' }, snapshot_text: '' };
  }
  let snapshot_text = '';
  try {
    snapshot_text = builder(chartObj) || '';
  } catch (error) {
    snapshot_text = '';
  }
  return { tool: 'progextra', technique, data: { ok: true }, snapshot_text };
}
