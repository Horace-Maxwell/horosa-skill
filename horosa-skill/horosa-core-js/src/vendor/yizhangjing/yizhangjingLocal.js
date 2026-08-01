// 一掌经 · 纯前端排盘引擎（零后端）。
// 十二地支各坐一星，由农历生年支/月/日/时支＋性别经掌上顺逆排四柱四宫、命宫、
// 人事十二宫，叠大限/小限/流年十二神与格局判识。全部为分支算术，可复现、可golden。
// 说明：星名用繁体（与断语数据键一致）；月/闰月/节气月归属在调用方解析后以整数 month 传入，
// 本引擎保持纯函数便于逐例核验。
// 断语表（九品/互见/刑害等表驱动判识）从数据层读取，盘算主流程（calcYizhangjing）不依赖，
// 故 golden 四例字节不变；新增判识函数为独立导出，供装配层可选消费。
import DATA from './data/yizhangjingData.json' with { type: 'json' };

export const BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const ZODIAC = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'];
// 十二星与地支同序（子=天貴…亥=天壽）
export const STARS = ['天貴', '天厄', '天權', '天破', '天奸', '天文', '天福', '天驛', '天孤', '天刃', '天藝', '天壽'];
// 六道：每两支归一道
export const DAO = {
	子: '佛道', 午: '佛道',
	丑: '鬼道', 未: '鬼道',
	寅: '人道', 申: '人道',
	卯: '畜生道', 酉: '畜生道',
	辰: '修羅道', 戌: '修羅道',
	巳: '仙道', 亥: '仙道',
};
// 品级：上品(吉)/中品(平)/下品(凶)
export const GRADE_UP = ['天貴', '天權', '天福', '天壽'];
export const GRADE_MID = ['天文', '天驛', '天刃', '天藝'];
export const GRADE_DOWN = ['天破', '天奸', '天孤', '天厄'];

// 掌上手位（左手指节，男女皆用左手，别在顺逆）
export const HAND_POS = [
	'无名指·根下', '中指·根下', '食指·根下', '食指·下节', '食指·中节', '食指·上节',
	'中指·上节', '无名指·上节', '小指·上节', '小指·中节', '小指·下节', '小指·根下',
];

// 人事十二宫（自命宫一律顺布）
export const PALACES = ['命', '财帛', '兄弟', '田宅(父母)', '子女', '奴仆', '夫妻', '疾厄', '迁移', '官禄', '福德', '相貌'];

// 流年巡宫十二神三套（起流年支＝太岁，顺布）
export const FLOW_SETS = {
	A: ['太岁', '太阳', '青龙', '太阴', '官符', '小耗', '丧门', '朱雀', '白虎', '贵人', '吊客', '病符'],
	B: ['太岁', '青龙', '丧门', '六合', '官符', '小耗', '大耗', '朱雀', '白虎', '贵神', '吊客', '病符'],
	C: ['太岁', '太阳', '丧门', '太阴', '五鬼', '小耗', '岁破', '龙德', '白虎', '福德', '天狗', '病符'],
};

export function mod12(n) {
	return ((n % 12) + 12) % 12;
}

export function branchIndex(branch) {
	return BRANCHES.indexOf(`${branch || ''}`.trim());
}

export function starOf(idx) {
	return STARS[mod12(idx)];
}

export function daoOf(idx) {
	return DAO[BRANCHES[mod12(idx)]];
}

export function gradeOf(star, gradeSet) {
	// gradeSet='variant'（品级分类变体）：天驛（天驿）由中品改归下品（最凶）。
	// 默认（无 gradeSet）字节不变，golden 与既有调用不受影响。
	if (gradeSet === 'variant' && star === '天驛') return '下品';
	if (GRADE_UP.indexOf(star) >= 0) return '上品';
	if (GRADE_DOWN.indexOf(star) >= 0) return '下品';
	return '中品';
}

// 年支阴阳：子寅辰午申戌=阳(偶)，丑卯巳未酉亥=阴(奇)
export function yinyang(yearIdx) {
	return mod12(yearIdx) % 2 === 0 ? '阳' : '阴';
}

