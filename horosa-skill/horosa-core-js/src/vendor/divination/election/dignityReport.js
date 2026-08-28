// divination/election/dignityReport.js
// 「尊贵强弱」页数据引擎：五重本质矩阵(随流派界/三分) + 偶然尊贵满分表(共用 scoreAccidental)
// + 接纳五级与「主人自陷弱接纳为害」 + 吉化/凶化条件清单 + 面神像取位。
// 全部为展示层派生(不回写 facts,不进核心十模块权重);吉化/凶化另以模块入非默认档权重。
import { SIGNS, signOfLon, SIGN_ORDER } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { triplicityRulers, faceAt, termRulerAt, DIGNITY_SCORE } from '../data/dignities.js';
import { termRulerForVariant } from '../engine/almuten.js';
import { scoreAccidental } from '../data/accidentalDignity.js';
import { receptionsOf } from '../engine/reception.js';
import { aspectsOf, applyingAspects } from '../engine/aspectsEngine.js';
import { isBesieged } from '../engine/conditions.js';
import { norm360, angularDist } from '../engine/utils.js';
import { classicalGlobalValue } from '../../utils/classicalChartGlobals.js';

const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
const OUTER = ['uranus', 'neptune', 'pluto'];
const BENEFICS = ['jupiter', 'venus'];
const MALEFICS = ['saturn', 'mars'];
export const cnOf = (k) => (PLANETS[k] || {}).cn || k;

function termRulerBy(facts, lon, eff){
	const v = eff ? eff.termsVariant : 0;
	if(!v) return termRulerAt(lon);
	return termRulerForVariant(lon, { termsVariant: v, isDiurnal: !!(facts.meta && facts.meta.isDiurnal) });
}

// ── 五重本质尊贵矩阵(逐星;随 eff.termsVariant/tripSystem)──────────────────
export function essentialMatrix(facts, eff){
	const isDay = !!facts.meta.isDiurnal;
	const tripVariant = (eff && eff.tripSystem === 'ptolemaic') ? 'ptolemaic' : undefined;
	const keys = SEVEN.concat((eff && eff.bodySet === 'classical7') ? [] : OUTER.filter((k) => facts.planets[k]));
	return keys.filter((k) => facts.planets[k]).map((k) => {
		const p = facts.planets[k];
		const sg = SIGNS[p.sign] || {};
		const trips = triplicityRulers(sg.element, tripVariant) || {};
		const row = {
			key: k, cn: cnOf(k), sign: p.sign, signCn: sg.cn || p.sign, signlon: p.signlon,
			domicile: sg.domicile === k,
			exaltation: !!(sg.exaltation && sg.exaltation.planet === k),
			triplicity: (isDay ? trips.day : trips.night) === k,
			triplicityPart: trips.participating === k,
			term: termRulerBy(facts, p.lon, eff) === k,
			face: (faceAt(p.lon) || {}).ruler === k,
			detriment: Array.isArray(sg.detriment) ? sg.detriment.indexOf(k) >= 0 : sg.detriment === k,
			fall: sg.fall === k,
		};
		row.peregrine = !(row.domicile || row.exaltation || row.triplicity || row.triplicityPart || row.term || row.face);
		let score = 0;
		if(row.domicile) score += DIGNITY_SCORE.domicile;
		if(row.exaltation) score += DIGNITY_SCORE.exaltation;
		if(row.triplicity || row.triplicityPart) score += DIGNITY_SCORE.triplicity;
		if(row.term) score += DIGNITY_SCORE.term;
		if(row.face) score += DIGNITY_SCORE.face;
		if(row.detriment) score += DIGNITY_SCORE.detriment;
		if(row.fall) score += DIGNITY_SCORE.fall;
		// [WP-4] 外来减分可调:默认 −5(1647 计分零回归)/0(不减,另派口径)——读全局仓单键。
		if(row.peregrine && !row.detriment && !row.fall){
			let pg = -5;
			try{
				const v = Number(classicalGlobalValue('peregrineScore'));
				if(Number.isFinite(v)){ pg = v; }
			}catch(e){ /* 守默认 */ }
			score += pg;
		}
		row.score = score;
		return row;
	});
}

// ── 偶然尊贵满分表(共用 data/accidentalDignity 单一真值)────────────────────
export function accidentalTable(facts, eff){
	const opts = eff ? { partileDef: eff.partileDef, fixedStarOrb: eff.fixedStarOrb, fixedStarOrbMode: eff.fixedStarOrbMode } : {};
	return SEVEN.filter((k) => facts.planets[k]).map((k) => ({ key: k, cn: cnOf(k), ...scoreAccidental(k, facts, opts) }));
}

