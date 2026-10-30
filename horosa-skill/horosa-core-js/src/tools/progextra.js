// progextra: run a vendored 星阙 progression builder (balbillus / triplicityrulers / keypoints /
// lunationphase) on a chart object. These are pure frontend builders (read the chart, output the
// single-section text); the skill passes the /chart response as payload.chart. Returns { snapshot_text }.
//
// payload.options → the builder's `opts` (上游 techniqueMountSettings.js:1237-1274 的挂载齿轮 =
// aiAnalysisContext.js:2998-3013 regen 传给 builder 的同一组键)：
//   balbillus        { startPlanet, yearType, mode }
//   triplicityrulers { system, division, lifespan }
//   keypoints        { mode }
//   yearsystem129    { startPlanet, order, yearType, subRule }（上游 regenChart.js:263-267：齿轮键 ys129* → 这四键）
// 缺省（undefined）交给 builder 自己的 resolveOpts 回落缺省 = 与上游逐字一致。值域校验在 Python 侧先做
// （service._run_progextra_js_tool），这里只透传。
import { buildBalbillusSnapshotText } from '../vendor/astroextra/balbillus.js';
import { buildTriplicityRulersSnapshotText } from '../vendor/astroextra/triplicityRulers.js';
import { buildKeypointsSnapshotText } from '../vendor/astroextra/keypoints120.js';
import { buildLunationPhaseSnapshotText } from '../vendor/astroextra/lunationPhase.js';
import { buildYearSystem129SnapshotText } from '../vendor/astroextra/yearSystem129.js';
import { buildAgePointSnapshotFromResult } from '../vendor/astroextra/AstroAgePoint.js';
import { buildDistributionsSnapshotFromResult } from '../vendor/astroextra/AstroDistributions.js';

const BUILDERS = {
  balbillus: buildBalbillusSnapshotText,
  triplicityrulers: buildTriplicityRulersSnapshotText, // 三分主星推运 (星阙 v2.6.x)
  keypoints: buildKeypointsSnapshotText, // 数字相位推运
  lunationphase: buildLunationPhaseSnapshotText, // 月相推运
  // 129 年系统：上游 v3.13.0 删后端 yearsystem129.py，改前端 utils/yearSystem129 单源（/chart 不再回 predictives.yearsystem129）。
  yearsystem129: buildYearSystem129SnapshotText,
};

// 后端结果型（上游 v3.13.0）：Python 先拉 /predict/agepoint · /predict/dist（JS 层不发 HTTP，AGENTS §4.2），
// 再把后端结果作 payload.result 交给上游 buildXxxSnapshotFromResult(chartObj, r, opts)——与页面「已取到结果直接拼」同一函数。
// chartObj 只需 {params}（[当前时点] 定位行读 params.birth；[起盘信息] 由 Python 层出，stub 掉）。
//   agepoint      { apMethod, apEvents, apYear, apMaxAge }
//   distributions { distReleaser, distMethod, distYear, distYears }
const FROM_RESULT_BUILDERS = {
  agepoint: buildAgePointSnapshotFromResult,
  distributions: buildDistributionsSnapshotFromResult,
};

export function runProgExtra(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const technique = `${input.technique || ''}`;
  const chartObj = input.chart && input.chart.chart ? input.chart : { chart: (input.chart || {}).chart || (input.chart || {}) };
  const options = input.options && typeof input.options === 'object' ? input.options : {};
  const fromResult = FROM_RESULT_BUILDERS[technique];
  const result = input.result && typeof input.result === 'object' ? input.result : {};
  const builder = fromResult ? (chart, opts) => fromResult(chart, result, opts) : BUILDERS[technique];
  if (!builder) {
    return { tool: 'progextra', technique, data: { ok: false, reason: 'unknown_technique' }, snapshot_text: '' };
  }
  let snapshot_text = '';
  // [当前时点] 定位行（上游 buildCurrentMomentLines(chartObj, extraLines) 的 extraLines）：vendored builder 的
  // astroAiSnapshot stub 把它写进这个全局槽（见 vendor_manifest stub_import），这里每次调用前清空、调用后取走。
  globalThis.__horosaProgMomentLines = [];
  // payload.now_ms：Python 服务层的「此刻」（可冻结的 _clock）。vendored builder 的 [当前时点] 定位行按 Date.now()
  // （moment() 亦经 Date.now）取此刻——调用期间钉到同一瞬时，与 Python 侧 [当前时点] 基线两行不错位；缺省=真实此刻。
  const nowMs = Number(input.now_ms);
  const realNow = Date.now;
  if (Number.isFinite(nowMs)) {
    Date.now = () => nowMs;
  }
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
  } finally {
    Date.now = realNow;
  }
  const moment_lines = Array.isArray(globalThis.__horosaProgMomentLines) ? globalThis.__horosaProgMomentLines : [];
  globalThis.__horosaProgMomentLines = [];
  return { tool: 'progextra', technique, data: { ok: true, options }, snapshot_text, moment_lines };
}
