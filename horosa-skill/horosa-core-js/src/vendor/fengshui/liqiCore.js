// 风水 · 理气六派共享原语（纯函数，无 DOM，可单测）。
// 飞星核心移植 golden 基准,与内核基准字节级一致。
import {
	SHAN_24, OPP_GONG, SANHE_ZHI, SANHE_SHUANGSHAN, SANHE_STAGE, SANHE_JU_CS,
	XIANTIAN_POS, HOUTIAN_POS, POS_NAME, ZIBAI_STAR, TIXING_SHEN, TIXING_DISPUTED,
	SANHE_XIANGFA_STAGE, SANHE_XIANGFA_LIST, SANHE_XIANGFA_NOTE,
	JING_YANG, JING_YIN, NAYIN_60, GANZHI_60, DIZHI, GUA8_XIANTIAN_NUM,
	GUA64_TABLE, GUAYUN_PAIRS, GUAYUN_YUAN, BA_YAO_SHA, SI_DA_HUANGQUAN,
	SHAN_ORDER, SHAN_CENTER_DEG, FENJIN_GAN_JX,
	GUA64_CIRCLE, GUA64_CIRCLE_META, YAO_NAMES,
} from './fengshuiData.js';

// ── 飞星原语（内核基准）──────────────────────────────────────────────
// 飞泊步序：5→0,6→1,7→2,8→3,9→4,1→5,2→6,3→7,4→8。
export function idx(n) { return (n - 5 + 9) % 9; }
export function val(center, n, forward) {
	return forward ? ((center - 1 + idx(n)) % 9 + 1) : (((center - 1 - idx(n)) % 9 + 9) % 9 + 1);
}

// 宫(洛书数)+元龙 → 山名（入中本宫取同元龙之山定阴阳）。
const GONG_YUAN = (()=>{
	const m = {};
	Object.keys(SHAN_24).forEach((s)=>{ const [g, y, yy] = SHAN_24[s]; m[`${g}|${y}`] = [s, yy]; });
	return m;
})();

// 玄空飞星 下卦排盘（pan 移植）。入参：元运 yun(1-9)、向首山 xiangShan。
// 返回 {zuoShan, yunPan, shanPan, xiangPan, ge, gZuo, gXiang, yuanLong}。
// 🔴 元运必须是 1-9 整数：此前只守了山不守运，非法运会算出 0/−1 等越界星值，
//    非数入参更会在 GONG_YUAN[`${Vx}|…`][1] 上抛 TypeError（Vx 越界 → 查不到该键）。
function validYun(yun) { const n = Number(yun); return Number.isInteger(n) && n >= 1 && n <= 9; }

export function flyChart(yun, xiangShan) {
	const meta = SHAN_24[xiangShan];
	if (!meta || !validYun(yun)) { return null; }
	const [gXiang, yXiang, yyXiang] = meta;
	const gZuo = OPP_GONG[gXiang];
	const zuoShan = GONG_YUAN[`${gZuo}|${yXiang}`][0];   // 坐山：与向同元龙、在坐宫
	const yunPan = {};
	for (let n = 1; n <= 9; n++) { yunPan[n] = val(yun, n, true); }
	// 向盘
	const Vx = yunPan[gXiang];
	const fx = (Vx === 5) ? (yyXiang === +1) : (GONG_YUAN[`${Vx}|${yXiang}`][1] === +1);
	const xiangPan = {};
	for (let n = 1; n <= 9; n++) { xiangPan[n] = val(Vx, n, fx); }
	// 山盘（坐山元龙 = 向山元龙）
	const Vs = yunPan[gZuo];
	const yyZuo = SHAN_24[zuoShan][2];
	const fs = (Vs === 5) ? (yyZuo === +1) : (GONG_YUAN[`${Vs}|${yXiang}`][1] === +1);
	const shanPan = {};
	for (let n = 1; n <= 9; n++) { shanPan[n] = val(Vs, n, fs); }
	// 格局
	const ge = geOf(shanPan, xiangPan, gZuo, gXiang, yun);
	return { zuoShan, xiangShan, yun, yunPan, shanPan, xiangPan, ge, gZuo, gXiang, yuanLong: yXiang };
}

