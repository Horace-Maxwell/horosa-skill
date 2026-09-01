// election: run 星阙's 择日 (electional) judgment engine on a chart object + topic, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the candidate-moment
// chart (traditional) in Python and passes the /chart response as payload.chart.
import { runElection } from '../vendor/divination/election/electionEngine.js';
import { buildElectionSnapshot } from '../vendor/divination/election/electionSnapshot.js';
import { TOPIC_MASTER } from '../vendor/divination/data/topicMaster.js';
import { ELECTION_PARAM_BY_KEY } from '../vendor/divination/election/electionParams.js';
import { WEST_SCHOOLS } from '../vendor/divination/election/westernSchools.js';

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
  const opts = { westSchool, electionParams };
  let snapshot_text = '';
  let judgment = null;
  try {
    judgment = runElection(chart, topicId, null, null, opts);
    snapshot_text = judgment ? (buildElectionSnapshot(judgment) || '') : '';
  } catch (error) {
    snapshot_text = '';
  }
  return {
    tool: 'election',
    topicId,
    data: {
      ok: !!snapshot_text,
      topic: judgment && judgment.topic ? judgment.topic.cn : null,
      overall: judgment && judgment.overall ? { score: judgment.overall.score, gradeCn: judgment.overall.gradeCn } : null,
      hard_flags: judgment && Array.isArray(judgment.hard_flags) ? judgment.hard_flags.length : 0,
      // 口径回执：不认识的键必须**说出来**，不能像此前那样连整包 opts 一起无声吞掉。
      school: westSchool || 'modern_main',
      params_applied: Object.keys(electionParams).sort(),
      params_ignored: ignoredParams.sort(),
    },
    snapshot_text,
  };
}

export default runElectionTool;
