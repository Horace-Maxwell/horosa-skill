// 开钥（Opening of the Key）完整五操作（古籍 3.5(9) + 6.2 + 7.12）：金色黎明/托特招牌大牌阵，用全 78 张。
// 每操作独立洗牌+切牌→分堆（YHVH四界/黄道十二宫/三十六旬/生命树十质点/收束）→定位指示牌所在堆→
// 沿指示牌面朝方向【环形计数(6.2)】成链 + 【首尾配对】查元素尊位。指示牌(Significator)必选，为全操作锚点。
import { shuffle } from './shuffle.js';
import { dignify } from './dignities.js';
import { cardElement } from './cardSchema.js';

// 计数值：默认走 card.countingValue（古籍6.2 通行版：数字=面值/Ace=5/Princess=7/其余宫廷=4/三母大牌=3/七行星大牌=9/十二星座大牌=12）。
// 另备「按质点」宫廷版（King=2/Queen=3/Prince=6/Princess=9，RWS 键映射）可切。
export const COUNTING_ALT_COURT = { king: 2, queen: 3, knight: 6, page: 9 };
export function countingValueOf(card, table){
	if(!card){ return 1; }
	if(table === 'sephira' && card.court){ return COUNTING_ALT_COURT[card.court] || 4; }
	return card.countingValue || 1;
}

// 朝向：Queen/Princess(RWS page) 朝右数 +1；Knight(GD，=RWS king)/Prince(=RWS knight) 朝左数 −1；逆位反向；非宫廷随当前方向。
export const FACING = { queen: 1, page: 1, king: -1, knight: -1 };
export function facingOf(card, isReversed){
	let d = (card && card.court) ? (FACING[card.court] || 1) : 1;
	if(isReversed){ d *= -1; }
	return d;
}

// 环形计数(6.2)：从 sig 起，步=计数值，方向=base×facing，逆位反向，seen 去重成链。
export function countChain(pile, sigIndex, opts){
	const o = opts || {};
	const n = pile.length;
	if(!n || sigIndex < 0){ return []; }
	let idx = sigIndex;
	const chain = [pile[idx]];
	const seen = new Set([idx]);
	const base = o.direction || 1;
	const maxLinks = o.maxLinks || Math.min(n, 13);
	for(let k = 0; k < maxLinks; k++){
		const cur = pile[idx];
		const step = countingValueOf(cur.card, o.table);
		const d = base * facingOf(cur.card, cur.isReversed);
		idx = (((idx + d * step) % n) + n) % n;
		if(seen.has(idx)){ break; }
		seen.add(idx);
		chain.push(pile[idx]);
	}
	return chain;
}

// 首尾配对(6.2)：第1+末、第2+倒2…向中央；每对查元素尊位(dignify)。
export function pairing(pile){
	const pairs = [];
	let i = 0;
	let j = pile.length - 1;
	while(i < j){
		const a = pile[i];
		const b = pile[j];
		const dig = dignify(cardElement(a.card), cardElement(b.card), null);
		pairs.push({ a: a.card, b: b.card, aRev: a.isReversed, bRev: b.isReversed, strength: dig ? dig.strength : null, notes: dig ? dig.notes : '' });
		i += 1;
		j -= 1;
	}
	if(i === j){ pairs.push({ a: pile[i].card, b: null, aRev: pile[i].isReversed, bRev: false, strength: null, notes: '', center: true }); }
	return pairs;
}

// round-robin 发牌到 k 堆
function dealPiles(layout, k){
	const piles = Array.from({ length: k }, () => []);
	layout.forEach((item, i) => { piles[i % k].push(item); });
	return piles;
}
function findSigPile(piles, sigId){
	for(let p = 0; p < piles.length; p++){
		const idx = piles[p].findIndex((it) => it.card && it.card.id === sigId);
		if(idx >= 0){ return { pile: p, index: idx }; }
	}
	return { pile: -1, index: -1 };
}

const OP_DEFS = [
	{ op: 1, name: '四元素 / YHVH 四界', piles: 4, labels: ['火·权杖界(Yod)', '水·圣杯界(Heh)', '风·宝剑界(Vav)', '土·钱币界(Heh末)'] },
	{ op: 2, name: '黄道十二宫', piles: 12, labels: null },
	{ op: 3, name: '三十六旬(Decan)', piles: 36, labels: null },
	{ op: 4, name: '生命之树 10 质点', piles: 10, labels: ['Kether 王冠', 'Chokmah 智慧', 'Binah 理解', 'Chesed 仁慈', 'Geburah 严厉', 'Tiphareth 美', 'Netzach 胜利', 'Hod 荣耀', 'Yesod 根基', 'Malkuth 王国'] },
];

// 开钥五操作。deckCards=78 张牌; sigId=指示牌 id; seed=可复现种子; opts.table='sephira' 切质点计数版。
export function openingOfKey(deckCards, sigId, seed, opts){
	const o = opts || {};
	if(!Array.isArray(deckCards) || deckCards.length < 40){ return null; }
	if(sigId === undefined || sigId === null){ return { error: '开钥必须选定指示牌（Significator），它是全部五操作的锚点。' }; }
	const inDeck = deckCards.some((c) => c.id === sigId);
	if(!inDeck){ return { error: '指示牌不在此牌组。' }; }
	const operations = OP_DEFS.map((def) => {
		const sh = shuffle(`${seed}|ook${def.op}`, { size: deckCards.length, usesReversals: true, pReversed: 0.5 });
		const layout = sh.order.map((idx, pos) => ({ card: deckCards[idx], isReversed: sh.reversed[pos] }));
		const piles = dealPiles(layout, def.piles);
		const loc = findSigPile(piles, sigId);
		const sigPile = loc.pile >= 0 ? piles[loc.pile] : [];
		const chain = countChain(sigPile, loc.index, { table: o.table, maxLinks: Math.min(sigPile.length, 13) });
		const pairs = pairing(sigPile);
		return {
			op: def.op, name: def.name,
			pileLabel: def.labels ? def.labels[loc.pile] : `第 ${loc.pile + 1} 宫/旬`,
			pileIndex: loc.pile, pileSize: sigPile.length,
			chain, pairs,
		};
	});
	const op5 = { op: 5, name: '细化 / 收束', summary: operations.map((op) => `${op.name}→落「${op.pileLabel}」(链${op.chain.length}·配对${op.pairs.length})`).join('；') };
	return { sigId, operations, op5 };
}

export default openingOfKey;
