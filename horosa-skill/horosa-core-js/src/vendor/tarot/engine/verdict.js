// 定局法引擎(古籍第6部分):Yes/No(5法) · 精华牌 Quintessence · 计数链 · 生命/灵魂/流年牌 · 综合合读。
// 极性/计数值已随卡片携带(core78 polarity/countingValue);本模块只做派生计算,纯函数、确定性。
import { SUITS, SUIT_ELEMENT, ELEMENT_CN, decanDate, SIGN_MODE, PLANET_THEME, SIGN_BRIEF, COURT_MODE, NUMBER_META, SIGN_CN, PLANET_CN } from '../decks/correspondences.js';
import { cardElement, isTrumpArcana } from './cardSchema.js';

const PIP_NAME_CN = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 10: '十' };

// --- 6.1 Yes/No:mode = majority/orientation/single/numeric/polarity + TP4 三新法 weighted_center/anchor/single3 ---
export const YESNO_MODES = ['majority', 'orientation', 'single', 'numeric', 'polarity', 'weighted_center', 'anchor', 'single3'];
export const YESNO_MODE_LABEL = {
	majority: '多数', orientation: '朝向', single: '首牌', numeric: '数字阈值', polarity: '极性',
	weighted_center: '中位加权', anchor: '答案锚位', single3: '单张三态',
};
export function yesNo(draws, mode){
	if(!Array.isArray(draws) || !draws.length){ return { verdict: 'MAYBE 未定', score: 0, mode: mode || 'majority' }; }
	const m = mode || 'majority';
	const polVal = (d) => (d.card.polarity || 0) * (d.isReversed ? -1 : 1);
	// TP4 法6「中位加权」:正=+1 逆=−1,中间那张 ×2;平手出三义注。
	if(m === 'weighted_center'){
		const mid = Math.floor(draws.length / 2);
		const score = draws.reduce((s, d, i) => s + (d.isReversed ? -1 : 1) * (i === mid && draws.length % 2 === 1 ? 2 : 1), 0);
		const verdict = score > 0 ? 'YES 是' : score < 0 ? 'NO 否' : 'MAYBE 未定';
		const note = score === 0 ? '平手三义:结果尚未定形/此刻不宜作答/问题欠清晰' : null;
		return { verdict, score, mode: m, note };
	}
	// TP4 法7「答案锚位」:答案位(中位或标记位)与结果位(末位)皆「正立且不凶」才 YES;答案位为逆位王牌=NO(延迟)。
	if(m === 'anchor'){
		const n = draws.length;
		const aIdx = (() => { const i = draws.findIndex((d) => d.position && d.position.anchor); return i >= 0 ? i : Math.floor((n - 1) / 2); })();
		const a = draws[aIdx];
		const o = draws[n - 1];
		const ok = (d) => !d.isReversed && (d.card.polarity || 0) >= 0;
		if(a.isReversed && a.card.number === 1 && !a.card.court && a.card.arcana === 'minor'){
			return { verdict: 'NO 否', score: -2, mode: m, note: '答案位为逆位王牌——因延迟而否(时机未熟)' };
		}
		const score = (ok(a) ? 1 : 0) + (ok(o) ? 1 : 0);
		const verdict = score === 2 ? 'YES 是' : score === 1 ? 'MAYBE 未定' : 'NO 否';
		return { verdict, score: score - 1, mode: m, note: `答案位=${a.card.name_cn}·结果位=${o.card.name_cn}(两位皆正且不凶方为是)` };
	}
	// TP4 法8「单张三态」:首牌 正而吉=是/正而艰=是,但需努力/逆=否。
	if(m === 'single3'){
		const d = draws[0];
		if(d.isReversed){ return { verdict: 'NO 否', score: -1, mode: m }; }
		if((d.card.polarity || 0) > 0){ return { verdict: 'YES 是', score: 1, mode: m }; }
		return { verdict: '是,但需努力', score: 0, mode: m, note: '正立而属艰难之牌——可成,须加倍经营' };
	}
	let score;
	if(m === 'orientation'){ score = draws.reduce((s, d) => s + (d.isReversed ? -1 : 1), 0); }
	else if(m === 'single'){ score = polVal(draws[0]); }
	else if(m === 'numeric'){ const sum = draws.reduce((s, d) => s + cardNumericValue(d.card), 0); score = sum - draws.length * 5; } // 6.1 法5:数字和 vs 阈值(张数×5),≥阈值为 YES
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
// mode(TP2):'standard' 通行(归约≤21,0/22 归愚人0)| 'fool22' 马赛数值加法口径(愚人计22,归约≤22,22=愚人)。
export function quintessence(draws, deckCards, includeCourts, mode){
	const cv = includeCourts === false ? { page: 0, knight: 0, queen: 0, king: 0 } : { page: 11, knight: 12, queen: 13, king: 14 };
	const fool22 = mode === 'fool22';
	let s = draws.reduce((acc, d) => {
		const c = d.card;
		if(fool22 && c && isTrumpArcana(c.arcana) && c.number === 0){ return acc + 22; }
		return acc + cardNumericValue(c, cv);
	}, 0);
	const cap = fool22 ? 22 : 21;
	while(s > cap){ s = String(s).split('').reduce((a, c) => a + Number(c), 0); }
	if(fool22){
		if(s === 22 || s === 0){ return majorByNumber(deckCards, 0); }
		return majorByNumber(deckCards, s);
	}
	if(s === 0 || s === 22){ s = 0; }
	return majorByNumber(deckCards, s);
}

// --- TP2 数值加法分组(马赛口径,恰 3 张时):总和 A+B+C=底层面;A+C=外显面;A+B=左/承受侧影响;B+C=右/主动侧影响。
// 全部按 fool22 口径归约到大牌。非 3 张返回 null。
export function theosophicalGroups(draws, deckCards){
	if(!Array.isArray(draws) || draws.length !== 3){ return null; }
	const g = (subset) => quintessence(subset, deckCards, undefined, 'fool22');
	const [a, b, c] = draws;
	return {
		total: g([a, b, c]),
		outer: g([a, c]),
		left: g([a, b]),
		right: g([b, c]),
	};
}

// 「大牌族」判定:RWS 系 'major',Minchiate/Visconti 历史牌组沿用 CORE78 大牌但改了 arcana 名(*_trump)。
// 精华牌/生命牌需按各自大牌体系归约,故放宽到含 '_trump' 后缀的大牌(number 仍沿 RWS 0..21)。
// [QA-5] 判据本体已上收至 cardSchema(显示层与判读层从此同一口径);此处仅转出,既有 import 不受影响。
export { isTrumpArcana };

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
export function synthesize(draws, suitElementSwap){
	// G4 火/风互换:花色→元素映射可切（Wands→风、Swords→火）。
	const SUIT_ELEM = suitElementSwap ? { wands: 'air', cups: 'water', swords: 'fire', pentacles: 'earth' } : SUIT_ELEMENT;
	const suitCount = { wands: 0, cups: 0, swords: 0, pentacles: 0 };
	let majors = 0;
	let courts = 0;
	let rev = 0;
	const ranks = {};
	draws.forEach((d) => {
		const c = d.card;
		if(d.isReversed){ rev += 1; }
		if(isTrumpArcana(c.arcana)){ majors += 1; }   // [X1] *_trump 历史大牌同归大牌族,勿当小牌污染花色/重复数字
		else{
			if(suitCount[c.suit] !== undefined){ suitCount[c.suit] += 1; }
			if(c.court){ courts += 1; }
			if(c.number && !c.court){ ranks[c.number] = (ranks[c.number] || 0) + 1; }
		}
	});
	const elemCount = { fire: 0, water: 0, air: 0, earth: 0 };
	SUITS.forEach((s) => { elemCount[SUIT_ELEM[s]] += suitCount[s]; });
	let dom = null;
	let max = 0;
	Object.keys(elemCount).forEach((e) => { if(elemCount[e] > max){ max = elemCount[e]; dom = e; } });
	if(max === 0){ dom = null; }
	const repeats = {};
	Object.keys(ranks).forEach((k) => { if(ranks[k] >= 2){ repeats[k] = ranks[k]; } });
	// 6.6 极性定局:阳(火+风·主动) vs 阴(水+土·接受);含大牌(经 cardElement 归元素)。
	let yang = 0;
	let yin = 0;
	draws.forEach((d) => {
		const e = cardElement(d.card, suitElementSwap);
		if(e === 'fire' || e === 'air'){ yang += 1; }
		else if(e === 'water' || e === 'earth'){ yin += 1; }
	});
	const activePassive = { yang, yin, verdict: yang > yin ? '主动出击期' : yin > yang ? '接受沉淀期' : '动静平衡' };
	// TP1 逆位密度诊断:洗牌自然分布下约半数逆位属常态(十张出六七张仍正常);
	//   全逆(≥3张且全逆)→全逆位阵读法;比率>0.7→偏多:非自然发展/受阻主题明显,附三策略。
	const total = draws.length;
	const ratio = total ? rev / total : 0;
	let reversalDiagnosis = null;
	if(total >= 3 && rev === total){
		reversalDiagnosis = { level: 'all', ratio, note: '全逆位阵:整体转入「受阻/内在/待突破」视角解读——逐张先读正位本义,再看它此刻被什么卡住、或正从何处松脱。' };
	}else if(total >= 3 && ratio > 0.7){
		reversalDiagnosis = { level: 'high', ratio, note: '逆位偏多:事态非自然展开、或当事人不愿面对、或事情在隐性推进。可:①改问「此刻什么最有帮助」重占;②整体转正只读共通主题;③以少数正位牌为能量通道。' };
	}
	// ═══ TP3 判定器扩展(全部确定性统计,零抽牌影响) ═══
	// 模式尊贵:数字牌按旬星座三态,宫廷按位阶三态(后=本位/骑=固定/王=变动;侍辖一季不计),大牌按星座对应。
	const modeCount = { 本位: 0, 固定: 0, 变动: 0 };
	// 行星/星座归组:同行星/同星座 ≥2 张 → 主题线。
	const planetTally = {};
	const signTally = {};
	// 奇偶(数字牌):偶=承受/静,奇=行动/破格。旬相三分(2·5·8 上升/3·6·9 续座/4·7·10 下降)。
	let odd = 0;
	let even = 0;
	const phaseTally = { '上升(初发)': 0, '续座(全盛)': 0, '下降(收变)': 0 };
	draws.forEach((d) => {
		const c = d.card;
		if(!c){ return; }
		if(isTrumpArcana(c.arcana)){
			if(c.astro && SIGN_MODE[c.astro]){ modeCount[SIGN_MODE[c.astro]] += 1; signTally[c.astro] = (signTally[c.astro] || 0) + 1; }
			if(c.astro && PLANET_THEME[c.astro]){ planetTally[c.astro] = (planetTally[c.astro] || 0) + 1; }
			return;
		}
		if(c.court){
			if(COURT_MODE[c.court] && modeCount[COURT_MODE[c.court]] !== undefined){ modeCount[COURT_MODE[c.court]] += 1; }
			return;
		}
		if(c.number >= 1 && c.number <= 10){
			(c.number % 2 === 0) ? even += 1 : odd += 1;
			const meta = NUMBER_META[c.number];
			if(meta && meta.phase && phaseTally[meta.phase] !== undefined){ phaseTally[meta.phase] += 1; }
		}
		if(c.decanSign && SIGN_MODE[c.decanSign]){ modeCount[SIGN_MODE[c.decanSign]] += 1; signTally[c.decanSign] = (signTally[c.decanSign] || 0) + 1; }
		if(c.decanPlanet){ planetTally[c.decanPlanet] = (planetTally[c.decanPlanet] || 0) + 1; }
	});
	const planetGroups = Object.keys(planetTally).filter((p) => planetTally[p] >= 2)
		.map((p) => ({ planet: p, cn: PLANET_CN[p] || p, count: planetTally[p], theme: PLANET_THEME[p] || '' }));
	const signGroups = Object.keys(signTally).filter((sg) => signTally[sg] >= 2)
		.map((sg) => ({ sign: sg, cn: SIGN_CN[sg] || sg, count: signTally[sg], brief: SIGN_BRIEF[sg] || '' }));
	// 大小牌配比(常态约 1:2.5):超比=事关重大/非人力可控成分高;全小牌=日常可控短期。
	let majorRatioNote = null;
	if(draws.length >= 5){
		const pct = majors / draws.length;
		if(pct > 0.4){ majorRatioNote = '大牌超常态比(常态约1:2.5)——事关重大,非当事人可控的成分偏高'; }
		else if(majors === 0){ majorRatioNote = '全为小牌——日常层面,短期、可自力改变'; }
	}
	// 四要素互动(简法,独立于尊位):同类同现(火+风/水+土)=改善;异类同现(火+水/风+土)=转难;缺席=缺该性质。
	const present = Object.keys(elemCount).filter((e) => elemCount[e] > 0);
	const has = (e) => present.includes(e);
	const interaction = { improve: [], worsen: [], missing: Object.keys(elemCount).filter((e) => elemCount[e] === 0) };
	if(has('fire') && has('air')){ interaction.improve.push('火+风'); }
	if(has('water') && has('earth')){ interaction.improve.push('水+土'); }
	if(has('fire') && has('water')){ interaction.worsen.push('火+水'); }
	if(has('air') && has('earth')){ interaction.worsen.push('风+土'); }
	const elementInteraction = (interaction.improve.length || interaction.worsen.length || (interaction.missing.length && interaction.missing.length < 4)) ? interaction : null;
	return {
		total: draws.length, suitCount, elemCount, majors, courts, reversed: rev,
		domElement: dom, domElementCn: dom ? ELEMENT_CN[dom] : null, repeats, activePassive,
		reversalDiagnosis,
		modeCount, planetGroups, signGroups, oddEven: { odd, even }, phaseTally, majorRatioNote, elementInteraction,
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

// --- 3.7/6.10 计时(花色→单位,数字→数量;可配 timingTable;旬星附大致日期段) ---
export const SUIT_TIME_UNIT = { wands: '日', cups: '周', swords: '时辰/小时', pentacles: '月' };
export function timing(card, timingTable){
	if(!card || isTrumpArcana(card.arcana)){ return card && isTrumpArcana(card.arcana) ? '大牌:时机由命运定,难以精确计时' : '—'; }
	const table = timingTable || SUIT_TIME_UNIT;
	const unit = table[card.suit];
	if(!unit){ return '—'; }
	const qty = card.court ? '一段时期' : `${card.number || '?'}`;
	const dd = decanDate(card);
	return `约 ${qty} ${unit}${dd ? `(旬星日期段 ${dd})` : ''}`;
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
	if(summary.reversalDiagnosis){ lines.push(`逆位诊断:${summary.reversalDiagnosis.note}`); }
	if(summary.activePassive){ lines.push(`极性:阳(火风)${summary.activePassive.yang} 阴(水土)${summary.activePassive.yin}→${summary.activePassive.verdict}`); }
	if(summary.total){
		const pct = Math.round(100 * summary.majors / summary.total);
		lines.push(`大牌占比:${pct}%${pct >= 50 ? '(大牌多→命运/重大主题)' : ''}`);
	}
	const repKeys = Object.keys(summary.repeats);
	if(repKeys.length){
		lines.push(`重复数字:${repKeys.map((k) => `${PIP_NAME_CN[k] || k}×${summary.repeats[k]}`).join('、')}`);
	}
	// TP3 判定器扩展行(条件产出:有信号才出行,避免小阵噪声)
	if(summary.majorRatioNote){ lines.push(summary.majorRatioNote); }
	if(summary.modeCount && (summary.modeCount.本位 + summary.modeCount.固定 + summary.modeCount.变动) >= 3){
		const mc = summary.modeCount;
		const domMode = mc.本位 >= mc.固定 && mc.本位 >= mc.变动 ? '本位(发起)' : mc.固定 >= mc.变动 ? '固定(坚持)' : '变动(变通)';
		lines.push(`三态:本位${mc.本位} 固定${mc.固定} 变动${mc.变动}→偏${domMode}`);
	}
	if(summary.planetGroups && summary.planetGroups.length){
		lines.push(`行星主题线:${summary.planetGroups.map((g) => `${g.cn}×${g.count}(${g.theme})`).join('、')}`);
	}
	if(summary.signGroups && summary.signGroups.length){
		lines.push(`星座聚集:${summary.signGroups.map((g) => `${g.cn}×${g.count}(${g.brief})`).join('、')}`);
	}
	if(summary.elementInteraction){
		const ei = summary.elementInteraction;
		const segs = [];
		if(ei.improve.length){ segs.push(`同类同现 ${ei.improve.join('/')}=气机相生`); }
		if(ei.worsen.length){ segs.push(`异类同现 ${ei.worsen.join('/')}=相制费力`); }
		if(ei.missing.length && ei.missing.length < 4){ segs.push(`缺${ei.missing.map((e) => ELEMENT_CN[e]).join('、')}=缺该性质`); }
		if(segs.length){ lines.push(`四要素互动(简法):${segs.join('；')}`); }
	}
	return lines.join('；');
}