// 四大格局判定（下卦/替卦共用，逻辑与原内联一致）。
function geOf(shanPan, xiangPan, gZuo, gXiang, yun) {
	const wmt = (shanPan[gZuo] === yun);     // 旺山（当运山星到坐）
	const wmx = (xiangPan[gXiang] === yun);  // 旺向（当运向星到向）
	const ssx = (shanPan[gXiang] === yun);   // 当运山星到向
	const sxz = (xiangPan[gZuo] === yun);    // 当运向星到坐
	if (wmt && wmx) { return '旺山旺向'; }
	if (ssx && sxz) { return '上山下水'; }
	if (ssx && xiangPan[gXiang] === yun) { return '双星到向'; }
	if (shanPan[gZuo] === yun && sxz) { return '双星到坐'; }
	return '其他/侧局';
}

// 替星查询（方案 shen 沈氏 / youbi 右弼9 / bengong 本宫数）。正统古法。
export function tixingOf(shan, variant = 'shen') {
	if (TIXING_DISPUTED.has(shan)) {
		if (variant === 'youbi') { return 9; }
		if (variant === 'bengong') { return SHAN_24[shan][0]; }
	}
	return TIXING_SHEN[shan];
}

// 替卦（兼向起星）排盘：入中数改用替星，顺逆/元龙判定同下卦。正统古法。
//   variant: shen|youbi|bengong；五黄无替仍用 5。
export function flyChartTi(yun, xiangShan, variant = 'shen') {
	const meta = SHAN_24[xiangShan];
	if (!meta || !validYun(yun)) { return null; }
	const [gXiang, yXiang, yyXiang] = meta;
	const gZuo = OPP_GONG[gXiang];
	const zuoShan = GONG_YUAN[`${gZuo}|${yXiang}`][0];
	const yunPan = {};
	for (let n = 1; n <= 9; n++) { yunPan[n] = val(yun, n, true); }
	// 向盘替卦：运盘向首数所落宫、与向首同元龙之山 → 替星入中。
	const Vx = yunPan[gXiang];
	let cx; let fx;
	if (Vx === 5) { cx = 5; fx = (yyXiang === +1); }
	else { const [sX, yyX] = GONG_YUAN[`${Vx}|${yXiang}`]; cx = tixingOf(sX, variant); fx = (yyX === +1); }
	const xiangPan = {};
	for (let n = 1; n <= 9; n++) { xiangPan[n] = val(cx, n, fx); }
	// 山盘替卦
	const Vs = yunPan[gZuo];
	const yyZuo = SHAN_24[zuoShan][2];
	let cs; let fs;
	if (Vs === 5) { cs = 5; fs = (yyZuo === +1); }
	else { const [sS, yyS] = GONG_YUAN[`${Vs}|${yXiang}`]; cs = tixingOf(sS, variant); fs = (yyS === +1); }
	const shanPan = {};
	for (let n = 1; n <= 9; n++) { shanPan[n] = val(cs, n, fs); }
	const ge = geOf(shanPan, xiangPan, gZuo, gXiang, yun);
	return {
		zuoShan, xiangShan, yun, yunPan, shanPan, xiangPan, ge, gZuo, gXiang, yuanLong: yXiang,
		method: '替卦', tiVariant: variant, sameAsXiaGua: (cx === Vx && cs === Vs),
	};
}

// ── 三合 十二长生（内核基准）：某双山地支在某局处第几长生 ──────────────────
export function sanheStageAt(zhi, ju) {
	const cs = SANHE_JU_CS[ju];
	const off = ((SANHE_ZHI.indexOf(zhi) - SANHE_ZHI.indexOf(cs)) % 12 + 12) % 12;
	return SANHE_STAGE[off];
}
// 全周表：12 双山 × 4 局。
export function sanheChangshengTable() {
	return SANHE_ZHI.map((z)=>({
		zhi: z,
		shuangshan: SANHE_SHUANGSHAN[z],
		火局: sanheStageAt(z, '火局'),
		金局: sanheStageAt(z, '金局'),
		水局: sanheStageAt(z, '水局'),
		木局: sanheStageAt(z, '木局'),
	}));
}

