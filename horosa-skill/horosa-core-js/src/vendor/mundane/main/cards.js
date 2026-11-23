// 世俗盘右栏卡片段与排盘设置跨会话保留
// 从 MundaneMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { rulesetConfig, MUNDANE_RULESETS } from '../ruleset.js';

import { MUNDANE_HOUSE_MEANINGS, describeEclipse, describeEclipseAfflictions, mundaneFixedStarHits, PLANET_CN as MUN_PLANET_CN, describeMundaneWeather, describeSpecialAxes, mundaneConjunctionIndicator, buildMundaneStarPoints } from '../describe.js';
import { describeSarosFamily } from '../saros.js';
import { describeQuadrantNations } from '../omenology.js';
import { mundaneDistribution, mundanePatternMeaning } from '../patterns.js';
// headless stub：AstroExtraCommon 是 React 页面公共件，不 vendor。chartRequestKey 只用于 [盘型格局] 的
// `st.patKey === chartRequestKey(chart)` 缓存一致性判定——headless 的相位格局就是对**同一张盘**现取的，
// 故恒等键即正解：调用方（tools/mundaneCards.js）传 patKey 时用同一常量 HEADLESS_PAT_KEY。
const chartRequestKey = () => 'headless';
import { describeSolunar, isDormantChart, SOLUNAR_WEIGHTS, ANGULARITY_ORBS } from '../solunar.js';
import { segmentIndex } from '../../utils/segmentIndex.js';
import { NAKSHATRA_27, NAK_KEYPOINTS, munthaSign, vimshottariFromMoon, PLANET_CN_V, kpSubLordAt, garbhaDeliveryDate, GARBHA_CONST } from '../vedicMundane.js';
import { datePartOf } from '../../bazi/dateStrSafe.js';
import { describeWarQuestion, describeWeatherQuestion, describePriceQuestion } from '../mundaneHorary.js';
import { SIGNS } from '../../divination/data/signs.js';
import { ingressGovernance } from '../momentPipeline.js';
import { computeConjunctionEras } from '../conjunctionEras.js';
import { computeCurrentAge, GREAT_YEAR_CONST } from '../greatYear.js';
import { definePageSettings } from '../../utils/pageSettingsStore.js';
import { shellFieldSchema } from '../../utils/divinationShellSettings.js';
import { safeFacts, ascRuler, INGRESSES, currentYear, MODALITY_CN, SEASON_INGRESS_CN, clampYear, MUN_SIGN_CN, MUN_PCN, munSignOf, norm360m, munDegInSign, ELEMENT_CN, CYCLE_PAIRS, yearLabel, SIGN_KEYS, computeAges, dignityText, BARBAULT_SETS, BARBAULT_HARMONICS } from './tables.js';

