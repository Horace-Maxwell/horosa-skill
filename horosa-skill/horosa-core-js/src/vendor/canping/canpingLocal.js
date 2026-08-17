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

// 大运排法三档（诸法分歧；默认 mingGongQiyun）：
//   mingGongQiyun —— 命宫顺行 + 起运岁按生日推算（《参评诀》口径，本仓默认）
//   mingGongOne   —— 命宫顺行 + 恒一岁起（v3.6.0 及以前的旧行为，保留可回退）
//   baziStyle     —— 八字大运法：阳男阴女顺／阴男阳女逆，自月建下一位起，十年一运
//                    （《河洛理数》注解所载「采用推八字取大运之法」；起运岁沿用所选起运推算）
export const CANPING_DAYUN_RULES = ['mingGongQiyun', 'mingGongOne', 'baziStyle'];
export const CANPING_DAYUN_RULE_LABELS = {
	mingGongQiyun: '命宫顺行 · 生日推起运（默认）',
	mingGongOne: '命宫顺行 · 恒一岁起',
	baziStyle: '八字大运法（阳男阴女顺／阴男阳女逆）',
};
const YANG_GANS = ['甲', '丙', '戊', '庚', '壬'];

/**
 * 起运岁（《参评诀》口径）：农历**单月**由三十逆数至生日、**双月**由初一顺数至生日；
 * 得数 ÷3 → 商＝岁、余 2 ＝ +8 个月、余 1 ＝ +4 个月。
 * 表格起始整岁 = 商 + (有余数 ? 1 : 0)（如 1 岁 8 个月 → 自 2 岁起行）。
 * 缺农历月日时退回 1（＝旧行为，绝不抛）。
 */
export function qiyunFromLunarDate(lunarMonth, lunarDay) {
	const m = Math.trunc(Number(lunarMonth) || 0);
	const d = Math.trunc(Number(lunarDay) || 0);
	if (m < 1 || m > 12 || d < 1 || d > 30) {
		return { startAge: 1, years: 0, months: 0, count: 0, usable: false };
	}
	const count = (m % 2 === 1) ? (30 - d + 1) : d;   // 单月三十逆数 ／ 双月初一顺数
	const years = Math.floor(count / 3);
	const rem = count % 3;
	const months = rem === 2 ? 8 : (rem === 1 ? 4 : 0);
	const startAge = Math.max(1, years + (rem > 0 ? 1 : 0));
	return { startAge, years, months, count, usable: true };
}

export function dayunSequence(dayPalaceBranch, hourBranch, qiyunAge = 1, count = 9, opts = {}) {
	const mg = mingGong(dayPalaceBranch, hourBranch);
	const rule = CANPING_DAYUN_RULES.indexOf(opts.rule) >= 0 ? opts.rule : 'mingGongQiyun';
	const seq = [];
	if (rule === 'baziStyle') {
		// [Win-D69] 八字大运法与八字模块同源:此前本档只抄了排序(阳男阴女顺逆+月建下一位),
		// 起运岁却仍用《参评诀》口径(单双月数日÷3)——与八字模块的**节气起运法**必然对不上
		// (用户实测 v3.8.1:起运岁数/年份双双错位;锚例 1990-03-15 男:参评诀 7 岁 vs 节气法 8 岁)。
		// 根治=调用方注入 opts.baziYun(取自 buildLocalBaziResult().bazi.direction,即 lunar-js
		// 节气起运真源):干支/起讫虚岁/公历年份逐项与八字盘逐字节同源。缺注入(远程农历桥域外
		// /测试裸调)→ 旧排序法回退(零崩,UI 会失去年份列)。
		const inj = Array.isArray(opts.baziYun) ? opts.baziYun.filter((d)=>d && d.branch) : null;
		if (inj && inj.length) {
			inj.slice(0, count).forEach((d, k) => {
				seq.push({ index: k, branch: d.branch, ganzi: d.ganzi || '', ageStart: d.ageStart, ageEnd: d.ageEnd, startYear: d.startYear, endYear: d.endYear });
			});
			const fwd = inj.length > 1 ? ((BRANCH_NUM[inj[1].branch] || 0) === ((BRANCH_NUM[inj[0].branch] || 0) % 12) + 1) : true;
			return { seq, mingGong: mg, rule, forward: fwd, baziSourced: true };
		}
		// 阳年干男／阴年干女 顺行；阴年干男／阳年干女 逆行。自月建**下一位**起（八字通例）。
		const yangYear = YANG_GANS.indexOf(`${opts.yearGz || ''}`.charAt(0)) >= 0;
		const male = opts.gender !== '女';
		const forward = yangYear === male;
		const startIdx = BRANCH_NUM[opts.monthBranch] || BRANCH_NUM[mg];
		for (let k = 0; k < count; k += 1) {
			const branch = branchFromNum(forward ? startIdx + k + 1 : startIdx - k - 1);
			const ageStart = qiyunAge + 10 * k;
			seq.push({ index: k, branch, ageStart, ageEnd: ageStart + 9 });
		}
		return { seq, mingGong: mg, rule, forward };
	}
	const startIdx = BRANCH_NUM[mg];
	for (let k = 0; k < count; k += 1) {
		const branch = branchFromNum(startIdx + k);
		const ageStart = qiyunAge + 10 * k;
		seq.push({ index: k, branch, ageStart, ageEnd: ageStart + 9 });
	}
	return { seq, mingGong: mg, rule, forward: true };
}

