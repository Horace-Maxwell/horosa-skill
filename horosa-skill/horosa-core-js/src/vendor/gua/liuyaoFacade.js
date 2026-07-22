// 六爻断盘门面:按 settings 编排全引擎(结构/旺衰/月破空墓/用神/动变/神煞/六神/错综互/断诀/古法/应期),
// 为中栏、右栏页签、AI 快照提供单一真值源。默认不改既有输出字段与既有快照行(零回归);新结构走新增字段。
import { getXunEmpty, getGua64, LiuQi } from './GuaConst.js';
import { littleEndian } from './guaHelper.js';
import { LIUCHONG, LIUHE, shengKe, ZHI_YINYANG, TIANGAN, DIZHI, CHANGSHENG_STAGES, CHANGSHENG_START, CHANGSHENG_START_ALT } from './LiuYaoConst.js';
import { analyzeGua, fushenForGua, palaceTypeOf, parseYaoName, pureGuaOf, guaChongHe, guaSanHeHui } from './LiuYaoEngine.js';
import { analyzeYongShen } from './liuyaoYongShen.js';
import { analyzeDongBian, bianGuaOf } from './liuyaoDongBian.js';
import { annotateShenSha } from './liuyaoShenSha.js';
import { annotateShenShaEx } from './liuyaoShenShaEx.js';
import { annotateLiuShen, cuoGuaOf, zongGuaOf, huGuaOf } from './liuyaoLiuShen.js';
import { normalizeLiuyaoSettings } from './liuyaoSchools.js';
import { sanCengOnYaos, anDongOf, jueChuFengSheng, heChuFengChong, suiGuanRuMu, zhuGuiShangShen, wuGuiOf,
	suiJinFuChain, feiFuShengKe, fushenUsable, chengGangOf, zhenKongJueOf, mieMoOf, wangShuaiWithYuqi,
	jinShenBy, tuiShenBy, xinpaiScoreOf, jinSuoBaYao, LIUQIN_XIE, riYueYinDong } from './liuyaoDuanJue.js';
import { ganForYaos, nayinOf, shiShenOf, yueLiuShenOnYaos, zhiFuOf, shengJiangOf, sixteenChangesOf,
	sixteenPositionOf, guaShengOf as guaShengZhangOf, pastFutureOf, sanXianOf, baJieGuaQi, neiTaiOf,
	zhongQiByMonth, baJieByMonth, pickZhongQi, pickBaJie } from './liuyaoGuFa.js';
import { computeYingQi, qiRiByAsk } from './liuyaoYingQi.js';

// 关联卦(之/互/伏神/错/综)完整装卦:与本卦同口径;六亲一律以「本卦卦宫五行」为我(京房锚定);不递归。
function analyzeGuaFull(g, engCtx, s, benGongElem, c){
	if(!g || !g.yaoname){ return null; }
	const base = analyzeGua(g, { ...engCtx, movingPositions: [] });
	if(benGongElem && LiuQi[benGongElem]){
		base.yaos.forEach((y) => { if(y.wuxing){ y.liuqin = LiuQi[benGongElem][y.wuxing] || y.liuqin; } });
	}
	const liushen = s.sixGods ? annotateLiuShen(base.yaos, engCtx.dayGan) : null;
	const shensha = (s.shensha && s.shensha.on)
		? annotateShenSha(base.yaos, { dayGan: c.dayGan, dayZhi: c.dayZhi, yearGan: c.yearGan, yearZhi: c.yearZhi }, s.shensha)
		: null;
	// 关联卦亦配逐爻天干 + 日辰月建引动(装卦表「日·月」列同源填充,不再空列)。
	const gans = ganForYaos(g);
	const riYue = riYueYinDong(base.yaos, gans, c);
	return {
		name: g.name, index: g.index, settings: s,
		palaceType: base.palaceType, yaos: base.yaos, gans, riYue,
		guaShen: null, liuShen: liushen, shenSha: shensha, fushenAll: null, related: null,
	};
}