// ── 乾坤国宝 先后天位（内核基准）：坐山卦 → {后天方位, 先天位(主丁), 后天位(主财)} ──
export function qkgbPositions(zuoGua) {
	if (!(zuoGua in HOUTIAN_POS)) { return null; }
	const XT_AT = {};   // 方位→先天卦（反查）
	Object.keys(XIANTIAN_POS).forEach((k)=>{ XT_AT[XIANTIAN_POS[k]] = k; });
	const xtw = XIANTIAN_POS[zuoGua];           // 先天位 = 坐卦在先天图方位
	const zw = HOUTIAN_POS[zuoGua];             // 坐卦后天方位
	const guaAtXt = XT_AT[zw];                  // 该方位在先天属什么卦
	const htw = HOUTIAN_POS[guaAtXt];           // 该卦后天方位
	return {
		zuoGua,
		houtianFang: POS_NAME[zw], houtianFangPos: zw,
		xianTianWei: POS_NAME[xtw], xianTianWeiPos: xtw,     // 主丁
		houTianWei: POS_NAME[htw], houTianWeiPos: htw,       // 主财
	};
}

// ── 紫白 年入中（内核基准 year_center）：11 − 年数字根，三元逐年逆退 ────────
export function zibaiYearCenter(year) {
	// 净化:负/小数/非数 → 取绝对整数,避免 '-' 等字符令数字根 NaN(非法流年防御)。
	let s = String(Math.abs(Math.trunc(Number(year) || 0))).split('').reduce((a, d)=>a + (+d), 0);
	while (s > 9) { s = String(s).split('').reduce((a, d)=>a + (+d), 0); }
	let c = 11 - s;
	if (c > 9) { c -= 9; }
	if (c <= 0) { c += 9; }
	return c;
}
export function zibaiYearStar(year) {
	const c = zibaiYearCenter(year);
	return { center: c, star: ZIBAI_STAR[c] };
}

// ── 八宅 命卦（正统古法「数字相加古法」，跨世纪通用，与公式法等价）──────────
//   n = 出生公历年四位数字反复相加至个位(1-9);男 = 11−n(得10还原1)、女 = 4+n(>9减9);
//   余 5 → 男坤(2)/女艮(8);余 0 作 9。立春为界由调用方传所属命理年(默认公历年)。
export function mingGua(year, isMale) {
	let n = String(year).split('').reduce((a, d)=>a + (+d), 0);
	while (n > 9) { n = String(n).split('').reduce((a, d)=>a + (+d), 0); }
	let g = isMale ? (11 - n) : (4 + n);
	if (g === 10) { g = 1; }          // 男得 10 还原 1
	if (g > 9) { g -= 9; }            // 女 >9 减 9
	if (g === 0) { g = 9; }           // 余 0 作 9（离）
	if (g === 5) { return isMale ? 2 : 8; }   // 中宫寄坤(男)/艮(女)
	return g;
}

// 命卦 → 东西四命组（坎离震巽=东四 / 乾坤艮兑=西四）。
const EAST_GROUP = new Set([1, 9, 3, 4]);   // 坎离震巽
export function mingGroup(gua) { return EAST_GROUP.has(gua) ? '东四命' : '西四命'; }

// ══════════════════════════════════════════════════════════════════════════
// 补齐波次 · 共享原语（纯函数）。依赖顶部 import 的 fengshuiData 常量。
// ══════════════════════════════════════════════════════════════════════════

// ── 净阴净阳（8.2.3）：山名 → '阳'|'阴'|null（子午卯酉按坎离震兑卦归）──────────
export function najiaYinYang(shan) {
	if (JING_YANG.has(shan)) { return '阳'; }
	if (JING_YIN.has(shan)) { return '阴'; }
	return null;
}

// ── 六十甲子纳音（10.1）：干支 → {name, wuxing}；年干支速算 ────────────────────
export function nayinOf(ganzhi) { return NAYIN_60[ganzhi] || null; }
export function yearGanZhi(year) {
	const y = Math.trunc(Number(year) || 0);
	const i = ((y - 4) % 60 + 60) % 60;   // 公元 4 年 = 甲子
	return GANZHI_60[i];
}
export function yearZhiOf(year) { return yearGanZhi(year).slice(-1); }

