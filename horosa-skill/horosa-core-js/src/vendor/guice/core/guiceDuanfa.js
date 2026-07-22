// 皇极轨策 · 断法 —— 纯函数、零副作用。
//
// 断之诸端：体用生克 / 体用四诀（轻重次序·真生真克·衰旺·动静）/ 卦气旺衰 /
//           四位五行生克 / 数全空缺 / 主算客算 / 诸卦反对性情。
import { Gua8 } from '../../gua/GuaConst.js';
import { WUXING_SHENG, WUXING_KE } from '../../gua/LiuYaoConst.js';
import {
	TIYONG_SHENGKE, TIYONG_QINGZHONG, GUA_QI_WANG, GUA_QI_SHUAI, SIJI_ZHI,
	XIANTIAN_NUM, SIWEI_XIANG,
} from './guiceConst.js';
import { tiHuYongHu, guaBianAll } from './guiceGuaBian.js';

const ELEM_OF = Gua8.reduce((m, g) => { m[g.name] = g.elem; return m; }, {});
const sheng = (a, b) => WUXING_SHENG[a] === b;
const ke = (a, b) => WUXING_KE[a] === b;

/** 体用生克：用生体助力／体克用费力可成／比和吉／体生用耗损／用克体大凶 */
export function tiYongShengKe(tiGua, yongGua) {
	const t = ELEM_OF[tiGua]; const y = ELEM_OF[yongGua];
	if (!t || !y) return null;
	let key;
	if (t === y) key = '比和';
	else if (sheng(y, t)) key = '用生体';
	else if (ke(t, y)) key = '体克用';
	else if (sheng(t, y)) key = '体生用';
	else if (ke(y, t)) key = '用克体';
	else key = '比和';
	return { tiGua, yongGua, tiElem: t, yongElem: y, key, ...TIYONG_SHENGKE[key] };
}

/** 卦气旺衰：震巽木旺于春／离火旺于夏／乾兑金旺于秋／坎水旺于冬／坤艮旺于辰戌丑未月 */
export function guaQi(gua, monthZhi) {
	if (!ELEM_OF[gua] || !monthZhi) return null;
	const jie = SIJI_ZHI.indexOf(monthZhi) >= 0 ? '四季'
		: (['寅', '卯'].indexOf(monthZhi) >= 0 ? '春'
			: (['巳', '午'].indexOf(monthZhi) >= 0 ? '夏'
				: (['申', '酉'].indexOf(monthZhi) >= 0 ? '秋'
					: (['亥', '子'].indexOf(monthZhi) >= 0 ? '冬' : null))));
	if (!jie) return { gua, monthZhi, qi: '平', jie: null };
	const wang = (GUA_QI_WANG[jie] || []).indexOf(gua) >= 0;
	const shuai = (GUA_QI_SHUAI[jie] || []).indexOf(gua) >= 0;
	return { gua, monthZhi, jie, qi: wang ? '旺' : (shuai ? '衰' : '平') };
}

/**
 * 体用四诀之「轻重次序」：用最紧 > 互次之 > 变又次之。
 * 用 = 即应；互 = 中间之应；变 = 终应。
 * 变卦克体则未后不吉；变生体或比和则临终吉利。
 */
export function qingZhongCiXu(up, lo, dongYao) {
	const all = guaBianAll(up, lo, dongYao);
	const hu = tiHuYongHu(all ? [...Gua8.find((g) => g.name === lo).value, ...Gua8.find((g) => g.name === up).value] : null, dongYao);
	if (!all || !hu) return null;
	const ti = hu.tiGua;
	const bianTiGua = hu.tiZai === 'up' ? all.bian.up : all.bian.lo;
	const rows = [
		{ ...TIYONG_QINGZHONG[0], gua: hu.yongGua, ...tiYongShengKe(ti, hu.yongGua) },
		{ ...TIYONG_QINGZHONG[1], gua: hu.yongHu, ...tiYongShengKe(ti, hu.yongHu) },
		{ ...TIYONG_QINGZHONG[2], gua: bianTiGua, ...tiYongShengKe(ti, bianTiGua) },
	];
	const bian = rows[2];
	return {
		tiGua: ti, rows,
		zhongYing: bian.key === '用克体' ? '变卦克体 —— 未后不吉'
			: ((bian.key === '用生体' || bian.key === '比和') ? '变生体或比和 —— 临终吉利' : '变卦无克无生 —— 终无大碍'),
	};
}

/** 真生真克（须分真火/形色）—— 古籍所举之例，列以备参，不作自动判 */
export const ZHEN_SHENG_ZHEN_KE = [
	{ ju: '炉灶之真火克金；红紫之色不克', yi: '色属火而非真火' },
	{ ju: '土 vs 瓦器', yi: '瓦器已成，非土之生' },
	{ ju: '柴薪 vs 未伐之树木', yi: '柴薪可生火，未伐之木不可' },
];
export const ZHEN_SHENG_ZHEN_KE_ZE = '能克则不吉；不能克则不顺而已';

