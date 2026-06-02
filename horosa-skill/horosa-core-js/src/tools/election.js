// election: run 星阙's 择日 (electional) judgment engine on a chart object + topic, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the candidate-moment
// chart (traditional) in Python and passes the /chart response as payload.chart.
import { runElection } from '../vendor/divination/election/electionEngine.js';
import { buildElectionSnapshot } from '../vendor/divination/election/electionSnapshot.js';
import { TOPIC_MASTER } from '../vendor/divination/data/topicMaster.js';

export function runElectionTool(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const chart = input.chart && typeof input.chart === 'object' ? input.chart : {};
  let topicId = `${input.topicId || input.topic || 'marriage'}`;
  if (!TOPIC_MASTER[topicId]) {
    topicId = 'marriage';
  }
  let snapshot_text = '';
  let judgment = null;
  try {
    judgment = runElection(chart, topicId);
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
    },
    snapshot_text,
  };
}

export default runElectionTool;
