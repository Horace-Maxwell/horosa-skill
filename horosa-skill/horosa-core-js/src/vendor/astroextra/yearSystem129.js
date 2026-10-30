import moment from 'moment';
import { birthMomentOfChart, civilDateOfMoment } from '../utils/civilMoment.js';
import * as AstroConst from './progConst.js';
import * as AstroText from './progConst.js';
import { TIME_LORD_YEAR_TYPES } from '../utils/timeLordYears.js';
// 三段补厚共享 helper(起盘信息 / 当前时点 / 方法说明;astroAiSnapshot 不回引本文件,无环)。
// namespace import + typeof 守卫:测试环境可能部分 mock astroAiSnapshot,缺函数时回 [] 保底。
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

// 129 年系统(时主):七星各管其小年(土 30 / 木 12 / 火 15 / 日 19 / 金 8 / 水 20 / 月 25,合 129 年)。
//  ① 主限序:七星按本命黄经升序、从起始星旋转铺开(黄道顺序);可选迦勒底序(土木火日金水月,从起始星旋转)。
//  ② 主限长度 = 小年 × 年长。
//  ③ 子限:从父期主星起按同一次序,三种铺法 ——
//     days         子星小年 × ⌊2.5 × 父星小年⌋ 日;一轮七颗合计不到父期,不填满
//     proportional 父期 × 子星小年 ⁄ 129;一轮刚好填满父期
//     equal        父期 ⁄ 7
//  起始星默认太阳,可选区分光体(昼日夜月)或任一颗。单一来源:页面、AI 快照等各处都调本模块。
export const YS129_MINOR_YEARS = {
	[AstroConst.SATURN]: 30,
	[AstroConst.JUPITER]: 12,
	[AstroConst.MARS]: 15,
	[AstroConst.SUN]: 19,
	[AstroConst.VENUS]: 8,
	[AstroConst.MERCURY]: 20,
	[AstroConst.MOON]: 25,
};
const CHALDEAN = [AstroConst.SATURN, AstroConst.JUPITER, AstroConst.MARS, AstroConst.SUN, AstroConst.VENUS, AstroConst.MERCURY, AstroConst.MOON];

export const YS129_SECT_START = 'sect';
export const YS129_SECT_START_LABEL = '区分光体（昼生太阳、夜生月亮）';
export const YS129_START_OPTIONS = [YS129_SECT_START, AstroConst.SUN, AstroConst.MOON, AstroConst.MERCURY, AstroConst.VENUS, AstroConst.MARS, AstroConst.JUPITER, AstroConst.SATURN];
export const YS129_ORDERS = {
	zodiacal: '黄道顺序（本命黄经递增）',
	chaldean: '迦勒底序（土木火日金水月）',
};
export const YS129_SUB_RULES = {
	days: '日数法（子星小年 × ⌊2.5 × 主星小年⌋ 日，不填满主限）',
	proportional: '比例法（主限 × 子星小年 ⁄ 129，填满主限）',
	equal: '七等分（主限 ⁄ 7）',
};
export const YS129_YEAR_TYPES = TIME_LORD_YEAR_TYPES;
export const YS129_DEFAULT_OPTS = { startPlanet: AstroConst.SUN, order: 'zodiacal', yearType: 'solar', subRule: 'days', maxAge: 120 };

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

