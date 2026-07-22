// 皇极轨策 · 起卦十四法 —— 纯函数、全整数。
//
// 两条通则（诸法皆本此）：
//   · 卦数起例：任意数以八除，取其余为卦；「如得八數整，即坤卦，更不必除也」→ 整除得八，非零。
//   · 爻以六除：重卦总数以六除，取其余为动爻；「如不滿六，止用此數為動爻，不必再除」→ 整除得六。
//
// 起卦所得（卦与动爻）为报数/字占/时辰之冻结值 —— 一经起出即不可按时重算，
// 重算即伪造一个不同之卦。故上层以 payload 存之。
import { Gua8 } from '../../gua/GuaConst.js';

const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

/** 卦数起例：以八除取余，整除得八（坤）。返 {num, gua} */
export function guaByNumber(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0));
	if (!v) return null;
	const r = v % 8 || 8;
	return { num: r, gua: Gua8[r - 1].name };
}
/** 爻以六除：整除得六 */
export function yaoByNumber(n) {
	const v = Math.abs(Math.trunc(Number(n) || 0));
	if (!v) return null;
	return v % 6 || 6;
}
/** 支数：子1 丑2 … 亥12 */
export function zhiNum(zhi) { const i = ZHI.indexOf(zhi); return i < 0 ? null : i + 1; }

const mk = (up, lo, yao, steps, extra = {}) => (up && lo && yao
	? { up: up.gua, lo: lo.gua, upNum: up.num, loNum: lo.num, dongYao: yao, steps, ...extra } : null);

// ── 法1 年月日时起例 ────────────────────────────────────
// 上卦 = (年+月+日) ÷8；下卦 = (年+月+日+时) ÷8；动爻 = (年+月+日+时) ÷6
export function qiGuaByTime({ yearZhi, lunarMonth, lunarDay, hourZhi }) {
	const y = zhiNum(yearZhi); const m = Number(lunarMonth); const d = Number(lunarDay); const h = zhiNum(hourZhi);
	if (!y || !(m >= 1 && m <= 12) || !(d >= 1 && d <= 30) || !h) return null;
	const s1 = y + m + d; const s2 = s1 + h;
	return mk(guaByNumber(s1), guaByNumber(s2), yaoByNumber(s2), [
		{ label: '上卦', detail: `年${y} + 月${m} + 日${d} = ${s1}，÷8 余`, value: guaByNumber(s1).gua },
		{ label: '下卦', detail: `${s1} + 时${h} = ${s2}，÷8 余`, value: guaByNumber(s2).gua },
		{ label: '动爻', detail: `${s2} ÷6 余`, value: `${yaoByNumber(s2)} 爻动` },
	], { fa: 'time' });
}

// ── 法2 卦数起例·报数 ──────────────────────────────────
// 报一数（单数）→ 此数÷8 为上卦、时数÷8 为下卦；报二数（双数）→ 先数为上、后数为下。
// 动爻皆取（总数+时数）÷6。
export function qiGuaByBaoShu({ nums, hourZhi }) {
	const ns = (Array.isArray(nums) ? nums : [nums]).map((x) => Math.abs(Math.trunc(Number(x) || 0))).filter(Boolean);
	const h = zhiNum(hourZhi);
	if (!ns.length || !h) return null;
	if (ns.length === 1) {
		const total = ns[0] + h;
		return mk(guaByNumber(ns[0]), guaByNumber(h), yaoByNumber(total), [
			{ label: '上卦', detail: `所报之数 ${ns[0]} ÷8 余`, value: guaByNumber(ns[0]).gua },
			{ label: '下卦', detail: `时数 ${h} ÷8 余`, value: guaByNumber(h).gua },
			{ label: '动爻', detail: `${ns[0]} + 时${h} = ${total}，÷6 余`, value: `${yaoByNumber(total)} 爻动` },
		], { fa: 'baoshu', danShu: true });
	}
	const [a, b] = ns; const total = a + b + h;
	return mk(guaByNumber(a), guaByNumber(b), yaoByNumber(total), [
		{ label: '上卦', detail: `先数 ${a} ÷8 余`, value: guaByNumber(a).gua },
		{ label: '下卦', detail: `后数 ${b} ÷8 余`, value: guaByNumber(b).gua },
		{ label: '动爻', detail: `${a} + ${b} + 时${h} = ${total}，÷6 余`, value: `${yaoByNumber(total)} 爻动` },
	], { fa: 'baoshu', danShu: false });
}

