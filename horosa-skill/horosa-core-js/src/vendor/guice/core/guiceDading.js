// 皇极轨策 · 大定起数 —— 纯函数、全整数。
//
// 起数之链（四步，逐步皆可见）：
//   ① 卦策数 = 上卦策 + 下卦策，单卦之策 = 120 + 先天数×6
//   ② 六十甲子天地立成定数：四柱各取一数而和之（两本并存，见 guiceJiaziShu）
//   ③ 四柱阴阳加策：以四柱支辰定老少 —— 子寅辰为老阳、未酉亥为老阴、午申戌为少阳、丑卯巳为少阴；
//      老胜加七百二十、少胜加三百六十、相等则从阳亦加七百二十
//   ④ 却将克岁数除之：以年干取数而减之（甲乙除十一、丙丁除三、戊己除十一、庚辛除四、壬癸除九）
//   所得之数除万不用，取千百十零，以九畴数配卦（七借巽、十借艮），空位隔位相借。
import { DADING_GUA_CE, YINYANG_CE, YINYANG_CE_JIA, KE_SUI_SHU } from './guiceConst.js';
import { LIUSHIJIAZI_DINGSHU } from './guiceJiaziShu.js';
import { splitYuanHuiYunShi, borrowEmptyDigits, digitToGua } from './guiceEngine.js';

const kindOfZhi = (z) => Object.keys(YINYANG_CE).find((k) => YINYANG_CE[k].indexOf(z) >= 0) || null;

/** ① 卦策数 */
export function guaCeShu(up, lo) {
	const a = DADING_GUA_CE[up]; const b = DADING_GUA_CE[lo];
	if (a === undefined || b === undefined) return null;
	return { up, lo, upCe: a, loCe: b, value: a + b };
}

/** ② 六十甲子天地立成定数：四柱各取一数而和之 */
export function jiaziDingShu(pillars, table = 'xinyifawei') {
	if (!Array.isArray(pillars) || pillars.length !== 4) return null;
	const T = (LIUSHIJIAZI_DINGSHU[table] || LIUSHIJIAZI_DINGSHU.xinyifawei).table;
	const items = pillars.map((gz) => ({ gz, num: T[gz] }));
	if (items.some((x) => x.num === undefined)) return null;
	return { table, items, value: items.reduce((s, x) => s + x.num, 0) };
}

/** ③ 四柱阴阳加策 */
export function yinYangJiaCe(pillars) {
	if (!Array.isArray(pillars) || pillars.length !== 4) return null;
	const items = pillars.map((gz) => ({ gz, zhi: gz[1], kind: kindOfZhi(gz[1]) }));
	if (items.some((x) => !x.kind)) return null;
	const lao = items.filter((x) => x.kind.startsWith('老')).length;
	const shao = items.filter((x) => x.kind.startsWith('少')).length;
	const sheng = lao > shao ? '老胜' : (shao > lao ? '少胜' : '相等');
	return {
		items, lao, shao, sheng, value: YINYANG_CE_JIA[sheng],
		note: sheng === '相等' ? '老少相等，从阳' : '',
	};
}

/** ④ 克岁数：以年干取之（克「岁」之数，故取年干） */
export function keSuiShu(yearGan) {
	const row = KE_SUI_SHU.find((r) => r.gan.indexOf(yearGan) >= 0);
	return row ? { yearGan, gua: row.gua, value: row.num } : null;
}

/**
 * 大定起数全链。
 * pillars = [年, 月, 日, 时] 之干支；up/lo = 本卦上下卦。
 */
export function calcDading({ pillars, up, lo, dadingTable = 'xinyifawei' }) {
	const ce = guaCeShu(up, lo);
	const ds = jiaziDingShu(pillars, dadingTable);
	const yy = yinYangJiaCe(pillars);
	const ks = pillars && pillars[0] ? keSuiShu(pillars[0][0]) : null;
	if (!ce || !ds || !yy || !ks) return null;
	const value = ce.value + ds.value + yy.value - ks.value;
	const parts = splitYuanHuiYunShi(value);
	const borrowed = borrowEmptyDigits(parts);
	const siwei = ['千', '百', '十', '零'].map((wei) => {
		const b = borrowed[wei];
		return { wei, ...b, ...(digitToGua(b.value, 'jiuchou') || {}) };
	});
	return {
		pillars, up, lo, value, parts, siwei,
		guaCe: ce, dingShu: ds, yinYang: yy, keSui: ks,
		steps: [
			{ label: '卦策数', detail: `${up} ${ce.upCe} + ${lo} ${ce.loCe}（单卦之策 = 120 + 先天数×6）`, value: ce.value },
			{ label: '六十甲子天地立成定数', detail: ds.items.map((x) => `${x.gz} ${x.num}`).join(' + '), value: ds.value },
			{ label: '四柱阴阳加策', detail: `${yy.items.map((x) => `${x.zhi}${x.kind}`).join('·')} → 老${yy.lao} 少${yy.shao} → ${yy.sheng}${yy.note ? `（${yy.note}）` : ''}`, value: `+${yy.value}` },
			{ label: '却将克岁数除之', detail: `年干 ${ks.yearGan} → 除 ${ks.gua.join('')} ${ks.value}`, value: `−${ks.value}` },
			{ label: '合', detail: `${ce.value} + ${ds.value} + ${yy.value} − ${ks.value}`, value },
			{ label: '九畴配卦', detail: `千${parts.qian} 百${parts.bai} 十${parts.shi} 零${parts.ling}（七借巽、十借艮；空位隔位相借）`, value: siwei.map((x) => x.gua).join('') },
		],
	};
}

export default { calcDading, guaCeShu, jiaziDingShu, yinYangJiaCe, keSuiShu };
