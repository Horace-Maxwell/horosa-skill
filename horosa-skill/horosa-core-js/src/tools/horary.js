// horary: run 星阙's 卜卦 (horary) judgment engine on a chart object + question category, emit the AI snapshot.
// The whole divination/ engine is vendored (pure logic, no React); the skill casts the horary chart
// (traditional, at the question moment) in Python and passes the /chart response as payload.chart.
import { runHorary } from '../vendor/divination/horary/horaryEngine.js';
import { buildHorarySnapshot } from '../vendor/divination/horary/horarySnapshot.js';
import { CATEGORY_DEF } from '../vendor/divination/horary/significators.js';

export function runHoraryTool(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const chart = input.chart && typeof input.chart === 'object' ? input.chart : {};
  let category = `${input.category || 'general'}`;
  if (!CATEGORY_DEF[category]) {
    category = 'general';
  }
  let snapshot_text = '';
  let judgment = null;
  try {
    judgment = runHorary(chart, category);
    snapshot_text = judgment ? (buildHorarySnapshot(judgment) || '') : '';
  } catch (error) {
    snapshot_text = '';
  }
  return {
    tool: 'horary',
    category,
    data: {
      ok: !!snapshot_text,
      verdict: judgment && judgment.verdict ? judgment.verdict.summary : null,
      significators: judgment ? judgment.significators : null,
      radicality: judgment && judgment.radicality ? { suitable: judgment.radicality.suitable } : null,
    },
    snapshot_text,
  };
}

export default runHoraryTool;
