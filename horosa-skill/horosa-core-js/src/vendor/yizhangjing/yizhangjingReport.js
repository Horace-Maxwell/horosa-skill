// 一掌经 · 模型装配 + AI 快照文本（引擎 + 断语数据 → 展示模型 / 快照串）。
// UI 与 AI 挂载共用本模块；引擎(yizhangjingLocal)保持纯函数，本模块负责农历解析与断语拼接。
import {
	calcYizhangjing, BRANCHES, ZODIAC, STARS, gradeOf, wuxingState, xiaoxianStarAt, xunShenAt,
	pillarWeights, nineGradeExact, tongxianList, xiaoxianStarAtDir, xiaoxianQuick, xunShenRoles,
	flowSub, brotherCount, starPolarity, branchClash, pairHits, pillarWuxing, ziSubPeriod, starLabel, daoLabel,
} from './yizhangjingLocal.js';
import DATA from './data/yizhangjingData.json' with { type: 'json' };
import SHENSHA from './data/yizhangjingShensha.json' with { type: 'json' };
import LORE from './data/yizhangjingLore.json' with { type: 'json' };

// 农历月序 → 文献层月诗键（与 YiZhangJingMain 的 MONTH_LABELS 同表；1 起）。
const LORE_MONTH_LABELS = ['', '正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];

const ZODIAC_TO_BRANCH = {};
ZODIAC.forEach((z, i) => { ZODIAC_TO_BRANCH[z] = BRANCHES[i]; });

// 从 baziLunarLocal 的 bazi 结果解析一掌经四宫入参（正月初一年支 + 农历月/日 + 时支）。
// 岁首＝正月初一(shengXiaoLunar/yearGZByLunar)，非立春——一掌经口径，异八字。
export function resolveLunarInput(bazi, opts) {
	if (!bazi) return null;
	const nl = bazi.nongli || {};
	const fc = bazi.fourColumns || {};
	const gz = (p) => (p && (p.ganzi || p.ganZhi)) || '';
	// 年支：正月初一口径
	let yearBranch = '';
	if (nl.yearGZByLunar && nl.yearGZByLunar.length >= 2) yearBranch = nl.yearGZByLunar.charAt(1);
	else if (nl.shengXiaoLunar && ZODIAC_TO_BRANCH[nl.shengXiaoLunar]) yearBranch = ZODIAC_TO_BRANCH[nl.shengXiaoLunar];
	// 时支
	const hourBranch = gz(fc.time).charAt(1);
	const gender = bazi.gender === 'Female' || bazi.gender === 0 || bazi.gender === '女' ? '女' : '男';
	// 月：默认农历月(monthNum)；节气月取八字月支序(寅=1…丑=12)
	let month = parseInt(nl.monthNum, 10) || 0;
	const lunarMonth = parseInt(nl.monthNum, 10) || 0; // 真实农历月序（不随定月法/闰月折算变动，供显示层标注生辰）
	let monthNote = '农历月';
	if (opts && opts.dingYue === 'jieqi') {
		const mZhi = gz(fc.month).charAt(1);
		const mi = BRANCHES.indexOf(mZhi);
		if (mi >= 0) {
			month = ((mi - BRANCHES.indexOf('寅') + 12) % 12) + 1;
			monthNote = '节气月';
		}
	} else if (nl.leap) {
		// 闰月归属：默认十五折半（十五含前作本月、后作下月）；
		// 夜半折半（leapRule='midnight'）：十五当日且生时=子且属晚子(00:xx)→作下月，余同十五折半。
		const day = parseInt(nl.dayNum, 10) || 0;
		const leapRule = opts && opts.leapRule === 'midnight' ? 'midnight' : 'half';
		let toNext = day > 15;
		let note = day > 15 ? '闰月·十五后作下月' : '闰月·十五前作本月';
		if (leapRule === 'midnight' && day === 15) {
			const hb15 = gz(fc.time).charAt(1);
			const hm = /(\d{1,2}):/.exec(`${nl.clockTime || ''}`);
			const lateZi = hb15 === '子' && hm && parseInt(hm[1], 10) === 0; // 晚子=00:xx
			if (lateZi) { toNext = true; note = '闰月·十五夜半(晚子)作下月'; }
		}
		if (toNext) { month = month + 1; if (month > 12) month -= 12; }
		monthNote = note;
	}
	const day = parseInt(nl.dayNum, 10) || 0;
	if (!yearBranch || !hourBranch || !month || !day) return null;
	return { yearBranch, month, lunarMonth, day, hourBranch, gender, monthNote, leap: !!nl.leap };
}

function starData(star) {
	return (DATA.data && DATA.data[star]) || {};
}

// ── 神煞合参层：起例（由生年支／日干支／月支／日柱旬定各神煞落地支）──────────────
// 通用命理合参口径（非本术原生）：年支类＝太岁顺行(岁前十二神)／三合／三会；
// 日干类＝贵人・禄・刃・食神临官；月支类＝血刃；旬空＝日柱旬。名称与断语逐字对应现有神煞表。
const SS_STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ssAt = (i) => BRANCHES[((i % 12) + 12) % 12];
const ssBi = (z) => BRANCHES.indexOf(`${z || ''}`);
// 三合桃花(咸池)／三合驿马／年支破碎／三会孤辰・寡宿
const SS_PEACH = { 申: '酉', 子: '酉', 辰: '酉', 亥: '子', 卯: '子', 未: '子', 寅: '卯', 午: '卯', 戌: '卯', 巳: '午', 酉: '午', 丑: '午' };
const SS_HORSE = { 申: '寅', 子: '寅', 辰: '寅', 亥: '巳', 卯: '巳', 未: '巳', 寅: '申', 午: '申', 戌: '申', 巳: '亥', 酉: '亥', 丑: '亥' };
const SS_BROKEN = { 子: '巳', 午: '巳', 卯: '巳', 酉: '巳', 寅: '酉', 申: '酉', 巳: '酉', 亥: '酉', 辰: '丑', 戌: '丑', 丑: '丑', 未: '丑' };
const SS_GU = { 亥: '寅', 子: '寅', 丑: '寅', 寅: '巳', 卯: '巳', 辰: '巳', 巳: '申', 午: '申', 未: '申', 申: '亥', 酉: '亥', 戌: '亥' };
const SS_GUA = { 亥: '戌', 子: '戌', 丑: '戌', 寅: '丑', 卯: '丑', 辰: '丑', 巳: '辰', 午: '辰', 未: '辰', 申: '未', 酉: '未', 戌: '未' };
// 日干类（文昌・禄・阳刃・天乙贵人两位・食神临官天厨・国印贵人）
const SS_WENCHANG = { 甲: '巳', 乙: '午', 丙: '申', 丁: '酉', 戊: '申', 己: '酉', 庚: '亥', 辛: '子', 壬: '寅', 癸: '卯' };
const SS_LU = { 甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午', 庚: '申', 辛: '酉', 壬: '亥', 癸: '子' };
const SS_YANGREN = { 甲: '卯', 乙: '辰', 丙: '午', 丁: '未', 戊: '午', 己: '未', 庚: '酉', 辛: '戌', 壬: '子', 癸: '丑' };
const SS_TIANYI = { 甲: ['丑', '未'], 乙: ['子', '申'], 丙: ['亥', '酉'], 丁: ['亥', '酉'], 戊: ['丑', '未'], 己: ['子', '申'], 庚: ['丑', '未'], 辛: ['寅', '午'], 壬: ['卯', '巳'], 癸: ['卯', '巳'] };
const SS_TIANCHU = { 甲: '巳', 乙: '午', 丙: '巳', 丁: '午', 戊: '申', 己: '酉', 庚: '亥', 辛: '子', 壬: '寅', 癸: '卯' };
const SS_GUOYIN = { 甲: '戌', 乙: '亥', 丙: '丑', 丁: '寅', 戊: '丑', 己: '寅', 庚: '辰', 辛: '巳', 壬: '未', 癸: '申' };
// 月支类（血刃，按农历月序对应之月支）
const SS_XUEREN = { 寅: '丑', 卯: '未', 辰: '寅', 巳: '申', 午: '卯', 未: '酉', 申: '辰', 酉: '戌', 戌: '巳', 亥: '亥', 子: '午', 丑: '子' };

// 日柱旬空两支
function ssXunKong(dayGZ) {
	if (!dayGZ || dayGZ.length < 2) return [];
	const gi = SS_STEMS.indexOf(dayGZ.charAt(0));
	const zi = ssBi(dayGZ.charAt(1));
	if (gi < 0 || zi < 0) return [];
	const k = ((((zi - gi) % 12) + 12) % 12 + 10) % 12; // 旬空首支＝旬内未历之支
	return [ssAt(k), ssAt(k + 1)];
}

// 定位 21 神煞落地支（缺项静默略过）：返回 [{name,branches:[支…],group}]
export function locateShensha(input, bazi) {
	if (!input) return [];
	const yb = input.yearBranch;
	const yi = ssBi(yb);
	if (yi < 0) return [];
	const fc = (bazi && bazi.fourColumns) || {};
	const dayGZ = (fc.day && (fc.day.ganzi || fc.day.ganZhi)) || '';
	const monthZhi = ((fc.month && (fc.month.ganzi || fc.month.ganZhi)) || '').charAt(1);
	const dg = dayGZ.charAt(0);
	const out = [];
	const push = (name, branches, group) => {
		const bs = (Array.isArray(branches) ? branches : [branches]).filter((b) => b && ssBi(b) >= 0);
		if (bs.length) out.push({ name, branches: Array.from(new Set(bs)), group });
	};
	// 年支类：岁前十二神（太岁顺行）＋红鸾天喜天哭＋三合桃花驿马＋年支破碎＋三会孤寡
	push('大耗', ssAt(yi + 6), '年支·岁前');
	push('病符', ssAt(yi + 11), '年支·岁前');
	push('白虎', ssAt(yi + 8), '年支·岁前');
	push('喪門', ssAt(yi + 2), '年支·岁前');
	push('天狗', ssAt(yi + 10), '年支·岁前');
	push('五鬼年飛', ssAt(yi + 4), '年支·岁前');
	push('紅鸞', ssAt(3 - yi), '年支');
	push('天喜', ssAt(9 - yi), '年支');
	push('天哭', ssAt(6 - yi), '年支');
	push('咸池', SS_PEACH[yb], '年支·三合');
	push('驛馬', SS_HORSE[yb], '年支·三合');
	push('的殺破碎', SS_BROKEN[yb], '年支');
	push('孤辰寡宿', [SS_GU[yb], SS_GUA[yb]], '年支·三会');
	// 日干类
	if (dg) {
		push('文昌', SS_WENCHANG[dg], '日干');
		push('祿勳', SS_LU[dg], '日干·禄');
		if (SS_YANGREN[dg]) push('陽刃飛刃', [SS_YANGREN[dg], ssAt(ssBi(SS_YANGREN[dg]) + 6)], '日干·刃');
		push('天玉貴', SS_TIANYI[dg], '日干·贵人');
		push('天廚', SS_TIANCHU[dg], '日干');
		push('國印', SS_GUOYIN[dg], '日干·贵人');
	}
	// 月支类
	if (monthZhi) push('血刃', SS_XUEREN[monthZhi], '月支');
	// 日柱旬空
	push('空亡', ssXunKong(dayGZ), '日柱·旬空');
	return out;
}

// 人事宫首字(简体) → 神煞表宫键(繁体短名)：仅 财→財、迁→遷 相异
const SS_PALACE_KEY = { 命: '命', 财: '財', 兄: '兄', 田: '田', 子: '子', 奴: '奴', 夫: '夫', 疾: '疾', 迁: '遷', 官: '官', 福: '福', 相: '相' };

// 神煞落宫命中：把每个神煞的落地支映射到坐该支的人事宫，取该宫断语（仅列本盘落宫）
export function computeShenshaHits(input, bazi, renshi) {
	const located = locateShensha(input, bazi);
	if (!located.length || !renshi || !renshi.length) return [];
	const byBranch = {};
	renshi.forEach((g, i) => { byBranch[g.branch] = { palace: g.palace, star: g.star, order: i }; });
	const hits = [];
	located.forEach((s) => {
		s.branches.forEach((br) => {
			const g = byBranch[br];
			if (!g) return;
			const short = SS_PALACE_KEY[`${g.palace}`.charAt(0)] || `${g.palace}`.charAt(0);
			const text = (SHENSHA.rows[s.name] && SHENSHA.rows[s.name][short]) || '';
			hits.push({ name: s.name, group: s.group, branch: br, palace: g.palace, palaceOrder: g.order, star: g.star, text });
		});
	});
	hits.sort((a, b) => a.palaceOrder - b.palaceOrder);
	return hits;
}

// 人事十二宫（命起顺布）→ 十二宫寓意表键（传统宫名；按位序对应，字虽异位同）。
const PALACE_MEANING_KEYS = ['命宫', '财帛', '兄弟', '田宅', '男女', '奴仆', '夫妻', '疾厄', '迁移', '官禄', '福德', '相貌'];

// 逐日值星：农历日(1-30) → 6 轮值星之一（初一/初七/十三…同轮）。
function dayStarRound(dayNum) {
	const d = parseInt(dayNum, 10);
	if (!d || d < 1) return null;
	const arr = (LORE.poems && LORE.poems.dayStar) || [];
	return arr[(d - 1) % 6] || null;
}

// 时辰细分 初/中/末：由钟表时分定位在本时辰(2h)内的三分段（0-40/40-80/80-120 分）。
function hourSubKey(clockTime, hourBranch) {
	const zi = BRANCHES.indexOf(`${hourBranch || ''}`);
	const m = /(\d{1,2}):(\d{2})/.exec(`${clockTime || ''}`);
	if (zi < 0 || !m) return '初';
	const hh = parseInt(m[1], 10); const mm = parseInt(m[2], 10);
	const startHour = (23 + 2 * zi) % 24;            // 子=23,丑=1,寅=3…亥=21
	const mins = (((hh - startHour + 24) % 24) * 60 + mm);
	return mins < 40 ? '初' : (mins < 80 ? '中' : '末');
}

// 时组诗：生时支属哪一组（子午卯酉／辰戌丑未／寅申巳亥）。
function hourGroupOf(hourBranch) {
	const groups = (LORE.poems && LORE.poems.hourGroup) || {};
	const keys = Object.keys(groups);
	for (let i = 0; i < keys.length; i++) {
		const g = groups[keys[i]];
		if (g && Array.isArray(g.branches) && g.branches.indexOf(hourBranch) >= 0) return { key: keys[i], ...g };
	}
	return null;
}

// 组装完整展示模型：引擎盘 + 逐柱断语 + 象义/星性/职业/流年总论 + 交互格 + 重犯 + 神煞
export function buildYizhangjingModel(bazi, opts) {
	const input = resolveLunarInput(bazi, opts);
	if (!input) return null;
	const chart = calcYizhangjing({ ...input, opts: opts || {} });
	if (!chart) return null;

	const timeStar = chart.timeStar;
	const dayStar = chart.pillars[2].star;
	const monthStar = chart.pillars[1].star;

	// 逐柱断语（年=祖上/月=父母事业/日=夫妻/时=子女自身）
	const pillarKeys = ['nian', 'yue', 'ri', 'shi'];
	const pillars = chart.pillars.map((p, i) => ({
		...p,
		text: starData(p.star)[pillarKeys[i]] || '',
		xiangyi: starData(p.star).xiangyi || '',
		xingxing: starData(p.star).xingxing || '',
	}));

	// 重犯：详解(fan2/3/4) + 所选口诀组(α/β)
	const kouKey = opts && opts.chongfanKou === 'beta' ? 'beta' : 'alpha';
	const repeats = chart.repeats.map((r) => {
		const d = starData(r.star);
		const fanKey = r.count >= 4 ? 'fan4' : (r.count >= 3 ? 'fan3' : 'fan2');
		return {
			star: r.star, count: r.count,
			detail: d[fanKey] || '',
			alpha: (DATA.chongfan && DATA.chongfan.alpha && DATA.chongfan.alpha[r.star]) || '',
			beta: (DATA.chongfan && DATA.chongfan.beta && DATA.chongfan.beta[r.star]) || '',
			chosen: kouKey,
		};
	});

	// 交互格：日×时（列=日柱星，行=时柱星）；运×时（列=运星，行=时柱星）
	const rishi = (DATA.grid_rishi && DATA.grid_rishi.rows[timeStar] && DATA.grid_rishi.rows[timeStar][dayStar]) || '';
	const zhiye = starData(monthStar).zhiye || '';
	const liunianZong = starData(timeStar).liunian || '';

	// 显示层选项（映射层：盘算用 A 系内部键，仅显示换名）
	const o = opts || {};
	const gradeSet = o.gradeSet === 'variant' ? 'variant' : undefined;
	const naming = (o.starNaming === 'B' || o.starNaming === 'C') ? o.starNaming : 'A';
	const daoTerm = o.daoTerm === 'edao' ? 'edao' : 'gui';
	const annualMethod = (o.annualMethod === 'liunian' || o.annualMethod === 'xiaoxian') ? o.annualMethod : '';
	const xiaoDir = o.xiaoxianDir === 'always' ? 'always' : 'chart';

	const fourStars = chart.pillars.map((p) => p.star);
	const fourIdx = chart.fourIdx;
	const yearIdxNum = BRANCHES.indexOf(input.yearBranch);
	const hourIdxNum = BRANCHES.indexOf(input.hourBranch);

	// 大限：运×时断语（运星 × 时柱星，B14 正确口径）；grade 随品级分类
	const dayun = chart.dayun.map((d) => ({
		...d,
		grade: gradeOf(d.star, gradeSet),
		yunshi: (DATA.grid_yunshi && DATA.grid_yunshi.rows[timeStar] && DATA.grid_yunshi.rows[timeStar][d.star]) || '',
		wuxing: wuxingState(chart.monthBranch, d.branch),
	}));

	// B15 流年运×时改用「月柱星」口径（大限用时柱星、流年用月柱星）：按 12 流年支预表
	const liunianYunshi = {};
	BRANCHES.forEach((b) => {
		const flowStar = STARS[BRANCHES.indexOf(b)];
		liunianYunshi[b] = (DATA.grid_yunshi && DATA.grid_yunshi.rows[monthStar] && DATA.grid_yunshi.rows[monthStar][flowStar]) || '';
	});

	// 人事十二宫 + 十二宫寓意 + 神煞叠加（合参层，模型恒备数据供 UI 切换）
	const renshi = chart.renshi.map((g, k) => ({
		...g, grade: gradeOf(g.star, gradeSet),
		meaning: (DATA.palaceMeaning && DATA.palaceMeaning[PALACE_MEANING_KEYS[k]]) || '',
		label: starLabel(g.star, naming),
	}));
	const shenshaHits = computeShenshaHits(input, bazi, renshi);

	// ── WP-C 新增派生字段（全部可选消费，老 UI 不读不炸）──
	const sishi = pillarWeights(fourStars, gradeSet);
	const ninePinExact = nineGradeExact(fourStars, gradeSet);
	// 童限开关（tongxianShow，默认开）：关时不出童限（某些流派不用童限）——门控在此，UI/快照按 tongxian.length 显现。
	const tongxian = (o.tongxianShow === false) ? [] : tongxianList(chart.mingIdx, chart.startAge);
	const xunRoles = xunShenRoles(fourIdx, yearIdxNum, chart.opts.flowSet);
	const flowSubRep = flowSub(yearIdxNum, input.month, input.day, hourIdxNum);
	const pillarWx = pillarWuxing(fourIdx, fourIdx.month, gradeSet);
	const brothers = brotherCount(chart.monthBranch);
	const polarity = starPolarity(fourStars);
	const clashes = branchClash(fourIdx, chart.mingIdx);
	const pairHitList = pairHits(fourStars);
	const nianyun = starData(chart.pillars[0].star).nianyun || '';
	// 位置速断：逐柱按柱位取该柱主星的年/月/日/时速断
	const posKeys = ['nian', 'yue', 'ri', 'shi'];
	const posQuick = chart.pillars.map((p, i) => ({
		label: p.label, star: p.star,
		text: ((DATA.posQuick && DATA.posQuick[p.star]) || {})[posKeys[i]] || '',
	}));
	// 各柱逢星速断：命中该柱主星在表中的行
	const pillarLabels = ['年', '月', '日', '时'];
	const pillarQuickHits = (DATA.pillarQuick || []).filter((row) => {
		const pi = pillarLabels.indexOf(row.pillar);
		return pi >= 0 && Array.isArray(row.stars) && row.stars.indexOf(fourStars[pi]) >= 0;
	});
	// 六道分布：四柱各道计数 + 共通特质/前世身份
	const daoDist = {};
	chart.pillars.forEach((p) => { daoDist[p.dao] = (daoDist[p.dao] || 0) + 1; });
	const daoRows = Object.keys(daoDist).map((dao) => ({
		dao, term: daoLabel(dao, daoTerm), count: daoDist[dao],
		traits: ((DATA.daoTraits && DATA.daoTraits[dao]) || {}).traits || '',
		prevLife: ((DATA.daoTraits && DATA.daoTraits[dao]) || {}).prevLife || [],
	}));
	// 逐日值星 / 时辰细断 / 时组诗 / 星名映射
	const clockTime = (bazi && bazi.nongli && bazi.nongli.clockTime) || '';
	const cm = /(\d{1,2}):(\d{2})/.exec(clockTime);
	const ziSub = cm ? ziSubPeriod(parseInt(cm[1], 10), parseInt(cm[2], 10)) : null;
	const hourSub = hourSubKey(clockTime, input.hourBranch);
	const hourDetailNode = ((LORE.poems && LORE.poems.hourDetail && LORE.poems.hourDetail[input.hourBranch]) || {})[hourSub] || null;
	const dayStarPick = dayStarRound(input.day);
	const hourGroupPick = hourGroupOf(input.hourBranch);
	const aliasMap = {};
	STARS.forEach((s) => { aliasMap[s] = starLabel(s, naming); });

	return {
		input, chart, pillars, repeats, rishi, zhiye, liunianZong, dayun, renshi, shenshaHits,
		timeStar, dayStar, monthStar,
		shenshaLayer: !!(opts && opts.shenshaLayer),
		// 显示层选项回显
		naming, daoTerm, gradeSet: gradeSet || 'standard', annualMethod, xiaoDir, chongfanKou: kouKey,
		// 新派生
		sishi, ninePinExact, tongxian, xunRoles, flowSub: flowSubRep, pillarWuxing: pillarWx,
		brothers, polarity, clashes, pairHits: pairHitList, nianyun, posQuick, pillarQuickHits,
		daoRows, liunianYunshi, aliasMap,
		ziSub, hourSub, hourDetail: hourDetailNode, dayStarPick, hourGroupPick,
	};
}

// 神煞落宫（合参层）：给定神煞名 + 人事十二宫，返回各宫断语（用现有 21×12 表）
export function shenshaForPalace(shenshaName, palaceName) {
	const row = SHENSHA.rows && SHENSHA.rows[shenshaName];
	return row ? (row[palaceName] || '') : '';
}

export function listShensha() {
	return Object.keys((SHENSHA && SHENSHA.rows) || {});
}

// AI 快照文本：计算盘 + 核心断语 + 文献层【诗文】【四柱文献】（后两段登记为默认关段：builder 恒产，导出层按设置控）
export function buildYizhangjingSnapshotText(model) {
	if (!model) return '';
	const c = model.chart;
	const L = [];
	// 🔴 段头必须独占一行（^【…】$），否则导出「AI导出设置」按段过滤失效并把相邻段一并误删
	// （parseSectionTitleLine 只认整行等于【段名】的行）。描述/括注一律落到下一行。
	const rawMonth = model.input.lunarMonth || c.input.month;
	const paiNote = c.input.month !== rawMonth ? `·排作${c.input.month}月` : '';
	L.push('【起盘信息】');
	L.push(`性别：${c.input.gender}　生年支：${c.input.yearBranch}(${ZODIAC[BRANCHES.indexOf(c.input.yearBranch)]})　农历${model.input.leap ? '闰' : ''}${rawMonth}月${c.input.day}日　生时支：${c.input.hourBranch}（${model.input.monthNote}${paiNote}）`);
	L.push(`本命阴阳：${c.yinyang}年 → ${c.dirText}　命宫定法：${c.opts.mgMethod === 'shuZhiMao' ? '数至卯' : '时上起命'}　大限一宫${c.opts.N}年　大限起运：${c.opts.startMode === 'age1' ? '1岁连续' : '秘传起运'}`);
	// 流派配置行：让 AI 快照反映用户全部所选（逐年法/显示层/断语组），非默认项显式标出。
	const cfg = [];
	cfg.push(`逐年法：${model.annualMethod === 'liunian' ? `流年十二神(${c.opts.flowSet}组)` : `小限·起${c.xiaoStartLabel || '日柱宫'}·${model.xiaoDir === 'always' ? '一律顺行' : '随盘向'}`}`);
	cfg.push(`重犯口诀：${model.chongfanKou === 'beta' ? '异传组' : '常见组'}`);
	if (model.gradeSet === 'variant') cfg.push('品级分类：变体(天驿归凶)');
	if (model.naming && model.naming !== 'A') cfg.push(`星名系统：${model.naming}系(显示层)`);
	if (model.daoTerm === 'edao') cfg.push('六道术语：饿鬼道系(显示层)');
	if (c.opts.earlyZi) cfg.push('早子调宫：开');
	L.push(cfg.join('　'));
	L.push('');
	L.push('【四柱四宫断语】');
	L.push('（年=祖上／月=父母事业／日=夫妻／时=子女自身·主星）');
	model.pillars.forEach((p) => {
		L.push(`${p.label}宫 ${p.branch}(${p.zodiac})·${p.star}·${p.dao}·${p.grade}：${p.text}`);
	});
	L.push('');
	L.push('【命宫与人事十二宫】');
	L.push(`命宫 ${c.mingBranch}宫·${c.mingStar}`);
	L.push('| 宫位 | 星曜 |');
	L.push('| --- | --- |');
	model.renshi.forEach((g) => { L.push(`| ${g.palace} | ${g.branch}${g.star} |`); });
	if (model.sishi && model.sishi.rows) {
		L.push('');
		L.push('【四世与权重】');
		L.push('（四柱＝四世：根苗花果，加权分＝Σ权重×品级分[上+1/中0/下−1]）');
		L.push(`加权总分：${model.sishi.score}`);
		L.push('| 柱 | 世 | 年龄段 | 权重 | 星 | 品级 |');
		L.push('| --- | --- | --- | --- | --- | --- |');
		model.sishi.rows.forEach((r) => { L.push(`| ${r.pillar} | ${r.shi} | ${r.age} | ${r.weight}% | ${r.star} | ${r.grade} |`); });
	}
	if (model.renshi && model.renshi.some((g) => g.meaning)) {
		L.push('');
		L.push('【人事十二宫寓意】');
		model.renshi.forEach((g) => { if (g.meaning) L.push(`${g.palace}（${g.branch}${g.star}）：${g.meaning}`); });
	}
	L.push('');
	L.push('【格局判定】');
	L.push(`四宫等第：${c.fourPalaceRank}　命格：${c.mingGe}　九品估：${c.nineGrade}　（上品×${c.gradeCount.up} 中品×${c.gradeCount.mid} 下品×${c.gradeCount.down}）`);
	if (model.ninePinExact) {
		L.push('');
		L.push('【九品定格】');
		if (model.ninePinExact.matched) {
			L.push(`星组合精确命中：${model.ninePinExact.grade}${model.ninePinExact.level ? '·' + model.ninePinExact.level : ''}`);
			if (model.ninePinExact.text) L.push(model.ninePinExact.text);
		} else {
			L.push(`（按品级数估）${model.ninePinExact.grade}`);
		}
	}
	if (model.nianyun) {
		L.push('');
		L.push('【年上运程】');
		L.push(`（以生年星${model.chart.pillars[0].star}为纲）`);
		L.push(model.nianyun);
	}
	if (model.posQuick && model.posQuick.some((p) => p.text)) {
		L.push('');
		L.push('【位置速断】');
		model.posQuick.forEach((p) => { if (p.text) L.push(`${p.label}柱${p.star}：${p.text}`); });
	}
	if (model.repeats.length) {
		L.push('');
		L.push('【重犯】');
		// 「重犯口诀」所选组以 ★当前 标出（否则快照两组恒列、AI 读不到用户所宗）。
		model.repeats.forEach((r) => {
			const aMark = r.chosen !== 'beta' ? '★当前' : '';
			const bMark = r.chosen === 'beta' ? '★当前' : '';
			L.push(`${r.star}×${r.count}：${r.detail}`);
			L.push(`　速断(常见组${aMark})：${r.alpha}　速断(异传组${bMark})：${r.beta}`);
		});
	}
	if (model.rishi) {
		L.push('');
		L.push('【交互格】');
		L.push(`日${model.dayStar}×时${model.timeStar}：${model.rishi}`);
	}
	if (model.zhiye) {
		L.push('');
		L.push('【职业适性】');
		L.push(`（月柱${model.monthStar}）：${model.zhiye}`);
	}
	L.push('');
	L.push('【大限】');
	L.push(`从月宫起·一宫${c.opts.N}年·${c.dirText}`);
	L.push('| 年龄 | 地支 | 星 | 道 | 品级 | 五行 | 运势 |');
	L.push('| --- | --- | --- | --- | --- | --- | --- |');
	model.dayun.forEach((d) => {
		L.push(`| ${d.from}-${d.to}岁 | ${d.branch} | ${d.star} | ${d.dao} | ${d.grade} | ${d.wuxing || '—'} | ${d.yunshi || '—'} |`);
	});
	if (model.tongxian && model.tongxian.length) {
		L.push('');
		L.push('【童限】');
		L.push('（未交大运前·一律逆行·一宫一年）');
		L.push(model.tongxian.map((t) => `${t.age}岁=${t.palace}(${t.branch}${t.star})`).join('　'));
	}
	L.push('');
	// 逐年法互斥（B10 明训：小限/流年只用一套）：annualMethod 未设时二者并列（零回归）
	const showXiao = model.annualMethod !== 'liunian';
	const showLiunian = model.annualMethod !== 'xiaoxian';
	const xiaoLabel = c.xiaoStartLabel || '日柱宫';
	const xiaoStars = [];
	for (let a = 1; a <= 12; a++) { xiaoStars.push(`${a}=${xiaoxianStarAtDir(c.xiaoStartIdx, c.dir, a, model.xiaoDir)}`); }
	L.push('【小限与流年十二神】');
	if (showXiao) {
		L.push(`小限一宫一年·起${xiaoLabel}·${model.xiaoDir === 'always' ? '一律顺行' : '随盘向'}：${xiaoStars.join(' ')}`);
	}
	if (showLiunian) {
		L.push(`流年十二神（${c.opts.flowSet}组）以本命年支「${c.input.yearBranch}」起太岁顺布，四柱/命宫落宫值神：` +
			[['年', c.fourIdx.year], ['月', c.fourIdx.month], ['日', c.fourIdx.day], ['时', c.fourIdx.time], ['命', c.mingIdx]]
				.map(([lab, idx]) => `${lab}=${xunShenAt(BRANCHES.indexOf(c.input.yearBranch), idx, c.opts.flowSet)}`).join(' '));
		if (model.xunRoles && model.xunRoles.length) {
			L.push(`巡宫四位：${model.xunRoles.map((r) => `${r.pillar}${r.role}=${r.shen}`).join('　')}`);
		}
	}
	if (model.flowSub) {
		L.push('');
		L.push('【流月流日流时】');
		L.push('（流年宫起正月→初一→子时·一律顺行）');
		L.push(`流月：${model.flowSub.month.branch}${model.flowSub.month.star}　流日：${model.flowSub.day.branch}${model.flowSub.day.star}　流时：${model.flowSub.time.branch}${model.flowSub.time.star}`);
	}
	if (model.liunianZong && showLiunian) {
		L.push('');
		L.push('【流年总论】');
		L.push(`（主星${model.timeStar}）：${model.liunianZong}`);
	}
	// 【叠断】默认关段（builder 恒产，导出层按设置控）：刑冲害/星组合互见/阴阳克父母/兄弟数/四柱旺衰
	const dieLines = [];
	if (model.clashes && model.clashes.hits && model.clashes.hits.length) {
		dieLines.push('◆ 刑冲害：' + model.clashes.hits.map((h) => h.type === '刑' ? `${h.group}刑` : `${h.a}${h.b}${h.type}`).join('、'));
	}
	if (model.pairHits && model.pairHits.length) {
		model.pairHits.forEach((r) => dieLines.push(`◆ 互见 ${r.text}`));
	}
	if (model.polarity && model.polarity.judge) {
		dieLines.push(`◆ 阴阳（星曜六阳${model.polarity.yang}·六阴${model.polarity.yin}）：${model.polarity.judge}`);
	}
	if (model.brothers) {
		dieLines.push(`◆ 兄弟数：${model.brothers.text}（${model.brothers.note}）`);
	}
	if (model.pillarWuxing && model.pillarWuxing.length) {
		dieLines.push('◆ 四柱旺衰：' + model.pillarWuxing.map((w) => `${w.pillar}${w.branch}(${w.wuxing})${w.state}`).join('　'));
	}
	if (dieLines.length) {
		L.push('');
		L.push('【叠断】');
		dieLines.forEach((x) => L.push(x));
	}
	// 神煞合参层（默认关；开启且有落宫时才入快照）：按人事宫列本盘落入之神煞与断语
	if (model.shenshaLayer && model.shenshaHits && model.shenshaHits.length) {
		L.push('');
		L.push('【神煞合参】');
		L.push('（通用命理合参层·非本术原生：生年支／日干／月支／日柱旬定位，仅列本盘落宫）');
		const grouped = {};
		const order = [];
		model.shenshaHits.forEach((h) => {
			if (!grouped[h.palace]) { grouped[h.palace] = { branch: h.branch, star: h.star, items: [] }; order.push(h.palace); }
			grouped[h.palace].items.push(h);
		});
		L.push('| 宫位 | 坐 | 神煞 | 断语 |');
		L.push('| --- | --- | --- | --- |');
		order.forEach((pal) => {
			const g = grouped[pal];
			g.items.forEach((it, ii) => {
				const palCell = ii === 0 ? pal : '—';
				const seatCell = ii === 0 ? `${g.branch}·${g.star}` : '—';
				L.push(`| ${palCell} | ${seatCell} | ${it.name} | ${it.text || '（无断语）'} |`);
			});
		});
	}
	// 【诗文】doctrine 段（默认关段：builder 恒产，导出层按设置控）：与右栏「诗文」tab renderLore 同口径，
	// 只取本盘命中的月诗（真实农历生月）与时文（生时支），非全库；原文引自 yizhangjingLore.json 零改写。
	const loreMonthKey = LORE_MONTH_LABELS[model.input.lunarMonth || c.input.month] || '';
	const loreMonthPoem = (LORE.poems && LORE.poems.month && LORE.poems.month[loreMonthKey]) || null;
	const loreHourMain = (LORE.poems && LORE.poems.hourMain && LORE.poems.hourMain[c.input.hourBranch]) || null;
	if (loreMonthPoem || (loreHourMain && loreHourMain.text)) {
		L.push('');
		L.push('【诗文】');
		L.push('（古本诗文含旧时代观念，仅作文献保留）');
		if (loreMonthPoem) {
			L.push(`◆ 本月生人诗（${loreMonthKey}）`);
			if (loreMonthPoem.poem) L.push(loreMonthPoem.poem);
			if (loreMonthPoem.prose) L.push(loreMonthPoem.prose);
		}
		if (loreHourMain && loreHourMain.text) {
			L.push(`◆ 本时生人（${c.input.hourBranch}时${loreHourMain.range ? '·' + loreHourMain.range : ''}）`);
			L.push(loreHourMain.text);
		}
		if (model.hourGroupPick && model.hourGroupPick.poem) {
			L.push(`◆ 时组诗（${model.hourGroupPick.key}）`);
			L.push(model.hourGroupPick.poem);
		}
	}
	// 【逐日值星】doctrine 段（默认关段）：按农历生日命中 6 轮值星之一（非全库罗列）。
	if (model.dayStarPick && model.dayStarPick.text) {
		L.push('');
		L.push('【逐日值星】');
		L.push('（古本逐日值星含旧时代观念，仅作文献保留）');
		L.push(`◆ ${model.dayStarPick.star}值日（${model.dayStarPick.days}）`);
		L.push(model.dayStarPick.text);
	}
	// 【时辰细断】doctrine 段（默认关段）：按子初/中/末（或时初中末）命中 1/3（非全库罗列）。
	if (model.hourDetail && (model.hourDetail.prose || (model.hourDetail.poems && model.hourDetail.poems.length))) {
		L.push('');
		L.push('【时辰细断】');
		L.push('（古本时辰细断含旧时代观念，仅作文献保留）');
		L.push(`◆ ${c.input.hourBranch}时${model.hourSub}${model.hourDetail.range ? '（' + model.hourDetail.range + '）' : ''}`);
		if (model.hourDetail.prose) L.push(model.hourDetail.prose);
		(model.hourDetail.poems || []).forEach((pm) => L.push(pm));
	}
	// 【四柱文献】doctrine 段（默认关段）：与右栏「四柱文献」tab renderSiZhuLore 同口径，
	// 只取本盘四柱各主星的逐星全文（非全库十二星）；原文零改写；全缺不产段。
	const loreSizhuLabels = ['年柱 · 祖上', '月柱 · 父母事业', '日柱 · 夫妻', '时柱 · 自身主星'];
	const loreStarBlocks = (model.pillars || [])
		.map((p, i) => ({ label: loreSizhuLabels[i] || '', star: p.star, full: (LORE.starFull && LORE.starFull[p.star]) || '' }))
		.filter((b) => b.full);
	if (loreStarBlocks.length) {
		L.push('');
		L.push('【四柱文献】');
		L.push('（各柱主星逐星全文·古本文献层）');
		loreStarBlocks.forEach((b) => {
			L.push(`◆ ${b.label} · ${b.star}`);
			L.push(b.full);
		});
	}
	return L.join('\n');
}

export default { buildYizhangjingModel, buildYizhangjingSnapshotText, resolveLunarInput, locateShensha, computeShenshaHits, shenshaForPalace, listShensha };