export function buildMundaneCardSections(chart, extra, state, facts){
	const ex = extra || {};
	const st = state || {};
	const type = ex.mundaneType || 'ingress';
	const cfg = rulesetConfig(ex.mundaneRuleset);
	const out = [];
	const push = (lines) => { if(lines && lines.length > 1){ out.push(lines.join('\n')); } };
	if(!chart){ return out; }
	const f = facts || safeFacts(chart);
	const isNatalLike = type !== 'cycles';

	// ── 概览页 ──
	if(type === 'ingress'){
		try{
			const yl = ascRuler(chart);
			const ing = INGRESSES.find((i) => i.term === (ex.ingressTerm || '春分'));
			const effRule = (ex.mundaneIngressRule && ex.mundaneIngressRule !== 'auto') ? ex.mundaneIngressRule : cfg.ingressRule;
			const gov = yl ? ingressGovernance(yl.signKey, effRule, ex.ingressTerm || '春分') : null;
			if(ex.ingressMoment && yl){
				const L = ['[年盘概要]', `${ex.ingressYear != null ? ex.ingressYear : currentYear()} 年 · ${ing ? ing.label.split('（')[0] : '春分入宫'} · 入宫时刻 ${ex.ingressMoment}`];
				L.push(`上升 ${yl.signCn} → 年主星(命主) ${yl.rulerCn}`);
				if(gov){
					L.push(`本盘上升 ${MODALITY_CN[yl.modality] || ''}星座 · ${cfg.label} → 主管约 ${gov.spanMonths} 个月${gov.needSeasonal && gov.needSeasonal.length ? `；季度递归 → 须再起 ${gov.needSeasonal.map((sk) => SEASON_INGRESS_CN[sk] || sk).join(' / ')} 入境盘各管一季` : ''}`);
					if(gov.note){ L.push(gov.note); }
				}
				push(L);
			}
		}catch(e){ /* noop */ }
		try{
			const seed = (st.seasonSeedYear === clampYear(ex.ingressYear, currentYear())) ? st.seasonSeed : null;
			if(seed){
				const L = ['[四季入境盘]', `${clampYear(ex.ingressYear, currentYear())} 年四枢轴入境时刻（当地时区）：`];
				INGRESSES.forEach((ing) => { const hit = seed[ing.term]; L.push(`- ${SEASON_INGRESS_CN[ing.signKey] || ing.term}：${(hit && hit.time) ? hit.time.slice(0, 16) : '—'}${ex.ingressTerm === ing.term ? '（当前）' : ''}`); });
				push(L);
			}
		}catch(e){ /* noop */ }
	}
	if((type === 'newmoon' || type === 'fullmoon') && f && ex.selectedMoment){
		try{
			const moon = f.planets ? f.planets.moon : null;
			const L = [type === 'newmoon' ? '[新月图判读]' : '[满月图判读]', `时刻 ${ex.selectedMoment}`];
			if(moon && moon.sign){ L.push(`月亮 ${MUN_SIGN_CN(moon.sign)}${moon.house ? ` · 第${moon.house}宫（${MUNDANE_HOUSE_MEANINGS[moon.house]}）` : ''}`); }
			L.push(type === 'newmoon' ? '新月（日月合相）影响约一个月，主新启与变动；与当季入宫盘对照（入宫为时针、朔望为分针）。' : '满月（日月对分）影响约一个月，主成熟与张力；与当季入宫盘对照（入宫为时针、朔望为分针）。');
			push(L);
		}catch(e){ /* noop */ }
	}
	if((type === 'solecl' || type === 'lunecl') && f){
		try{
			const kind = type === 'lunecl' ? 'lunar' : 'solar';
			const effOrb = (ex.mundaneOrbScheme && ex.mundaneOrbScheme !== 'auto') ? ex.mundaneOrbScheme : cfg.orbScheme;
			const ec = describeEclipse(f, kind);
			const aff = describeEclipseAfflictions(f, kind, effOrb);
			if(ex.selectedMoment && ec){
				const L = [type === 'lunecl' ? '[月食图判读]' : '[日食图判读]', `时刻 ${ex.selectedMoment}${ex.eclipseTypeText ? ` · ${ex.eclipseTypeText}` : ''}`];
				L.push(`${ec.luminaryCn} ${MUN_SIGN_CN(ec.sign)} · ${ec.decanLabel}${ec.house ? ` · 第${ec.house}宫` : ''}`);
				if(ec.elementText){ L.push(`元素：${ec.elementText}`); }
				if(ec.decanText){ L.push(`分度：${ec.decanText}`); }
				if(aff && aff.afflictors.length){ L.push(`受冲行星：${aff.afflictors.map((a) => `${a.cn}${a.aspect}(${a.orb}°)${a.malefic ? '⚠' : ''}`).join('、')}（定受影响主题）`); }
				const lp = f.planets ? f.planets[kind === 'lunar' ? 'moon' : 'sun'] : null;
				if(lp && lp.lon != null){
					const hits = mundaneFixedStarHits([{ key: 'eclipse', cn: '食点', lon: lp.lon }], ex.scanYear || currentYear(), 1.5);
					if(hits.length){ L.push(`食点近恒星：${hits.map((h) => `${h.starCn}${h.royal ? `(王星·${h.royal})` : ''}（${h.nature} ${h.orb}°）`).join('、')}（恒星临食点增其象）`); }
				}
				if(cfg.eclipseTiming !== 'none' && st.eclipseDetail && st.eclipseDetail.durationHours){ L.push(`时长：约 ${st.eclipseDetail.durationHours} 小时 → 影响约 ${st.eclipseDetail.influence} ${st.eclipseDetail.influenceUnit}（食时长定则）`); }
				L.push(cfg.eclipseTiming !== 'none' ? '食以可见地区最应；日食时长→影响年数、月食时长→影响月数。' : '食以可见地区最应；本规则集（周期派）不采食时长定则,以周期相位为主。');
				push(L);
			}
			const r = describeSarosFamily(f);
			if(r){
				const L = ['[食族 Saros]', `${r.node.cn}（月距交点 ${r.node.distToNode.toFixed(1)}°）`, r.numberingNote];
				L.push(`三周期：Saros ${r.constTable.sarosSynodicMonths} 朔望月 = ${r.constTable.sarosDays} 日 = ${r.constTable.sarosLabel}；Metonic ${r.constTable.metonicYears} 年 = ${r.constTable.metonicSynodicMonths} 朔望月（${r.constTable.metonicNote}）；Inex ${r.constTable.inexSynodicMonths} 朔望月 ≈ ${r.constTable.inexDays} 日（${r.constTable.inexNote}）`);
				L.push(`族生命周期：每族 ${r.lifecycle.membersRange.join('–')} 次食 · ${r.lifecycle.stepYears} · ${r.lifecycle.eclipticShiftDeg || r.lifecycle.westShiftDeg}；${r.lifecycle.phases.map((p) => `${p.cn}：${p.note}`).join('；')}`);
				L.push(`判读四步：${r.steps.join('；')}`);
				push(L);
			}
			const quad = describeQuadrantNations(f);
			if(quad){ push(['[天象占参考]', `食落象限 → ${quad.cn}（${quad.span}）${quad.note ? '；' + quad.note : ''}`, '（色占/彗星/大气天象为查表参考,见页面折叠表）']); }
		}catch(e){ /* noop */ }
	}
	if(type === 'region' && f){
		try{
			if(f.houses){
				const L = [`[地区盘·12世俗宫]${ex.regionCn ? '（' + ex.regionCn + '）' : ''}`, '| 宫 | 宫义 | 宫头座 | 宫内星 |', '| --- | --- | --- | --- |'];
				for(let h = 1; h <= 12; h++){
					const hi = f.houses[h];
					const occ = ((hi && hi.planets) || []).filter((k) => MUN_PLANET_CN[k]).map(MUN_PCN);
					L.push(`| ${h} | ${MUNDANE_HOUSE_MEANINGS[h]} | ${hi && hi.sign ? MUN_SIGN_CN(hi.sign) : '—'} | ${occ.length ? occ.join('、') : '—'} |`);
				}
				push(L);
			}
			if(f.meta){
				const m = f.meta;
				const ascKey = m.ascSign || (m.ascLon != null ? munSignOf(m.ascLon) : null);
				const mcKey = m.mcLon != null ? munSignOf(m.mcLon) : null;
				const ascDeg = (m.ascDegree != null) ? m.ascDegree : (m.ascLon != null ? norm360m(m.ascLon) % 30 : null);
				const mcDeg = m.mcLon != null ? norm360m(m.mcLon) % 30 : null;
				const L = ['[时刻校正]', `当前上升 ${ascKey ? MUN_SIGN_CN(ascKey) : '—'} ${ascDeg != null ? ascDeg.toFixed(2) + '°' : ''}；当前天顶 ${mcKey ? MUN_SIGN_CN(mcKey) : '—'} ${mcDeg != null ? mcDeg.toFixed(2) + '°' : ''}（四轴对时刻极敏感,上升约 4 分钟移 1°）`];
				if(Array.isArray(st.rectRows) && st.rectRows.length){
					const hitN = st.rectRows.filter((r) => r.hits.length).length;
					L.push('事件年反推 · 返照收敛检验：');
					st.rectRows.forEach((r) => { L.push(`- ${r.year}：返照上升 ${r.srAsc != null ? `${(r.srAsc % 30).toFixed(1)}°` : '—'}${r.hits.length ? ` 命中${r.hits.join('/')}` : ' 未中轴'}`); });
					L.push(`收敛度 ${hitN}/${st.rectRows.length}（该年返照上升合本盘四轴 ±3°）`);
				}
				if(st.relocData && st.relocCity){
					const rm = st.relocData;
					const rA = rm.ascSign || (rm.ascLon != null ? munSignOf(rm.ascLon) : null);
					const rM = rm.mcLon != null ? munSignOf(rm.mcLon) : null;
					const rAd = (rm.ascDegree != null) ? rm.ascDegree : (rm.ascLon != null ? norm360m(rm.ascLon) % 30 : null);
					const rMd = rm.mcLon != null ? norm360m(rm.mcLon) % 30 : null;
					L.push(`重定位四轴（${st.relocCity}·同时刻）：上升 ${rA ? MUN_SIGN_CN(rA) : '—'} ${rAd != null ? rAd.toFixed(2) + '°' : ''}；天顶 ${rM ? MUN_SIGN_CN(rM) : '—'} ${rMd != null ? rMd.toFixed(2) + '°' : ''}（保黄经星位不变,仅四轴/宫随地点重算）`);
				}
				push(L);
			}
		}catch(e){ /* noop */ }
	}
	if((type === 'ingress' || type === 'newmoon' || type === 'fullmoon') && f){
		try{
			const w = describeMundaneWeather(f);
			const scope = (type === 'newmoon' || type === 'fullmoon') ? '本旬' : '本季';
			const L = ['[天气占星]'];
			if(w && w.factors.length){
				L.push(`临角或合月行星定${scope}天气倾向：`);
				w.factors.forEach((fa) => { L.push(`- ${fa.cn}${[fa.angular ? '临角' : '', fa.nearMoon ? '合月' : ''].filter(Boolean).length ? '（' + [fa.angular ? '临角' : '', fa.nearMoon ? '合月' : ''].filter(Boolean).join('·') + '）' : ''} → ${fa.weather}${fa.malefic ? '（凶星）' : ''}`); });
			}else{ L.push(`本盘无临角/合月行星主导,${scope}天气倾向不显著(合于时令)。`); }
			push(L);
		}catch(e){ /* noop */ }
	}
	if(isNatalLike && f){
		try{
			const sp = describeSpecialAxes(f);
			if(sp){
				const L = ['[四轴特殊点]'];
				[['赤道上升点', sp.eastPoint], ['天顶点 Vertex', sp.vertex], ['反天顶', sp.antivertex]].forEach(([cn, lon]) => { if(lon != null){ L.push(`${cn}：${MUN_SIGN_CN(munSignOf(lon))} ${munDegInSign(lon)}`); } });
				if(sp.note){ L.push(sp.note); }
				push(L);
			}
		}catch(e){ /* noop */ }
	}

	// ── 判读页 ──
	if(isNatalLike && f){
		try{
			const ind = mundaneConjunctionIndicator(f);
			if(ind){ push(['[会合指示星]', `木土会合于 ${ind.signCn}（${ELEMENT_CN[ind.element] || ind.element} · 角距 ${ind.sep}°）；指示星 ${ind.strongerCn}（${ind.tone}）`, ind.toneText, `气候 / 领域：${ind.climate}`]); }
		}catch(e){ /* noop */ }
		try{
			const dist = mundaneDistribution(f, cfg.showOuterPlanets);
			const L = ['[盘型格局]'];
			if(dist){
				if(dist.jonesInfo){ L.push(`分布型 ${dist.jonesInfo.cn}：${dist.jonesInfo.text}`); }
				L.push(`元素偏盛 ${dist.domElementCn}象（火${dist.elements.fire}·土${dist.elements.earth}·风${dist.elements.air}·水${dist.elements.water}）${dist.domElementText ? '：' + dist.domElementText : ''}`);
				L.push(`模式偏盛 ${dist.domModeCn}（基本${dist.modes.cardinal}·固定${dist.modes.fixed}·变动${dist.modes.mutable}）${dist.domModeText ? '：' + dist.domModeText : ''}`);
				if(dist.hemispheres){ L.push(`半球 上${dist.hemispheres.above}/下${dist.hemispheres.below}（外显↔内政）· 东${dist.hemispheres.east}/西${dist.hemispheres.west}（自主↔关系）`); }
				L.push(`分布基准：${dist.count} 体（${dist.classical ? '七曜·古典/中世纪规则集' : '含三王星·现代/Barbault 规则集'}）`);
			}
			const allPats = (st.patKey === chartRequestKey(chart) && st.patData) ? st.patData : null;
			if(allPats){
				const OUTER = ['uranus', 'neptune', 'pluto'];
				const pats = cfg.showOuterPlanets ? allPats : allPats.filter((pp) => !(pp.points || []).some((id) => OUTER.indexOf(String(id).toLowerCase()) >= 0));
				if(pats.length){
					L.push('相位格局：');
					pats.forEach((pp) => { const m = mundanePatternMeaning(pp.type); if(m){ L.push(`- ${m.cn}${pp.apex ? `（顶点 ${MUN_PCN(pp.apex)}）` : ''}${pp.sign ? `（${MUN_SIGN_CN(String(pp.sign).toLowerCase())}）` : ''}：${m.text}`); } });
				}else{ L.push('相位格局：本盘无显著相位格局。'); }
			}
			push(L);
		}catch(e){ /* noop */ }
	}

	// ── 恒星页 ──
	if(isNatalLike && f){
		try{
			const year = ex.ingressYear || currentYear();
			const hits = mundaneFixedStarHits(buildMundaneStarPoints(f), year, 1.5);
			if(hits.length){
				const L = [`[世运恒星命中]`, `（${year} 年岁差校正 · orb 1.5°；恒星合四轴或日月时极具分量,王星尤重）`];
				hits.forEach((h) => { L.push(`- ${h.pointCn} 合 ${h.starCn}${h.royal ? `（王星·${h.royal}）` : ''} ${h.nature} · ${h.orb}°：${h.meaning}`); });
				push(L);
			}
		}catch(e){ /* noop */ }
		try{
			const dp = chart.declParallel;
			if(dp){
				const groups = Array.isArray(dp.parallel) ? dp.parallel : [];
				const contra = dp.contraParallel && typeof dp.contraParallel === 'object' ? dp.contraParallel : {};
				const ck = Object.keys(contra).filter((k) => Array.isArray(contra[k]) && contra[k].length);
				if(groups.length || ck.length){
					const L = ['[赤纬平行]', '（同赤纬 ≤1° 成平行=如合相之力；异号反平行=如对冲）'];
					groups.forEach((g) => { L.push(`- 平行：${(Array.isArray(g) ? g : []).map(MUN_PCN).join(' × ')}`); });
					ck.slice(0, 10).forEach((k) => { L.push(`- 反平行：${MUN_PCN(k)} ↔ ${contra[k].map(MUN_PCN).join('、')}`); });
					push(L);
				}
			}
		}catch(e){ /* noop */ }
	}

	// ── 恒星派入境 / 吠陀世运 / 世运问判 / 行星周期 ──
	if(type === 'solunar'){
		try{
			const stx = describeSolunar(ex.solunarType || 'capsolar', ex.solunarWeights || 'scheme_a');
			const dormant = f ? isDormantChart(f, ex.solunarOrb || 3) : null;
			if(stx){ push(['[恒星派入境·概览]', `${stx.cn}：有效期 ${stx.span}；相对强度 ${stx.weight}（口径 ${stx.weightsCn}）`, dormant != null ? (dormant ? `休眠盘：无行星入角（容许 ${ex.solunarOrb || 3}°）——本盘无信息,实务可略过,看下一级时间盘。` : '活跃盘：有行星入角,见 [角化] 段。') : '', '时间降阶：年=Capsolar → 季=最近非休眠季太阳入境 → 月=Caplunar → 周=最近非休眠月入境。'].filter(Boolean)); }
		}catch(e){ /* noop */ }
	}
	if(type === 'vedicmundane' && f){
		try{
			const m = f.planets ? f.planets.moon : null;
			const L = ['[吠陀世运·年度盘]'];
			if(st.vedicMoment){ L.push(`当前入境时刻：${st.vedicMoment}`); }
			if(m && m.lon != null){ const i = segmentIndex(norm360m(m.lon), 13 + 20 / 60, 27); L.push(`盘中月宿：${NAKSHATRA_27[i]}（第 ${i + 1} 宿）${NAK_KEYPOINTS[i] ? ' ' + NAK_KEYPOINTS[i] : ''}`); }
			const age = (ex.vedicFoundingYear != null) ? Math.max(0, (ex.vedicYear || currentYear()) - ex.vedicFoundingYear) : null;
			const muntha = (age != null && ex.vedicNatalAsc) ? munthaSign(ex.vedicNatalAsc, age) : null;
			if(muntha){ L.push(`Muntha 敏感点：${MUN_SIGN_CN(muntha)}（建国上升每年顺进一座,盘龄 ${age}）`); }
			push(L);
			if(m && m.lon != null){
				const startStr = st.vedicMoment ? datePartOf(st.vedicMoment) : `${ex.vedicYear || currentYear()}-04-14`;
				const r = vimshottariFromMoon(m.lon, startStr, ex.vedicDashaYearLen === 360 ? 360 : 365.2425);
				if(r){
					const D = ['[世运大运]', `（Vimshottari · 年长口径 ${ex.vedicDashaYearLen === 360 ? '360（传统）' : '365.2425（现代）'}）起运主 ${PLANET_CN_V[r.lordKey]}（月在第 ${r.nakIdx + 1} 宿,余额 ${(r.balanceRatio * 100).toFixed(1)}%）`];
					r.periods.forEach((pd) => { D.push(`- ${pd.cn} 大运 ${pd.fromYear}–${pd.toYear}：${pd.meaning}`); });
					push(D);
				}
				const K = ['[KP 副主链]', '| 行星 | 所在宿 | 宿主(场域) | 副主(成败) |', '| --- | --- | --- | --- |'];
				['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].forEach((k) => { const pl = f.planets[k]; if(pl && pl.lon != null){ const kp = kpSubLordAt(pl.lon); K.push(`| ${PLANET_CN_V[k]} | ${NAKSHATRA_27[kp.nakIdx]} | ${PLANET_CN_V[kp.starLord] || kp.starLord} | ${PLANET_CN_V[kp.subLord] || kp.subLord} |`); } });
				if(K.length > 3){ push(K); }
			}
			if(st.garbhaDate){ const dv = garbhaDeliveryDate(st.garbhaDate); if(dv){ push(['[天气与农业]', `云之孕：受孕日 ${st.garbhaDate} → 预测降雨日 ${dv}（孕期固定 ${GARBHA_CONST.gestationDays} 日）`]); } }
		}catch(e){ /* noop */ }
	}
	if(type === 'mundanehorary' && f){
		try{
			const kind = ex.mhKind || 'war';
			const fmtScore = (sc, role) => sc ? `- ${role}：${sc.cn}${sc.house ? `（第${sc.house}宫）` : ''} 得力 ${sc.total != null ? sc.total : sc.score}${sc.items && sc.items.length ? `（${sc.items.map((it) => `${it.cn} ${it.v > 0 ? '+' + it.v : it.v}`).join('，')}）` : ''}` : '';
			const L = ['[世运问判·得力明细]'];
			if(kind === 'war'){ const w = describeWarQuestion(f); if(w){ L.push(fmtScore(w.us, w.us.role), fmtScore(w.them, w.them.role)); if(w.moon){ L.push(fmtScore(w.moon, w.moon.role)); } if(w.note){ L.push(w.note); } } }
			else if(kind === 'weather'){ const wq = describeWeatherQuestion(f); if(wq){ (wq.angular || []).forEach((a) => L.push(`- 临角 ${a.cn}（第${a.house}宫）：${a.text}`)); if(!wq.angular || !wq.angular.length){ L.push('无行星临角。'); } if(wq.note){ L.push(wq.note); } } }
			else { const pq = describePriceQuestion(f); if(pq){ pq.wealth.forEach((x) => L.push(fmtScore(x.strength, `第 ${x.house} 宫主（财货）`))); if(pq.note){ L.push(pq.note); } } }
			push(L.filter(Boolean));
		}catch(e){ /* noop */ }
	}
	if(type === 'cycles'){
		try{
			const results = Array.isArray(st.gcResults) ? st.gcResults : [];
			if(results.length){
				const pairCn = (CYCLE_PAIRS.find((pp) => pp.key === st.gcPair) || {}).cn || '木土';
				const aspCn = st.gcAspect === 180 ? '对分' : '合相';
				const L = [`[木土纪元]`, `（${pairCn}${aspCn} · ${st.gcCoord === 'helio' ? '日心' : '地心'} · ${yearLabel(clampYear(st.gcStart, 1300))}–${yearLabel(clampYear(st.gcEnd, 2200))} · 共 ${results.length} 次）`];
				if(st.gcMode === 'flat'){
					results.slice(0, 80).forEach((c) => { L.push(`- ${yearLabel(c.year)}-${String(c.month).padStart(2, '0')} ${MUN_SIGN_CN(SIGN_KEYS[c.sign])}${c.lon != null ? ` ${(c.lon % 30).toFixed(1)}°` : ''}`); });
				}else{
					computeAges(results).forEach((age) => {
						L.push(`◆ ${age.leadingCn}时代（${ELEMENT_CN[age.element]} · ${dignityText(age.dignities)}）：${age.conjs.map((g) => `${yearLabel(g.year)}-${String(g.month).padStart(2, '0')} ${MUN_SIGN_CN(SIGN_KEYS[g.sign])}${((SIGNS[SIGN_KEYS[g.sign]] || {}).element !== age.element) ? '(过渡)' : ''}`).join('、')}`);
					});
					const eras = computeConjunctionEras(results);
					if(eras && eras.segments.length){
						L.push(`历史会合分期：${eras.segments.map((sg) => `${sg.elementCn}象 ${yearLabel(sg.from)}–${yearLabel(sg.to)}`).join('；')}`);
						if(eras.marks && eras.marks.length){ L.push(`变迁点：${eras.marks.map((mk) => `${yearLabel(mk.year)} ${mk.cn || mk.kind || ''}`).join('；')}`); }
					}
				}
				if(Array.isArray(st.msCancerRows) && st.msCancerRows.length){ L.push(`土火合巨蟹命中年：${st.msCancerRows.map((r) => yearLabel(r.year)).join('、')}`); }
				push(L);
			}
			const gy = computeCurrentAge(currentYear(), st.gyModel || 'fagan');
			if(gy){ push(['[大年时代]', `${currentYear()} 年春分点 · 恒星${gy.signCn} ${gy.degInSign.toFixed(2)}° → 当前为${gy.currentAgeCn}（岁差口径 ${st.gyModel === 'lahiri' ? 'Lahiri' : 'Fagan/Bradley'}）`, `岁差周期(大年)≈ ${GREAT_YEAR_CONST.precessionYears} 年；柏拉图月(一个时代)≈ ${GREAT_YEAR_CONST.platonicMonthYears.join('–')} 年；春分点以约 ${GREAT_YEAR_CONST.rateArcsecPerYear}″/年西退。`]); }
			if(st.cycleTableText && st.cycleTableKey === chartRequestKey(chart)){ push(st.cycleTableText.split('\n')); }
			if(cfg.showBarbault && st.bbData && Array.isArray(st.bbData.points) && st.bbData.points.length){
				const pts = st.bbData.points;
				let gmin = pts[0]; let gmax = pts[0];
				pts.forEach((pp) => { if(pp.index < gmin.index){ gmin = pp; } if(pp.index > gmax.index){ gmax = pp; } });
				// 组合 / 谐波 / 年段一律取算图时记下的(bbData),不取下拉此刻的值 —— 改了下拉没点「绘制」时两者不同
				const bb = st.bbData;
				const set = BARBAULT_SETS.find((ss) => ss.key === (bb.setKey || st.bbSet)) || BARBAULT_SETS[0];
				push(['[Barbault 聚散指数]', `（慢星组合 ${set.cn}${bb.harm > 1 ? ` · ${bb.harm} 次谐波` : ''} · ${yearLabel(bb.startYear !== undefined ? bb.startYear : clampYear(st.bbStart, 1900))}–${yearLabel(bb.endYear !== undefined ? bb.endYear : clampYear(st.bbEnd, 2050))} · ${pts.length} 点）`, `最深谷（聚集）${gmin.year}-${String(gmin.month).padStart(2, '0')}（${Math.round(gmin.index)}°）；最高峰（四散）${gmax.year}-${String(gmax.month).padStart(2, '0')}（${Math.round(gmax.index)}°）`]);
			}
		}catch(e){ /* noop */ }
	}
	return out;
}

export const CARD = {
	border: '1px solid var(--horosa-border, rgba(128,128,128,0.16))',
	borderRadius: 12,
	padding: '14px 16px',
	marginBottom: 14,
	background: 'var(--horosa-surface-sunken, rgba(128,128,128,0.025))',
};
export const CARD_TITLE = { fontSize: 13.5, fontWeight: 700, marginBottom: 12, letterSpacing: '0.03em', display: 'flex', alignItems: 'center', gap: 8 };

// 排盘设置跨会话保留(用户实报:排盘设置改了之后每次重开软件都要重设)。只收口径:
// 世运规则集 / 判读容许度 / 入境主管制 / 恒星入境的强度口径与角化容许 / 世运大运年长 / 黄道 / 宫制;Barbault 页的慢星组合与谐波(state 键,另由页面读写)。
// 不收「起哪种盘、哪一年、哪个节气、哪个国家」—— 盘型、年份、节气、地区、问题类型都是每一张盘的输入。
export const MUNDANE_SETTING_EXTRA_KEYS = ['mundaneRuleset', 'mundaneOrbScheme', 'mundaneIngressRule', 'solunarWeights', 'solunarOrb', 'vedicDashaYearLen'];
export const MUNDANE_PAGE_SETTINGS = definePageSettings('horosa.mundane.settings.v1', {
	mundaneRuleset: { label: '世运规则集', def: 'modern', oneOf: MUNDANE_RULESETS.map((r)=>r.key) },
	mundaneOrbScheme: { label: '判读容许度', def: 'auto', oneOf: ['auto', 'moiety', 'by_aspect'] },
	mundaneIngressRule: { label: '入境主管制', def: 'auto', oneOf: ['auto', 'quarterly', 'aries_annual', 'capricorn_year'] },
	solunarWeights: { label: '日月恒星入境·强度口径', def: 'scheme_a', oneOf: Object.keys(SOLUNAR_WEIGHTS) },
	solunarOrb: { label: '日月恒星入境·角化容许', def: 3, oneOf: ANGULARITY_ORBS.map((o)=>o.orb) },
	vedicDashaYearLen: { label: '世运大运·年长口径', def: 365.2425, oneOf: [365.2425, 360] },
	// Barbault 页两项口径(state 键,不在盘壳 extra 里):在页上亲手改即落盘,构造时读回
	bbSet: { label: 'Barbault 指数·慢星组合', def: 'slow5', oneOf: BARBAULT_SETS.map((s)=>s.key) },
	bbHarm: { label: 'Barbault 指数·谐波', def: 1, oneOf: BARBAULT_HARMONICS.map((h)=>h.v) },
	...shellFieldSchema(0),
});
// 用户亲手改 extra 里的设置项:落盘(只收 schema 里的键,输入类键自动忽略)+ 原样 setExtra
export function userSetExtra(setExtra, patch){
	MUNDANE_PAGE_SETTINGS.save(patch);
	setExtra(patch);
}
