// 六爻断盘门面(WP-J):按 settings 编排全引擎(结构/旺衰/月破空墓/用神/动变/神煞/六神/错综互),
// 为中栏、右栏8页签、AI 快照提供单一真值源。默认不改既有中栏与既有快照行(零回归);新结构数据走新面。
import { getXunEmpty, getGua64, LiuQi } from './GuaConst.js';
import { littleEndian } from './guaHelper.js';
import { LIUCHONG, LIUHE, shengKe } from './LiuYaoConst.js';
import { analyzeGua, fushenForGua, palaceTypeOf, parseYaoName, pureGuaOf, guaChongHe, guaSanHeHui } from './LiuYaoEngine.js';
import { analyzeYongShen } from './liuyaoYongShen.js';
import { analyzeDongBian, bianGuaOf } from './liuyaoDongBian.js';
import { annotateShenSha } from './liuyaoShenSha.js';
import { annotateLiuShen, cuoGuaOf, zongGuaOf, huGuaOf } from './liuyaoLiuShen.js';
import { normalizeLiuyaoSettings } from './liuyaoSchools.js';

// 关联卦(之/互/伏神/错/综)完整装卦:与本卦同口径出全部信息(六神/伏神/旺衰/状态/神煞),
// 六亲一律以「本卦卦宫五行」为我(京房锚定);关联卦自身为静卦(无动变),不再递归算其关联卦。
function analyzeGuaFull(g, engCtx, s, benGongElem, c){
	if(!g || !g.yaoname){ return null; }
	const base = analyzeGua(g, { ...engCtx, movingPositions: [] });
	// 六亲改按本卦宫(与本卦/中栏一致),并刷新依赖六亲的标记无;旺衰/状态/长生只依五行地支,不变
	if(benGongElem && LiuQi[benGongElem]){
		base.yaos.forEach((y) => { if(y.wuxing){ y.liuqin = LiuQi[benGongElem][y.wuxing] || y.liuqin; } });
	}
	const liushen = s.sixGods ? annotateLiuShen(base.yaos, engCtx.dayGan) : null;
	const shensha = (s.shensha && s.shensha.on)
		? annotateShenSha(base.yaos, { dayGan: c.dayGan, dayZhi: c.dayZhi, yearGan: c.yearGan, yearZhi: c.yearZhi }, s.shensha)
		: null;
	return {
		name: g.name, index: g.index,
		settings: s,
		palaceType: base.palaceType,
		yaos: base.yaos,
		guaShen: null,        // 卦身只论本卦
		liuShen: liushen,
		shenSha: shensha,
		fushenAll: null,      // 关联卦逐爻伏神(base.yaos[i].fushen 已含,按其自身本宫)
		related: null,        // 不递归
	};
}

