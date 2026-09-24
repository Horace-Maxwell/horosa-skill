// components/mundane/MundaneMain.js
// 世俗盘 Mundane：类型选择器统辖多种世俗盘——
//   入宫盘（四正入宫，精确入宫时刻）/ 新月图 / 满月图 / 日食图 / 月食图 / 地区盘 / 行星周期（木土大合相纪元）。
// 入宫：/jieqi 精确节气种子 + /chart。新月满月/日月食：momentPipeline（/astroextra/ephemeris）扫描事件 → 选中按精确时刻排盘。
// 地区盘：预置/自定义历史建置时刻 + 12 世俗宫义。行星周期：/astroextra/greatconj 精算木土大合。
// 解读层：divination/mundane/describe（行星落世俗宫判词、食的元素/分度判词）。



// headless stub：模块顶层 `const Option = XQSelect.Option; const TabPane = XQTabs.TabPane;` 只服务已截断的 UI；空对象令其求值为 undefined 而不抛。
const XQSelect = {}; const XQTabs = {};





import { SIGNS } from '../divination/data/signs.js';
import { ingressGovernance } from './momentPipeline.js';
import { buildFacts } from '../divination/engine/chartFacts.js';


import { describeMundaneChart, describeEclipse, describeEclipseAfflictions, describeIngressSkeleton, describeMundaneVictor, describeMundaneWeather, describeMundaneSyzygy, buildMundaneStarPoints, mundaneFixedStarHits, mundaneConjunctionIndicator, describeSpecialAxes, MUNDANE_HOUSE_MEANINGS, PLANET_CN as MUN_PLANET_CN } from './describe.js';

import { CONJUNCTION_LAYERS, PARALLEL_TRIADS, computeConjunctionEras, detectMarsSaturnCancer } from './conjunctionEras.js';
import { describeSarosFamily } from './saros.js';
import { SOLUNAR_TYPES, SOLUNAR_WEIGHTS, ANGULARITY_ORBS, OMEN_COMBOS, computeAngularity, isDormantChart, rulerDeathSignature, describeSolunar } from './solunar.js';
import { PLANET_CN_V, NAVANAYAKA_OFFICES, vimshottariFromMoon, kpSubLordAt, KP_NOTES, NAKSHATRA_27, NAK_KEYPOINTS, GARBHA_CONST, GARBHA_OMENS, garbhaDeliveryDate, buildSaptaNadi, SAPTA_NADI_COLS, SAPTA_NADI_READING, ARGHA_RULES, TRANSIT_RULES, ECLIPSE_VEDIC_RULES, KURMA_MODERN, KURMA_DISCLAIMER, munthaSign } from './vedicMundane.js';
import { MUNDANE_HORARY_KINDS, describeWarQuestion, describeWeatherQuestion, describePriceQuestion } from './mundaneHorary.js';
import { ECLIPSE_COLOR_OMEN, ECLIPSE_COLOR_NOTE, COMET_OMEN, WEATHER_OMENS, OMEN_STRUCTURE_NOTE, describeQuadrantNations } from './omenology.js';
import { GREAT_YEAR_CONST, AGE_BOUNDARY_METHODS, AGE_CLAIMS, AGE_CLAIMS_RANGE, AGE_SEQUENCE_NOTE, TIDAL_NOTE, computeCurrentAge } from './greatYear.js';
import { MUNDANE_RULESETS, rulesetConfig, hiddenBodiesFor } from './ruleset.js';


import { mundaneDistribution, mundanePatternMeaning } from './patterns.js';

// headless stub：AstroExtraCommon 是 React/AstroMeaning 依赖的前端文件，不 vendor。
// astroSymbol 只被 pGlyph/sGlyph（UI 字形，快照不调）引用；chartRequestKey 只用于 [盘型格局] 的
// `st.patKey === chartRequestKey(chart)` 缓存一致性判定——headless 的相位格局就是对**同一张盘**现取的，
// 故恒等键即正解：调用方（tools/mundaneCards.js）传 patKey 时用同一常量 HEADLESS_PAT_KEY。
const astroSymbol = (id) => id; const chartRequestKey = () => 'headless';





const Option = XQSelect.Option;
const TabPane = XQTabs.TabPane;

const MUNDANE_TYPES = [
	{ key: 'ingress', label: '入宫盘' },
	{ key: 'newmoon', label: '新月图' },
	{ key: 'fullmoon', label: '满月图' },
	{ key: 'solecl', label: '日食图' },
	{ key: 'lunecl', label: '月食图' },
	{ key: 'region', label: '地区盘' },
	{ key: 'cycles', label: '行星周期' },
	{ key: 'solunar', label: '恒星派入境' },
	{ key: 'vedicmundane', label: '吠陀世运' },
	{ key: 'mundanehorary', label: '世运卜卦' },
];

