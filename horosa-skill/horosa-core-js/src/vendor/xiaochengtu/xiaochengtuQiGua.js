// 小成图 · 起卦层 —— 三模式：manual（本卦+动爻）/ number（两数配卦）/ stock（开收盘价起卦）。
// 纯函数，零 UI 零接线。复用 gua/GuaConst 的 Gua8 / Gua64（卦爻 value 均为自下而上 littleEndian）。
import { Gua8, Gua64 } from '../gua/GuaConst.js';
import { TIAN_DI_SHU_GUA, XIAN_TIAN_GUA } from './xiaochengtuConst.js';

// ── 卦体工具 ───────────────────────────────────────────
/** 按名取八卦（Gua8 条目） */
export function trigramByName(name) {
	return Gua8.find((g) => g.name === name) || null;
}
/** 由三爻（自下而上 0/1）取八卦名 */
export function trigramFromLines(l3) {
	const hit = Gua8.find((g) => g.value[0] === l3[0] && g.value[1] === l3[1] && g.value[2] === l3[2]);
	return hit ? hit.name : null;
}
/** 上下卦 → 六爻（自下而上） */
export function linesOfHex(upName, loName) {
	const up = trigramByName(upName); const lo = trigramByName(loName);
	if (!up || !lo) return null;
	return [...lo.value, ...up.value];
}
/** 六爻 → 六十四卦名（查 Gua64；理论上必中） */
export function hexName(lines) {
	const key = lines.join('');
	const hit = Gua64.find((g) => g.value.join('') === key);
	return hit ? hit.name : null;
}
/** 六爻 → {up, lo, shangHu, xiaHu, name}；上互=爻345、下互=爻234 */
export function hexInfo(lines) {
	if (!Array.isArray(lines) || lines.length !== 6) return null;
	return {
		lines,
		name: hexName(lines),
		lo: trigramFromLines(lines.slice(0, 3)),
		up: trigramFromLines(lines.slice(3, 6)),
		xiaHu: trigramFromLines(lines.slice(1, 4)),   // 爻234
		shangHu: trigramFromLines(lines.slice(2, 5)), // 爻345
	};
}
/** 翻动爻（dongYaos 为 1..6 自下而上之爻位数组） */
export function flipYao(lines, dongYaos) {
	const ds = (Array.isArray(dongYaos) ? dongYaos : [dongYaos]).filter((n) => n >= 1 && n <= 6);
	return lines.map((v, i) => (ds.includes(i + 1) ? 1 - v : v));
}

// ── 配数 ───────────────────────────────────────────────
/** 天地数纳甲配卦：n mod 10（余0作10）→ 乾坤艮兑坎离震巽乾坤（奇阳偶阴） */
export function guaByTianDiShu(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0));
	if (!v) return null;
	const r = v % 10 || 10;
	return { num: r, gua: TIAN_DI_SHU_GUA[r - 1] };
}
/** 先天卦数配卦：n mod 8（余0作8）→ 乾兑离震巽坎艮坤 */
export function guaByXianTian(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0));
	if (!v && v !== 0) return null;
	const r = ((v % 8) + 8) % 8 || 8;
	return { num: r, gua: XIAN_TIAN_GUA[r - 1] };
}

// ── 模式一：manual（本卦+动爻） ─────────────────────────
// 之卦=翻动爻；无动爻则之卦=本卦（「若遇无动爻即无变卦者，仍按其卦作之卦排出即可」）。
export function qiGuaManual({ up, lo, dongYaos = [] }) {
	const benLines = linesOfHex(up, lo);
	if (!benLines) return null;
	const ds = (Array.isArray(dongYaos) ? dongYaos : [dongYaos]).filter((n) => n >= 1 && n <= 6);
	const zhiLines = ds.length ? flipYao(benLines, ds) : benLines.slice();
	return { mode: 'manual', ben: hexInfo(benLines), zhi: hexInfo(zhiLines), dongYaos: ds };
}

