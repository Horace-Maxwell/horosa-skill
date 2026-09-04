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
import { ZiLiuQin } from '../src/vendor/liureng/LRConst.js';
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
import { runTiebanFramework } from '../src/tools/tiebanFramework.js';
import { buildTiebanFramework } from '../src/vendor/tieban/tiebanFrameworkLocal.js';
import { computeQimenScanPan, buildQimenScanSeeds } from '../src/vendor/divination/zeri/qimenScanEngine.js';
import { buildLocalBaziResult } from '../src/vendor/bazi/baziLunarLocal.js';
import { runCanping } from '../src/tools/canping.js';
import { personBazi } from '../src/vendor/calendar/riziEngine.js';
import { runZeriScan, ZERI_TECHNIQUES } from '../src/tools/zeriScan.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const chart = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_traditional.json'), 'utf8'));
const liurengFix = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_liureng.json'), 'utf8'));
const guolaoFix = JSON.parse(readFileSync(join(HERE, 'fixtures', 'chart_guolao.json'), 'utf8'));

let failures = 0;
// 🔴 check() 必须认异步：早先它只 `fn()` 不看返回值，async 断言体的失败会变成
// unhandled rejection —— 打印 `ok`、退出码 0、CI 全绿，而断言其实根本没验。这与本轮清剿的
// 「presence 级绿灯掩盖值级错误」是同一形状，只不过发生在 harness 自己身上。
const pending = [];
process.on('unhandledRejection', (err) => {
  failures += 1;
  console.error(`  FAIL <unhandled rejection>: ${err && err.message ? err.message : err}`);
});
function check(name, fn) {
  try {
    const out = fn();
    if (out && typeof out.then === 'function') {
      pending.push(out.then(
        () => console.log(`  ok   ${name}`),
        (err) => { failures += 1; console.error(`  FAIL ${name}: ${err.message}`); },
      ));
      return;
    }
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

check('liureng 三传六亲走 vendor ZiLiuQin（消费点金标——手抄表时代 vendor 金标看不见它）', () => {
  const r = runLiureng({ ...liurengFix });
  const chartObj = normalizeChart(liurengFix);
  const daygan = `${chartObj.nongli.dayGanZi}`.charAt(0);
  const find = (o) => {
    if (!o || typeof o !== 'object') return null;
    if (Array.isArray(o.cuang) && Array.isArray(o.liuQin)) return o;
    for (const v of Object.values(o)) { const hit = find(v); if (hit) return hit; }
    return null;
  };
  const sanchuan = find(r.data);
  assert(sanchuan && sanchuan.liuQin.length === 3, 'sanchuan object with cuang/liuQin not found in data');
  sanchuan.cuang.forEach((gz, i) => {
    const zi = `${gz}`.slice(-1);
    const want = (ZiLiuQin[zi] || {})[daygan] || '无';
    assert(sanchuan.liuQin[i] === want, `三传 ${gz} 六亲 ${sanchuan.liuQin[i]} ≠ vendor ${want}（日干 ${daygan}）`);
  });
});

check('liureng snapshot carries 毕法 + 占断向导 sections', () => {
  const r = runLiureng({ ...liurengFix, zhanCategory: 'hunyin' });
  const s = r.snapshot_text || '';
  assert(s.includes('[常用神煞]'), 'missing 常用神煞');
  assert(s.includes('[毕法（已命中）]'), 'missing 毕法 section');
  assert(/\n\d+\.\s/.test(s), 'no numbered 毕法 entries');
  assert(s.includes('[占断向导]') && s.includes('占事：婚姻'), 'missing 占断向导 for hunyin');
});

// 🔴 v0.35.0 值级金标：六亲表 ≡ 五行生克公式，120 格逐格对拍（上游 v3.9.4 真值校准同法）。
// LRConst.js 是 curated 手工件，`--from-manifest` 不碰它：乙日巳/午两格「父母」（应为「子孙」：
// 乙木生巳午火＝我生者）在四轮同步里静默滞留。负向对照：把任一格改回去，本检查必红。
check('liureng ZiLiuQin 六亲表与五行生克公式 120 格逐格一致', () => {
  const WX_GAN = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };
  const WX_ZHI = { 子: '水', 亥: '水', 寅: '木', 卯: '木', 巳: '火', 午: '火', 申: '金', 酉: '金', 辰: '土', 戌: '土', 丑: '土', 未: '土' };
  const SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };  // 我生
  const KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };     // 我克
  const expect = (gan, zhi) => {
    const me = WX_GAN[gan], it = WX_ZHI[zhi];
    if (me === it) return '兄弟';
    if (SHENG[me] === it) return '子孙';
    if (SHENG[it] === me) return '父母';
    if (KE[me] === it) return '妻财';
    return '官鬼';
  };
  const bad = [];
  let cells = 0;
  for (const zhi of Object.keys(WX_ZHI)) {
    for (const gan of Object.keys(WX_GAN)) {
      cells += 1;
      const got = ZiLiuQin[zhi] && ZiLiuQin[zhi][gan];
      if (got !== expect(gan, zhi)) bad.push(`${zhi}.${gan}=${got}(应${expect(gan, zhi)})`);
    }
  }
  assert(cells === 120, `expected 120 cells, walked ${cells}`);
  assert(bad.length === 0, `六亲表与公式不符: ${bad.join(' ')}`);
  assert(ZiLiuQin['巳']['乙'] === '子孙' && ZiLiuQin['午']['乙'] === '子孙', '乙日巳/午 must be 子孙 (upstream v3.9.4)');
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

// 🔴 v0.33.1 值级金标：params 必须是**起盘时刻**，不是 /chart 信封。
// 引擎读 params.time 判昼夜（:390）、params.date 判冬令（:397）；信封里两者都没有
// （只有 birth），于是 isDay 恒真、isWinter 恒假 —— 夜生盘拿天贵而非玉贵、孤月独明永不触发、
// 冬令排除永不生效。段照出、格局照列，只有判据是错的。
// 负向对照：把 params 换回整个信封，「12月 冬令」这条即红（金水相涵 会重新出现）。
check('guolaoMoira params 是起盘时刻：冬令排除真的生效', () => {
  const names = (params) => (runGuolaoMoira({ ...guolaoFix, params }).data.patterns || []).map((p) => p.name);
  const spring = names({ date: '1985-03-21', time: '10:00:00' });
  const winter = names({ date: '1985-12-21', time: '10:00:00' });
  assert(spring.includes('金水相涵'), `非冬令应命中金水相涵，实得 ${spring.join(',')}`);
  assert(!winter.includes('金水相涵'), `冬令须排除金水相涵（引擎 :203 的 !isWinter），实得 ${winter.join(',')}`);
  // 传整个信封 = 修复前的形状：date 取不到 → 恒非冬 → 冬令盘也会误报金水相涵
  const envelope = names(guolaoFix.chart || guolaoFix);
  assert(envelope.includes('金水相涵'), '信封形状应复现旧行为（此断言记录 bug 形状，勿删）');
});

// 🔴 v0.33.1 值级金标：起局三开关（timeAlg / after23NewDay / lateZiHourUseNextDay）是 QimenInput
// 继承来的**顶层**字段，扫描引擎却只从 options 读（qimenScanEngine.js:124-126）。Python 侧此前只传
// payload["options"] → 顶层写法静默丢弃，命中区间用默认起局算，而同一次调用的展示盘（走
// _run_qimen_tool）是 honor 顶层的 → 两者不同局，配置段还打出一个没用上的设置标签。
// ⚠️ 真太阳时校正需要 `lon`（不是只有 gpsLon）——测本条时 geo 必须带 lon，否则 timeAlg 看不出差异。
// 负向对照：Python 侧改回只读 options 并用顶层 timeAlg 调用，命中集即与 timeAlg=0 相同。
check('qimenzeri 起局口径真的生效：timeAlg 改变时柱', () => {
  const seeds = buildQimenScanSeeds(2028, 2028, 8);
  const geo = { zone: 8, lon: '119e18', lat: '26n05', gpsLon: 119.3, gpsLat: 26.08 };
  const at = (timeAlg) => computeQimenScanPan(geo, { timeAlg }, seeds, '2028-04-01', '19:02:00').ganzhi.time;
  assert(at(0) === '丁酉', `timeAlg=0 应为平太阳时 丁酉，实得 ${at(0)}`);
  assert(at(1) === '戊戌', `timeAlg=1 应为真太阳时 戊戌，实得 ${at(1)}`);
});

// 🔴 v0.33.1 值级金标：cfg 必须带黄道口径。[征象搜索配置] 的「搜索盘面」行读 cfg.zodiacal
// （tianxingSnapshot.js:76），Python 此前没往 ctx.cfg 里送 → 恒星盘搜索也恒打「回归黄道」，
// 而同一份输出里 [起盘信息] 的「黄道：」行读 fields（已正确填充）→ 一份交付物两行自相矛盾。
// 负向对照：从 cfg 里拿掉 zodiacal，本条即红。
check('tianxing 搜索盘面口径与实际搜索一致（恒星黄道不再被打成回归）', () => {
  const fields = { date: { value: '2029-03-01' }, time: { value: '00:00:00' }, zone: { value: 8 },
    zodiacal: { value: 1 }, siderealAyanamsa: { value: 'fagan_bradley' } };
  const line = (cfg) => (runTianxing({ action: 'snapshot', fields,
    ctx: { cfg, tree: { kind: 'group', joiner: 'all', children: [] }, results: [], truncated: false } }).snapshot_text || '')
    .split('\n').find((l) => l.startsWith('搜索盘面')) || '';
  const withZod = line({ startDate: '2029-03-01', endDate: '2029-03-10', hsys: 3, zodiacal: 1, siderealAyanamsa: 'fagan_bradley' });
  assert(withZod.includes('恒星黄道(fagan_bradley)'), `恒星盘应打恒星黄道，实得 ${withZod}`);
  // 缺 zodiacal = 修复前形状：恒打回归（此断言记录 bug 形状，勿删）
  assert(line({ startDate: '2029-03-01', endDate: '2029-03-10', hsys: 3 }).includes('回归黄道'), 'bug 形状复现失败');
});

// 🔴 v0.33.1 值级金标：铁板「考刻」。引擎读 opts.ke（tiebanFrameworkLocal.js:253），从不读
// opts.minute —— 工具此前传的正是 minute，于是 ke 恒为 1：eightKe.active 恒高亮初刻，
// 96 局（12 时辰 × 8 刻）塌缩成 12 个可达值，14:47 与 14:03 出同一局。刻分是铁板的立身之本。
// 换算口径：一时辰 120 分 = 8 刻 × 15′，时辰自**奇数**小时起（子 23、丑 1…），故偶数小时要 +60。
// 负向对照：把 ke 换回 minute 传入，下面 ju.ke 全变 1。
check('tiebanFramework 考刻由时分换算，96 局不再塌缩', () => {
  const fp = { year: '己巳', month: '壬申', day: '丁卯', hour: '庚子' };
  const ju = (ke) => buildTiebanFramework(fp, { birthYear: 1989, gender: 1, ke }).ju;
  assert(ju(1).label === '子时初刻＝全日第1刻', `ke=1 → ${ju(1).label}`);
  assert(ju(8).label === '子时八刻＝全日第8刻', `ke=8 → ${ju(8).label}`);
  // 端到端：同一时辰内的不同分钟必须落到不同刻（这正是修复前做不到的）
  const keOf = (hour, minute) => {
    const r = runTiebanFramework({ pillars: [
      { key: 'year', ganzhi: '己巳' }, { key: 'month', ganzhi: '壬申' },
      { key: 'day', ganzhi: '丁卯' }, { key: 'hour', ganzhi: '庚子' }], birthYear: 1989, gender: 1, hour, minute });
    return /全日第(\d+)刻/.exec(r.text || '');
  };
  const a = keOf(19, 3);   // 戌初，第 1 刻
  const b = keOf(20, 47);  // 戌末，第 8 刻
  assert(a && b && a[1] !== b[1], `同时辰不同分钟须落不同刻，实得 ${a && a[1]} vs ${b && b[1]}`);
});

check('calendarExtras 当事人时辰真的进盘（time 只喂时刻）', () => {
  // 值级：同日不同时辰的当事人，喜忌必须不同。修复前 calendarExtras 把
  // `YYYY-MM-DD HH:MM:SS` 整串塞给 time，parseDateTime 做 `time.split(':')` 后
  // Number('1990-05-15 03') = NaN → hour 恒 0 → 每个当事人都按子时起盘。
  const xi = (clock) => JSON.stringify(personBazi({ date: '1990-05-15', time: clock, gender: 1 }).xi);
  assert(xi('03:00:00') === '["水","木","火"]', `03:00 喜用实得 ${xi('03:00:00')}`);
  assert(xi('21:00:00') === '["水"]', `21:00 喜用实得 ${xi('21:00:00')}`);
  // 负向对照：把旧的整串形状喂回去，两个时辰会重新塌成同一盘（bug 复现）。
  const old = (clock) => JSON.stringify(personBazi({ date: '1990-05-15', time: `1990-05-15 ${clock}`, gender: 1 }).xi);
  assert(old('03:00:00') === old('21:00:00'), '旧整串形状本应塌盘，负向对照失效说明引擎已改口径');
});

check('canping 起运岁走农历真源，不再恒 1 岁', async () => {
  // 值级锚定：baziStyle 档的起运岁必须等于八字盘 direction[0].age（同源判据，
  // 不是自证）；默认《参评诀》档由农历月日推算，同盘得 3 岁。修复前 lunarMonth/
  // lunarDay 没转发 → 引擎守卫判非法 → 起运岁恒回落 1，九个大运区间整体平移。
  const birth = { date: '1998-02-20', time: '20:48:00', zone: 8, lon: '121e28', gender: '男' };
  const firstDayunAge = buildLocalBaziResult({ ...birth, gender: 1, timeAlg: 1 }).bazi.direction[0].age;
  assert(firstDayunAge === 5, `八字盘首运虚岁应为 5，实得 ${firstDayunAge}`);
  const qiyunOf = async (dayunRule) => (await runCanping({ ...birth, dayunRule })).data.qiyunAge;
  assert(await qiyunOf(undefined) === 3, `默认档起运岁应为 3，实得 ${await qiyunOf(undefined)}`);
  assert(await qiyunOf('baziStyle') === firstDayunAge,
    `baziStyle 档须与八字盘同源（${firstDayunAge}），实得 ${await qiyunOf('baziStyle')}`);
});

check('zhengchuan 大定男女分行，性别不再被 NaN 吃掉', async () => {
  // 值级：同盘男女的 大运／小运／岁君 必须不同。修复前传的是裸 gender，
  // 而 baziLunarLocal 做 `Number(params.gender) === 0 ? 0 : 1` —— Number('女') = NaN
  // ≠ 0 → 一律判男顺行 → 女命的大定死限年整体错位，且照常自信输出。
  const base = { school: 'dading', pillars: ['戊寅', '甲寅', '壬戌', '庚戌'], date: '1998-02-20',
    time: '20:48:00', zone: 8, lon: '121e28', lunarMonth: 1, lunarDay: 24, dadingYear: 2030 };
  const textOf = async (gender) => (await runZhengChuan({ ...base, gender })).snapshot_text || '';
  const male = await textOf('男');
  const female = await textOf('女');
  const yunLine = (s) => (s.split('\n').find((l) => l.includes('大运／小运／岁君')) || '').trim();
  assert(yunLine(male) && yunLine(female), '大定快照应含 大运／小运／岁君 行');
  assert(yunLine(male) !== yunLine(female),
    `男女须分行，实得同一行：${yunLine(male)}`);
  // 数字形式与中文形式必须等价（'女' 与 0 同盘）。
  assert(yunLine(await textOf(0)) === yunLine(female), '性别 0 应与 “女” 同盘');
});

check('baziGeju 分野口径真的进五行力量 + 缺柱不再无声', async () => {
  // 值级：cangVersion='fenye' 必须改变百分比分布（修复前 fy 在 st 之后才算，
  // 分野档结构上不可达 —— [月令司令（分野）] 报着司令干，[五行力量] 却按通行版加权）。
  const birth = { date: '1989-08-15', time: '23:30:00', zone: 8, lon: '121e28', gender: 1, timeAlg: 1 };
  const fc = buildLocalBaziResult(birth).bazi.fourColumns;
  const distOf = async (cangVersion) => {
    const s = (await runBaziGeju({ fourColumns: fc, birth, cangVersion })).snapshot_text || '';
    return (s.split('\n').find((l) => l.startsWith('分布：')) || '').trim();
  };
  const common = await distOf(undefined);
  const fenye = await distOf('fenye');
  assert(common === '分布：木2.6%　火22.3%　土23.6%　金18%　水33.5%', `通行档实得 ${common}`);
  assert(fenye === '分布：木2.7%　火23.6%　土23.6%　金14.5%　水35.5%', `分野档实得 ${fenye}`);
  assert(common !== fenye, '分野档必须改变加权，相同即说明 siLingGan 没接上');
  // 说明行须与实算口径一致（两段自相矛盾正是修复前的症状）。
  const fenyeText = (await runBaziGeju({ fourColumns: fc, birth, cangVersion: 'fenye' })).snapshot_text;
  assert(fenyeText.includes('（分野加权：'), '分野档说明行未切换');
  // 守卫查的是引擎真读的字段：柱在、stemInBranch 缺时必须结构化报错，而不是无声空段。
  const noCang = await runBaziGeju({ fourColumns: { ...fc, time: { stem: fc.time.stem } } });
  assert(noCang.data && noCang.data.ok === false && noCang.data.reason === 'incomplete_four_pillars',
    `藏干缺应结构化报错，实得 ${JSON.stringify(noCang.data)}`);
  assert(noCang.data.message.includes('time'), '错误须点名缺哪一柱');
});

check('horary/election 判读层旋钮真的接进引擎（锚定引擎自带词表）', () => {
  // 值级：覆写判读层参数必须改变快照。修复前 horary 只喂 horaryJudgeOpts 第 1 层、
  // election 干脆 runElection(chart, topicId) 两参调用 —— 46+13 个真参数结构上不可达，
  // 而 schema 上挂着一排旋钮（其中 receptionMode/almutenScheme/dignityScheme 等
  // 在引擎词表里根本不存在，是发明的名字）。
  const base = runHoraryTool({ chart, category: 'marriage' });
  const over = runHoraryTool({ chart, category: 'marriage', considerationsMode: 'ignore', lotsSet: 'core15' });
  assert(JSON.stringify(over.data.params_applied) === '["considerationsMode","lotsSet"]',
    `覆写未被采纳：${JSON.stringify(over.data.params_applied)}`);
  assert(base.snapshot_text !== over.snapshot_text, 'horary 判读层覆写必须改变快照');
  // 认不出的键要**回执**，不能像整包 opts 那样无声吞掉。
  const bogus = runHoraryTool({ chart, category: 'marriage', options: { notARealKnob: 1 } });
  assert(JSON.stringify(bogus.data.params_ignored) === '["notARealKnob"]',
    `未知键须回执，实得 ${JSON.stringify(bogus.data.params_ignored)}`);
  const e1 = runElectionTool({ chart, topicId: 'marriage' });
  const e2 = runElectionTool({ chart, topicId: 'marriage', school: 'hellenistic', options: { orbProfile: 'classic' } });
  assert(e1.data.school === 'modern_main' && e2.data.school === 'hellenistic',
    `流派档未生效：${e1.data.school} / ${e2.data.school}`);
  assert(e1.snapshot_text !== e2.snapshot_text, 'election 流派/参数覆写必须改变快照');
});

check('zeriScan 择日六技法：命中区间锚定到独立算出的真值', async () => {
  // 值级锚定：八字择时搜「甲子日」，61 天窗内必须恰好命中一次，且那一天由**另一条链**
  // （buildLocalBaziResult）独立确认确实是甲子日。这不是自证 —— 扫描引擎与八字排盘是两套代码。
  const geo = { zone: 8, lon: '121e28', lat: '31n14' };
  const jiazi = await runZeriScan({
    technique: 'bazizeri', action: 'scan',
    cfg: { startDate: '2026-03-01', startTime: '00:00', endDate: '2026-04-30', endTime: '23:59' },
    geo, options: { timeAlg: 1 },
    tree: { kind: 'group', joiner: 'all', negate: false, children: [
      { kind: 'leaf', type: 'day_ganzhi', negate: false, joiner: 'all', params: { values: ['甲子'] } }] },
  });
  assert(jiazi.data.ok === true, `扫描失败：${JSON.stringify(jiazi.data.error)}`);
  assert(jiazi.data.hit_count === 1, `61 天窗内甲子日应恰好 1 次，实得 ${jiazi.data.hit_count}`);
  const hit = jiazi.data.intervals[0];
  assert(hit.start === '2026-04-19 23:00' && hit.end === '2026-04-20 23:00',
    `命中区间应是子时为界的甲子日，实得 ${hit.start} ~ ${hit.end}`);
  // 独立锚：那一天的日柱由八字引擎自己算，必须是甲子。
  const dayGz = (d) => buildLocalBaziResult({ date: d, time: '12:00:00', zone: 8, lon: '121e28', gender: 1, timeAlg: 1 })
    .bazi.fourColumns.day.ganZhi;
  assert(dayGz('2026-04-20') === '甲子', `锚定日应为甲子，实得 ${dayGz('2026-04-20')}`);
  assert(dayGz('2026-04-19') === '癸亥' && dayGz('2026-04-21') === '乙丑', '前后日应为癸亥/乙丑');

  // 六个成员都必须能跑通并给出**结构化**结果（零命中也是合法结果，但错误绝不能降级成零命中）。
  // 叶参数取**引擎自带的 defaults**（newXLeaf 的产物），不是手编 —— 手编的参数会被 validate 拒掉，
  // 而「拒掉」在这条金标里恰好也会红，于是很难分清是接线坏了还是我参数写错了。
  const probes = {
    huanglizeri: { type: 'yi_has', params: { values: ['嫁娶'], matchMode: 'any' } },
    taiyizeri: { type: 'yinyang_ju', params: { value: '阳' } },
    ziweizeri: { type: 'wuxing_ju', params: { values: ['3'] } },
    liurengzeri: { type: 'ke_name', params: { values: ['元首课'] } },
    sanshizeri: { type: 'lr_ke_name', params: { values: ['元首课'] } },
  };
  for (const [technique, leaf] of Object.entries(probes)) {
    const r = await runZeriScan({
      technique, action: 'scan',
      cfg: { startDate: '2026-03-01', startTime: '00:00', endDate: '2026-03-08', endTime: '23:59' },
      geo, options: { timeAlg: 1 },
      tree: { kind: 'group', joiner: 'all', negate: false, children: [{ kind: 'leaf', negate: false, joiner: 'all', ...leaf }] },
    });
    assert(r.data.ok === true, `${technique} 扫描失败：${JSON.stringify(r.data.error)}`);
    assert(Number.isFinite(r.data.hit_count), `${technique} 未给出 hit_count`);
  }
  // 认不出的条件类必须**报错**，不能静默零命中（那读起来是一个有效的空结果）。
  const bogus = await runZeriScan({
    technique: 'bazizeri', action: 'scan',
    cfg: { startDate: '2026-03-01', startTime: '00:00', endDate: '2026-03-02', endTime: '23:59' },
    geo, tree: { kind: 'group', joiner: 'all', children: [{ kind: 'leaf', type: 'notARealConditionType', params: {} }] },
  });
  assert(bogus.data.ok === false && bogus.data.error.code === 'invalid_conditions',
    `未知条件类应结构化报错，实得 ${JSON.stringify(bogus.data)}`);
  assert(Object.keys(ZERI_TECHNIQUES).length === 6, '本地扫描成员应为 6 个');
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

await Promise.all(pending);
if (failures > 0) {
  console.error(`\nselfcheck: ${failures} failure(s)`);
  process.exit(1);
}
console.log('\nselfcheck: all JS engine golden checks passed');