export function calculate({ yearGz, monthBranch, dayBranch, hourBranch, gender = '男', method = 'ming', qiyunAge = 1, liunianBranch = null, lunarMonth = 0, lunarDay = 0, dayunRule = 'mingGongQiyun', baziYun = null }) {
	const element = nayinElement(yearGz);
	const dpBranch = dayPalace(monthBranch, dayBranch, method);
	const kindMain = (gender === '女' || gender === 'F' || gender === 'female' || gender === 0) ? 'female' : 'male';

	const benming = computeNumber(dpBranch, hourBranch, element);
	const benmingVerses = verses(element, benming, kindMain);

	// 起运岁：mingGongOne 档恒 1（旧行为）；其余档按生日推算，农历缺失时自动退回 1。
	// [Win-D69] baziStyle+注入 baziYun:起运岁改用八字真源首运虚岁(节气起运法,与八字盘同源),
	// 《参评诀》口径只服务命宫两档;无注入回退旧口径(零回归)。
	const rule = CANPING_DAYUN_RULES.indexOf(dayunRule) >= 0 ? dayunRule : 'mingGongQiyun';
	const inj = (rule === 'baziStyle' && Array.isArray(baziYun) && baziYun.length && baziYun[0] && baziYun[0].branch) ? baziYun : null;
	const qiyun = inj
		? { startAge: Math.max(1, Math.trunc(Number(inj[0].ageStart) || 1)), years: 0, months: 0, count: 0, usable: false, baziSourced: true }
		: (rule === 'mingGongOne'
			? { startAge: Math.max(1, Math.trunc(Number(qiyunAge) || 1)), years: 0, months: 0, count: 0, usable: false }
			: qiyunFromLunarDate(lunarMonth, lunarDay));
	const effQiyunAge = (qiyun.usable || qiyun.baziSourced) ? qiyun.startAge : Math.max(1, Math.trunc(Number(qiyunAge) || 1));

	const { seq, mingGong: mg, forward, baziSourced } = dayunSequence(dpBranch, hourBranch, effQiyunAge, 9, {
		rule, yearGz, monthBranch, gender, baziYun: inj,
	});
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
		dayun, liunian, qiyunAge: effQiyunAge,
		dayunRule: rule, dayunForward: forward, qiyunDetail: qiyun, baziSourced: !!baziSourced,
	};
}

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
function yearGanzhi(year) { return GANS[((year - 4) % 10 + 10) % 10] + BRANCHES[((year - 4) % 12 + 12) % 12]; }

