// 皇极轨策 · 元会运世历史层 —— 纯查表、纯函数。
//
// ⚠️ 与既有之「皇极经世」子tab（元会运世历史盘，走后端）不重叠 —— 彼为同级兄弟，此不碰之。
//
// 值年卦之构造（古籍明载其规则，非任意之表）：
//   六十四卦圆图抽去乾坤坎离四正卦，刚好六十卦；一个花甲又正好六十年 →
//   以主管六十年之世卦为该花甲首年之年卦，按圆图顺时针挨次而下。
//   排年卦时遇四正卦则跳过、不作值年卦。
//   已自证：此六十卦与仓内六十四卦表去四正者，集合恰等（无重无漏）。
import { SHIER_BIGUA, YUAN_HUI_YUN_SHI } from './guiceConst.js';

/** 值年卦序：自世卦鼎起，按圆图顺时针历六十卦而周（去四正） */
export const ZHINIAN_START = 1984;
export const ZHINIAN_SEQ = [
	'鼎', '恒', '巽', '井', '蛊', '升', '讼', '困', '未济', '解',
	'涣', '蒙', '师', '遁', '咸', '旅', '小过', '渐', '蹇', '艮',
	'谦', '否', '萃', '晋', '豫', '观', '比', '剥', '复', '颐',
	'屯', '益', '震', '噬嗑', '随', '无妄', '明夷', '贲', '既济', '家人',
	'丰', '革', '同人', '临', '损', '节', '中孚', '归妹', '睽', '兑',
	'履', '泰', '大畜', '需', '小畜', '大壮', '大有', '夬', '姤', '大过',
];
export const SI_ZHENG_GUA = ['乾', '坤', '坎', '离'];

/** 当下之运世层级（会 → 正运 → 运卦 → 世卦 → 旬卦） */
export const YUN_SHI_CENGJI = [
	{ ceng: '会', gua: '午会', xia: ['姤', '大过', '鼎', '恒', '巽'], note: '午会自公元前 2217 年始' },
	{ ceng: '正运', gua: '大过' },
	{ ceng: '运卦', gua: '姤', from: 1744, to: 2103 },
	{ ceng: '世卦', gua: '鼎', from: 1984, to: 2043 },
	{ ceng: '旬卦', gua: '蛊', from: 2004, to: 2063 },
];

/** 值年卦：以年求之（周而复始） */
export function zhiNianGua(year) {
	// 🔴 先拒非数：Number(null)/Number('')/Number(false) 皆得 0 而 isInteger(0) 为真 →
	//    不先拒则 null 会被算成公元 0 年而误出年卦（实测误出「大有」）。
	if (year === null || year === undefined || year === '' || typeof year === 'boolean') return null;
	const y = Math.trunc(Number(year));
	if (!Number.isInteger(y)) return null;
	const i = ((y - ZHINIAN_START) % 60 + 60) % 60;
	return {
		year: y, gua: ZHINIAN_SEQ[i], index: i,
		huajia: { start: ZHINIAN_START + Math.floor((y - ZHINIAN_START) / 60) * 60 },
		shiGua: YUN_SHI_CENGJI.find((c) => c.ceng === '世卦' && y >= c.from && y <= c.to) || null,
	};
}

/** 一花甲六十年之年卦表 */
export function zhiNianTable(fromYear = ZHINIAN_START) {
	const base = ZHINIAN_START + Math.floor((fromYear - ZHINIAN_START) / 60) * 60;
	return ZHINIAN_SEQ.map((gua, i) => ({ year: base + i, gua }));
}

/** 十二辟卦（消息卦）：以月支求之 */
export function biGuaOf(monthZhi) {
	return SHIER_BIGUA.find((x) => x.zhi === monthZhi) || null;
}
export function biGuaTable() { return SHIER_BIGUA; }

/** 元会运世：1元=12会=360运=4320世=129600年 */
export function yuanHuiYunShi() { return { ...YUAN_HUI_YUN_SHI }; }

/** 历史层之全 */
export function lishi({ year, monthZhi }) {
	return {
		zhiNian: year ? zhiNianGua(year) : null,
		biGua: monthZhi ? biGuaOf(monthZhi) : null,
		cengji: YUN_SHI_CENGJI,
		yhys: YUAN_HUI_YUN_SHI,
	};
}

export default { lishi, zhiNianGua, zhiNianTable, biGuaOf, biGuaTable, ZHINIAN_SEQ };
