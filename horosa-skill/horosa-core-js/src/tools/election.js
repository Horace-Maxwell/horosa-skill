// election: run 星阙's 择日 (electional) judgment engine on a chart object + topic, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the candidate-moment
// chart (traditional) in Python and passes the /chart response as payload.chart.
import { runElection } from '../vendor/divination/election/electionEngine.js';
import { buildElectionSnapshot } from '../vendor/divination/election/electionSnapshot.js';
import { TOPIC_MASTER } from '../vendor/divination/data/topicMaster.js';
import { ELECTION_PARAM_BY_KEY, resolveElectionParams } from '../vendor/divination/election/electionParams.js';
import { evaluateTopicPack } from '../vendor/divination/election/rulePacks.js';
import { WEST_SCHOOLS, schoolOf } from '../vendor/divination/election/westernSchools.js';
import { buildFacts } from '../vendor/divination/engine/chartFacts.js';
import { SIGN_ORDER } from '../vendor/divination/data/signs.js';
import { CLASSICAL_PLANETS } from '../vendor/divination/data/planets.js';
import { judgeLayerFromPlain } from '../vendor/utils/judgeLayerHeadless.js';

// 买卖方向（上游 ElectionMain.js:379-384 下拉三档：''=不指定 / sell / buy）。
const TRADE_SIDES = ['', 'sell', 'buy'];

// 顶层参数来源：Python 以 payload.params 整包转交请求顶层；直接调用（selfcheck 金标）时顶层键写在 payload 本身。
function paramsOf(input) {
  return input.params && typeof input.params === 'object' ? input.params : input;
}

// 危象日参照（WP-8）：上游 fetchCrisisBase（ElectionMain.js:159-171）= 病始日期正午在择日地点起盘 → buildFacts →
// 月黄经，存 extra.crisisBase = { date, moonLon }。Python 按同一口径起盘，把盘交过来（crisisChart），这里只做
// 上游同款 buildFacts 取月亮；也接受上游存档形状 crisisBase:{date, moonLon} 直通。
function resolveCrisisBase(input, invalid, errors) {
  const given = input.crisisBase;
  if (given && typeof given === 'object' && !Array.isArray(given)) {
    const moonLon = Number(given.moonLon);
    if (!Number.isFinite(moonLon)) {
      invalid.push({ key: 'crisisBase', value: given, allowed: '{date, moonLon:number} 或病始日期 YYYY-MM-DD' });
      return null;
    }
    return { date: `${given.date || ''}`, moonLon };
  }
  const chart = input.crisisChart && typeof input.crisisChart === 'object' ? input.crisisChart : null;
  if (!chart) return null;
  try {
    const F = buildFacts(chart);
    const moonLon = F && F.planets && F.planets.moon ? F.planets.moon.lon : null;
    if (moonLon === null || moonLon === undefined) {
      errors.push('危象日参照：病始盘取不到月亮黄经');
      return null;
    }
    return { date: `${input.crisisDate || ''}`, moonLon };
  } catch (error) {
    errors.push(`危象日参照：${(error && error.message) || error}`);
    return null;
  }
}

// 回归盘：Python 按上游 returnCharts.solveReturnBefore 求出「择日时刻之前最近一次」精确回归时刻，
// 把**最后一次成功起的盘**（上游 facts 的来源盘）连同 momentStr 交过来；这里只做上游同款 buildFacts(R)
// （returnCharts.js:43/:55），拼回 { momentStr, facts } 这个上游形状。缺盘 = 该返未求得（上游 null）。
function returnEntry(raw, errors, label) {
  if (!raw || typeof raw !== 'object' || !raw.chart || typeof raw.chart !== 'object') return null;
  try {
    const facts = buildFacts(raw.chart);
    if (!facts) errors.push(`${label}: buildFacts 返回空`);
    return facts ? { momentStr: `${raw.momentStr || ''}`, facts } : null;
  } catch (error) {
    errors.push(`${label}: ${(error && error.message) || error}`);
    return null;
  }
}

