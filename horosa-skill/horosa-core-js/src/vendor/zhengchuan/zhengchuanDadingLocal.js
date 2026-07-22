// 神数正传 · 大定神数 —— 前端本地确定性引擎（零后端 / 零随机 / 全整数）。
//
// 大定数是条文类神数的底层钥匙：北派邵子一系的 6144 条文与南派铁板/铁算一系的
// 12000 条文，其运算皆以此为基。故本模块不是并列的第五支，而是流派间共用的底座。
//
// 核心：干支策数 = 太玄数(干) + 太玄数(支) + 纳音五行本数(水1 火2 木3 金4 土5)
//   两张表仓内既有且已与古籍数表逐字互证 → 直接复用，不复制常量：
//   · 太玄数 taixuanPeishu() ← tiebanFrameworkLocal（与古籍太玄配数表逐字相同）
//   · 纳音五行 nayinElement() ← canpingLocal
//   已对古籍算例逐步验证：五个直接策值 5/5；七位积 115 逐字命中；
//   死年链 795→13807→13752→余27→三因81→余9 六步全中；死月/时链 32→224→44→132→0 全中。
//
// 推命链（起推人生死数）：
//   死年：七位(四柱+大运+小运+岁君)策积 + 岁数×17 + 13012 − 55
//         → 45 除取余（整除即尽期）→ 不满45 则三因 → 12 除 → 见绝期
//   死月/日/时：生柱策 + 候选柱策 → 阳辰×7 / 阴辰×8
//         → 45 除取余 → 不满45 则三因 → 12 除 → 余 0 即尽
import { taixuanPeishu } from './tiebanFrameworkLocal.js';
import { nayinElement } from '../canping/canpingLocal.js';

const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

/** 五行本数配数表（古籍所载）：水1 火2 木3 金4 土5 */
export const WUXING_BEN = { 水: 1, 火: 2, 木: 3, 金: 4, 土: 5 };

/** 起推人生死数的三个虚加/虚除常数（古籍口诀所定） */
export const DADING_CONST = { perYear: 17, base: 13012, tianShu: 55, div1: 45, div2: 12, yangMul: 7, yinMul: 8 };

/** 干支策数 = 太玄数(干) + 太玄数(支) + 纳音五行本数 */
export function dadingCe(gz) {
	if (!gz || gz.length < 2) return null;
	const g = taixuanPeishu(gz[0]);
	const z = taixuanPeishu(gz[1]);
	const el = nayinElement(gz);
	const b = WUXING_BEN[el];
	if (g == null || z == null || b == null) return null;
	return { ce: g + z + b, gan: g, zhi: z, nayin: el, ben: b };
}

/** 阳辰＝地支序为偶数位（子寅辰午申戌）；阴辰＝丑卯巳未酉亥 */
export function isYangChen(gz) {
	return ZHI.indexOf(gz[1]) % 2 === 0;
}

function gzIndex(gz) {
	for (let i = 0; i < 60; i += 1) {
		if (GAN[i % 10] === gz[0] && ZHI[i % 12] === gz[1]) return i;
	}
	return -1;
}

function gzAt(i) {
	const n = ((i % 60) + 60) % 60;
	return GAN[n % 10] + ZHI[n % 12];
}

/** 五虎遁：年干 → 该年正月之月干；正月建寅 */
const WUHU = { 甲: '丙', 己: '丙', 乙: '戊', 庚: '戊', 丙: '庚', 辛: '庚', 丁: '壬', 壬: '壬', 戊: '甲', 癸: '甲' };
export function monthGzOf(yearGan, monthNo) {
	const startGan = WUHU[yearGan];
	const i = gzIndex(startGan + '寅');
	return gzAt(i + (monthNo - 1));
}

/** 五鼠遁：日干 → 该日子时之时干 */
const WUSHU = { 甲: '甲', 己: '甲', 乙: '丙', 庚: '丙', 丙: '戊', 辛: '戊', 丁: '庚', 壬: '庚', 戊: '壬', 癸: '壬' };
export function hourGzOf(dayGan, zhiIdx) {
	const i = gzIndex(WUSHU[dayGan] + '子');
	return gzAt(i + zhiIdx);
}

/**
 * 死年推算：给定岁数，走古籍口诀之链，产出每一步中间量。
 * 七位 = 年月日时四柱 + 大运 + 小运 + 岁君。
 */
