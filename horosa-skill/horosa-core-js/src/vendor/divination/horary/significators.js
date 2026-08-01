// divination/horary/significators.js
// 问题类别 → 征象星指派（按宫位/转宫 + 自然征象星）。
// 问卜者恒为 1宫主 + 月亮；事项为 用事宫主 + 自然征象星。
import { SIGNS } from '../data/signs.js';

// category → { quesitedHouse, naturalSig[], roleLabels }
export const CATEGORY_DEF = {
	general: { quesitedHouse: null, natural: [], quesitedLabel: '事项', note: '综合：事项守护星取月亮下一个入相的星 / 相关宫主。' },
	wealth: { quesitedHouse: 2, natural: ['fortune', 'jupiter'], quesitedLabel: '财物' },
	family: { quesitedHouse: 3, natural: [], quesitedLabel: '兄弟/亲属' },
	property: { quesitedHouse: 4, natural: ['saturn', 'moon'], quesitedLabel: '房产/田宅' },
	// 父/母宫位由 opts.parentHousesVariant 动态决定(传统 4父/10母 vs 现代 4母/10父),
	// 在 assignSignificators 内按 variant 改写 quesitedHouse——CATEGORY_DEF 静态表只放缺省。
	father: { quesitedHouse: 4, natural: ['sun', 'saturn'], quesitedLabel: '父亲', parentRole: 'father' },
	mother: { quesitedHouse: 10, natural: ['moon', 'venus'], quesitedLabel: '母亲', parentRole: 'mother' },
	pregnancy: { quesitedHouse: 5, natural: ['jupiter', 'venus', 'moon'], quesitedLabel: '子嗣' },
	health: { quesitedHouse: 6, natural: [], quesitedLabel: '疾病', patientIsQuerent: true },
	marriage: { quesitedHouse: 7, natural: ['venus'], quesitedLabel: '对象/婚姻' },
	lawsuit: { quesitedHouse: 7, natural: ['mars'], quesitedLabel: '对手' },
	theft: { quesitedHouse: 7, natural: [], quesitedLabel: '盗贼/失物', theft: true },
	death: { quesitedHouse: 8, natural: ['saturn'], quesitedLabel: '死亡/遗产' },
	travel: { quesitedHouse: 9, natural: ['mercury'], quesitedLabel: '旅行/远行' },
	career: { quesitedHouse: 10, natural: ['sun'], quesitedLabel: '职位/事业' },
	hope: { quesitedHouse: 11, natural: ['jupiter'], quesitedLabel: '愿望/朋友' },
	enemy: { quesitedHouse: 12, natural: [], quesitedLabel: '私敌' },
	// B3/B7-失物 专题补类（2026-07 批2）：消息/书信=3宫+水星;失物(非盗窃)=2宫动产+月亮线索。
	message: { quesitedHouse: 3, natural: ['mercury'], quesitedLabel: '消息/书信' },
	lost: { quesitedHouse: 2, natural: ['moon'], quesitedLabel: '失物', lost: true },
};

export function ascRulerKey(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}

// ── 转宫法/衍生宫（05§5）：「P 宫的第 T 宫」→ 本盘第 R 宫。
//  经典验证例：兄弟的钱 3+2→4;配偶的钱 7+2→8;朋友的事业 11+10→8;孙子女 5+5→9。──
export function turnedHouseOf(pHouse, tHouse){
	const P = Number(pHouse); const T = Number(tHouse);
	if(!(P >= 1 && P <= 12 && T >= 1 && T <= 12)) return null;
	return ((P + T - 2) % 12) + 1;
}

// 父母宫口径（05§5.3 之争）：'traditional'(默认)=4父/10母;'modern'=4母/10父。
export function parentHouses(variant){
	return variant === 'modern' ? { father: 10, mother: 4 } : { father: 4, mother: 10 };
}

// ── 月亮升格为主象征的四条件（05§4.1）：上升巨蟹/命主逆行或无力/命主与事项主无相位/同主一星。──
export function moonPromotionCheck(facts, lord1, lordQ, hasAspectL1Q){
	const reasons = [];
	if(facts.meta.ascSign === 'cancer') reasons.push('上升巨蟹（月本为命主）');
	const lp = lord1 && facts.planets[lord1];
	if(lp && lp.retro) reasons.push('命主星逆行');
	if(lp && (lp.dignityScore <= -4 || lp.peregrine)) reasons.push('命主星无力（落陷/游走）');
	if(lord1 && lordQ && lord1 !== 'moon' && hasAspectL1Q === false) reasons.push('命主与事项主无相位');
	if(lord1 && lordQ && lord1 === lordQ) reasons.push('同主一星');
	return { promote: reasons.length > 0, reasons };
}

// 指派征象星。
// opts（可选;不传=既有行为字节不变）：
//   onePlanetBoth —— 同主一星裁决法 'A'(紧连偏正面注记)|'B'(事在问者之手)|'C'(看共用星被否容纳)|
//                    'D'(让给所问,问者改月亮)|'E'(改用 almuten 拆分,由引擎二次处理);缺省=保持现状(同星双任)。
//   parentHousesVariant —— 'traditional'|'modern'(供父母类转宫)。
export function assignSignificators(facts, category, opts){
	opts = opts || {};
	const def = CATEGORY_DEF[category] || CATEGORY_DEF.general;
	const lord1 = ascRulerKey(facts);
	let qh = def.quesitedHouse;
	// 父母宫两派:传统 4父/10母(缺省表值即传统);现代对调为 4母/10父。
	if(def.parentRole && opts.parentHousesVariant === 'modern'){
		qh = (def.parentRole === 'father') ? 10 : 4;
	}
	let lordQ = qh && facts.houses[qh] ? facts.houses[qh].ruler : null;
	// general：取月亮下一个入相的星作事项守护
	if(!lordQ && category === 'general'){
		lordQ = null; // 由 engine 用月亮入相补
	}
	const natural = (def.natural || []).filter((k) => facts.planets[k])[0] || null;
	const out = {
		querentKey: def.patientIsQuerent ? lord1 : lord1,
		quesitedKey: lordQ,
		quesitedHouse: qh,
		quesitedLabel: def.quesitedLabel,
		natural,
		moon: 'moon',
		def,
	};
	// 同主一星（命主=事项主）：按所选裁决法处置;缺省保持现状（法A式注记由 UI 呈现）。
	if(lord1 && lordQ && lord1 === lordQ){
		out.sharedRuler = { planet: lord1, method: opts.onePlanetBoth || null };
		if(opts.onePlanetBoth === 'D'){
			out.querentKey = 'moon';
			out.sharedRuler.note = '同主一星（法D）：共用星让给所问之事，问者改由月亮代表。';
		}else if(opts.onePlanetBoth === 'B'){
			out.sharedRuler.note = '同主一星（法B）：事在问者之手，主动权在问卜者。';
		}else if(opts.onePlanetBoth === 'C'){
			out.sharedRuler.note = '同主一星（法C）：视共用星是否被容纳——被容纳且不受克则成，未容纳则不成。';
		}else if(opts.onePlanetBoth === 'E'){
			out.sharedRuler.note = '同主一星（法E）：以事项宫头 almuten 拆出另一象征星（见征象 Tab almuten 行）。';
		}else if(opts.onePlanetBoth === 'A'){
			out.sharedRuler.note = '同主一星（法A）：二者紧密相连，事多半成，质量看该星尊贵。';
		}
	}
	return out;
}

export default assignSignificators;
