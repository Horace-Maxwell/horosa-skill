// 统一 Card 字段 schema + 显示工具(各派牌名/8-11 换号/占星对应行)。纯函数(卡片是 plain object,便于快照序列化)。
// 字段(手册附录 A.1):id(0..n 数字,facade 兼容) · sid(字符串 id the_fool/wands_05) · arcana · suit · number(rank)
//   · court · name_cn/name_en(默认 rws 显示,facade 兼容) · names{rws,thoth,tdm,golden_dawn} · element · symbol
//   · hebrew · astro · path · decanTitle/decanPlanet/decanSign · courtEie/courtSpan · polarity · countingValue
//   · keywords_upright/keywords_reversed(facade 兼容) · meanings{up,rev}(同源)
import {
	SUIT_NAME, SUIT_CN, PIP_NAME_EN, PIP_NAME_CN, COURT_NAME, COURT_CN,
	NUM_OVERRIDE, SIGN_CN, PLANET_CN, ELEMENT_EN_CN, CONTINENTAL_HEBREW,
} from '../decks/correspondences.js';

// deck 的 name_key(各派命名取哪一套)。未注册的 deck 回落 rws。
export function deckNameKey(deck){
	return (deck && deck.nameKey) || 'rws';
}

// 大牌各派编号(力量↔正义按派换号)
export function cardNumber(card, deck){
	if(card.arcana !== 'major'){ return null; }
	const ov = NUM_OVERRIDE[card.sid];
	const deckId = (deck && deck.id) || 'rws';
	if(ov && ov[deckId] !== undefined){ return ov[deckId]; }
	return card.number;
}

// 显示名(按 deck):大牌=「编号 各派名 中文」;数字牌=「Ace of Wands 权杖一」;宫廷=「Page of Wands 权杖侍从」
export function displayName(card, deck){
	const nk = deckNameKey(deck);
	if(card.arcana === 'major'){
		const name = (card.names && (card.names[nk] || card.names.rws)) || card.name_en;
		const num = cardNumber(card, deck);
		const numS = (num !== null && num !== undefined) ? `${num} ` : '';
		return `${numS}${name} ${card.name_cn}`.trim();
	}
	const suitEn = (SUIT_NAME[nk] && SUIT_NAME[nk][card.suit]) || SUIT_NAME.rws[card.suit];
	const suitCn = SUIT_CN[card.suit];
	if(card.number !== null && card.number !== undefined && !card.court){
		return `${PIP_NAME_EN[card.number]} of ${suitEn}  ${suitCn}${PIP_NAME_CN[card.number]}`;
	}
	const rankEn = (COURT_NAME[nk] && COURT_NAME[nk][card.court]) || COURT_NAME.rws[card.court];
	const rankCn = (COURT_CN[nk] && COURT_CN[nk][card.court]) || COURT_CN.rws[card.court];
	return `${rankEn} of ${suitEn}  ${suitCn}${rankCn}`;
}

// 中文短名(中栏卡片主显;facade 的 name_cn 即此)
export function displayNameCn(card, deck){
	const nk = deckNameKey(deck);
	if(card.arcana === 'major'){ return card.name_cn; }
	const suitCn = SUIT_CN[card.suit];
	if(card.number !== null && card.number !== undefined && !card.court){
		return `${suitCn}${PIP_NAME_CN[card.number]}`;
	}
	const rankCn = (COURT_CN[nk] && COURT_CN[nk][card.court]) || COURT_CN.rws[card.court];
	return `${suitCn}${rankCn}`;
}

// 英文显示名(中栏次名):大牌「编号 各派名」;数字牌「Ace of Wands」;宫廷「Page of Wands」(按派)
export function displayNameEn(card, deck){
	const nk = deckNameKey(deck);
	if(card.arcana === 'major'){
		const name = (card.names && (card.names[nk] || card.names.rws)) || card.name_en;
		const num = cardNumber(card, deck);
		return `${(num !== null && num !== undefined) ? `${num} ` : ''}${name}`.trim();
	}
	const suitEn = (SUIT_NAME[nk] && SUIT_NAME[nk][card.suit]) || SUIT_NAME.rws[card.suit];
	if(card.number !== null && card.number !== undefined && !card.court){
		return `${PIP_NAME_EN[card.number]} of ${suitEn}`;
	}
	const rankEn = (COURT_NAME[nk] && COURT_NAME[nk][card.court]) || COURT_NAME.rws[card.court];
	return `${rankEn} of ${suitEn}`;
}

// 占星/对应行。变体 B(托特):Emperor/Star 的「字母+路径」整对互换(星座不变)。
export function astroLine(card, deck, variantOverride){
	const variant = variantOverride || (deck && deck.variant) || 'A';
	if(card.arcana === 'major'){
		const a = card.astro;
		let extra = '';
		if(SIGN_CN[a]){ extra = `(${SIGN_CN[a]})`; }
		else if(PLANET_CN[a]){ extra = `(${PLANET_CN[a]})`; }
		else if(ELEMENT_EN_CN[a]){ extra = `(${ELEMENT_EN_CN[a]})`; }
		let heb = card.hebrew;
		let path = card.path;
		if(variant === 'B'){
			if(card.sid === 'the_emperor'){ heb = 'Tzaddi'; path = 28; }
			else if(card.sid === 'the_star'){ heb = 'Heh'; path = 15; }
		}else if(variant === 'C' && CONTINENTAL_HEBREW[card.sid]){
			// 大陆派字母(Continental):整体晚一格,Fool=Shin/Magician=Aleph;路径不显(大陆派不用 GD 路径制)。
			return `占星 ${a}${extra} · 希伯来 ${CONTINENTAL_HEBREW[card.sid]}(大陆派)`;
		}
		return `占星 ${a}${extra} · 希伯来 ${heb} · 路径 ${path}`;
	}
	if(card.number === 1){
		return `元素之根 Root of ${String(card.element || '').replace(/^\w/, (m) => m.toUpperCase())}`;
	}
	if(card.number !== null && card.number !== undefined && !card.court){
		const p = card.decanPlanet;
		const s = card.decanSign;
		return `"${card.decanTitle}" · ${p}(${PLANET_CN[p] || p}) in ${s}(${SIGN_CN[s] || s})`;
	}
	return `${card.courtEie} · ${card.courtSpan}`;
}

// card → 元素(尊位用):自带 element;大牌无 element 时经占星星座推。
export function cardElement(card){
	if(card.element){ return card.element; }
	if(card.arcana === 'major' && card.astro && SIGN_CN[card.astro]){
		const SIGN_ELEMENT = { Aries: 'fire', Leo: 'fire', Sagittarius: 'fire', Taurus: 'earth', Virgo: 'earth', Capricorn: 'earth', Gemini: 'air', Libra: 'air', Aquarius: 'air', Cancer: 'water', Scorpio: 'water', Pisces: 'water' };
		return SIGN_ELEMENT[card.astro] || null;
	}
	return null;
}
