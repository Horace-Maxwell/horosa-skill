// Node golden self-check for the vendored 星阙 JS engines (no jest): runs horary / election /
// progextra(balbillus) on a fixed traditional-chart fixture and asserts the snapshot shape. This is
// the only test that exercises the ~40-file divination/ tree + balbillus.js at the JS layer; the
// Python @requires_chart tests only reach them via a live chart service. Exit non-zero on any failure
// so `npm test` / CI fails loudly.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { runHoraryTool } from '../src/tools/horary.js';
import { runElectionTool } from '../src/tools/election.js';
import { runProgExtra } from '../src/tools/progextra.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const chart = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_traditional.json'), 'utf8'));

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`  ok   ${name}`);
  } catch (err) {
    failures += 1;
    console.error(`  FAIL ${name}: ${err.message}`);
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

check('horary(marriage) emits a verdict snapshot', () => {
  const r = runHoraryTool({ chart, category: 'marriage' });
  assert(r.data.ok === true, 'data.ok should be true');
  const s = r.snapshot_text || '';
  for (const sec of ['[起卦信息]', '[根本性]', '[征象星指派]', '[裁决]']) {
    assert(s.includes(sec), `missing section ${sec}`);
  }
  assert(s.split('\n').length >= 10, 'snapshot too short');
  assert(typeof r.data.verdict === 'string' && r.data.verdict.length > 0, 'missing verdict');
});

check('horary unknown category falls back to general', () => {
  const r = runHoraryTool({ chart, category: 'no_such_category' });
  assert(r.category === 'general', `expected general, got ${r.category}`);
  assert((r.snapshot_text || '').includes('[起卦信息]'), 'missing 起卦信息');
});

check('election(surgery) emits a scored snapshot', () => {
  const r = runElectionTool({ chart, topicId: 'surgery' });
  assert(r.data.ok === true, 'data.ok should be true');
  const s = r.snapshot_text || '';
  for (const sec of ['[起盘信息]', '[总评]', '[红线]', '[建议]']) {
    assert(s.includes(sec), `missing section ${sec}`);
  }
  assert(r.data.overall && typeof r.data.overall.score === 'number', 'missing overall.score');
});

check('election unknown topic falls back to marriage', () => {
  const r = runElectionTool({ chart, topicId: 'no_such_topic' });
  assert(r.topicId === 'marriage', `expected marriage, got ${r.topicId}`);
});

check('progextra(balbillus) emits the 旺距削减 table', () => {
  const r = runProgExtra({ technique: 'balbillus', chart });
  const s = r.snapshot_text || '';
  assert(s.includes('[Balbillus]'), 'missing [Balbillus]');
  assert(s.includes('旺距削减'), 'missing 旺距削减 description');
  assert(s.includes('| 主限 | 子限 |'), 'missing period table header');
  assert(s.split('\n').filter((l) => l.startsWith('|')).length >= 5, 'too few table rows');
});

check('progextra unknown technique returns empty, not a crash', () => {
  const r = runProgExtra({ technique: 'no_such', chart });
  assert(r.data.ok === false, 'unknown technique should be ok=false');
  assert(r.snapshot_text === '', 'unknown technique should have empty snapshot');
});

if (failures > 0) {
  console.error(`\nselfcheck: ${failures} failure(s)`);
  process.exit(1);
}
console.log('\nselfcheck: all JS engine golden checks passed');