// ── 三合四大局立向（5.9）：由局之长生环反推每种向法的向双山 ────────────────────
//   changshengRing: [{shuangshan, zhi, stage}]（sanhe 已算的当局环）。
export function sanheXiangFaAll(changshengRing) {
	if (!Array.isArray(changshengRing)) { return []; }
	return SANHE_XIANGFA_LIST.map((type)=>{
		const stage = SANHE_XIANGFA_STAGE[type];
		const cell = changshengRing.find((c)=>c.stage === stage);
		return { type, stage, shuangshan: cell ? cell.shuangshan : null, note: SANHE_XIANGFA_NOTE[type] };
	});
}

// ── 黄泉八曜煞（5.5）：坐山卦 → 忌方支；向 → 四大黄泉忌方 ──────────────────────
export function huangquanBaYao(zuoGua) { return BA_YAO_SHA[zuoGua] || null; }
export function huangquanSiDa(xiangShan) { return SI_DA_HUANGQUAN[xiangShan] || null; }

// ── 拨砂消砂五格（5.11）：以向五行为「我」，砂五行 → 五格 ─────────────────────
const WX_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
const WX_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };
export function boshaWuGe(myWuxing, shaWuxing) {
	if (!myWuxing || !shaWuxing) { return null; }
	if (WX_SHENG[shaWuxing] === myWuxing) { return { ge: '生格', rel: '砂生我(印)', jx: 'good', zhu: '荫庇·贵人·添丁' }; }
	if (shaWuxing === myWuxing) { return { ge: '旺格', rel: '砂同我(比和)', jx: 'good', zhu: '兴旺·助力' }; }
	if (WX_KE[myWuxing] === shaWuxing) { return { ge: '财格', rel: '我克砂(奴)', jx: 'mild', zhu: '得财(须我强)' }; }
	if (WX_SHENG[myWuxing] === shaWuxing) { return { ge: '泄格', rel: '我生砂(泄)', jx: 'bad', zhu: '退气·耗损' }; }
	if (WX_KE[shaWuxing] === myWuxing) { return { ge: '煞格', rel: '砂克我(官鬼)', jx: 'bad', zhu: '伤丁·官非·横祸' }; }
	return null;
}

// ── 乾坤国宝 龙门八局 九大水位（7.B.1/3/7）──────────────────────────────────
// 后天八卦方位度（坎北0·艮东北45·震东90·巽东南135·离南180·坤西南225·兑西270·乾西北315）。
const GONG_DEG = { 1: 0, 8: 45, 3: 90, 4: 135, 9: 180, 2: 225, 7: 270, 6: 315 };
const DEG_GONG = (()=>{ const m = {}; Object.keys(GONG_DEG).forEach((g)=>{ m[GONG_DEG[g]] = +g; }); return m; })();
function degToGong(deg) { return DEG_GONG[((deg % 360) + 360) % 360]; }
// 坐山卦 → 九水位（先天/后天/案劫/天劫/地刑几何确定;宾/客/辅/正窍标依局图）。
export function qkgbFullPositions(zuoGua) {
	const base = qkgbPositions(zuoGua);
	if (!base) { return null; }
	const zw = base.houtianFangPos;                     // 坐卦后天宫
	const xiangGong = OPP_GONG[zw] || zw;               // 向首宫（案劫）
	const xiangDeg = GONG_DEG[xiangGong];
	const tianJieGong = degToGong(xiangDeg - 45);       // 天劫=向左前
	const diXingGong = degToGong(xiangDeg + 45);        // 地刑=向右前
	const pos = (gong, name, meta)=>({ gong, name, posName: gong != null ? POS_NAME[gong] : '依局图', ...meta });
	return {
		zuoGua, xiangGong,
		xianTianWeiPos: base.xianTianWeiPos, houTianWeiPos: base.houTianWeiPos,
		list: [
			pos(base.xianTianWeiPos, '先天位', { role: '主丁', want: 'come', jx: 'good' }),
			pos(base.houTianWeiPos, '后天位', { role: '主财', want: 'come', jx: 'good' }),
			pos(xiangGong, '案劫位', { role: '向首明堂', want: 'go', jx: 'neutral' }),
			pos(tianJieGong, '天劫位', { role: '最凶·向左前', want: 'go', jx: 'bad' }),
			pos(diXingGong, '地刑位', { role: '刑伤·向右前', want: 'none', jx: 'bad' }),
			pos(null, '宾位', { role: '客财外姓', want: 'come', jx: 'neutral', tuFig: true }),
			pos(null, '客位', { role: '女口外家', want: 'come', jx: 'neutral', tuFig: true }),
			pos(null, '辅卦位', { role: '辅佐旺丁', want: 'come', jx: 'neutral', tuFig: true }),
			pos(null, '正窍位', { role: '出水口·消库', want: 'go', jx: 'neutral', tuFig: true }),
		],
	};
}

