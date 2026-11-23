// 六爻起卦:卦名与爻文字、由爻值成卦、按时间 / 按手录爻起卦
// 从 GuaZhanMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { getGua64, Gua64, ZiList, Gua8 } from '../../gua/GuaConst.js';
import { littleEndian } from '../../gua/littleEndian.js';
import * as AstroConst from '../../../constants/AstroConst.js';

export function guaText(gua){
	if(!gua){
		return '';
	}
	const ord = gua.ord !== undefined ? `第${gua.ord}卦` : '';
	const house = gua.house ? `${gua.house.name || ''}宫${gua.house.elem || ''}` : '';
	return `${ord} ${gua.name || ''} ${gua.desc || ''} ${house}`.trim();
}

export function lineText(line){
	if(line === undefined || line === null){
		return '';
	}
	return `${line}`.trim();
}

// 从六爻线值(0阴/1阳,初爻→上爻)算任一卦对象。自给自足:AI挂载经 regenerateSixyaoSnapshot→buildTimeGua 时
// gua 无 guaDesc(故旧版只剩本卦),但 yao 六爻线值始终在 → 据此稳定算出 之/互/错/综卦,挂载与导出都全面。
export function guaFromYaoValues(values){
	if(!values || values.length !== 6 || values.some((v)=>v !== 0 && v !== 1)){
		return null;
	}
	const g = getGua64(littleEndian(values));
	const idx = g ? g.index : null;
	return (idx !== null && idx !== undefined && Gua64[idx]) ? Gua64[idx] : null;
}

// 时间起卦（梅花/时间确定式法）——纯函数，供 AI 挂载「起课时间」无头复用（与 genTimeGua 同口径）。
export function buildTimeGua(nongli){
	if(!nongli || !nongli.year || !nongli.time || nongli.monthInt === undefined || nongli.dayInt === undefined){
		return null;
	}
	const y = ZiList.indexOf(('' + nongli.year).substr(1)) + 1;
	const m = nongli.monthInt;
	const d = nongli.dayInt;
	const t = ZiList.indexOf(('' + nongli.time).substr(1)) + 1;
	let up = (y + m + d) % 8 - 1; up = up < 0 ? 7 : up;
	let down = (y + m + d + t) % 8 - 1; down = down < 0 ? 7 : down;
	let cyao = (y + m + d + t) % 6 - 1; cyao = cyao < 0 ? 5 : cyao;
	const upGua = Gua8[up];
	const downGua = Gua8[down];
	if(!upGua || !downGua){ return null; }
	const yao = [0, 0, 0, 0, 0, 0].map(() => ({ value: -1, change: false, color: AstroConst.AstroColor.Stroke, name: null }));
	for(let i = 0; i < downGua.value.length; i++){ yao[i].value = downGua.value[i]; }
	for(let i = 0; i < upGua.value.length; i++){ yao[i + 3].value = upGua.value[i]; }
	yao[cyao].change = true;
	const gua = getGua64(littleEndian(yao.map((x) => x.value)));
	const guaidx = gua ? gua.index : null;
	if(guaidx !== null && Gua64[guaidx]){
		for(let i = 0; i < yao.length; i++){ yao[i].name = Gua64[guaidx].yaoname[i]; }
	}
	return { yao, currentGua: guaidx, nongli };
}

// 按爻起卦(用户亲手摇出 / 报出的六爻)——纯函数,与 buildTimeGua 同形产物;装配与 onManualCast 逐步相同
// (emptyYao → 填爻值与动爻 → getCurrentGua → setupYao),仅爻源不同。lines = 0 阴 / 1 阳 ×6(初爻在前);moving = 动爻位 1-6。
export function buildLinesGua(lines, moving, nongli){
	if(!Array.isArray(lines) || lines.length !== 6 || lines.some((v) => v !== 0 && v !== 1)){ return null; }
	const mv = Array.isArray(moving) ? moving : [];
	const yao = lines.map((v, i) => ({ value: v, change: mv.indexOf(i + 1) >= 0, color: AstroConst.AstroColor.Stroke, name: null }));
	const gua = getGua64(littleEndian(lines));
	const guaidx = gua ? gua.index : null;
	if(guaidx === null || guaidx === undefined || !Gua64[guaidx]){ return null; }
	for(let i = 0; i < yao.length; i++){ yao[i].name = Gua64[guaidx].yaoname[i]; }
	return { yao, currentGua: guaidx, nongli: nongli || null };
}
