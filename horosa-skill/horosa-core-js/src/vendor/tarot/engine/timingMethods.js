// 计时法引擎(TP4):五法并立,全部确定性。
//   suit_unit   花色单位法(现行:权杖日/圣杯周/宝剑时辰/钱币月,数字定量,旬星附日期)
//   major_number 大牌数字法(另取一张大牌:编号N=N个单位内;愚人=此事难成不必期)
//   major_zodiac 大牌星座法(另取一张大牌:有星座=该星座区间内;无星座对应=一年内难定)
//   decan_full   旬星全谱法(逐张:数字牌=旬10天窗/宫廷=跨段区间/星座大牌=月份区间/行星大牌=曜日/王牌=象限季;三元素大牌不用于计时)
//   ace_hunt     翻至王牌法(独立52子集去大牌去侍从,种子派生:王牌定季→已翻的该季宫廷定月→其座三旬小牌定旬)
import { shuffle } from './shuffle.js';
import { isTrumpArcana } from './arcana.js'; // [QA-9] 王牌判据单一真值源(零依赖叶子)
import { timing } from './verdict.js';
import {
	SUITS, DECAN, DECAN_DATE, signDateRange, SIGN_CN, PLANET_CN, PLANET_WEEKDAY,
	COURT_SPAN_SIGNS, ACE_QUADRANT_SIGNS, SIGN_MODE,
} from '../decks/correspondences.js';

export const TIMING_METHODS = ['suit_unit', 'major_number', 'major_zodiac', 'decan_full', 'ace_hunt'];
export const TIMING_METHOD_LABEL = {
	suit_unit: '花色单位', major_number: '大牌数字', major_zodiac: '大牌星座', decan_full: '旬星全谱', ace_hunt: '翻至王牌',
};

// 从「余牌序」取第一张大牌(E 两法所用的「另抽一张大牌」,确定性=剔除已抽后顺序首张大牌)。
function firstMajorFromRest(restIds, byId){
	for(let i = 0; i < (restIds || []).length; i++){
		const c = byId[restIds[i]];
		// [QA-9] 认 *_trump:此前写死 'major',维斯康蒂/米兰凯特阵中明明有大牌却报「异常牌组」,两法全废
		if(c && isTrumpArcana(c.arcana)){ return c; }
	}
	return null;
}

// 宫廷跨段日期(GD 口径):跨入座末旬起 → 本位座前两旬止;此处以两座区间粗示。
function courtSpanDate(card){
	const spans = COURT_SPAN_SIGNS[card.suit] && COURT_SPAN_SIGNS[card.suit][card.court];
	if(!spans){ return null; }
	if(card.court === 'page'){
		const r1 = signDateRange(spans[0]);
		const r2 = signDateRange(spans[spans.length - 1]);
		return r1 && r2 ? `${r1.split('~')[0]}~${r2.split('~')[1]}(一季)` : null;
	}
	const a = signDateRange(spans[0]);
	const b = signDateRange(spans[1]);
	if(!a || !b){ return null; }
	return `${a.split('~')[1]}前后~${b.split('~')[1]}`;
}

// 单张牌的旬星全谱计时文案。
export function decanTimingOf(card){
	if(!card){ return null; }
	if(isTrumpArcana(card.arcana)){ // [QA-9] 同上
		if(card.astro && SIGN_CN[card.astro]){ return `${SIGN_CN[card.astro]}座区间 ${signDateRange(card.astro) || ''}`; }
		if(card.astro && PLANET_CN[card.astro]){ return `${PLANET_CN[card.astro]}主日(${PLANET_WEEKDAY[card.astro] || ''})`; }
		return '三元素之牌:不用于计时';
	}
	if(card.court){ const d = courtSpanDate(card); return d ? `宫廷跨段 ${d}` : null; }
	if(card.number === 1){
		const signs = ACE_QUADRANT_SIGNS[card.suit] || [];
		const r1 = signs.length ? signDateRange(signs[0]) : null;
		const r2 = signs.length ? signDateRange(signs[signs.length - 1]) : null;
		return r1 && r2 ? `象限一季 ${r1.split('~')[0]}~${r2.split('~')[1]}` : null;
	}
	if(card.number >= 2 && card.number <= 10 && card.decanSign){
		const dd = DECAN_DATE[card.suit] && DECAN_DATE[card.suit][card.number];
		return dd ? `旬窗 ${dd}(${PLANET_CN[card.decanPlanet] || card.decanPlanet} in ${SIGN_CN[card.decanSign] || card.decanSign})` : null;
	}
	return null;
}

// 翻至王牌法的「季→宫廷→星座」表(此派单星座口径:后=本位/王=固定/骑=变动 各守一季三座)。
export const SEASON_COURTS = {
	wands: [['wands_queen', 'Aries'], ['pentacles_king', 'Taurus'], ['swords_knight', 'Gemini']],
	cups: [['cups_queen', 'Cancer'], ['wands_king', 'Leo'], ['pentacles_knight', 'Virgo']],
	swords: [['swords_queen', 'Libra'], ['cups_king', 'Scorpio'], ['wands_knight', 'Sagittarius']],
	pentacles: [['pentacles_queen', 'Capricorn'], ['swords_king', 'Aquarius'], ['cups_knight', 'Pisces']],
};
export const SEASON_CN = { wands: '春', cups: '夏', swords: '秋', pentacles: '冬' };

