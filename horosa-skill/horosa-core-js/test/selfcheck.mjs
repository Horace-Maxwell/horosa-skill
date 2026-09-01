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
import { runXiaoLiuRen } from '../src/tools/xiaoliuren.js';
import { runFeiGong } from '../src/tools/feigong.js';
import { runXiaoChengTu } from '../src/tools/xiaochengtu.js';
import { runGuice } from '../src/tools/guice.js';
import { runZhengChuan } from '../src/tools/zhengchuan.js';
import { runLingqi } from '../src/tools/lingqi.js';
import { runTianxing } from '../src/tools/tianxing.js';
import { runQizhengElection } from '../src/tools/qizhengElection.js';
import { runBaziGeju } from '../src/tools/baziGeju.js';
import { buildLocalBaziResult } from '../src/vendor/bazi/baziLunarLocal.js';

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

check('xiaoliuren(dao) 三数起三传 + 生克/化解，determinism', () => {
  const p = { nums: [5, 20, 7], school: 'dao', askEvent: '求财' };
  const r = runXiaoLiuRen(p);
  assert(r.snapshot_text, 'should emit a snapshot');
  ['[问事]', '[起课]', '[三传]', '[生克]', '[九神]', '[化解]'].forEach((h) => assert(r.snapshot_text.includes(h), `missing ${h}`));
  assert(JSON.stringify(r.data.chuan) === JSON.stringify(['小吉', '空亡', '速喜']), `unexpected 三传: ${r.data.chuan}`);
  assert(r.snapshot_text.includes('拜'), 'dao school should carry 拜解');
  const again = runXiaoLiuRen(p);
  assert(again.snapshot_text === r.snapshot_text, '同三数须同盘（冻结起课）');
  // 主流六宫无五行生克，段如实标注。
  const main = runXiaoLiuRen({ nums: [5, 20, 7], school: 'main', askEvent: '求财' });
  assert(main.snapshot_text.includes('主流六宫不调取五行生克'), 'main school should note no 生克');
});

check('feigong 时上起青龙飞九宫，7 段 + determinism', () => {
  const p = { qiMode: 'manualZhi', zhi: '午', dayGan: '甲', dayZhi: '子', mingAge: 35, mingGender: 'male', liuYueMonth: 1, askEvent: '求财' };
  const r = runFeiGong(p);
  assert(r.snapshot_text, 'should emit a snapshot');
  ['[问事]', '[起局]', '[干支]', '[命宫]', '[宫位]', '[运气]', '[应期]'].forEach((h) => assert(r.snapshot_text.includes(h), `missing ${h}`));
  assert(r.data.qiZhi === '午', `unexpected 起支: ${r.data.qiZhi}`);
  assert(r.snapshot_text.includes('甲乘龙飞九宫'), 'missing 甲乘龙飞九宫');
  const again = runFeiGong(p);
  assert(again.snapshot_text === r.snapshot_text, '同起支须同盘（冻结局）');
});

check('xiaochengtu 洛书九宫 + 股市段条件 + 大衍 seed 确定性', () => {
  const manual = runXiaoChengTu({ qiguaFa: 'manual', up: '乾', lo: '兑', dongYaos: [3], yongGong: 1, askEvent: '求财' });
  ['[问事]', '[起卦]', '[佈局]', '[推导]', '[四象]', '[应期]'].forEach((h) => assert(manual.snapshot_text.includes(h), `missing ${h}`));
  assert(!manual.snapshot_text.includes('[股市]'), 'non-stock must not emit [股市]');
  const stock = runXiaoChengTu({ qiguaFa: 'stock', open: '1563.60', close: '1571.10', yongGong: 1 });
  assert(stock.snapshot_text.includes('[股市]'), 'stock mode must emit [股市]');
  const noSeed = runXiaoChengTu({ qiguaFa: 'dayan' });
  assert(noSeed.data.reason === 'dayan_seed_required', 'dayan without seed must refuse');
  const a = runXiaoChengTu({ qiguaFa: 'dayan', seed: 12345 });
  const b = runXiaoChengTu({ qiguaFa: 'dayan', seed: 12345 });
  assert(a.snapshot_text === b.snapshot_text, '大衍同 seed 须同盘');
});

