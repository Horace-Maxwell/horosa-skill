// 辅盘「调波盘 / 龙盘 / 重置盘」快照里各自那段专属正文的单一来源:辅盘页出盘即存与 AI 无头复算(aiAnalysisContext/derivedLabsHeadless)
// 都调这里,两处逐字相同。只管拼行,不取数。
import * as AstroConst from '../constants/AstroConst.js';
import { AstroTxtMsg, AstroMsgCN } from '../../constants/AstroText.js';

// 星 / 点 / 星座写中文(与快照「星与虚点」表同一张名表:日 / 月 / 室女…;表里没有的原样)
const cn = (id)=>(id && (AstroTxtMsg[id] || AstroMsgCN[id])) || `${id || ''}`;
const signPos = (sign, signlon)=>`${sign ? `${cn(sign)} ` : ''}${signlon != null ? Number(signlon).toFixed(2) + '°' : ''}`;

// 调波数夹取整数 1-360(空串 / 小数原样下发,后端 int('') / int('2.5') 会抛错)
export const HARMONIC_DEFAULT = 9;
export function clampHarmonic(raw, fallback = HARMONIC_DEFAULT){
	const n = Number.parseInt(`${raw === undefined || raw === null ? '' : raw}`.trim(), 10);
	if(!Number.isFinite(n)){ return fallback; }
	return Math.min(360, Math.max(1, n));
}

const fix2 = (v)=>(v != null ? Number(v).toFixed(2) : '—');
function positionAndConjunctionLines(res, word){
	const out = [];
	((res && res.positions) || []).forEach((row)=>{
		if(row && row.id){ out.push(`${cn(row.id)}：本命黄经 ${fix2(row.natalLon)}° → ${word} ${signPos(row.sign, row.signlon)}`); }
	});
	((res && res.conjunctions) || []).forEach((c)=>{
		if(c && c.a && c.b){ out.push(`同频：${cn(c.a)} 合 ${cn(c.b)}（误差 ${c.orb != null ? Number(c.orb).toFixed(3) : '—'}）`); }
	});
	return out;
}

// [调波盘]:H 数 / 位置表 / 同频
export function harmonicSnapshotLines(res, harmonicShown){
	const r = res || {};
	const out = ['[调波盘]', `调波数：H${r.harmonic || harmonicShown || ''}`].concat(positionAndConjunctionLines(r, '调波'));
	return out.length > 1 ? out : [];
}

// 龙盘宫位口径(两家):whole = 按龙盘上升所在整座等分(缺省);shift = 本命宫头一并减去北交点黄经(整盘平移,落宫与本命一致)
export const DRACONIC_HOUSE_MODES = ['whole', 'shift'];
export const DRACONIC_HOUSE_LABELS = { whole: '整宫(随龙盘上升)', shift: '本命宫头平移(保留分宫制)' };
// 真 / 平交点随盘的 westNodeType('true' = 真交点;缺省平交点)
export function draconicNodeTypeLabel(chartObj){
	const v = chartObj && chartObj.params ? chartObj.params.westNodeType : undefined;
	return v === 'true' || v === true ? '真交点' : '平交点';
}
// [龙盘]:龙首归零基准 / 宫位口径 / 位置 / 同频
export function draconicSnapshotLines(res, houseMode, natalChartObj){
	const r = res || {};
	const out = ['[龙盘]'];
	if(r.nodeLon != null){ out.push(`北交点 ${Number(r.nodeLon).toFixed(2)}°（${draconicNodeTypeLabel(natalChartObj)}） → 归零白羊 0°（龙盘基准）`); }
	out.push(`宫位口径：${DRACONIC_HOUSE_LABELS[houseMode] || DRACONIC_HOUSE_LABELS.whole}${houseMode === 'shift' ? '，各星落宫与本命一致' : ''}`);
	return out.concat(positionAndConjunctionLines(r, '龙盘'));
}

// 重置盘:四角(上升 / 中天 / 下降 / 天底)重置前后对照
export const RELOCATION_ANGLE_IDS = [AstroConst.ASC, AstroConst.MC, AstroConst.DESC, AstroConst.IC];
export function relocationAnglesOf(chartShaped){
	const objs = (chartShaped && chartShaped.chart && chartShaped.chart.objects) || [];
	const map = {};
	objs.forEach((o)=>{ if(o && RELOCATION_ANGLE_IDS.indexOf(o.id) >= 0){ map[o.id] = o; } });
	return map;
}
// [重置盘] 专属段 + 按重置地点算的 [盘面细节] / [古典格局](段间空一行;回单元素数组 —— 行数组会滤掉空行)
export function relocationSnapshotSpecialty(natalChartObj, relocChart, relocLat, relocLon, extras){
	const { detailsText = '', classicalText = '' } = extras || {};
	const out = ['[重置盘]'];
	out.push(`重置地点：纬 ${relocLat} / 经 ${relocLon}`);
	try{
		const natal = relocationAnglesOf(natalChartObj);
		const reloc = relocationAnglesOf(relocChart);
		const pos = (o)=>(o ? signPos(o.sign, o.signlon) : '—');
		RELOCATION_ANGLE_IDS.forEach((id)=>{
			const n = natal && natal[id]; const r = reloc && reloc[id];
			if(n || r){ out.push(`${cn(id)}：本命 ${pos(n)} → 重置后 ${pos(r)}`); }
		});
	}catch(e){ /* 角点缺省不产行 */ }
	const lines = out.length > 1 ? out : [];
	return [[lines.join('\n'), detailsText, classicalText].filter(Boolean).join('\n\n')];
}
// 「可能性」(星落星座的断语):重置只换地点、出生 UT 不变 → 各星所落星座与本命相同,断语借本命那份(只借 PlanetSign)
export function withNatalPlanetSign(relocChart, natal){
	if(!relocChart || typeof relocChart !== 'object'){ return relocChart; }
	const own = relocChart.predict && relocChart.predict.PlanetSign;
	const natalSigns = natal && natal.predict && natal.predict.PlanetSign;
	if(own || !natalSigns){ return relocChart; }
	return { ...relocChart, predict: { ...(relocChart.predict || {}), PlanetSign: natalSigns } };
}
