// 世运卜卦(古籍卜问篇)。机制同卜卦(可判性/入相完成/光线传递/互容),但问主=公众/国家,
// 宫义按世运读。三类问:战争/天气/物价。纯前端从 facts 派生(dignityScore/combustion/
// retro/house/ruler/mutuals 均后端现成),不重跑卜卦引擎。
const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
const DOMICILE = { aries: 'mars', taurus: 'venus', gemini: 'mercury', cancer: 'moon', leo: 'sun', virgo: 'mercury', libra: 'venus', scorpio: 'mars', sagittarius: 'jupiter', capricorn: 'saturn', aquarius: 'saturn', pisces: 'jupiter' };
const PLANET_CN = { sun: '日', moon: '月', mercury: '水', venus: '金', mars: '火', jupiter: '木', saturn: '土' };

export const MUNDANE_HORARY_KINDS = [
	{ key: 'war', cn: '战争 · 冲突' },
	{ key: 'weather', cn: '天气' },
	{ key: 'price', cn: '物价 · 收成' },
];

function houseRuler(facts, houseNo){
	const H = facts.houses || {};
	const h = H[houseNo];
	if(h && h.ruler){ return String(h.ruler).toLowerCase(); }
	if(h && h.sign){ return DOMICILE[String(h.sign).toLowerCase()] || null; }
	return null;
}

// 强弱评分(状态口径,回显明细):尊贵分 + 角宫 +3/果宫 −2 + 焦伤 −5/束下 −2 + 逆行 −4。
function sideStrength(facts, planetKey){
	const p = facts.planets[planetKey];
	if(!p){ return null; }
	const items = [];
	let score = 0;
	if(typeof p.dignityScore === 'number'){ score += p.dignityScore; items.push({ cn: '必然尊贵', v: p.dignityScore }); }
	if(p.house){
		if([1, 4, 7, 10].indexOf(p.house) >= 0){ score += 3; items.push({ cn: '角宫', v: +3 }); }
		else if([3, 6, 9, 12].indexOf(p.house) >= 0){ score -= 2; items.push({ cn: '果宫', v: -2 }); }
	}
	if(p.combustion === 'combust'){ score -= 5; items.push({ cn: '焦伤', v: -5 }); }
	else if(p.combustion === 'under_beams'){ score -= 2; items.push({ cn: '日光束下', v: -2 }); }
	if(p.retro){ score -= 4; items.push({ cn: '逆行', v: -4 }); }
	return { planet: planetKey, cn: PLANET_CN[planetKey] || planetKey, score, items, house: p.house, sign: p.sign };
}

function inMutualReception(facts, a, b){
	try{
		const mut = facts.result && facts.result.mutuals;
		if(!mut){ return false; }
		const list = Array.isArray(mut) ? mut : Object.keys(mut).map((k) => ({ a: k, b: mut[k] }));
		return list.some((m) => {
			const s = JSON.stringify(m).toLowerCase();
			return s.indexOf(String(a).toLowerCase()) >= 0 && s.indexOf(String(b).toLowerCase()) >= 0;
		});
	}catch(e){ return false; }
}

// ① 战争问:己=1 宫主+月;敌=7 宫主。较强/状态佳/受互容者胜;两主之间的光线传递=谈判/媾和。
export function describeWarQuestion(facts){
	if(!facts || !facts.planets || !facts.houses){ return null; }
	const usKey = houseRuler(facts, 1);
	const themKey = houseRuler(facts, 7);
	if(!usKey || !themKey){ return null; }
	const us = sideStrength(facts, usKey);
	const them = sideStrength(facts, themKey);
	const moon = sideStrength(facts, 'moon');
	if(!us || !them){ return null; }
	const usTotal = us.score + (moon && usKey !== 'moon' ? Math.round(moon.score / 2) : 0);   // 月半权归己方(问主=公众)
	const reception = inMutualReception(facts, usKey, themKey);
	let verdict;
	if(reception){ verdict = { tone: 'neutral', text: '双方主星互容——和解/盟约倾向压过胜负,宜谈判。' }; }
	else if(usTotal > them.score + 2){ verdict = { tone: 'us', text: '己方(一宫)显著较强——防御/进取皆有利。' }; }
	else if(them.score > usTotal + 2){ verdict = { tone: 'them', text: '敌方(七宫)显著较强——不宜启衅,宜守。' }; }
	else{ verdict = { tone: 'even', text: '两强相当——胜负系于状态与时机,慎断。' }; }
	return {
		us: { ...us, total: usTotal, role: '己方 · 一宫主' },
		them: { ...them, total: them.score, role: '敌方 · 七宫主' },
		moon: moon ? { ...moon, role: '月亮 · 公众/事态' } : null,
		reception,
		verdict,
		note: '两主之间若有光线传递(第三星先后与两主成相) → 谈判/媾和之象;详见卜卦盘完成法。',
	};
}

