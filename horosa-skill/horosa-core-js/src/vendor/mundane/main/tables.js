// 世俗盘页常量与小件:盘种 / 入境、行星与星座中文、元素配色、周期配对与巴博三重、时代分期、尊贵、宫位与地理分区表格
// 从 MundaneMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
// headless stub：AstroExtraCommon 是 React 页面公共件，不 vendor。astroSymbol 只被 UI 字形（pGlyph/sGlyph）用，快照不调；
// 恒等映射保持「拿到的就是 id」。
const astroSymbol = (id) => id;
import { SIGNS } from '../../divination/data/signs.js';
import { buildFacts } from '../../divination/engine/chartFacts.js';
import { PLANET_CN as MUN_PLANET_CN } from '../describe.js';

export const MUNDANE_TYPES = [
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

export const INGRESSES = [
	{ term: '春分', label: '春分 · 白羊入宫（年盘）', signKey: 'aries' },
	{ term: '夏至', label: '夏至 · 巨蟹入宫', signKey: 'cancer' },
	{ term: '秋分', label: '秋分 · 天秤入宫', signKey: 'libra' },
	{ term: '冬至', label: '冬至 · 摩羯入宫', signKey: 'capricorn' },
];

export const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
export const norm360m = (x) => (((x % 360) + 360) % 360);
const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
export const PLANET_CN = { sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星', jupiter: '木星', saturn: '土星' };
const PLANET_ZH = { sun: '日', moon: '月', mercury: '水', venus: '金', mars: '火', jupiter: '木', saturn: '土' };
export const ELEMENT_COLOR = { fire: '#c0392b', earth: '#8a6d3b', air: '#2c7fb8', water: '#1a7f6b' };
export const ELEMENT_BG = { fire: 'rgba(192,57,43,0.08)', earth: 'rgba(138,109,59,0.08)', air: 'rgba(44,127,184,0.08)', water: 'rgba(26,127,107,0.08)' };
export const ELEMENT_CN = { fire: '火象', earth: '土象', air: '风象', water: '水象' };
const ELEMENT_SHORT = { fire: '火', earth: '土', air: '风', water: '水' };

export const MODALITY_CN = { cardinal: '基本', fixed: '固定', mutable: '变动' };
export const SEASON_INGRESS_CN = { aries: '春分·白羊', cancer: '夏至·巨蟹', libra: '秋分·天秤', capricorn: '冬至·摩羯' };
// 两个页面级覆盖的中文名(左栏下拉与 AI 快照同源,改文案只改这一处)。
export const MUNDANE_ORB_SCHEME_CN = { moiety: '受冲容许 ≤2°(古典收紧)', by_aspect: '按相位(现代 ≤3°)' };
export const MUNDANE_INGRESS_RULE_CN = { quarterly: '季度制(按四轴模式递归)', aries_annual: '全年制(白羊盘主全年)', capricorn_year: '摩羯优先(冬至为年首)' };

// 复用 App 自带的占星字体 glyph（AstroFont），不用 unicode 符号。
export const PLANET_ASTRO_ID = { sun: 'Sun', moon: 'Moon', mercury: 'Mercury', venus: 'Venus', mars: 'Mars', jupiter: 'Jupiter', saturn: 'Saturn', uranus: 'Uranus', neptune: 'Neptune', pluto: 'Pluto' };
export function pGlyph(k){ return astroSymbol(PLANET_ASTRO_ID[k] || k); }
export function sGlyph(signKey){ const s = signKey ? SIGNS[signKey] : null; return (s && s.en) ? astroSymbol(s.en) : null; }

// 行星周期：可选慢星对 + 合/冲。木土合走既有「时代纪元」富视图；其余走 /astroextra/planetcycles 平铺时间轴。
export const CYCLE_PAIRS = [
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
export const CYCLE_ASPECTS = [{ v: 0, cn: '合相 0°' }, { v: 180, cn: '对分 180°' }];
// Barbault 行星周期指数(§9.3)可选慢星组合:对数 = C(n,2),满刻度 = 对数×180°。
export const BARBAULT_SETS = [
	{ key: 'slow5', cn: '五慢星 ♃♄♅♆♇（默认）', planets: ['Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'] },
	{ key: 'outer3', cn: '仅外三星 ♅♆♇（最平滑）', planets: ['Uranus', 'Neptune', 'Pluto'] },
	{ key: 'slow4', cn: '土外四星 ♄♅♆♇', planets: ['Saturn', 'Uranus', 'Neptune', 'Pluto'] },
];
// 谐波:每对角距先乘 h 再折半圆;1 = 原指数,2 看合冲,3 看三分,4 看刑
export const BARBAULT_HARMONICS = [{ v: 1, cn: '原指数' }, { v: 2, cn: '2 次谐波' }, { v: 3, cn: '3 次谐波' }, { v: 4, cn: '4 次谐波' }];

// 一组（约60年/3次）合相的大三合相态：纯X(全本象) / 摄Y(2本1邻) / 摄大Y(1本2邻)。
export function triadPhase(triad, ageEl){
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

export function currentYear(){
	return new Date().getFullYear();
}

// 盘面事实(buildFacts 遇缺字段的盘会抛):各卡 / 各段一律按「无事实」处理。
export function safeFacts(chart){
	try{ return buildFacts(chart); }catch(e){ return null; }
}

export function clampYear(v, dflt){
	const n = Number(v);
	if(!Number.isFinite(n)){ return dflt; }
	return Math.max(-3000, Math.min(3000, Math.round(n)));
}

export function yearLabel(y){
	return y <= 0 ? `前${1 - y}` : `${y}`;
}

// year → 'YYYY-MM-DD'（正年补零；负年加 -）。
export function ymd(year, m, d){
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

export function dignityText(d){
	const z = (p) => PLANET_ZH[p] || p;
	const parts = [];
	if(d.ruler && d.exalt && d.ruler === d.exalt){ parts.push(z(d.ruler) + '主强'); }
	else { if(d.ruler){ parts.push(z(d.ruler) + '主'); } if(d.exalt){ parts.push(z(d.exalt) + '强'); } }
	if(d.detr){ parts.push(z(d.detr) + '落'); }
	return parts.join('·');
}

export function computeAges(conjs){
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
export function ascRuler(chart){
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

// ── 右栏 33 卡 → AI 快照段(此前只覆盖 8 卡)。每段与对应 render*Card 同一 describe/纯函数与同一入参;
// 页面按需拉取物(相位格局/四季/返照/次限/校正/重定位/木土会合/Barbault/九主/食时长)由 state 传入,算过才成段;
// 静态教义表(色占/彗星/过境通则/龟形分野等)按用户裁决只留可算部分+简注,不整表灌入。全部异常降级为不产段。
export const MUN_SIGN_CN = (k) => ((SIGNS[k] || {}).cn || k || '');
export const MUN_PCN = (k) => (MUN_PLANET_CN[String(k || '').toLowerCase()] || k);
export function munDegInSign(lon){ return `${(norm360m(lon) % 30).toFixed(2)}°`; }
export function munSignOf(lon){ return SIGN_KEYS[Math.floor(norm360m(lon) / 30)]; }
