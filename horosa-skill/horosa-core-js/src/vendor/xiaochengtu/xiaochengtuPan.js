// 小成图 · 盘面层 —— 佈局(九宫落卦)/ 正推 / 旁推 / 数占 / 四象阖辟往来 / 幅度涨跌 / K线定用宫。
// 纯函数,零 UI 零接线。
import {
	DI_PAN, GUA_GONG, PANG_GONG,
	SHENG_GUA, YANG_GUA, FUDU, ZHU_YAO_WEI,
	SI_XIANG_MATRIX, SI_XIANG_BASE, SI_XIANG_YI,
	KLINE_YONG_GONG,
} from './xiaochengtuConst.js';

// ── 佈局:本卦/之卦(hexInfo)→ 天盘九宫落卦 ─────────────
// 9=本卦上 / 1=本卦下 / 3=之卦上 / 7=之卦下 /
// 4=本卦上互(爻345) / 2=本卦下互(爻234) / 8=之卦上互 / 6=之卦下互。
export function buildPan(qi) {
	const { ben, zhi } = qi || {};
	if (!ben || !zhi) return null;
	const tianPan = {
		9: ben.up, 1: ben.lo, 3: zhi.up, 7: zhi.lo,
		4: ben.shangHu, 2: ben.xiaHu, 8: zhi.shangHu, 6: zhi.xiaHu,
	};
	return { tianPan, diPan: { ...DI_PAN }, ben, zhi };
}

// ── 正推 ───────────────────────────────────────────────
// 「用宫为何宫就从地盘的何宫推起。」
// 用宫天地盘相同 → 伏位不动(采用旁推法)。
// 否则循环记录(宫, 天盘卦, 卦数),下一宫 = 该卦之宫数;
//   下一宫已访 → 记毕本步而止(「出现重复因此而止」);
//   下一宫天地盘相同 → 记毕本步而止(「继续推导天地相同,无须推导」)。
export function zhengTui(pan, g0) {
	if (!pan || !DI_PAN[g0]) return null;
	const tian = pan.tianPan;
	if (tian[g0] === DI_PAN[g0]) {
		return { start: g0, fuWei: true, steps: [], stopReason: '伏位' };
	}
	const steps = [];
	const visited = new Set();
	let g = g0;
	let stopReason = '';
	for (let guard = 0; guard < 9; guard += 1) {
		visited.add(g);
		const t = tian[g];
		steps.push({ gong: g, diGua: DI_PAN[g], tianGua: t, shu: GUA_GONG[t] });
		const next = GUA_GONG[t];
		if (visited.has(next)) { stopReason = '复宫而止'; break; }
		if (tian[next] === DI_PAN[next]) { stopReason = '临伏位而止'; break; }
		g = next;
	}
	return { start: g0, fuWei: false, steps, stopReason };
}

/** 正推链逐字文本:如「乾宫震卦→震宫坎卦→坎宫坤卦而止」;伏位则如「艮宫艮卦,天地盘相同,伏位不动」。
 *  🔴 [P3 压测实爆] 亦须认得 pangTui 产物({pangGong,gua},无 steps 无 fuWei):
 *  用宫恰为伏位时,UI 推导 tab 与 AI 快照层都把 td.pang 喂进本函数 —— 旧版 r.steps.map
 *  直接 TypeError = 该类卦局「推导页白屏 + AI 导出必炸」(3072 组合链压测抓出)。 */
export function zhengTuiText(r) {
	if (!r) return '';
	if (r.fuWei) return `${DI_PAN[r.start]}宫${DI_PAN[r.start]}卦,天地盘相同,伏位不动`;
	if (r.pangGong) return `旁宫${r.pangGongGua}(${r.pangGong})得天盘${r.gua}卦`;
	if (!Array.isArray(r.steps)) return '';
	return `${r.steps.map((s) => `${s.diGua}宫${s.tianGua}卦`).join('→')}而止`;
}

// ── 旁推 ───────────────────────────────────────────────
// 「震与巽互为旁宫、艮与兑互为旁宫、离与坎互为旁宫、乾与坤互为旁宫」,取旁宫天盘卦一步。
export function pangTui(pan, g0) {
	if (!pan || !PANG_GONG[g0]) return null;
	const pangGong = PANG_GONG[g0];
	return { start: g0, pangGong, pangGongGua: DI_PAN[pangGong], gua: pan.tianPan[pangGong] };
}

