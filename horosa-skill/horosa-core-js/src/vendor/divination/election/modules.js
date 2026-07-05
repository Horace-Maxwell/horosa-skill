// divination/election/modules.js
// 13 个分析模块（择日清单 §3），按优先级=UI 顺序。每模块产 section{key,title,verdict,score,findings,detail}。
import { planetCondition } from '../engine/conditions.js';
import { moonReport } from '../engine/moon.js';
import { aspectsOf } from '../engine/aspectsEngine.js';
import { receptionsOf } from '../engine/reception.js';
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { FIXED_STARS, starLonAt } from '../data/fixedStars.js';
import { angularDist, norm360 } from '../engine/utils.js';
import { PLANETARY_HOURS, DAY_RULERS } from '../data/planetaryHours.js';
import { mansionOf, MANSION_ELECTION_SETS, TOPIC_MANSION_MAP } from '../data/lunarMansions.js';
import { paransAt } from '../engine/paransLocal.js';
import { radicality } from '../engine/radicality.js';
import { termRulerAt, faceAt, triplicityRulers } from '../data/dignities.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
function clamp(x){ return Math.max(0, Math.min(100, Math.round(x))); }
function verdictOf(s){ return s >= 70 ? 'good' : (s >= 52 ? 'neutral' : (s >= 38 ? 'caution' : 'bad')); }
function scoreFromFindings(findings, baseSeed){
	let s = baseSeed === undefined ? 60 : baseSeed;
	findings.forEach((f) => { s += (f.polarity === 'positive' ? 1 : (f.polarity === 'negative' ? -1 : 0)) * (f.weight || 1) * 6; });
	return clamp(s);
}
function lord1Of(facts){ const sg = facts.meta.ascSign; return SIGNS[sg] ? SIGNS[sg].domicile : null; }
const BENEFICS = ['jupiter', 'venus'];
const MALEFICS = ['mars', 'saturn'];

function mkFinding(polarity, message, weight){ return { polarity, message, text_zh: message, weight: weight || 1 }; }

function normLon(x){ return ((Number(x) % 360) + 360) % 360; }
// 取本盘公历年（用于恒星岁差修正）：优先读 /chart 回传的 params.birth/date；缺则用中性年（岁差差异 <1° 可忽略）。
function getChartYear(facts){
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ return Number(m[1]); } }
	}catch(e){ /* noop */ }
	return 2000;
}
// 两点的短弧中点（落入两点夹角较小一侧）。
function shortMidpoint(a, b){
	const m1 = normLon((Number(a) + Number(b)) / 2);
	const m2 = normLon(m1 + 180);
	return angularDist(m1, a) <= 90 ? m1 : m2;
}

function moonModule(facts){
	const r = moonReport(facts);
	const findings = r.findings.map((f) => ({ ...f, message: f.text_zh }));
	const score = scoreFromFindings(findings, 64);
	return { key: 'moon', title: '月亮（第一考量）', verdict: verdictOf(score), score, findings, detail_md: `月落 ${SIGNS[facts.planets.moon.sign] ? SIGNS[facts.planets.moon.sign].cn : ''}，${r.phase === 'waxing' ? '盈' : '亏'}。` };
}