// 顺逆方向：+1 顺 / -1 逆
// rule: 'yangNanYinNv'（阳男阴女顺·阴男阳女逆） / 'menShunNvNi'（男顺女逆）
export function direction(yearIdx, gender, rule) {
	const isMale = gender === '男' || gender === 1 || gender === 'Male' || gender === 'male';
	if (rule === 'menShunNvNi') {
		return isMale ? 1 : -1;
	}
	const yy = yinyang(yearIdx);
	return ((yy === '阳' && isMale) || (yy === '阴' && !isMale)) ? 1 : -1;
}

// 四柱四宫：年宫=生年支位；月宫=正月起年宫、数(生月-1)步；日宫=初一起月宫、数(生日-1)步；
// 时宫=子时起日宫、数(时序-1)步。earlyZi 时（生时=子且开关开）时宫±1（近似调宫）。
export function fourPalaces(yearIdx, month, day, hourIdx, gender, rule, earlyZi) {
	const d = direction(yearIdx, gender, rule);
	const yi = mod12(yearIdx);
	const mi = mod12(yi + d * (month - 1));
	const di = mod12(mi + d * (day - 1));
	const hourOrder = mod12(hourIdx) + 1; // 子=1…亥=12
	let ti = mod12(di + d * (hourOrder - 1));
	if (earlyZi && mod12(hourIdx) === 0) {
		const isMale = gender === '男' || gender === 1 || gender === 'Male' || gender === 'male';
		ti = mod12(ti + (isMale ? -1 : 1));
	}
	return { d, yi, mi, di, ti };
}

// 命宫：'shiShang'→时宫即命；'shuZhiMao'→时宫起生时、数至卯止（卯=3）。
export function mingGong(ti, hourIdx, d, method) {
	if (method === 'shuZhiMao') {
		const dist = mod12(3 - mod12(hourIdx));
		return mod12(ti + d * dist);
	}
	return mod12(ti); // 时上起命（时宫即命）
}

// 人事十二宫：自命宫顺布
export function renshiPalaces(mingIdx) {
	const out = [];
	for (let k = 0; k < 12; k++) {
		out.push({ palace: PALACES[k], idx: mod12(mingIdx + k), branch: BRANCHES[mod12(mingIdx + k)], star: starOf(mingIdx + k) });
	}
	return out;
}

// 大限起运虚岁：'mi'（秘传：按命宫星）/'age1'（1岁连续）
export function dayunStartAge(mingStar, gender, mode) {
	if (mode !== 'mi') return 1;
	const isMale = gender === '男' || gender === 1 || gender === 'Male' || gender === 'male';
	if (mingStar === '天厄') return isMale ? 4 : 2;
	if (mingStar === '天刃') return isMale ? 10 : 9;
	if (mingStar === '天破' || mingStar === '天孤') return isMale ? 12 : 6;
	return 1;
}

// 大限：起月宫、一宫 N 年、方向 d
export function dayunList(monthPalaceIdx, d, N, startAge, count) {
	const rows = [];
	const n = count || 10;
	for (let k = 0; k < n; k++) {
		const idx = mod12(monthPalaceIdx + d * k);
		const a1 = startAge + k * N;
		rows.push({ from: a1, to: a1 + N - 1, idx, branch: BRANCHES[idx], star: starOf(idx), dao: daoOf(idx), grade: gradeOf(starOf(idx)) });
	}
	return rows;
}

// 小限：一宫一年。start='ri'（日柱宫）/'yue'（月柱宫）
export function xiaoxianStarAt(startPalaceIdx, d, age) {
	return starOf(startPalaceIdx + d * (age - 1));
}

// 流年巡宫十二神：以流年地支起太岁顺布，取目标宫（支）当值神
export function xunShenAt(flowBranchIdx, targetIdx, setKey) {
	const set = FLOW_SETS[setKey] || FLOW_SETS.A;
	const step = mod12(mod12(targetIdx) - mod12(flowBranchIdx));
	return set[step];
}

// 重犯统计（四柱同星次数）
export function chongfanStat(fourStars) {
	const cnt = {};
	fourStars.forEach((s) => { cnt[s] = (cnt[s] || 0) + 1; });
	return Object.keys(cnt).filter((s) => cnt[s] >= 2).map((s) => ({ star: s, count: cnt[s] }));
}

