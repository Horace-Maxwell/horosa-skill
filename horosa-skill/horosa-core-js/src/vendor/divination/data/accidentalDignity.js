// divination/data/accidentalDignity.js
// 偶然尊贵/无力满分表（1647 印本「Fortitudes and Debilities」全表，卜卦 03§10）。
// 总分域约 +38 ~ −38。与 conditions.js 的启发式权重并存：
//   accidentalMode='heuristic'(默认) → 本表不参与裁决（零回归）；
//   accidentalMode='lilly' → planetCondition 附带本表明细 + 以合计分极性入裁决（单条聚合项）。
// 本表只管「偶然」项；必然尊贵(庙旺三分界面/陷落/peregrine)在 signs/dignities 侧，勿混入。
import { MEAN_DAILY_MOTION, motionRateOf } from './planets.js';
import { FIXED_STARS, starLonAt, starOrbFor } from './fixedStars.js';
import { aspectsOf } from '../engine/aspectsEngine.js';
import { isBesieged } from '../engine/conditions.js';
import { angularDist } from '../engine/utils.js';

// 逐宫定分（10/1=+5，7/4/11=+4，2/5=+3，9=+2，3=+1；12=−5，8/6=−2）。
export const ACCIDENTAL_HOUSE_SCORES = { 1: 5, 10: 5, 7: 4, 4: 4, 11: 4, 2: 3, 5: 3, 9: 2, 3: 1, 12: -5, 8: -2, 6: -2 };

// 东出/西入计分按行星分组：♄♃♂ 东出+2/西入−2；☿♀ 西入+2/东出−2；☽以盈亏计；☉不计。
const ORIENTAL_PLUS = ['saturn', 'jupiter', 'mars'];
const OCCIDENTAL_PLUS = ['mercury', 'venus'];
const BENEFICS = ['jupiter', 'venus'];
const MALEFICS = ['saturn', 'mars'];

// partile（紧密相位）判定三口径：'same_degree'(1647 同整数度,默认) / 'le3'(1677) / 'le1'(现代)。
// 纯值版(2026-07 提炼):主盘相位表「正」标记列与判读计分共用同一判据,单一真值防双实现漂移。
export function isPartileByValues(signlonA, signlonB, orb, partileDef){
	const def = partileDef || 'same_degree';
	if(def === 'le1') return typeof orb === 'number' && orb <= 1;
	if(def === 'le3') return typeof orb === 'number' && orb <= 3;
	if(signlonA === undefined || signlonB === undefined || signlonA === null || signlonB === null){
		return typeof orb === 'number' && orb <= 1;
	}
	return Math.floor(signlonA) === Math.floor(signlonB);
}

export function isPartile(facts, a, b, aspectHit, partileDef){
	const pa = facts.planets[a]; const pb = facts.planets[b];
	return isPartileByValues(pa && pa.signlon, pb && pb.signlon, aspectHit.orb, partileDef);
}

function chartYearOf(facts){
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ return Number(m[1]); } }
	}catch(e){ /* noop */ }
	return 2000;
}

function starHit(facts, lon, starEn, opts){
	const st = FIXED_STARS.find((s) => s.name_en === starEn);
	if(!st || lon === null || lon === undefined) return false;
	const orb = starOrbFor(st, opts);
	return angularDist(lon, starLonAt(st.lon_1995, chartYearOf(facts))) <= orb;
}

