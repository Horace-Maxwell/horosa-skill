// divination/election/rulePacks.js
// 37 用事专属规则包（择日清单 §6 + R2 六新分科）：把 topicMaster 的 must_have / must_avoid 代码逐项检验，
// 命中=加分(正)，未满足/触犯=扣分(负)，并出可读文案。在通用 13 模块之上叠加。
import { aspectBetween, aspectsOf, applyingAspects, separatingAspects } from '../engine/aspectsEngine.js';
import { moonReport } from '../engine/moon.js';
import { SIGNS, SIGN_ORDER } from '../data/signs.js';
import { PLANETS, motionRateOf } from '../data/planets.js';
import { FERTILE_SET, BARREN_SET } from '../data/signFertility.js';
import { angularDist, norm360 } from '../engine/utils.js';
import { aspectInProfile } from './orbPolicy.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
function lord(facts, h){ return facts.houses[h] && facts.houses[h].ruler; }
function p(facts, k){ return facts.planets[k]; }
function retro(facts, k){ return !!(p(facts, k) && p(facts, k).retro); }
function inHouse(facts, k, hs){ const x = p(facts, k); return !!(x && hs.indexOf(x.house) >= 0); }
// 两星相位查询随流派容许度档收紧(facts.eff.orbProfile;缺省/modern=后端表原样,零回归)。
function aspBetweenEff(facts, a, b){
	const x = aspectBetween(facts, a, b);
	if(!x) return null;
	const eff = facts.eff || null;
	if(eff && eff.orbProfile && eff.orbProfile !== 'modern' && !aspectInProfile(x, a, facts, eff.orbProfile)) return null;
	return x;
}
function goodAspect(facts, a, b){ if(!a || !b) return false; const x = aspBetweenEff(facts, a, b); return !!(x && [0, 60, 120].indexOf(x.angle) >= 0); }
function aspectAngle(facts, a, b){ const x = aspBetweenEff(facts, a, b); return x ? x.angle : null; }
function dignified(facts, k, min){ const x = p(facts, k); return !!(x && x.dignityScore >= (min === undefined ? 2 : min)); }
// 空亡随流派口径解算(缺省=后端 isVOC,零回归)。
function moonVocEff(facts){
	const eff = facts.eff || null;
	if(!eff || !eff.vocMode || eff.vocMode === 'classic') return !!(p(facts, 'moon') && p(facts, 'moon').isVOC);
	return !!moonReport(facts, { vocMode: eff.vocMode, vocIncludeOuter: !!eff.vocIncludeOuter }).voc;
}

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
	moon_voc: (f) => ({ pass: !moonVocEff(f), label: '月不空亡' }),
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
	moon_in_surgery_part_sign: (f, opts) => {
		// WP-8:部位经 opts.surgeryPart(星座 id)指定后真判;未指定沿现状 skip(零回归)。
		// R2:opts.surgeryPartOpposite=true 时延及对宫(诸家多延及,默认关=零回归)。
		const part = opts && opts.surgeryPart;
		if(!part || !SIGNS[part]) return { pass: true, label: '月不落手术部位星座（依部位）', skip: true };
		const moon = f.planets.moon;
		const parts = (SIGNS[part].body_parts || []).join('/');
		let bad = !!(moon && moon.sign === part);
		let oppNote = '';
		if(opts && opts.surgeryPartOpposite){
			const oppSign = SIGN_ORDER[(SIGN_ORDER.indexOf(part) + 6) % 12];
			if(moon && moon.sign === oppSign) bad = true;
			oppNote = '·延及对宫';
		}
		return { pass: !bad, label: `月不落手术部位星座（${SIGNS[part].cn}·${parts}${oppNote}）` };
	},
	// ── R2 六新分科 avoid 族 ─────────────────────────────────────────
	moon_in_barren_sign: (f) => ({ pass: !(p(f, 'moon') && BARREN_SET.indexOf(p(f, 'moon').sign) >= 0), label: '月不落不育座（白羊/双子/狮子/室女/人马/宝瓶）' }),
	moon_near_nodes: (f) => {
		const m = p(f, 'moon'); const nn = p(f, 'north_node'); const sn = p(f, 'south_node');
		const nodeLon = nn ? nn.lon : (sn ? norm360(sn.lon + 180) : null);
		if(!m || nodeLon === null) return { pass: true, label: '月不近交点/食处', skip: nodeLon === null };
		const d = Math.min(angularDist(m.lon, nodeLon), angularDist(m.lon, norm360(nodeLon + 180)));
		return { pass: d > 12, label: '月不近交点/食处（12° 外,避近食启航）' };
	},
	l1_weak_vs_l7: (f) => {
		const a = lord(f, 1); const b = lord(f, 7);
		const pa = a && p(f, a); const pb = b && p(f, b);
		if(!pa || !pb) return { pass: true, label: '己方不弱于对方', skip: true };
		const bad = pa.dignityScore < pb.dignityScore - 4 || pa.combustion === 'combust' || pa.house === 8;
		return { pass: !bad, label: '己方象征不显弱于对方（不燃烧/不落8宫/尊贵不悬殊）' };
	},
	l1_in_12_or_8: (f) => { const l = lord(f, 1); return { pass: !(l && p(f, l) && [8, 12].indexOf(p(f, l).house) >= 0), label: '上升主不落 8/12 宫（不释或狱中之兆）' }; },
	moon_hard_from_saturn_or_mars: (f) => ({ pass: !['saturn', 'mars'].some((k) => [0, 90, 180].indexOf(aspectAngle(f, 'moon', k)) >= 0), label: '月不受土（干枯脱发）火（粗糙断裂）合刑冲' }),
	talisman_ruler_afflicted: (f, opts) => {
		const star = opts && opts.talismanStar;
		if(!star || !p(f, star)) return { pass: true, label: '护符主星不受克（选主星后判）', skip: true };
		const x = p(f, star);
		const bad = x.retro || x.combustion === 'combust' || (x.signlon !== undefined && x.signlon >= 28);
		return { pass: !bad, label: `护符主星 ${cn(star)} 不逆行/不燃烧/不在座末` };
	},
	neptune_afflicted: (f) => ({ pass: !['mars', 'saturn'].some((k) => [90, 180].indexOf(aspectAngle(f, 'neptune', k)) >= 0), label: '海王未受凶星刑冲' }),
};