/** 法3 物数占 / 法4 声音占：其数÷8 为上卦、时数÷8 为下卦、(其数+时)÷6 为动爻 */
function qiGuaByShuAndHour(n, hourZhi, fa, label) {
	const v = Math.abs(Math.trunc(Number(n) || 0)); const h = zhiNum(hourZhi);
	if (!v || !h) return null;
	const total = v + h;
	return mk(guaByNumber(v), guaByNumber(h), yaoByNumber(total), [
		{ label: '上卦', detail: `${label} ${v} ÷8 余`, value: guaByNumber(v).gua },
		{ label: '下卦', detail: `时数 ${h} ÷8 余`, value: guaByNumber(h).gua },
		{ label: '动爻', detail: `${v} + 时${h} = ${total}，÷6 余`, value: `${yaoByNumber(total)} 爻动` },
	], { fa });
}
export const qiGuaByWuShu = ({ wuShu, hourZhi }) => qiGuaByShuAndHour(wuShu, hourZhi, 'wushu', '物数');
export const qiGuaByShengYin = ({ shengShu, hourZhi }) => qiGuaByShuAndHour(shengShu, hourZhi, 'shengyin', '声数');

// ── 法5 字占（十一档）─────────────────────────────────
// 通则：字数停匀则平分上下；不匀则少一字为上卦（天轻清）、多一字为下卦（地重浊）。
export const PING_ZE = { 平: 1, 上: 2, 去: 3, 入: 4 };
/** 一字之左右画：彳、丿之属为左（阳画→上卦）；一、乙、丶之属为右（阴画→下卦） */
export const YIZI_LEFT = '彳丿亻丨';
export const YIZI_RIGHT = '一乙丶乀';

export function ziZhanSplit(n) {
	if (n === 1) return { up: 0, lo: 0, special: 'yizi' };
	if (n === 2) return { up: 1, lo: 1, note: '两仪平分' };
	if (n === 3) return { up: 1, lo: 2, note: '三才' };
	if (n === 4) return { up: 2, lo: 2, note: '四象平分' };
	if (n === 5) return { up: 2, lo: 3, note: '五行' };
	if (n === 6) return { up: 3, lo: 3, note: '六爻平分' };
	if (n === 7) return { up: 3, lo: 4, note: '齐七政' };
	if (n === 8) return { up: 4, lo: 4, note: '八卦定位平分' };
	if (n === 9) return { up: 4, lo: 5, note: '九畴' };
	if (n === 10) return { up: 5, lo: 5, note: '成数平分' };
	if (n >= 11 && n <= 100) {
		const up = Math.floor(n / 2);
		return { up, lo: n - up, note: '十一字以上至百字：不用平仄，止用字数；均平则半上半下' };
	}
	return null;
}

/**
 * 字占。
 *   一字：太极未判 —— 草书混沌不可得卦；楷书取字画，左为阳画→上卦、右为阴画→下卦。
 *   二至四字：以字数分；四字以上不数画数，只以平仄声调（平1 上2 去3 入4）。
 *   十一字以上至百字：不用平仄，止用字数。
 */
