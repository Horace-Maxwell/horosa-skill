// tongshu/qimenDieShu.js — 奇门遁甲择日·裴晋公（唐）叠数法引擎（纯前端）。
// 叠数 = 天干配数[日干] + 地支配数[日支] + 地支配数[时支]，值域 13~27，查吉凶表。
// 只取出行当日干支与时辰地支（古法）；例题 9+9+6 笔误作 23，实为 24=吉，表采信 24。
import { buildHuangliDay } from '../calendar/huangliDay.js';
import { QIMEN_GAN_NUM, QIMEN_ZHI_NUM, QIMEN_DIESHU_TABLE } from './qimenData.js';

const HOUR_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const HOUR_RANGE = {
	子: '23-01', 丑: '01-03', 寅: '03-05', 卯: '05-07', 辰: '07-09', 巳: '09-11',
	午: '11-13', 未: '13-15', 申: '15-17', 酉: '17-19', 戌: '19-21', 亥: '21-23',
};

export function dieshuOf(dayGan, dayZhi, hourZhi) {
	const g = QIMEN_GAN_NUM[dayGan] || 0;
	const dz = QIMEN_ZHI_NUM[dayZhi] || 0;
	const hz = QIMEN_ZHI_NUM[hourZhi] || 0;
	const sum = g + dz + hz;
	const e = QIMEN_DIESHU_TABLE[sum] || {};
	return { sum, parts: { gan: g, dayZhi: dz, hourZhi: hz }, jx: e.jx || '', shi: e.shi || '', jie: e.jie || '', note: e.note || '' };
}

export function qimenDieShuDay({ y, m, d }) {
	const day = buildHuangliDay(y, m, d);
	const dayGZ = day.lunar.dayGZ;
	const dayGan = dayGZ[0];
	const dayZhi = dayGZ[1];
	const rows = HOUR_ZHI.map((hz)=>{
		const r = dieshuOf(dayGan, dayZhi, hz);
		return { hourZhi: hz, range: HOUR_RANGE[hz], sum: r.sum, jx: r.jx, shi: r.shi, jie: r.jie };
	});
	const best = rows.filter((r)=> r.jx === '吉').map((r)=> `${r.hourZhi}时(${r.sum})`);
	return { y, m, d, dayGZ, dayGan, dayZhi, rows, bestHours: best };
}

export default qimenDieShuDay;