// 四宫等第（以时宫为主）。gradeSet 可选：'variant' 时天驛归下品；默认字节不变。
export function fourPalaceRank(stars, timeStar, dayStar, gradeSet) {
	const isUp = (s) => gradeOf(s, gradeSet) === '上品';
	const isDown = (s) => gradeOf(s, gradeSet) === '下品';
	const up = stars.filter(isUp).length;
	const down = stars.filter(isDown).length;
	const timeUp = isUp(timeStar);
	const timeDown = isDown(timeStar);
	const dayUp = isUp(dayStar);
	const dayDown = isDown(dayStar);
	if (up === 4) return '最上等命（四宫全吉）';
	if (down === 4) return '下等命（四宫全凶）';
	if (timeUp && dayUp) return '上等命（时吉日吉·年月不足）';
	if (timeDown && dayDown) return '中等命（时凶日凶·年月吉）';
	return '中平之命（吉凶混见·以时宫为主）';
}

// 命格（定义化，最易上手）。gradeSet 可选，默认字节不变。
export function mingGe(stars, timeStar, dayStar, yearStar, monthStar, repeats, gradeSet) {
	const isUp = (s) => gradeOf(s, gradeSet) === '上品';
	const isDown = (s) => gradeOf(s, gradeSet) === '下品';
	const up = stars.filter(isUp).length;
	const down = stars.filter(isDown).length;
	const timeUp = isUp(timeStar);
	const timeDown = isDown(timeStar);
	const ymUp = isUp(yearStar) && isUp(monthStar);
	const ymDown = isDown(yearStar) && isDown(monthStar);
	const dtUp = isUp(dayStar) && timeUp;
	const dtDown = isDown(dayStar) && timeDown;
	const hasUpRepeat = repeats.some((r) => isUp(r.star));
	if (up === 4 && timeUp && repeats.length === 0) return '富贵之命（四吉·吉星居时·不重犯）';
	if (down === 4) return '贫贱之命（四柱全凶）';
	if (ymDown && dtUp) return '先贫后富（年月凶·日时吉）';
	if (ymUp && dtDown) return '先富后贫（年月吉·日时凶）';
	if ((timeStar === '天破' || timeStar === '天厄') && down >= 3) return '夭折之命（时坐破/厄+多凶·带疾可延）';
	if (down >= 3 || (timeDown && down >= 3)) return '凶恶之命（凶星三犯或时凶+多凶）';
	if (up >= 1 && hasUpRepeat) return '庸常之命（吉星两犯·福不久长）';
	return '庸常之命（吉凶中平混见）';
}

// 九品估（严格九品须按星组合，本处启发式，与验证过原型一致）
export function nineGradeEstimate(up, mid, down) {
	if (up === 4) return '上品上格';
	if (up === 3 && mid === 1) return '上中／中上格（视中品星）';
	if (up === 2 && mid === 2) return '中品中格';
	if (down === 4) return '下品下格';
	if (down >= 2 && up === 0) return '下品（中／下）格';
	return '中平格';
}

// 五行旺相休囚死（以生月月支五行定；地支五行：寅卯木/巳午火/申酉金/亥子水/辰戌丑未土）
const BRANCH_WUXING = { 寅: '木', 卯: '木', 巳: '火', 午: '火', 申: '金', 酉: '金', 亥: '水', 子: '水', 辰: '土', 戌: '土', 丑: '土', 未: '土' };
const SEASON_STATE = {
	木: { 木: '旺', 火: '相', 水: '休', 金: '囚', 土: '死' },
	火: { 火: '旺', 土: '相', 木: '休', 水: '囚', 金: '死' },
	金: { 金: '旺', 水: '相', 土: '休', 火: '囚', 木: '死' },
	水: { 水: '旺', 木: '相', 金: '休', 土: '囚', 火: '死' },
	土: { 土: '旺', 金: '相', 火: '休', 木: '囚', 水: '死' },
};
export function wuxingState(monthBranch, targetBranch) {
	const ling = BRANCH_WUXING[monthBranch];
	const w = BRANCH_WUXING[targetBranch];
	if (!ling || !w) return '';
	return (SEASON_STATE[ling] && SEASON_STATE[ling][w]) || '';
}

