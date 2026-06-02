// divination/election/rulePacks.js
// 27 用事专属规则包（择日清单 §6）：把 topicMaster 的 must_have / must_avoid 代码逐项检验，
// 命中=加分(正)，未满足/触犯=扣分(负)，并出可读文案。在通用 13 模块之上叠加。
import { aspectBetween } from '../engine/aspectsEngine.js';
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
function lord(facts, h){ return facts.houses[h] && facts.houses[h].ruler; }
function p(facts, k){ return facts.planets[k]; }
function retro(facts, k){ return !!(p(facts, k) && p(facts, k).retro); }
function inHouse(facts, k, hs){ const x = p(facts, k); return !!(x && hs.indexOf(x.house) >= 0); }
function goodAspect(facts, a, b){ if(!a || !b) return false; const x = aspectBetween(facts, a, b); return !!(x && [0, 60, 120].indexOf(x.angle) >= 0); }
function aspectAngle(facts, a, b){ const x = aspectBetween(facts, a, b); return x ? x.angle : null; }
function dignified(facts, k, min){ const x = p(facts, k); return !!(x && x.dignityScore >= (min === undefined ? 2 : min)); }

// must_avoid 检验：pass=已避开（好）
const AVOID_CHECK = {
	venus_retro: (f) => ({ pass: !retro(f, 'venus'), label: '金星不逆行' }),
	mercury_retro: (f) => ({ pass: !retro(f, 'mercury'), label: '水星不逆行' }),
	mercury_retro_for_contract: (f) => ({ pass: !retro(f, 'mercury'), label: '签约：水星不逆行' }),
	venus_retro_for_luxury: (f) => ({ pass: !retro(f, 'venus'), label: '高价物：金星不逆行' }),
	mars_retro: (f) => ({ pass: !retro(f, 'mars'), label: '火星不逆行' }),
	jupiter_retro: (f) => ({ pass: !retro(f, 'jupiter'), label: '木星不逆行' }),
	moon_in_scorpio: (f) => ({ pass: !(p(f, 'moon') && p(f, 'moon').sign === 'scorpio'), label: '月不落天蝎' }),
	moon_29deg: (f) => ({ pass: !(p(f, 'moon') && p(f, 'moon').signlon >= 29), label: '月不在 29°' }),
	moon_voc: (f) => ({ pass: !(p(f, 'moon') && p(f, 'moon').isVOC), label: '月不空亡' }),
	mars_in_1_or_7: (f) => ({ pass: !inHouse(f, 'mars', [1, 7]), label: '火星不在 1/7 宫' }),
	saturn_on_angle_1_7: (f) => ({ pass: !inHouse(f, 'saturn', [1, 4, 7, 10]), label: '土星不临角宫' }),
	uranus_on_angle_1_7: (f) => ({ pass: !inHouse(f, 'uranus', [1, 7]), label: '天王不在 1/7 宫' }),
	malefic_on_angle: (f) => ({ pass: !['mars', 'saturn'].some((k) => p(f, k) && p(f, k).angularity === 'angular' && p(f, k).dignityScore <= 0), label: '受剋凶星不临角宫' }),
	saturn_on_career_houses: (f) => ({ pass: !inHouse(f, 'saturn', [1, 2, 6, 8, 10]), label: '土星不入事业宫' }),
	saturn_in_12_property: (f) => ({ pass: !inHouse(f, 'saturn', [12]), label: '土星不在 12 宫' }),
	near_new_or_full_moon: (f) => ({ pass: !(f.meta.moonPhase && (f.meta.moonPhase.nearNew || f.meta.moonPhase.nearFull)), label: '不临新/满月' }),
	station_day: () => ({ pass: true, label: '当天无行星转停（需星历校验）', skip: true }),
	sun_in_12: (f) => ({ pass: !inHouse(f, 'sun', [12]), label: '太阳不落 12 宫' }),
	moon_in_6_or_12: (f) => ({ pass: !inHouse(f, 'moon', [6, 12]), label: '月不在 6/12 宫' }),
	malefic_in_1_3_9: (f) => ({ pass: !['mars', 'saturn'].some((k) => inHouse(f, k, [1, 3, 9])), label: '凶星不入 1/3/9 宫' }),
	moon_mars_hard: (f) => ({ pass: [90, 180].indexOf(aspectAngle(f, 'moon', 'mars')) < 0, label: '月火无刑冲' }),
	asc_mars_hard: (f) => ({ pass: true, label: '命度与火星无刑冲', skip: true }),
	moon_in_surgery_part_sign: () => ({ pass: true, label: '月不落手术部位星座（依部位）', skip: true }),
	neptune_afflicted: (f) => ({ pass: !['mars', 'saturn'].some((k) => [90, 180].indexOf(aspectAngle(f, 'neptune', k)) >= 0), label: '海王未受凶星刑冲' }),
};

