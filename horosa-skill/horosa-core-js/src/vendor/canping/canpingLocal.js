// 邵子参评数（金锁银匙）——前端本地计算（不走后端 / kentang）。
// 四柱来自 baziLunarLocal（星阙自己的八字），本模块只做金锁银匙起数 + 条文查找。
// 算法已对文档算例（本命2242/3242、大运寅3038/2438、流年戌2543/2943）逐字验证。
import TIAOWEN from './data/canpingTiaowen.json' with { type: 'json' };

const BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const BRANCH_NUM = {};
BRANCHES.forEach((b, i) => { BRANCH_NUM[b] = i + 1; });

// 明法（胖胖熊）：月支(月建/八字月支)反向取日宫支
const MONTH_TO_DAY_PALACE = {
	寅: '亥', 卯: '戌', 辰: '酉', 巳: '申', 午: '未', 未: '午',
	申: '巳', 酉: '辰', 戌: '卯', 亥: '寅', 子: '丑', 丑: '子',
};
const ELEMENT_ADD = { 水: 27, 火: 27, 土: 50, 木: 0, 金: 0 };   // 水火+27 土+50 木金+0
const ELEMENT_PEI = { 水: 1, 火: 2, 木: 3, 金: 4, 土: 5 };       // 水1火2木3金4土5

const NAYIN_PAIRS = [
	['甲子', '乙丑', '金'], ['丙寅', '丁卯', '火'], ['戊辰', '己巳', '木'],
	['庚午', '辛未', '土'], ['壬申', '癸酉', '金'], ['甲戌', '乙亥', '火'],
	['丙子', '丁丑', '水'], ['戊寅', '己卯', '土'], ['庚辰', '辛巳', '金'],
	['壬午', '癸未', '木'], ['甲申', '乙酉', '水'], ['丙戌', '丁亥', '土'],
	['戊子', '己丑', '火'], ['庚寅', '辛卯', '木'], ['壬辰', '癸巳', '水'],
	['甲午', '乙未', '金'], ['丙申', '丁酉', '火'], ['戊戌', '己亥', '木'],
	['庚子', '辛丑', '土'], ['壬寅', '癸卯', '金'], ['甲辰', '乙巳', '火'],
	['丙午', '丁未', '水'], ['戊申', '己酉', '土'], ['庚戌', '辛亥', '金'],
	['壬子', '癸丑', '木'], ['甲寅', '乙卯', '水'], ['丙辰', '丁巳', '土'],
	['戊午', '己未', '火'], ['庚申', '辛酉', '木'], ['壬戌', '癸亥', '水'],
];
const NAYIN_ELEMENT = {};
NAYIN_PAIRS.forEach(([a, b, el]) => { NAYIN_ELEMENT[a] = el; NAYIN_ELEMENT[b] = el; });

const PART_NAMES = { 水: '水部', 火: '火部', 木: '木部', 金: '金部', 土: '土部' };

export function nayinElement(yearGz) {
	return NAYIN_ELEMENT[yearGz] || '';
}

function branchFromNum(n) {
	return BRANCHES[((n - 1) % 12 + 12) % 12];
}

function branchOf(ganzhiOrBranch) {
	const s = `${ganzhiOrBranch || ''}`;
	if (s.length >= 2 && BRANCH_NUM[s[1]]) return s[1];
	if (s.length === 1 && BRANCH_NUM[s]) return s;
	return '';
}

export function dayPalace(monthBranch, dayBranch, method = 'ming') {
	if (method === 'gu') return dayBranch;
	return MONTH_TO_DAY_PALACE[monthBranch] || dayBranch;
}

export function mingGong(dayPalaceBranch, hourBranch) {
	// 命宫：日宫支配卯时起，逆数至生时
	const mao = BRANCH_NUM['卯'];
	const dp = BRANCH_NUM[dayPalaceBranch];
	const hb = BRANCH_NUM[hourBranch];
	const idx = ((dp - (hb - mao) - 1) % 12 + 12) % 12 + 1;
	return branchFromNum(idx);
}

export function computeNumber(dayBranch, hourBranch, element) {
	const dp = BRANCH_NUM[dayBranch];
	const hb = BRANCH_NUM[hourBranch];
	const shun = ((12 + (hb - dp)) % 12) + 1;   // 日支顺数至时支
	const ni = 14 - shun;                         // 时日顺冲（逆）
	const ziRound = dp + hb;                      // 时日皆从子上轮
	const add = ELEMENT_ADD[element] || 0;
	const pei = ELEMENT_PEI[element] || 0;
	const base = 2000 + ziRound + add + pei;
	return { shun, ni, ziRound, numShun: base + shun * 100, numNi: base + ni * 100 };
}

function lookup(element, number, kind) {
	const part = (TIAOWEN.parts || {})[element] || {};
	const entry = part[String(number)];
	if (entry) return entry[kind] || '';
	const sp = (TIAOWEN.special || {})[String(number)];
	if (sp) return sp.text || '';
	return '';
}

function verses(element, info, kind) {
	return {
		numShun: info.numShun,
		numNi: info.numNi,
		textShun: lookup(element, info.numShun, kind),
		textNi: lookup(element, info.numNi, kind),
	};
}