// 主排盘：输入农历年支/月(已解析整数)/日/时支＋性别＋opts → 完整结构化结果
export function calcYizhangjing(input) {
	const opts = input.opts || {};
	const yearIdx = branchIndex(input.yearBranch);
	const hourIdx = branchIndex(input.hourBranch);
	const month = parseInt(input.month, 10);
	const day = parseInt(input.day, 10);
	const gender = input.gender;
	if (yearIdx < 0 || hourIdx < 0 || !month || !day) return null;

	const rule = opts.shunniRule === 'menShunNvNi' ? 'menShunNvNi' : 'yangNanYinNv';
	const mgMethod = opts.mingGongMethod === 'shuZhiMao' ? 'shuZhiMao' : 'shiShang';
	const N = opts.dayunLength === 10 || opts.dayunLength === '10' ? 10 : 7;
	const startMode = opts.dayunStartAge === 'age1' ? 'age1' : 'mi';
	const xiaoStart = opts.xiaoxianStart === 'yue' ? 'yue' : 'ri';
	const flowSet = FLOW_SETS[opts.flowShenSet] ? opts.flowShenSet : 'A';
	const earlyZi = !!opts.zaoZiAdjust;
	// 品级分类变体（默认 undefined → gradeOf 字节不变，golden 与既有快照保持）
	const gradeSet = opts.gradeSet === 'variant' ? 'variant' : undefined;

	const c = fourPalaces(yearIdx, month, day, hourIdx, gender, rule, earlyZi);
	const mg = mingGong(c.ti, hourIdx, c.d, mgMethod);

	const fourIdx = { year: c.yi, month: c.mi, day: c.di, time: c.ti };
	const fourStars = [starOf(c.yi), starOf(c.mi), starOf(c.di), starOf(c.ti)];
	const pillars = ['年', '月', '日', '时'].map((label, i) => {
		const idx = [c.yi, c.mi, c.di, c.ti][i];
		return {
			label, idx, branch: BRANCHES[idx], zodiac: ZODIAC[idx], star: starOf(idx),
			dao: daoOf(idx), grade: gradeOf(starOf(idx), gradeSet), hand: HAND_POS[idx],
		};
	});

	const repeats = chongfanStat(fourStars);
	const up = fourStars.filter((s) => gradeOf(s, gradeSet) === '上品').length;
	const down = fourStars.filter((s) => gradeOf(s, gradeSet) === '下品').length;
	const mid = 4 - up - down;

	const startAge = dayunStartAge(starOf(mg), gender, startMode);
	const dayun = dayunList(c.mi, c.d, N, startAge, 10);
	const xiaoStartIdx = xiaoStart === 'yue' ? c.mi : c.di;

	return {
		input: { yearBranch: BRANCHES[yearIdx], month, day, hourBranch: BRANCHES[hourIdx], gender: (gender === '男' || gender === 1 || gender === 'Male') ? '男' : '女' },
		opts: { rule, mgMethod, N, startMode, xiaoStart, flowSet, earlyZi, gradeSet: gradeSet || 'standard' },
		dir: c.d,
		dirText: c.d === 1 ? '顺行' : '逆行',
		yinyang: yinyang(yearIdx),
		fourIdx,
		pillars,
		timeStar: starOf(c.ti),
		startAge,
		mingIdx: mg,
		mingBranch: BRANCHES[mg],
		mingStar: starOf(mg),
		renshi: renshiPalaces(mg),
		repeats,
		gradeCount: { up, mid, down },
		fourPalaceRank: fourPalaceRank(fourStars, starOf(c.ti), starOf(c.di), gradeSet),
		mingGe: mingGe(fourStars, starOf(c.ti), starOf(c.di), starOf(c.yi), starOf(c.mi), repeats, gradeSet),
		nineGrade: nineGradeEstimate(up, mid, down),
		dayun,
		xiaoStartIdx,
		xiaoStartLabel: xiaoStart === 'yue' ? '月柱宫' : '日柱宫',
		monthBranch: BRANCHES[c.mi],
	};
}

// ══════════════════════════════════════════════════════════════════════════
// WP-B 判识扩展（表驱动/派生层）——均为独立导出，不改 calcYizhangjing 主流程。
// ══════════════════════════════════════════════════════════════════════════

const PILLAR_LABEL = ['年', '月', '日', '时'];

// ── B22 四世权重（根苗花果·年10/月15/日25/时50）──
export const SHISHI_WEIGHTS = [10, 15, 25, 50];
export const SHISHI_LABELS = ['根·前第三世', '苗·前第二世', '花·今世本身', '果·来世子孙'];
export const SHISHI_AGE = ['少年（祖上根基）', '青年（父母庇荫）', '中年（自身作为）', '晚年（子孙福泽）'];

function gradeScore(star, gradeSet) {
	const g = gradeOf(star, gradeSet);
	return g === '上品' ? 1 : (g === '下品' ? -1 : 0);
}

