// 塔罗 AI/导出快照文本(确定性增强):头(牌组·牌阵·设置·种子·指示牌) + 逐牌(各派名·正逆·占象·含义·尊位)
//   + 综合块 + 可选定局/生命牌摘要。供 UI 直断与 AI 快照共用,单一真值源。
import { getDeck, getDeckCards } from './deckRegistry.js';
import { displayName, astroLine } from './cardSchema.js';
import { orientationLabel } from './spreads.js';
import { synthesizeText, yesNo, quintessence, birthCards, yearCard, majorByNumber } from './verdict.js';

function meaningOf(card, isReversed){
	const m = card.meanings || {};
	const arr = isReversed ? (m.rev || card.keywords_reversed) : (m.up || card.keywords_upright);
	return (arr || []).slice(0, 5).join('、');
}

// reading 来自 engine/reading.buildReading。question 可单独传(优先于 reading.question)。
export function buildReadingText(reading, question){
	if(!reading || !Array.isArray(reading.draws) || !reading.draws.length){
		return '【塔罗】尚未抽牌,请先在塔罗页抽牌后再导出。';
	}
	const deck = getDeck(reading.deckId);
	const eff = reading.settings || {};
	const q = question !== undefined && question !== null ? question : reading.question;
	const lines = [];
	lines.push(`【${reading.deckTitle || (deck && deck.title) || '塔罗'}】${reading.spreadTitle || ''}(种子:${reading.seed})`);
	const meta = [eff.reversals ? '逆位 ON' : '逆位 OFF'];
	if(eff.dignities){ meta.push('元素尊位 ON'); }
	if(eff.variant){ meta.push(`变体 ${eff.variant}`); }
	lines.push(`设置:${meta.join(' · ')}`);
	if(q){ lines.push(`所问:${q}`); }
	if(reading.significator && reading.significator.card){
		lines.push(`指示牌:${displayName(reading.significator.card, deck)}`);
	}
	lines.push('—');
	reading.draws.forEach((d) => {
		const card = d.card;
		if(!card){ return; }
		const head = `位置${d.position.i}(${d.position.label})：${displayName(card, deck)}（${orientationLabel(d.isReversed)}）`;
		lines.push(head);
		lines.push(`  占象:${astroLine(card, deck, eff.variant)}`);
		lines.push(`  含义:${meaningOf(card, d.isReversed)}`);
		if(d.dignity){ lines.push(`  尊位:${d.dignity.strength}(${d.dignity.notes})`); }
	});
	lines.push('—');
	if(reading.summary){ lines.push(`综合:${synthesizeText(reading.summary)}`); }
	// 定局摘要(Yes/No + 精华牌)
	try{
		const cards = getDeckCards(reading.deckId);
		const v = yesNo(reading.draws, eff.verdictMode || 'majority');
		const quint = quintessence(reading.draws, cards);
		lines.push(`定局:Yes/No=${v.verdict}(${eff.verdictMode || 'majority'},score ${v.score})${quint ? ` · 精华牌 ${displayName(quint, deck)}` : ''}`);
	}catch(e){ /* 定局可选,失败不阻断 */ }
	// 生命牌(若给生日)
	if(eff.birth && eff.birth.year && eff.birth.month && eff.birth.day){
		try{
			const cards = getDeckCards(reading.deckId);
			const bc = birthCards(Number(eff.birth.year), Number(eff.birth.month), Number(eff.birth.day));
			const pc = majorByNumber(cards, bc.personality <= 21 ? bc.personality : 0);
			const sc = majorByNumber(cards, bc.soul);
			lines.push(`生命牌:人格 ${pc ? displayName(pc, deck) : bc.personality} · 灵魂 ${sc ? displayName(sc, deck) : bc.soul}`);
			if(eff.birth.refYear){
				const yn = yearCard(Number(eff.birth.month), Number(eff.birth.day), Number(eff.birth.refYear));
				const yc = majorByNumber(cards, yn <= 21 ? yn : 0);
				lines.push(`${eff.birth.refYear} 流年牌:${yc ? displayName(yc, deck) : yn}`);
			}
		}catch(e){ /* 生命牌可选 */ }
	}
	if(reading.draws.length === 1){ lines.push('（单张牌阵:以上即为对所问之事的一句核心指引。）'); }
	return lines.join('\n');
}

export default buildReadingText;
