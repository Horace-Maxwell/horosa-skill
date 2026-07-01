// 抽牌编排器:buildReading(deckId, spreadType, seed, settings)。单一真值源,中栏+右栏皆从返回 reading 渲染。
// deck/变体/尊位/逆位 不重洗(同 order,仅换呈现/掩朝向);指示牌/牌阵/种子 重抽(改池)。
import { getDeck, getDeckCards, DEFAULT_DECK } from './deckRegistry.js';
import { SPREADS, DEFAULT_SPREAD, drawSpread } from './spreads.js';
import { shuffle } from './shuffle.js';
import { resolveSignificatorSid } from './significator.js';
import { dignify } from './dignities.js';
import { synthesize } from './verdict.js';
import { cardElement } from './cardSchema.js';
import { grandTableau, box9, pairString } from './lenormandReading.js';

// 解析有效设置:用户值优先,缺省回落 deck 默认。
export function resolveSettings(deck, settings){
	const s = settings || {};
	return {
		reversals: s.reversals === undefined ? !!deck.usesReversals : !!s.reversals,
		dignities: s.dignities === undefined ? !!deck.dignities : !!s.dignities,
		variant: s.variant || deck.variant || 'A',
		showCorrespondences: s.showCorrespondences === undefined ? (deck.variant === 'B' || deck.dignities) : !!s.showCorrespondences,
		sig: s.sig || { mode: 'none' },
		verdictMode: s.verdictMode || 'majority',
		birth: s.birth || null,
	};
}

// 主函数。settings 可选;缺省 → deck 默认(rws 两参旧调用零回归)。
export function buildReading(deckId, spreadType, seed, settings){
	const deck = getDeck(deckId || DEFAULT_DECK);
	const cards = getDeckCards(deck.id);
	const byId = {};
	cards.forEach((c) => { byId[c.id] = c; });
	const resolve = (id) => byId[id] || null;

	const type = SPREADS[spreadType] ? spreadType : DEFAULT_SPREAD;
	const eff = resolveSettings(deck, settings);

	// 指示牌:从池中剔除其 id(保持 size 排列确定性)
	let sigCard = null;
	let sigId = null;
	if(deck.caps && deck.caps.significator){
		const sid = resolveSignificatorSid(eff.sig);
		if(sid){
			sigCard = cards.find((c) => c.sid === sid) || null;
			if(sigCard){ sigId = sigCard.id; }
		}
	}

	const sh = shuffle(seed, { size: deck.size, usesReversals: eff.reversals, pReversed: deck.pReversed });
	// 剔除指示牌 index:order 去掉 sigId,reversed 同步去掉(保持对齐)
	let order = sh.order;
	let reversed = sh.reversed;
	if(sigId !== null && sigId !== undefined){
		const keep = order.map((v, i) => ({ v, r: reversed[i] })).filter((x) => x.v !== sigId);
		order = keep.map((x) => x.v);
		reversed = keep.map((x) => x.r);
	}
	const draws = drawSpread(type, { order, reversed }, resolve);

	// 元素尊位(线性邻接)
	if(eff.dignities){
		const elems = draws.map((d) => (d.card ? cardElement(d.card) : null));
		draws.forEach((d, i) => {
			const le = i > 0 ? elems[i - 1] : null;
			const re = i < draws.length - 1 ? elems[i + 1] : null;
			d.dignity = dignify(elems[i], le, re);
		});
	}

	const spread = SPREADS[type];
	// Lenormand 读法:Grand Tableau / 9 宫盒 / 成句 分析挂到 reading.lenormand
	let lenormand = null;
	if(deck.caps && deck.caps.readingMethod === 'lenormand'){
		if(type === 'grand_tableau'){ lenormand = { kind: 'gt', gt: grandTableau(draws, 8) }; }
		else if(type === 'lenormand_box9'){ lenormand = { kind: 'box9', box9: box9(draws) }; }
		else{ lenormand = { kind: 'pair', pair: pairString(draws) }; }
	}
	return {
		deckId: deck.id, deckTitle: deck.title, deckCaps: deck.caps,
		spreadType: type, spreadTitle: spread.label, seed,
		question: (settings && settings.question) || '',
		settings: eff,
		significator: sigCard ? { sid: sigCard.sid, cardId: sigCard.id, card: sigCard } : null,
		draws,
		summary: synthesize(draws),
		lenormand,
	};
}

export default buildReading;
