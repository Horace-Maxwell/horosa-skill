import moment from 'moment';
import * as AstroConst from './progConst.js';
import * as AstroText from './progConst.js';

// Balbillus 法（129 年系统 · 旺距削减变体）。还原自经典占星 Balbillus / 129-year Time-Lord 体系：
//  ① 七星各有「Balbillus 小年」(Σ=129)；
//  ② 主限长度 = N × (1 − d/360)，d = 本命星黄经离其「擢升度」的角距（每差 1 星座扣 N 月、每差 1 度扣 N 日，等价式）；
//  ③ 主限序 = 七星按本命黄经升序、从起始星旋转铺开；
//  ④ 每主限期再以该期主星为起点、按 129 权重递归切分子限（可至 5 层）；
//  ⑤ 始终用 Hellenistic 年（默认 360 日 / 30 日月），可切 solar(365.2422 日)。
//  距离口径 d 有 nearest（最近角距）/ forward（自擢升度顺黄道到本命星）两解 → 做成参数。
//  独立引擎，不碰 decennials.js / yearsystem129.js。

export const BALBILLUS_TOTAL = 129;

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

// 年制：Balbillus 用回归年 365.24219879 日。
// 「Egyptian/Hellenistic(360)」选项只是标签、不影响周期数学；故默认 solar，
// 真 360 日年保留给想要古典 Hellenistic 的用户。
export const BALBILLUS_YEAR_TYPES = {
	solar: { days: 365.24219879, label: 'Solar 回归年（365.2422 日）' },
	hellenistic: { days: 360, label: 'Egyptian/Hellenistic（360 日）' },
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
	maxDepth: 5,
	maxAge: 120,
};

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

function parseBirthMoment(chartObj){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim();
	if(!birth){ return null; }
	const m = moment(birth.replace(/\//g, '-'), ['YYYY-MM-DD HH:mm:ss', 'YYYY-MM-DD HH:mm', 'YYYY-MM-DD']);
	return m.isValid() ? m : null;
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

// d = 本命星黄经离其擢升度的角距。nearest=最近角距；forward=自擢升度顺黄道到本命星。
export function balbillusDistance(lon, exalt, mode){
	const raw = norm360(lon - exalt);
	if(mode === 'forward'){ return raw; }
	return Math.min(raw, 360 - raw);
}

// 削减拟合：日/月/火这 3 星用的不是黄经距，但等价于「黄经最近角距的线性变换」d = a×ecl + b——
// 即便在擢升处也有基础削减 b。其余四星 a=1/b=0（纯黄经最近角距）。仅 nearest 口径生效。
const BALBILLUS_REDUCTION_FIT = {
	[AstroConst.SUN]: { a: 0.9431, b: 19.47 },
	[AstroConst.MOON]: { a: 0.9592, b: 14.76 },
	[AstroConst.MARS]: { a: 0.9268, b: 24.39 },
};

// 主限长度（年）= N × (1 − d/360)。
export function balbillusPeriodYears(planet, lon, mode){
	const N = BALBILLUS_YEARS[planet];
	if(lon === null || lon === undefined || BALBILLUS_EXALT[planet] === undefined){ return N; }
	let d = balbillusDistance(lon, BALBILLUS_EXALT[planet], mode);
	const fit = BALBILLUS_REDUCTION_FIT[planet];
	if(fit && mode === 'nearest'){ d = fit.a * d + fit.b; }
	d = Math.max(0, Math.min(360, d));
	return N * (1 - d / 360);
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
	return moment(ctx.birthMs).add(days, 'days').format('YYYY-MM-DD');
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

// 子限结构：时间单位逐级降级——每子段时长 = 削减年数(子星) × 当前层时间单位
// (L2=月)，自父星起按行进序铺开；**末段填满父期剩余**（最后一颗星被拉长到父期末），
// 自然长度溢出父期则截断。**不是**原先的「129 权重切父期」。
export function buildBalbillusChildren(ctx, node){
	if(!node || node.level >= ctx.opts.maxDepth){ return []; }
	const seq = rotate(ctx.order, node.planet);
	const unit = timeUnitDays(ctx, node.level + 1);
	const parentEnd = node.startDays + node.durDays;
	const children = [];
	let t = node.startDays;
	for(let i = 0; i < seq.length; i++){
		const p = seq[i];
		const isLast = i === seq.length - 1;
		let dur;
		if(isLast){
			dur = Math.max(0, parentEnd - t);
		}else{
			dur = balbillusPeriodYears(p, ctx.longitudes[p], ctx.opts.mode) * unit;
			if(t + dur > parentEnd){ dur = parentEnd - t; }
		}
		if(dur <= 0){ break; }
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
	lines.push('[Balbillus]');
	lines.push(`Balbillus 法（129 年系统 · 旺距削减）：主限长度 = 小年 × (1 − 离擢升度角距/360)，七星按本命黄经序从 ${planetTxt(o.startPlanet)} 起铺开，再按 129 权重递归切子限。年制=${BALBILLUS_YEAR_TYPES[o.yearType].label}、距离口径=${BALBILLUS_MODES[o.mode]}。`);
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
	return lines.join('\n');
}