// 加权分＝Σ(权重×品级分{上+1/中0/下−1})；逐柱输出世/年龄段/权重/品级。
export function pillarWeights(fourStars, gradeSet) {
	const rows = PILLAR_LABEL.map((label, i) => ({
		pillar: label,
		shi: SHISHI_LABELS[i],
		age: SHISHI_AGE[i],
		weight: SHISHI_WEIGHTS[i],
		star: fourStars[i],
		grade: gradeOf(fourStars[i], gradeSet),
	}));
	const score = rows.reduce((s, r, i) => s + SHISHI_WEIGHTS[i] * gradeScore(fourStars[i], gradeSet), 0);
	return { rows, score };
}

// ── B19/20/21 九品精确定格 ──
// 星多重集签名（排列无关）：排序后 join。
function multisetKey(stars) {
	return [...stars].sort().join('|');
}
// ①四星多重集匹配 combo（含「三X一Y」具体格已在表中）②孤星≥2 优先走孤克格
// ③全不中→回落启发式并标 matched:false。保留 nineGradeEstimate 供旧测试。
export function nineGradeExact(fourStars, gradeSet) {
	const key = multisetKey(fourStars);
	const guCount = fourStars.filter((s) => s === '天孤').length;
	if (guCount >= 2 && DATA.ninePin && Array.isArray(DATA.ninePin.guke)) {
		for (let i = 0; i < DATA.ninePin.guke.length; i++) {
			const g = DATA.ninePin.guke[i];
			if ((g.patterns || []).some((p) => multisetKey(p) === key)) {
				return { grade: g.grade, level: g.grade, text: g.text || '', matched: true, kind: 'guke' };
			}
		}
	}
	if (DATA.ninePin && Array.isArray(DATA.ninePin.combo)) {
		for (let i = 0; i < DATA.ninePin.combo.length; i++) {
			const g = DATA.ninePin.combo[i];
			if ((g.patterns || []).some((p) => multisetKey(p) === key)) {
				return { grade: g.grade, level: g.level || '', matched: true, kind: 'combo' };
			}
		}
	}
	const up = fourStars.filter((s) => gradeOf(s, gradeSet) === '上品').length;
	const down = fourStars.filter((s) => gradeOf(s, gradeSet) === '下品').length;
	const mid = 4 - up - down;
	return { grade: nineGradeEstimate(up, mid, down), level: '', matched: false, kind: 'estimate' };
}

// ── B6 童限：未交大运前，无论男女一律逆行，命宫1岁→相貌2岁→福德3岁…共 startAge−1 年 ──
export function tongxianList(mingIdx, startAge) {
	const n = (parseInt(startAge, 10) || 1) - 1;
	if (n <= 0) return [];
	const out = [];
	for (let k = 0; k < n; k++) {
		const idx = mod12(mingIdx - k);          // 逆行数支：命→相貌→福德…（人事宫顺布，逆数即 −k）
		const palaceOrder = mod12(-k);           // 宫序 0,11,10,…（命→相貌→福德）
		out.push({ age: k + 1, idx, branch: BRANCHES[idx], star: starOf(idx), palace: PALACES[palaceOrder], dao: daoOf(idx), grade: gradeOf(starOf(idx)) });
	}
	return out;
}

// ── B8 小限顺逆：dirMode 'chart'(随盘向,现状) / 'always'(一律顺行) ──
export function xiaoxianStarAtDir(startPalaceIdx, d, age, dirMode) {
	const dir = dirMode === 'always' ? 1 : d;
	return starOf(startPalaceIdx + dir * (age - 1));
}

// ── B9 小限速算式：(命宫序＋生年序)−流年序，不足＋12、有余−12，规整 1–12 ──
export function xiaoxianQuick(mingIdx, yearIdx, flowIdx) {
	const m = mod12(mingIdx) + 1;   // 序：子=1…亥=12
	const y = mod12(yearIdx) + 1;
	const f = mod12(flowIdx) + 1;
	let v = m + y - f;
	while (v < 1) v += 12;
	while (v > 12) v -= 12;
	return { num: v, branch: BRANCHES[v - 1], star: STARS[v - 1] };
}

