// 紫白飞星 · 年/月/日/时入中九宫 + 紫白吉凶 + 紫白诀（8.1 / 8.9）。日时用 lunar-javascript 取干支与节气。
import { Solar } from 'lunar-javascript';
import { zibaiYearCenter } from './liqiCore.js';
import { ZIBAI_STAR, ZIBAI_JX, GONG_NAME, GONG_GUA, NINE_STAR_MEANING, GANZHI_60, DIZHI } from './fengshuiData.js';

const idxF = (n)=>(n - 5 + 9) % 9;
function flyFromCenter(center) {
	const pan = {};
	for (let g = 1; g <= 9; g++) { pan[g] = (center - 1 + idxF(g)) % 9 + 1; }
	return pan;
}

// 月入中（8.1.2）：年支三组定正月入中星，逐月逆退。
const MONTH_START = { 子: 8, 午: 8, 卯: 8, 酉: 8, 辰: 5, 戌: 5, 丑: 5, 未: 5, 寅: 2, 申: 2, 巳: 2, 亥: 2 };
const YEAR_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];   // 1900=庚子(支子)起
function yearZhi(year) { return YEAR_ZHI[((year - 1900) % 12 + 12) % 12]; }
export function monthCenter(year, month) {
	const start = MONTH_START[yearZhi(year)];
	let c = start - (month - 1);
	c = ((c - 1) % 9 + 9) % 9 + 1;
	return c;
}

