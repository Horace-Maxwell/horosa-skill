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
import { runLiureng, normalizeChart } from '../src/tools/liureng.js';
import { buildLiuRengReferenceContext } from '../src/vendor/liureng/liurengRefContext.js';
import { matchBiFa } from '../src/vendor/liureng/LRBiFaDoc.js';
import { runGuolaoMoira } from '../src/tools/guolaoMoira.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const chart = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_traditional.json'), 'utf8'));
const liurengFix = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_liureng.json'), 'utf8'));
const guolaoFix = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_guolao.json'), 'utf8'));

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

// 六壬毕法 (星阙 v2.5.x Phase4)：buildLiuRengReferenceContext + matchBiFa verbatim 抽取，
// 在固定盘上应组装出有效 ~75 字段 context 并机械命中若干毕法。
check('liureng refContext builds + matchBiFa hits', () => {
  const chartObj = normalizeChart(liurengFix);  // unwrap raw /chart response → nongli/objects at top
  const ctx = buildLiuRengReferenceContext(liurengFix.liureng, chartObj, 2, null, null);
  assert(ctx && ctx.dayGanZi && ctx.dayGanZi.length === 2, 'context missing dayGanZi');
  assert(Array.isArray(ctx.sanChuanBranches) && ctx.sanChuanBranches.length === 3, 'sanChuan should have 3 branches');
  assert(Array.isArray(ctx.keUpBranches) && ctx.keUpBranches.length >= 1, 'keUp branches missing');
  const hits = matchBiFa(ctx);
  assert(Array.isArray(hits) && hits.length >= 1, 'matchBiFa should hit ≥1 毕法 on this 盘');
  assert(hits.every((h) => h.no && h.name && h.verse), 'each 毕法 hit needs no/name/verse');
});

check('liureng snapshot carries 毕法 + 占断向导 sections', () => {
  const r = runLiureng({ ...liurengFix, zhanCategory: 'hunyin' });
  const s = r.snapshot_text || '';
  assert(s.includes('[常用神煞]'), 'missing 常用神煞');
  assert(s.includes('[毕法（已命中）]'), 'missing 毕法 section');
  assert(/\n\d+\.\s/.test(s), 'no numbered 毕法 entries');
  assert(s.includes('[占断向导]') && s.includes('占事：婚姻'), 'missing 占断向导 for hunyin');
});

// 七政四余 政余格局 (星阙 v2.6.x Moira DSL)：buildLocalMoiraPatterns verbatim 抽取。固定盘
// 1985-03-21 应命中喜格「金水相涵」+ 忌格「孛犯太阳」(盘面物象格局，不依赖 七政神煞)。
check('guolaoMoira evaluates 政余格局 patterns', () => {
  const r = runGuolaoMoira(guolaoFix);
  const names = (r.data.patterns || []).map((p) => p.name);
  assert(!r.data.error, `should not error: ${r.data.error}`);
  assert(names.includes('金水相涵'), `expected 金水相涵, got ${names.join(',')}`);
  assert(names.includes('孛犯太阳'), `expected 孛犯太阳, got ${names.join(',')}`);
  const s = r.snapshot_text || '';
  assert(s.includes('喜格：') && s.includes('忌格：'), 'snapshot missing 喜格/忌格 lines');
});

if (failures > 0) {
  console.error(`\nselfcheck: ${failures} failure(s)`);
  process.exit(1);
}
console.log('\nselfcheck: all JS engine golden checks passed');