// ② 天气问:月所在宿 + 角宫行星 + 性质断(吉临角晴;土寒歉/火热旱火/月金雨)。
const WEATHER_BY_PLANET = {
	saturn: '寒冷、阴沉、歉收之象', mars: '燥热、干旱、火警之象', moon: '湿润、降雨之象',
	venus: '温润、降雨、宜农之象', jupiter: '温和、晴稳(临角尤主雨量充沛)', mercury: '多风、多变', sun: '晴朗、干燥',
};
export function describeWeatherQuestion(facts){
	if(!facts || !facts.planets){ return null; }
	const m = facts.planets.moon;
	const angular = [];
	['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].forEach((k) => {
		const p = facts.planets[k];
		if(p && [1, 4, 7, 10].indexOf(p.house) >= 0){ angular.push({ planet: k, cn: PLANET_CN[k], house: p.house, text: WEATHER_BY_PLANET[k] }); }
	});
	const wet = angular.filter((a) => ['moon', 'venus'].indexOf(a.planet) >= 0).length;
	const dry = angular.filter((a) => ['mars', 'sun'].indexOf(a.planet) >= 0).length;
	const cold = angular.filter((a) => a.planet === 'saturn').length;
	let tone = '合于时令,无显著倾向';
	if(wet > dry && wet >= 1){ tone = '偏湿——降雨倾向'; }
	else if(dry > wet && dry >= 1){ tone = '偏燥——干旱/高温倾向'; }
	if(cold){ tone += ';土星临角另主寒冷/歉收'; }
	return {
		moonMansion: m && m.su28 ? m.su28 : null,
		angular, tone,
		note: '以月所在宿为纲、临角行星为断;与入境/朔望盘天气卡互参。',
	};
}

// ③ 物价问:2/8/11 宫及主;入相/停滞逆行/互容判涨跌;歉收=4 宫受克+火土相会。
export function describePriceQuestion(facts){
	if(!facts || !facts.planets || !facts.houses){ return null; }
	const wealth = [2, 8, 11].map((h) => {
		const rk = houseRuler(facts, h);
		const st = rk ? sideStrength(facts, rk) : null;
		return { house: h, ruler: rk, strength: st };
	}).filter((x) => x.strength);
	if(!wealth.length){ return null; }
	const avg = wealth.reduce((s, x) => s + x.strength.score, 0) / wealth.length;
	const retroCount = wealth.filter((x) => facts.planets[x.ruler] && facts.planets[x.ruler].retro).length;
	let trend;
	if(avg >= 4 && retroCount === 0){ trend = { dir: 'up', text: '财货诸宫主强而顺行——供需活络,价稳中趋涨' }; }
	else if(avg <= 0 || retroCount >= 2){ trend = { dir: 'down', text: '财货诸宫主弱/多逆——市况迟滞,价疲趋跌' }; }
	else{ trend = { dir: 'flat', text: '强弱互见——价格盘整,以入相位方向定短势' }; }
	// 歉收判据:4 宫(庄稼)主受克(焦伤/逆行/落陷≤−4)或火土同宫。
	const fourth = houseRuler(facts, 4);
	const fSt = fourth ? sideStrength(facts, fourth) : null;
	const marsH = facts.planets.mars ? facts.planets.mars.house : null;
	const satH = facts.planets.saturn ? facts.planets.saturn.house : null;
	const cropRisk = !!((fSt && fSt.score <= -4) || (marsH && satH && marsH === satH));
	return {
		wealth, trend, cropRisk,
		cropNote: cropRisk ? '⚠ 四宫(庄稼)受克或火土相会——歉收风险,粮价看涨' : '四宫无重克——收成无显著凶象',
		note: '具体商品另配其座(如金=白羊与摩羯),以火/土行于商品座之 3/6/10/11 宫判涨;新/满月逢凶兆日物价涨。',
	};
}

export default { MUNDANE_HORARY_KINDS, describeWarQuestion, describeWeatherQuestion, describePriceQuestion };
