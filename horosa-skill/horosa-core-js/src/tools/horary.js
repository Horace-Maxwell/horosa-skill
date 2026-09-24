// horary: run 星阙's 卜卦 (horary) judgment engine on a chart object + question category, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the horary chart
// (traditional, at the question moment) in Python and passes the /chart response as payload.chart.
//
// 两个入口（payload.action 分流）：
// 1. 'backend_fields'：流派档 → 起盘字段补丁（上游 horarySchools.horaryBackendFields(school, overrides)，
//    页面 HoraryMain.js:543 `{ zodiacal: 0, ...horaryBackendFields(school) }` / 挂载 aiAnalysisContext.js:2264 同源）。
//    Python 先取它再铸 /chart —— 宫制/界系/三分集/福点反转/星群随流派，不在 Python 手抄一份会漂移的档表。
// 2. 缺省：判读 + 快照（runHorary + buildHorarySnapshot）。
import { runHorary } from '../vendor/divination/horary/horaryEngine.js';
import { buildHorarySnapshot } from '../vendor/divination/horary/horarySnapshot.js';
import { CATEGORY_DEF } from '../vendor/divination/horary/significators.js';
import { horaryJudgeOpts, horaryBackendFields, HORARY_SCHOOLS, HORARY_PARAM_BY_KEY } from '../vendor/divination/horary/horarySchools.js';
import { judgeLayerFromPlain } from '../vendor/utils/judgeLayerHeadless.js';

// 起盘阵营（上游 HoraryMain CAMP_OPTIONS 的三个值；buildHorarySnapshot 只认 querent / 其它非 astrologer 值）。
const CASTING_CAMPS = ['astrologer', 'querent', 'midpoint'];

function resolveSchool(input) {
  const school = `${input.school || 'classical'}`;
  return HORARY_SCHOOLS[school] ? school : 'classical';
}

// 顶层参数来源：Python 以 payload.params 整包转交请求顶层；直接调用（selfcheck 金标）时顶层键写在 payload 本身。
function paramsOf(input) {
  return input.params && typeof input.params === 'object' ? input.params : input;
}

// 页面覆盖层（上游 extra.horaryOverrides 的同一语义）的收集：
//   · options.{…}：任意引擎词表键；
//   · 顶层键：词表里 scope≠'global' 的判读键 + 全部 sendToBackend 键（HoraryInput 把 hsys/termsVariant/
//     geminiBoundEmended/tradition 声明为卜卦自己的旋钮 = 显式覆盖，压过流派档）。
//   上游把**同一个** horaryOverrides 同时交给 horaryBackendFields（起盘）与 horaryJudgeOpts（判读第 4 层）——
//   judge 集因此含 sendToBackend 键（判读的界系/双子界序随之）；backend 集 = sendToBackend 键 + tripSystem。
//   🔴 顶层 scope='global' 的判读键（cazimiOrb/vocMode/partileDef/恒星轨…）**不**进这一层 —— 它们是用户的
//     全局设置，上游经 judgeLayerOverrides() 进第 2 层（流派差异集之下），见 judgeLayerFromPlain。
function collectOverrides(input) {
  const raw = { ...(input.options && typeof input.options === 'object' ? input.options : {}) };
  const params = paramsOf(input);
  Object.keys(params).forEach((k) => {
    const spec = HORARY_PARAM_BY_KEY[k];
    if (!spec || params[k] === undefined || params[k] === null || k in raw) return;
    if (spec.scope === 'global' && !spec.sendToBackend) return;
    raw[k] = params[k];
  });
  const judge = {};
  const backend = {};
  const ignored = [];
  Object.keys(raw).forEach((k) => {
    const spec = HORARY_PARAM_BY_KEY[k];
    if (!spec) { ignored.push(k); return; }
    judge[k] = raw[k];
    // horaryBackendFields 只收 sendToBackend 键 + tripSystem（→ triplicity 随档下发）。
    if (spec.sendToBackend || k === 'tripSystem') backend[k] = raw[k];
  });
  return { judge, backend, ignored };
}

export function runHoraryTool(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  // 流派决定两段的有无：[偶然尊贵满分表] 只在 accidentalMode==='lilly' 出、[阿拉伯点全集] 只在
  // lotsSet==='core15' 出（见 horarySchools.js），两者都是 renaissance/medieval 档才给的口径。
  const school = resolveSchool(input);
  const { judge: overrides, backend: backendOverrides, ignored: ignoredParams } = collectOverrides(input);
  if (input.action === 'backend_fields') {
    return {
      tool: 'horary',
      school,
      data: {
        ok: true,
        school,
        backendFields: horaryBackendFields(school, Object.keys(backendOverrides).length ? backendOverrides : null),
        backend_overrides: Object.keys(backendOverrides).sort(),
      },
    };
  }
  const chart = input.chart && typeof input.chart === 'object' ? input.chart : {};
  let category = `${input.category || 'general'}`;
  if (!CATEGORY_DEF[category]) {
    category = 'general';
  }
  // 全局层（第 2 层）：请求顶层古典键 → judgeLayerOverrides 同形（只含改过的键；认不出的枚举值回执 invalid）。
  const { overrides: globals, invalid } = judgeLayerFromPlain(paramsOf(input));
  const castingCamp = `${input.castingCamp || 'astrologer'}`;
  if (CASTING_CAMPS.indexOf(castingCamp) < 0) {
    invalid.push({ key: 'castingCamp', value: input.castingCamp, allowed: CASTING_CAMPS });
  }
  // 🔴 horaryJudgeOpts(id, overrides, globals) 是四层口径链：内建默认 < 全局层 < 流派差异集 < 页面覆盖。
  // 可覆写键**锚定引擎自己的词表** HORARY_PARAM_BY_KEY；起盘那一半（后端层四键 + tripSystem）由 action=backend_fields 给 Python。
  // 定盘自评三键随档并入 opts（上游页面 HoraryMain.js:531-533 / 挂载 aiAnalysisContext.js:2294-2299 同构）：
  // sincerityConfirmed 页面缺省勾选（!== false）；confirmYouthMatch / isEventChart 缺省不勾。
  const opts = {
    ...horaryJudgeOpts(school, Object.keys(overrides).length ? overrides : null, globals),
    sincerityConfirmed: input.sincerityConfirmed !== false,
    confirmYouthMatch: !!input.confirmYouthMatch,
    isEventChart: !!input.isEventChart,
  };
  let snapshot_text = '';
  let judgment = null;
  if (!invalid.length) {
    try {
      judgment = runHorary(chart, category, opts);
      // 上游 buildHorarySnapshot(j, chart, opts3)：第 2 参是 /chart 原始响应（[古典接纳] 段读它的 receptions/mutuals）；
      // 第 3 参只收问句与阵营（HoraryMain.js:593）→ [定盘考量] 段的「所问之事 / 起盘阵营」两行。
      const opts3 = { questionText: input.questionText ? `${input.questionText}` : undefined, castingCamp };
      snapshot_text = judgment ? (buildHorarySnapshot(judgment, chart, opts3) || '') : '';
    } catch (error) {
      snapshot_text = '';
    }
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
      params_global: Object.keys(globals).sort(),
      params_ignored: ignoredParams.sort(),
      invalid_inputs: invalid,
    },
    snapshot_text,
  };
}

export default runHoraryTool;