// 主入口：对单星按满分表逐项计分。
// opts：partileDef / fixedStarOrb / fixedStarOrbMode / meanTable（水金均值地心争议档）。
// 返回 { total, items: [{key, score, text_zh}] }（items 仅含命中项）。
export function scoreAccidental(planetKey, facts, opts){
	opts = opts || {};
	const p = facts.planets[planetKey];
	if(!p) return { total: 0, items: [] };
	const items = [];
	const add = (key, score, text) => items.push({ key, score, text_zh: text });
	const isLight = planetKey === 'sun' || planetKey === 'moon';

	// 宫位
	if(p.house && ACCIDENTAL_HOUSE_SCORES[p.house] !== undefined){
		add('house', ACCIDENTAL_HOUSE_SCORES[p.house], `落 ${p.house} 宫（${ACCIDENTAL_HOUSE_SCORES[p.house] > 0 ? '+' : ''}${ACCIDENTAL_HOUSE_SCORES[p.house]}）`);
	}
	// 顺行+4（日月不适用）/ 逆行−5
	if(p.retro){
		add('retrograde', -5, '逆行（−5）');
	}else if(!isLight){
		add('direct', 4, '顺行（+4）');
	}
	// 迅疾+2 / 迟缓−2（vs 平均日行度）
	const rate = motionRateOf(planetKey, p.speed, opts);
	if(rate === 'swift') add('swift', 2, '行度迅疾（>平均日行度，+2）');
	else if(rate === 'slow') add('slow', -2, '行度迟缓（<平均日行度，−2）');
	// 东出/西入（分行星组）；月亮以渐盈/渐亏计
	if(ORIENTAL_PLUS.indexOf(planetKey) >= 0 && p.orientality){
		add('orientality', p.orientality === 'oriental' ? 2 : -2, p.orientality === 'oriental' ? '东出（♄♃♂ 东出 +2）' : '西入（♄♃♂ 西入 −2）');
	}else if(OCCIDENTAL_PLUS.indexOf(planetKey) >= 0 && p.orientality){
		add('orientality', p.orientality === 'occidental' ? 2 : -2, p.orientality === 'occidental' ? '西入（☿♀ 西入 +2）' : '东出（☿♀ 东出 −2）');
	}
	if(planetKey === 'moon' && facts.meta.moonPhase){
		add('moon_phase', facts.meta.moonPhase.phase === 'waxing' ? 2 : -2, facts.meta.moonPhase.phase === 'waxing' ? '月渐盈（+2）' : '月渐亏（−2）');
	}
	// 太阳三态（cazimi+5/焦伤−5/日下−4）；全然自由 +5
	if(planetKey !== 'sun'){
		if(p.combustion === 'cazimi') add('cazimi', 5, '在日心 cazimi（+5）');
		else if(p.combustion === 'combust') add('combust', -5, '燃烧（−5）');
		else if(p.combustion === 'under_beams') add('under_beams', -4, '在日光束下（−4）');
		else add('free_of_sun', 5, '脱离焦伤与光束（+5）');
	}
	// partile 相位项（合♃♀+5/拱+4/六合+3；合☊+4/合☋−4；合♄♂−5/冲−4/刑−4）——凶星自身与另一凶星互看仍计。
	const partileDef = opts.partileDef;
	aspectsOf(facts, planetKey).forEach((x) => {
		if(!isPartile(facts, planetKey, x.other, x, partileDef)) return;
		if(BENEFICS.indexOf(x.other) >= 0 && x.other !== planetKey){
			if(x.angle === 0) add('partile_conj_benefic', 5, `与${x.other === 'jupiter' ? '木星' : '金星'} partile 合（+5）`);
			else if(x.angle === 120) add('partile_trine_benefic', 4, `与${x.other === 'jupiter' ? '木星' : '金星'} partile 拱（+4）`);
			else if(x.angle === 60) add('partile_sextile_benefic', 3, `与${x.other === 'jupiter' ? '木星' : '金星'} partile 六合（+3）`);
		}
		if(MALEFICS.indexOf(x.other) >= 0 && x.other !== planetKey){
			if(x.angle === 0) add('partile_conj_malefic', -5, `与${x.other === 'saturn' ? '土星' : '火星'} partile 合（−5）`);
			else if(x.angle === 180) add('partile_opp_malefic', -4, `与${x.other === 'saturn' ? '土星' : '火星'} partile 冲（−4）`);
			else if(x.angle === 90) add('partile_square_malefic', -4, `与${x.other === 'saturn' ? '土星' : '火星'} partile 刑（−4）`);
		}
		if(x.other === 'north_node' && x.angle === 0) add('partile_conj_nnode', 4, '与北交点 partile 合（+4）');
		if(x.other === 'south_node' && x.angle === 0) add('partile_conj_snode', -4, '与南交点 partile 合（−4）');
	});
	// 王者/凶恒星（只取合相）
	if(starHit(facts, p.lon, 'Regulus', opts)) add('conj_regulus', 6, '合轩辕十四 Regulus（+6）');
	if(starHit(facts, p.lon, 'Spica', opts)) add('conj_spica', 5, '合角宿一 Spica（+5）');
	if(starHit(facts, p.lon, 'Algol', opts)) add('conj_algol', -5, '合大陵五 Algol（−5）');   // [H1c] 1647 传统 −5
	// 围攻
	if(isBesieged(planetKey, facts)) add('besieged', -5, '被土火围攻 besieged（−5）');   // [H1c] 1647 传统 −5(旧 −4 系数值偏差;死链修复时一并校正)

	const total = items.reduce((s, x) => s + x.score, 0);
	return { total, items };
}

export default scoreAccidental;