// 全表流年：自 startAge 至 endAge(虚岁)逐岁。太岁(当年年支)替日宫支、当时大运支替时支起数。
// 大运用命宫顺行(calculate 内 dayunSequence)，每岁按虚岁定位所属大运。
export function liunianSeries({ yearGz, monthBranch, dayBranch, hourBranch, gender = '男', method = 'ming', qiyunAge = 1, birthYear = 0, startAge = 1, endAge = 120, lunarMonth = 0, lunarDay = 0, dayunRule = 'mingGongQiyun', baziYun = null }) {
	const r = calculate({ yearGz, monthBranch, dayBranch, hourBranch, gender, method, qiyunAge, lunarMonth, lunarDay, dayunRule, baziYun });
	const { element, dayun } = r;
	// 🔴 定位大运用**引擎实算的起运岁**(r.qiyunAge),不是入参 qiyunAge——起运岁按生日推算后
	// 两者会不同,用入参会让整张流年表的大运列错位。
	const effQiyunAge = r.qiyunAge;
	const dayunAt = (age) => {
		if (!dayun.length) return { branch: r.mingGong, ageStart: 1, ageEnd: 10 };
		let k = Math.floor((age - effQiyunAge) / 10);
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
	// 回传**实算**起运岁与档位（消费方按此渲染/对齐；回传入参会与表内容不符）
	return { element, partName: r.partName, dayun, rows, qiyunAge: effQiyunAge, dayunRule: r.dayunRule, qiyunDetail: r.qiyunDetail };
}

export function buildSnapshotText(result, opts = {}) {
	if (!result) return '';
	const lines = [];
	const bm = result.benming || {};
	const v = bm.verses || {};
	lines.push('[起盘]');
	lines.push(`年纳音：${result.element}（${result.partName}）  取法：${result.method === 'gu' ? '古法(八字日支)' : '明法(月支反向)'}`);
	lines.push(`日宫支：${result.dayPalaceBranch}  命宫：${result.mingGong}`);
	// 性别取层与大运法必须进快照:AI 此前看不出取的是上层洞门(男命)还是中层闺门(女命)、
	// 也看不出大运用了哪一法(段头字串是导出锚点,一律不动,只在段内补行)。
	lines.push(`性别取层：${result.kindMain === 'female' ? '女命（中层闺门）' : '男命（上层洞门）'}`);
	lines.push('');
	lines.push('[本命]');
	lines.push(`顺 ${v.numShun}：${v.textShun}`);
	lines.push(`逆 ${v.numNi}：${v.textNi}`);
	lines.push('');
	lines.push('[大运·歲運]');
	{
		const q = result.qiyunDetail || {};
		// [Win-D69] baziSourced=真源注入:排法/起运措辞照实(节气起运,与八字盘同源),AI 不再被
		// 「参评诀起运」误导;未注入(域外回退)维持旧措辞逐字。
		const ruleCn = result.dayunRule === 'baziStyle'
			? (result.baziSourced
				? `八字大运法（${result.dayunForward ? '顺行' : '逆行'}，与八字盘同源）`
				: `八字大运法（${result.dayunForward ? '顺行' : '逆行'}，自月建下一位起）`)
			: '命宫顺行';
		const qCn = result.baziSourced
			? `节气起运（自 ${result.qiyunAge} 岁行运，起讫与八字盘一致）`
			: (q.usable
				? `起运 ${q.years} 岁${q.months ? `${q.months} 个月` : ''}（自 ${result.qiyunAge} 岁行运）`
				: '一岁起运');
		lines.push(`排法：${ruleCn}  ${qCn}`);
	}
	// [v2 排版批量·表化] 同构逐条行改 GFM 表(紫微宫位总览范式):段头/值表达式零变更
	// (ageStart-ageEnd岁/branch/顺numShun/textShun/逆numNi/textNi 逐字复用),仅排版骨架换表头+分隔行+数据行。
	if (result.baziSourced) {
		// [Win-D69] 真源档:干支+公历年两列(与八字盘可直接对照;AI 引用有年份锚)。
		lines.push('| 歲段 | 公历年 | 大运 | 顺 | 顺辞 | 逆 | 逆辞 |');
		lines.push('| --- | --- | --- | --- | --- | --- | --- |');
		(result.dayun || []).forEach((d) => {
			const dv = d.verses || {};
			const yr = d.startYear && d.endYear ? `${d.startYear}-${d.endYear}` : '—';
			lines.push(`| ${d.ageStart}-${d.ageEnd}岁 | ${yr} | ${d.ganzi || d.branch} | 顺${dv.numShun} | ${dv.textShun} | 逆${dv.numNi} | ${dv.textNi} |`);
		});
	} else {
		lines.push('| 歲段 | 大运支 | 顺 | 顺辞 | 逆 | 逆辞 |');
		lines.push('| --- | --- | --- | --- | --- | --- |');
		(result.dayun || []).forEach((d) => {
			const dv = d.verses || {};
			lines.push(`| ${d.ageStart}-${d.ageEnd}岁 | ${d.branch} | 顺${dv.numShun} | ${dv.textShun} | 逆${dv.numNi} | ${dv.textNi} |`);
		});
	}
	const ynRows = opts && Array.isArray(opts.liunianRows) ? opts.liunianRows : null;
	if (ynRows && ynRows.length) {
		// 全生涯流年表:此前 buildCanpingSnapshotForRecord 不传 liunianBranch → result.liunian 恒 null、流年段恒空,
		// 挂载/导出都缺流年。改由调用方喂入 liunianSeries(...).rows,逐岁出 太岁/大运/顺逆数(紧凑,不含逐句判语避免过长)。
		lines.push('');
		lines.push('[流年·歲運]');
		// [v2 排版批量·表化] 1-120 岁全表改 GFM 表:值表达式逐字复用(age岁/yzz/太岁taisuiBranch/
		// 大运dayunBranch/顺numShun/逆numNi),仅排版骨架变化;单行 else 分支(非同构全表)保持原样。
		lines.push('| 歲 | 年·干支 | 太岁 | 大运 | 顺 | 逆 |');
		lines.push('| --- | --- | --- | --- | --- | --- |');
		ynRows.forEach((row) => {
			const rv = row.verses || {};
			const yzz = row.year ? `${row.year}·${row.ganzhi}` : '';
			lines.push(`| ${row.age}岁 | ${yzz} | 太岁${row.taisuiBranch || '-'} | 大运${row.dayunBranch || '-'} | 顺${rv.numShun} | 逆${rv.numNi} |`);
		});
	} else if (result.liunian) {
		const lv = result.liunian.verses || {};
		lines.push('');
		lines.push('[流年·歲運]');
		lines.push(`太岁${result.liunian.taisuiBranch}/大运${result.liunian.dayunBranch}：顺${lv.numShun} ${lv.textShun} ／ 逆${lv.numNi} ${lv.textNi}`);
	}
	return lines.join('\n');
}

export default calculate;
