// 统一 Card 字段 schema + 显示工具(各派牌名/8-11 换号/占星对应行)。纯函数(卡片是 plain object,便于快照序列化)。
// 字段(古籍附录 A.1):id(0..n 数字,facade 兼容) · sid(字符串 id the_fool/wands_05) · arcana · suit · number(rank)
//   · court · name_cn/name_en(默认 rws 显示,facade 兼容) · names{rws,thoth,tdm,golden_dawn} · element · symbol
//   · hebrew · astro · path · decanTitle/decanPlanet/decanSign · courtEie/courtSpan · polarity · countingValue
//   · keywords_upright/keywords_reversed(facade 兼容) · meanings{up,rev}(同源)
import {
	SUIT_NAME, SUIT_CN, PIP_NAME_EN, PIP_NAME_CN, COURT_NAME, COURT_CN,
	NUM_OVERRIDE, SIGN_CN, PLANET_CN, ELEMENT_EN_CN, CONTINENTAL_HEBREW,
	SEPHIROTH, sephiraLabel, pathJoin, ACE_QUADRANT, COURT_SEPHIRA,
	MODERN_PLANET, MODERN_PLANET_CN,
} from '../decks/correspondences.js';
import { reversedText } from './reversalModes.js';
import { isTrumpArcana } from './arcana.js'; // [QA-9] 王牌判据单一真值源(零依赖叶子)
import { CORE78 } from '../decks/core78.js'; // 回退前课链查前一号牌(core78 不反向依赖本模块,无环)
import { degreesMeaningOf } from '../decks/marseilleMeanings.js'; // 第三牌义轨「数字度」(马赛口径)
import { courtEieOf, courtZodiacOf } from '../decks/courtSystems.js'; // TP7 宫廷元素/星座两体系

// [QA-5] 「王牌」单一判据。牌组把大牌另名(minchiate_trump / visconti_trump)以标其体系,
// 但显示层此前一律写死 arcana === 'major' → 这两副的王牌在显示层全线漏判,落进数字牌分支,
// 于是出「undefined of undefined」这样的脏名(快照/导出/挂载同源受害)。判读层本已有此判据(verdict),
// 显示层却是另一套字面量口径 —— 两套口径就是病根,此处收敛为单源,verdict 改从此处取。
export { isTrumpArcana };
// [QA-5] 是否为「塔罗结构」的牌(王牌/四花色小牌/空白牌)。雷诺曼、吉普赛、扑克牌等牌组
// 自成体系(花色不在四花色表内、序数超出一至十),套塔罗命名与旬星对应只会产出 null 串,
// 故显示层遇之一律回落到牌自带的名与「—」。判据取数据本身(花色能否查到)而非枚举牌组名,新牌组自动适用。
export function isTarotStructured(card){
	if(!card){ return false; }
	if(isTrumpArcana(card.arcana) || card.arcana === 'blank'){ return true; }
	return !!(SUIT_NAME.rws && SUIT_NAME.rws[card.suit]);
}