function natalLon(chartObj, id){
	const chart = (chartObj && chartObj.chart) ? chartObj.chart : {};
	const objects = Array.isArray(chart.objects) ? chart.objects : [];
	const o = objects.find((x) => x.id === id);
	if(!o){ return null; }
	if(o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
	return (idx >= 0 && o.signlon !== undefined && o.signlon !== null) ? idx * 30 + Number(o.signlon) : null;
}

function rotate(list, start){
	const i = list.indexOf(start);
	return i <= 0 ? list.slice() : list.slice(i).concat(list.slice(0, i));
}

export function resolveYearSystem129Opts(opts){
	const o = { ...YS129_DEFAULT_OPTS, ...(opts || {}) };
	if(YS129_START_OPTIONS.indexOf(o.startPlanet) < 0){ o.startPlanet = YS129_DEFAULT_OPTS.startPlanet; }
	if(!YS129_ORDERS[o.order]){ o.order = YS129_DEFAULT_OPTS.order; }
	if(!YS129_YEAR_TYPES[o.yearType]){ o.yearType = YS129_DEFAULT_OPTS.yearType; }
	if(!YS129_SUB_RULES[o.subRule]){ o.subRule = YS129_DEFAULT_OPTS.subRule; }
	if(!(o.maxAge > 0)){ o.maxAge = YS129_DEFAULT_OPTS.maxAge; }
	return o;
}

function startPlanetOf(chartObj, opt){
	if(opt !== YS129_SECT_START){ return opt; }
	const chart = (chartObj && chartObj.chart) || {};
	return chart.isDiurnal === false ? AstroConst.MOON : AstroConst.SUN;
}

// 主限 / 子限行进序
export function yearSystem129Order(chartObj, opts){
	const o = resolveYearSystem129Opts(opts);
	const start = startPlanetOf(chartObj, o.startPlanet);
	if(o.order === 'chaldean'){ return rotate(CHALDEAN, start); }
	const lons = {};
	CHALDEAN.forEach((p) => { lons[p] = natalLon(chartObj, p); });
	const planets = CHALDEAN.filter((p) => lons[p] !== null);
	if(planets.length < CHALDEAN.length){ return rotate(CHALDEAN, start); }
	planets.sort((a, b) => norm360(lons[a]) - norm360(lons[b]));
	return rotate(planets, start);
}

function subDurationsDays(parent, parentDays, seq, rule){
	if(rule === 'equal'){ return seq.map(() => parentDays / seq.length); }
	if(rule === 'proportional'){ return seq.map((p) => parentDays * YS129_MINOR_YEARS[p] / 129); }
	const unit = Math.floor(2.5 * YS129_MINOR_YEARS[parent]);
	return seq.map((p) => YS129_MINOR_YEARS[p] * unit);
}

// 返回 { opts, order, birthMs, rows: [{ mainDirect, startDays, durDays, durYears, startDate, subDirect: [{ subDirect, startDays, durDays, durYears, date }] }] }
export function computeYearSystem129(chartObj, opts){
	const o = resolveYearSystem129Opts(opts);
	const order = yearSystem129Order(chartObj, o);
	const birth = birthMomentOfChart(chartObj);
	const birthMs = birth ? birth.valueOf() : null;
	const yearDays = YS129_YEAR_TYPES[o.yearType].days;
	const dateOf = (days) => (birthMs === null ? '' : civilDateOfMoment(moment(birthMs).add(days, 'days')));
	const rows = [];
	let t = 0;
	for(let i = 0; t < o.maxAge * yearDays && i < 100; i++){
		const p = order[i % order.length];
		const durDays = YS129_MINOR_YEARS[p] * yearDays;
		const seq = rotate(order, p);
		const subDur = subDurationsDays(p, durDays, seq, o.subRule);
		let s = t;
		const subs = seq.map((q, k) => {
			const node = { subDirect: q, startDays: s, durDays: subDur[k], durYears: subDur[k] / yearDays, date: dateOf(s) };
			s += subDur[k];
			return node;
		});
		rows.push({ mainDirect: p, startDays: t, durDays, durYears: durDays / yearDays, startDate: dateOf(t), subDirect: subs });
		t += durDays;
	}
	return { opts: o, order, birthMs, rows };
}

function planetTxt(id){
	if(id === undefined || id === null || id === ''){ return '-'; }
	return AstroText.AstroTxtMsg[id] || `${id}`;
}

export function yearSystem129StartLabel(opt){
	return opt === YS129_SECT_START ? YS129_SECT_START_LABEL : planetTxt(opt);
}

// 一行口径说明(页面头部与 AI 快照共用)
export function yearSystem129OptionsLine(chartObj, opts){
	const o = resolveYearSystem129Opts(opts);
	const start = startPlanetOf(chartObj, o.startPlanet);
	const startTxt = o.startPlanet === YS129_SECT_START ? `区分光体 → ${planetTxt(start)}` : planetTxt(start);
	return `起始星=${startTxt}、次序=${YS129_ORDERS[o.order]}、年制=${YS129_YEAR_TYPES[o.yearType].label}、子限=${YS129_SUB_RULES[o.subRule]}`;
}

// 129 年系统 AI 快照。段头与 aiExport preset 对齐(起盘信息 / 129年系统表格 / 当前时点 / 方法说明)。无本命七星返回 ''。
export function buildYearSystem129SnapshotText(chartObj, opts){
	if(!chartObj || !chartObj.chart){ return ''; }
	const res = computeYearSystem129(chartObj, opts);
	if(!res.rows.length){ return ''; }
	const lines = [];
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[129年系统表格]');
	lines.push(`七星各管其小年（土 30 / 木 12 / 火 15 / 日 19 / 金 8 / 水 20 / 月 25，合 129 年）。${yearSystem129OptionsLine(chartObj, res.opts)}。`);
	lines.push('');
	lines.push('| 主限 | 子限 | 起始日期 | 时长(年) |');
	lines.push('| --- | --- | --- | --- |');
	res.rows.forEach((main) => {
		main.subDirect.forEach((sub, i) => {
			const mainLabel = i === 0 ? `${planetTxt(main.mainDirect)}(${main.durYears.toFixed(2)}年,起 ${main.startDate || '-'})` : '';
			lines.push(`| ${mainLabel} | ${planetTxt(sub.subDirect)} | ${sub.date || '-'} | ${sub.durYears.toFixed(2)} |`);
		});
	});
	// 定位行:按本引擎的天数轴(自出生起日历天)找今日落点;日数法子限一轮不填满主限,落在空档时只报主限。
	const extraLines = [];
	if(res.birthMs !== null){
		const ageDays = (Date.now() - res.birthMs) / 86400000;
		const cur = res.rows.find((r) => ageDays >= r.startDays && ageDays < r.startDays + r.durDays);
		if(cur){
			extraLines.push(`当前主限：${planetTxt(cur.mainDirect)}（起 ${cur.startDate || '-'}，时长 ${cur.durYears.toFixed(2)} 年）`);
			const sub = cur.subDirect.find((n) => ageDays >= n.startDays && ageDays < n.startDays + n.durDays);
			extraLines.push(sub ? `当前子限：${planetTxt(sub.subDirect)}（起 ${sub.date || '-'}）` : '当前子限：本主限一轮子限已走完（日数法不填满主限，余下时段无子限）');
		}
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('yearsystem129')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}
