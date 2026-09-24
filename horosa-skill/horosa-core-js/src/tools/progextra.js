// progextra: run a vendored 星阙 progression builder (balbillus / triplicityrulers / keypoints /
// lunationphase) on a chart object. These are pure frontend builders (read the chart, output the
// single-section text); the skill passes the /chart response as payload.chart. Returns { snapshot_text }.
//
// payload.options → the builder's `opts` (上游 techniqueMountSettings.js:1237-1274 的挂载齿轮 =
// aiAnalysisContext.js:2998-3013 regen 传给 builder 的同一组键)：
//   balbillus        { startPlanet, yearType, mode }
//   triplicityrulers { system, division, lifespan }
//   keypoints        { mode }
// 缺省（undefined）交给 builder 自己的 resolveOpts 回落缺省 = 与上游逐字一致。值域校验在 Python 侧先做
// （service._run_progextra_js_tool），这里只透传。
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
  const options = input.options && typeof input.options === 'object' ? input.options : {};
  const builder = BUILDERS[technique];
  if (!builder) {
    return { tool: 'progextra', technique, data: { ok: false, reason: 'unknown_technique' }, snapshot_text: '' };
  }
  let snapshot_text = '';
  // [当前时点] 定位行（上游 buildCurrentMomentLines(chartObj, extraLines) 的 extraLines）：vendored builder 的
  // astroAiSnapshot stub 把它写进这个全局槽（见 vendor_manifest stub_import），这里每次调用前清空、调用后取走。
  globalThis.__horosaProgMomentLines = [];
  try {
    snapshot_text = builder(chartObj, options) || '';
  } catch (error) {
    // 不静默：builder 抛错如实回 ok:false + 原因，Python 侧据此进 envelope 警告。
    return {
      tool: 'progextra',
      technique,
      data: { ok: false, reason: 'builder_failed', error: `${(error && error.message) || error}` },
      snapshot_text: '',
    };
  }
  const moment_lines = Array.isArray(globalThis.__horosaProgMomentLines) ? globalThis.__horosaProgMomentLines : [];
  globalThis.__horosaProgMomentLines = [];
  return { tool: 'progextra', technique, data: { ok: true, options }, snapshot_text, moment_lines };
}