// ── 玄空大卦 64卦识别 + 卦运结构（6.7/6.8，框架版·卦运须按易盘）─────────────────
//   下卦(内)、上卦(外) 卦名 → 重卦名 + 先天数 + 结构卦运（合十对/上下元）。
export function gua64Of(lowerGua, upperGua) {
	const t = GUA64_TABLE[lowerGua];
	if (!t || !t[upperGua]) { return null; }
	const name = t[upperGua];
	const nLow = GUA8_XIANTIAN_NUM[lowerGua];
	const nUp = GUA8_XIANTIAN_NUM[upperGua];
	const pure = (lowerGua === upperGua);                     // 八纯卦=父母卦
	return {
		name, lowerGua, upperGua, xianTianLow: nLow, xianTianUp: nUp, pure,
		// 结构卦运：以两经卦先天数之和取模定「结构位」(1-9)，仅作框架推定，须按易盘校。
		structYun: ((nLow + nUp - 2) % 9) + 1,
		heShiPair: null,   // 由 dagua 结合用户卦运方案补
	};
}
// ── 兼向度数自动判别（4.5/4.12）：向首度数 → 下卦/兼向替卦/空亡/出卦 ──────────
//   中心±3°下卦;3-6°兼向替卦;6-7.5°深兼(同卦)或出卦大空亡(异卦);近山缝小空亡。
export function jianXiangByDeg(deg, boundaryDeg = 3) {
	const d = ((Number(deg) % 360) + 360) % 360;
	const idx = Math.floor(((d - 337.5 + 360) % 360) / 15) % 24;
	const shan = SHAN_ORDER[idx];
	const center = SHAN_CENTER_DEG[shan];
	let dist = ((d - center + 540) % 360) - 180;   // 有符号偏中心度(-7.5~7.5)
	if (dist > 180) { dist -= 360; } if (dist < -180) { dist += 360; }
	const adj = SHAN_ORDER[(idx + (dist >= 0 ? 1 : -1) + 24) % 24];   // 兼向侧邻山
	const sameGua = SHAN_24[shan] && SHAN_24[adj] && SHAN_24[shan][0] === SHAN_24[adj][0];
	const ad = Math.abs(dist);
	let mode; let jian = false; let kong = false;
	if (ad <= boundaryDeg) { mode = '下卦(正向)'; }
	else if (ad <= 6) { mode = `兼${adj}${ad.toFixed(1)}°(替卦)`; jian = true; }
	else if (ad < 7.4) { jian = true; mode = sameGua ? `深兼${adj}(卦内·替卦)` : `兼${adj}·近异卦界(出卦风险)`; if (!sameGua) { kong = true; } }
	else { mode = sameGua ? '骑山缝·小空亡' : '出卦·大空亡(乖戾大凶)'; kong = true; jian = true; }
	return { xiangShan: shan, dist: +dist.toFixed(2), adjShan: adj, sameGua, mode, jian, kong };
}

