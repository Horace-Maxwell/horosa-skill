// G16 单度主星 · 三分序(保罗式)变体 —— 纯前端派生,零后端。
// 默认体系(迦勒底连续序)由后端 perchart 算好直接显示,不经此模块;
// 此模块只负责三分序分支:每入新座按昼/夜重置,逐度循三分主星序。
import { TRIPLICITY } from './hellenisticData.js';

// 四元素流转序(火→土→风→水),与黄道十二座按序对应:
// 白羊/狮子/射手=火,金牛/处女/摩羯=土,双子/天秤/水瓶=风,巨蟹/天蝎/双鱼=水。
const ELEMENT_CYCLE = ['Fire', 'Earth', 'Air', 'Water'];

// 座序(0=白羊..11=双鱼)→ 元素索引(0=火/1=土/2=风/3=水)。
function signElementIndex(signIndex){
	return ((signIndex % 4) + 4) % 4;   // 白羊起火,四象循环
}

// 取某元素按昼/夜的首三分主星(Dorothean 三主表的 day / night)。
function triplicityRuler(elementKey, isDiurnal){
	const dor = (TRIPLICITY && TRIPLICITY.Dorothean) || {};
	const row = dor[elementKey];
	if(!row){ return null; }
	return isDiurnal ? (row.day || null) : (row.night || null);
}

// 三分序单度主星:lon=绝对黄经(0-360),isDiurnal=是否日生盘(决定昼/夜主星)。
// 算法:座内第 1 度(signlon∈[0,1))= 本座元素的当令(昼/夜)三分主星;
// 逐度沿元素流转(火→土→风→水)取各元素当令主星,循环;每入新座从本座元素重置。
export function monomoiriaTriplicity(lon, isDiurnal){
	const L = ((Number(lon) % 360) + 360) % 360;
	if(!Number.isFinite(L)){ return null; }
	const signIndex = Math.floor(L / 30);          // 0..11
	const degInSign = Math.floor(L - signIndex * 30);   // 0..29(座内整度,入新座即归零=重置)
	const startElem = signElementIndex(signIndex);
	const elemIdx = (startElem + degInSign) % 4;    // 沿四象流转
	return triplicityRuler(ELEMENT_CYCLE[elemIdx], !!isDiurnal);
}
