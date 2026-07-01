// 定局法引擎(手册第6部分):Yes/No(5法) · 精华牌 Quintessence · 计数链 · 生命/灵魂/流年牌 · 综合合读。
// 极性/计数值已随卡片携带(core78 polarity/countingValue);本模块只做派生计算,纯函数、确定性。
import { SUITS, SUIT_ELEMENT, ELEMENT_CN } from '../decks/correspondences.js';
import { cardElement } from './cardSchema.js';

const PIP_NAME_CN = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 10: '十' };

// --- 6.1 Yes/No:mode = majority/orientation/single/numeric/polarity ---
export function yesNo(draws, mode){
	if(!Array.isArray(draws) || !draws.length){ return { verdict: 'MAYBE 未定', score: 0, mode: mode || 'majority' }; }
	const m = mode || 'majority';
	const polVal = (d) => (d.card.polarity || 0) * (d.isReversed ? -1 : 1);
	let score;
	if(m === 'orientation'){ score = draws.reduce((s, d) => s + (d.isReversed ? -1 : 1), 0); }
	else if(m === 'single'){ score = polVal(draws[0]); }
	else if(m === 'numeric'){ score = draws.reduce((s, d) => s + cardNumericValue(d.card), 0) % 2 === 0 ? 1 : -1; }
	else if(m === 'polarity'){ score = draws.reduce((s, d) => s + (d.card.polarity || 0), 0); }
	else{ score = draws.reduce((s, d) => s + polVal(d), 0); } // majority
	const verdict = score > 0 ? 'YES 是' : score < 0 ? 'NO 否' : 'MAYBE 未定';
	return { verdict, score, mode: m };
}

// 牌的数值(大牌=编号;数字牌=rank;宫廷 page11/knight12/queen13/king14)。
// _trump(Minchiate/Visconti)大牌沿 RWS number;Minchiate 扩展牌(德目/元素/星座)number=null,落 0 不计。
export function cardNumericValue(card, courtValues){
	const cv = courtValues || { page: 11, knight: 12, queen: 13, king: 14 };
	if(isTrumpArcana(card.arcana) && card.number !== null && card.number !== undefined){ return card.number; }
	if(card.number !== null && card.number !== undefined && !card.court){ return card.number; }
	return cv[card.court] || 0;
}

// --- 6.3 精华牌:全阵数值和归约到一张大牌(0..21) ---
export function quintessence(draws, deckCards, includeCourts){
	const cv = includeCourts === false ? { page: 0, knight: 0, queen: 0, king: 0 } : { page: 11, knight: 12, queen: 13, king: 14 };
	let s = draws.reduce((acc, d) => acc + cardNumericValue(d.card, cv), 0);
	while(s > 21){ s = String(s).split('').reduce((a, c) => a + Number(c), 0); }
	if(s === 0 || s === 22){ s = 0; }
	return majorByNumber(deckCards, s);
}

// 「大牌族」判定:RWS 系 'major',Minchiate/Visconti 历史牌组沿用 CORE78 大牌但改了 arcana 名(*_trump)。
// 精华牌/生命牌需按各自大牌体系归约,故放宽到含 '_trump' 后缀的大牌(number 仍沿 RWS 0..21)。
export function isTrumpArcana(arcana){
	return arcana === 'major' || (typeof arcana === 'string' && arcana.endsWith('_trump'));
}

export function majorByNumber(deckCards, n){
	return (deckCards || []).find((c) => isTrumpArcana(c.arcana) && c.number === n) || null;
}

// --- 6.2 计数链(简化线性演示;完整开钥需环形+朝向,P7) ---
export function countingChain(draws, start, maxLinks){
	const cards = draws.map((d) => d.card);
	const n = cards.length;
	if(!n){ return []; }
	let idx = (start || 0) % n;
	const chain = [cards[idx]];
	const seen = new Set([idx]);
	const limit = maxLinks || 10;
	for(let k = 0; k < limit; k++){
		idx = (idx + (cards[idx].countingValue || 1)) % n;
		if(seen.has(idx)){ break; }
		seen.add(idx);
		chain.push(cards[idx]);
	}
	return chain;
}

// --- 6.4 生命牌/灵魂牌/流年牌(数字学) ---
export function reduceTo(n, cap){
	const c = cap || 22;
	let v = n;
	while(v > c){ v = String(v).split('').reduce((a, d) => a + Number(d), 0); }
	return v;
}
export function birthCards(year, month, day){
	const personality = reduceTo(month + day + year, 22);
	const soul = reduceTo(personality, 9);
	return { personality, soul };
}
export function yearCard(birthMonth, birthDay, year){
	return reduceTo(birthMonth + birthDay + year, 22);
}