// ── 接纳五级 + 由陷弱接纳为害 ─────────────────────────────────────────────
const GRADE_ORDER = ['ruler', 'exalt', 'trip', 'term', 'face'];
const GRADE_CN = { ruler: '庙(主要)', exalt: '旺(主要)', trip: '三分(次要)', term: '界(次要)', face: '面(最弱)' };
export function receptionGrade(tokens){
	const t = Array.isArray(tokens) ? tokens : [];
	for(let i = 0; i < GRADE_ORDER.length; i++){
		if(t.indexOf(GRADE_ORDER[i]) >= 0) return { token: GRADE_ORDER[i], cn: GRADE_CN[GRADE_ORDER[i]], rank: i + 1 };
	}
	return t.length ? { token: t[0], cn: String(t[0]), rank: 9 } : null;
}
export function receptionReport(facts){
	const seen = {};
	const out = [];
	SEVEN.forEach((k) => {
		receptionsOf(facts, k).forEach((r) => {
			const id = `${r.supplier}>${r.beneficiary}`;
			if(seen[id]) return;
			seen[id] = 1;
			const g = receptionGrade(r.supplierRulership);
			const host = facts.planets[r.supplier];
			const harmful = !!(host && host.dignityScore <= -4);
			out.push({
				supplier: r.supplier, supplierCn: cnOf(r.supplier),
				beneficiary: r.beneficiary, beneficiaryCn: cnOf(r.beneficiary),
				grade: g, band: r.band, strong: r.strong, harmful,
				text: `${cnOf(r.supplier)} 接纳 ${cnOf(r.beneficiary)}（${g ? g.cn : '—'}）${harmful ? '——主人自处陷/弱,由陷弱接纳反为害' : (r.strong ? '——庙旺主要接纳,可救援硬相' : '')}`,
			});
		});
	});
	return out.sort((a, b) => ((a.grade ? a.grade.rank : 9) - (b.grade ? b.grade.rank : 9)));
}

