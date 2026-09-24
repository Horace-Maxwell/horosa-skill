// election: run 星阙's 择日 (electional) judgment engine on a chart object + topic, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the candidate-moment
// chart (traditional) in Python and passes the /chart response as payload.chart.
import { runElection } from '../vendor/divination/election/electionEngine.js';
import { buildElectionSnapshot } from '../vendor/divination/election/electionSnapshot.js';
import { TOPIC_MASTER } from '../vendor/divination/data/topicMaster.js';
import { ELECTION_PARAM_BY_KEY, resolveElectionParams } from '../vendor/divination/election/electionParams.js';
import { WEST_SCHOOLS } from '../vendor/divination/election/westernSchools.js';
import { buildFacts } from '../vendor/divination/engine/chartFacts.js';

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
  if (input.action === 'resolve_params') {
    const effective = resolveElectionParams(westSchool, {}, electionParams);
    return {
      tool: 'election',
      data: {
        ok: true,
        effective,
        school: westSchool || 'modern_main',
        params_applied: Object.keys(electionParams).sort(),
        params_ignored: ignoredParams.sort(),
      },
    };
  }
  const opts = { westSchool, electionParams };
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
  try {
    judgment = runElection(chart, topicId, natalFacts, null, opts);
    snapshot_text = judgment ? (buildElectionSnapshot(judgment, snapshotExtra) || '') : '';
  } catch (error) {
    snapshot_text = '';
  }
  const data = {
    ok: !!snapshot_text,
    topic: judgment && judgment.topic ? judgment.topic.cn : null,
    overall: judgment && judgment.overall ? { score: judgment.overall.score, gradeCn: judgment.overall.gradeCn } : null,
    hard_flags: judgment && Array.isArray(judgment.hard_flags) ? judgment.hard_flags.length : 0,
    // 口径回执：不认识的键必须**说出来**，不能像此前那样连整包 opts 一起无声吞掉。
    school: westSchool || 'modern_main',
    params_applied: Object.keys(electionParams).sort(),
    params_ignored: ignoredParams.sort(),
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
