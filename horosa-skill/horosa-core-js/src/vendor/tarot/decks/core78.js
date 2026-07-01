// 4 大核心共享的 78 张骨架(马赛/伟特/托特/金色黎明)+ DECKS 配置。
// 牌对象同时带:facade 兼容字段(id 0..77/suit/number/name_cn/name_en/element/symbol/keywords_*)
// + 富对应字段(sid/arcana/court/names/hebrew/astro/path/decan*/courtEie/courtSpan/polarity/countingValue)。
import {
	SUITS, SUIT_ELEMENT, MAJORS_CORR, DECAN, COURT_ASTRO, COURT_ORDER,
} from './correspondences.js';
import {
	SUIT_KW, MAJOR_KW, NUM_KW, COURT_KW, ACE_KW,
} from './meanings78.js';

// 花色符号 + 中文前缀(facade 兼容:沿用现有 静态 name_cn 口径)
export const SUIT_META = {
	major: { element: '', symbol: '✦', cnPrefix: '', kw: [] },
	wands: { element: 'fire', symbol: '◆', cnPrefix: '权杖', kw: SUIT_KW.wands },
	cups: { element: 'water', symbol: '♥', cnPrefix: '圣杯', kw: SUIT_KW.cups },
	swords: { element: 'air', symbol: '♠', cnPrefix: '宝剑', kw: SUIT_KW.swords },
	pentacles: { element: 'earth', symbol: '♦', cnPrefix: '星币', kw: SUIT_KW.pentacles },
};