// gua: Gua64 条目;movingPositions:[1-6];
// ctx:{ dayGan, dayZhi, monthGan, monthZhi, monthNum, yearGan, yearZhi, hourZhi, jieqiName, kongPair? }
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

	const base = analyzeGua(gua, engCtx);
	const yong = analyzeYongShen(base.yaos, s.askType, { ...engCtx, movingPositions: moves }, s.yongOverride);
	const dongbian = analyzeDongBian(gua, moves, engCtx);
	// 进退神土路径开关(break=戌丑断开):覆写动变标记
	if(s.jinTuiTu === 'break' && dongbian.moves){
		dongbian.moves.forEach((m) => {
			m.jinShen = jinShenBy(m.ben.zhi, m.bian.zhi, 'break');
			m.tuiShen = tuiShenBy(m.ben.zhi, m.bian.zhi, 'break');
		});
	}
	if(s.bianyaoScope === 'blind' && dongbian.moves && dongbian.moves.length){
		const eff = [];
		dongbian.moves.forEach((m) => {
			base.yaos.forEach((y) => {
				if(y.pos === m.pos){ return; }
				const sk = shengKe(m.bian.wuxing, y.wuxing);
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

	let fushenAll = null;
	if(s.fushen === 'all'){
		const fu = fushenForGua(gua);
		fushenAll = fu ? fu.map((f) => ({ pos: f.pos, zhi: f.zhi, wuxing: f.wuxing, liuqin: f.liuqin })) : null;
	}

	const benGongElem = gua.house && gua.house.elem;
	const cuo = cuoGuaOf(gua), zong = zongGuaOf(gua), hu = huGuaOf(gua);
	const fuPure = pureGuaOf(gua);
	const bian = moves.length ? bianGuaOf(gua, moves) : null;
	const movingSet = new Set(moves);
	const pt = base.palaceType;
	const shiPos = pt ? pt.shi : 0;

	// ── 扩展块(全部按开关产出;关=null,零回归) ──
	// 年支源:立春(默认,干支年即 nongli 立春口径)/正月初一(nongli 农历年口径)——由 UI 依 yearBoundary 传对应 yearZhi
	const env = sanCengOnYaos(base.yaos, c); // 三层环境恒算(轻量),显示层控
	base.yaos.forEach((y, i) => {
		y.anDong = anDongOf(y);
		y.sanCeng = env.perYao[i] ? env.perYao[i].tags : [];
		if(s.yuqi){ y.yuqiStrong = wangShuaiWithYuqi(y.wuxing, c.monthZhi, true).strongByYuqi; }
		if(y.xunKong){ y.zhenKongJue = zhenKongJueOf(y.wuxing, c.monthZhi, y.dayRel && (y.dayRel.sheng || y.dayRel.same)); }
		if(y.yuePo){ y.yuepoDetail = { tianShi: y.zhi, fengHe: LIUHE[y.zhi], note: s.yuepoMode === 'always' ? '长期标破' : '当月为破,出月不破;逢填实/逢合之日应' }; }
	});
	const gans = ganForYaos(gua); // 逐爻天干(纳甲干)
	const riYue = riYueYinDong(base.yaos, gans, c); // 日月生克逐爻引动(5.4 最重要外力),恒算轻量
	const nayinDay = (c.dayGan && c.dayZhi) ? nayinOf(c.dayGan, c.dayZhi) : null;
	const shiShen = shiShenOf(gua, s.shishen);
	const yueLiuShenAnn = s.yueLiushen && c.monthNum ? yueLiuShenOnYaos(base.yaos, c.monthNum) : null;
	const shenShaEx = s.shenshaEx && s.shenshaEx.on
		? annotateShenShaEx(base.yaos, { monthNum: c.monthNum, monthZhi: c.monthZhi, dayGan: c.dayGan, dayZhi: c.dayZhi, yearZhi: c.yearZhi, shiZhi: shiPos ? base.yaos[shiPos - 1].zhi : '' }, s.shenshaEx.set)
		: null;

	// 断诀命中(doctrine)
	let duanJue = null;
	if(s.doctrine){
		const yongLiuqin = (yong && ['父母', '兄弟', '子孙', '妻财', '官鬼'].indexOf(yong.yong) >= 0)
			? yong.yong : (shiPos ? base.yaos[shiPos - 1].liuqin : '');
		const feiFu = base.yaos.map((y, i) => {
			const fu = (fushenAll && fushenAll[i]) || y.fushen;
			if(!fu){ return null; }
			return { pos: y.pos, ...feiFuShengKe({ zhi: y.zhi, wuxing: y.wuxing }, fu), usable: fushenUsable({ ...fu, xunKong: false, yuePo: false, wuxing: fu.wuxing }, y, engCtx, s.tuChangsheng) };
		}).filter(Boolean);
		duanJue = {
			anDong: base.yaos.filter((y) => y.anDong === '暗动').map((y) => y.pos),
			chongSan: base.yaos.filter((y) => y.anDong === '冲散(日破)').map((y) => y.pos),
			jueSheng: jueChuFengSheng(base.yaos, movingSet, engCtx, s.tuChangsheng),
			heChong: heChuFengChong(base.yaos, engCtx),
			suiGuan: suiGuanRuMu(base.yaos, { dayGan: c.dayGan, dayZhi: c.dayZhi, tuMode: s.tuChangsheng, shiPos, shiShenPos: shiShen ? shiShen.pos : 0, benmingZhi: s.benming }),
			zhuGui: zhuGuiShangShen(base.yaos, movingSet, shiPos, base.guaShen ? base.guaShen.body : ''),
			wuGui: wuGuiOf(base.yaos),
			suiJinFu: suiJinFuChain(base.yaos, movingSet, yongLiuqin, engCtx),
			chengGang: chengGangOf(base.yaos),
			mieMo: mieMoOf(gua.name, c.monthZhi),
			feiFu,
			xieQi: base.yaos.filter((y) => movingSet.has(y.pos) && LIUQIN_XIE[y.liuqin] === yongLiuqin).map((y) => ({ pos: y.pos, duan: `${y.liuqin}动泄${yongLiuqin}气` })),
			jinSuoShi: shiPos ? jinSuoBaYao(base.yaos[shiPos - 1], engCtx, s.tuChangsheng, null) : null,
			xinpaiShi: shiPos ? xinpaiScoreOf(base.yaos[shiPos - 1], (dongbian.moves || []).find((m) => m.pos === shiPos)) : null,
			// WP-7:新派量化除世爻,另出用神爻打分(古籍口径:世/用神并量);用神取定位主爻,不上卦则 null。
			xinpaiYong: (yong && yong.located && yong.located.yong && yong.located.yong.primary)
				? xinpaiScoreOf(base.yaos[yong.located.yong.primary - 1], (dongbian.moves || []).find((m) => m.pos === yong.located.yong.primary)) : null,
			xinpaiYongLiuqin: (yong && yong.located && yong.located.yong && yong.located.yong.primary) ? base.yaos[yong.located.yong.primary - 1].liuqin : '',
		};
	}

	// 古法进阶(gufa)
	let gufa = null;
	if(s.gufa){
		const zq = pickZhongQi(c.jieqiName) || zhongQiByMonth(c.monthZhi);
		const bj = pickBaJie(c.jieqiName) || baJieByMonth(c.monthZhi);
		const seq16 = sixteenChangesOf(fuPure);
		gufa = {
			shengJiang: zq ? shengJiangOf(gua, zq, movingSet, shiPos) : null,
			sixteen: seq16, sixteenPos: sixteenPositionOf(gua, fuPure),
			guaSheng: guaShengZhangOf(gua, base.yaos, liushen),
			pastFuture: pastFutureOf(gua, base.yaos),
			sanXian: sanXianOf(gua, bian, movingSet),
			baJie: bj ? { jie: bj, map: baJieGuaQi(bj, 'home'), neiTai: neiTaiOf(bj, TRIGRAM_NAME(gua.value.slice(0, 3))) } : null,
			zhiFu: zhiFuOf(base.yaos, c),
		};
	}

	// 应期
	let yingqi = null;
	if(s.yingqi && yong && yong.located && yong.located.yong && yong.located.yong.primary){
		const yy = base.yaos[yong.located.yong.primary - 1];
		const dm = (dongbian.moves || []).find((m) => m.pos === yy.pos) || null;
		const ziSun = base.yaos.find((x) => x.liuqin === '子孙');
		const gui = base.yaos.find((x) => x.liuqin === '官鬼');
		yingqi = {
			rules: computeYingQi(yy, dm, { dayZhi: c.dayZhi, monthZhi: c.monthZhi, tuMode: s.tuChangsheng }),
			byAsk: qiRiByAsk(s.askType, {
				yongZhi: yy.zhi, yongWx: yy.wuxing, ziSunZhi: ziSun ? ziSun.zhi : '',
				guiWx: gui ? gui.wuxing : '', shiZhi: shiPos ? base.yaos[shiPos - 1].zhi : '',
				guaShenBody: base.guaShen ? base.guaShen.body : '', tuMode: s.tuChangsheng,
			}),
			yongPos: yy.pos,
		};
	}

	// ── 典籍补齐派生(纯新增字段,不改既有输出;显示/AI 快照同源消费) ──
	const benCH = guaChongHe(gua);
	const bianCH = bian ? guaChongHe(bian) : '';
	// A1 世应关系:世×应 生克冲合比 + 俱空
	const yingPos = pt ? pt.ying : 0;
	let shiYingRel = null;
	if(shiPos && yingPos){
		const sy = base.yaos[shiPos - 1], yy = base.yaos[yingPos - 1];
		if(sy && yy){
			let rel = '';
			if(LIUCHONG[sy.zhi] === yy.zhi){ rel = '世应相冲'; }
			else if(LIUHE[sy.zhi] === yy.zhi){ rel = '世应相合'; }
			else { const sk = shengKe(sy.wuxing, yy.wuxing); rel = sk === '生' ? '世生应' : sk === '泄' ? '应生世' : sk === '克' ? '世克应' : sk === '耗' ? '应克世' : sk === '同' ? '比和' : ''; }
			const bothVoid = !!(sy.xunKong && yy.xunKong);
			const NOTE = { 世应相合: '相合主和谐、易成', 世生应: '我生彼、费力向外', 应生世: '彼来生我、得助', 世克应: '我制彼、主动可成', 应克世: '彼制我、受制难谋', 比和: '世应比和、平顺相当', 世应相冲: '相冲主对立、难成' };
			shiYingRel = { shiPos, yingPos, shiYao: { zhi: sy.zhi, wuxing: sy.wuxing, liuqin: sy.liuqin }, yingYao: { zhi: yy.zhi, wuxing: yy.wuxing, liuqin: yy.liuqin }, rel, bothVoid, note: bothVoid ? '世应俱空、人无准实、彼此无心' : (NOTE[rel] || '') };
		}
	}
	// A2 卦变吉凶:本卦×之卦 冲合转换(仅有变卦时出)
	let guaBianDuan = null;
	if(bian && benCH && bianCH){
		const M = { '六冲卦→六合卦': '先散后成', '六合卦→六冲卦': '先成后散', '六冲卦→六冲卦': '始终冲动、难持久', '六合卦→六合卦': '和缓持续' };
		const duan = M[`${benCH}→${bianCH}`];
		if(duan){ guaBianDuan = { ben: benCH, bian: bianCH, duan }; }
	}
	// A3 动态四态:独发/独静/尽发/尽静
	const mc = dongbian ? (dongbian.movingCount || 0) : 0;
	const DONGTAI = { 0: { tai: '尽静', note: '六爻皆静、以日月与用神旺衰定' }, 1: { tai: '独发', note: '一爻独动、力专而显、事之关键' }, 5: { tai: '独静', note: '五动一静、独静之爻为事之枢' }, 6: { tai: '尽发', note: '六爻皆动、以变卦与世用取向定' } };
	const dongTai = DONGTAI[mc] ? { count: mc, ...DONGTAI[mc] } : { count: mc, tai: '常态', note: '' };
	// A4 间爻:世应之间(三、四爻),中介/媒人/第三方
	const jianYao = [3, 4].map((p) => ({ pos: p, liuqin: base.yaos[p - 1] ? base.yaos[p - 1].liuqin : '', zhi: base.yaos[p - 1] ? base.yaos[p - 1].zhi : '' }));

	return {
		settings: s,
		gua: { name: gua.name, index: gua.index, value: gua.value.slice() },
		palaceType: pt,
		guaXing: { ben: benCH, bian: bianCH },
		heHui: guaSanHeHui(gua, movingSet).filter((h) => h.hasMoving),
		yaos: base.yaos,
		guaShen: s.guashen ? base.guaShen : null,
		yongShen: yong,
		dongBian: dongbian,
		shenSha: shensha,
		liuShen: liushen,
		fushenAll,
		related: {
			bian: bian ? analyzeGuaFull(bian, engCtx, s, benGongElem, c) : null,
			hu: analyzeGuaFull(hu, engCtx, s, benGongElem, c),
			fu: analyzeGuaFull(fuPure, engCtx, s, benGongElem, c),
			zong: analyzeGuaFull(zong, engCtx, s, benGongElem, c),
			cuo: analyzeGuaFull(cuo, engCtx, s, benGongElem, c),
		},
		kongPair, monthKong,
		// —— 新增面 ——
		env: env.env, gans, riYue, nayinDay, shiShen, yueLiuShenAnn, shenShaEx, duanJue, gufa, yingqi,
		// —— 典籍补齐派生 ——
		shiYingRel, guaBianDuan, dongTai, jianYao,
	};
}

// 内卦三爻 → 经卦名(八节内胎用)
function TRIGRAM_NAME(bits3){
	const key = (bits3 || []).join('');
	return ({ '111': '乾', '110': '兑', '101': '离', '100': '震', '011': '巽', '010': '坎', '001': '艮', '000': '坤' })[key] || '';
}

export function guaFromLines(lines){
	if(!Array.isArray(lines) || lines.length !== 6){ return null; }
	return getGua64(littleEndian(lines));
}
