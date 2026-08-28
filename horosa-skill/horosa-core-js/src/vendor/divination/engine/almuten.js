// divination/engine/almuten.js
// Almuten（胜利星/总管，卜卦 03§7）：
//  (a) 逐度 almuten —— 对给定黄经，庙5/旺4/三分3(按昼夜)/界2/面1 加权累计，最高者胜（可并列）。
//  (b) Almuten Figuris —— 太阳/月亮/上升/福点/前次朔望 五关键点跨点求和，总分最高者=整盘总管。
// 结果对界系敏感（须与所选 termsVariant/tripSystem 联动）；权重可配（almuten_weights）。
// 文档算例（03§7，托勒密界）：火星摩羯27°昼盘 → 土5+2=7 / 火4 / 金3 / 日1 → almuten=土星。
import { SIGNS, signOfLon } from '../data/signs.js';
import { termRulerAt, termsVariantKey, faceAt, triplicityRulers } from '../data/dignities.js';
import { CHALDEAN_TERMS_DAY, CHALDEAN_TERMS_NIGHT, SIGN_EN } from '../data/hellenisticData.js';

const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
export const DEFAULT_ALMUTEN_WEIGHTS = { domicile: 5, exaltation: 4, triplicity: 3, term: 2, face: 1 };

// 界主查询（almuten 专用整流,亦供择日尊贵矩阵复用）：字符串/数字变体皆收；
// 迦勒底按昼夜取表（键为大写座名）。
export function termRulerForVariant(lon, opts){
	const raw = opts.termsVariant;
	const key = (typeof raw === 'number') ? termsVariantKey(raw) : (raw || 'ptolemaic');
	if(key === 'chaldean'){
		const tbl = opts.isDiurnal === false ? CHALDEAN_TERMS_NIGHT : CHALDEAN_TERMS_DAY;
		const signEn = SIGN_EN[Math.floor((((lon % 360) + 360) % 360) / 30)];
		const deg = ((lon % 360) + 360) % 360 % 30;
		const segs = tbl[signEn] || [];
		for(let i = 0; i < segs.length; i++){
			if(deg >= segs[i][1] && deg < segs[i][2]) return String(segs[i][0]).toLowerCase();
		}
		return segs.length ? String(segs[segs.length - 1][0]).toLowerCase() : null;
	}
	return termRulerAt(lon, key, { geminiEmended: !!opts.geminiEmended, customTermsDay: opts.customTermsDay, customTermsNight: opts.customTermsNight, isDiurnal: opts.isDiurnal });   // [R4-P2] 表体+昼夜透传
}

// (a) 逐度 almuten。opts：isDiurnal(默认 true)、termsVariant(默认'ptolemaic'=经典传本)、
// tripSystem('ptolemaic'|'dorothean'，默认 'ptolemaic'——水象昼夜皆火星)、weights、geminiEmended、
// tripIncludeParticipating(默认 false;true 时 Dorothean 共主也 +3)。
export function almutenAt(lon, opts){
	opts = opts || {};
	const W = { ...DEFAULT_ALMUTEN_WEIGHTS, ...(opts.weights || {}) };
	const isDay = opts.isDiurnal !== false;
	const sign = signOfLon(lon);
	const sgn = SIGNS[sign] || {};
	const scores = {};
	const breakdown = [];
	const add = (layer, planet, pts) => {
		if(!planet || SEVEN.indexOf(planet) < 0) return;   // almuten 只计七政（交点不入）
		scores[planet] = (scores[planet] || 0) + pts;
		breakdown.push({ layer, planet, pts });
	};
	add('domicile', sgn.domicile, W.domicile);
	if(sgn.exaltation && sgn.exaltation.planet) add('exaltation', sgn.exaltation.planet, W.exaltation);
	const trip = triplicityRulers(sgn.element, opts.tripSystem === 'dorothean' ? undefined : 'ptolemaic');
	if(trip){
		add('triplicity', isDay ? trip.day : trip.night, W.triplicity);
		if(opts.tripIncludeParticipating && trip.participating) add('triplicity_part', trip.participating, W.triplicity);
	}
	add('term', termRulerForVariant(lon, { ...opts, isDiurnal: isDay }), W.term);
	const face = faceAt(lon);
	if(face) add('face', face.ruler, W.face);

	let best = -1;
	Object.keys(scores).forEach((k) => { if(scores[k] > best) best = scores[k]; });
	const winners = Object.keys(scores).filter((k) => scores[k] === best).sort();
	return { lon, sign, scores, winners, best, breakdown };
}

// (b) Almuten Figuris：五关键点（日/月/上升/福点/前次朔望）跨点求和。
// syzygyLon 缺失时按文档口径降级（少一点参与并注明），不臆造。
export function almutenFiguris(facts, lots, opts){
	opts = opts || {};
	const caveats = [];
	const points = [];
	const push = (label, lon) => { if(lon !== null && lon !== undefined){ points.push({ label, lon }); } };
	push('太阳', facts.planets.sun && facts.planets.sun.lon);
	push('月亮', facts.planets.moon && facts.planets.moon.lon);
	push('上升', facts.meta.ascLon);
	push('福点', lots && lots.fortune && lots.fortune.lon);
	if(opts.syzygyLon !== null && opts.syzygyLon !== undefined){ push('前次朔望', opts.syzygyLon); }
	else { caveats.push('前次朔望黄经不可得：按四点计（缺一点参与，结果注明）。'); }

	const total = {};
	const per = points.map((pt) => {
		const r = almutenAt(pt.lon, { ...opts, isDiurnal: facts.meta.isDiurnal });
		Object.keys(r.scores).forEach((k) => { total[k] = (total[k] || 0) + r.scores[k]; });
		return { ...pt, sign: r.sign, scores: r.scores, winners: r.winners };
	});
	let best = -1;
	Object.keys(total).forEach((k) => { if(total[k] > best) best = total[k]; });
	const winners = Object.keys(total).filter((k) => total[k] === best).sort();
	return { points: per, totals: total, winners, best, caveats };
}

export default almutenAt;