// --- 综合合读(花色/元素/大牌%/宫廷/正逆/重复数字) ---
export function synthesize(draws){
	const suitCount = { wands: 0, cups: 0, swords: 0, pentacles: 0 };
	let majors = 0;
	let courts = 0;
	let rev = 0;
	const ranks = {};
	draws.forEach((d) => {
		const c = d.card;
		if(d.isReversed){ rev += 1; }
		if(c.arcana === 'major'){ majors += 1; }
		else{
			if(suitCount[c.suit] !== undefined){ suitCount[c.suit] += 1; }
			if(c.court){ courts += 1; }
			if(c.number && !c.court){ ranks[c.number] = (ranks[c.number] || 0) + 1; }
		}
	});
	const elemCount = { fire: 0, water: 0, air: 0, earth: 0 };
	SUITS.forEach((s) => { elemCount[SUIT_ELEMENT[s]] += suitCount[s]; });
	let dom = null;
	let max = 0;
	Object.keys(elemCount).forEach((e) => { if(elemCount[e] > max){ max = elemCount[e]; dom = e; } });
	if(max === 0){ dom = null; }
	const repeats = {};
	Object.keys(ranks).forEach((k) => { if(ranks[k] >= 2){ repeats[k] = ranks[k]; } });
	return {
		total: draws.length, suitCount, elemCount, majors, courts, reversed: rev,
		domElement: dom, domElementCn: dom ? ELEMENT_CN[dom] : null, repeats,
	};
}

// --- 6.8 配对/镜像/桥接 ---
export function pairings(draws){
	const adj = [];
	for(let i = 0; i + 1 < draws.length; i++){
		adj.push({ a: draws[i].card, b: draws[i + 1].card });
	}
	const mirror = [];
	const n = draws.length;
	for(let i = 0; i < Math.floor(n / 2); i++){
		mirror.push({ a: draws[i].card, b: draws[n - 1 - i].card });
	}
	const bridge = n >= 2 ? { a: draws[0].card, b: draws[n - 1].card } : null;
	return { adjacent: adj, mirror, bridge };
}

// --- 3.7/6.10 计时(花色→单位,数字→数量;一种通行口径,可声明) ---
const SUIT_TIME_UNIT = { wands: '日', cups: '周', swords: '时辰/小时', pentacles: '月' };
export function timing(card){
	if(!card || card.arcana === 'major'){ return card && card.arcana === 'major' ? '大牌:时机由命运定,难以精确计时' : '—'; }
	const unit = SUIT_TIME_UNIT[card.suit];
	if(!unit){ return '—'; }
	const qty = card.court ? '一段时期' : `${card.number || '?'}`;
	return `约 ${qty} ${unit}(花色定单位·数字定数量)`;
}

// --- 6.9 澄清牌(从未抽出的余牌确定性取一张补充) ---
export function clarifier(draws, deckCards){
	const used = new Set(draws.map((d) => d.card && d.card.id));
	const rest = deckCards.filter((c) => !used.has(c.id));
	if(!rest.length){ return null; }
	// 确定性:取余牌中 id 最小(可复现)
	return rest.reduce((a, b) => (a.id <= b.id ? a : b));
}

// 综合摘要文字(供 AI/导出)
export function synthesizeText(summary){
	if(!summary || !summary.total){ return ''; }
	const sc = summary.suitCount;
	const ec = summary.elemCount;
	const lines = [];
	lines.push(`花色:权杖${sc.wands} 圣杯${sc.cups} 宝剑${sc.swords} 钱币${sc.pentacles} | 大牌${summary.majors} 宫廷${summary.courts}`);
	lines.push(`元素:火${ec.fire} 水${ec.water} 风${ec.air} 土${ec.earth}`);
	if(summary.domElement){
		const theme = { fire: '行动/意志', water: '情感/关系', air: '思维/沟通', earth: '物质/现实' }[summary.domElement];
		lines.push(`主导元素:${summary.domElementCn}(${theme})`);
	}
	lines.push(`正逆:正位${summary.total - summary.reversed} 逆位${summary.reversed}`);
	if(summary.total){
		const pct = Math.round(100 * summary.majors / summary.total);
		lines.push(`大牌占比:${pct}%${pct >= 50 ? '(大牌多→命运/重大主题)' : ''}`);
	}
	const repKeys = Object.keys(summary.repeats);
	if(repKeys.length){
		lines.push(`重复数字:${repKeys.map((k) => `${PIP_NAME_CN[k] || k}×${summary.repeats[k]}`).join('、')}`);
	}
	return lines.join('；');
}