// ── 吉化 Bonification / 凶化 Maltreatment 条件清单 ─────────────────────────
// 判据(公开古籍通行口径):±3°入相合/优位整宫四分与三分(黄道在先者为主)/两侧体围合(±7°)
// /cazimi/背离其定位星(2·6·8·12 座不相见)/派内吉星执矛于区分光(合相式,先升 ≤15° 且未入日光束)。
function signIdxOf(sign){ return SIGN_ORDER.indexOf(sign); }
function overcomes(facts, aKey, bKey){
	const a = facts.planets[aKey]; const b = facts.planets[bKey];
	if(!a || !b) return null;
	const d = (signIdxOf(b.sign) - signIdxOf(a.sign) + 12) % 12;
	if(d === 3) return 'square';   // a 居 b 之右四分(优位)
	if(d === 4) return 'trine';    // a 居 b 之右三分(优位)
	return null;
}
export function bonificationReport(facts){
	const items = [];
	const add = (kind, key, text) => items.push({ kind, key, cn: cnOf(key), polarity: kind === 'bonify' ? 'positive' : 'negative', text });
	const bodies = SEVEN.filter((k) => facts.planets[k]);

	bodies.forEach((k) => {
		const p = facts.planets[k];
		// cazimi
		if(p.combustion === 'cazimi') add('bonify', k, `${cnOf(k)} 居日心（cazimi）——吉化:如得王座之护`);
		// ±3° 入相合
		applyingAspects(facts, k).forEach((x) => {
			if(x.angle !== 0 || typeof x.orb !== 'number' || x.orb > 3) return;
			if(BENEFICS.indexOf(x.other) >= 0) add('bonify', k, `${cnOf(k)} 与吉星 ${cnOf(x.other)} 3° 内入相合——吉化:吉星占上风迫其向善`);
			if(MALEFICS.indexOf(x.other) >= 0 && MALEFICS.indexOf(k) < 0) add('maltreat', k, `${cnOf(k)} 与凶星 ${cnOf(x.other)} 3° 内入相合——凶化:同度受击`);
		});
		// 优位凌制(整宫口径:黄道在先者为主)
		BENEFICS.forEach((b) => {
			if(b === k) return;
			const oc = overcomes(facts, b, k);
			if(oc === 'square') add('bonify', k, `${cnOf(b)} 自优位四分凌制 ${cnOf(k)}（整宫,右侧居先）——吉化强式`);
			else if(oc === 'trine') add('bonify', k, `${cnOf(b)} 自优位三分投光 ${cnOf(k)}——吉化`);
		});
		MALEFICS.forEach((m) => {
			if(m === k) return;
			const oc = overcomes(facts, m, k);
			if(oc === 'square') add('maltreat', k, `${cnOf(m)} 自优位四分凌制 ${cnOf(k)}（整宫,右侧居先）——凶化最烈式`);
		});
		// 体围合(±7° 两侧近邻;吉围/凶围)
		const others = bodies.filter((o) => o !== k && facts.planets[o].lon != null);
		if(p.lon != null && others.length >= 2){
			let prev = null; let next = null;
			others.forEach((o) => {
				const d = norm360(facts.planets[o].lon - p.lon);
				const dPrev = 360 - d;
				if(d > 0 && d <= 7 && (!next || d < next.d)) next = { o, d };
				if(dPrev > 0 && dPrev <= 7 && (!prev || dPrev < prev.d)) prev = { o, d: dPrev };
			});
			if(prev && next){
				const bothBen = BENEFICS.indexOf(prev.o) >= 0 && BENEFICS.indexOf(next.o) >= 0;
				const bothMal = MALEFICS.indexOf(prev.o) >= 0 && MALEFICS.indexOf(next.o) >= 0;
				if(bothBen) add('bonify', k, `${cnOf(k)} 两侧 7° 内为 ${cnOf(prev.o)}·${cnOf(next.o)} 吉星环抱——良性围合`);
				if(bothMal) add('maltreat', k, `${cnOf(k)} 两侧 7° 内被 ${cnOf(prev.o)}·${cnOf(next.o)} 凶星夹击——体围攻`);
			}
		}
		// 背离其定位星(2/6/8/12 座不相见)
		const disp = SIGNS[p.sign] ? SIGNS[p.sign].domicile : null;
		if(disp && disp !== k && facts.planets[disp]){
			const d = (signIdxOf(facts.planets[disp].sign) - signIdxOf(p.sign) + 12) % 12;
			if([1, 5, 7, 11].indexOf(d) >= 0){
				add('maltreat', k, `${cnOf(k)} 与其定位星 ${cnOf(disp)} 互处背离（第 ${d + 1} 座,无法相见相助）`);
			}
		}
	});
	// 光线围攻(surround 后端判定)
	['sun', 'moon', 'mercury', 'venus', 'jupiter'].forEach((k) => {
		if(facts.planets[k] && isBesieged(k, facts)) add('maltreat', k, `${cnOf(k)} 被土火围攻（光线/体,后端判定）——凶化`);
	});
	// 执矛(合相式):派内吉星先升于区分光 ≤15°;燃烧/日心者不算(日下光允许——
	// 对太阳而言 15° 窗必在光束下,古法以「先升可见」论,不因光束一票否决)。
	const light = facts.meta.isDiurnal ? 'sun' : 'moon';
	const guard = facts.meta.isDiurnal ? 'jupiter' : 'venus';
	const lp = facts.planets[light]; const gp = facts.planets[guard];
	if(lp && gp && lp.lon != null && gp.lon != null && gp.combustion !== 'combust' && gp.combustion !== 'cazimi'){
		const ahead = norm360(lp.lon - gp.lon);   // 吉星在光之先(先升)
		if(ahead > 0.3 && ahead <= 15){
			add('bonify', light, `${cnOf(guard)} 先升于${facts.meta.isDiurnal ? '太阳' : '月亮'} ${ahead.toFixed(1)}°（派内吉星执矛护卫·合相式）`);
		}
	}
	return items;
}

// ── 面神像取位(上升度/月度;表在 data/decanImages.DECAN_IMAGES_AGRIPPA)──────
export function facePositions(facts){
	const spots = [];
	const pushSpot = (label, lon) => {
		if(lon === null || lon === undefined) return;
		const sign = signOfLon(lon);
		const f = faceAt(lon);
		spots.push({ label, sign, signCn: SIGNS[sign] ? SIGNS[sign].cn : sign, faceIndex: f.faceIndex, ruler: f.ruler, rulerCn: cnOf(f.ruler) });
	};
	pushSpot('上升度', facts.meta.ascLon);
	pushSpot('月亮度', facts.planets.moon ? facts.planets.moon.lon : null);
	return spots;
}

export default essentialMatrix;
