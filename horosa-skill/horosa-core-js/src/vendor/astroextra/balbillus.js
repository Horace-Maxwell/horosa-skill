import moment from 'moment';
import { birthMomentOfChart, civilDateOfMoment } from '../utils/civilMoment.js';
import * as AstroConst from './progConst.js';
import * as AstroText from './progConst.js';
// [YB] 三段补厚共享 helper(起盘信息/当前时点/方法说明;astroAiSnapshot 不回引本文件,无环)。
// namespace import + typeof 守卫:测试环境可能部分 mock astroAiSnapshot(只留 buildAstroSnapshotContent 等),
// 缺函数时回 [] 保底 → 输出与补厚前逐字节一致,不炸挂载。
// headless stub：上游 [YB] 三段补厚用它产 [起盘信息]/[当前时点]/[方法说明]，但 skill 的 Python 层
// 已经产这三段（_predictive_setup_section_text / _predictive_common_sections_text），再让 JS 产一遍会重段。
// 上游每个调用点都写了 typeof …==='function' 守卫：未定义的 helper 回退 []（不产段）。唯一例外是
// buildCurrentMomentLines——它收下 builder 自算的 [当前时点] 定位行（extraLines，如「当前主限」），交给
// tools/progextra.js 回传 Python 追加进 [当前时点]（= 上游 buildCurrentMomentLines(chartObj, extraLines)），自身仍返 []。
const astroAiSnapshot = {
	buildCurrentMomentLines: (chartObj, extraLines) => {
		globalThis.__horosaProgMomentLines = Array.isArray(extraLines) ? extraLines.filter(Boolean).map((l) => `${l}`) : [];
		return [];
	},
};

const birthHeaderLines = (c) => (typeof astroAiSnapshot.buildPredictiveBirthHeaderLines === 'function' ? astroAiSnapshot.buildPredictiveBirthHeaderLines(c) : []);
const currentMomentLines = (c, x) => (typeof astroAiSnapshot.buildCurrentMomentLines === 'function' ? astroAiSnapshot.buildCurrentMomentLines(c, x) : []);
const methodNoteLines = (k) => (typeof astroAiSnapshot.buildMethodNoteLines === 'function' ? astroAiSnapshot.buildMethodNoteLines(k) : []);

// Balbillus 法（时主,旺距削减）:
//  ① 主限长度(年) = N′ × (360 − d) ⁄ 360。d = 本命星所在「序数度」(⌊黄经⌋ + 1)离其擢升度的最近整度角距;
//     N′ = 水 20 / 金 8 / 木 12 / 土 30、日 18 / 月 24 / 火 14(三星取小年减一)。360 日历下即 N′ × (360 − d) 日,
//     换成所选年长再按比例放大。
//  ② 主限序 = 七星按本命黄经升序、从起始星旋转铺开。
//  ③ 子限:以父期主星为起点按同一次序,每颗子星 = 它上一层时长 ÷ 12(第二层 = 一级时长 ÷ 12,第三层 ÷ 144 …);
//     一轮七颗合计不到父期 —— 「一轮」照此不填满,「循环」重复这一轮直到父期末,「填满」把一轮的末段拉长到父期末。
//  ④ 年长随选项(回归年 / 恒星年 / 360 日 / Abu Ma'shar / Masha'allah / Bija 修正)。
//  距离口径 d 另有 forward(自擢升度顺黄道到本命星)一解,做成参数。
//  独立引擎,不碰 decennials.js / yearSystem129.js。
import { TIME_LORD_YEAR_TYPES } from '../utils/timeLordYears.js';

// 七星 Balbillus 小年（年）。Σ = 129。
export const BALBILLUS_YEARS = {
	[AstroConst.SUN]: 19,
	[AstroConst.MOON]: 25,
	[AstroConst.SATURN]: 30,
	[AstroConst.JUPITER]: 12,
	[AstroConst.MARS]: 15,
	[AstroConst.VENUS]: 8,
	[AstroConst.MERCURY]: 20,
};

