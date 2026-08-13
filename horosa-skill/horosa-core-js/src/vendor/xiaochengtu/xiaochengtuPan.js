// 小成图 · 盘面层 —— 佈局(九宫落卦)/ 正推 / 旁推 / 数占 / 四象阖辟往来 / 幅度涨跌 / K线定用宫。
// 纯函数,零 UI 零接线。
import {
	DI_PAN, GUA_GONG, PANG_GONG, BU_JU_SLOTS,
	SHENG_GUA, YANG_GUA, FUDU, ZHU_YAO_WEI,
	SI_XIANG_MATRIX_BY_KOUJING, SI_XIANG_BASE, SI_XIANG_YI,
	KLINE_YONG_GONG,
	GUA_ZUO_ZHI, ZHI_YUE, ZHI_YANG, RI_XUN_PREFIX, NUM_HANZI, SHI_GONG_SUGGEST,
} from './xiaochengtuConst.js';

/** 问事荐宫(仅提示,不改任何计算):按各宫所主词表首命中者;无命中 → null。
 *  载例明载两条:「问出行看震宫,问来人看艮宫」;余词出各宫所主原文。 */
export function suggestGong(askEvent) {
	const s = `${askEvent || ''}`.trim();
	if (!s) return null;
	for (const item of SHI_GONG_SUGGEST) {
		const hit = item.words.find((w) => s.indexOf(w) >= 0);
		if (hit) return { gong: item.gong, gua: DI_PAN[item.gong], zhu: item.zhu, word: hit };
	}
	return null;
}