export function runElectionTool(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const chart = input.chart && typeof input.chart === 'object' ? input.chart : {};
  let topicId = `${input.topicId || input.topic || 'marriage'}`;
  if (!TOPIC_MASTER[topicId]) {
    topicId = 'marriage';
  }
  // 🔴 opts 必须传：runElection(result, topicId, natalFacts, mundaneSet, opts) 的四层口径解析
  // （电engine:91 resolveElectionParams）全靠它，此前只传两参 → 流派档与 13 个判读层参数
  // 结构上不可达，而 schema 上却挂着一排「择日流派档/尊贵取法/…」的旋钮，纯属声称。
  // 可覆写键**锚定引擎自己的词表** ELECTION_PARAM_BY_KEY，不手抄一份会漂移的清单。
  const westSchool = WEST_SCHOOLS[`${input.school || ''}`] ? `${input.school}` : undefined;
  const rawParams = { ...(input.options && typeof input.options === 'object' ? input.options : {}) };
  Object.keys(input).forEach((k) => {
    if (ELECTION_PARAM_BY_KEY[k] && input[k] !== undefined && input[k] !== null && !(k in rawParams)) {
      rawParams[k] = input[k];
    }
  });
  const electionParams = {};
  const ignoredParams = [];
  Object.keys(rawParams).forEach((k) => {
    if (ELECTION_PARAM_BY_KEY[k]) { electionParams[k] = rawParams[k]; } else { ignoredParams.push(k); }
  });
  // 有效口径（四层合并）：Python 取「主限命中」时要用 eff.pdTimeKey —— 上游 ElectionMain.fetchPdHits
  // 正是 resolveElectionParams(westSchool, {}, electionParams).pdTimeKey（ElectionMain.js:234）。
  // 由引擎自己的解析器给出，Python 不手抄流派默认表。
  // 全局层（第 2 层）：请求顶层古典键 → judgeLayerOverrides 同形（只含改过的键）。上游页面/存档/挂载三处都
  // `...judgeLayerOverrides()` 展进 runElection 的 opts（ElectionJudgment.js:296 / ElectionMain.js:497 /
  // aiAnalysisContext.js:2358-2363），resolveElectionParams 按 GLOBAL_JUDGE_KEYS 白名单收编进第 2 层。
  const { overrides: globals, invalid } = judgeLayerFromPlain(paramsOf(input));
  if (input.action === 'resolve_params') {
    const effective = resolveElectionParams(westSchool, globals, electionParams);
    const sc = schoolOf(westSchool);
    return {
      tool: 'election',
      data: {
        ok: true,
        effective,
        school: westSchool || 'modern_main',
        // 流派宫制联动（westernSchools.js hsys；null=不联动）：页面切档 patchFields({hsys})（ElectionMain.js:348-353）、
        // 挂载再生 chartRecord.hsys = sc.hsys（aiAnalysisContext.js:2316-2327）。Python 起盘前取它。
        schoolHsys: sc && sc.hsys !== undefined ? sc.hsys : null,
        params_applied: Object.keys(electionParams).sort(),
        params_global: Object.keys(globals).sort(),
        params_ignored: ignoredParams.sort(),
        invalid_inputs: invalid,
      },
    };
  }
  // 用事专属四键（上游左栏按用事显示的控件，ElectionMain.js:376-440）：值域锚定引擎词表，认不出的报出来。
  const tradeSide = input.tradeSide === undefined || input.tradeSide === null ? '' : `${input.tradeSide}`;
  if (TRADE_SIDES.indexOf(tradeSide) < 0) invalid.push({ key: 'tradeSide', value: input.tradeSide, allowed: TRADE_SIDES });
  const talismanStar = input.talismanStar ? `${input.talismanStar}` : null;
  if (talismanStar && CLASSICAL_PLANETS.indexOf(talismanStar) < 0) invalid.push({ key: 'talismanStar', value: input.talismanStar, allowed: CLASSICAL_PLANETS });
  const surgeryPart = input.surgeryPart ? `${input.surgeryPart}` : null;
  if (surgeryPart && SIGN_ORDER.indexOf(surgeryPart) < 0) invalid.push({ key: 'surgeryPart', value: input.surgeryPart, allowed: SIGN_ORDER });
  const extraErrors = [];
  const crisisBase = resolveCrisisBase(input, invalid, extraErrors);
  // 上游 runElection opts（ElectionJudgment.js:296 同集同序）：流派档 / 部位 / 危象基准 / 全局判读层 / 流派口径覆盖 /
  // 买卖方向 / 护符主星 / 部位对宫。
  const opts = {
    westSchool, surgeryPart, crisisBase,
    ...globals,
    electionParams, tradeSide,
    talismanStar, surgeryPartOpposite: !!input.surgeryPartOpposite,
  };
  // 本命合参（可选）：上游 selectNatal 以本命参数补拉 /chart → buildFacts → runElection 的 natalFacts（ElectionMain.js:173-188）。
  const natalChart = input.natalChart && typeof input.natalChart === 'object' ? input.natalChart : null;
  let natalFacts = null;
  let natalError = null;
  if (natalChart) {
    try {
      natalFacts = buildFacts(natalChart);
      if (!natalFacts) natalError = 'buildFacts(natalChart) 返回空（本命盘缺 chart 对象）';
    } catch (error) {
      natalError = `${(error && error.message) || error}`;
    }
  }
  // [回归与主限]（上游 v3.11 [Q-445]）：页面按需拉取物经 extra 进快照（ElectionJudgment.js:289）。
  const extraIn = input.extra && typeof input.extra === 'object' ? input.extra : null;
  let snapshotExtra;
  let returnRows = 0;
  const returnErrors = [];
  if (extraIn) {
    const rs = extraIn.returnSet && typeof extraIn.returnSet === 'object'
      ? {
        solar: returnEntry(extraIn.returnSet.solar, returnErrors, '日返'),
        lunar: returnEntry(extraIn.returnSet.lunar, returnErrors, '月返'),
      }
      : null;
    returnRows = (rs && rs.solar ? 1 : 0) + (rs && rs.lunar ? 1 : 0);
    snapshotExtra = { returnSet: rs, pdHits: Array.isArray(extraIn.pdHits) ? extraIn.pdHits : null };
  }
  let snapshot_text = '';
  let judgment = null;
  // 用事专属四键只在对应用事的规则包里被消费（上游左栏也只在该用事显示控件）。给了却不作用 → 回执 unused_inputs
  // 让 Python 说出来。判据不手抄「哪个用事读哪个键」：拿引擎自己的 evaluateTopicPack 去掉该键重跑一遍比对。
  const unusedInputs = [];
  if (!invalid.length) {
    try {
      judgment = runElection(chart, topicId, natalFacts, null, opts);
      snapshot_text = judgment ? (buildElectionSnapshot(judgment, snapshotExtra) || '') : '';
      if (judgment && judgment.facts && judgment.topic) {
        const packSig = (o) => JSON.stringify(evaluateTopicPack(judgment.facts, judgment.topic, o));
        const base = JSON.stringify(judgment.topicPack);
        if (tradeSide && packSig({ ...opts, tradeSide: '' }) === base) unusedInputs.push('tradeSide');
        if (talismanStar && packSig({ ...opts, talismanStar: null }) === base) unusedInputs.push('talismanStar');
        if (surgeryPart && packSig({ ...opts, surgeryPart: null }) === base) unusedInputs.push('surgeryPart');
        if (input.surgeryPartOpposite && packSig({ ...opts, surgeryPartOpposite: false }) === base) unusedInputs.push('surgeryPartOpposite');
        if (crisisBase && !judgment.crisis) unusedInputs.push('crisisBase');
      }
    } catch (error) {
      snapshot_text = '';
    }
  }
  const data = {
    ok: !!snapshot_text,
    topic: judgment && judgment.topic ? judgment.topic.cn : null,
    overall: judgment && judgment.overall ? { score: judgment.overall.score, gradeCn: judgment.overall.gradeCn } : null,
    hard_flags: judgment && Array.isArray(judgment.hard_flags) ? judgment.hard_flags.length : 0,
    // 口径回执：不认识的键必须**说出来**，不能像此前那样连整包 opts 一起无声吞掉。
    school: westSchool || 'modern_main',
    params_applied: Object.keys(electionParams).sort(),
    params_global: Object.keys(globals).sort(),
    params_ignored: ignoredParams.sort(),
    invalid_inputs: invalid,
    crisis: judgment && judgment.crisis ? { elapsedDeg: judgment.crisis.elapsedDeg, nearestMark: judgment.crisis.nearestMark } : null,
    unused_inputs: unusedInputs,
    extra_errors: extraErrors,
  };
  // 合参回执（只在给了本命/回归物料时出现，缺省路径的 data 逐键不变）：给了本命却没并进判读
  // （本命盘坏了）、回归盘建不出 facts —— 都必须能被 Python 看见并上报，不许静默少段。
  if (natalChart) {
    data.natal = { integrated: !!natalFacts, error: natalError };
  }
  if (snapshotExtra) {
    data.returns = {
      returnCharts: returnRows,
      pdHits: snapshotExtra.pdHits ? snapshotExtra.pdHits.length : null,
      errors: returnErrors,
    };
  }
  return { tool: 'election', topicId, data, snapshot_text };
}

export default runElectionTool;