// must_have 检验：pass=满足（好）
const HAVE_CHECK = {
	sun_moon_good_aspect: (f) => ({ pass: goodAspect(f, 'sun', 'moon'), label: '日月吉相（个性融洽）' }),
	venus_moon_good_aspect: (f) => ({ pass: goodAspect(f, 'venus', 'moon'), label: '金月吉相（感情融洽）' }),
	l1_l7_good_aspect: (f) => ({ pass: goodAspect(f, lord(f, 1), lord(f, 7)), label: '命主-7宫主吉相（关系长久）' }),
	// [R2 修] move_in 引用多年而检查缺席(静默跳过)——补上:命主与四宫主吉相=人宅相安。
	l1_l4_good_aspect: (f) => ({ pass: goodAspect(f, lord(f, 1), lord(f, 4)), label: '命主-4宫主吉相（人宅相安）' }),
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
	// ── R2 六新分科 have 族 ──────────────────────────────────────────
	moon_in_fertile_sign: (f) => {
		const m = p(f, 'moon');
		return { pass: !!(m && FERTILE_SET.indexOf(m.sign) >= 0), label: '月落多产座（巨蟹/天蝎/双鱼首推,金牛次之）' };
	},
	moon_waxing_for_growth: (f) => ({ pass: !!(f.meta.moonPhase && f.meta.moonPhase.phase === 'waxing'), label: '月增光（生长/求取/释放之事宜）' }),
	moon_in_water_sign: (f) => { const m = p(f, 'moon'); return { pass: !!(m && SIGNS[m.sign] && SIGNS[m.sign].element === 'water'), label: '月落水象座（合航海之元素）' }; },
	moon_free_from_malefic_strict: (f) => {
		// 航海严格式:月与火/土全无托勒密相位(入相出相皆不沾)。
		const hits = aspectsOf(f, 'moon').filter((a) => ['mars', 'saturn'].indexOf(a.other) >= 0);
		return { pass: hits.length === 0, label: '月绝对免土火（无任何相位——海难之典型签为月受凶克）' };
	},
	l4_strong: (f) => { const l = lord(f, 4); return { pass: !!(l && p(f, l) && p(f, l).dignityScore >= 0 && !p(f, l).retro), label: '4宫主有力不逆（土地/作物之根）' }; },
	l9_strong: (f) => { const l = lord(f, 9); return { pass: !!(l && p(f, l) && p(f, l).dignityScore >= 0 && !p(f, l).retro), label: '9宫主有力不逆（航程之主）' }; },
	l1_stronger_than_l7: (f) => {
		const a = lord(f, 1); const b = lord(f, 7);
		const pa = a && p(f, a); const pb = b && p(f, b);
		if(!pa || !pb) return { pass: false, label: '己方（1宫主）强于对方（7宫主）', skip: !pa && !pb };
		return { pass: pa.dignityScore > pb.dignityScore || (pa.dignityScore === pb.dignityScore && pa.angularity === 'angular' && pb.angularity !== 'angular'), label: '己方（1宫主）强于对方（7宫主）' };
	},
	moon_separating_l7_applying_l1: (f) => {
		const l1 = lord(f, 1); const l7 = lord(f, 7);
		if(!l1 || !l7) return { pass: true, label: '月离对方入相己方', skip: true };
		const sep7 = separatingAspects(f, 'moon').some((a) => a.other === l7);
		const app1 = applyingAspects(f, 'moon').some((a) => a.other === l1);
		return { pass: sep7 && app1, label: '月离 7 宫主而入相 1 宫主（运流向己）' };
	},
	moon_increasing_speed: (f) => {
		const m = p(f, 'moon');
		return { pass: !!(m && motionRateOf('moon', m.speed) === 'swift'), label: '月行速增（快于平均日行——自由渐长）' };
	},
	moon_sep_mal_app_ben: (f) => {
		const sepMal = separatingAspects(f, 'moon').some((a) => ['mars', 'saturn'].indexOf(a.other) >= 0);
		const appBen = applyingAspects(f, 'moon').some((a) => ['venus', 'jupiter'].indexOf(a.other) >= 0);
		return { pass: sepMal && appBen, label: '月离凶入吉（离土/火而入相木/金）' };
	},
	l12_weak: (f) => {
		const l = lord(f, 12);
		if(!l || !p(f, l)) return { pass: true, label: '12宫主（狱）转弱', skip: true };
		const x = p(f, l);
		return { pass: x.dignityScore < 0 || x.angularity === 'cadent' || !!x.combustion, label: '12宫主（狱）转弱（陷弱/果宫/焰下任一）' };
	},
	talisman_ruler_dignified_angular: (f, opts) => {
		const star = opts && opts.talismanStar;
		if(!star || !p(f, star)) return { pass: true, label: '护符主星庙旺+临升/中天（选主星后判）', skip: true };
		const x = p(f, star);
		const dign = x.dignityScore >= 4;
		let nearAxis = false;
		if(x.lon != null){
			if(f.meta.ascLon != null && angularDist(x.lon, f.meta.ascLon) <= 10) nearAxis = true;
			if(f.meta.mcLon != null && angularDist(x.lon, f.meta.mcLon) <= 10) nearAxis = true;
		}
		const angular = x.house === 1 || x.house === 10;
		return { pass: dign && (nearAxis || angular), label: `护符主星 ${cn(star)} 庙旺且临升/中天（距轴 10° 内最佳）` };
	},
	planetary_day_hour_match: (f, opts) => {
		const star = opts && opts.talismanStar;
		if(!star) return { pass: true, label: '行星日/时匹配护符主星（选主星后判）', skip: true };
		const hourHit = f.meta.hourRuler === star;
		const dayHit = f.meta.dayRuler === star;
		return { pass: hourHit, label: `现值${hourHit ? '正是' : '非'} ${cn(star)} 之时${dayHit ? '＋其之日（日时合一尤强）' : (hourHit ? '（若兼其日更强）' : '')}` };
	},
	trade_side_strength: (f, opts) => {
		const side = opts && opts.tradeSide;
		if(!side) return { pass: true, label: '售强己方/购强对方（选方向后判）', skip: true };
		const a = lord(f, 1); const b = lord(f, 7);
		const pa = a && p(f, a); const pb = b && p(f, b);
		if(!pa || !pb) return { pass: true, label: '买卖方向判据', skip: true };
		if(side === 'sell'){
			const l7AppL1 = applyingAspects(f, b).some((x) => x.other === a);
			return { pass: pa.dignityScore >= pb.dignityScore, label: `售:己方(1宫主${cn(a)})强于对方${l7AppL1 ? '，且对方入相己方（买家来你）' : ''}` };
		}
		return { pass: pb.dignityScore >= pa.dignityScore, label: `购:货主方(7宫主${cn(b)})强——所购之物有主而实` };
	},
};

// opts:西方深化扩展(surgeryPart 等);检查函数第二参可选、不消费者行为不变。
export function evaluateTopicPack(facts, topic, opts){
	const items = [];
	(topic.must_have || []).forEach((code) => {
		const fn = HAVE_CHECK[code];
		if(!fn) return;
		const r = fn(facts, opts);
		if(r.skip) return;
		items.push({ kind: 'have', code, label: r.label, pass: r.pass });
	});
	(topic.must_avoid || []).forEach((code) => {
		const fn = AVOID_CHECK[code];
		if(!fn) return;
		const r = fn(facts, opts);
		if(r.skip) return;
		items.push({ kind: 'avoid', code, label: r.label, pass: r.pass });
	});
	const passed = items.filter((x) => x.pass).length;
	const total = items.length;
	const notes = topic.notes || '';
	return { items, passed, total, notes };
}

export default evaluateTopicPack;
