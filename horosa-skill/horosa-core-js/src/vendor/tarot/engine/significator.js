// 指示牌(Significator)——代表问卜者的牌,抽牌前从牌池剔除(手册§3.4)。
// 自动:性别·年龄·星座元素 → 宫廷牌(火→权杖…;<18 侍从/女→王后/≥35 国王/否则骑士)。
// 手动:直接给 16 宫廷之一的 sid。Etteilla 用双指示牌(男 Card1 / 女 Card8),见 etteilla deck。
import { SIGN_ELEMENT, ELEMENT_SUIT } from '../decks/correspondences.js';

// 自动指示牌 sid(如 'wands_queen')。sign=英文星座名;无星座→null。
export function significatorId(gender, age, sign){
	if(!sign || !SIGN_ELEMENT[sign]){ return null; }
	const suit = ELEMENT_SUIT[SIGN_ELEMENT[sign]];
	let rank;
	if(age !== null && age !== undefined && age < 18){ rank = 'page'; }
	else if(gender === 'female'){ rank = 'queen'; }
	else if(age !== null && age !== undefined && age >= 35){ rank = 'king'; }
	else{ rank = 'knight'; }
	return `${suit}_${rank}`;
}

// 据 settings.sig 解析出要剔除的 sid(none/auto/manual)。返回 sid 或 null。
export function resolveSignificatorSid(sig){
	if(!sig || !sig.mode || sig.mode === 'none'){ return null; }
	if(sig.mode === 'manual'){ return sig.manualId || null; }
	if(sig.mode === 'auto'){
		const age = (sig.age === '' || sig.age === null || sig.age === undefined) ? null : Number(sig.age);
		return significatorId(sig.gender || 'male', Number.isFinite(age) ? age : null, sig.sign || null);
	}
	return null;
}