// 某星座的三旬小牌(由 DECAN 反查,序=旬序)。
function decanPipsOfSign(sign, byId){
	const out = [];
	SUITS.forEach((suit) => {
		Object.keys(DECAN[suit]).forEach((rank) => {
			if(DECAN[suit][rank][2] !== sign){ return; }
			const sid = `${suit}_${String(rank).padStart(2, '0')}`;
			const card = Object.values(byId).find((c) => c.sid === sid);
			if(card){ out.push({ card, rank: Number(rank), date: DECAN_DATE[suit][rank] }); }
		});
	});
	return out.sort((a, b) => ((a.rank - 2) % 3) - ((b.rank - 2) % 3));
}

// 翻至王牌法:独立 52 子集(去 22 大牌与 4 侍从),`${seed}|timing` 派生洗牌,翻至首张王牌。
export function aceHuntTiming(deckCards, seed){
	const pool = deckCards.filter((c) => c.arcana === 'minor' && c.court !== 'page');
	if(pool.length < 40){ return { error: '此牌组结构不支持翻至王牌法(需含四花色小牌)。' }; }
	const byId = {};
	pool.forEach((c, i) => { byId[i] = c; });
	const sh = shuffle(`${seed}|timing`, { size: pool.length, usesReversals: false });
	const flipped = [];
	let ace = null;
	for(let i = 0; i < sh.order.length; i++){
		const c = byId[sh.order[i]];
		flipped.push(c);
		if(c.number === 1){ ace = c; break; }
	}
	if(!ace){ return { error: '未翻出王牌(异常)。' }; }
	const season = SEASON_CN[ace.suit];
	const flippedSids = new Set(flipped.map((c) => c.sid));
	const courts = SEASON_COURTS[ace.suit] || [];
	const courtHit = courts.find(([sid]) => flippedSids.has(sid)) || null;
	const result = { flippedCount: flipped.length, aceName: ace.name_cn, season, seasonSuitCn: ace.name_cn.slice(0, 2) };
	if(!courtHit){
		result.note = `王牌定季=${season};已翻牌中无该季宫廷牌——一年内时点难定(或此事不在年内)。`;
		return result;
	}
	const [courtSid, sign] = courtHit;
	const courtCard = pool.find((c) => c.sid === courtSid);
	result.month = { name: courtCard ? courtCard.name_cn : courtSid, sign, signCn: SIGN_CN[sign], range: signDateRange(sign) };
	const pips = decanPipsOfSign(sign, byId).filter((p) => flippedSids.has(p.card.sid));
	if(!pips.length){
		result.note = `定至月份:${SIGN_CN[sign]}座 ${signDateRange(sign)}(已翻牌中无该座三旬小牌,不再细分旬)。`;
		return result;
	}
	result.decans = pips.map((p) => ({ name: p.card.name_cn, date: p.date }));
	result.note = `季=${season}(${ace.name_cn})→月=${SIGN_CN[sign]}座(${result.month.name})→旬=${result.decans.map((x) => `${x.name} ${x.date}`).join('/')}`;
	return result;
}

// 计时总装:按 method 产出行数组(供定局 tab 与 [定局] 段)。
export function computeTimingLines(reading, deckCards, method, opts){
	const m = TIMING_METHODS.includes(method) ? method : 'suit_unit';
	const o = opts || {};
	const draws = (reading && reading.draws) || [];
	const byId = {};
	deckCards.forEach((c) => { byId[c.id] = c; });
	if(m === 'suit_unit'){
		return draws.filter((d) => d.card).map((d) => `${d.position.label}:${d.card.name_cn} → ${timing(d.card)}`);
	}
	if(m === 'major_number' || m === 'major_zodiac'){
		const major = firstMajorFromRest(reading && reading.restIds, byId);
		if(!major){ return ['余牌中无大牌可取(异常牌组)。']; }
		if(m === 'major_number'){
			const unit = o.unit === '天' || o.unit === '月' ? o.unit : '周';
			if(major.number === 0){ return [`另取大牌=${major.name_cn}:此事难成于期内,不必以时相待。`]; }
			return [`另取大牌=${major.name_cn}(${major.number}) → 约 ${major.number} ${unit}内`];
		}
		if(major.astro && SIGN_CN[major.astro]){
			return [`另取大牌=${major.name_cn} → ${SIGN_CN[major.astro]}座区间 ${signDateRange(major.astro) || ''}内`];
		}
		return [`另取大牌=${major.name_cn}(无星座对应) → 一年内难定/未必应期`];
	}
	if(m === 'decan_full'){
		return draws.filter((d) => d.card).map((d) => {
			const t = decanTimingOf(d.card);
			return `${d.position.label}:${d.card.name_cn} → ${t || '—'}`;
		});
	}
	// ace_hunt
	const r = aceHuntTiming(deckCards, reading.seed);
	if(r.error){ return [r.error]; }
	const lines = [`翻牌 ${r.flippedCount} 张至王牌「${r.aceName}」→ 季=${r.season}`];
	lines.push(r.note);
	return lines;
}