// 传统擢升度（绝对黄经 0–360）：日 白羊19° / 月 金牛3° / 土 天秤21° / 木 巨蟹15° / 火 摩羯28° / 金 双鱼27° / 水 室女15°。
export const BALBILLUS_EXALT = {
	[AstroConst.SUN]: 0 + 19,
	[AstroConst.MOON]: 30 + 3,
	[AstroConst.SATURN]: 180 + 21,
	[AstroConst.JUPITER]: 90 + 15,
	[AstroConst.MARS]: 270 + 28,
	[AstroConst.VENUS]: 330 + 27,
	[AstroConst.MERCURY]: 150 + 15,
};

const PLANETS = [
	AstroConst.SUN, AstroConst.MOON, AstroConst.SATURN, AstroConst.JUPITER,
	AstroConst.MARS, AstroConst.VENUS, AstroConst.MERCURY,
];

// 年制:与 129 年系统共用一张年长表(utils/timeLordYears)。
export const BALBILLUS_YEAR_TYPES = TIME_LORD_YEAR_TYPES;

// 主限基数 N′:日 / 月 / 火取小年减一,其余同小年。
export const BALBILLUS_PERIOD_BASE = {
	[AstroConst.SUN]: 18,
	[AstroConst.MOON]: 24,
	[AstroConst.SATURN]: 30,
	[AstroConst.JUPITER]: 12,
	[AstroConst.MARS]: 14,
	[AstroConst.VENUS]: 8,
	[AstroConst.MERCURY]: 20,
};

// 子限铺法
export const BALBILLUS_SUB_RULES = {
	once: '一轮（各子限 = 该星上一层时长 ÷ 12,不填满父期）',
	cycle: '循环（一轮接一轮直到父期末）',
	fill: '填满（一轮,末段拉长到父期末）',
};

// 距离口径：nearest 最近角距；forward 自擢升度顺黄道到本命星。
export const BALBILLUS_MODES = {
	nearest: '最近角距（nearest）',
	forward: '顺黄道距（forward）',
};

export const BALBILLUS_DEFAULT_OPTS = {
	startPlanet: AstroConst.SUN,
	mode: 'nearest',
	yearType: 'solar',
	subRule: 'once',
	maxDepth: 5,
	maxAge: 120,
};

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

// 出生时刻单源(全年份域:公元前 / 公元 1–99 年 / 五位年不误读;见 utils/civilMoment)
function parseBirthMoment(chartObj){
	return birthMomentOfChart(chartObj);
}