check('guice 报数起卦 + 演数四位 + 卦变断法 + determinism', () => {
  const p = { qiguaFa: 'baoshu', nums: [7, 9], hourZhi: '午', yearZhi: '午', monthZhi: '巳', lunarMonth: 4, lunarDay: 5, year: 2026, dayGan: '甲', pillars: ['丙午', '癸巳', '甲子', '庚午'], askEvent: '问事业' };
  const r = runGuice(p);
  assert(r.snapshot_text, 'should emit a snapshot');
  ['[占事直断]', '[起卦]', '[演数]', '[四位]', '[卦变]', '[断法]'].forEach((h) => assert(r.snapshot_text.includes(h), `missing ${h}`));
  assert(r.data.gua.ben === '山天大畜', `unexpected 本卦: ${r.data.gua.ben}`);
  assert(r.snapshot_text.includes('策数'), 'missing 策数');
  const again = runGuice(p);
  assert(again.snapshot_text === r.snapshot_text, '同起卦输入须同盘（冻结卦）');
});

// zhengchuan 铁板异步载条文正文库 → 用异步块（.mjs 顶层 await 可用）。
try {
  const tb = await runZhengChuan({ school: 'tieban', pillars: ['戊寅', '甲寅', '壬戌', '庚戌'], gender: 1, lunarMonth: 1, lunarDay: 24 });
  ['[起盘信息]', '[起数]', '[本命条文]', '[流年条文]'].forEach((h) => assert(tb.snapshot_text.includes(h), `tieban missing ${h}`));
  assert(tb.snapshot_text.length > 2000, 'tieban 本命条文正文应非空（verses 已链）');
  const xy = await runZhengChuan({ school: 'xinyi', item: '财', gong: '乾' });
  assert(xy.snapshot_text.includes('[起盘信息]'), 'xinyi 起盘信息 missing');
  const lq = await runZhengChuan({ school: 'liuqin', pillars: ['戊寅', '甲寅', '壬戌', '庚戌'], gender: 1, lunarMonth: 1, lunarDay: 24 });
  assert(lq.snapshot_text.includes('[十二宫与六亲宫]'), 'liuqin 十二宫与六亲宫 missing');
  console.log('  ok   zhengchuan tieban(条文)/xinyi(查询)/liuqin(六亲) 三流派');
} catch (err) {
  failures += 1;
  console.error(`  FAIL zhengchuan: ${err.message}`);
}

// 六壬三传 **值级** 钉死（v0.26.0）。此前只断言 `sanChuanBranches.length === 3` —— 那是形状不是值，
// 三传重排能静默通过。上游 v3.7.1 的两处勘正各留了可复核的具名课式，正好当金标：
//   #46 列举序≠判定序：八专须在遥克**之前**。旧序把「八专结构 + 遥克」误发蒿矢/弹射。
//   #62 伏吟末传子卯互刑：丁卯/己卯/辛卯 三日伏吟，末传 卯 → 午。
// 全域 8640 课（60 日干支 × 12 月将 × 12 时）穷举差分显示：改动仅落在这两桶内，桶外为 0。
try {
  const { buildLiuRengLayout, buildKeData } = await import('../src/vendor/liureng/liurengRefContext.js');
  const ChuangChart = (await import('../src/vendor/liureng/ChuangChart.js')).default;
  const baseObj = normalizeChart(liurengFix);
  const cast = (dayGanZi, yue, timeZhi) => {
    const chartObj = { ...baseObj, nongli: { ...baseObj.nongli, dayGanZi, time: `甲${timeZhi}` } };
    const layout = buildLiuRengLayout(chartObj, 2, { yue, timeZhi });
    const ke = buildKeData(layout, chartObj);
    const h = new ChuangChart({
      owner: null, chartObj, nongli: chartObj.nongli, ke: ke.raw,
      liuRengChart: { upZi: layout.upZi, downZi: layout.downZi, houseTianJiang: layout.houseTianJiang },
      x: 0, y: 0, width: 0, height: 0,
    });
    h.genCuangs();
    return { name: h.cuangs.name, chuan: h.cuangs.cuang.join('→') };
  };
  // #46 —— 上游逐字点名的两课。旧（错）序在此发蒿矢课/弹射课。
  const a = cast('甲寅', '戌', '丑');
  assert(a.name === '八专课', `甲寅日戌将丑时 应为八专课(上游 #46)，实得 ${a.name}`);
  assert(a.chuan === '空丑→癸亥→癸亥', `甲寅日戌将丑时 三传应为 空丑→癸亥→癸亥，实得 ${a.chuan}`);
  const b = cast('甲寅', '戌', '午');
  assert(b.name === '八专课', `甲寅日戌将午时 应为八专课(上游 #46)，实得 ${b.name}`);
  assert(b.chuan === '庚申→戊午→戊午', `甲寅日戌将午时 三传应为 庚申→戊午→戊午，实得 ${b.chuan}`);
  // #62 —— 伏吟(月将=时支)三卯日，末传取 午 而非 卯。
  for (const day of ['丁卯', '己卯', '辛卯']) {
    const r = cast(day, '子', '子');
    assert(r.chuan.endsWith('午'), `${day}日伏吟 末传应为 午(上游 #62 子卯互刑)，实得 ${r.chuan}`);
  }
  console.log('  ok   liureng 三传值级金标：#46 八专序 + #62 伏吟末传子卯互刑');
} catch (err) {
  failures += 1;
  console.error(`  FAIL liureng 三传值级金标: ${err.message}`);
}

