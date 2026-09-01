// horary: run 星阙's 卜卦 (horary) judgment engine on a chart object + question category, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the horary chart
// (traditional, at the question moment) in Python and passes the /chart response as payload.chart.
import { runHorary } from '../vendor/divination/horary/horaryEngine.js';
import { buildHorarySnapshot } from '../vendor/divination/horary/horarySnapshot.js';
import { CATEGORY_DEF } from '../vendor/divination/horary/significators.js';
import { horaryJudgeOpts, HORARY_SCHOOLS, HORARY_PARAM_BY_KEY } from '../vendor/divination/horary/horarySchools.js';

export function runHoraryTool(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const chart = input.chart && typeof input.chart === 'object' ? input.chart : {};
  let category = `${input.category || 'general'}`;
  if (!CATEGORY_DEF[category]) {
    category = 'general';
  }
  // 流派决定两段的有无：[偶然尊贵满分表] 只在 accidentalMode==='lilly' 出、[阿拉伯点全集] 只在
  // lotsSet==='core15' 出（见 horarySchools.js），两者都是 renaissance/medieval 档才给的口径。
  // 默认仍是 classical —— 不传 school 时行为与此前逐字不变。
  let school = `${input.school || 'classical'}`;
  if (!HORARY_SCHOOLS[school]) {
    school = 'classical';
  }
  // 🔴 horaryJudgeOpts(id, overrides, globals) 是四层口径链，此前只喂第 1 层（流派档），
  // 于是 46 个判读层参数（lotsSet/considerationsMode/vocMode/…）结构上不可达 ——
  // schema 却挂着其中两个的描述。可覆写键**锚定引擎自己的词表** HORARY_PARAM_BY_KEY，
  // 后端层四键（hsys/termsVariant/geminiBoundEmended/tradition）不走这里，它们随 /chart 发。
  const rawOverrides = { ...(input.options && typeof input.options === 'object' ? input.options : {}) };
  Object.keys(input).forEach((k) => {
    const spec = HORARY_PARAM_BY_KEY[k];
    if (spec && !spec.sendToBackend && input[k] !== undefined && input[k] !== null && !(k in rawOverrides)) {
      rawOverrides[k] = input[k];
    }
  });
  const overrides = {};
  const ignoredParams = [];
  Object.keys(rawOverrides).forEach((k) => {
    const spec = HORARY_PARAM_BY_KEY[k];
    if (spec && !spec.sendToBackend) { overrides[k] = rawOverrides[k]; } else { ignoredParams.push(k); }
  });
  const opts = horaryJudgeOpts(school, overrides);
  let snapshot_text = '';
  let judgment = null;
  try {
    judgment = runHorary(chart, category, opts);
    // 上游 buildHorarySnapshot(j, chart, opts3)：第 2 参是 /chart 原始响应，[古典接纳] 段直接读它的
    // receptions/mutuals；只传第 1 参就恒缺该段。
    snapshot_text = judgment ? (buildHorarySnapshot(judgment, chart, opts) || '') : '';
  } catch (error) {
    snapshot_text = '';
  }
  return {
    tool: 'horary',
    category,
    school,
    data: {
      ok: !!snapshot_text,
      verdict: judgment && judgment.verdict ? judgment.verdict.summary : null,
      significators: judgment ? judgment.significators : null,
      radicality: judgment && judgment.radicality ? { suitable: judgment.radicality.suitable } : null,
      // 口径回执：不认识的键必须说出来，不能无声吞掉（后端层键走 /chart，不在此列）。
      params_applied: Object.keys(overrides).sort(),
      params_ignored: ignoredParams.sort(),
    },
    snapshot_text,
  };
}

export default runHoraryTool;
