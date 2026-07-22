// 皇极轨策 · 演数引擎 —— 纯函数、全整数、零副作用、零星历依赖。
//
// 演数之法：以本卦之身数（上下卦原策之和）配动爻与体用卦正数，演出策数或轨数；
// 除万不用，取千百十零四位，立于元会运世之下断之。
//
// 🔴 六十四卦三百八十四爻全表由本层公式派生，不硬编 ——
//    古籍之全表只作 golden（见 __tests__/guice384.golden.test.js），384/384 逐字吻合、零误差。
//    硬编表则失「规则自证」，且印本之误将随之固化。
import { Gua8 } from '../../gua/GuaConst.js';
import {
	XIANTIAN_NUM, HOUTIAN_NUM, CE_YANG, CE_YIN, GUI_YANG, GUI_YIN,
	WUXING_SHENGCHENG, JIUCHOU_BY_DIGIT, JIUCHOU_BORROWED, JIEWEI_XIANGJIE,
	YUAN_HUI_YUN_SHI, GANG_GAN,
} from './guiceConst.js';

const GUA_BY_NAME = Gua8.reduce((m, g) => { m[g.name] = g; return m; }, {});
export const YANSHU_MODES = { ce: '策数', gui: '轨数' };

/** 演数之档：策数用先天正数与 36/24；轨数用后天正数与 128/112 */
function modeOf(mode) {
	return mode === 'gui'
		? { num: HOUTIAN_NUM, yang: GUI_YANG, yin: GUI_YIN }
		: { num: XIANTIAN_NUM, yang: CE_YANG, yin: CE_YIN };
}

/** 身数 = Σ(阳爻取阳策 + 阴爻取阴策) = 上卦原策 + 下卦原策 */
export function bodyNumber(up, lo, mode = 'ce') {
	const gu = GUA_BY_NAME[up]; const gl = GUA_BY_NAME[lo];
	if (!gu || !gl) return null;
	const { yang, yin } = modeOf(mode);
	const sum = (g) => g.value.reduce((s, b) => s + (b ? yang : yin), 0);
	return sum(gl) + sum(gu);
}

/**
 * 动策/动轨之数。
 *   下卦动（爻 1/2/3）：用卦=下卦、体卦=上卦 → 用×10×身 + 爻×身 + 身 + 体 + 用 + 爻
 *   上卦动（爻 4/5/6）：用卦=上卦、体卦=下卦 → 爻×10×身 + 用×身 + 身 + 体 + 用 + 爻
 * 两式已对古籍全表 384/384 逐字验过。
 */
export function moveNumber(up, lo, dongYao, mode = 'ce') {
	const f = Number(dongYao);
	// 须整数：本层宣称全整数，而 1.5 之类能过区间之查却演出小数(实测 14860.5) → 显式拒之
	if (!Number.isInteger(f) || !(f >= 1 && f <= 6)) return null;
	const body = bodyNumber(up, lo, mode);
	if (body === null) return null;
	const { num } = modeOf(mode);
	const G = num[up]; const H = num[lo];
	if (G === undefined || H === undefined) return null;
	const xiaDong = f < 4;
	const yongGua = xiaDong ? lo : up;      // 用卦 = 动爻所在之卦
	const tiGua = xiaDong ? up : lo;        // 体卦 = 另一卦
	const value = xiaDong
		? (H * 10 + f) * body + body + f + G + H
		: f * 10 * body + G * body + body + f + G + H;
	return {
		up, lo, dongYao: f, mode, body, value,
		yongGua, tiGua, yongNum: num[yongGua], tiNum: num[tiGua],
		xiaDong,
		formula: xiaDong
			? `用${H}×10×身${body} + 爻${f}×身${body} + 身${body} + 体${G} + 用${H} + 爻${f}`
			: `爻${f}×10×身${body} + 用${G}×身${body} + 身${body} + 体${H} + 用${G} + 爻${f}`,
	};
}

/** 除万不用 → 千百十零。零位以 0 记（下断时视作「空」，可隔位相借）。 */
export function splitYuanHuiYunShi(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0)) % 10000;   // 除万不用
	return {
		raw: Number(n) || 0, kept: v,
		qian: Math.floor(v / 1000) % 10,
		bai: Math.floor(v / 100) % 10,
		shi: Math.floor(v / 10) % 10,
		ling: v % 10,
	};
}

/** 五与十之寄宫：刚日(阳干)五寄艮、十寄坤；柔日(阴干)反之。两法所载正相反 → 亦可指定。 */
export function jiGongOf(digit, mode = 'ganrou', dayGan) {
	if (digit !== 5 && digit !== 10) return null;
	if (mode === 'wuGen') return digit === 5 ? '艮' : '坤';
	if (mode === 'wuKun') return digit === 5 ? '坤' : '艮';
	const gang = dayGan ? GANG_GAN.indexOf(dayGan) >= 0 : true;   // 无日干可凭时按刚日
	return gang ? (digit === 5 ? '艮' : '坤') : (digit === 5 ? '坤' : '艮');
}

