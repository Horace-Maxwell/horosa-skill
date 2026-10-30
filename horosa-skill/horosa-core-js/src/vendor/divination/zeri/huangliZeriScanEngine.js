// 日粒度扫描引擎(纯前端零 HTTP)。
// 供数单源 = buildHuangliDay(老黄历卡片/吉日榜/日子馆/AI 快照同一函数,自带 memo)——
// 主黄历算法修正,择日自动跟。日粒度技法**不套** hourlyScanEngine(分钟 pick 语义不适用,
// 见其头注释铁律):逐日判定+连续命中日合并成行;行 pick=起日 12:00(跳老黄历页黄金采样点,
// 日级字段与 hour 无关,无边界内缩需求)。
// 树求值形状与奇门同构(组 all/any/not/xor + 叶 spec.evaluate),explain 叶序=UI 树 DFS 先序。
import { buildHuangliDay } from '../../calendar/huangliDay.js';
import { formatWallDate, nonexistentWallDateMessage } from './hourlyScanEngine.js';
import { HUANGLI_CONDITION_TYPES, makeHuangliZeriEvalCtx } from './huangliZeriConditionTypes.js';
import { datePartOf, parseDateParts } from '../../bazi/dateStrSafe.js';
import { civilJdnOfYmd, civilYmdOfJdn } from '../../utils/civilCalendar.js';

export const HUANGLI_MAX_TOTAL_HITS = 1000;
export const HUANGLI_MAX_SPAN_DAYS_TOTAL = 1830;
const CHUNK_DAYS = 64;

function pad2(n){
	return n < 10 ? `0${n}` : `${n}`;
}
// 日序号(自 1970-01-01 起的民用日序,结果行 startOrd / endOrd 对外口径;1583 年起与 Date.UTC ÷ 一日逐值相同)⇄ 民用日期
// (civilCalendar 单源:1582 以前儒略历,世纪年 2 月 29 日照扫;1582-10-04 的次日是 10-15,缺口里的 10 天不当真日期;0–99 年不当 19xx)。
const EPOCH_JDN = civilJdnOfYmd(1970, 1, 1);
function ymdToOrd(y, m, d){
	return civilJdnOfYmd(y, m, d) - EPOCH_JDN;
}
function ordToYmd(ord){
	const p = civilYmdOfJdn(ord + EPOCH_JDN);
	return { y: p.year, m: p.month, d: p.day };
}
function ymdText(w){
	return formatWallDate(w.y, w.m, w.d);   // 年补足 4 位(墙钟时间串单一来源)
}
function parseDateStr(s){
	// 黄历日引擎的可靠域是公元 1–9999 年(域外照旧判无效范围)
	const p = parseDateParts(`${s || ''}`.trim());
	return p && p.year >= 1 && p.year <= 9999 ? { y: p.year, m: p.month, d: p.day } : null;
}

export function evaluateHuangliTree(node, day, ctx, explain){
	const evalCtx = ctx || makeHuangliZeriEvalCtx(day);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateHuangliTree(child, day, evalCtx, explain));
		const passes = children.map((c)=>c.pass);
		let pass;
		if(node.type === 'any'){
			pass = passes.some(Boolean);
		}else if(node.type === 'not'){
			pass = !passes.every(Boolean);
		}else if(node.type === 'xor'){
			pass = passes.filter(Boolean).length % 2 === 1;
		}else{
			pass = passes.every(Boolean);
		}
		return explain ? { kind: 'group', op: node.type || 'all', pass, children } : { pass };
	}
	const spec = node ? HUANGLI_CONDITION_TYPES[node.type] : null;
	if(!spec){
		return explain ? { kind: 'leaf', type: node ? node.type : '?', pass: false, actual: '未知条件类型' } : { pass: false };
	}
	let verdict;
	try{
		verdict = spec.evaluate(day, node.params || {}, evalCtx) || { pass: false, actual: '' };
	}catch(e){
		verdict = { pass: false, actual: `求值异常:${e && e.message ? e.message : e}` };
	}
	return explain ? { kind: 'leaf', type: node.type, pass: !!verdict.pass, actual: verdict.actual || '' } : { pass: !!verdict.pass };
}

// 行特征列:建除·值宿·黄黑道(结果表「日课」列,与老黄历卡口径同源)。
function dayBadge(day){
	const jc = day.jianchu && day.jianchu.name ? `${day.jianchu.name}日` : '';
	const xiu = day.xiu && day.xiu.name ? `${day.xiu.name}宿` : '';
	const dao = day.tianshen && day.tianshen.type ? day.tianshen.type : '';
	return [jc, xiu, dao].filter(Boolean).join('·');
}