// 灵棋经（上游 v3.9.0）值级金标 —— 段集恒定 + 同刻同卦幂等 + 卦是冻结值。
// 这三条是上游 __tests__/lingqi*.test.js 的不变量，headless 侧必须同样成立：
//   ① 七段恒出（注家开关只影响段内行，不改段集 —— 上游 parityAll 双向哨兵口径）；
//   ② 同一占时两次调用字节幂等（占时种子；headless 不走 random 档，否则古法「不可再擲」失守）；
//   ③ 给了 counts 就复排、绝不重掷（读档/事盘纪律）。
check('lingqi 七段恒出 + 同刻幂等 + counts 冻结不重掷', () => {
  const at = { year: 2028, month: 4, day: 6, hour: 9, minute: 33, question: '事业', category: 'career' };
  const a = runLingqi(at);
  const b = runLingqi({ ...at });
  const titles = a.snapshot_text.split('\n').filter((l) => l.startsWith('[')).map((l) => l.trim());
  assert(
    JSON.stringify(titles) === JSON.stringify(['[起盘信息]', '[棋势]', '[卦象]', '[繇辞]', '[诸家注]', '[课断]', '[断诗]']),
    `段集应恒为七段，实得 ${titles.join(' ')}`,
  );
  assert(a.snapshot_text === b.snapshot_text, '同一占时两次调用必须字节幂等（占时种子）');
  assert(Array.isArray(a.counts) && a.counts.length === 3, 'counts 必须是三层');
  assert(a.counts.every((n) => n >= 0 && n <= 4), `counts 各层应在 0..4，实得 ${a.counts}`);
  // 关掉全部注家显示：段头仍在，只有段内行变 —— 这正是「开关不改段集」。
  const hidden = runLingqi({ ...at, zhuVisible: { yan: 0, he: 0, chen: 0, liu: 0, ke: 0, shi: 0 } });
  const hiddenTitles = hidden.snapshot_text.split('\n').filter((l) => l.startsWith('[')).map((l) => l.trim());
  assert(JSON.stringify(hiddenTitles) === JSON.stringify(titles), '注家开关不得改变段集');
  assert(hidden.snapshot_text !== a.snapshot_text, '注家开关必须改变段内文本（否则开关是死旋钮）');
  // 冻结卦：显式 counts 必须被照单复排，而不是按种子重掷。
  const frozen = runLingqi({ ...at, counts: [4, 0, 2] });
  assert(
    JSON.stringify(frozen.counts) === JSON.stringify([4, 0, 2]),
    `冻结 counts 必须原样复排，实得 ${frozen.counts}`,
  );
});