// ── 模式一·补：大衍蓍草起卦（十八变，可复现） ───────────
// 每爻三变得 6/7/8/9（老阴6/少阳7/少阴8/老阳9,蓍草概率 1/5/7/3 之十六);老阴老阳为动爻。
// 之卦=动爻取变,无动爻则之卦=本卦(沿用现口径)。seed 入 payload 可复现;或手录每爻 6/7/8/9。
function seededRng(seed) {
	let s = (Math.trunc(Number(seed)) || 1) >>> 0;
	return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}
function yaoFromRoll16(n) {
	const r = (((n % 16) + 16) % 16);
	if (r < 3) return 9;   // 老阳(3/16)
	if (r < 8) return 7;   // 少阳(5/16)
	if (r < 15) return 8;  // 少阴(7/16)
	return 6;              // 老阴(1/16)
}
const YAO_LABEL = { 6: '老阴 ×', 7: '少阳', 8: '少阴', 9: '老阳 ○' };
export function qiGuaByDaYan({ seed, manualCounts } = {}) {
	let counts;
	if (Array.isArray(manualCounts) && manualCounts.length === 6 && manualCounts.every((v) => [6, 7, 8, 9].indexOf(Number(v)) >= 0)) {
		counts = manualCounts.map(Number);
	} else {
		const rng = seededRng(seed || 1);
		counts = Array.from({ length: 6 }, () => yaoFromRoll16(Math.floor(rng() * 16)));
	}
	// 本卦自下而上:老阳9/少阳7=阳(1);老阴6/少阴8=阴(0)。动爻=老阴6或老阳9。
	const benLines = counts.map((c) => ((c === 9 || c === 7) ? 1 : 0));
	const dongYaos = counts.map((c, i) => ((c === 6 || c === 9) ? i + 1 : 0)).filter(Boolean);
	const zhiLines = dongYaos.length ? flipYao(benLines, dongYaos) : benLines.slice();
	return {
		mode: 'dayan', counts, ben: hexInfo(benLines), zhi: hexInfo(zhiLines), dongYaos,
		steps: counts.map((c, i) => ({ label: `第${i + 1}爻`, detail: `十八变之三变得 ${c}(${YAO_LABEL[c]})`, value: c })),
	};
}

// ── 模式一·补二：摇钱三变起卦（可复现） ─────────────────
// 古籍两载例皆自「摇钱/摇卦」而得(「摇钱得家人之损」「用小成图摇卦得乾之兑」),
// 🔴 惟书中只记所得之卦而未记铜钱规则,故此处按通行摇钱古法:三枚铜钱一掷为一变,三变成一爻;
//    背数 0/1/2/3 → 老阴6(三字,1/8) / 少阳7(3/8) / 少阴8(3/8) / 老阳9(三背,1/8),老阴老阳为动爻。
//    与大衍蓍草之十六分概率(3/5/7/1)不同,是为两法之别(同为六爻十八变而分布有异)。
// 之卦=动爻取变,无动爻则之卦=本卦(沿用现口径)。seed 可复现;或手录每爻 6/7/8/9。
export function qiGuaByYaoQian({ seed, manualCounts } = {}) {
	let counts;
	if (Array.isArray(manualCounts) && manualCounts.length === 6 && manualCounts.every((v) => [6, 7, 8, 9].indexOf(Number(v)) >= 0)) {
		counts = manualCounts.map(Number);
	} else {
		const rng = seededRng(seed || 1);
		// 每爻三掷,每掷背(1)/字(0);背数 + 6 = 该爻之数。
		counts = Array.from({ length: 6 }, () => 6 + [0, 1, 2].reduce((acc) => acc + (rng() < 0.5 ? 1 : 0), 0));
	}
	const benLines = counts.map((c) => ((c === 9 || c === 7) ? 1 : 0));
	const dongYaos = counts.map((c, i) => ((c === 6 || c === 9) ? i + 1 : 0)).filter(Boolean);
	const zhiLines = dongYaos.length ? flipYao(benLines, dongYaos) : benLines.slice();
	return {
		mode: 'yaoqian', counts, ben: hexInfo(benLines), zhi: hexInfo(zhiLines), dongYaos,
		steps: counts.map((c, i) => {
			const bei = c - 6;
			return { label: `第${i + 1}爻`, detail: `三变得 ${bei}背${3 - bei}字 → ${c}(${YAO_LABEL[c]})`, value: c };
		}),
	};
}