/**
 * 数字 → 卦。返 guaBorrow（九畴借宫／寄宫）—— 🔴 不可名作 borrowed：
 * 「隔位相借」（borrowEmptyDigits 之 borrowed）与「九畴借宫」语义两别，共用一键则展开时相盖。
 *   xiantian：五行生成数（一六坎水／二七离火／三震八巽木／四兑九乾金／五坤十艮土）
 *   houtian ：后天正数（五与十无卦 → 寄宫，其所寄有异说，见 jiGongOf）
 *   jiuchou ：九畴数（七借巽、十借艮 —— 借之所在由口诀自载，非推定）
 * digit 以 0 记零位；零位在数上作十论（十位之数），故 0 归入 10。
 */
export function digitToGua(digit, system = 'xiantian', opts = {}) {
	const d = Number(digit);
	if (!(d >= 0 && d <= 10)) return null;
	const n = d === 0 ? 10 : d;
	if (system === 'jiuchou') {
		const gua = JIUCHOU_BY_DIGIT[n] || null;
		return gua ? { digit: n, gua, guaBorrow: JIUCHOU_BORROWED[n] ? `${n}借${gua}` : null, system } : null;
	}
	if (system === 'houtian') {
		const inv = Object.keys(HOUTIAN_NUM).find((k) => HOUTIAN_NUM[k] === n);
		if (inv) return { digit: n, gua: inv, guaBorrow: null, system };
		const ji = jiGongOf(n, opts.jiGongMode || 'ganrou', opts.dayGan);
		return ji ? { digit: n, gua: ji, guaBorrow: `${n}寄${ji}`, system, jiGong: true } : null;
	}
	const e = WUXING_SHENGCHENG[n];
	return e ? { digit: n, gua: e.gua, wuxing: e.wuxing, guaBorrow: null, system } : null;
}

/**
 * 隔位相借：无千则借十，无百则借零，无十则借千，无零则借百。
 * 「无」谓其位为空（0）。所借者为原数，非递归（借来之位若亦空则仍空）。
 */
export function borrowEmptyDigits(parts) {
	const src = { 千: parts.qian, 百: parts.bai, 十: parts.shi, 零: parts.ling };
	const out = {};
	Object.keys(src).forEach((wei) => {
		const v = src[wei];
		if (v !== 0) { out[wei] = { value: v, empty: false, borrowed: null }; return; }
		const from = JIEWEI_XIANGJIE[wei];
		const bv = src[from];
		out[wei] = bv !== 0
			? { value: bv, empty: true, borrowed: `无${wei}借${from}` }
			: { value: 0, empty: true, borrowed: null };   // 所借之位亦空 → 仍空，不再递归
	});
	return out;
}

/** 元会运世：1元=12会=360运=4320世=129600年 */
export function yuanHuiYunShiOf(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0));
	return {
		yuan: Math.floor(v / YUAN_HUI_YUN_SHI.nian),
		hui: Math.floor(v / (YUAN_HUI_YUN_SHI.nian / YUAN_HUI_YUN_SHI.hui)) % YUAN_HUI_YUN_SHI.hui,
		nian: v,
	};
}

/** 六十四卦三百八十四爻全表（由公式派生，非硬编）。懒生成 + 模块级缓存 —— 非起卦路径。 */
const tableCache = {};
export function buildGuiceTable(mode = 'ce') {
	if (tableCache[mode]) return tableCache[mode];
	const rows = [];
	Gua8.forEach((gu) => Gua8.forEach((gl) => {
		for (let f = 1; f <= 6; f += 1) {
			const r = moveNumber(gu.name, gl.name, f, mode);
			if (r) rows.push({ up: gu.name, lo: gl.name, dongYao: f, body: r.body, value: r.value });
		}
	}));
	tableCache[mode] = rows;
	return rows;
}
export function __resetGuiceTableCache() { Object.keys(tableCache).forEach((k) => delete tableCache[k]); }

/** 演一盘之数：策与轨并出，四位与借位随之。 */
export function yanShu(up, lo, dongYao, opts = {}) {
	const mode = opts.yanshuFa === 'gui' ? 'gui' : 'ce';
	const m = moveNumber(up, lo, dongYao, mode);
	if (!m) return null;
	const parts = splitYuanHuiYunShi(m.value);
	const borrowed = borrowEmptyDigits(parts);
	const system = opts.qiguaShu === 'houtian' ? 'houtian' : (opts.qiguaShu === 'jiuchou' ? 'jiuchou' : 'xiantian');
	const siwei = ['千', '百', '十', '零'].map((wei) => {
		const b = borrowed[wei];
		return { wei, ...b, ...(digitToGua(b.value, system, opts) || {}) };
	});
	return { ...m, parts, siwei, system };
}

export default { bodyNumber, moveNumber, splitYuanHuiYunShi, digitToGua, borrowEmptyDigits, buildGuiceTable, yanShu };