// 天星择日 [单时判读]（v0.33.0）：explain 树（编译形）+ UI 树 DFS 配对 → 设定/实际 文本段。
check('tianxing explain_section renders 设定/实际 pairs with ✓✗', () => {
  // 叶用 skill schema 的裸形（{type, params}，无 kind）——这是 agent 实际传入的形状。
  const uiTree = {
    kind: 'group', joiner: 'all', children: [
      { type: 'in_sign', params: { planet: 'Venus', signs: [5] } },
      { type: 'aspect', params: { planetA: 'Venus', planetB: 'Moon', angle: 120, orb: 6 }, negate: true },
    ],
  };
  const explain = {
    kind: 'group', op: 'all', pass: false, children: [
      { kind: 'leaf', type: 'in_sign', pass: true, actual: '金 158°51′ 处女' },
      { kind: 'leaf', type: 'aspect', pass: false, actual: '金-月 距 120° 差 8.2°(限 6°)' },
    ],
  };
  const r = runTianxing({ action: 'explain_section', t: '2026/09/01 14:30:00', tree: uiTree, explain });
  assert(r.data.ok === true, 'data.ok should be true');
  const s = r.snapshot_text || '';
  assert(s.startsWith('[单时判读]'), 'missing [单时判读] header');
  assert(s.includes('判读时刻：2026/09/01 14:30:00'), 'missing 判读时刻 line');
  assert(s.includes('且(全部满足) ✗'), 'missing group gate line');
  assert(s.includes('✓') && s.includes('✗'), 'missing pass marks');
  const settings = s.split('\n').filter((l) => l.trim().startsWith('设定 '));
  const actuals = s.split('\n').filter((l) => l.trim().startsWith('实际 '));
  assert(settings.length === 2 && actuals.length === 2, `expected 2 设定/实际 pairs, got ${settings.length}/${actuals.length}`);
  assert(s.includes('(取反)'), 'negate leaf must carry (取反)');
  assert(actuals[1].includes('金-月'), 'actual text must come from the explain tree');
});

// 七政择日动盘（v0.33.0 批 I-1b）：山位换算走 vendored electionCore（232.9° 罗盘 → 00申山24，
// 与 GuoLaoElectionTable 同式）；黄道列为地支镜像度（白羊=戌）。
check('qizhengelection pan renders 地支度+山位+地平号', () => {
  const r = runQizhengElection({
    kind: 'pan',
    fields: { date: '2026-09-01', time: '14:30', zone: '+08:00', pos: '北京' },
    options: { plate: 'di', ziZheng: 'true', eleLifeMode: 'sunrise' },
    data: {
      trueSolarTime: '14:15:31', equationOfTimeMin: -0.0809, lifeDeg: 157.578,
      sunAzimuthSpeedDegPerMin: 0.2819,
      rise: { sunrise: '05:42:11', sunset: '18:31:04', moonrise: '20:02:00', moonset: '08:11:00' },
      planets: [
        { id: 'Sun', label: '日', lonTropical: 158.855, retrograde: false, azimuth: 232.9188, altitudeTrue: 46.25 },
        { id: 'Mercury', label: '水', lonTropical: 172.4, retrograde: true, azimuth: 245.1, altitudeTrue: -3.4 },
      ],
    },
  });
  assert(r.data.ok === true, `ok=false: ${JSON.stringify(r.data.error || {})}`);
  const s = r.snapshot_text || '';
  for (const sec of ['[起盘信息]', '[择日动盘]', '[天象要素]']) {
    assert(s.includes(sec), `missing ${sec}`);
  }
  // 158.855° = 处女 8°51′ → 镜像地支 巳（白羊=戌序）；232.92° 罗盘 → 00申山25（vendored mountainPosition 实算）。
  assert(s.includes('日：08巳51 | 00申山25+ | 方位 232.9° 高度 46.3° | 平'), `sun row wrong: ${s.split('\n').find((l) => l.startsWith('日：'))}`);
  assert(s.includes('| 逆'), 'retrograde mark missing');
  assert(s.includes('真太阳时：14:15:31') && s.includes('命度：07巳34（日出起）'), 'astronomy extras wrong');
});