function natalLon(chartObj, id){
	const chart = (chartObj && chartObj.chart) ? chartObj.chart : {};
	const objects = Array.isArray(chart.objects) ? chart.objects : [];
	const o = objects.find((x) => x.id === id);
	if(!o){ return null; }
	if(o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
	if(idx >= 0 && o.signlon !== undefined && o.signlon !== null){ return idx * 30 + Number(o.signlon); }
	return null;
}

function rotate(list, start){
	const i = list.indexOf(start);
	if(i <= 0){ return list.slice(); }
	return list.slice(i).concat(list.slice(0, i));
}

// 序数度:黄经 [k, k+1) 记第 k+1 度(擢升度本身即整度数)。
export function ordinalDegree(lon){
	return Math.floor(norm360(lon)) + 1;
}

// d = 本命星序数度离其擢升度的整度角距。nearest = 最近角距;forward = 自擢升度顺黄道到本命星。
export function balbillusDistance(lon, exalt, mode){
	const raw = norm360(ordinalDegree(lon) - exalt);
	if(mode === 'forward'){ return raw; }
	return Math.min(raw, 360 - raw);
}

// 主限长度(年)= N′ × (360 − d) ⁄ 360。
export function balbillusPeriodYears(planet, lon, mode){
	const base = BALBILLUS_PERIOD_BASE[planet];
	if(lon === null || lon === undefined || BALBILLUS_EXALT[planet] === undefined){ return base; }
	const d = balbillusDistance(lon, BALBILLUS_EXALT[planet], mode);
	return base * (360 - d) / 360;
}

// 七星按本命黄经升序、旋转到起始星 → 主限/子限统一行进序。
export function zodiacalOrder(longitudes, startPlanet){
	const planets = PLANETS.filter((p) => longitudes[p] !== null && longitudes[p] !== undefined);
	planets.sort((a, b) => norm360(longitudes[a]) - norm360(longitudes[b]));
	const list = planets.length ? planets : PLANETS.slice();
	return rotate(list, startPlanet);
}

function resolveOpts(opts){
	const o = { ...BALBILLUS_DEFAULT_OPTS, ...(opts || {}) };
	if(!BALBILLUS_YEAR_TYPES[o.yearType]){ o.yearType = 'solar'; }
	if(!BALBILLUS_MODES[o.mode]){ o.mode = 'nearest'; }
	if(!BALBILLUS_SUB_RULES[o.subRule]){ o.subRule = 'once'; }
	if(BALBILLUS_YEARS[o.startPlanet] === undefined){ o.startPlanet = AstroConst.SUN; }
	if(!(o.maxDepth >= 1)){ o.maxDepth = 5; }
	if(!(o.maxAge > 0)){ o.maxAge = 120; }
	return o;
}

// 构造上下文：本命七星黄经 + 行进序 + 出生 + 选项。前端组件持有 ctx 后即可懒构造树。
export function buildBalbillusContext(chartObj, opts){
	const o = resolveOpts(opts);
	const longitudes = {};
	PLANETS.forEach((p) => { longitudes[p] = natalLon(chartObj, p); });
	const order = zodiacalOrder(longitudes, o.startPlanet);
	const birth = parseBirthMoment(chartObj);
	return { longitudes, order, birthMs: birth ? birth.valueOf() : null, opts: o };
}

function dateOf(ctx, days){
	if(ctx.birthMs === null || ctx.birthMs === undefined){ return ''; }
	return civilDateOfMoment(moment(ctx.birthMs).add(days, 'days'));   // 民用历日期标签(1582 以前儒略历)
}

function makeNode(ctx, planet, level, startDays, durDays){
	return {
		key: `${level}|${planet}|${Math.round(startDays * 100)}`,
		planet,
		level,
		startDays,
		durDays,
		startDate: dateOf(ctx, startDays),
		durYears: durDays / BALBILLUS_YEAR_TYPES[ctx.opts.yearType].days,
		isLeaf: level >= ctx.opts.maxDepth,
	};
}

// 各层时间单位（天），逐层 /12：L1=年(365.2422)、L2=年/12(月,30.4368)、L3=年/144(2.5364)…
function timeUnitDays(ctx, level){
	const y = BALBILLUS_YEAR_TYPES[ctx.opts.yearType].days;
	return y / Math.pow(12, Math.max(0, level - 1));
}

// 一级主限：按旺距削减后的长度，循环行进序铺开到 maxAge。
export function buildBalbillusRoots(ctx){
	const { order, longitudes, opts } = ctx;
	const yearDays = BALBILLUS_YEAR_TYPES[opts.yearType].days;
	const maxDays = opts.maxAge * yearDays;
	const roots = [];
	let tDays = 0;
	let i = 0;
	while(tDays < maxDays && i < 200){
		const p = order[i % order.length];
		const durYears = balbillusPeriodYears(p, longitudes[p], opts.mode);
		const durDays = Math.max(0, durYears) * yearDays;
		roots.push(makeNode(ctx, p, 1, tDays, durDays));
		if(durDays <= 0){ break; }
		tDays += durDays;
		i++;
	}
	return roots;
}

// 子限:以父期主星为起点按行进序,每颗子星 = 它上一层时长 ÷ 12(第 k 层 = 一级时长 ÷ 12^(k−1));
// 一轮合计不到父期 —— once 照此不填满,cycle 一轮接一轮到父期末(末段截断),fill 把一轮的末段拉长到父期末。
export function buildBalbillusChildren(ctx, node){
	if(!node || node.level >= ctx.opts.maxDepth){ return []; }
	const seq = rotate(ctx.order, node.planet);
	const unit = timeUnitDays(ctx, node.level + 1);
	const parentEnd = node.startDays + node.durDays;
	const rule = ctx.opts.subRule;
	const children = [];
	let t = node.startDays;
	for(let i = 0; i < seq.length * (rule === 'cycle' ? 64 : 1); i++){
		const p = seq[i % seq.length];
		const isLastOfRound = (i % seq.length) === seq.length - 1;
		let dur = balbillusPeriodYears(p, ctx.longitudes[p], ctx.opts.mode) * unit;
		if(rule === 'fill' && isLastOfRound){ dur = parentEnd - t; }
		if(t + dur > parentEnd){ dur = parentEnd - t; }
		if(dur <= 1e-9){ break; }
		children.push(makeNode(ctx, p, node.level + 1, t, dur));
		t += dur;
	}
	return children;
}

function planetTxt(id){
	if(id === undefined || id === null || id === ''){ return '-'; }
	return AstroText.AstroTxtMsg[id] || `${id}`;
}

// AI 快照：展平一级主限 + 二级子限（够 AI 用，避免深递归爆量）。section 头与 aiExport preset 对齐。
export function buildBalbillusSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const ctx = buildBalbillusContext(chartObj, opts);
	const roots = buildBalbillusRoots(ctx);
	if(!roots.length){ return ''; }
	const o = ctx.opts;
	const lines = [];
	// [YB] 头部盘主生辰([起盘信息];无数据 helper 自返 [],不产空段头)。
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[Balbillus]');
	lines.push(`Balbillus 法（旺距削减）：主限长度 = N′ ×（360 − 离擢升度的整度角距）⁄ 360 年（N′：水 20 / 金 8 / 木 12 / 土 30 / 日 18 / 月 24 / 火 14），七星按本命黄经序从 ${planetTxt(o.startPlanet)} 起铺开；子限每颗 = 该星上一层时长 ÷ 12。年制=${BALBILLUS_YEAR_TYPES[o.yearType].label}、距离口径=${BALBILLUS_MODES[o.mode]}、子限=${BALBILLUS_SUB_RULES[o.subRule]}。`);
	lines.push('');
	lines.push('| 主限 | 子限 | 起始日期 | 时长(年) |');
	lines.push('| --- | --- | --- | --- |');
	roots.forEach((main) => {
		const subs = buildBalbillusChildren(ctx, main);
		if(!subs.length){
			lines.push(`| ${planetTxt(main.planet)} | - | ${main.startDate || '-'} | ${main.durYears.toFixed(2)} |`);
			return;
		}
		subs.forEach((sub, i) => {
			const mainLabel = i === 0 ? `${planetTxt(main.planet)}(${main.durYears.toFixed(2)}年)` : '';
			lines.push(`| ${mainLabel} | ${planetTxt(sub.planet)} | ${sub.startDate || '-'} | ${sub.durYears.toFixed(2)} |`);
		});
	});
	// [YB] 尾部 [当前时点]+[方法说明];定位行用本引擎自己的天数轴(startDays/durDays=自出生起日历天)找今日落点。
	const extraLines = [];
	if(ctx.birthMs !== null && ctx.birthMs !== undefined){
		const ageDays = (Date.now() - ctx.birthMs) / 86400000;
		const curMain = roots.find((n) => ageDays >= n.startDays && ageDays < n.startDays + n.durDays);
		if(curMain){
			extraLines.push(`当前主限：${planetTxt(curMain.planet)}（起 ${curMain.startDate || '-'}，时长 ${curMain.durYears.toFixed(2)} 年）`);
			const curSub = buildBalbillusChildren(ctx, curMain).find((n) => ageDays >= n.startDays && ageDays < n.startDays + n.durDays);
			if(curSub){
				extraLines.push(`当前子限：${planetTxt(curSub.planet)}（起 ${curSub.startDate || '-'}）`);
			}
		}
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('balbillus')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}