// gua: Gua64 条目(本卦);movingPositions:[1-6];
// ctx:{ dayGan, dayZhi, monthZhi, yearGan, yearZhi, kongPair? }
export function analyzeLiuyao(gua, movingPositions, ctx, settings){
	if(!gua){ return null; }
	const s = normalizeLiuyaoSettings(settings);
	const c = ctx || {};
	const kongPair = c.kongPair || (c.dayGan && c.dayZhi ? getXunEmpty(c.dayGan, c.dayZhi) : '');
	const monthKong = (c.monthGan && c.monthZhi) ? getXunEmpty(c.monthGan, c.monthZhi) : '';
	const moves = (movingPositions || []).filter((p) => p >= 1 && p <= 6);
	const engCtx = {
		dayGan: c.dayGan, dayZhi: c.dayZhi, monthZhi: c.monthZhi,
		kongPair, tuMode: s.tuChangsheng, yuepoMode: s.yuepoMode,
		movingPositions: moves,
	};

	const base = analyzeGua(gua, engCtx); // {palaceType, guaShen, yaos[]}
	const yong = analyzeYongShen(base.yaos, s.askType, { ...engCtx, movingPositions: moves });
	const dongbian = analyzeDongBian(gua, moves, engCtx);
	// 盲派(bianyaoScope='blind'):变爻可作用本卦「他爻」(非本位)——算其生克冲合,供右栏动变显示(传统派不显)
	if(s.bianyaoScope === 'blind' && dongbian.moves && dongbian.moves.length){
		const eff = [];
		dongbian.moves.forEach((m) => {
			base.yaos.forEach((y) => {
				if(y.pos === m.pos){ return; } // 排除本位(本位=回头作用)
				const sk = shengKe(m.bian.wuxing, y.wuxing); // 变爻五行 对 本卦他爻
				const chong = LIUCHONG[m.bian.zhi] === y.zhi;
				const he = LIUHE[m.bian.zhi] === y.zhi;
				const tags = [sk === '生' ? '生' : '', sk === '克' ? '克' : '', chong ? '冲' : '', he ? '合' : ''].filter(Boolean);
				if(tags.length){ eff.push({ from: m.pos, to: y.pos, toLiuqin: y.liuqin, rel: tags.join('') }); }
			});
		});
		dongbian.blindEffects = eff;
	}
	const shensha = s.shensha && s.shensha.on
		? annotateShenSha(base.yaos, { dayGan: c.dayGan, dayZhi: c.dayZhi, yearGan: c.yearGan, yearZhi: c.yearZhi }, s.shensha)
		: null;
	const liushen = s.sixGods ? annotateLiuShen(base.yaos, c.dayGan) : null;

	// 飞伏:'all' 逐爻全标 / 'missing' 仅缺用神(base 已按 missing 填了 yao.fushen)
	let fushenAll = null;
	if(s.fushen === 'all'){
		const fu = fushenForGua(gua);
		fushenAll = fu ? fu.map((f) => ({ pos: f.pos, zhi: f.zhi, wuxing: f.wuxing, liuqin: f.liuqin })) : null;
	}

	const benGongElem = gua.house && gua.house.elem;
	const cuo = cuoGuaOf(gua), zong = zongGuaOf(gua), hu = huGuaOf(gua);
	const fu = pureGuaOf(gua);                 // 伏神卦=本宫首卦
	const bian = moves.length ? bianGuaOf(gua, moves) : null; // 之卦

	return {
		settings: s,
		gua: { name: gua.name, index: gua.index, value: gua.value.slice() },
		palaceType: base.palaceType,
		guaXing: {                       // 卦象性质(§5.7):六冲卦/六合卦 + 卦变(本→之)
			ben: guaChongHe(gua),
			bian: bian ? guaChongHe(bian) : '',
		},
		heHui: guaSanHeHui(gua, new Set(moves)).filter((h) => h.hasMoving), // 三合局/三会方(§1.5):三支齐现且有动方成局

		yaos: base.yaos,                 // 逐爻结构(地支/五行/六亲/世应/旺衰/日辰/月破/旬空/长生/入墓/飞伏)
		guaShen: s.guashen ? base.guaShen : null,
		yongShen: yong,                  // 用神/原忌仇 + 定位
		dongBian: dongbian,              // 变卦/变爻/回头/进退/反伏吟/化空墓绝破
		shenSha: shensha,                // 逐爻神煞(可关)
		liuShen: liushen,                // 逐爻六神取象(可关)
		fushenAll,                       // fushen==='all' 时逐爻全标
		related: {                       // 关联卦完整装卦(与本卦同口径,六亲以本卦宫为我):之/互/伏神/综/错
			bian: bian ? analyzeGuaFull(bian, engCtx, s, benGongElem, c) : null,   // 之卦(有动爻时)
			hu: analyzeGuaFull(hu, engCtx, s, benGongElem, c),                     // 互卦
			fu: analyzeGuaFull(fu, engCtx, s, benGongElem, c),                     // 伏神卦(本宫首卦)
			zong: analyzeGuaFull(zong, engCtx, s, benGongElem, c),                 // 综卦
			cuo: analyzeGuaFull(cuo, engCtx, s, benGongElem, c),                   // 错卦
		},
		kongPair,
		monthKong,
	};
}

// 从六爻线值(自下而上 1阳0阴)+ 动爻位 取本卦条目(供 UI 直接喂线值)
export function guaFromLines(lines){
	if(!Array.isArray(lines) || lines.length !== 6){ return null; }
	return getGua64(littleEndian(lines));
}