check('qizhengelection eclipses decodes swisseph kind flags', () => {
  const r = runQizhengElection({
    kind: 'eclipses',
    fields: { date: '2026-09-01', zone: '+08:00' },
    options: { kind: 'solar' },
    data: { rows: [
      { date: '2027-02-06', time: '23:59:39', kindFlag: 9 },
      { date: '2027-08-02', time: '18:06:41', kindFlag: 5 },
    ] },
  });
  const s = r.snapshot_text || '';
  assert(s.includes('未来日食'), 'missing title');
  assert(s.includes('2027-02-06 23:59:39　环食·中心'), 'annular decode wrong');
  assert(s.includes('2027-08-02 18:06:41　全食·中心'), 'total decode wrong');
});

check('qizhengelection azimuthsearch rows carry 山位', () => {
  const r = runQizhengElection({
    kind: 'azimuthsearch',
    fields: { date: '2026-09-01', zone: '+08:00' },
    options: { body: '日', targetAz: 180, days: 1 },
    data: { rows: [{ date: '2026-09-01', time: '12:14:31', azimuth: 180.0 }] },
  });
  const s = r.snapshot_text || '';
  assert(s.includes('日 到达 180.0°(未来 1 天)'), 'missing title (upstream verbatim)');
  assert(s.includes('12:14:31　180.0°（07午山30）'), `row wrong: ${s}`);
});

check('tianxing explain_section without explain tree fails loudly', () => {
  const r = runTianxing({ action: 'explain_section', t: 'x', tree: null, explain: null });
  assert(r.data.ok === false, 'missing explain must be ok=false');
  assert(r.data.error.code === 'missing_explain_tree', `code=${r.data.error.code}`);
});

// 八字格局 值级金标：固定盘 1989-09-04 00:30 男（己巳 壬申 丁卯 庚子）跑真引擎，逐字冻结四项。
//
// 🔴 为什么要值级、不只查段头：baziGeju.js 曾把时柱键写成 `hour`（三个引擎一律读 `time`），四柱
// 静默变三柱 —— 段头照出、行数照够、任何「有没有 [格局·用神]」式断言全绿，只有值是错的：取格从
// 正财格塌成正官格、日主同党 34.3%(真值 27.9%)、盲派 `时宾()` 空。四柱来源与生产同构
// （buildLocalBaziResult 即上游本地引擎），所以这里冻的就是用户会看到的那串字。
check('baziGeju 值级金标：时柱入算 + 取格/成败/盲派逐字', () => {
  const birth = { date: '1989-09-04', time: '00:30:00', zone: 8, lon: 120, gender: 1, timeAlg: 1 };
  const bazi = buildLocalBaziResult(birth).bazi;
  const fc = bazi.fourColumns;
  assert(fc.time && fc.time.ganzi === '庚子', `fixture 时柱 drifted: ${fc.time && fc.time.ganzi}`);
  const s = runBaziGeju({ fourColumns: fc, birth }).snapshot_text || '';
  for (const sec of ['[五行力量]', '[格局·用神]', '[盲派结构]', '[月令司令（分野）]']) {
    assert(s.includes(sec), `missing ${sec}`);
  }
  // 取格：时柱缺席时会误判成「正官格（月令官·中气透干）」。
  assert(s.includes('格局：正财格（月令财·本气透干）'), `geju wrong: ${s.split('\n').find((l) => l.startsWith('格局：'))}`);
  // 成败/破格行（桌面 BaZi.js 有、快照层曾整行不渲染）。
  assert(s.includes('成败：破格——月令申逢刑，忌神坏格无救。'), 'missing 成败 line');
  // 五行力量：时柱庚子入算才是 27.9%（缺时柱 34.3%）。
  assert(s.includes('日主火：身弱（同党印比 27.9%'), `dayMaster wrong: ${s.split('\n').find((l) => l.startsWith('日主'))}`);
  // 盲派宾主四位齐全 —— 时柱缺席时这里是 `时宾()`。
  assert(s.includes('宾主：年宾(己巳) 月宾(壬申) 日主(丁卯) 时宾(庚子)'), `mangpai wrong: ${s.split('\n').find((l) => l.startsWith('宾主：'))}`);
  assert(!/时宾\(\)/.test(s), '时柱 dropped out of 盲派 (fourColumns key must be `time`, not `hour`)');
});

if (failures > 0) {
  console.error(`\nselfcheck: ${failures} failure(s)`);
  process.exit(1);
}
console.log('\nselfcheck: all JS engine golden checks passed');