// 对应叠层后缀（G3）：仅在 UI「显示对应」开启时追加，故经 opts.showCorrespondences 门控——
// reportText 不传该 opts → [逐牌详解] 占象列逐字节不变（reportTextTable fixture 稳定）。
export function correspondenceSuffix(card, variant){
	if(!card){ return ''; }
	if(!isTarotStructured(card)){ return ''; }
	if(isTrumpArcana(card.arcana)){
		// [QA-8] 大陆派(变体 C)不用 GD 路径制 —— astroLine 在 C 档已明写「路径不显」,
		// 此处却仍按 GD 路径表附「路径连 X–Y」,同一张牌两行自相矛盾(既存于 tdm/wirth/egyptian,
		// 本轮王牌判据修复后 visconti 亦入此径)。两处收敛为同一口径:C 档不附路径。
		if(variant === 'C'){ return ''; }
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
	if(!isTrumpArcana(card.arcana)){ return null; }
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
	if(card.arcana === 'blank'){ return `${card.name_en} ${card.name_cn}`; }
	// [QA-5] 非塔罗结构(雷诺曼/吉普赛/扑克牌等)用自带名,不套四花色命名
	if(!isTarotStructured(card)){ return `${card.name_en || ''} ${card.name_cn || ''}`.trim(); }
	if(isTrumpArcana(card.arcana)){
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
	if(isTrumpArcana(card.arcana) || card.arcana === 'blank'){ return card.name_cn; }
	if(!isTarotStructured(card)){ return card.name_cn || card.name_en || ''; }
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
	if(card.arcana === 'blank'){ return card.name_en; }
	if(!isTarotStructured(card)){ return card.name_en || ''; }
	if(isTrumpArcana(card.arcana)){
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
// modern(TP3):三元素大牌附现代行星注(风=天王星/水=海王星/火=冥王星),默认不传=不附(reportText 字节稳定由 eff 显式控制)。
export function astroLine(card, deck, variantOverride, modern, courtView){
	const variant = variantOverride || (deck && deck.variant) || 'A';
	if(card.arcana === 'blank'){ return '—(空白牌无对应)'; }
	// [QA-5] 非塔罗结构的牌不套占星对应(此前会拼出「"null" · null(null) in null(null)」进快照/导出/挂载);
	// 塔罗结构但该牌未载对应数据(如米兰凯特的美德/元素王牌 astro=null)同样以「—」如实呈现,不造假对应。
	if(!isTarotStructured(card)){ return '—'; }
	if(isTrumpArcana(card.arcana)){
		if(!card.astro && !card.hebrew){ return '—'; }
		const a = card.astro;
		let extra = '';
		if(SIGN_CN[a]){ extra = `(${SIGN_CN[a]})`; }
		else if(PLANET_CN[a]){ extra = `(${PLANET_CN[a]})`; }
		else if(ELEMENT_EN_CN[a]){ extra = `(${ELEMENT_EN_CN[a]})`; }
		const modernNote = modern && MODERN_PLANET[card.sid] ? ` · 近代 ${MODERN_PLANET_CN[MODERN_PLANET[card.sid]]}` : '';
		let heb = card.hebrew;
		let path = card.path;
		if(variant === 'B'){
			if(card.sid === 'the_emperor'){ heb = 'Tzaddi'; path = 28; }
			else if(card.sid === 'the_star'){ heb = 'Heh'; path = 15; }
		}else if(variant === 'C' && CONTINENTAL_HEBREW[card.sid]){
			// 大陆派字母(Continental):整体晚一格,Fool=Shin/Magician=Aleph;路径不显(大陆派不用 GD 路径制)。
			return `占星 ${a}${extra}${modernNote} · 希伯来 ${CONTINENTAL_HEBREW[card.sid]}(大陆派)`;
		}
		return `占星 ${a}${extra}${modernNote} · 希伯来 ${heb} · 路径 ${path}`;
	}
	if(card.number === 1){
		return `元素之根 Root of ${String(card.element || '').replace(/^\w/, (m) => m.toUpperCase())}`;
	}
	if(card.number !== null && card.number !== undefined && !card.court){
		const p = card.decanPlanet;
		const s = card.decanSign;
		if(!card.decanTitle || !p || !s){ return '—'; }
		return `"${card.decanTitle}" · ${p}(${PLANET_CN[p] || p}) in ${s}(${SIGN_CN[s] || s})`;
	}
	// TP7 宫廷两体系:courtView={elementSystem:'gd'|'alt', zodiacSystem:'gd_span'|'simple'};缺省=现行字节。
	if(courtView && (courtView.elementSystem === 'alt' || courtView.zodiacSystem === 'simple')){
		const eie = courtEieOf(card, courtView.elementSystem);
		const zod = courtZodiacOf(card, courtView.zodiacSystem);
		if(!eie && !zod){ return '—'; }
		return [eie, zod].filter(Boolean).join(' · ');
	}
	if(!card.courtEie && !card.courtSpan){ return '—'; }
	return [card.courtEie, card.courtSpan].filter(Boolean).join(' · ');
}

// ——「回退前课」链(TP1):逆位=未修完「前一号牌」的正位课题。数字牌回同花色前一号;王牌回同花色十;
// 大牌回前一号(愚人无前牌=时机未熟特文;因果之牌照正位读=该派明示例外);宫廷不入链(回落预存逆位义)。
function retreatPrevCard(card){
	if(isTrumpArcana(card.arcana)){
		if(card.number === 0 || card.number === null || card.number === undefined){ return null; }
		return CORE78.find((c) => c.arcana === 'major' && c.number === card.number - 1) || null;
	}
	if(card.court || !card.suit){ return null; }
	const prevRank = card.number === 1 ? 10 : card.number - 1;
	const sid = prevRank === 10 ? `${card.suit}_10` : `${card.suit}_${String(prevRank).padStart(2, '0')}`;
	return CORE78.find((c) => c.sid === sid) || null;
}
export function retreatText(card, sys, upText, storedRevText){
	if(isTrumpArcana(card.arcana) && card.sid === 'justice'){
		return `${upText}(因果之律不因倒置而改——此牌逆位照正位读)`;
	}
	if(isTrumpArcana(card.arcana) && card.number === 0){
		return '时机未熟的开始——回到当下,先安顿脚下再启程';
	}
	const prev = retreatPrevCard(card);
	if(!prev){ return storedRevText; } // 宫廷/异构牌组不入链,回落预存逆位义
	const prevUp = cardMeaning(prev, false, sys, 'stored');
	return `未修完前一课「${prev.name_cn}」:${prevUp}`;
}

// 三轨牌义统一取值:system='manual' 逐牌唯一义 / 'waite' 数字原型×花色派生义 / 'degrees' 马赛数字度(TP2)。
// 默认 manual。返回统一为显示字符串。degrees 轨对无度义的牌(异构牌组)回落 manual 轨。
// reversalMode:逆位时按十三模式动态生成文案(默认 'stored' 预存逆位义,零回归;'retreat' 引擎型走回退链)。
export function cardMeaning(card, reversed, system, reversalMode){
	if(!card){ return ''; }
	const sys = system === 'waite' ? 'waite' : system === 'degrees' ? 'degrees' : 'manual';
	let up;
	let rev;
	if(sys === 'degrees'){
		const deg = degreesMeaningOf(card);
		if(deg){
			up = deg;
			// 马赛派本无逆位教义;用户强开逆位时,逆位义=该度「危险面」已含于度义括注,预存逆位义作后备。
			rev = (card.meaningsManual && card.meaningsManual.rev) || deg;
		}
	}
	if(up === undefined && sys !== 'waite' && card.meaningsManual){
		up = card.meaningsManual.up || '';
		rev = card.meaningsManual.rev || '';
	}else if(up === undefined){
		const m = card.meanings || {};
		const upArr = (m.up || card.keywords_upright) || [];
		const revArr = (m.rev || card.keywords_reversed) || [];
		up = Array.isArray(upArr) ? upArr.join('、') : String(upArr || '');
		rev = Array.isArray(revArr) ? revArr.join('、') : String(revArr || '');
	}
	if(!reversed){ return up; }
	if(reversalMode === 'retreat'){ return retreatText(card, sys, up, rev); }
	if(reversalMode && reversalMode !== 'stored'){ return reversedText(up, rev, reversalMode); }
	return rev;
}

// card → 元素(尊位用):自带 element;大牌无 element 时经占星星座推。
// swap（G4 火/风互换·少数派 分歧点1）：仅小牌花色层——Wands 火→风、Swords 风→火（Cups/Pentacles 不变；大牌占星元素不动）。
export function cardElement(card, swap){
	let e = null;
	if(card.element){ e = card.element; }
	else if(isTrumpArcana(card.arcana) && card.astro && SIGN_CN[card.astro]){
		const SIGN_ELEMENT = { Aries: 'fire', Leo: 'fire', Sagittarius: 'fire', Taurus: 'earth', Virgo: 'earth', Capricorn: 'earth', Gemini: 'air', Libra: 'air', Aquarius: 'air', Cancer: 'water', Scorpio: 'water', Pisces: 'water' };
		e = SIGN_ELEMENT[card.astro] || null;
	}
	if(swap && !isTrumpArcana(card.arcana)){
		if(card.suit === 'wands' && e === 'fire'){ return 'air'; }
		if(card.suit === 'swords' && e === 'air'){ return 'fire'; }
	}
	return e;
}