/** 动静：体互为静、用变为动；外应中方应/天时/地理为静，人事/器物为动 */
export const DONG_JING_ZE = {
	jing: ['体卦', '互卦', '中方应', '天时', '地理'],
	dong: ['用卦', '变卦', '人事', '器物'],
	yingQi: { 坐: '应迟', 行: '应速', 立: '半迟半速' },
	chengGua: '起卦须一动一静方成卦',
};

/** 四位五行生克：千百十零之卦，两两相较 */
export function siweiShengKe(siwei) {
	if (!Array.isArray(siwei) || siwei.length !== 4) return null;
	const rows = [];
	for (let i = 0; i < 4; i += 1) {
		for (let j = i + 1; j < 4; j += 1) {
			const a = siwei[i]; const b = siwei[j];
			if (!a.gua || !b.gua) continue;
			const ea = ELEM_OF[a.gua]; const eb = ELEM_OF[b.gua];
			let rel = '无涉';
			if (ea === eb) rel = '比和';
			else if (sheng(ea, eb)) rel = `${a.wei}生${b.wei}`;
			else if (sheng(eb, ea)) rel = `${b.wei}生${a.wei}`;
			else if (ke(ea, eb)) rel = `${a.wei}克${b.wei}`;
			else if (ke(eb, ea)) rel = `${b.wei}克${a.wei}`;
			rows.push({ a: a.wei, b: b.wei, aGua: a.gua, bGua: b.gua, aElem: ea, bElem: eb, rel });
		}
	}
	return rows;
}

/** 数全空缺：四位有空者，取其象而言其缺 */
export function shuQuanKongQue(siwei) {
	if (!Array.isArray(siwei)) return null;
	const empties = siwei.filter((x) => x.empty);
	return {
		count: empties.length,
		items: empties.map((x) => {
			const xiang = SIWEI_XIANG.find((s) => s.wei === x.wei);
			return { wei: x.wei, borrowed: x.borrowed, xiang: xiang ? xiang.xiang : '', ren: xiang ? xiang.ren : '' };
		}),
		quan: empties.length === 0 ? '四位皆实，数全' : (empties.length === 4 ? '四位皆空' : `${empties.length} 位空缺`),
	};
}

/**
 * 主算客算：主算 = 体卦数之和（本、互、变之体）；客算 = 用卦数之和。
 * 多算胜、少算负。宏观用先天数。
 */
export function zhuKeSuan(up, lo, dongYao) {
	const lines = [...Gua8.find((g) => g.name === lo).value, ...Gua8.find((g) => g.name === up).value];
	const hu = tiHuYongHu(lines, dongYao);
	const all = guaBianAll(up, lo, dongYao);
	if (!hu || !all) return null;
	const bianTi = hu.tiZai === 'up' ? all.bian.up : all.bian.lo;
	const bianYong = hu.tiZai === 'up' ? all.bian.lo : all.bian.up;
	const zhu = [{ label: '本之体', gua: hu.tiGua }, { label: '体互', gua: hu.tiHu }, { label: '变之体', gua: bianTi }];
	const ke2 = [{ label: '本之用', gua: hu.yongGua }, { label: '用互', gua: hu.yongHu }, { label: '变之用', gua: bianYong }];
	const sum = (arr) => arr.reduce((s, x) => s + (XIANTIAN_NUM[x.gua] || 0), 0);
	const zs = sum(zhu); const ks = sum(ke2);
	return {
		zhu: zhu.map((x) => ({ ...x, num: XIANTIAN_NUM[x.gua] })), zhuSuan: zs,
		ke: ke2.map((x) => ({ ...x, num: XIANTIAN_NUM[x.gua] })), keSuan: ks,
		sheng: zs > ks ? '主算胜' : (ks > zs ? '客算胜' : '主客相当'),
		ze: '多算胜、少算负',
	};
}

/** 断一盘之全 */
export function duanfa({ up, lo, dongYao, monthZhi, siwei }) {
	const lines = Gua8.find((g) => g.name === lo) && Gua8.find((g) => g.name === up)
		? [...Gua8.find((g) => g.name === lo).value, ...Gua8.find((g) => g.name === up).value] : null;
	if (!lines) return null;
	const hu = tiHuYongHu(lines, dongYao);
	if (!hu) return null;
	return {
		tiYong: tiYongShengKe(hu.tiGua, hu.yongGua),
		qingZhong: qingZhongCiXu(up, lo, dongYao),
		guaQi: { ti: guaQi(hu.tiGua, monthZhi), yong: guaQi(hu.yongGua, monthZhi) },
		zhuKe: zhuKeSuan(up, lo, dongYao),
		siweiShengKe: siwei ? siweiShengKe(siwei) : null,
		kongQue: siwei ? shuQuanKongQue(siwei) : null,
		zhenShengZhenKe: ZHEN_SHENG_ZHEN_KE, zhenZe: ZHEN_SHENG_ZHEN_KE_ZE,
		dongJing: DONG_JING_ZE,
	};
}

export default { duanfa, tiYongShengKe, guaQi, qingZhongCiXu, zhuKeSuan, siweiShengKe, shuQuanKongQue };