export function qiGuaByZi({ text, shu = 'kai', tones, hourZhi }) {
	const chars = `${text || ''}`.replace(/\s/g, '');
	const n = chars.length;
	if (!n) return null;
	if (n === 1) {
		if (shu === 'cao') return { error: '草书混沌未判，一字不可得卦' };
		const left = [...chars[0]].length; void left;
		const l = Number((tones && tones.leftStrokes) || 0);
		const r = Number((tones && tones.rightStrokes) || 0);
		if (!l || !r) return { error: '一字须取其字画：左为阳画（上卦）、右为阴画（下卦）' };
		const total = l + r; const h = zhiNum(hourZhi);
		const yao = yaoByNumber(h ? total + h : total);
		return mk(guaByNumber(l), guaByNumber(r), yao, [
			{ label: '上卦', detail: `左之阳画 ${l} ÷8 余`, value: guaByNumber(l).gua },
			{ label: '下卦', detail: `右之阴画 ${r} ÷8 余`, value: guaByNumber(r).gua },
			{ label: '动爻', detail: `合二卦之数 ${h ? `${total}+时${h}` : total} ÷6 余`, value: `${yao} 爻动` },
		], { fa: 'zizhan', dang: 1, note: '一字：太极未判，取字画左右' });
	}
	const sp = ziZhanSplit(n);
	if (!sp) return { error: '字过百者，本法不载' };
	const usePingZe = n >= 4 && n <= 10;
	let upSum; let loSum; let how;
	if (usePingZe) {
		const ts = Array.isArray(tones) ? tones : [];
		if (ts.length !== n) return { error: `四字以上至十字须以平仄声调取数（平1 上2 去3 入4），当出 ${n} 个声调` };
		const val = ts.map((t) => PING_ZE[t] || 0);
		if (val.some((v) => !v)) return { error: '声调只取 平／上／去／入' };
		upSum = val.slice(0, sp.up).reduce((a, b) => a + b, 0);
		loSum = val.slice(sp.up).reduce((a, b) => a + b, 0);
		how = '以平仄声调取数';
	} else {
		upSum = sp.up; loSum = sp.lo;
		how = n <= 3 ? '以字数取数' : '不用平仄，止用字数';
	}
	const h = zhiNum(hourZhi);
	const total = upSum + loSum;
	const yao = yaoByNumber(h ? total + h : total);
	return mk(guaByNumber(upSum), guaByNumber(loSum), yao, [
		{ label: '分字', detail: `${n} 字 —— ${sp.note}${sp.up === sp.lo ? '' : '（少一字为上卦、多一字为下卦）'}`, value: `上 ${sp.up} 字／下 ${sp.lo} 字` },
		{ label: '上卦', detail: `${how}：上 ${upSum} ÷8 余`, value: guaByNumber(upSum).gua },
		{ label: '下卦', detail: `${how}：下 ${loSum} ÷8 余`, value: guaByNumber(loSum).gua },
		{ label: '动爻', detail: `合二卦之总数 ${h ? `${total}+时${h}` : total} ÷6 余`, value: `${yao} 爻动` },
	], { fa: 'zizhan', dang: n, note: sp.note });
}

// ── 法6 丈尺占（不加时；寸数不用）───────────────────────
export function qiGuaByZhangChi({ zhang, chi }) {
	const z = Math.abs(Math.trunc(Number(zhang) || 0)); const c = Math.abs(Math.trunc(Number(chi) || 0));
	if (!z || !c) return null;
	const total = z + c;
	return mk(guaByNumber(z), guaByNumber(c), yaoByNumber(total), [
		{ label: '上卦', detail: `丈数 ${z} ÷8 余`, value: guaByNumber(z).gua },
		{ label: '下卦', detail: `尺数 ${c} ÷8 余`, value: guaByNumber(c).gua },
		{ label: '动爻', detail: `丈${z} + 尺${c} = ${total}，÷6 余（本法不加时；寸数不用）`, value: `${yaoByNumber(total)} 爻动` },
	], { fa: 'zhangchi' });
}

// ── 法7 尺寸占（加时；分数不用）─────────────────────────
export function qiGuaByChiCun({ chi, cun, hourZhi }) {
	const c = Math.abs(Math.trunc(Number(chi) || 0)); const u = Math.abs(Math.trunc(Number(cun) || 0));
	const h = zhiNum(hourZhi);
	if (!c || !u || !h) return null;
	const total = c + u + h;
	return mk(guaByNumber(c), guaByNumber(u), yaoByNumber(total), [
		{ label: '上卦', detail: `尺数 ${c} ÷8 余`, value: guaByNumber(c).gua },
		{ label: '下卦', detail: `寸数 ${u} ÷8 余`, value: guaByNumber(u).gua },
		{ label: '动爻', detail: `尺${c} + 寸${u} + 时${h} = ${total}，÷6 余（本法加时；分数不用）`, value: `${yaoByNumber(total)} 爻动` },
	], { fa: 'chicun' });
}