export function dayunSequence(dayPalaceBranch, hourBranch, qiyunAge = 1, count = 9) {
	const mg = mingGong(dayPalaceBranch, hourBranch);
	const startIdx = BRANCH_NUM[mg];
	const seq = [];
	for (let k = 0; k < count; k += 1) {
		const branch = branchFromNum(startIdx + k);
		const ageStart = qiyunAge + 10 * k;
		seq.push({ index: k, branch, ageStart, ageEnd: ageStart + 9 });
	}
	return { seq, mingGong: mg };
}

export function calculate({ yearGz, monthBranch, dayBranch, hourBranch, gender = '男', method = 'ming', qiyunAge = 1, liunianBranch = null }) {
	const element = nayinElement(yearGz);
	const dpBranch = dayPalace(monthBranch, dayBranch, method);
	const kindMain = (gender === '女' || gender === 'F' || gender === 'female' || gender === 0) ? 'female' : 'male';

	const benming = computeNumber(dpBranch, hourBranch, element);
	const benmingVerses = verses(element, benming, kindMain);

	const { seq, mingGong: mg } = dayunSequence(dpBranch, hourBranch, qiyunAge);
	const dayun = seq.map((d) => {
		const info = computeNumber(dpBranch, d.branch, element);
		return { ...d, ...info, verses: verses(element, info, 'luck') };
	});

	let liunian = null;
	if (liunianBranch) {
		const curDayun = dayun.length ? dayun[0].branch : mg;
		const info = computeNumber(branchOf(liunianBranch), curDayun, element);
		liunian = { taisuiBranch: branchOf(liunianBranch), dayunBranch: curDayun, ...info, verses: verses(element, info, 'luck') };
	}

	return {
		method, gender, element, partName: PART_NAMES[element] || `${element}部`,
		fourPillars: { yearGz, monthBranch, dayBranch, hourBranch },
		dayPalaceBranch: dpBranch, mingGong: mg, kindMain,
		benming: { ...benming, verses: benmingVerses },
		dayun, liunian, qiyunAge,
	};
}

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
function yearGanzhi(year) { return GANS[((year - 4) % 10 + 10) % 10] + BRANCHES[((year - 4) % 12 + 12) % 12]; }

// 全表流年：自 startAge 至 endAge(虚岁)逐岁。太岁(当年年支)替日宫支、当时大运支替时支起数。
// 大运用命宫顺行(calculate 内 dayunSequence)，每岁按虚岁定位所属大运。
export function liunianSeries({ yearGz, monthBranch, dayBranch, hourBranch, gender = '男', method = 'ming', qiyunAge = 1, birthYear = 0, startAge = 1, endAge = 120 }) {
	const r = calculate({ yearGz, monthBranch, dayBranch, hourBranch, gender, method, qiyunAge });
	const { element, dayun } = r;
	const dayunAt = (age) => {
		if (!dayun.length) return { branch: r.mingGong, ageStart: 1, ageEnd: 10 };
		let k = Math.floor((age - qiyunAge) / 10);
		if (k < 0) k = 0;
		if (k > dayun.length - 1) k = dayun.length - 1;
		return dayun[k];
	};
	const rows = [];
	for (let age = startAge; age <= endAge; age += 1) {
		const year = birthYear ? birthYear + age - 1 : 0;
		const taisui = year ? BRANCHES[((year - 4) % 12 + 12) % 12] : '';
		const dy = dayunAt(age);
		const info = computeNumber(taisui || dayBranch, dy.branch, element);
		rows.push({
			age, year, ganzhi: year ? yearGanzhi(year) : '', taisuiBranch: taisui,
			dayunBranch: dy.branch, dayunRange: `${dy.ageStart}-${dy.ageEnd}`,
			...info, verses: verses(element, info, 'luck'),
		});
	}
	return { element, partName: r.partName, dayun, rows, qiyunAge };
}

export function buildSnapshotText(result) {
	if (!result) return '';
	const lines = [];
	const bm = result.benming || {};
	const v = bm.verses || {};
	lines.push('[起盘]');
	lines.push(`年纳音：${result.element}（${result.partName}）  取法：${result.method === 'gu' ? '古法(八字日支)' : '明法(月支反向)'}`);
	lines.push(`日宫支：${result.dayPalaceBranch}  命宫：${result.mingGong}`);
	lines.push('');
	lines.push('[本命]');
	lines.push(`顺 ${v.numShun}：${v.textShun}`);
	lines.push(`逆 ${v.numNi}：${v.textNi}`);
	lines.push('');
	lines.push('[大运·歲運]');
	(result.dayun || []).forEach((d) => {
		const dv = d.verses || {};
		lines.push(`${d.ageStart}-${d.ageEnd}岁 ${d.branch}：顺${dv.numShun} ${dv.textShun} ／ 逆${dv.numNi} ${dv.textNi}`);
	});
	if (result.liunian) {
		const lv = result.liunian.verses || {};
		lines.push('');
		lines.push('[流年·歲運]');
		lines.push(`太岁${result.liunian.taisuiBranch}/大运${result.liunian.dayunBranch}：顺${lv.numShun} ${lv.textShun} ／ 逆${lv.numNi} ${lv.textNi}`);
	}
	return lines.join('\n');
}

export default calculate;
