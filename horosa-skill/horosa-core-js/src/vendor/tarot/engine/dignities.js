// 元素尊位(Elemental Dignities)——金色黎明/托特核心,逆位的替代法。
// 基础:中心牌看左右两邻元素(同元素+2 强化 / 友+1 / 敌-1 / 中立 0);两邻相争→本牌主导。
// 进阶 dignify3(手册§6.7):三张式主从——同元素全增、主元素决定基调。
import { ELEMENT_CN, isFriend, isEnemy } from '../decks/correspondences.js';

// 基础尊位:center/left/right 为元素('fire'/'water'/'air'/'earth'/null)。返回 { strength, score, notes }
export function dignify(center, left, right){
	let score = 0;
	const notes = [];
	[['左', left], ['右', right]].forEach(([label, nb]) => {
		if(nb === null || nb === undefined || center === null || center === undefined){
			notes.push(`${label}邻:中立`);
			return;
		}
		if(nb === center){ score += 2; notes.push(`${label}邻同元素·强烈强化`); }
		else if(isFriend(center, nb)){ score += 1; notes.push(`${label}邻${ELEMENT_CN[nb]}友好·强化`); }
		else if(isEnemy(center, nb)){ score -= 1; notes.push(`${label}邻${ELEMENT_CN[nb]}敌对·削弱`); }
		else{ notes.push(`${label}邻${ELEMENT_CN[nb]}中立`); }
	});
	if(left && right && isEnemy(left, right)){ notes.push('两邻相争→本牌主导'); }
	const strength = score >= 2 ? '强' : score < 0 ? '弱' : '平';
	return { strength, score, notes: notes.join('；') };
}

// 进阶三张式(§6.7):三张牌元素综合,判主从。返回 { strength, dominant, notes }
export function dignify3(elemA, elemB, elemC){
	const els = [elemA, elemB, elemC].filter(Boolean);
	if(els.length < 2){ return { strength: '平', dominant: elemB || null, notes: '元素不足,无尊位综合' }; }
	const counts = {};
	els.forEach((e) => { counts[e] = (counts[e] || 0) + 1; });
	let dominant = els[0];
	let max = 0;
	Object.keys(counts).forEach((e) => { if(counts[e] > max){ max = counts[e]; dominant = e; } });
	// 中心牌(B)与两邻的基础尊位
	const base = dignify(elemB, elemA, elemC);
	const notes = [];
	if(max >= 2){ notes.push(`${ELEMENT_CN[dominant]}元素占主(${max}/${els.length})·该气质主导全局`); }
	if(elemA && elemC && isEnemy(elemA, elemC)){ notes.push('首尾相争·以中心牌为枢纽'); }
	return { strength: base.strength, dominant, notes: [base.notes].concat(notes).filter(Boolean).join('；') };
}