// ── 法10/12 占动物 · 端法后天起卦（物卦起例）───────────
// 上卦 = 物之卦；下卦 = 所来方位之卦；动爻 = (物卦数 + 方位数 + 时数) ÷6
export function qiGuaByWuFang({ wuGuaNum, fangGuaNum, hourZhi, fa = 'duanfa' }) {
	const w = Math.abs(Math.trunc(Number(wuGuaNum) || 0)); const f = Math.abs(Math.trunc(Number(fangGuaNum) || 0));
	const h = zhiNum(hourZhi);
	if (!(w >= 1 && w <= 8) || !(f >= 1 && f <= 8) || !h) return null;
	const total = w + f + h;
	return mk({ num: w, gua: Gua8[w - 1].name }, { num: f, gua: Gua8[f - 1].name }, yaoByNumber(total), [
		{ label: '上卦', detail: `物之卦 ${Gua8[w - 1].name}（${w}）`, value: Gua8[w - 1].name },
		{ label: '下卦', detail: `所来方位之卦 ${Gua8[f - 1].name}（${f}）`, value: Gua8[f - 1].name },
		{ label: '动爻', detail: `物${w} + 方${f} + 时${h} = ${total}，÷6 余`, value: `${yaoByNumber(total)} 爻动` },
	], { fa });
}

// ── 法11 占静物 ─────────────────────────────────────────
// 屋宅初创／树木初置／器置成 之时可起；「群物之动」「江河山石」不可起卦。
export const JING_WU_BU_KE = ['群物之动', '江河山石'];
export function qiGuaByJingWu({ kind, yearZhi, lunarMonth, lunarDay, hourZhi }) {
	if (JING_WU_BU_KE.indexOf(kind) >= 0) {
		return { error: `${kind}：本法不可起卦（无初创之时可稽）` };
	}
	const r = qiGuaByTime({ yearZhi, lunarMonth, lunarDay, hourZhi });
	return r ? { ...r, fa: 'jingwu', note: `以${kind || '初创'}之时起卦` } : null;
}

// ── 法8/9 为人占 · 自己占 ───────────────────────────────
// 取诸语声字数／人品／身／物／服色／年月日时／书写来意 —— 语多则只用初听一句或末后一句。
export const WEIREN_QU = [
	{ key: 'yusheng', label: '语声字数' }, { key: 'renpin', label: '人品' },
	{ key: 'shen', label: '取诸身' }, { key: 'wu', label: '取诸物' },
	{ key: 'fuse', label: '服色' }, { key: 'shijian', label: '年月日时' },
	{ key: 'laiyi', label: '书写来意' },
];
export const WEIREN_YUDUO = '语多则只用初听一句或末后一句';

export const QI_GUA_FA = [
	{ key: 'time', label: '年月日时起例' }, { key: 'baoshu', label: '卦数起例（报数）' },
	{ key: 'wushu', label: '物数占' }, { key: 'shengyin', label: '声音占' },
	{ key: 'zizhan', label: '字占' }, { key: 'zhangchi', label: '丈尺占' },
	{ key: 'chicun', label: '尺寸占' }, { key: 'weiren', label: '为人占' },
	{ key: 'ziji', label: '自己占' }, { key: 'dongwu', label: '占动物' },
	{ key: 'jingwu', label: '占静物' }, { key: 'duanfa', label: '端法后天起卦' },
];

/** 统一入口：按法分派 */
export function qiGua(fa, input = {}) {
	switch (fa) {
		case 'time': return qiGuaByTime(input);
		case 'baoshu': return qiGuaByBaoShu(input);
		case 'wushu': return qiGuaByWuShu(input);
		case 'shengyin': return qiGuaByShengYin(input);
		case 'zizhan': return qiGuaByZi(input);
		case 'zhangchi': return qiGuaByZhangChi(input);
		case 'chicun': return qiGuaByChiCun(input);
		case 'dongwu': return qiGuaByWuFang({ ...input, fa: 'dongwu' });
		case 'duanfa': return qiGuaByWuFang({ ...input, fa: 'duanfa' });
		case 'jingwu': return qiGuaByJingWu(input);
		case 'weiren': case 'ziji': {
			// 为人/自己占取诸多端 —— 其数一经取得即同物数占之链
			// 「其数」控件写 shu2(与字占 shu 分键);兼容旧调用方仍传 shu。
			const wr = input.shu2 != null ? input.shu2 : input.shu;
			const r = qiGuaByWuShu({ wuShu: wr, hourZhi: input.hourZhi });
			return r ? { ...r, fa, qu: input.qu, note: WEIREN_YUDUO } : null;
		}
		default: return null;
	}
}

export default { qiGua, guaByNumber, yaoByNumber, zhiNum, ziZhanSplit };