// must_have 检验：pass=满足（好）
const HAVE_CHECK = {
	sun_moon_good_aspect: (f) => ({ pass: goodAspect(f, 'sun', 'moon'), label: '日月吉相（个性融洽）' }),
	venus_moon_good_aspect: (f) => ({ pass: goodAspect(f, 'venus', 'moon'), label: '金月吉相（感情融洽）' }),
	l1_l7_good_aspect: (f) => ({ pass: goodAspect(f, lord(f, 1), lord(f, 7)), label: '命主-7宫主吉相（关系长久）' }),
	venus_in_1_or_7: (f) => ({ pass: inHouse(f, 'venus', [1, 7]), label: '金星入 1/7 宫（爱情和谐）' }),
	venus_jupiter_aspect: (f) => ({ pass: goodAspect(f, 'venus', 'jupiter'), label: '金木吉相' }),
	l10_strong: (f) => { const l = lord(f, 10); return { pass: !!(l && p(f, l) && p(f, l).dignityScore >= 0 && !p(f, l).retro), label: '10宫主有力不逆' }; },
	sun_in_career_house: (f) => ({ pass: inHouse(f, 'sun', [1, 2, 6, 8, 10]), label: '太阳落事业宫且吉' }),
	moon_l4_good_aspect: (f) => ({ pass: goodAspect(f, 'moon', lord(f, 4)), label: '月-4宫主吉相' }),
	moon_saturn_trine: (f) => ({ pass: [60, 120].indexOf(aspectAngle(f, 'moon', 'saturn')) >= 0, label: '月土三合/六合（购地有利）' }),
	saturn_well_aspected: (f) => ({ pass: goodAspect(f, 'saturn', 'jupiter') || goodAspect(f, 'saturn', 'sun'), label: '土星有吉相（稳固）' }),
	moon_good_aspect: (f) => ({ pass: ['venus', 'jupiter'].some((k) => goodAspect(f, 'moon', k)), label: '月与吉星吉相' }),
	moon_good_aspect_fixed: (f) => ({ pass: ['venus', 'jupiter'].some((k) => goodAspect(f, 'moon', k)), label: '月与吉星吉相（固定宫佳）' }),
	jupiter_in_5: (f) => ({ pass: inHouse(f, 'jupiter', [5]), label: '木星入 5 宫（爱情）' }),
	jupiter_in_6: (f) => ({ pass: inHouse(f, 'jupiter', [6]), label: '木星入 6 宫（求职）' }),
	angular_benefic: (f) => ({ pass: ['venus', 'jupiter'].some((k) => p(f, k) && p(f, k).angularity === 'angular'), label: '吉星入角宫' }),
	mars_dignified: (f) => ({ pass: dignified(f, 'mars'), label: '火星入廟旺/有尊贵' }),
	l8_well_aspected: (f) => { const l = lord(f, 8); return { pass: !!(l && !['mars', 'saturn'].some((k) => [90, 180].indexOf(aspectAngle(f, l, k)) >= 0)), label: '8宫主无凶相' }; },
	asc_strong: (f) => { const l = lord(f, 1); return { pass: !!(l && p(f, l) && p(f, l).dignityScore >= 0 && !p(f, l).retro), label: '命主有力不逆' }; },
	neptune_well_aspected: (f) => ({ pass: ['venus', 'jupiter'].some((k) => goodAspect(f, 'neptune', k)), label: '海王有吉相' }),
	uranus_pluto_good_aspect: (f) => ({ pass: ['venus', 'jupiter', 'sun', 'moon'].some((k) => goodAspect(f, 'uranus', k) || goodAspect(f, 'pluto', k)), label: '天/冥有吉相（改变之力）' }),
	moon_in_disease_sign_well_aspected: (f) => ({ pass: ['venus', 'jupiter'].some((k) => goodAspect(f, 'moon', k)), label: '月落病所星座且吉相' }),
	venus_mercury_dignified: (f) => ({ pass: dignified(f, 'venus', 0) || dignified(f, 'mercury', 0), label: '金/水有尊贵' }),
	mercury_well_aspected: (f) => ({ pass: ['venus', 'jupiter'].some((k) => goodAspect(f, 'mercury', k)), label: '水星有吉相' }),
	moon_no_hard_aspect: (f) => ({ pass: !['mars', 'saturn'].some((k) => [90, 180].indexOf(aspectAngle(f, 'moon', k)) >= 0), label: '月无刑冲' }),
};

export function evaluateTopicPack(facts, topic){
	const items = [];
	(topic.must_have || []).forEach((code) => {
		const fn = HAVE_CHECK[code];
		if(!fn) return;
		const r = fn(facts);
		if(r.skip) return;
		items.push({ kind: 'have', code, label: r.label, pass: r.pass });
	});
	(topic.must_avoid || []).forEach((code) => {
		const fn = AVOID_CHECK[code];
		if(!fn) return;
		const r = fn(facts);
		if(r.skip) return;
		items.push({ kind: 'avoid', code, label: r.label, pass: r.pass });
	});
	const passed = items.filter((x) => x.pass).length;
	const total = items.length;
	const notes = topic.notes || '';
	return { items, passed, total, notes };
}

export default evaluateTopicPack;
