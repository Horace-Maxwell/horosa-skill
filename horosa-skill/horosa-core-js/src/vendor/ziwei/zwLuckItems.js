// 从上游 ZWLuckPanel.js 精确抽出的运限项构建闭包（该文件其余部分是 React 组件，整份 vendor
// 会把 JSX 带进来、Node 直接解析失败 —— 本轮踩到）。函数体与常量逐字未改。
import { julianDayIndex } from '../utils/julianDayIndex.js';
import { parseYearFromDateStr } from '../bazi/dateStrSafe.js';
import { Lunar, LunarMonth } from 'lunar-javascript';
import * as ZWConst from '../bazi/ZWConst.js';
import * as ZiWeiHelper from './ZiWeiHelper.js';

const DAY_ANCHOR_IDX = 28;

const DAY_ANCHOR_JDI = julianDayIndex(2026, 5, 18);

const DIZI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];

const LUNAR_MONTH = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月'];

const SHICHEN = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

const XIAOXIAN_START = {
	'寅': '辰', '午': '辰', '戌': '辰', '申': '戌', '子': '戌', '辰': '戌',
	'亥': '丑', '卯': '丑', '未': '丑', '巳': '未', '酉': '未', '丑': '未',
};

// houses[] 是连续地支但起始宫不固定 → 必须按地支搜数组下标，不可用 DIZI 位置

const ZI_HOUR_START = { '甲': '甲', '己': '甲', '乙': '丙', '庚': '丙', '丙': '戊', '辛': '戊', '丁': '庚', '壬': '庚', '戊': '壬', '癸': '壬' };

function buildDaxianItems(chart) {
	if (!chart || !chart.houses) return [];
	const arr = [];
	for (let i = 0; i < 12; i++) {
		const d = chart.houses[i] && chart.houses[i].direction;
		if (d) arr.push({ i, start: d[0], end: d[1], ganzi: chart.houses[i].ganzi });
	}
	arr.sort((a, b) => a.start - b.start);
	return arr.map((x) => ({
		id: `dx-${x.i}`, level: 'daxian', mingIndex: x.i, ganzi: x.ganzi,
		gan: x.ganzi.charAt(0), zhi: x.ganzi.charAt(1), start: x.start, end: x.end,
		top: `${x.start}~${x.end}`, sub: `${x.ganzi}限`,
	}));
}

function buildLiunianItems(chart, daxian) {
	if (!chart || !daxian) return [];
	const birthY = birthYearOf(chart);
	const startYear = birthY + daxian.start - 1;
	const out = [];
	for (let k = 0; k < (daxian.end - daxian.start + 1); k++) {
		const year = startYear + k;
		const gz = yearGanzi(year);
		if (!gz || gz.length < 2) continue;
		const zhi = gz.charAt(1);
		out.push({
			id: `ln-${year}`, level: 'liunian', year, age: daxian.start + k, ganzi: gz,
			gan: gz.charAt(0), zhi, mingIndex: houseIdxByBranch(chart, zhi),
			top: `${year}`, sub: `${gz}`,
		});
	}
	return out;
}

function buildXiaoxianItems(chart, daxian) {
	if (!chart || !chart.houses || !chart.yearZi || !daxian) return [];
	const startZhi = XIAOXIAN_START[chart.yearZi];
	if (!startZhi) return [];
	const startIdx = houseIdxByBranch(chart, startZhi);
	if (startIdx < 0) return [];
	const male = chart.gender === 'Male' || chart.gender === 1 || chart.gender === '1';
	// P1-B 小限顺逆：'0'=男顺女逆(现状默认，零回归) / '1'=阳男阴女顺、阴男阳女逆(中州)。
	let xxMode = '0';
	try { xxMode = localStorage.getItem('ziweiXiaoxianYinyang') || '0'; } catch (e) { xxMode = '0'; }
	let clockwise;
	if (xxMode === '1') {
		const yang = chart.yearPolar === 'Positive';
		clockwise = (yang && male) || (!yang && !male);
	} else {
		clockwise = male;
	}
	const birthY = birthYearOf(chart);
	const out = [];
	for (let age = daxian.start; age <= daxian.end; age++) {
		const step = age - 1;
		const idx = clockwise ? (startIdx + step) % 12 : ((startIdx - step) % 12 + 12) % 12;
		const house = chart.houses[idx];
		if (!house) continue;
		const ganzi = house.ganzi;
		out.push({
			id: `xx-${age}`, level: 'xiaoxian', age, year: birthY + age - 1, mingIndex: idx,
			ganzi, gan: ganzi.charAt(0), zhi: ganzi.charAt(1),
			top: `${age}岁`, sub: `${ganzi}`,
		});
	}
	return out;
}