function ascRulerModule(facts){
	const l = lord1Of(facts);
	const findings = [];
	if(l && facts.planets[l]){
		const p = facts.planets[l];
		if(p.retro) findings.push(mkFinding('negative', `命主星 ${cn(l)} 逆行（命主不可逆行）`, 3));
		if(p.dignityScore >= 4) findings.push(mkFinding('positive', `命主星 ${cn(l)} 有力（+${p.dignityScore}）`, 2));
		else if(p.dignityScore <= -4) findings.push(mkFinding('negative', `命主星 ${cn(l)} 落陷/弱`, 2));
		if(p.angularity === 'angular' || p.angularity === 'succedent') findings.push(mkFinding('positive', `命主星入${p.angularity === 'angular' ? '角' : '续'}宫`, 1));
		else if([3, 6, 9, 12].indexOf(p.house) >= 0) findings.push(mkFinding('negative', `命主星入弱宫(${p.house})`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'asc_ruler', title: '命主星（第二考量）', verdict: verdictOf(score), score, findings, detail_md: l ? `命主星 = ${cn(l)}` : '命主星未定' };
}

function ascendantModule(facts, topic){
	const findings = [];
	const sg = facts.meta.ascSign;
	const mod = SIGNS[sg] ? SIGNS[sg].modality : null;
	const pref = (topic.preferred_asc_modality) || [];
	if(mod && pref.length){
		if(pref.indexOf(mod) >= 0) findings.push(mkFinding('positive', `命宫三方四正(${mod})匹配本用事偏好`, 2));
		else if(mod === 'mutable' && (topic.topic_id === 'marriage' || topic.topic_id === 'business')) findings.push(mkFinding('negative', '变动宫坐命（婚姻/事业忌）', 2));
	}
	const ad = facts.meta.ascDegree;
	if(ad !== null && ad !== undefined){
		if(ad > 28) findings.push(mkFinding('negative', `命度 ${ad.toFixed(1)}°>28°（变动气质）`, 1));
		else if(ad >= 1 && ad <= 5) findings.push(mkFinding('positive', `命度 ${ad.toFixed(1)}°（1–5°，固定性强）`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'ascendant', title: '命度/上升（第三考量）', verdict: verdictOf(score), score, findings, detail_md: `上升 ${SIGNS[sg] ? SIGNS[sg].cn : ''} ${ad !== null ? ad.toFixed(1) + '°' : ''}` };
}

function sunModule(facts){
	const findings = [];
	const s = facts.planets.sun;
	if(s){
		if([12].indexOf(s.house) >= 0) findings.push(mkFinding('negative', '太阳落 12 宫（出版/魅力类用事尤忌）', 1));
		const asp = aspectsOf(facts, 'sun').filter((a) => [60, 120].indexOf(a.angle) >= 0 && BENEFICS.indexOf(a.other) >= 0);
		if(asp.length) findings.push(mkFinding('positive', `太阳与吉星${asp[0].angle}°`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'sun', title: '太阳', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function anglesModule(facts){
	const findings = [];
	[1, 4, 7, 10].forEach(() => {});
	Object.keys(facts.planets).forEach((k) => {
		const p = facts.planets[k];
		if(p.angularity !== 'angular') return;
		if(BENEFICS.indexOf(k) >= 0 && p.dignityScore >= 0) findings.push(mkFinding('positive', `吉星 ${cn(k)} 入角宫`, 2));
		if(MALEFICS.indexOf(k) >= 0 && (p.dignityScore <= 0 || p.retro)) findings.push(mkFinding('negative', `凶星 ${cn(k)} 受剋入角宫`, 2));
		if(k === 'uranus' && (p.house === 1 || p.house === 7)) findings.push(mkFinding('negative', '天王星在 1/7 宫（变动/分离）', 2));
	});
	const score = scoreFromFindings(findings, 60);
	return { key: 'angles', title: '角宫吉凶分布（纳吉排凶）', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function maleficHandlingModule(facts){
	const findings = [];
	MALEFICS.forEach((k) => {
		const p = facts.planets[k]; if(!p) return;
		const hardNoHelp = aspectsOf(facts, k).filter((a) => [90, 180].indexOf(a.angle) >= 0);
		const benefHelp = aspectsOf(facts, k).filter((a) => [60, 120].indexOf(a.angle) >= 0 && BENEFICS.indexOf(a.other) >= 0);
		if(hardNoHelp.length && !benefHelp.length) findings.push(mkFinding('negative', `${cn(k)} 凶相无吉相援助`, 2));
		else if(benefHelp.length) findings.push(mkFinding('positive', `${cn(k)} 有吉相援助（化解）`, 1));
	});
	const score = scoreFromFindings(findings, 62);
	return { key: 'malefic_handling', title: '凶星处理', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function topicSigModule(facts, topic){
	const findings = [];
	(topic.natural_significators || []).forEach((k) => {
		const p = facts.planets[k]; if(!p) return;
		const c = planetCondition(k, facts);
		if(c.score > 0) findings.push(mkFinding('positive', `自然徵象星 ${cn(k)} 有力(+${c.score})`, 2));
		else if(c.score < 0) findings.push(mkFinding('negative', `自然徵象星 ${cn(k)} 受剋(${c.score})`, 2));
		if(p.retro) findings.push(mkFinding('negative', `自然徵象星 ${cn(k)} 逆行`, 2));
	});
	(topic.key_houses || []).slice(0, 2).forEach((hn) => {
		const lord = facts.houses[hn] && facts.houses[hn].ruler;
		if(lord && facts.planets[lord]){
			const c = planetCondition(lord, facts);
			if(c.score < 0) findings.push(mkFinding('negative', `${hn}宫主 ${cn(lord)} 受剋`, 1));
			else if(c.score > 0) findings.push(mkFinding('positive', `${hn}宫主 ${cn(lord)} 有力`, 1));
		}
	});
	const score = scoreFromFindings(findings, 60);
	return { key: 'topic_significators', title: '徵象星（自然+宫主）', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function topicHouseModule(facts, topic){
	const findings = [];
	const hn = (topic.key_houses || [])[0];
	if(hn && facts.houses[hn]){
		(facts.houses[hn].planets || []).forEach((k) => {
			if(BENEFICS.indexOf(k) >= 0) findings.push(mkFinding('positive', `吉星 ${cn(k)} 在用事宫(${hn})`, 1));
			if(MALEFICS.indexOf(k) >= 0) findings.push(mkFinding('negative', `凶星 ${cn(k)} 在用事宫(${hn})`, 1));
		});
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'topic_house', title: '用事宫本身', verdict: verdictOf(score), score, findings, detail_md: hn ? `用事宫 = ${hn} 宫` : '' };
}

function aspectPatternsModule(facts){
	// 检测：大三角 / 风筝 / 三刑会沖(T) / 大十字 / 星聚。择日喜大三角·风筝·小三角·矩形，忌 T·大十字。
	const findings = [];
	const ps = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].filter((k) => facts.planets[k]);
	const has = (a, b, ang) => aspectsOf(facts, a).some((x) => x.other === b && x.angle === ang);
	// 大三角：三星两两 120°
	let grandTrine = null;
	for(let i = 0; i < ps.length && !grandTrine; i++){
		for(let j = i + 1; j < ps.length && !grandTrine; j++){
			for(let k = j + 1; k < ps.length && !grandTrine; k++){
				if(has(ps[i], ps[j], 120) && has(ps[j], ps[k], 120) && has(ps[i], ps[k], 120)){ grandTrine = [ps[i], ps[j], ps[k]]; }
			}
		}
	}
	if(grandTrine){
		findings.push(mkFinding('positive', `大三角格局（${grandTrine.map(cn).join('·')}，能量和谐·吉）`, 2));
		// 风筝：第四星对冲大三角某顶点
		let kite = false;
		grandTrine.forEach((v) => { if(!kite){ const opp = ps.find((p) => grandTrine.indexOf(p) < 0 && has(v, p, 180)); if(opp){ kite = true; } } });
		if(kite){ findings.push(mkFinding('positive', '风筝格局（大三角 + 对冲焦点，聚力·吉）', 1)); }
	}
	// 三刑会沖 T：两星对冲 + 皆 90° 第三星
	let tsquare = null;
	for(let i = 0; i < ps.length && !tsquare; i++){
		for(let j = i + 1; j < ps.length && !tsquare; j++){
			if(has(ps[i], ps[j], 180)){
				const apex = ps.find((p) => p !== ps[i] && p !== ps[j] && has(p, ps[i], 90) && has(p, ps[j], 90));
				if(apex){ tsquare = [ps[i], ps[j], apex]; }
			}
		}
	}
	if(tsquare){ findings.push(mkFinding('negative', `三刑会沖 T 格局（${tsquare.map(cn).join('·')}，张力·避）`, 2)); }
	// 大十字：≥2 组对冲
	const oppPairs = [];
	for(let i = 0; i < ps.length; i++){ for(let j = i + 1; j < ps.length; j++){ if(has(ps[i], ps[j], 180)){ oppPairs.push([ps[i], ps[j]]); } } }
	if(oppPairs.length >= 2){ findings.push(mkFinding('negative', '疑似大十字（两组对冲交织，巨张力·避）', 2)); }
	// 星聚：≥3 星同座
	const bySign = {};
	ps.forEach((k) => { const s = facts.planets[k].sign; if(s){ (bySign[s] = bySign[s] || []).push(k); } });
	Object.keys(bySign).forEach((s) => { if(bySign[s].length >= 3){ findings.push(mkFinding('neutral', `星聚 ${SIGNS[s] ? SIGNS[s].cn : s}（${bySign[s].map(cn).join('·')}，能量集中）`, 1)); } });
	const score = scoreFromFindings(findings, 60);
	return { key: 'aspect_patterns', title: '相位格局', verdict: verdictOf(score), score, findings, detail_md: '大三角 / 风筝 / 三刑会沖 / 大十字 / 星聚' };
}

function receptionModule(facts, topic){
	const findings = [];
	const recs = receptionsOf(facts, 'moon').filter((r) => r.strong);
	if(recs.length) findings.push(mkFinding('positive', '存在强接纳（可救援用事星）', 1));
	// 日月中点：吉/凶星合日月短弧中点（婚庆/合作类用事尤重）。
	const sun = facts.planets.sun; const moon = facts.planets.moon;
	if(sun && moon && sun.lon != null && moon.lon != null){
		const mid = shortMidpoint(sun.lon, moon.lon);
		['venus', 'jupiter', 'mars', 'saturn'].forEach((k) => {
			const p = facts.planets[k]; if(!p || p.lon == null) return;
			if(angularDist(p.lon, mid) <= 1.5){
				if(BENEFICS.indexOf(k) >= 0) findings.push(mkFinding('positive', `${cn(k)} 合日月中点（和合·吉）`, 1));
				else findings.push(mkFinding('negative', `${cn(k)} 合日月中点（扰动·忌）`, 1));
			}
		});
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'reception_fixedstar_midpoint', title: '接纳 / 日月中点', verdict: verdictOf(score), score, findings, detail_md: '强接纳救援 + 吉凶星合日月中点（≤1.5°）' };
}

function fixedStarsModule(facts, topic){
	const findings = [];
	const year = getChartYear(facts);
	const points = { 命度: facts.meta.ascLon, 天顶: facts.meta.mcLon, 太阳: facts.planets.sun && facts.planets.sun.lon, 月亮: facts.planets.moon && facts.planets.moon.lon };
	// 命主星
	const l1 = lord1Of(facts);
	if(l1 && facts.planets[l1]){ points[`命主星(${cn(l1)})`] = facts.planets[l1].lon; }
	// 用事自然徵象星
	(topic && topic.natural_significators || []).forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null){ points[`用事星(${cn(k)})`] = p.lon; } });
	Object.keys(points).forEach((label) => {
		const lon = points[label]; if(lon === null || lon === undefined) return;
		FIXED_STARS.forEach((st) => {
			if(angularDist(lon, starLonAt(st.lon_1995, year)) <= 1){
				if(st.election && st.election.avoid) findings.push(mkFinding('negative', `${label} 会合凶恒星 ${st.name_cn}（${st.meaning}）`, 2));
				else findings.push(mkFinding('positive', `${label} 会合吉恒星 ${st.name_cn}（${st.meaning}）`, 2));
			}
		});
	});
	const score = scoreFromFindings(findings, 60);
	return { key: 'fixed_stars', title: '恒星会合', verdict: verdictOf(score), score, findings, detail_md: `≤1° 会合关键点才计（岁差修正至 ${year} 年）` };
}

// ===== WP-1 宗派(sect)深化:昼夜派/得派吉凶星/hayz·halb/喜乐宫 =====
// 消费后端既有字段:meta.isDiurnal、p.ofSect(日木土昼/月金火夜/水按晨昏)、
// p.hayyiz('None'|'Hayyiz'|'DemiHayyiz'|'InWrongPos')、p.joy、p.aboveHorizon。
const SECT_SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
function sectModule(facts){
	const findings = [];
	const day = !!facts.meta.isDiurnal;
	const sectBenefic = day ? 'jupiter' : 'venus';    // 得派吉星=本盘首席吉星
	const outMalefic = day ? 'mars' : 'saturn';       // 离派凶星=本盘最须提防
	const inMalefic = day ? 'saturn' : 'mars';        // 得派凶星=凶性缓和

	findings.push(mkFinding('neutral', `${day ? '昼' : '夜'}盘：得派吉星为${cn(sectBenefic)}（首席吉星），离派凶星为${cn(outMalefic)}（凶性最烈）`, 1));

	const sb = facts.planets[sectBenefic];
	if(sb){
		if(sb.dignityScore >= 2 && !sb.retro) findings.push(mkFinding('positive', `得派吉星 ${cn(sectBenefic)} 有力顺行，可堪重用`, 2));
		if(sb.angularity === 'angular') findings.push(mkFinding('positive', `得派吉星 ${cn(sectBenefic)} 临角宫，助力直接`, 2));
	}
	const om = facts.planets[outMalefic];
	if(om){
		if(om.angularity === 'angular') findings.push(mkFinding('negative', `离派凶星 ${cn(outMalefic)} 临角宫：本盘最烈之凶落显位`, 3));
		else if(om.house && [3, 6, 9, 12].indexOf(om.house) >= 0) findings.push(mkFinding('positive', `离派凶星 ${cn(outMalefic)} 落果宫(${om.house})，凶性被边缘化`, 1));
	}
	const im = facts.planets[inMalefic];
	if(im && im.angularity === 'angular') findings.push(mkFinding('neutral', `得派凶星 ${cn(inMalefic)} 临角宫：虽凶但得派，凶性有节制`, 1));

	SECT_SEVEN.forEach((k) => {
		const p = facts.planets[k];
		if(!p) return;
		if(p.hayyiz === 'Hayyiz') findings.push(mkFinding('positive', `${cn(k)} 得时(hayz)：宗派/半球/阴阳座三者皆合，如人得志`, 2));
		else if(p.hayyiz === 'DemiHayyiz') findings.push(mkFinding('positive', `${cn(k)} 半得时(halb)，状态偏佳`, 1));
		else if(p.hayyiz === 'InWrongPos') findings.push(mkFinding('negative', `${cn(k)} 失时(逆其宗派之位)，如人失所`, 1));
		if(p.joy) findings.push(mkFinding('positive', `${cn(k)} 入喜乐宫，自得其乐`, 1));
	});

	const score = scoreFromFindings(findings, 60);
	return { key: 'sect', title: '宗派（昼夜派）', verdict: verdictOf(score), score, findings, detail_md: `${day ? '昼' : '夜'}盘。得时=宗派+半球+阴阳座三合；喜乐宫=水1月3金5火6日9木11土12。` };
}

// ===== WP-2 月相机制全集:传光/收光/阻碍/挫败/回避风险/围攻/野逸 =====
// 数据源=后端相位表(入相/出相+orb)+速度/逆行;凡涉「未来完成序」者按 orb 大小保守推断并明示口径。
const MOON_MECH_BENEFICS = ['jupiter', 'venus'];
const MOON_MECH_MALEFICS = ['mars', 'saturn'];
function isBen(k){ return MOON_MECH_BENEFICS.indexOf(k) >= 0; }
function isMal(k){ return MOON_MECH_MALEFICS.indexOf(k) >= 0; }
function moonMechanicsModule(facts){
	const findings = [];
	const moon = facts.planets.moon;
	if(!moon) return { key: 'moon_mechanics', title: '月相机制', verdict: 'neutral', score: 60, findings, detail_md: '' };
	// 全模块仅论七曜:传光/收光/阻碍/挫败为古典机制,不涉三王星;
	// 且三王星常年近守留速度,纳入会量产伪「挫败/回避」噪音。
	const ma = aspectsOf(facts, 'moon').filter((a) => SECT_SEVEN.indexOf(a.other) >= 0);
	const app = ma.filter((a) => a.applying);
	const sep = ma.filter((a) => a.separating);

	// 传光 translation of light:月刚离 A、正入 B → 把 A 之光传递给 B(连接两事)。
	sep.forEach((s) => {
		app.forEach((a) => {
			if(s.other === a.other) return;
			const pol = isMal(a.other) ? 'negative' : (isBen(a.other) ? 'positive' : 'neutral');
			findings.push(mkFinding(pol, `传光：月离 ${cn(s.other)}（${s.angle}°）转而入相 ${cn(a.other)}（${a.angle}°，差 ${a.orb != null ? Number(a.orb).toFixed(1) : '-'}°）——将前者之事引渡给后者${isMal(a.other) ? '，所托非人' : (isBen(a.other) ? '，善果可期' : '')}`, isMal(a.other) || isBen(a.other) ? 2 : 1));
		});
	});

	// 收光 collection of light:A、B 同时入相更慢的 X → X 汇集双方(第三方促成)。
	SECT_SEVEN.forEach((x) => {
		if(x === 'moon') return;
		const collectors = [];
		SECT_SEVEN.forEach((k) => {
			if(k === x) return;
			const ka = aspectsOf(facts, k).filter((a) => a.applying && a.other === x);
			if(ka.length) collectors.push(k);
		});
		const px = facts.planets[x];
		const slower = px && px.speed != null && collectors.every((k) => {
			const pk = facts.planets[k];
			return pk && pk.speed != null && Math.abs(px.speed) < Math.abs(pk.speed);
		});
		if(collectors.length >= 2 && slower){
			const pol = isMal(x) ? 'negative' : (isBen(x) ? 'positive' : 'neutral');
			findings.push(mkFinding(pol, `收光：${collectors.map(cn).join('、')} 同入相更慢的 ${cn(x)}——由${isMal(x) ? '凶星' : (isBen(x) ? '吉星' : '第三方')}居间汇集促成`, 2));
		}
	});

	// 阻碍 prohibition:月入相 B,另一七曜 C 亦入相 B 且差更小(先成相截走)。
	// 同一目标只报「最先成相」的一位阻碍者(其余更远者无实义,徒增噪音)。
	app.forEach((a) => {
		let best = null;
		SECT_SEVEN.forEach((c) => {
			if(c === 'moon' || c === a.other) return;
			aspectsOf(facts, c).forEach((x) => {
				if(x.applying && x.other === a.other && x.orb != null && a.orb != null && x.orb < a.orb){
					if(!best || x.orb < best.orb) best = { c, orb: x.orb };
				}
			});
		});
		if(best){
			findings.push(mkFinding('negative', `阻碍：${cn(best.c)} 先于月与 ${cn(a.other)} 成相（${Number(best.orb).toFixed(1)}° < ${Number(a.orb).toFixed(1)}°），月之所求被截走`, 2));
		}
	});

	// 挫败 frustration:月入相 B,而 B 自身先与他曜成相(入相差更小)→ B 无暇受月。
	// B 只会「先赴最紧一约」,故仅报其中差最小者。
	app.forEach((a) => {
		let best = null;
		aspectsOf(facts, a.other).forEach((x) => {
			if(x.applying && x.other !== 'moon' && SECT_SEVEN.indexOf(x.other) >= 0
				&& x.orb != null && a.orb != null && x.orb < a.orb){
				if(!best || x.orb < best.orb) best = x;
			}
		});
		if(best){
			findings.push(mkFinding('negative', `挫败：${cn(a.other)} 先赴与 ${cn(best.other)} 之约（${Number(best.orb).toFixed(1)}°），月的入相落空`, 1));
		}
	});

	// 回避风险 refranation:月正入相之星临守留/逆行(可能在成相前转向退出)。
	app.forEach((a) => {
		const p = facts.planets[a.other];
		if(p && ((p.speed != null && Math.abs(p.speed) < 0.05) || p.retro)){
			findings.push(mkFinding('negative', `回避风险：${cn(a.other)} ${p.retro ? '逆行' : '守留'}中，月入相恐未成先退（按现速推断）`, 1));
		}
	});

	// 围攻 besiegement:光线围攻(出相凶+入相凶)与体围攻(黄经两侧 7° 内被火土夹)。
	['moon', 'venus', 'jupiter', 'sun', 'mercury'].forEach((k) => {
		const p = facts.planets[k];
		if(!p) return;
		const ka = aspectsOf(facts, k);
		const sepMal = ka.some((a) => a.separating && isMal(a.other));
		const appMal = ka.some((a) => a.applying && isMal(a.other));
		if(sepMal && appMal){
			findings.push(mkFinding('negative', `光线围攻：${cn(k)} 离一凶复入一凶（火/土前后夹击），腹背受敌`, 2));
		}
		const mars = facts.planets.mars; const sat = facts.planets.saturn;
		if(mars && sat && p.lon != null){
			const dM = angularDist(p.lon, mars.lon); const dS = angularDist(p.lon, sat.lon);
			if(dM <= 7 && dS <= 7){
				findings.push(mkFinding('negative', `体围攻：${cn(k)} 黄经两侧 7° 内被火土同夹，处境艰险`, 2));
			}
		}
	});

	// 野逸 feral:全无托勒密相位(后端已判)。
	if(moon.feral) findings.push(mkFinding('negative', '月亮野逸（与七政全无主相位）：如野马无缰，行事无援', 2));

	if(!findings.length) findings.push(mkFinding('neutral', '月相机制平顺：无传光/收光/阻碍/挫败/围攻诸象', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'moon_mechanics', title: '月相机制（传光·收光·围攻）', verdict: verdictOf(score), score, findings, detail_md: '中世纪择日核心:月为万事之引线;凡涉先后成相者按现盘入相差推断。' };
}


// ===== WP-3 行星时/值日星:后端 timerStar/dayerStar 已算,此处判用事匹配与时主状态 =====
function planetaryHourModule(facts, topic){
	const findings = [];
	const hr = facts.meta.hourRuler;
	const dr = facts.meta.dayRuler;
	const sigs = (topic && topic.natural_significators) || [];
	if(!hr){
		findings.push(mkFinding('neutral', '本盘未回传行星时主星', 1));
		const score0 = scoreFromFindings(findings, 60);
		return { key: 'planetary_hours', title: '行星时（时主/日主）', verdict: verdictOf(score0), score: score0, findings, detail_md: '' };
	}
	const themes = PLANETARY_HOURS[hr];
	findings.push(mkFinding('neutral', `现值 ${cn(hr)} 之时、${dr ? cn(dr) : '—'} 之日${themes ? `；此时主题：${themes.join(' / ')}` : ''}`, 1));
	if(sigs.indexOf(hr) >= 0) findings.push(mkFinding('positive', `用事星 ${cn(hr)} 正当其时（首选:择事项主星之行星时）`, 2));
	if(dr && sigs.indexOf(dr) >= 0){
		findings.push(mkFinding('positive', `值日星 ${cn(dr)} 即用事星`, 1));
		if(dr === hr) findings.push(mkFinding('positive', '日时合一：值日星与时主同星，其力尤强', 2));
	}
	const hp = facts.planets[hr];
	if(hp){
		if(hp.dignityScore >= 2 && !hp.retro && !hp.combustion) findings.push(mkFinding('positive', `时主 ${cn(hr)} 有尊贵、顺行、免燃烧`, 1));
		if(hp.retro) findings.push(mkFinding('negative', `时主 ${cn(hr)} 逆行`, 1));
		if(hp.combustion === 'combust') findings.push(mkFinding('negative', `时主 ${cn(hr)} 燃烧`, 1));
		if(hp.angularity === 'angular') findings.push(mkFinding('positive', `时主 ${cn(hr)} 临角宫`, 1));
	}
	if((hr === 'mars' || hr === 'saturn') && sigs.indexOf(hr) < 0) findings.push(mkFinding('negative', `凶星 ${cn(hr)} 之时（非其所辖用事宜避）`, 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'planetary_hours', title: '行星时（时主/日主）', verdict: verdictOf(score), score, findings, detail_md: '值日星序:日月火水木金土(周日起);行星时按迦勒底序自日出轮转。' };
}

// ===== WP-4 月宿(西方28宿·Agrippa 白羊0°均分) =====
function mansionModule(facts, topic){
	const findings = [];
	const moon = facts.planets.moon;
	if(!moon || moon.lon == null){
		return { key: 'mansions', title: '月宿（西方28宿）', verdict: 'neutral', score: 60, findings, detail_md: '' };
	}
	const m = mansionOf(moon.lon);
	findings.push(mkFinding('neutral', `月在第 ${m.n} 宿 ${m.name}（${m.alt}）：${m.nature}。用途：${m.use}`, 1));
	const map = TOPIC_MANSION_MAP[topic && topic.topic_id];
	if(map){
		const goodSet = map.good ? MANSION_ELECTION_SETS[map.good] : null;
		const badSet = map.bad ? MANSION_ELECTION_SETS[map.bad] : null;
		if(goodSet && goodSet.indexOf(m.n) >= 0) findings.push(mkFinding('positive', `本宿正宜此用事（速查${map.good === 'travel_good' ? '·旅' : map.good === 'love' ? '·爱/婚姻' : map.good === 'gain' ? '·收益' : '·疗愈'}集）`, 2));
		else if(badSet && badSet.indexOf(m.n) >= 0) findings.push(mkFinding('negative', `本宿忌此用事（${map.bad === 'travel_bad' ? '阻旅行' : '毁灭/不和/分离'}集，专此意者除外）`, 2));
	}else if(m.good === false){
		findings.push(mkFinding('negative', '本宿性凶（毁灭/不和类），一般用事宜避', 1));
	}
	// 通则:月增光+不受克 于吉宿则善用
	const mp = facts.meta.moonPhase;
	if(m.good === true && mp && mp.phase === 'waxing' && !moon.combustion) findings.push(mkFinding('positive', '月增光、免燃烧而入吉宿：可乘其力', 1));
	if(moon.combustion === 'combust') findings.push(mkFinding('negative', '月燃烧：宿力难用（通则尤忌）', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'mansions', title: '月宿（西方28宿）', verdict: verdictOf(score), score, findings, detail_md: `Agrippa 白羊0°均分 12°51′26″/宿；通则:择月入所选宿、增光不受克、不空亡。` };
}

// ===== WP-5 映点隐合/隐冲(≤1°):映点=关于巨蟹0°轴对称(180−λ);反映点=关于白羊0°轴(360−λ) =====
const ANTISCIA_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
function antisciaModule(facts){
	const findings = [];
	const pts = [];
	ANTISCIA_KEYS.forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null) pts.push({ k, lon: p.lon }); });
	if(facts.meta.ascLon != null) pts.push({ k: 'asc', lon: facts.meta.ascLon, isPoint: true });
	const nameOf = (o) => (o.k === 'asc' ? '命度' : cn(o.k));
	for(let i = 0; i < pts.length; i++){
		for(let j = 0; j < pts.length; j++){
			if(i === j) continue;
			const a = pts[i]; const b = pts[j];
			if(a.isPoint) continue; // 映点只从行星投出,命度仅作受点
			const anti = norm360(180 - a.lon);
			const contra = norm360(360 - a.lon);
			const dA = angularDist(anti, b.lon);
			const dC = angularDist(contra, b.lon);
			if(i < j || b.isPoint){ // 行星对去重(i<j);受点=命度恒报
				if(dA <= 1){
					const mal = isMal(a.k) || isMal(b.k);
					findings.push(mkFinding(mal ? 'negative' : (isBen(a.k) || isBen(b.k) ? 'positive' : 'neutral'), `映点隐合：${nameOf(a)} 映点（${anti.toFixed(1)}°）合 ${nameOf(b)}（差 ${dA.toFixed(1)}°）——如暗中合相${mal ? '，凶星者尤须防暗损' : ''}`, 2));
				}
				if(dC <= 1){
					findings.push(mkFinding('negative', `反映点隐冲：${nameOf(a)} 反映点（${contra.toFixed(1)}°）冲 ${nameOf(b)}（差 ${dC.toFixed(1)}°）——如暗中对分`, 1));
				}
			}
		}
	}
	if(!findings.length) findings.push(mkFinding('neutral', '无 ≤1° 映点隐合/隐冲', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'antiscia', title: '映点（隐合/隐冲）', verdict: verdictOf(score), score, findings, detail_md: '映点=关于巨蟹0°—摩羯0°轴对称;反映点=关于白羊0°—天秤0°轴。仅 ≤1° 计。' };
}

// ===== WP-6 恒星交映(parans·Brady 口径·固定地点) =====
function paransModule(facts, topic){
	const findings = [];
	const params = (facts.result && facts.result.params) || {};
	// 空串防御:Number('')===0 会把「缺失」误当赤道 —— 非空才数值化。
	const lat = (params.gpsLat != null && params.gpsLat !== '') ? Number(params.gpsLat) : null;
	if(lat === null || !Number.isFinite(lat)){
		findings.push(mkFinding('neutral', '缺地理纬度，无法计算恒星交映', 1));
		return { key: 'parans', title: '恒星交映（parans）', verdict: 'neutral', score: 60, findings, detail_md: '' };
	}
	const year = getChartYear(facts);
	const stars = FIXED_STARS.slice(0, 10).map((st) => ({
		name_cn: st.name_cn, lon: starLonAt(st.lon_1995, year), dec: st.declination,
		avoid: !!(st.election && st.election.avoid), meaning: st.meaning,
		conditional: (st.election && st.election.conditional) || null,
	}));
	const bodies = [];
	ANTISCIA_KEYS.forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null) bodies.push({ key: k, cn: cn(k), lon: p.lon }); });
	const hits = paransAt(lat, bodies, stars, 2);
	// 同星同曜多轴命中只取最紧一对
	const seen = {};
	const sigs = (topic && topic.natural_significators) || [];
	hits.forEach((h) => {
		const kk = h.star + '|' + h.body;
		if(seen[kk]) return;
		seen[kk] = 1;
		const key = h.body === 'sun' || h.body === 'moon' || sigs.indexOf(h.body) >= 0;
		// 带条件限定的星(如「利事业不利婚姻」)不径直给正号:降 neutral 并附条件原文。
		const pol = h.avoid ? (key ? 'negative' : 'neutral') : (key && !h.conditional ? 'positive' : 'neutral');
		findings.push(mkFinding(pol, `${h.star} ${h.starAxis} 与 ${h.bodyCn} ${h.bodyAxis} 交映（差 ${h.diffMin} 分钟）——${h.meaning}${h.avoid && key ? '；凶星交映日/月/用事星须防' : ''}${h.conditional ? `（${h.conditional}）` : ''}`, h.avoid && key ? 2 : 1));
	});
	if(!Object.keys(seen).length) findings.push(mkFinding('neutral', '本时刻本地无紧恒星交映（≤8 分钟）', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'parans', title: '恒星交映（parans）', verdict: verdictOf(score), score, findings, detail_md: '固定地点:恒星与七曜四轴（升/中天/落/天底）恒星时差 ≤8 分钟判交映;行星按黄纬≈0 近似;主用 10 星。' };
}


// ===== WP-10a 可判性(radicality·Lilly 口径):这张盘本身可靠吗 =====
function radicalityModule(facts){
	const findings = [];
	let r = null;
	try{ r = radicality(facts); }catch(e){ r = null; }
	if(r){
		(r.ok || []).forEach((t) => findings.push(mkFinding('positive', t, 1)));
		(r.warnings || []).forEach((w) => findings.push(mkFinding('negative', w.text, 1)));
	}
	if(!findings.length) findings.push(mkFinding('neutral', '无可判性警告', 1));
	const score = scoreFromFindings(findings, 62);
	return { key: 'radicality', title: '可判性（盘之可靠）', verdict: verdictOf(score), score, findings, detail_md: '命度过早/过晚、月空/月燃、土星落一宫等——提示这一时刻的盘是否「可托付判断」,警告不阻断。' };
}

// ===== WP-10b 胜利星(Almuten Figuris·Ibn Ezra 法):命点五尊贵计分之总胜者 =====
// 五命点=日/月/命度/幸运点/产前朔望;事盘无产前朔望 → 按四命点计并注明。
// 计分:庙5 旺4 三分3(昼/夜/共各得3) 界2 面1。
const ALMUTEN_SCORE = { domicile: 5, exalt: 4, trip: 3, term: 2, face: 1 };
function almutenModule(facts){
	const findings = [];
	const pts = [];
	const sun = facts.planets.sun; const moon = facts.planets.moon; const fortune = facts.planets.fortune;
	if(sun && sun.lon != null) pts.push({ label: '太阳', lon: sun.lon });
	if(moon && moon.lon != null) pts.push({ label: '月亮', lon: moon.lon });
	if(facts.meta.ascLon != null) pts.push({ label: '命度', lon: facts.meta.ascLon });
	if(fortune && fortune.lon != null) pts.push({ label: '幸运点', lon: fortune.lon });
	const tally = {};
	const addScore = (k, v) => { if(k){ tally[k] = (tally[k] || 0) + v; } };
	pts.forEach((pt) => {
		const sg = SIGNS[signKeyOfLon(pt.lon)];
		if(!sg) return;
		addScore(sg.domicile, ALMUTEN_SCORE.domicile);
		if(sg.exaltation && sg.exaltation.planet && sg.exaltation.planet !== 'north_node' && sg.exaltation.planet !== 'south_node'){
			addScore(sg.exaltation.planet, ALMUTEN_SCORE.exalt);
		}
		const trips = triplicityRulers(sg.element);
		if(trips){ ['day', 'night', 'participating'].forEach((b) => addScore(trips[b], ALMUTEN_SCORE.trip)); }
		addScore(termRulerAt(pt.lon), ALMUTEN_SCORE.term);
		const fc = faceAt(pt.lon);
		addScore(fc && fc.ruler, ALMUTEN_SCORE.face);
	});
	const ranked = Object.keys(tally).sort((a, b) => tally[b] - tally[a]);
	if(!ranked.length){
		findings.push(mkFinding('neutral', '命点不足，无法计算胜利星', 1));
	}else{
		const top = ranked[0];
		const ties = ranked.filter((k) => tally[k] === tally[top]);
		findings.push(mkFinding('neutral', `胜利星（Almuten Figuris）：${ties.map(cn).join('、')}（${tally[top]} 分；按四命点计，事盘无产前朔望）`, 1));
		const p = facts.planets[top];
		if(p){
			if(p.dignityScore >= 2 && !p.retro) findings.push(mkFinding('positive', `胜利星 ${cn(top)} 在盘中有力顺行——全盘有主心骨`, 2));
			else if(p.retro || p.combustion === 'combust' || p.dignityScore <= -4) findings.push(mkFinding('negative', `胜利星 ${cn(top)} 受克（逆行/燃烧/落陷）——全盘乏主`, 2));
			if(p.angularity === 'angular') findings.push(mkFinding('positive', `胜利星 ${cn(top)} 临角宫`, 1));
		}
		const runner = ranked.slice(ties.length, ties.length + 2);
		if(runner.length) findings.push(mkFinding('neutral', `次位：${runner.map((k) => `${cn(k)}(${tally[k]})`).join('、')}`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'almuten', title: '胜利星（Almuten Figuris）', verdict: verdictOf(score), score, findings, detail_md: '命点(日/月/命度/幸运点)所在处五尊贵主星计分:庙5旺4三分3界2面1,总分最高者为全盘胜利星。' };
}

// 黄经 → 星座 key(供 almuten 用)
function signKeyOfLon(lon){
	const idx = Math.floor(normLon(lon) / 30);
	return ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'][idx];
}

export function runModules(facts, topic){
	return [
		moonModule(facts),
		ascRulerModule(facts),
		ascendantModule(facts, topic),
		topicSigModule(facts, topic),
		anglesModule(facts),
		topicHouseModule(facts, topic),
		sunModule(facts),
		maleficHandlingModule(facts),
		aspectPatternsModule(facts),
		receptionModule(facts, topic),
		fixedStarsModule(facts, topic),
		sectModule(facts),
		moonMechanicsModule(facts),
		planetaryHourModule(facts, topic),
		mansionModule(facts, topic),
		antisciaModule(facts),
		paransModule(facts, topic),
		radicalityModule(facts),
		almutenModule(facts),
	];
}

export default runModules;