// ── 模式二：number（两数→上下卦） ───────────────────────
// qiguaShu：'tiandi'（天地数纳甲，通用默认）/ 'xiantian'（先天卦数，股市默认）。
// 无动爻规格 → 之卦=本卦；如附动爻则照翻。
export function qiGuaByNumbers({ upNum, loNum, qiguaShu = 'tiandi', dongYaos = [] }) {
	const fn = qiguaShu === 'xiantian' ? guaByXianTian : guaByTianDiShu;
	const u = fn(upNum); const l = fn(loNum);
	if (!u || !l) return null;
	const benLines = linesOfHex(u.gua, l.gua);
	const ds = (Array.isArray(dongYaos) ? dongYaos : [dongYaos]).filter((n) => n >= 1 && n <= 6);
	const zhiLines = ds.length ? flipYao(benLines, ds) : benLines.slice();
	return {
		mode: 'number', qiguaShu, ben: hexInfo(benLines), zhi: hexInfo(zhiLines), dongYaos: ds,
		steps: [
			{ label: '上卦', detail: `${upNum} 配数`, value: u.gua },
			{ label: '下卦', detail: `${loNum} 配数`, value: l.gua },
		],
	};
}

// ── 模式三：stock（开收盘价起卦） ───────────────────────
// 开盘整数位数字和%8→主卦上；开盘小数位数字和%8→主卦下；
// 收盘整数位数字和%8→变卦上；收盘小数位数字和%8→变卦下。配数固定先天卦数。
// 数字和取余照「余数为8（即整除）作坤」之例（先天8=坤）。
function digitSum(str) {
	let s = 0;
	for (const ch of String(str)) { if (ch >= '0' && ch <= '9') s += ch.charCodeAt(0) - 48; }
	return s;
}
/** 价格拆整数位/小数位（建议以字符串传入以保留末尾 0；数字亦可） */
export function splitPrice(p) {
	const t = String(p).trim();
	const dot = t.indexOf('.');
	const intPart = dot < 0 ? t : t.slice(0, dot);
	const fracPart = dot < 0 ? '' : t.slice(dot + 1);
	return { intSum: digitSum(intPart), fracSum: digitSum(fracPart) };
}
export function qiGuaByStock({ open, close }) {
	if (open == null || close == null) return null;
	// 空串/无数字输入不成卦:否则数字和恒为 0→先天8→四卦皆坤,静默产出「坤为地 之 坤为地」伪盘而无报错。
	if (!/\d/.test(String(open)) || !/\d/.test(String(close))) return null;
	const o = splitPrice(open); const c = splitPrice(close);
	const bu = guaByXianTian(o.intSum);  // 主卦上
	const bl = guaByXianTian(o.fracSum); // 主卦下
	const zu = guaByXianTian(c.intSum);  // 变卦上
	const zl = guaByXianTian(c.fracSum); // 变卦下
	if (!bu || !bl || !zu || !zl) return null;
	return {
		mode: 'stock', qiguaShu: 'xiantian',
		ben: hexInfo(linesOfHex(bu.gua, bl.gua)),
		zhi: hexInfo(linesOfHex(zu.gua, zl.gua)),
		steps: [
			{ label: '主卦上', detail: `开盘整数位数字和 ${o.intSum} ÷8 余 ${bu.num}`, value: bu.gua },
			{ label: '主卦下', detail: `开盘小数位数字和 ${o.fracSum} ÷8 余 ${bl.num}`, value: bl.gua },
			{ label: '变卦上', detail: `收盘整数位数字和 ${c.intSum} ÷8 余 ${zu.num}`, value: zu.gua },
			{ label: '变卦下', detail: `收盘小数位数字和 ${c.fracSum} ÷8 余 ${zl.num}`, value: zl.gua },
		],
	};
}