const RANK_CN = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 10: '十', 11: '侍从', 12: '骑士', 13: '王后', 14: '国王' };
const RANK_EN = { 1: 'Ace', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten', 11: 'Page', 12: 'Knight', 13: 'Queen', 14: 'King' };
const SUIT_EN = { wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Pentacles' };
const COURT_BY_RANK = { 11: 'page', 12: 'knight', 13: 'queen', 14: 'king' };

// --- Yes/No 极性(手册§6.1 一种通行约定) ---
const MAJ_YES = new Set(['the_fool', 'the_magician', 'the_empress', 'the_emperor', 'the_hierophant', 'the_lovers', 'the_chariot', 'strength', 'wheel_of_fortune', 'temperance', 'the_star', 'the_sun', 'the_world', 'judgement']);
const MAJ_NO = new Set(['death', 'the_devil', 'the_tower', 'the_moon']);
const PIP_YESNO = {
	wands: { 1: 1, 2: 1, 3: 1, 4: 1, 5: 0, 6: 1, 7: 0, 8: 1, 9: 1, 10: -1 },
	cups: { 1: 1, 2: 1, 3: 1, 4: 0, 5: -1, 6: 1, 7: 0, 8: -1, 9: 1, 10: 1 },
	swords: { 1: 1, 2: 0, 3: -1, 4: 0, 5: -1, 6: 1, 7: -1, 8: -1, 9: -1, 10: -1 },
	pentacles: { 1: 1, 2: 1, 3: 1, 4: -1, 5: -1, 6: 1, 7: 0, 8: 1, 9: 1, 10: 1 },
};
const COURT_YESNO = { king: 1, queen: 1, knight: 1, page: 0 };

// --- 开钥计数值(手册§6.2 通行版本) ---
const PLANETARY_TRUMPS = new Set(['the_magician', 'high_priestess', 'the_empress', 'wheel_of_fortune', 'the_tower', 'the_sun', 'the_world']);
const MOTHER_TRUMPS = new Set(['the_fool', 'hanged_man', 'judgement']); // Aleph/Mem/Shin

function majorPolarity(sid){ return MAJ_YES.has(sid) ? 1 : MAJ_NO.has(sid) ? -1 : 0; }
function majorCounting(sid){ return MOTHER_TRUMPS.has(sid) ? 3 : PLANETARY_TRUMPS.has(sid) ? 9 : 12; }
function pipCounting(rank){ return rank === 1 ? 5 : rank; }
function courtCounting(court){ return court === 'page' ? 7 : 4; }

// 构建 78 张(顺序:大牌 0-21 → wands22-35 → cups36-49 → swords50-63 → pentacles64-77,与现有 facade 一致)
export function buildCore78(){
	const cards = [];
	MAJORS_CORR.forEach((m, n) => {
		const kw = MAJOR_KW[n];
		cards.push({
			id: n, sid: m.id, arcana: 'major', suit: 'major', number: n, court: null,
			name_cn: m.cn, name_en: m.rws,
			names: { rws: m.rws, thoth: m.thoth, tdm: m.tdm, golden_dawn: m.rws },
			element: m.elem || '', symbol: SUIT_META.major.symbol,
			hebrew: m.heb, astro: m.astro, path: m.path,
			decanTitle: null, decanPlanet: null, decanSign: null, courtEie: null, courtSpan: null,
			polarity: majorPolarity(m.id), countingValue: majorCounting(m.id),
			keywords_upright: kw.up, keywords_reversed: kw.rev,
			meanings: { up: kw.up, rev: kw.rev },
		});
	});
	SUITS.forEach((suit, si) => {
		const meta = SUIT_META[suit];
		const elem = SUIT_ELEMENT[suit];
		for(let rank = 1; rank <= 14; rank++){
			const id = 22 + si * 14 + (rank - 1);
			const court = COURT_BY_RANK[rank] || null;
			let up;
			let rev;
			let decanTitle = null;
			let decanPlanet = null;
			let decanSign = null;
			let courtEie = null;
			let courtSpan = null;
			let polarity;
			let countingValue;
			if(rank === 1){
				up = ACE_KW[suit].up.concat(meta.kw.slice(0, 1));
				rev = ACE_KW[suit].rev;
				decanTitle = `Root of ${elem.replace(/^\w/, (c) => c.toUpperCase())}`;
				polarity = PIP_YESNO[suit][1];
				countingValue = pipCounting(1);
			}else if(rank >= 11){
				up = COURT_KW[rank].up.concat(meta.kw.slice(0, 2));
				rev = COURT_KW[rank].rev.concat(meta.kw.slice(0, 1));
				const ca = COURT_ASTRO[suit][court];
				courtEie = ca[0];
				courtSpan = ca[1];
				decanTitle = `${court} of ${suit}`;
				polarity = COURT_YESNO[court];
				countingValue = courtCounting(court);
			}else{
				up = NUM_KW[rank].up.concat(meta.kw.slice(0, 2));
				rev = NUM_KW[rank].rev.concat(meta.kw.slice(0, 1));
				const d = DECAN[suit][rank];
				decanTitle = d[0];
				decanPlanet = d[1];
				decanSign = d[2];
				polarity = PIP_YESNO[suit][rank];
				countingValue = pipCounting(rank);
			}
			cards.push({
				id, sid: rank >= 11 ? `${suit}_${court}` : `${suit}_${String(rank).padStart(2, '0')}`,
				arcana: 'minor', suit, number: rank, court,
				name_cn: `${meta.cnPrefix}${RANK_CN[rank]}`, name_en: `${RANK_EN[rank]} of ${SUIT_EN[suit]}`,
				names: null, element: meta.element, symbol: meta.symbol,
				hebrew: null, astro: null, path: null,
				decanTitle, decanPlanet, decanSign, courtEie, courtSpan,
				polarity, countingValue,
				keywords_upright: up, keywords_reversed: rev,
				meanings: { up, rev },
			});
		}
	});
	return cards;
}

export const CORE78 = buildCore78();

// id(0..77)→ 牌,越界 null(facade 兼容)
export function getCard(id){
	if(typeof id !== 'number' || id < 0 || id >= CORE78.length){ return null; }
	return CORE78[id];
}

// 取一张牌按正/逆位的关键义数组(facade 兼容)
export function cardKeywords(card, reversed){
	if(!card){ return []; }
	return reversed ? (card.keywords_reversed || []) : (card.keywords_upright || []);
}

// 4 大核心牌组配置(uses_reversals/p_reversed/dignities/variant/illustrated_pips)
export const CORE_DECKS = {
	rws: { id: 'rws', title: 'Rider–Waite–Smith (RWS) 韦特-史密斯', nameKey: 'rws', size: 78, structure: '78major56minor', usesReversals: true, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: true },
	tdm: { id: 'tdm', title: 'Tarot de Marseille (TdM) 马赛塔罗', nameKey: 'tdm', size: 78, structure: '78major56minor', usesReversals: false, pReversed: 0.5, dignities: false, variant: 'C', illustratedPips: false },
	thoth: { id: 'thoth', title: 'Thoth 托特塔罗', nameKey: 'thoth', size: 78, structure: '78major56minor', usesReversals: false, pReversed: 0.5, dignities: true, variant: 'B', illustratedPips: true },
	golden_dawn: { id: 'golden_dawn', title: 'Golden Dawn (Book T) 金色黎明', nameKey: 'golden_dawn', size: 78, structure: '78major56minor', usesReversals: false, pReversed: 0.5, dignities: true, variant: 'A', illustratedPips: true },
};