// ── 三合线法：穿山72龙/透地60龙/120分金（5.12-5.14，通行三合盘·需按门派校）──
// 罗盘顺时针递增，甲子起壬山初(337.5°)。位置性旺相/孤虚/空亡可靠;干支标注注需按门派校。
const XIANFA_ORIGIN = 337.5;   // 壬山起点
function normDeg(deg) { return ((Number(deg) % 360) + 360) % 360; }
function offsetFromOrigin(deg) { return (normDeg(deg) - XIANFA_ORIGIN + 360) % 360; }
// 度 → 二十四山名。
export function shanAtDeg(deg) {
	const idx = Math.floor(offsetFromOrigin(deg) / 15) % 24;
	return SHAN_ORDER[idx];
}
// 穿山72龙：每山3龙(5°)，中龙正气旺相、边龙孤虚。
export function chuanshanAt(deg) {
	const off = offsetFromOrigin(deg);
	const shan = SHAN_ORDER[Math.floor(off / 15) % 24];
	const sub = Math.floor((off % 15) / 5);                       // 0/1/2
	const ganzhi = GANZHI_60[Math.floor(off / 5) % 60];           // 72格循环60甲子(需按门派校)
	const positional = sub === 1 ? '正气旺相' : '孤虚（边龙）';
	return { shan, longIndex: sub, ganzhi, positional, jx: sub === 1 ? 'good' : 'bad' };
}
// 透地60龙：360°/60=6°/龙，甲己龙空亡。
export function toudiAt(deg) {
	const off = offsetFromOrigin(deg);
	const ganzhi = GANZHI_60[Math.floor(off / 6) % 60];
	const gan = ganzhi[0];
	const kong = (gan === '甲' || gan === '己');
	return { shan: SHAN_ORDER[Math.floor(off / 15) % 24], ganzhi, nayin: nayinOf(ganzhi), kong, jx: kong ? 'bad' : 'good' };
}
// 120分金：每山5分金(3°)，中3旺相(位置)、边2空亡；干支天干旺相/孤虚/龟甲空亡。
export function fenjinAt(deg) {
	const off = offsetFromOrigin(deg);
	const shan = SHAN_ORDER[Math.floor(off / 15) % 24];
	const sub = Math.floor((off % 15) / 3);                       // 0-4
	const ganzhi = GANZHI_60[Math.floor(off / 3) % 60];           // 120=60×2
	const ganJx = FENJIN_GAN_JX[ganzhi[0]] || 'neutral';
	const positional = (sub >= 1 && sub <= 3) ? '旺相(取)' : '空亡(避)';
	return { shan, fenIndex: sub, ganzhi, ganJx, positional, jx: (sub >= 1 && sub <= 3 && ganJx === 'good') ? 'good' : (positional === '空亡(避)' || ganJx === 'void' ? 'bad' : 'neutral') };
}

// ── 六十四卦圆图 度数落卦落爻（6.1）────────────────────────────────────────
// 每卦 5.625°、每爻 0.9375°。爻序沿本宫内的卦序方向累进（东半宫度数递减、西半递增），
// 与圆图两仪分翼一致；各家易盘爻序方向略异，须按所宗盘校。
export function gua64AtDeg(deg) {
	const d = normDeg(deg);
	const key = (x)=>((x - GUA64_CIRCLE_META.startDeg) % 360 + 360) % 360;
	const k = key(d);
	// 圆图按 startDeg 顺时针等分，直接定位（不遍历比较，避免边界浮点漏格）。
	const gi = Math.min(63, Math.floor(k / GUA64_CIRCLE_META.degPerGua));
	const cell = GUA64_CIRCLE[gi];
	const offIn = k - gi * GUA64_CIRCLE_META.degPerGua;                       // 0..5.625（顺时针入卦度）
	const along = cell.descending ? (GUA64_CIRCLE_META.degPerGua - offIn) : offIn;   // 沿本宫卦序方向
	const yaoIndex = Math.min(5, Math.max(0, Math.floor(along / GUA64_CIRCLE_META.degPerYao)));
	return {
		gua: cell.name, guaIndex: gi, lower: cell.lower, upper: cell.upper, sector: cell.sector,
		yao: YAO_NAMES[yaoIndex], yaoIndex, degInGua: +offIn.toFixed(4),
		deg0: cell.deg0, deg1: cell.deg1, center: cell.center,
		shan: shanAtDeg(d),
	};
}

export { GUAYUN_PAIRS, GUAYUN_YUAN, SANHE_STAGE };