export function dadingDeathYear({ pillars, dayun, xiaoyun, suijun, age }) {
	const seven = [...pillars, dayun, xiaoyun, suijun];
	const items = seven.map((gz) => ({ gz, ...dadingCe(gz) }));
	if (items.some((x) => x.ce == null)) return null;
	const sum = items.reduce((a, b) => a + b.ce, 0);
	const steps = [];
	steps.push({ label: '七位策积', detail: items.map((x) => `${x.gz}${x.ce}`).join('+'), value: sum });
	let v = sum + age * DADING_CONST.perYear;
	steps.push({ label: `每岁虚加${DADING_CONST.perYear}`, detail: `${sum}+${age}×${DADING_CONST.perYear}`, value: v });
	v += DADING_CONST.base;
	steps.push({ label: `再虚加${DADING_CONST.base}`, detail: `+${DADING_CONST.base}`, value: v });
	v -= DADING_CONST.tianShu;
	steps.push({ label: `除天数${DADING_CONST.tianShu}`, detail: `−${DADING_CONST.tianShu}`, value: v });
	const r45 = v % DADING_CONST.div1;
	steps.push({ label: `${DADING_CONST.div1} 除取余`, detail: `${v} mod ${DADING_CONST.div1}`, value: r45 });
	const exhausted = r45 === 0;                       // 「四十五除是尽期」：整除即尽
	const tripled = exhausted ? 0 : r45 * 3;
	if (!exhausted) steps.push({ label: '不满45 故三因', detail: `${r45}×3`, value: tripled });
	const r12 = exhausted ? 0 : tripled % DADING_CONST.div2;
	steps.push({ label: `${DADING_CONST.div2} 除取余（见绝期）`, detail: `${tripled} mod ${DADING_CONST.div2}`, value: r12 });
	return { items, sum, steps, r45, tripled, r12, exhausted };
}

/** 月/日/时 共用的二柱链：生柱策 + 候选柱策 → 阳辰×7 / 阴辰×8 → 45 除 → 三因 → 12 除 */
export function dadingPairChain(birthGz, candGz) {
	const a = dadingCe(birthGz);
	const b = dadingCe(candGz);
	if (!a || !b) return null;
	const sum = a.ce + b.ce;
	const yang = isYangChen(birthGz);
	const mul = yang ? DADING_CONST.yangMul : DADING_CONST.yinMul;
	const prod = sum * mul;
	const r45 = prod % DADING_CONST.div1;
	const tripled = r45 * 3;
	const r12 = tripled % DADING_CONST.div2;
	return {
		birth: { gz: birthGz, ...a }, cand: { gz: candGz, ...b },
		sum, yang, mul, prod, r45, tripled, r12,
		exhausted: r12 === 0,
		steps: [
			{ label: '二柱策和', detail: `${birthGz}${a.ce}+${candGz}${b.ce}`, value: sum },
			{ label: `${yang ? '阳辰' : '阴辰'}以${mul}乘`, detail: `${sum}×${mul}`, value: prod },
			{ label: '45 除取余', detail: `${prod} mod 45`, value: r45 },
			{ label: '三因', detail: `${r45}×3`, value: tripled },
			{ label: '12 除取余', detail: `${tripled} mod 12`, value: r12 },
		],
	};
}

/** 逐月扫描：自尽年正月起，至链尽而止（余 0 即此月尽）。 */
export function dadingDeathMonth(birthMonthGz, deathYearGan) {
	const scan = [];
	for (let m = 1; m <= 12; m += 1) {
		const gz = monthGzOf(deathYearGan, m);
		const c = dadingPairChain(birthMonthGz, gz);
		scan.push({ monthNo: m, gz, ...c });
		if (c.exhausted) return { hit: scan[scan.length - 1], scan };
	}
	return { hit: null, scan };
}

/** 逐时扫描：自尽日子时起，至链尽而止。 */
export function dadingDeathHour(birthHourGz, deathDayGan) {
	const scan = [];
	for (let i = 0; i < 12; i += 1) {
		const gz = hourGzOf(deathDayGan, i);
		const c = dadingPairChain(birthHourGz, gz);
		scan.push({ zhi: ZHI[i], gz, ...c });
		if (c.exhausted) return { hit: scan[scan.length - 1], scan };
	}
	return { hit: null, scan };
}

export default { dadingCe, dadingDeathYear, dadingPairChain, dadingDeathMonth, dadingDeathHour };