// ── B12 巡宫四位：流年在四柱各司其职（年押运/月串宫/日守户/时巡门），取该柱当值神 ──
export const XUN_ROLES = ['押运', '串宫', '守户', '巡门'];
export function xunShenRoles(fourIdx, flowIdx, setKey) {
	const order = ['year', 'month', 'day', 'time'];
	return order.map((k, i) => ({
		role: XUN_ROLES[i],
		pillar: PILLAR_LABEL[i],
		branch: BRANCHES[mod12(fourIdx[k])],
		star: starOf(fourIdx[k]),
		shen: xunShenAt(flowIdx, fourIdx[k], setKey),
	}));
}

// ── B13 流月/流日/流时：流年宫起正月→初一→子时，一律顺行 ──
export function flowSub(flowYearPalaceIdx, month, day, hourIdx) {
	const m = parseInt(month, 10) || 1;
	const dd = parseInt(day, 10) || 1;
	const my = mod12(flowYearPalaceIdx + (m - 1));
	const dy = mod12(my + (dd - 1));
	const hourOrder = mod12(hourIdx) + 1;         // 子=1…亥=12
	const ty = mod12(dy + (hourOrder - 1));
	return {
		month: { idx: my, branch: BRANCHES[my], star: starOf(my) },
		day: { idx: dy, branch: BRANCHES[dy], star: starOf(dy) },
		time: { idx: ty, branch: BRANCHES[ty], star: starOf(ty) },
	};
}

// ── B24 兄弟数（术数取象，非人口统计）：月支五行取数理，出区间 ──
const WUXING_NUM = { 水: [1, 5, 7], 土: [1, 5, 7], 火: [2, 4, 8], 金: [3, 6, 9], 木: [3, 6, 9] };
export function brotherCount(monthBranch) {
	const wx = BRANCH_WUXING[monthBranch];
	if (!wx) return null;
	const nums = WUXING_NUM[wx];
	return {
		wuxing: wx, nums, low: nums[0], high: nums[nums.length - 1],
		text: `${nums[0]}–${nums[nums.length - 1]} 人`, note: '术数取象，非人口统计',
	};
}

// ── B25/B26 星曜阴阳分（⚠ 与判顺逆用的「年支阴阳」是两回事：此处按星曜本身归六阳六阴）──
export const STAR_YANG = ['天貴', '天權', '天奸', '天福', '天孤', '天藝'];
export const STAR_YIN = ['天厄', '天壽', '天刃', '天驛', '天文', '天破'];
export function starPolarity(fourStars) {
	const yang = fourStars.filter((s) => STAR_YANG.indexOf(s) >= 0).length;
	const yin = fourStars.filter((s) => STAR_YIN.indexOf(s) >= 0).length;
	let judge = '';
	if (yang === 4) judge = '四柱纯阳（孤阳不长）：父母必有刑伤。';
	else if (yin === 4) judge = '四柱纯阴（孤阴不生）：父母必有刑伤。';
	else if (yang > yin) judge = '阳星多：先克父。';
	else if (yin > yang) judge = '阴星多：先克母。';
	else judge = '阴阳均停：父母俱全，刑克较轻。';
	return { yang, yin, judge };
}

// ── B27 地支刑冲害叠断（命中挂刑害歌断语）──
const HAI_PAIRS = [['子', '未'], ['丑', '午'], ['寅', '巳'], ['卯', '辰'], ['申', '亥'], ['酉', '戌']];
const XING_GROUPS = [['子', '卯'], ['寅', '巳', '申'], ['丑', '戌', '未'], ['辰'], ['午'], ['酉'], ['亥']]; // 单元素=自刑
export function branchClash(fourIdx, mingIdx) {
	const idxs = [fourIdx.year, fourIdx.month, fourIdx.day, fourIdx.time];
	const set = idxs.map((i) => BRANCHES[mod12(i)]);
	const hits = [];
	for (let i = 0; i < idxs.length; i++) {
		for (let j = i + 1; j < idxs.length; j++) {
			if (mod12(idxs[i] - idxs[j]) === 6) {
				hits.push({ type: '冲', a: BRANCHES[mod12(idxs[i])], b: BRANCHES[mod12(idxs[j])], pillars: [PILLAR_LABEL[i], PILLAR_LABEL[j]] });
			}
		}
	}
	HAI_PAIRS.forEach(([x, y]) => {
		if (set.indexOf(x) >= 0 && set.indexOf(y) >= 0) hits.push({ type: '害', a: x, b: y });
	});
	XING_GROUPS.forEach((grp) => {
		if (grp.length === 1) {
			if (set.filter((s) => s === grp[0]).length >= 2) hits.push({ type: '自刑', a: grp[0], b: grp[0] });
		} else {
			const present = grp.filter((s) => set.indexOf(s) >= 0);
			if (present.length >= 2) hits.push({ type: '刑', group: grp.join(''), present });
		}
	});
	const branchHarm = DATA.branchHarm || {};
	const uniq = [];
	set.forEach((b) => { if (uniq.indexOf(b) < 0) uniq.push(b); });
	const harmTexts = uniq.filter((b) => branchHarm[b]).map((b) => ({ branch: b, text: branchHarm[b] }));
	return { hits, harmTexts };
}