// ── 日紫白（8.1.3）：阳遁三个甲子起一白·七赤·四绿顺行，阴遁三个甲子起九紫·三碧·六白逆行。──
// 遁内逐日连续 ±1：一白顺行 60 日到下一甲子正是七赤、再 60 日是四绿，再 60 日回到一白；九紫逆行同理得三碧、六白。
// 起遁点取「离冬至 / 夏至最近的甲子」（冬至这一侧起一白阳遁、夏至这一侧起九紫阴遁；日本九星气学日盘同此）。
// 正好前后各 30 日时取前一个（离至日 30.5 日以上才置闰）。
// 两至相隔约 182.6 日，三个甲子只有 180 日，每年差两三日，约十一二年攒满一个甲子：这时相邻两个起遁甲子隔 240 日，
// 多出的 60 日为「闰」，前遁延 30 日、后遁提前 30 日，在中间的甲午换遁——阳转阴甲午起三碧、阴转阳甲午起七赤，
// 换遁那天与前一日同星（正常换遁同理：阳遁末日九紫、阴遁首日九紫；阴遁末日一白、阳遁首日一白），其余每日 ±1 不断档。
// 民用日按当日 0 时（节气日期取 lunar-javascript 的北京时间日期）。
function gzIndex(gz) { return GANZHI_60.indexOf(gz); }
function solarOf(y, m, d) { return Solar.fromYmd(y, m, d); }
function dayNum(solar) { return Math.floor(solar.getJulianDay() + 0.5); }
// 取某年冬至/夏至 Solar，归一到当日 0 时（节气原 Solar 含时刻，会令日差非整）。
// 注意 getJieQiTable 以 solarOf(year,6,1) 所在农历年为准：「冬至」= year-1 年 12 月那个，「夏至」= year 年 6 月那个。
function jieqiSolar(year, name) {
	const t = solarOf(year, 6, 1).getLunar().getJieQiTable();
	const s = t[name];
	return s ? Solar.fromYmd(s.getYear(), s.getMonth(), s.getDay()) : null;
}
const SOLSTICE_CACHE = new Map();
// 公历 year 年的两个至日（6 月夏至、12 月冬至）及各自最近的甲子日序。
function solsticesOfYear(year) {
	if (SOLSTICE_CACHE.has(year)) { return SOLSTICE_CACHE.get(year); }
	const out = [];
	const pick = (solar, yang)=>{
		if (!solar) { return; }
		const n = dayNum(solar);
		const g = gzIndex(solar.getLunar().getDayInGanZhi());
		if (g < 0) { return; }
		const before = n - g;                  // 至日当日或之前的甲子
		const after = before + 60;
		const jiazi = (n - before) <= (after - n) ? before : after;   // 等距（各 30 日）取前一个
		out.push({ yang, solstice: n, jiazi });
	};
	pick(jieqiSolar(year, '夏至'), false);
	pick(jieqiSolar(year + 1, '冬至'), true);
	if (SOLSTICE_CACHE.size >= 512) { SOLSTICE_CACHE.clear(); }   // 有限淘汰:翻很多年份时不无限长
	SOLSTICE_CACHE.set(year, out);
	return out;
}
// 目标日所在的遁：返回 { yang, start(换遁日序), startStar, leapHead, jiazi(本遁上元甲子日序) }。
function dunOf(tDay, y) {
	const list = [];
	for (let yr = y - 2; yr <= y + 1; yr++) { solsticesOfYear(yr).forEach((x)=>list.push(x)); }
	list.sort((a, b)=>a.jiazi - b.jiazi);
	const duns = [];
	for (let i = 1; i < list.length; i++) {
		const cur = list[i];
		const gap = cur.jiazi - list[i - 1].jiazi;
		if (gap === 240) {
			duns.push({ yang: cur.yang, start: cur.jiazi - 30, startStar: cur.yang ? 7 : 3, leapHead: true, jiazi: cur.jiazi });
		} else {
			duns.push({ yang: cur.yang, start: cur.jiazi, startStar: cur.yang ? 1 : 9, leapHead: false, jiazi: cur.jiazi });
		}
	}
	const past = duns.filter((d)=>d.start <= tDay);
	return past.length ? past[past.length - 1] : null;
}
const YUAN_NAME = ['上元', '中元', '下元'];
export function dayCenter(y, m, d) {
	const target = solarOf(y, m, d);
	const tDay = dayNum(target);
	const dun = dunOf(tDay, y);
	if (!dun) { return null; }
	const { yang } = dun;
	const offset = tDay - dun.start;
	let c = yang ? (dun.startStar - 1 + offset) : (dun.startStar - 1 - offset);
	c = ((c % 9) + 9) % 9 + 1;
	// 元：上元甲子起每 60 日一元；闰头（甲午起的 30 日）与闰尾（下元满后延的 30 日）记「闰」。
	const sinceJiazi = tDay - dun.jiazi;
	const leap = sinceJiazi < 0 || sinceJiazi >= 180;
	const yuan = leap ? null : Math.floor(sinceJiazi / 60);
	return {
		center: c, yang, yuan, yuanName: leap ? '闰' : YUAN_NAME[yuan], leap,
		dunStart: tDay === dun.start,
		dayGanZhi: target.getLunar().getDayInGanZhi(),
	};
}

// ── 时紫白（8.1.4）：日支三元 + 冬夏至顺逆，子时起入中，逐时推。──
const HOUR_YANG_START = { 0: 1, 1: 4, 2: 7 };   // 子午卯酉/辰戌丑未/寅申巳亥 日 阳遁子时起一白/四绿/七赤
const HOUR_YIN_START = { 0: 9, 1: 6, 2: 3 };
function dayZhiGroup(dayZhi) {
	if ('子午卯酉'.indexOf(dayZhi) >= 0) { return 0; }
	if ('辰戌丑未'.indexOf(dayZhi) >= 0) { return 1; }
	return 2;
}
// 时家紫白的顺逆看至日本身(时家歌诀「冬后顺排夏后逆」):冬至到夏至前顺,夏至到冬至前逆。
// 不跟日家的换遁甲子走 —— 日遁按离至日最近的甲子换,前后可差到 30 日,时盘不随之提前或推后。
function hourYang(y, m, d) {
	const tDay = dayNum(solarOf(y, m, d));
	const list = [];
	for (let yr = y - 1; yr <= y; yr++) { solsticesOfYear(yr).forEach((x)=>list.push(x)); }
	const past = list.filter((x)=>x.solstice <= tDay).sort((a, b)=>a.solstice - b.solstice);
	return past.length ? past[past.length - 1].yang : null;
}

