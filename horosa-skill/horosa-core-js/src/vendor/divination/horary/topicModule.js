// divination/horary/topicModule.js
// 主题深化：按问题类别给「征象星对照」式专题判读（诉讼胜负 / 买房四角 / 怀孕）。
// 纯派生自 facts（宫主 + 单星状态），不改动通用完成法/裁决；供右栏「裁决」专题卡 + AI 快照。
import { PLANETS } from '../data/planets.js';
import { SIGNS } from '../data/signs.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || '—'; }
const ANG_BONUS = { angular: 2, succedent: 0, cadent: -1.5 };

// 综合力量：庙旺尊贵分 + 角宫加成 − 逆行/燃烧减损。用于「谁更强」对照。
function strengthOf(facts, key){
	const p = key && facts.planets[key];
	if(!p) return null;
	let s = (typeof p.dignityScore === 'number') ? p.dignityScore : 0;
	s += (ANG_BONUS[p.angularity] || 0);
	if(p.retro) s -= 1.5;
	if(p.combustion === 'combust') s -= 3;
	else if(p.combustion === 'cazimi') s += 3;
	return s;
}
function lordOf(facts, house){ return facts.houses[house] && facts.houses[house].ruler; }
function stateWord(facts, key){
	const p = key && facts.planets[key];
	if(!p) return '不明';
	const bits = [];
	if(p.dignityScore >= 4) bits.push('有力'); else if(p.dignityScore <= -4) bits.push('失势'); else bits.push('中平');
	if(p.angularity === 'angular') bits.push('角宫'); else if(p.angularity === 'cadent') bits.push('果宫');
	if(p.retro) bits.push('逆行');
	if(p.combustion === 'combust') bits.push('燃烧');
	return bits.join('·');
}
function cmpLine(facts, aKey, aLabel, bKey, bLabel){
	const sa = strengthOf(facts, aKey);
	const sb = strengthOf(facts, bKey);
	if(sa === null || sb === null) return { polarity: 'neutral', text: `${aLabel}/${bLabel} 征象星不全，无法直接对照强弱。` };
	const diff = sa - sb;
	const who = Math.abs(diff) < 1.5 ? '双方旗鼓相当' : (diff > 0 ? `${aLabel}占优` : `${bLabel}占优`);
	const pol = Math.abs(diff) < 1.5 ? 'neutral' : (diff > 0 ? 'positive' : 'negative');
	return { polarity: pol, text: `${aLabel}（${cn(aKey)}·${stateWord(facts, aKey)}） 对 ${bLabel}（${cn(bKey)}·${stateWord(facts, bKey)}） → ${who}。` };
}

export function buildTopicDeepening(facts, category){
	if(category === 'lawsuit'){
		const l1 = lordOf(facts, 1); const l7 = lordOf(facts, 7); const l10 = lordOf(facts, 10);
		const lines = [cmpLine(facts, l1, '本方（1宫）', l7, '对方（7宫）')];
		if(l10) lines.push({ polarity: 'neutral', text: `法官/裁决 = 10宫主 ${cn(l10)}（${stateWord(facts, l10)}）；其偏向哪方之征象星接纳，多主判向该方。` });
		return { title: '诉讼胜负（1宫本方 vs 7宫对方，10宫法官）', lines };
	}
	if(category === 'property'){
		// Sahl 四角：1宫买方 / 4宫标的(田宅) / 7宫卖方 / 10宫成交(价/结果)。
		const l1 = lordOf(facts, 1); const l4 = lordOf(facts, 4); const l7 = lordOf(facts, 7); const l10 = lordOf(facts, 10);
		const lines = [
			{ polarity: 'neutral', text: `买方＝1宫主 ${cn(l1)}（${stateWord(facts, l1)}）；卖方＝7宫主 ${cn(l7)}（${stateWord(facts, l7)}）。` },
			{ polarity: (strengthOf(facts, l4) >= 0 ? 'positive' : 'negative'), text: `标的（田宅）＝4宫主 ${cn(l4)}（${stateWord(facts, l4)}）→ ${strengthOf(facts, l4) >= 0 ? '房产/地块状况良好' : '房产/地块有瑕或不宜'}。` },
			{ polarity: (strengthOf(facts, l10) >= 0 ? 'positive' : 'negative'), text: `成交/价格＝10宫主 ${cn(l10)}（${stateWord(facts, l10)}）→ ${strengthOf(facts, l10) >= 0 ? '价钱/结果趋顺' : '价钱/结果多波折'}。` },
		];
		return { title: '买房四角（1买方·4标的·7卖方·10成交）', lines };
	}
	if(category === 'pregnancy'){
		const l5 = lordOf(facts, 5);
		const asc = facts.meta.ascSign;
		const ascGender = SIGNS[asc] ? SIGNS[asc].gender : null;  // masculine/feminine
		const benefic = ['jupiter', 'venus'].filter((k) => facts.planets[k] && facts.planets[k].dignityScore > -4);
		const lines = [
			{ polarity: (strengthOf(facts, l5) >= 0 ? 'positive' : 'negative'), text: `子嗣＝5宫主 ${cn(l5)}（${stateWord(facts, l5)}）＋月亮/木星/金星为自然征象。` },
			{ polarity: (benefic.length ? 'positive' : 'neutral'), text: benefic.length ? `吉星 ${benefic.map(cn).join('/')} 状态尚可 → 助孕育之象。` : '吉星（木星/金星）受损 → 孕育征象偏弱，宜谨慎。' },
		];
		if(ascGender) lines.push({ polarity: 'neutral', text: `性别参考（仅一征象，勿单凭）：上升座属${ascGender === 'masculine' ? '阳（偏男）' : '阴（偏女）'}，须合5宫主/月亮阴阳同断。` });
		return { title: '怀孕（5宫子嗣 + 月木金自然征象）', lines };
	}
	return null;
}

export default buildTopicDeepening;
