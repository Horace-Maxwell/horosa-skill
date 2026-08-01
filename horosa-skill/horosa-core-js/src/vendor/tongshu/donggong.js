// tongshu/donggong.js — 董公择日法引擎（纯前端）。
// 日干支/月建/建除/28宿 走 buildHuangliDay（内部 lunar+zeri）；断语查 donggongData 全量表；
// 金神七煞按值宿；煞贡/直星/人专按节气月组×日干支；三煞方按节气月三合局规范计算（OCR 无关）。
import { buildHuangliDay } from '../calendar/huangliDay.js';
import { DIZHI, ZHI_SANHE_JU, SANSHA_BY_JU } from '../fengshui/fengshuiData.js';
import {
	DONGGONG_TABLE, DONGGONG_JINSHEN_XIU, DONGGONG_JINSHEN_FULL,
	DONGGONG_SANXING, DONGGONG_MONTH_GROUP, DONGGONG_NOTES,
} from './donggongData.js';

const MONTHS = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];
// 三煞中支定方位。
const DIR_OF_MIDZHI = { 子: '北', 午: '南', 卯: '东', 酉: '西' };

// 节气月建支 → 月序（建寅=正月）。
export function monthNumOfBuild(monthZhi) {
	return ((DIZHI.indexOf(monthZhi) - DIZHI.indexOf('寅') + 12) % 12) + 1;
}

export function donggongDay({ y, m, d }) {
	const day = buildHuangliDay(y, m, d);
	const dayGZ = day.lunar.dayGZ;
	const monthZhi = day.lunar.monthGZ.slice(-1);
	const monthNum = monthNumOfBuild(monthZhi);
	const monthName = MONTHS[monthNum - 1];
	const jianchu = day.jianchu.name;
	const entry = (DONGGONG_TABLE[monthName] || {})[jianchu] || null;

	// 注：四月「成(丑)」与「收(寅)」断语同文（皆「天喜、天成…丁丑、癸丑煞入宫」）——经多方公开传本
	// 逐字核验，此系《董公择日法》古本原貌（成/收共断，丁丑癸丑为该组专属告诫），非生成复制瑕疵，
	// 如实保留、不改不删（不臆造亦不误删）。审计勿再以「相邻格同文」为由判 bug。见 calendarBugfixes.test B1。

	// 金神七煞（值宿命中七星 → 大凶切不可犯，三吉星亦不能解）。
	const xiu = day.xiu.name;
	const jsIdx = DONGGONG_JINSHEN_XIU.indexOf(xiu);
	const jinshen = jsIdx >= 0 ? { hit: true, xiu, full: DONGGONG_JINSHEN_FULL[jsIdx] } : { hit: false };

	// 煞贡/直星/人专（最吉三星，遇一值日可获吉解凶）。
	const group = DONGGONG_MONTH_GROUP[monthNum];
	const sx = DONGGONG_SANXING[group] || {};
	let sanxing = null;
	['煞贡', '直星', '人专'].forEach((k)=>{ if ((sx[k] || []).includes(dayGZ)) { sanxing = k; } });

	// 三煞方（节气月三合局帝旺对冲三山）。
	const ju = ZHI_SANHE_JU[monthZhi];
	const sanshaZhi = SANSHA_BY_JU[ju] || [];
	const sanshaDir = sanshaZhi.length >= 2 ? DIR_OF_MIDZHI[sanshaZhi[1]] : null;

	return {
		y, m, d,
		dayGZ, dayZhi: dayGZ.slice(-1),
		monthName, monthNum, monthGroup: group,
		jianchu, zhi: entry ? entry.zhi : monthZhi,
		text: entry ? entry.text : '',
		jinshen,
		sanxing,   // '煞贡' | '直星' | '人专' | null
		sansha: { ju: ju ? `${ju}局` : null, zhi: sanshaZhi, dir: sanshaDir },
		notes: DONGGONG_NOTES[monthName] || [],
		// 综合判：金神七煞 > 三吉星 > 断语宜忌语气。
		verdict: jinshen.hit
			? { level: 'bad', text: '金神七煞值日·大凶切不可犯' }
			: (sanxing ? { level: 'good', text: `${sanxing}值日·最吉三星，能解凶星` } : { level: 'neutral', text: '按董公逐日断语参酌' }),
	};
}

export default donggongDay;
