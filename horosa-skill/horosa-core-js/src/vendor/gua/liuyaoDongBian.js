// 六爻动变体系(WP-G):动爻→变卦(之卦)+ 变爻回头作用(生/克/冲/合)+ 化进退神 + 反吟伏吟 + 化空墓绝破。
// 变爻六亲仍以「本卦卦宫五行」为我(§3.11 传统派通例)。传统派变爻只回头作用本位;盲派扩展由 bianyaoScope 开关上层处理。
import { littleEndian } from './guaHelper.js';
import { getGua64, LiuQi } from './GuaConst.js';
import { ZHI_WUXING, LIUCHONG, LIUHE, shengKe } from './LiuYaoConst.js';
import { parseYaoName, changshengOf, isYuePo, isXunKong } from './LiuYaoEngine.js';

// §3.13 化进神(同五行地支顺进):寅卯/巳午/申酉/亥子/丑辰未戌(土循环)
const JIN_SHEN = { 寅: '卯', 巳: '午', 申: '酉', 亥: '子', 丑: '辰', 辰: '未', 未: '戌', 戌: '丑' };
// 化退神(地支逆退)
const TUI_SHEN = { 卯: '寅', 午: '巳', 酉: '申', 子: '亥', 戌: '未', 未: '辰', 辰: '丑', 丑: '戌' };

export function isJinShen(benZhi, bianZhi){ return JIN_SHEN[benZhi] === bianZhi; }
export function isTuiShen(benZhi, bianZhi){ return TUI_SHEN[benZhi] === bianZhi; }
export function isFuYin(benZhi, bianZhi){ return !!benZhi && benZhi === bianZhi; }            // §3.14 伏吟:地支相同
export function isFanYin(benZhi, bianZhi){ return !!benZhi && LIUCHONG[benZhi] === bianZhi; }  // 反吟:地支相冲

// 变爻对本位动爻的回头作用
export function huiTouOf(benZhi, benWx, bianZhi, bianWx){
	const sk = shengKe(bianWx, benWx); // 变 对 本
	return {
		sheng: sk === '生', // 回头生
		ke: sk === '克',    // 回头克
		chong: LIUCHONG[benZhi] === bianZhi, // 回头冲
		he: LIUHE[benZhi] === bianZhi,       // 回头合
	};
}

// 求变卦(之卦):翻动爻
export function bianGuaOf(benGua, movingPositions){
	if(!benGua || !benGua.value || !movingPositions || movingPositions.length === 0){ return null; }
	const v = benGua.value.slice();
	movingPositions.forEach((p) => { if(p >= 1 && p <= 6){ v[p - 1] = v[p - 1] ? 0 : 1; } });
	return getGua64(littleEndian(v));
}

// 逐动爻的变爻信息 + 回头作用 + 化进退/反伏吟 + 化空墓绝破
// ctx:{ monthZhi, dayZhi, kongPair, tuMode='water' }
export function bianYaoInfo(benGua, movingPositions, ctx){
	const c = ctx || {};
	const tuMode = c.tuMode || 'water';
	const bian = bianGuaOf(benGua, movingPositions);
	if(!bian){ return { bianGua: null, moves: [] }; }
	const benGongWx = benGua.house && benGua.house.elem; // 本卦卦宫五行(我)
	const moves = (movingPositions || []).slice().sort((a, b) => a - b).map((pos) => {
		const ben = parseYaoName((benGua.yaoname && benGua.yaoname[pos - 1]) || '');
		const bn = parseYaoName((bian.yaoname && bian.yaoname[pos - 1]) || '');
		const bianLiuqin = (benGongWx && bn.wuxing && LiuQi[benGongWx]) ? LiuQi[benGongWx][bn.wuxing] : '';
		const hui = huiTouOf(ben.zhi, ben.wuxing, bn.zhi, bn.wuxing);
		const cs = c.dayZhi ? changshengOf(bn.wuxing, c.dayZhi, tuMode) : '';
		return {
			pos,
			ben: { zhi: ben.zhi, wuxing: ben.wuxing, liuqin: ben.liuqin },
			bian: { zhi: bn.zhi, wuxing: bn.wuxing, liuqin: bianLiuqin },
			jinShen: isJinShen(ben.zhi, bn.zhi),
			tuiShen: isTuiShen(ben.zhi, bn.zhi),
			fuYin: isFuYin(ben.zhi, bn.zhi),
			fanYin: isFanYin(ben.zhi, bn.zhi),
			huiTou: hui,
			// 化空/化破(月破)/化墓/化绝
			huaKong: c.kongPair ? isXunKong(bn.zhi, c.kongPair) : false,
			huaPo: c.monthZhi ? isYuePo(bn.zhi, c.monthZhi) : false,
			huaMu: cs === '墓',
			huaJue: cs === '绝',
			bianChangsheng: cs,
		};
	});
	return { bianGua: { name: bian.name, index: bian.index }, moves };
}

// 卦级反吟/伏吟(内外卦相同→伏吟之局;内外卦相冲→反吟之局,多见震巽内外动)——返回标记供解读
export function guaFuFanYin(benGua, bianGua){
	if(!benGua || !bianGua){ return { guaFuYin: false, guaFanYin: false }; }
	// 上下卦地支首支比较(粗判:本卦初爻支 vs 变卦初爻支 相同=伏吟 / 相冲=反吟)
	const b0 = parseYaoName((benGua.yaoname && benGua.yaoname[0]) || '').zhi;
	const v0 = parseYaoName((bianGua.yaoname && bianGua.yaoname[0]) || '').zhi;
	return { guaFuYin: !!b0 && b0 === v0, guaFanYin: !!b0 && LIUCHONG[b0] === v0 };
}

// 汇总动变(供右栏「动变」页 + AI 快照)
export function analyzeDongBian(benGua, movingPositions, ctx){
	const info = bianYaoInfo(benGua, movingPositions, ctx);
	const bianGuaEntry = bianGuaOf(benGua, movingPositions);
	const guaYin = guaFuFanYin(benGua, bianGuaEntry);
	return { ...info, ...guaYin, movingCount: (movingPositions || []).length };
}
