// 一掌经 · 纯前端排盘引擎（零后端）。
// 十二地支各坐一星，由农历生年支/月/日/时支＋性别经掌上顺逆排四柱四宫、命宫、
// 人事十二宫，叠大限/小限/流年十二神与格局判识。全部为分支算术，可复现、可golden。
// 说明：星名用繁体（与断语数据键一致）；月/闰月/节气月归属在调用方解析后以整数 month 传入，
// 本引擎保持纯函数便于逐例核验。

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

export function gradeOf(star) {
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

// 四宫等第（以时宫为主）
export function fourPalaceRank(stars, timeStar, dayStar) {
	const up = stars.filter((s) => GRADE_UP.indexOf(s) >= 0).length;
	const down = stars.filter((s) => GRADE_DOWN.indexOf(s) >= 0).length;
	const timeUp = GRADE_UP.indexOf(timeStar) >= 0;
	const timeDown = GRADE_DOWN.indexOf(timeStar) >= 0;
	const dayUp = GRADE_UP.indexOf(dayStar) >= 0;
	const dayDown = GRADE_DOWN.indexOf(dayStar) >= 0;
	if (up === 4) return '最上等命（四宫全吉）';
	if (down === 4) return '下等命（四宫全凶）';
	if (timeUp && dayUp) return '上等命（时吉日吉·年月不足）';
	if (timeDown && dayDown) return '中等命（时凶日凶·年月吉）';
	return '中平之命（吉凶混见·以时宫为主）';
}

// 命格（定义化，最易上手）
export function mingGe(stars, timeStar, dayStar, yearStar, monthStar, repeats) {
	const up = stars.filter((s) => GRADE_UP.indexOf(s) >= 0).length;
	const down = stars.filter((s) => GRADE_DOWN.indexOf(s) >= 0).length;
	const timeUp = GRADE_UP.indexOf(timeStar) >= 0;
	const timeDown = GRADE_DOWN.indexOf(timeStar) >= 0;
	const ymUp = GRADE_UP.indexOf(yearStar) >= 0 && GRADE_UP.indexOf(monthStar) >= 0;
	const ymDown = GRADE_DOWN.indexOf(yearStar) >= 0 && GRADE_DOWN.indexOf(monthStar) >= 0;
	const dtUp = GRADE_UP.indexOf(dayStar) >= 0 && timeUp;
	const dtDown = GRADE_DOWN.indexOf(dayStar) >= 0 && timeDown;
	const hasUpRepeat = repeats.some((r) => GRADE_UP.indexOf(r.star) >= 0);
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

	const c = fourPalaces(yearIdx, month, day, hourIdx, gender, rule, earlyZi);
	const mg = mingGong(c.ti, hourIdx, c.d, mgMethod);

	const fourIdx = { year: c.yi, month: c.mi, day: c.di, time: c.ti };
	const fourStars = [starOf(c.yi), starOf(c.mi), starOf(c.di), starOf(c.ti)];
	const pillars = ['年', '月', '日', '时'].map((label, i) => {
		const idx = [c.yi, c.mi, c.di, c.ti][i];
		return {
			label, idx, branch: BRANCHES[idx], zodiac: ZODIAC[idx], star: starOf(idx),
			dao: daoOf(idx), grade: gradeOf(starOf(idx)), hand: HAND_POS[idx],
		};
	});

	const repeats = chongfanStat(fourStars);
	const up = fourStars.filter((s) => GRADE_UP.indexOf(s) >= 0).length;
	const down = fourStars.filter((s) => GRADE_DOWN.indexOf(s) >= 0).length;
	const mid = 4 - up - down;

	const startAge = dayunStartAge(starOf(mg), gender, startMode);
	const dayun = dayunList(c.mi, c.d, N, startAge, 10);
	const xiaoStartIdx = xiaoStart === 'yue' ? c.mi : c.di;

	return {
		input: { yearBranch: BRANCHES[yearIdx], month, day, hourBranch: BRANCHES[hourIdx], gender: (gender === '男' || gender === 1 || gender === 'Male') ? '男' : '女' },
		opts: { rule, mgMethod, N, startMode, xiaoStart, flowSet, earlyZi },
		dir: c.d,
		dirText: c.d === 1 ? '顺行' : '逆行',
		yinyang: yinyang(yearIdx),
		fourIdx,
		pillars,
		timeStar: starOf(c.ti),
		mingIdx: mg,
		mingBranch: BRANCHES[mg],
		mingStar: starOf(mg),
		renshi: renshiPalaces(mg),
		repeats,
		gradeCount: { up, mid, down },
		fourPalaceRank: fourPalaceRank(fourStars, starOf(c.ti), starOf(c.di)),
		mingGe: mingGe(fourStars, starOf(c.ti), starOf(c.di), starOf(c.yi), starOf(c.mi), repeats),
		nineGrade: nineGradeEstimate(up, mid, down),
		dayun,
		xiaoStartIdx,
		xiaoStartLabel: xiaoStart === 'yue' ? '月柱宫' : '日柱宫',
		monthBranch: BRANCHES[c.mi],
	};
}

export default { calcYizhangjing };