export function hourCenter(y, m, d, hour) {
	const dc = dayCenter(y, m, d);
	if (!dc) { return null; }
	const yang = hourYang(y, m, d);
	if (yang === null) { return null; }
	const dayZhi = dc.dayGanZhi.slice(-1);
	const grp = dayZhiGroup(dayZhi);
	const shiZhiIdx = Math.floor(((Number(hour) || 0) + 1) / 2) % 12;   // 子=0
	const start = yang ? HOUR_YANG_START[grp] : HOUR_YIN_START[grp];
	let c = yang ? (start - 1 + shiZhiIdx) : (start - 1 - shiZhiIdx);
	c = ((c % 9) + 9) % 9 + 1;
	return { center: c, yang, shiZhi: DIZHI[shiZhiIdx] };
}

// ── 紫白诀名句（8.9，断验字典）：两星相会引动。──
export const ZIBAI_JUE = [
	{ when: [1, 2], text: '一白二黑交临，损主重病' },
	{ when: [3, 7], text: '三碧七赤叠至，被劫盗，更见官灾' },
	{ when: [4, 8], text: '八会四而小口殒生（四绿文昌，然八四会主伤小口）' },
	{ when: [7, 9], text: '七九合辙，常招回禄之灾' },
	{ when: [2, 5], text: '二五交加，罹死亡并生疾病' },
	{ when: [6, 7], text: '六七交剑，争斗官非' },
	{ when: [9, 5], text: '五九相逢，火照五黄，暴病' },
];

function palacesOf(pan) {
	const out = [];
	for (let g = 1; g <= 9; g++) {
		const star = pan[g];
		out.push({ gong: g, name: GONG_NAME[g], gua: GONG_GUA[g], star, starName: ZIBAI_STAR[star], jx: ZIBAI_JX[star], meaning: NINE_STAR_MEANING[star] });
	}
	return out;
}

// 紫白排盘：年/月(/日/时)入中九宫。date {y,m,d,hour} 供日时。
export function zibai({ year, month, date } = {}) {
	const y = year || new Date().getFullYear();
	const yc = zibaiYearCenter(y);
	const yearPan = flyFromCenter(yc);
	let monthPan = null; let mc = null;
	if (month) { mc = monthCenter(y, month); monthPan = flyFromCenter(mc); }
	// 日/时紫白（给完整年月日）。
	let dayInfo = null; let dayPan = null; let hourInfo = null; let hourPan = null;
	if (date && date.m && date.d) {
		try {
			dayInfo = dayCenter(date.y || y, date.m, date.d);
			if (dayInfo) { dayPan = flyFromCenter(dayInfo.center); }
			if (dayInfo && date.hour != null) { hourInfo = hourCenter(date.y || y, date.m, date.d, date.hour); if (hourInfo) { hourPan = flyFromCenter(hourInfo.center); } }
		} catch (e) { dayInfo = null; }
	}
	return {
		available: true, year: y, month: month || null,
		yearCenter: yc, yearCenterStar: ZIBAI_STAR[yc],
		monthCenter: mc, monthCenterStar: mc ? ZIBAI_STAR[mc] : null,
		yearPalaces: palacesOf(yearPan),
		monthPalaces: monthPan ? palacesOf(monthPan) : null,
		dayInfo, dayPalaces: dayPan ? palacesOf(dayPan) : null,
		hourInfo, hourPalaces: hourPan ? palacesOf(hourPan) : null,
		jue: ZIBAI_JUE,
		note: '一六八九吉、二三五七凶、四绿文昌、五黄大凶;日紫白以离冬至/夏至最近的甲子换遁(阳一七四顺、阴九三六逆,遇闰甲午换遁),时紫白依日支三元与顺逆',
	};
}
