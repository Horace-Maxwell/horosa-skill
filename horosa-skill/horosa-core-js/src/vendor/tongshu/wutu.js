// tongshu/wutu.js — 天元乌兔择日法引擎（纯前端）。
// 玉函天星诀九星飞星起日：
//   1. 月朔（农历初一）干支；朔前最近卯日定阴阳（甲己丁壬戊癸阳顺／乙庚丙辛阴逆）。
//   2. 截法图：朔前卯日置子位，按其阴阳一日一支数至月朔 → 月朔截法地支 → 九宫（月首宫）。
//   3. 排山图：月朔置于该宫，按月朔日阴阳一日一宫（宫号±1）数去 → 每日九星。
// 日月木金水为吉、土孛火罗计为凶；太阳值日上吉、太阴值日次吉。
// 源例「癸亥七月」有异文（月朔误作戊戌实为己巳、太阴廿三实为廿二），本引擎按自洽算法+实历勘正。
import { Solar } from 'lunar-javascript';

const DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const YANG_GAN = new Set(['甲', '己', '丁', '壬', '戊', '癸']);   // 阳顺；余（乙庚丙辛）阴逆
// 截法图（月首图）：地支 → 九宫。
const JIEFA_ZHI_TO_GONG = { 子: 1, 丑: 8, 寅: 8, 卯: 3, 辰: 4, 巳: 4, 午: 9, 未: 2, 申: 2, 酉: 7, 戌: 6, 亥: 6 };
// 排山图：九宫 → 九星。
export const PAISHAN_STAR = {
	1: { name: '水星', jx: 'good' }, 2: { name: '太阴', jx: 'good' }, 3: { name: '木星', jx: 'good' },
	4: { name: '计都', jx: 'bad' }, 5: { name: '土星', jx: 'bad' }, 6: { name: '罗喉', jx: 'bad' },
	7: { name: '金星', jx: 'good' }, 8: { name: '太阳', jx: 'good' }, 9: { name: '火星', jx: 'bad' },
};

function isYang(gan) { return YANG_GAN.has(gan); }
function dayDiff(a, b) {
	return Math.round((new Date(a.getYear(), a.getMonth() - 1, a.getDay()).getTime()
		- new Date(b.getYear(), b.getMonth() - 1, b.getDay()).getTime()) / 86400000);
}

// 给定 solar 日 → 该农历月月朔 solar（减去农历日-1）。
function monthShuo(solar) {
	const day = solar.getLunar().getDay();
	return solar.next(-(day - 1));
}
// 月朔前最近卯日（严格早于月朔，即不含月朔本身；最多回溯 12 日）。
function priorMaoDay(shuo) {
	let p = shuo.next(-1);
	for (let k = 0; k < 12; k++) {
		if (p.getLunar().getDayInGanZhi()[1] === '卯') { return p; }
		p = p.next(-1);
	}
	return null;
}

// 计算某 solar 日的乌兔九星值日。
export function wutuForDate({ y, m, d }) {
	const solar = Solar.fromYmd(y, m, d);
	const lunar = solar.getLunar();
	const dayInMonth = lunar.getDay();               // 农历日（1..）
	const shuo = monthShuo(solar);
	const shuoGZ = shuo.getLunar().getDayInGanZhi();
	const mao = priorMaoDay(shuo);
	if (!mao) { return null; }
	const maoGZ = mao.getLunar().getDayInGanZhi();

	// 截法：朔前卯日阴阳定顺逆，从子起数至月朔。
	const jiefaDir = isYang(maoGZ[0]) ? 1 : -1;
	const diff = dayDiff(shuo, mao);                 // 月朔 - 朔前卯日（日数）
	const jiefaZhiIdx = ((0 + jiefaDir * diff) % 12 + 12) % 12;   // 子=0
	const jiefaZhi = DIZHI[jiefaZhiIdx];
	const seedGong = JIEFA_ZHI_TO_GONG[jiefaZhi];    // 月朔月首宫

	// 排山：月朔日阴阳定顺逆，从 seedGong 起，一日一宫。
	const paishanDir = isYang(shuoGZ[0]) ? 1 : -1;
	const k = dayInMonth - 1;                        // 距月朔天数
	const gong = ((seedGong - 1 + paishanDir * k) % 9 + 9) % 9 + 1;
	const star = PAISHAN_STAR[gong];

	return {
		y, m, d,
		dayGZ: lunar.getDayInGanZhi(),
		dayInMonth,
		shuoGZ, maoGZ,
		jiefaZhi, seedGong,
		gong,
		star: star.name,
		jx: star.jx,
		isSun: star.name === '太阳',
		isMoon: star.name === '太阴',
	};
}

// 列某农历月（含 solar 日的月）逐日乌兔值日 + 太阳/太阴日汇总。
export function wutuMonth({ y, m, d }) {
	const solar = Solar.fromYmd(y, m, d);
	const shuo = monthShuo(solar);
	const rows = [];
	let cur = shuo;
	// 一农历月 29~30 日：数到下个初一止。
	for (let i = 0; i < 30; i++) {
		const l = cur.getLunar();
		if (i > 0 && l.getDay() === 1) { break; }
		const r = wutuForDate({ y: cur.getYear(), m: cur.getMonth(), d: cur.getDay() });
		if (!r) { cur = cur.next(1); continue; }   // 防御：wutuForDate 理论恒非 null（12 连续日必含卯日），仍收口
		rows.push({ dayInMonth: l.getDay(), dayGZ: l.getDayInGanZhi(), star: r.star, jx: r.jx, isSun: r.isSun, isMoon: r.isMoon, ymd: cur.toYmd() });
		cur = cur.next(1);
	}
	return {
		shuoGZ: shuo.getLunar().getDayInGanZhi(),
		rows,
		sunDays: rows.filter((x)=> x.isSun),
		moonDays: rows.filter((x)=> x.isMoon),
	};
}

export default wutuForDate;
