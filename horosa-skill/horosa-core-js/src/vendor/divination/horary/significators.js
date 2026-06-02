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
};

export function ascRulerKey(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}

// 指派征象星
export function assignSignificators(facts, category){
	const def = CATEGORY_DEF[category] || CATEGORY_DEF.general;
	const lord1 = ascRulerKey(facts);
	const qh = def.quesitedHouse;
	let lordQ = qh && facts.houses[qh] ? facts.houses[qh].ruler : null;
	// general：取月亮下一个入相的星作事项守护
	if(!lordQ && category === 'general'){
		lordQ = null; // 由 engine 用月亮入相补
	}
	const natural = (def.natural || []).filter((k) => facts.planets[k])[0] || null;
	return {
		querentKey: def.patientIsQuerent ? lord1 : lord1,
		quesitedKey: lordQ,
		quesitedHouse: qh,
		quesitedLabel: def.quesitedLabel,
		natural,
		moon: 'moon',
		def,
	};
}

export default assignSignificators;
