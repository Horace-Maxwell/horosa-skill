import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';

// 数字相位推运（120 年关键点）。纯前端：仅重新切分本命盘。
//  ① 七星「小年数」：土3 / 水8 / 日18 / 金5 / 火7 / 木9 / 月13。
//  ② 释放点：身=月亮 / 命=上升（默认月亮）。
//  ③ 位置挂钩：行星落「自释放点起第 k 个星座」→ 与数字 k 挂钩，凡 N 为 k 的倍数之年即激活该星
//     （「过运传递与接收」：释放点 → 该行星）。
//  ④ 查表挂钩：凡 N 为某星小年的倍数之年，亦激活该星。
//  ⑤ 既被位置又被查表激活之年，作用叠加。
// 区别于 yearsystem129（Balbillus 旺距变体，后端算），本法用小年 + 因数激活。

export const PERIOD_NUMBERS = {
	[AstroConst.SATURN]: 3,
	[AstroConst.MERCURY]: 8,
	[AstroConst.SUN]: 18,
	[AstroConst.VENUS]: 5,
	[AstroConst.MARS]: 7,
	[AstroConst.JUPITER]: 9,
	[AstroConst.MOON]: 13,
};

export const RELEASE_MODES = { soul: '身（月亮起）', body: '命（上升起）' };

export const KEYPOINTS_DEFAULT_OPTS = { mode: 'soul', maxAge: 120 };

const PLANETS = [AstroConst.SUN, AstroConst.MOON, AstroConst.MERCURY, AstroConst.VENUS, AstroConst.MARS, AstroConst.JUPITER, AstroConst.SATURN];

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

function findObj(chartObj, id){
	const objs = (chartObj && chartObj.chart && chartObj.chart.objects) || [];
	return objs.find((x) => x.id === id) || null;
}

function lonOf(chartObj, id){
	const o = findObj(chartObj, id);
	if(o && o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	if(o){
		const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
		if(idx >= 0 && o.signlon !== undefined && o.signlon !== null){ return idx * 30 + Number(o.signlon); }
	}
	return null;
}

function ascLon(chartObj){
	const o = findObj(chartObj, AstroConst.ASC);
	if(o && o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	const chart = chartObj && chartObj.chart;
	if(chart && chart.houseMap && chart.houseMap.House1 && chart.houseMap.House1.lon !== undefined){ return Number(chart.houseMap.House1.lon); }
	return null;
}

function signIndexOfLon(lon){ return Math.floor(norm360(lon) / 30); }

function planetTxt(id){ return AstroText.AstroTxtMsg[id] || `${id}`; }

// 因数对：N = a×b（a≤b），用于显示「28 = 4×7」。
function factorPairs(n){
	const pairs = [];
	for(let a = 2; a * a <= n; a++){
		if(n % a === 0){ pairs.push([a, n / a]); }
	}
	return pairs;
}

function resolveOpts(opts){
	const o = { ...KEYPOINTS_DEFAULT_OPTS, ...(opts || {}) };
	if(!RELEASE_MODES[o.mode]){ o.mode = 'soul'; }
	o.maxAge = Number(o.maxAge) > 0 ? Math.min(120, Number(o.maxAge)) : 120;
	return o;
}

export function buildKeypoints(chartObj, opts){
	const o = resolveOpts(opts);
	const chart = chartObj && chartObj.chart;
	if(!chart){ return null; }
	const releaseLon = o.mode === 'body' ? ascLon(chartObj) : lonOf(chartObj, AstroConst.MOON);
	if(releaseLon == null){ return { mode: o.mode, rows: [], positions: [] }; }
	const releaseSignIdx = signIndexOfLon(releaseLon);
	// 各星「位置数」k = 自释放点起第几个星座（1..12）。
	const positions = PLANETS.map((p) => {
		const lon = lonOf(chartObj, p);
		if(lon == null){ return null; }
		const k = ((signIndexOfLon(lon) - releaseSignIdx) % 12 + 12) % 12 + 1;
		return { planet: p, planetCn: planetTxt(p), k, period: PERIOD_NUMBERS[p] };
	}).filter(Boolean);
	const rows = [];
	for(let N = 1; N <= o.maxAge; N++){
		const posActive = positions.filter((x) => N % x.k === 0);
		const tableActive = PLANETS.filter((p) => N % PERIOD_NUMBERS[p] === 0).map((p) => ({ planet: p, planetCn: planetTxt(p), period: PERIOD_NUMBERS[p] }));
		if(!posActive.length && !tableActive.length){ continue; }
		rows.push({
			age: N,
			house: ((N - 1) % 12) + 1,
			factors: factorPairs(N),
			posActive,
			tableActive,
		});
	}
	return { mode: o.mode, modeCn: RELEASE_MODES[o.mode], releaseSignIdx, positions, rows };
}

export function buildKeypointsSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const r = buildKeypoints(chartObj, opts);
	if(!r || !r.rows || !r.rows.length){ return ''; }
	const lines = ['[数字相位推运]'];
	lines.push(`释放点=${r.modeCn}。各星与「自释放点起第 k 个星座」挂钩数字 k，凡年龄为 k 或其小年（土3/水8/日18/金5/火7/木9/月13）之倍数即激活该星（过运传递：释放点→该星）。`);
	lines.push('');
	lines.push('星位挂钩：' + r.positions.map((x) => `${x.planetCn}=第${x.k}座(小年${x.period})`).join('，'));
	lines.push('');
	lines.push('| 年龄 | 因数 | 位置激活 | 小年激活 |');
	lines.push('| --- | --- | --- | --- |');
	r.rows.forEach((row) => {
		const fac = row.factors.length ? row.factors.map((f) => f.join('×')).join('/') : '质数';
		const pos = row.posActive.length ? row.posActive.map((x) => x.planetCn).join('·') : '-';
		const tab = row.tableActive.length ? row.tableActive.map((x) => x.planetCn).join('·') : '-';
		lines.push(`| ${row.age} | ${fac} | ${pos} | ${tab} |`);
	});
	return lines.join('\n');
}

export default { buildKeypoints, buildKeypointsSnapshotText, PERIOD_NUMBERS, RELEASE_MODES, KEYPOINTS_DEFAULT_OPTS };