const INGRESSES = [
	{ term: '春分', label: '春分 · 白羊入宫（年盘）', signKey: 'aries' },
	{ term: '夏至', label: '夏至 · 巨蟹入宫', signKey: 'cancer' },
	{ term: '秋分', label: '秋分 · 天秤入宫', signKey: 'libra' },
	{ term: '冬至', label: '冬至 · 摩羯入宫', signKey: 'capricorn' },
];

const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
const norm360m = (x) => (((x % 360) + 360) % 360);
const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
const PLANET_CN = { sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星', jupiter: '木星', saturn: '土星' };
const PLANET_ZH = { sun: '日', moon: '月', mercury: '水', venus: '金', mars: '火', jupiter: '木', saturn: '土' };
const ELEMENT_COLOR = { fire: '#c0392b', earth: '#8a6d3b', air: '#2c7fb8', water: '#1a7f6b' };
const ELEMENT_BG = { fire: 'rgba(192,57,43,0.08)', earth: 'rgba(138,109,59,0.08)', air: 'rgba(44,127,184,0.08)', water: 'rgba(26,127,107,0.08)' };
const ELEMENT_CN = { fire: '火象', earth: '土象', air: '风象', water: '水象' };
const ELEMENT_SHORT = { fire: '火', earth: '土', air: '风', water: '水' };

const MODALITY_CN = { cardinal: '基本', fixed: '固定', mutable: '变动' };
const SEASON_INGRESS_CN = { aries: '春分·白羊', cancer: '夏至·巨蟹', libra: '秋分·天秤', capricorn: '冬至·摩羯' };
// [Q-150/T-60] 两个页面级覆盖的中文名(左栏下拉与 AI 快照同源,改文案只改这一处)。
export const MUNDANE_ORB_SCHEME_CN = { moiety: '受冲容许 ≤2°(古典收紧)', by_aspect: '按相位(现代 ≤3°)' };
export const MUNDANE_INGRESS_RULE_CN = { quarterly: '季度制(按四轴模式递归)', aries_annual: '全年制(白羊盘主全年)', capricorn_year: '摩羯优先(冬至为年首)' };

// 复用 App 自带的占星字体 glyph（AstroFont），不用 unicode 符号。
const PLANET_ASTRO_ID = { sun: 'Sun', moon: 'Moon', mercury: 'Mercury', venus: 'Venus', mars: 'Mars', jupiter: 'Jupiter', saturn: 'Saturn', uranus: 'Uranus', neptune: 'Neptune', pluto: 'Pluto' };
function pGlyph(k){ return astroSymbol(PLANET_ASTRO_ID[k] || k); }
function sGlyph(signKey){ const s = signKey ? SIGNS[signKey] : null; return (s && s.en) ? astroSymbol(s.en) : null; }

// 行星周期：可选慢星对 + 合/冲。木土合走既有「时代纪元」富视图；其余走 /astroextra/planetcycles 平铺时间轴。
const CYCLE_PAIRS = [
	{ key: 'jupiter-saturn', cn: '木 ✕ 土（时代纪元）' },
	{ key: 'saturn-uranus', cn: '土 ✕ 天王' },
	{ key: 'saturn-neptune', cn: '土 ✕ 海王' },
	{ key: 'saturn-pluto', cn: '土 ✕ 冥王' },
	{ key: 'uranus-neptune', cn: '天王 ✕ 海王' },
	{ key: 'uranus-pluto', cn: '天王 ✕ 冥王' },
	{ key: 'neptune-pluto', cn: '海王 ✕ 冥王' },
	{ key: 'jupiter-uranus', cn: '木 ✕ 天王' },
	{ key: 'jupiter-neptune', cn: '木 ✕ 海王' },
	{ key: 'jupiter-pluto', cn: '木 ✕ 冥王' },
	{ key: 'mars-saturn', cn: '火 ✕ 土' },
];
const CYCLE_ASPECTS = [{ v: 0, cn: '合相 0°' }, { v: 180, cn: '对分 180°' }];
// Barbault 行星周期指数(§9.3)可选慢星组合:对数 = C(n,2),满刻度 = 对数×180°。
const BARBAULT_SETS = [
	{ key: 'slow5', cn: '五慢星 ♃♄♅♆♇（默认）', planets: ['Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'] },
	{ key: 'outer3', cn: '仅外三星 ♅♆♇（最平滑）', planets: ['Uranus', 'Neptune', 'Pluto'] },
	{ key: 'slow4', cn: '土外四星 ♄♅♆♇', planets: ['Saturn', 'Uranus', 'Neptune', 'Pluto'] },
];

// 一组（约60年/3次）合相的大三合相态：纯X(全本象) / 摄Y(2本1邻) / 摄大Y(1本2邻)。
function triadPhase(triad, ageEl){
	const els = triad.map((c) => (SIGNS[SIGN_KEYS[c.sign]] || {}).element);
	const match = els.filter((e) => e === ageEl).length;
	const other = els.find((e) => e && e !== ageEl) || ageEl;
	if(match >= triad.length){ return { label: '纯' + ELEMENT_SHORT[ageEl], el: ageEl }; }
	if(match >= 2){ return { label: '摄' + ELEMENT_SHORT[other], el: other }; }
	return { label: '摄大' + ELEMENT_SHORT[other], el: other };
}

const AGE_EPOCHS = [
	{ y: -1199, s: 6 }, { y: -959, s: 7 },
	{ y: -720, s: 8 }, { y: -541, s: 9 }, { y: -302, s: 10 }, { y: -124, s: 11 },
	{ y: 114, s: 0 }, { y: 292, s: 1 }, { y: 411, s: 2 }, { y: 590, s: 3 },
	{ y: 769, s: 4 }, { y: 1007, s: 5 }, { y: 1186, s: 6 }, { y: 1305, s: 7 },
	{ y: 1603, s: 8 }, { y: 1842, s: 9 }, { y: 2020, s: 10 }, { y: 2259, s: 11 },
	{ y: 2497, s: 0 }, { y: 2676, s: 1 },
];

function currentYear(){
	try{ return new Date().getFullYear(); }catch(e){ return 2026; }
}

function clampYear(v, dflt){
	const n = Number(v);
	if(!Number.isFinite(n)){ return dflt; }
	return Math.max(-3000, Math.min(3000, Math.round(n)));
}

function yearLabel(y){
	return y <= 0 ? `前${1 - y}` : `${y}`;
}

// year → 'YYYY-MM-DD'（正年补零；负年加 -）。
function ymd(year, m, d){
	const y = year < 0 ? `-${String(-year).padStart(4, '0')}` : String(year).padStart(4, '0');
	return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function ageEpochFor(year){
	let ep = AGE_EPOCHS[0];
	for(let i = 0; i < AGE_EPOCHS.length; i++){
		if(AGE_EPOCHS[i].y <= year){ ep = AGE_EPOCHS[i]; } else { break; }
	}
	return ep;
}

function dignities(idx){
	const s = SIGNS[SIGN_KEYS[idx]] || {};
	const ruler = s.domicile;
	const exalt = (s.exaltation && SEVEN.indexOf(s.exaltation.planet) >= 0) ? s.exaltation.planet : null;
	const detr = (SIGNS[SIGN_KEYS[(idx + 6) % 12]] || {}).domicile;
	return { ruler, exalt, detr };
}

function dignityText(d){
	const z = (p) => PLANET_ZH[p] || p;
	const parts = [];
	if(d.ruler && d.exalt && d.ruler === d.exalt){ parts.push(z(d.ruler) + '主强'); }
	else { if(d.ruler){ parts.push(z(d.ruler) + '主'); } if(d.exalt){ parts.push(z(d.exalt) + '强'); } }
	if(d.detr){ parts.push(z(d.detr) + '落'); }
	return parts.join('·');
}

function computeAges(conjs){
	const ages = [];
	let cur = null;
	(conjs || []).forEach((c) => {
		const ep = ageEpochFor(c.year);
		if(!cur || cur.epochY !== ep.y){
			if(cur){ ages.push(cur); }
			const sign = SIGNS[SIGN_KEYS[ep.s]] || {};
			cur = {
				epochY: ep.y, leadingCn: sign.cn, leadingSignKey: SIGN_KEYS[ep.s],
				element: sign.element, dignities: dignities(ep.s), conjs: [],
			};
		}
		cur.conjs.push(c);
	});
	if(cur){ ages.push(cur); }
	return ages;
}

// 入宫盘上升座 → 域主星 = 年主星。
function ascRuler(chart){
	let key = null;
	let lon = null;
	try{
		const facts = buildFacts(chart);
		if(facts && facts.meta){
			if(facts.meta.ascSign){ key = facts.meta.ascSign; }
			else if(facts.meta.ascLon != null){ lon = facts.meta.ascLon; }
		}
		if(key == null && facts && facts.lons && facts.lons.asc != null){ lon = facts.lons.asc; }
	}catch(e){ /* noop */ }
	if(key == null && lon != null){ key = SIGN_KEYS[Math.floor((((lon % 360) + 360) % 360) / 30)]; }
	const sign = key ? SIGNS[key] : null;
	if(!sign){ return null; }
	return { signKey: key, signCn: sign.cn, modality: sign.modality, rulerKey: sign.domicile, rulerCn: PLANET_CN[sign.domicile] || sign.domicile };
}

// AI 快照段:世俗宫义/地理分野 逐行 → GFM 表(v1/v2 归一器直通、docx/PDF 渲染真表)。
// 单元格值表达式与旧逐字同源(planetCn/house/houseMeaning/signTemper/text · a.cn/countries),只改排版;
// 抽为模块级纯函数供 buildAiSnapshot 调用并可单测(数值不变证明)。宫号保「第N宫」原子 token。
export function formatMundaneHouseTable(rows){
	const out = ['| 星 | 宫 | 宫义 | 星座 | 判读 |', '| --- | --- | --- | --- | --- |'];
	(rows || []).forEach((r) => {
		const zodiac = r.signTemper ? `${r.sign || ''}·${r.signTemper.modeElement}` : '—';
		out.push(`| ${r.planetCn} | 第${r.house}宫 | ${r.houseMeaning} | ${zodiac} | ${r.text} |`);
	});
	return out.join('\n');
}
export function formatMundaneChorographyTable(axes){
	const out = ['| 星座 | 分野 |', '| --- | --- |'];
	(axes || []).forEach((a) => { out.push(`| ${a.cn} | ${a.regions.countries.slice(0, 4).join('、')} |`); });
	return out.join('\n');
}

// ── [Q-444/T-407] 右栏 33 卡 → AI 快照段(此前只覆盖 8 卡)。每段与对应 render*Card 同一 describe/纯函数与同一入参;
// 页面按需拉取物(相位格局/四季/返照/次限/校正/重定位/木土会合/Barbault/九主/食时长)由 state 传入,算过才成段;
// 静态教义表(色占/彗星/过境通则/龟形分野等)按用户裁决只留可算部分+简注,不整表灌入。全部异常降级为不产段。
const MUN_SIGN_CN = (k) => ((SIGNS[k] || {}).cn || k || '');
const MUN_PCN = (k) => (MUN_PLANET_CN[String(k || '').toLowerCase()] || k);
function munDegInSign(lon){ return `${(norm360m(lon) % 30).toFixed(2)}°`; }
function munSignOf(lon){ return SIGN_KEYS[Math.floor(norm360m(lon) / 30)]; }

export function buildMundaneCardSections(chart, extra, state, facts){
	const ex = extra || {};
	const st = state || {};
	const type = ex.mundaneType || 'ingress';
	const cfg = rulesetConfig(ex.mundaneRuleset);
	const out = [];
	const push = (lines) => { if(lines && lines.length > 1){ out.push(lines.join('\n')); } };
	if(!chart){ return out; }
	const f = facts || (() => { try{ return buildFacts(chart); }catch(e){ return null; } })();
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
			if(m && m.lon != null){ const i = Math.floor(norm360m(m.lon) / (13 + 20 / 60)); L.push(`盘中月宿：${NAKSHATRA_27[i]}（第 ${i + 1} 宿）${NAK_KEYPOINTS[i] ? ' ' + NAK_KEYPOINTS[i] : ''}`); }
			const age = (ex.vedicFoundingYear != null) ? Math.max(0, (ex.vedicYear || currentYear()) - ex.vedicFoundingYear) : null;
			const muntha = (age != null && ex.vedicNatalAsc) ? munthaSign(ex.vedicNatalAsc, age) : null;
			if(muntha){ L.push(`Muntha 敏感点：${MUN_SIGN_CN(muntha)}（建国上升每年顺进一座,盘龄 ${age}）`); }
			push(L);
			if(m && m.lon != null){
				const startStr = st.vedicMoment ? st.vedicMoment.slice(0, 10) : `${ex.vedicYear || currentYear()}-04-14`;
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
			if(cfg.showBarbault && st.bbData && Array.isArray(st.bbData.points) && st.bbData.points.length){
				const pts = st.bbData.points;
				let gmin = pts[0]; let gmax = pts[0];
				pts.forEach((pp) => { if(pp.index < gmin.index){ gmin = pp; } if(pp.index > gmax.index){ gmax = pp; } });
				const set = BARBAULT_SETS.find((ss) => ss.key === st.bbSet) || BARBAULT_SETS[0];
				push(['[Barbault 聚散指数]', `（慢星组合 ${set.cn} · ${yearLabel(clampYear(st.bbStart, 1900))}–${yearLabel(clampYear(st.bbEnd, 2050))} · ${pts.length} 点）`, `最深谷（聚集）${gmin.year}-${String(gmin.month).padStart(2, '0')}（${Math.round(gmin.index)}°）；最高峰（四散）${gmax.year}-${String(gmax.month).padStart(2, '0')}（${Math.round(gmax.index)}°）`]);
			}
		}catch(e){ /* noop */ }
	}
	return out;
}
