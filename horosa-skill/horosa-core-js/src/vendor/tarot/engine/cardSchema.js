// 统一 Card 字段 schema + 显示工具(各派牌名/8-11 换号/占星对应行)。纯函数(卡片是 plain object,便于快照序列化)。
// 字段(古籍附录 A.1):id(0..n 数字,facade 兼容) · sid(字符串 id the_fool/wands_05) · arcana · suit · number(rank)
//   · court · name_cn/name_en(默认 rws 显示,facade 兼容) · names{rws,thoth,tdm,golden_dawn} · element · symbol
//   · hebrew · astro · path · decanTitle/decanPlanet/decanSign · courtEie/courtSpan · polarity · countingValue
//   · keywords_upright/keywords_reversed(facade 兼容) · meanings{up,rev}(同源)
import {
	SUIT_NAME, SUIT_CN, PIP_NAME_EN, PIP_NAME_CN, COURT_NAME, COURT_CN,
	NUM_OVERRIDE, SIGN_CN, PLANET_CN, ELEMENT_EN_CN, CONTINENTAL_HEBREW,
	SEPHIROTH, sephiraLabel, pathJoin, ACE_QUADRANT, COURT_SEPHIRA,
} from '../decks/correspondences.js';
import { reversedText } from './reversalModes.js';

// 对应叠层后缀（G3）：仅在 UI「显示对应」开启时追加，故经 opts.showCorrespondences 门控——
// reportText 不传该 opts → [逐牌详解] 占象列逐字节不变（reportTextTable fixture 稳定）。
export function correspondenceSuffix(card, variant){
	if(!card){ return ''; }
	if(card.arcana === 'major'){
		const j = pathJoin(card.sid, variant);
		if(!j){ return ''; }
		const a = SEPHIROTH[j[0]];
		const b = SEPHIROTH[j[1]];
		return (a && b) ? ` · 路径连 ${a.name}–${b.name}` : '';
	}
	if(card.number === 1){
		const q = ACE_QUADRANT[card.suit];
		return ` · ${sephiraLabel(1)}${q ? ` · 象限 ${q.signs}(${q.season})` : ''}`;
	}
	if(card.number !== null && card.number !== undefined && !card.court){
		const lbl = sephiraLabel(card.sephira);
		return lbl ? ` · ${lbl}` : '';
	}
	if(card.court){
		const lbl = sephiraLabel(COURT_SEPHIRA[card.court]);
		return lbl ? ` · ${lbl}` : '';
	}
	return '';
}

// deck 的 name_key(各派命名取哪一套)。未注册的 deck 回落 rws。
export function deckNameKey(deck){
	return (deck && deck.nameKey) || 'rws';
}

// 大牌各派编号(力量↔正义按派换号)
export function cardNumber(card, deck){
	if(card.arcana !== 'major'){ return null; }
	const ov = NUM_OVERRIDE[card.sid];
	if(!ov){ return card.number; }
	const deckId = (deck && deck.id) || 'rws';
	if(ov[deckId] !== undefined){ return ov[deckId]; }
	// [X1] 换号随【命名体系】走:wirth/egyptian/visconti 等 nameKey='tdm' 的牌组按大陆序
	// (正义8·力量11),此前按 deck.id 查表(表内无其 id)恒回落 RWS 序,与其自declared命名矛盾。
	const nk = deckNameKey(deck);
	if(ov[nk] !== undefined){ return ov[nk]; }
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

// 双轨牌义统一取值（G5）：system='manual' 走逐牌唯一义（meaningsManual 字符串）,'waite' 走「数字原型×花色」派生义
// （meanings 关键词数组，join 显示）。默认 manual（手册逐牌义为权威主轴）。返回统一为显示字符串。
// reversalMode（G2）：逆位时按五模式动态生成文案（默认 'stored' 用预存逆位义，零回归）。
export function cardMeaning(card, reversed, system, reversalMode){
	if(!card){ return ''; }
	const sys = system === 'waite' ? 'waite' : 'manual';
	let up;
	let rev;
	if(sys === 'manual' && card.meaningsManual){
		up = card.meaningsManual.up || '';
		rev = card.meaningsManual.rev || '';
	}else{
		const m = card.meanings || {};
		const upArr = (m.up || card.keywords_upright) || [];
		const revArr = (m.rev || card.keywords_reversed) || [];
		up = Array.isArray(upArr) ? upArr.join('、') : String(upArr || '');
		rev = Array.isArray(revArr) ? revArr.join('、') : String(revArr || '');
	}
	if(!reversed){ return up; }
	if(reversalMode && reversalMode !== 'stored'){ return reversedText(up, rev, reversalMode); }
	return rev;
}

// card → 元素(尊位用):自带 element;大牌无 element 时经占星星座推。
// swap（G4 火/风互换·少数派 分歧点1）：仅小牌花色层——Wands 火→风、Swords 风→火（Cups/Pentacles 不变；大牌占星元素不动）。
export function cardElement(card, swap){
	let e = null;
	if(card.element){ e = card.element; }
	else if(card.arcana === 'major' && card.astro && SIGN_CN[card.astro]){
		const SIGN_ELEMENT = { Aries: 'fire', Leo: 'fire', Sagittarius: 'fire', Taurus: 'earth', Virgo: 'earth', Capricorn: 'earth', Gemini: 'air', Libra: 'air', Aquarius: 'air', Cancer: 'water', Scorpio: 'water', Pisces: 'water' };
		e = SIGN_ELEMENT[card.astro] || null;
	}
	if(swap && card.arcana !== 'major'){
		if(card.suit === 'wands' && e === 'fire'){ return 'air'; }
		if(card.suit === 'swords' && e === 'air'){ return 'fire'; }
	}
	return e;
}
