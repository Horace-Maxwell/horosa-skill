// divination/election/returnCharts.js
// 回归盘(日返/月返)与主限命中——择日「合参」第三段。全部按需触发(UI 按钮拉取),不默认拉盘。
// 日返=太阳精确还本命黄经(~365.25 日);月返=月还本命度(27.3 恒星月,勿与 29.5 朔望混)。
// 主限命中=只读复用既有主限引擎:按本命参数带 predictive+主限法补拉一张命盘,
// 取 Result 顶层 predictives.primaryDirection 过滤择日日期前后命中;绝不触碰引擎与默认路径。
import moment from 'moment';



import { PLANETS } from '../data/planets.js';
import { SIGNS } from '../data/signs.js';
import { SOLAR_RETURN_DAYS, LUNAR_RETURN_DAYS } from '../engine/timeLords.js';

const cn = (k) => (PLANETS[k] || {}).cn || k;
const RATE = { sun: 360 / SOLAR_RETURN_DAYS, moon: 360 / LUNAR_RETURN_DAYS };   // °/日(平均)

function shortDelta(target, cur){
	return ((target - cur + 540) % 360) - 180;   // ∈(−180,180]
}
function fmt(m){ return m.format('YYYY-MM-DD HH:mm:ss'); }

// 牛顿迭代求「电盘时刻之前最近一次」回归精确时刻。返回 {momentStr, facts} 或 null。
// 回归盘要点(展示层):光体状态 + 角宫吉凶 + 上升座。
export function judgeReturnFacts(kindCn, ret){
	if(!ret || !ret.facts) return [];
	const facts = ret.facts;
	const notes = [];
	const asc = facts.meta.ascSign;
	notes.push({ pol: 'info', text: `${kindCn}时刻 ${ret.momentStr}，上升 ${SIGNS[asc] ? SIGNS[asc].cn : asc || '—'}。` });
	['jupiter', 'venus'].forEach((k) => {
		const p = facts.planets[k];
		if(p && p.angularity === 'angular') notes.push({ pol: 'positive', text: `${kindCn}盘吉星 ${cn(k)} 临角宫（本期得助）。` });
	});
	['saturn', 'mars'].forEach((k) => {
		const p = facts.planets[k];
		if(p && p.angularity === 'angular') notes.push({ pol: 'negative', text: `${kindCn}盘凶星 ${cn(k)} 临角宫（本期承压）。` });
	});
	const light = facts.meta.isDiurnal ? 'sun' : 'moon';
	const lp = facts.planets[light];
	if(lp){
		if(lp.dignityScore >= 2) notes.push({ pol: 'positive', text: `${kindCn}盘区分光 ${cn(light)} 有尊贵。` });
		else if(lp.combustion === 'combust' || lp.dignityScore <= -4) notes.push({ pol: 'negative', text: `${kindCn}盘区分光 ${cn(light)} 受克。` });
	}
	return notes;
}

// 双返一站式:自电盘时刻回推最近日返+月返(约 6+6 次轻量排盘,cache:true)。
// 主限命中(只读):本命参数 + predictive/主限法旗标补拉命盘 → 取 predictives.primaryDirection,
// 过滤择日日期 ±windowDays,按时距升序取前 N。行结构 [_, promissor, significator, method, date]。
