// 一掌经 · 模型装配 + AI 快照文本（引擎 + 断语数据 → 展示模型 / 快照串）。
// UI 与 AI 挂载共用本模块；引擎(yizhangjingLocal)保持纯函数，本模块负责农历解析与断语拼接。
import { calcYizhangjing, BRANCHES, ZODIAC, gradeOf, wuxingState, xiaoxianStarAt, xunShenAt } from './yizhangjingLocal.js';
import DATA from './data/yizhangjingData.json' with { type: 'json' };
import SHENSHA from './data/yizhangjingShensha.json' with { type: 'json' };

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
		// 闰月归属：默认十五折半（十五含前作本月、后作下月）
		const day = parseInt(nl.dayNum, 10) || 0;
		if (day > 15) {
			month = month + 1;
			if (month > 12) month -= 12;
			monthNote = '闰月·十五后作下月';
		} else {
			monthNote = '闰月·十五前作本月';
		}
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

	// 大限：运×时断语（运星 × 时柱星）
	const dayun = chart.dayun.map((d) => ({
		...d,
		yunshi: (DATA.grid_yunshi && DATA.grid_yunshi.rows[timeStar] && DATA.grid_yunshi.rows[timeStar][d.star]) || '',
		wuxing: wuxingState(chart.monthBranch, d.branch),
	}));

	// 人事十二宫 + 神煞叠加（合参层，opts.shenshaLayer 开时才带，但模型恒备数据供 UI 切换）
	const renshi = chart.renshi.map((g) => ({ ...g, grade: gradeOf(g.star) }));
	// 神煞合参层：由生年支／日干／月支／日柱旬定位各神煞落地支 → 坐该支之人事宫（仅列本盘落宫）
	const shenshaHits = computeShenshaHits(input, bazi, renshi);

	return {
		input, chart, pillars, repeats, rishi, zhiye, liunianZong, dayun, renshi, shenshaHits,
		timeStar, dayStar, monthStar,
		shenshaLayer: !!(opts && opts.shenshaLayer),
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

// AI 快照文本：计算盘 + 核心断语（文献层古本诗/逐星全文属显示层，不入快照）
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
	L.push(`本命阴阳：${c.yinyang}年 → ${c.dirText}　命宫定法：${c.opts.mgMethod === 'shuZhiMao' ? '数至卯' : '时上起命'}　大限一宫${c.opts.N}年　流年十二神：${c.opts.flowSet}组`);
	L.push('');
	L.push('【四柱四宫断语】');
	L.push('（年=祖上／月=父母事业／日=夫妻／时=子女自身·主星）');
	model.pillars.forEach((p) => {
		L.push(`${p.label}宫 ${p.branch}(${p.zodiac})·${p.star}·${p.dao}·${p.grade}：${p.text}`);
	});
	L.push('');
	L.push('【命宫与人事十二宫】');
	L.push(`命宫 ${c.mingBranch}宫·${c.mingStar}`);
	L.push(model.renshi.map((g) => `${g.palace}=${g.branch}${g.star}`).join('　'));
	L.push('');
	L.push('【格局判定】');
	L.push(`四宫等第：${c.fourPalaceRank}　命格：${c.mingGe}　九品估：${c.nineGrade}　（上品×${c.gradeCount.up} 中品×${c.gradeCount.mid} 下品×${c.gradeCount.down}）`);
	if (model.repeats.length) {
		L.push('');
		L.push('【重犯】');
		model.repeats.forEach((r) => {
			L.push(`${r.star}×${r.count}：${r.detail}`);
			L.push(`　速断(常见)：${r.alpha}　速断(异传)：${r.beta}`);
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
	model.dayun.forEach((d) => {
		L.push(`${d.from}-${d.to}岁 ${d.branch}·${d.star}(${d.dao}·${d.grade}${d.wuxing ? '·' + d.wuxing : ''})：${d.yunshi}`);
	});
	L.push('');
	const xiaoLabel = c.xiaoStartLabel || '日柱宫';
	const xiaoStars = [];
	for (let a = 1; a <= 12; a++) { xiaoStars.push(`${a}=${xiaoxianStarAt(c.xiaoStartIdx, c.dir, a)}`); }
	L.push('【小限与流年十二神】');
	L.push(`小限一宫一年·起${xiaoLabel}：${xiaoStars.join(' ')}`);
	L.push(`流年十二神（${c.opts.flowSet}组）以本命年支「${c.input.yearBranch}」起太岁顺布，四柱/命宫落宫值神：` +
		[['年', c.fourIdx.year], ['月', c.fourIdx.month], ['日', c.fourIdx.day], ['时', c.fourIdx.time], ['命', c.mingIdx]]
			.map(([lab, idx]) => `${lab}=${xunShenAt(BRANCHES.indexOf(c.input.yearBranch), idx, c.opts.flowSet)}`).join(' '));
	if (model.liunianZong) {
		L.push('');
		L.push('【流年总论】');
		L.push(`（主星${model.timeStar}）：${model.liunianZong}`);
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
		order.forEach((pal) => {
			const g = grouped[pal];
			L.push(`${pal}(${g.branch}·${g.star})：` + g.items.map((it) => `${it.name}—${it.text || '（无断语）'}`).join('；'));
		});
	}
	return L.join('\n');
}

export default { buildYizhangjingModel, buildYizhangjingSnapshotText, resolveLunarInput, locateShensha, computeShenshaHits, shenshaForPalace, listShensha };