/** 综合推导:用宫伏位 → 旁推;否则正推。 */
export function tuiDao(pan, g0) {
	const zheng = zhengTui(pan, g0);
	if (!zheng) return null;
	if (zheng.fuWei) return { ...zheng, pang: pangTui(pan, g0) };
	return zheng;
}

// ── 数占(问数以数应):正推链各步天盘卦之宫数相加 ────────
export function shuZhan(pan, g0) {
	const r = zhengTui(pan, g0);
	if (!r) return null;
	if (r.fuWei) return { ...r, sum: null, pang: pangTui(pan, g0) };
	const sum = r.steps.reduce((acc, s) => acc + s.shu, 0);
	return { ...r, sum };
}

// ── 四象「阖辟往来」 ────────────────────────────────────
// 上升下升=往 / 上降下降=來 / 上降下升=闔 / 上升下降=闢;得配=一阴一阳。
export function siXiang(upName, loName) {
	if (!GUA_GONG[upName] || !GUA_GONG[loName]) return null;
	const upSheng = SHENG_GUA.includes(upName);
	const loSheng = SHENG_GUA.includes(loName);
	let type;
	if (upSheng && loSheng) type = '往';
	else if (!upSheng && !loSheng) type = '來';
	else if (!upSheng && loSheng) type = '闔';
	else type = '闢';
	const dePei = YANG_GUA.includes(upName) !== YANG_GUA.includes(loName);
	return {
		up: upName, lo: loName, type,
		yi: SI_XIANG_YI[type],                       // 外引/内引/向心/离心
		dePei,                                        // 得配=一阴一阳
		ci: SI_XIANG_MATRIX[type][dePei ? '得配' : '失配'], // 得失配之辞
		baseCi: SI_XIANG_BASE[type],                  // 图注基调(乾往悔/坤來吝/泰闔吉/否闢凶)
	};
}

/** 六爻卦(hexInfo)之四象 */
export function siXiangOfHex(hex) {
	if (!hex) return null;
	return siXiang(hex.up, hex.lo);
}

// ── 幅度三分法 / 涨跌两分法 ─────────────────────────────
export function fuDu(gua) {
	if (!FUDU[gua]) return null;
	return { gua, zhuYao: ZHU_YAO_WEI[gua], fudu: FUDU[gua] };
}
/** 涨跌两分法:升卦=涨,降卦=跌(坎阳而降、离阴而升,注意颠倒属性)。 */
export function zhangDie(gua) {
	if (!GUA_GONG[gua]) return null;
	return SHENG_GUA.includes(gua) ? '涨' : '跌';
}

// ── 应期:三分法(旬) / 两分法(半月) ─────────────────────
// 🔴 与股市 fuDu/zhangDie 分开命名(后者不动,零回归):此二法用于「通用应期」(月内定位),
// 语义是「时段」而非「幅度/涨跌」;应期卦取用宫天盘卦(或旁推所得卦),由 UI/AI 层择定。
/** 三分法:上主爻卦(艮兑乾)→上旬、中主爻卦(坎离)→中旬、下主爻卦(震巽坤)→下旬。 */
export function sanFen(gua) {
	const xun = ZHU_YAO_WEI[gua];
	if (!xun) return null;
	return { gua, xun }; // xun ∈ 上|中|下
}
/** 两分法:升卦(乾艮震离)=阳=前半月、降卦(坎巽坤兑)=阴=后半月。 */
export function liangFen(gua) {
	if (!GUA_GONG[gua]) return null;
	const yang = SHENG_GUA.includes(gua);
	return { gua, ban: yang ? '前半' : '后半', yy: yang ? '阳' : '阴' };
}

// ── K线定用宫 ──────────────────────────────────────────
// body:'阳'|'阴';upper/lower=有无上/下影线;doji=十字星(阴阳莫辨)→ null 须手动。
export function klineYongGong({ body, upper = false, lower = false, doji = false } = {}) {
	if (doji) return null;
	if (body !== '阳' && body !== '阴') return null;
	const shadow = upper && lower ? '双影' : upper ? '仅上影' : lower ? '仅下影' : '无影';
	const hit = KLINE_YONG_GONG[`${body}线${shadow}`];
	if (!hit) return null;
	return { ...hit, gong: GUA_GONG[hit.gua], key: `${body}线${shadow}` };
}
