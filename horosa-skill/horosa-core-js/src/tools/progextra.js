// progextra: run a vendored 星阙 v2.5.0 progression builder (balbillus / persiandirected / yearsystem129)
// on a chart object. These are pure frontend builders (read the chart, output the single-section text);
// the skill passes the /chart response as payload.chart. Returns { snapshot_text }.
import { buildBalbillusSnapshotText } from '../vendor/astroextra/balbillus.js';

const BUILDERS = {
  balbillus: buildBalbillusSnapshotText,
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