// 主入口。cfg:{startDate,endDate}(日粒度,无时刻);tree:compile 产物(与奇门同构);
// onProgress({done,total,hits,partial});signal:AbortSignal;limits.maxHits 测试注入。
export async function scanHuangli({ cfg, tree, onProgress, signal, limits }){
	const missing = nonexistentWallDateMessage(cfg && cfg.startDate, cfg && cfg.endDate);
	if(missing){
		const err = new Error(missing);
		err.code = 'invalid_date';
		throw err;
	}
	const w0 = parseDateStr(cfg && cfg.startDate);
	const w1 = parseDateStr(cfg && cfg.endDate);
	if(!w0 || !w1){
		const err = new Error('时间范围无效:须给起止日期');
		err.code = 'invalid_range';
		throw err;
	}
	const o0 = ymdToOrd(w0.y, w0.m, w0.d);
	const o1 = ymdToOrd(w1.y, w1.m, w1.d);
	if(!(o1 >= o0)){
		const err = new Error('时间范围无效:结束须不早于起始');
		err.code = 'invalid_range';
		throw err;
	}
	const total = o1 - o0 + 1;
	if(total > HUANGLI_MAX_SPAN_DAYS_TOTAL){
		const err = new Error(`跨度 ${total} 天超上限 ${HUANGLI_MAX_SPAN_DAYS_TOTAL} 天`);
		err.code = 'span_too_large';
		throw err;
	}
	const maxHits = (limits && Number(limits.maxHits) > 0) ? Number(limits.maxHits) : HUANGLI_MAX_TOTAL_HITS;
	const rows = [];
	let truncated = false;
	let cur = null;	// {startOrd, endOrd, badge}
	let evalCount = 0;
	const closeCur = ()=>{
		if(!cur){
			return;
		}
		const sw = ordToYmd(cur.startOrd);
		const ew = ordToYmd(cur.endOrd);
		rows.push({
			start: ymdText(sw),
			end: ymdText(ew),
			days: cur.endOrd - cur.startOrd + 1,
			// pick=起日/止日正午(黄金采样点;日级字段与 hour 无关,跳老黄历页直达该日)
			pick: `${ymdText(sw)} 12:00:00`,
			pickEnd: `${ymdText(ew)} 12:00:00`,
			startOrd: cur.startOrd,
			endOrd: cur.endOrd,
			badge: cur.badge,
		});
		cur = null;
	};
	let done = 0;
	const report = ()=>{
		if(typeof onProgress === 'function'){
			try{
				onProgress({ done, total, hits: rows.length, partial: rows.slice() });
			}catch(e){
				// 进度回调异常不阻断
			}
		}
	};
	for(let ord = o0; ord <= o1; ord++){
		if(signal && signal.aborted){
			const err = new Error('huangli scan aborted');
			err.name = 'AbortError';
			throw err;
		}
		const w = ordToYmd(ord);
		let pass = false;
		let badge = '';
		try{
			const day = buildHuangliDay(w.y, w.m, w.d);
			evalCount++;
			pass = !!evaluateHuangliTree(tree, day, null, false).pass;
			if(pass){
				badge = dayBadge(day);
			}
		}catch(e){
			pass = false;	// 域外/异常日按不命中(勿静默中断整扫)
		}
		if(pass){
			if(!cur){
				cur = { startOrd: ord, endOrd: ord, badge };
			}else{
				cur.endOrd = ord;	// 连续命中日并行(badge 保首日)
			}
		}else{
			closeCur();
		}
		if(rows.length >= maxHits){
			truncated = true;
			cur = null;
			break;
		}
		done = ord - o0 + 1;
		if(done % CHUNK_DAYS === 0){
			report();
			await new Promise((resolve)=>setTimeout(resolve, 0));
		}
	}
	closeCur();
	if(rows.length > maxHits){
		rows.length = maxHits;
		truncated = true;
	}
	done = total;
	report();
	return { intervals: rows, truncated, stats: { samples: total, evalCount, spanDays: total } };
}

// 单日判读(结果行「详情」):t='YYYY-MM-DD'(或含时刻,截日)。
export function explainHuangliAt({ tree, t }){
	const w = parseDateStr(datePartOf(`${t || ''}`.trim()));
	if(!w){
		return { t: `${t || ''}`, tree: null, err: 'invalid_time' };
	}
	let day;
	try{
		day = buildHuangliDay(w.y, w.m, w.d);
	}catch(e){
		return { t: ymdText(w), tree: null, err: 'no_day' };
	}
	return { t: ymdText(w), tree: evaluateHuangliTree(tree, day, null, true), badge: dayBadge(day) };
}