// ── 佈局:本卦/之卦(hexInfo)→ 天盘九宫落卦 ─────────────
// 9=本卦上 / 1=本卦下 / 3=之卦上 / 7=之卦下 /
// 4=本卦上互(爻345) / 2=本卦下互(爻234) / 8=之卦上互 / 6=之卦下互。
// 🔴 落宫映射单一真值源 = BU_JU_SLOTS(此前常量与本函数各存一份副本,改一处必漏另一处)。
export function buildPan(qi) {
	const { ben, zhi } = qi || {};
	if (!ben || !zhi) return null;
	const src = { benUp: ben.up, benLo: ben.lo, benShangHu: ben.shangHu, benXiaHu: ben.xiaHu,
		zhiUp: zhi.up, zhiLo: zhi.lo, zhiShangHu: zhi.shangHu, zhiXiaHu: zhi.xiaHu };
	const tianPan = {};
	Object.keys(BU_JU_SLOTS).forEach((g) => { tianPan[g] = src[BU_JU_SLOTS[g]]; });
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
// koujing:'zheng'(正传·乙本原文,默认) | 'yiwen'(异文·甲本情伪论所推);二者只「闢」一象之辞相反。
export function siXiang(upName, loName, koujing = 'zheng') {
	if (!GUA_GONG[upName] || !GUA_GONG[loName]) return null;
	const upSheng = SHENG_GUA.includes(upName);
	const loSheng = SHENG_GUA.includes(loName);
	let type;
	if (upSheng && loSheng) type = '往';
	else if (!upSheng && !loSheng) type = '來';
	else if (!upSheng && loSheng) type = '闔';
	else type = '闢';
	const dePei = YANG_GUA.includes(upName) !== YANG_GUA.includes(loName);
	const matrix = SI_XIANG_MATRIX_BY_KOUJING[koujing] || SI_XIANG_MATRIX_BY_KOUJING.zheng;
	return {
		up: upName, lo: loName, type,
		yi: SI_XIANG_YI[type],                       // 外引/内引/向心/离心
		dePei,                                        // 得配=一阴一阳(得配为情、失配为伪)
		qingWei: dePei ? '情' : '伪',                 // 情伪(「阴阳得配为情,阴阳失配为伪」)
		sheng: { up: upSheng ? '升' : '降', lo: loSheng ? '升' : '降' }, // 升降(独坎降、独离升)
		ci: matrix[type][dePei ? '得配' : '失配'],    // 得失配之辞(闢随口径)
		baseCi: SI_XIANG_BASE[type],                  // 图注基调(乾往悔/坤來吝/泰闔吉/否闢凶)
		koujing: SI_XIANG_MATRIX_BY_KOUJING[koujing] ? koujing : 'zheng',
	};
}

/** 六爻卦(hexInfo)之四象 */
export function siXiangOfHex(hex, koujing = 'zheng') {
	if (!hex) return null;
	return siXiang(hex.up, hex.lo, koujing);
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
/** 两分法(升降·半月):升卦(乾艮震离)=阳=前半月、降卦(坎巽坤兑)=阴=后半月。 */
export function liangFen(gua) {
	if (!GUA_GONG[gua]) return null;
	const yang = SHENG_GUA.includes(gua);
	return { gua, ban: yang ? '前半' : '后半', yy: yang ? '阳' : '阴' };
}
/** 两分法(阴阳·定支):卦之阴阳依说卦「乾坎艮震为阳、巽离坤兑为阴」,用于月建二支择一。
 *  🔴 与上「升降·半月」两分分治:坎、离二卦在两法下结论正相反(坎阳而降、离阴而升),不可混用。
 *  载例实证:「离属阴支,两分法得亥之为农历十月」—— 离在此法属阴(升降法则离属升/阳)。 */
export function liangFenZhi(gua) {
	if (!GUA_GONG[gua]) return null;
	const yang = YANG_GUA.includes(gua);
	return { gua, yy: yang ? '阳' : '阴' };
}

/** 日候选:卦数 N → 每月三个「N 日」(初N / 十N / 二十N),再由三分法定旬取一。 */
export function riCandidates(shu) {
	const n = Number(shu);
	if (!(n >= 1 && n <= 9)) return null;
	const hz = NUM_HANZI[n - 1];
	const byXun = { 上: `${RI_XUN_PREFIX.上}${hz}`, 中: `${RI_XUN_PREFIX.中}${hz}`, 下: `${RI_XUN_PREFIX.下}${hz}` };
	return { shu: n, hz, byXun, list: [byXun.上, byXun.中, byXun.下] };
}

// ── 应期推演(定日 + 定月) ───────────────────────────────
/** 🔴 本链条系【古籍单一载例逐步归纳】(「乾之兑」问来人一例),非书中另立之明文总则;
 *  书中总则只曰「其中有三分法与两分法之参用」。UI/AI 展示须标明「系载例归纳」。
 *  逐跳(载例原文对读):
 *   ① 起宫:用宫;用宫伏位则依旁推自旁宫起。
 *   ② 正推得日卦:「从艮宫巽正推得巽宫乾」—— 起宫天盘卦之宫,其天盘卦即日卦;其卦数即日数。
 *   ③ 日候选:「乾数六,每月有初六十六二十六」。
 *   ④ 三分定旬:「则用巽之旁推到震宫得兑…用三分法则兑为上旬初六日也」。
 *   ⑤ 旁推得月卦:「月当从日上推,乾六旁推坤宫又得乾」。
 *   ⑥ 月卦坐支:「乾坐戌亥二月建,此中二支只有其一」(单支卦则直取,无须两分)。
 *   ⑦ 两分定支:「又用乾正推视乾宫为离,离属阴支,两分法得亥」。
 *   ⑧ 定月:「之为农历十月,是为十月初六日到也」。 */
export function yingQiTui(pan, g0) {
	if (!pan || !pan.tianPan || !DI_PAN[g0]) return null;
	const tian = pan.tianPan;
	const steps = [];
	const push = (label, text) => { steps.push({ label, text }); };
	const fuWei = tian[g0] === DI_PAN[g0];
	const out = { start: g0, fuWei, steps, summary: '' };

	// ① 起宫(伏位自旁宫起)
	const startGong = fuWei ? PANG_GONG[g0] : g0;
	const startGua = startGong ? tian[startGong] : null;
	if (!startGua || !GUA_GONG[startGua]) return out;
	out.startGong = startGong;
	out.startGua = startGua;
	push('起宫', fuWei
		? `用宫 ${g0}${DI_PAN[g0]}宫天地盘同卦(伏位),依旁推自 ${startGong}${DI_PAN[startGong]}宫起,天盘得${startGua}`
		: `用宫 ${g0}${DI_PAN[g0]}宫,天盘得${startGua}`);

	// ② 正推一步得日卦 + ③ 日候选
	const g1 = GUA_GONG[startGua];
	const riGua = g1 ? tian[g1] : null;
	if (!riGua || !GUA_GONG[riGua]) return out;
	out.riGua = riGua;
	out.riShu = GUA_GONG[riGua];
	push('正推得日卦', `${startGua}之宫为${g1}(${DI_PAN[g1]}宫),其天盘得${riGua},${riGua}数${out.riShu}`);
	const cand = riCandidates(out.riShu);
	if (cand) {
		out.riCandidates = cand.list.slice();
		push('日候选', `每月有${cand.list.join('、')},此三个${cand.hz},须三分法定之`);
	}

	// ④ 三分定旬 → 定日
	const pg1 = PANG_GONG[g1];
	const xunGua = pg1 ? tian[pg1] : null;
	const sf = xunGua ? sanFen(xunGua) : null;
	if (sf && cand) {
		out.xunGua = xunGua;
		out.xun = sf.xun;
		out.ri = cand.byXun[sf.xun];
		push('三分定旬', `${startGua}旁推至 ${pg1}${DI_PAN[pg1]}宫得${xunGua},${xunGua}为${sf.xun}主爻卦 → ${sf.xun}旬,即${out.ri}`);
	}

	// ⑤ 旁推得月卦 + ⑥ 坐支
	const gY = PANG_GONG[GUA_GONG[riGua]];
	const yueGua = gY ? tian[gY] : null;
	const zuo = yueGua ? GUA_ZUO_ZHI[yueGua] : null;
	if (!zuo) { out.summary = out.ri || ''; return out; }
	out.yueGua = yueGua;
	out.zuoZhi = zuo.zhis.slice();
	out.zuoZhiInferred = zuo.inferred;
	push('旁推得月卦', `月当从日上推:${riGua}数${out.riShu},自 ${GUA_GONG[riGua]}${DI_PAN[GUA_GONG[riGua]]}宫旁推至 ${gY}${DI_PAN[gY]}宫得${yueGua},${yueGua}坐${zuo.zhis.join('')}${zuo.zhis.length > 1 ? '二月建' : '一月建'}`);

	// ⑦ 定支(双支则两分,单支直取)
	if (zuo.zhis.length === 1) {
		out.zhi = zuo.zhis[0];
		push('定支', `${yueGua}只坐一支,直取${out.zhi},无须两分`);
	} else {
		const gZ = GUA_GONG[yueGua];
		const dingZhiGua = gZ ? tian[gZ] : null;
		const lz = dingZhiGua ? liangFenZhi(dingZhiGua) : null;
		if (lz) {
			out.dingZhiGua = dingZhiGua;
			out.dingZhiYY = lz.yy;
			out.zhi = zuo.zhis.find((z) => (lz.yy === '阳' ? ZHI_YANG.includes(z) : !ZHI_YANG.includes(z)));
			push('两分定支', `又用${yueGua}正推视 ${gZ}${DI_PAN[gZ]}宫为${dingZhiGua},${dingZhiGua}属${lz.yy}支,两分法于${zuo.zhis.join('、')}中得${out.zhi}`);
		}
	}

	// ⑧ 定月
	if (out.zhi && ZHI_YUE[out.zhi]) {
		out.yue = ZHI_YUE[out.zhi];
		push('定月', `${out.zhi}为农历${out.yue}`);
	}
	out.summary = (out.yue && out.ri) ? `农历${out.yue}${out.ri}` : (out.yue || out.ri || '');
	return out;
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