// ── B28 星组合互见（四星两两无序查 pairRule，去重）──
export function pairHits(fourStars) {
	const uniq = [];
	fourStars.forEach((s) => { if (uniq.indexOf(s) < 0) uniq.push(s); });
	const rules = DATA.pairRule || [];
	const seen = {};
	const out = [];
	for (let i = 0; i < uniq.length; i++) {
		for (let j = i + 1; j < uniq.length; j++) {
			const x = uniq[i]; const y = uniq[j];
			rules.forEach((r) => {
				if ((r.a === x && r.b === y) || (r.a === y && r.b === x)) {
					if (!seen[r.text]) { seen[r.text] = 1; out.push(r); }
				}
			});
		}
	}
	return out;
}

// ── B23 四柱旺衰（各支对月令取旺相休囚死 + 用法断语）──
const STATE_TEXT = { 旺: '当令得时', 相: '得生有气', 休: '退气无力', 囚: '受制困顿', 死: '全然无气' };
export function pillarWuxing(fourIdx, monthBranchIdx, gradeSet) {
	const monthBranch = BRANCHES[mod12(monthBranchIdx)];
	return ['year', 'month', 'day', 'time'].map((k, i) => {
		const b = BRANCHES[mod12(fourIdx[k])];
		const state = wuxingState(monthBranch, b);
		const star = starOf(fourIdx[k]);
		const g = gradeOf(star, gradeSet);
		const strong = state === '旺' || state === '相';
		const omen = strong
			? (g === '上品' ? '吉星旺相，福力大兴。' : g === '下品' ? '凶星旺相，为祸尤烈。' : '中星旺相，平中见起。')
			: (g === '上品' ? '吉星失气，福力打折。' : g === '下品' ? '凶星失气，为害稍轻。' : '中星失气，平淡守常。');
		return { pillar: PILLAR_LABEL[i], branch: b, star, wuxing: BRANCH_WUXING[b], state, stateText: STATE_TEXT[state] || '', omen };
	});
}

// ── B31 子时细分：子初23:00–23:40 / 子中23:40–00:20 / 子末00:20–01:00 ──
export function ziSubPeriod(hh, mm) {
	const h = parseInt(hh, 10);
	if (isNaN(h)) return null;
	const m = parseInt(mm, 10) || 0;
	const isZi = h === 23 || h === 0;
	if (!isZi) return null;
	const t = (h === 23 ? 0 : 60) + m; // 自 23:00 起的分钟数
	if (t < 40) return { key: 'chu', label: '子初', range: '23:00–23:40' };
	if (t < 80) return { key: 'zhong', label: '子中', range: '23:40–00:20' };
	return { key: 'mo', label: '子末', range: '00:20–01:00' };
}

// ── A2/A7/A8 显示层映射（盘算一律用 A 系内部键，仅换显示名 → 零算法回归）──
// 星名系统：'A'(主流,默认) / 'B'(异名·断语互通) / 'C'(仅异名显示)。
export function starLabel(star, naming) {
	if ((naming === 'B' || naming === 'C')) {
		const idx = STARS.indexOf(star);
		if (idx >= 0) {
			const zhi = BRANCHES[idx];
			const alias = (DATA.starAlias || {})[zhi];
			if (alias && alias[naming] && alias[naming] !== '—' && alias[naming] !== star) return alias[naming];
		}
	}
	return star;
}
// 六道术语：'gui'(鬼道/修羅道,默认) / 'edao'(饿鬼道/阿修羅道)。
export function daoLabel(dao, term) {
	if (term === 'edao') {
		if (dao === '鬼道') return '饿鬼道';
		if (dao === '修羅道') return '阿修羅道';
	}
	return dao;
}

export default { calcYizhangjing };