function buildLiuyueItems(chart, year) {
	if (!chart || !Number.isFinite(year)) return [];
	const gz = yearGanzi(year);
	const yearGan = gz.charAt(0);
	const yearZhi = gz.charAt(1);
	const doujunZhi = ZiWeiHelper.getDouJun(chart.zidou, yearZhi);
	const doujunIdx = houseIdxByBranch(chart, doujunZhi);
	const out = [];
	for (let m = 0; m < 12; m++) {
		const gan = monthGan(yearGan, m);
		const zhi = DIZI[(2 + m) % 12]; // 正月建寅
		const mingIndex = doujunIdx < 0 ? -1 : (doujunIdx + m) % 12;
		out.push({
			id: `ly-${year}-${m}`, level: 'liuyue', month: m + 1, year,
			ganzi: gan + zhi, gan, zhi, mingIndex,
			top: LUNAR_MONTH[m], sub: `${gan}${zhi}`,
		});
	}
	return out;
}

function buildLiuriItems(chart, year, liuyue) {
	if (!chart || !liuyue) return [];
	let days = 30;
	let firstSolar = null;
	try {
		const lm = LunarMonth.fromYm(year, liuyue.month);
		if (lm && typeof lm.getDayCount === 'function') days = lm.getDayCount();
	} catch (e) { days = 30; }
	try {
		const s = Lunar.fromYmd(year, liuyue.month, 1).getSolar();
		// AD 1-99 绕开 Date 构造器 0-99→1900+ 映射(流日轴日干支曾整体平移 1900 年)
		firstSolar = new Date(0);
		firstSolar.setFullYear(s.getYear(), s.getMonth() - 1, s.getDay());
		firstSolar.setHours(0, 0, 0, 0);
	} catch (e) { firstSolar = null; }
	const out = [];
	for (let d = 1; d <= days; d++) {
		let ganzi = '';
		if (firstSolar) {
			const dt = new Date(0);
			dt.setFullYear(firstSolar.getFullYear(), firstSolar.getMonth(), firstSolar.getDate() + (d - 1));
			dt.setHours(0, 0, 0, 0);
			ganzi = dayGanziByDate(dt);
		}
		const zhi = ganzi ? ganzi.charAt(1) : '';
		const mingIndex = (liuyue.mingIndex + (d - 1)) % 12;
		out.push({
			id: `lr-${year}-${liuyue.month}-${d}`, level: 'liuri', day: d, year,
			ganzi, gan: ganzi ? ganzi.charAt(0) : '', zhi, mingIndex,
			top: `${d}`, sub: ganzi || `${d}日`,
		});
	}
	return out;
}

function buildLiushiItems(chart, liuri) {
	if (!chart || !liuri || !liuri.gan) return [];
	const out = [];
	for (let h = 0; h < 12; h++) {
		const gan = hourGan(liuri.gan, h);
		const zhi = DIZI[h];
		const mingIndex = (liuri.mingIndex + h) % 12;
		out.push({
			id: `ls-${liuri.day}-${h}`, level: 'liushi', hourIdx: h,
			ganzi: gan + zhi, gan, zhi, mingIndex,
			top: `${SHICHEN[h]}时`, sub: `${gan}${zhi}`,
		});
	}
	return out;
}

function houseName(chart, idx, short) {
	if (!chart || !chart.houses || idx === undefined || idx === null || idx < 0) return '—';
	const h = chart.houses[idx];
	const name = h && h.name ? h.name : '—';
	return short ? name.replace(/[宫宮]$/, '') : name;
}

function houseIdxByBranch(chart, zhi) {
	if (!chart || !chart.houses || !zhi) return -1;
	return chart.houses.findIndex((h) => h && h.ganzi && h.ganzi.charAt(1) === zhi);
}

function birthYearOf(chart) {
	if (chart && chart.birth) {
		const y = parseYearFromDateStr(`${chart.birth}`);
		if (!Number.isNaN(y)) return y;
	}
	return 2000;
}

function yearGanzi(year) {
	if (!Number.isFinite(year)) return '';
	const gi = (((year - 4) % 10) + 10) % 10;
	const zi = (((year - 4) % 12) + 12) % 12;
	return GANS[gi] + DIZI[zi];
}

function monthGan(yearGan, monthIdx /*0=正月*/) {
	const start = ZWConst.WuHuDun ? ZWConst.WuHuDun[yearGan] : null;
	const si = GANS.indexOf(start);
	if (si < 0) return '';
	return GANS[(si + monthIdx) % 10];
}

function dayGanziByDate(date) {
	const jdi = julianDayIndex(date.getFullYear(), date.getMonth() + 1, date.getDate());
	const idx = (((jdi - DAY_ANCHOR_JDI + DAY_ANCHOR_IDX) % 60) + 60) % 60;
	return GANS[idx % 10] + DIZI[idx % 12];
}

function hourGan(dayGan, hourIdx /*0=子*/) {
	const si = GANS.indexOf(ZI_HOUR_START[dayGan]);
	if (si < 0) return '';
	return GANS[(si + hourIdx) % 10];
}

export { buildDaxianItems, buildLiunianItems, buildXiaoxianItems, buildLiuyueItems, buildLiuriItems, buildLiushiItems, houseName, houseIdxByBranch };
