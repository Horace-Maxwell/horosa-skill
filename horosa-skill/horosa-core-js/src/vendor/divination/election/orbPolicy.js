// divination/election/orbPolicy.js
// 相位容许度三档（前端二次筛选，不改后端）：
//   'modern'  —— 现代宽轨＝后端半距和相位表原样（默认档零回归,不做任何过滤,不另造现代表以免臆造）;
//   'moiety'  —— 古典光半径和（data/aspects.PLANET_ORB：日15/月12/土木9/火8/金水7),
//                两星相位须 orb ≤ (半径A+半径B)/2 才计;
//   'sign'    —— 整宫紧轨：moiety 之上再要求两星星座本身构成该相位（同座=合、隔四座=三合…）。
// moiety/sign 只会「剔除」后端相位,故三档集合恒满足 sign ⊆ moiety ⊆ modern。
import { pairOrb } from '../data/aspects.js';
import { SIGN_ORDER } from '../data/signs.js';

function signIdx(sign){
	return SIGN_ORDER.indexOf(String(sign || '').toLowerCase());
}

// 两星座是否构成整宫位相（0/60/90/120/180）。
export function signCongruent(signA, signB, angle){
	const a = signIdx(signA); const b = signIdx(signB);
	if(a < 0 || b < 0) return false;
	const d = Math.abs(a - b) % 12;
	const steps = Math.min(d, 12 - d);
	return steps * 30 === Math.round(angle);
}

// 单条相位是否入档。x 形如 aspectsEngine 输出 {other, angle, orb, ...}；key=本星。
export function aspectInProfile(x, key, facts, profile){
	if(!profile || profile === 'modern') return true;
	if(typeof x.orb === 'number' && x.orb > pairOrb(key, x.other)) return false;
	if(profile === 'sign'){
		const pa = facts.planets[key]; const pb = facts.planets[x.other];
		if(!pa || !pb) return true;
		return signCongruent(pa.sign, pb.sign, x.angle);
	}
	return true;
}

// 过滤某星的整组相位。
export function filterAspects(list, key, facts, profile){
	if(!profile || profile === 'modern') return list;
	return (list || []).filter((x) => aspectInProfile(x, key, facts, profile));
}

export default filterAspects;
