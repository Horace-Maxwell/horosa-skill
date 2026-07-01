// 牌组注册表:统一 Deck schema + capabilities + 各 deck 注册。caps 驱动 UI 条件渲染与读法分派。
// 全部流派(可变张数 22/36/52/74/78/97、可变结构、可变读法)都在此登记;P0/P1 先登记 4 大核心 78 张。
import { CORE78, CORE_DECKS } from '../decks/core78.js';

const REGISTRY = {};
const GROUPS = []; // [{ group, items:[deckId] }]

// 注册一个牌组。entry={...deckConfig, caps, cards(数组或()=>数组), group}
export function registerDeck(entry){
	if(!entry || !entry.id){ return; }
	REGISTRY[entry.id] = entry;
	const groupName = entry.group || '其他';
	let g = GROUPS.find((x) => x.group === groupName);
	if(!g){ g = { group: groupName, items: [] }; GROUPS.push(g); }
	if(!g.items.includes(entry.id)){ g.items.push(entry.id); }
}

export function getDeck(deckId){
	return REGISTRY[deckId] || REGISTRY.rws || null;
}

export function getDeckCards(deckId){
	const d = getDeck(deckId);
	if(!d){ return []; }
	return typeof d.cards === 'function' ? d.cards() : (d.cards || []);
}

export function hasDeck(deckId){ return !!REGISTRY[deckId]; }

// UI 分组下拉用:[{ group, items:[{value,label}] }]
export function listDeckGroups(){
	return GROUPS.map((g) => ({
		group: g.group,
		items: g.items.map((id) => ({ value: id, label: REGISTRY[id].title })),
	})).filter((g) => g.items.length);
}

export function listDeckIds(){ return Object.keys(REGISTRY); }

// 默认能力(4 核心 78 张):有大小阿卡纳、78 张、塔罗读法、可指示牌、可变体
function tarot78Caps(deck){
	return {
		reversals: !!deck.usesReversals,
		dignities: !!deck.dignities,
		variant: true,            // A/B/C 可选(门控在"显示进阶对应")
		significator: true,
		numOverride: true,
		embeddedPlayingCard: false,
		readingMethod: 'tarot',
		spreads: ['single', 'three', 'three_sit', 'horseshoe', 'celtic', 'relation', 'tree_of_life', 'zodiac', 'annual', 'croix'],
	};
}

// --- 注册 4 大核心(共享 CORE78 骨架,差异=配置) ---
const CORE_GROUP = '七十八张体系';
['rws', 'tdm', 'thoth', 'golden_dawn'].forEach((id) => {
	const deck = CORE_DECKS[id];
	registerDeck({ ...deck, group: CORE_GROUP, caps: tarot78Caps(deck), cards: CORE78 });
});

// --- 注册扩展流派(P2-P6:各自带 caps + cards + group) ---
import { CONTINENTAL_DECKS } from '../decks/continental.js';
import { ETTEILLA_DECK } from '../decks/etteilla.js';
import { LENORMAND_DECK } from '../decks/lenormand.js';
import { KIPPER_DECK } from '../decks/kipper.js';
import { SIBILLA_DECK } from '../decks/sibilla.js';
import { CARTOMANCY_DECK } from '../decks/cartomancy.js';
import { MINCHIATE_DECK } from '../decks/minchiate.js';
import { VISCONTI_DECK } from '../decks/visconti.js';

[...CONTINENTAL_DECKS, ETTEILLA_DECK, LENORMAND_DECK, KIPPER_DECK, SIBILLA_DECK, CARTOMANCY_DECK, MINCHIATE_DECK, VISCONTI_DECK].forEach((d) => registerDeck(d));

export const DEFAULT_DECK = 'rws';
