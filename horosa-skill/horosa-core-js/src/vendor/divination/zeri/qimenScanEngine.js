// [奇门择日] 找局扫描引擎(纯前端,零 HTTP)。
// 供数链与 dunjiaBackendParity.test.js 同范式:buildLocalNongliLite(轻量 nongli,跳过三推运
// ≈97% 成本) + calcDunJia(纯函数本地排盘;时家定局本地↔后端有 42,731 点 0 差 parity 锚背书)。
// 候选生成 = 时间范围内逐小时采样(60 分步长,时家每时辰≥1 样)+ 相邻样本状态不同时对过渡段
// 做「递归转变分解」到分钟(中点与两端都不同 = 发现第三盘,两半各自递归)——
// 🔴 绝不解析式硬推时辰边界:真太阳时(timeAlg=0)时辰边界随经度/均时差漂移、晚子时
//   (after23NewDay=0)把子时截成两盘、置闰/拆补在至点时刻可在同一时辰内翻局
//   (2015-12-22 冬至 12:48 案例),采样+递归分解对这些天然正确,连「至界翻局与时辰边界
//   同落一小时产生的不足一小时过渡盘」也能自动成行(T2② 金标钉死)。
//   唯一物理盲区 = 两端状态相同的中间毛刺,时辰轮转不回头,不存在此形态。
// 🔴 不做「按四柱 memo 求值」:同四柱不保证同盘(至界分钟级翻局),每样本直算
//   (lite+calc 约 2-4ms,月窗≈2s;上限窗见 QIMEN_MAX_SPAN_DAYS_TOTAL)。
import { calcDunJia } from '../../dunjia/DunJiaCalc.js';
import { buildLocalNongliLite } from '../../bazi/baziLunarLocal.js';
import { buildLocalJieqiYearSeed } from '../../../shared/localNongliAdapter.js';
import { QIMEN_CONDITION_TYPES, makeQimenEvalCtx } from './qimenConditionTypes.js';

// 上限对齐天星(scanOrchestrator):命中 1000 条截断、总跨度 ≤1830 天(约 5 年)。
export const QIMEN_MAX_TOTAL_HITS = 1000;
export const QIMEN_MAX_SPAN_DAYS_TOTAL = 1830;
const STEP_MS = 3600e3;
const MINUTE_MS = 60e3;
const CHUNK_SAMPLES = 96;

function pad2(n){
	return n < 10 ? `0${n}` : `${n}`;
}
// zone 兼容 fields.zone 的两种历史形态:数值小时(8/8.5/-3)与字符串('+08:00'/'8')。
export function qimenZoneOffsetMinutes(zone){
	if(typeof zone === 'number' && Number.isFinite(zone)){
		return Math.round(zone * 60);
	}
	const text = `${zone === undefined || zone === null ? '' : zone}`.trim();
	if(!text){
		return 480;
	}
	const m = /^([+-]?)(\d{1,2})(?::?(\d{2}))?$/.exec(text);
	if(!m){
		return 480;
	}
	const sign = m[1] === '-' ? -1 : 1;
	return sign * (Number(m[2]) * 60 + Number(m[3] || 0));
}
function wallToMs(dateStr, timeStr, offsetMin){
	const dp = `${dateStr || ''}`.split('-').map(Number);
	const tp = `${timeStr || '00:00'}`.split(':').map(Number);
	if(dp.length < 3 || dp.some((n)=>!Number.isFinite(n))){
		return NaN;
	}
	// setUTCFullYear 绕开 Date.UTC 对 0-99 年的 1900+ 历史映射(仓内铁律,见 baziLunarLocal)。
	const d = new Date(0);
	d.setUTCFullYear(dp[0], dp[1] - 1, dp[2]);
	d.setUTCHours(tp[0] || 0, tp[1] || 0, tp[2] || 0, 0);
	return d.getTime() - offsetMin * MINUTE_MS;
}
function msToWall(ms, offsetMin){
	const d = new Date(ms + offsetMin * MINUTE_MS);
	return {
		y: d.getUTCFullYear(), mo: d.getUTCMonth() + 1, dd: d.getUTCDate(),
		hh: d.getUTCHours(), mm: d.getUTCMinutes(),
	};
}
function wallDateStr(w){
	return `${w.y}-${pad2(w.mo)}-${pad2(w.dd)}`;
}
function wallTimeStr(w){
	return `${pad2(w.hh)}:${pad2(w.mm)}:00`;
}
function wallText(w){
	return `${wallDateStr(w)} ${pad2(w.hh)}:${pad2(w.mm)}`;
}

// 盘面身份键:局 + 值符值使 + 九宫全要素(含特殊标记)。同 plateKey ⇒ 条件求值面完全同盘;
// 行折叠按它切分 —— 时家逐时辰自然分行,日/月/年家在盘不变的连续命中时辰自动并为一行。
function plateKeyOf(pan){
	const cells = (pan && pan.cells ? pan.cells : []).map((c)=>[
		c.palaceNum, c.diGan || '', c.tianGan || '', c.door || '', c.tianXing || '', c.god || '',
		c.hasJiXing ? 1 : 0, c.hasRuMu ? 1 : 0, c.hasMenPo ? 1 : 0, c.hasKongWang ? 1 : 0,
		c.isYiMa ? 1 : 0, c.isZhiFu ? 1 : 0, c.isZhiShi ? 1 : 0,
	].join('')).join('|');
	return `${pan ? pan.juText : ''}#${pan ? pan.zhiFu : ''}#${pan ? pan.zhiShi : ''}#${cells}`;
}

// ── 条件树求值(树形状 = compileQimenTree 产物:组{type:all/any/not/xor,conditions[]}/叶{type,params}) ──
// explain=true 时返回判读树:组{kind:'group',op,pass,children}/叶{kind:'leaf',type,pass,actual},
// 叶序与 UI 树 DFS 先序一致(compile 不增删叶),工作台「设定 vs 实际」按此对位。
export function evaluateQimenTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeQimenEvalCtx(pan);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateQimenTree(child, pan, evalCtx, explain));
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
	const spec = node ? QIMEN_CONDITION_TYPES[node.type] : null;
	if(!spec){
		return explain ? { kind: 'leaf', type: node ? node.type : '?', pass: false, actual: '未知条件类型' } : { pass: false };
	}
	let verdict;
	try{
		verdict = spec.evaluate(pan, node.params || {}, evalCtx) || { pass: false, actual: '' };
	}catch(e){
		verdict = { pass: false, actual: `求值异常:${e && e.message ? e.message : e}` };
	}
	return explain ? { kind: 'leaf', type: node.type, pass: !!verdict.pass, actual: verdict.actual || '' } : { pass: !!verdict.pass };
}

// 单时刻起盘(geoParams = DunJiaMain.genParams 形状去掉 date/time;options = 22 参数盘面选项)。
export function computeQimenScanPan(geoParams, options, jieqiYearSeeds, dateStr, timeStr){
	const params = {
		...geoParams,
		date: dateStr,
		time: timeStr,
		gender: geoParams && geoParams.gender !== undefined ? geoParams.gender : 1,
		timeAlg: options && options.timeAlg !== undefined ? options.timeAlg : 0,
		after23NewDay: options && options.after23NewDay !== undefined ? options.after23NewDay : 1,
		lateZiHourUseNextDay: options && options.lateZiHourUseNextDay !== undefined ? options.lateZiHourUseNextDay : 1,
	};
	const lite = buildLocalNongliLite(params);
	const nongli = { ...lite.bazi.nongli, bazi: lite.bazi };
	const fields = {
		date: { value: { format: ()=>dateStr } },
		time: { value: { format: ()=>timeStr } },
		zone: { value: params.zone },
	};
	return calcDunJia(fields, nongli, options, { jieqiYearSeeds });
}

export function buildQimenScanSeeds(startYear, endYear, zone){
	const seeds = {};
	for(let y = startYear - 1; y <= endYear + 1; y++){
		try{
			seeds[y] = buildLocalJieqiYearSeed(y, zone);
		}catch(e){
			// 种子域外(如 lunar 可靠域边缘)按缺省处理,calcDunJia 自身有回退语义
		}
	}
	return seeds;
}

function abortError(){
	const err = new Error('qimen scan aborted');
	err.name = 'AbortError';
	return err;
}
function rangeError(code, detail){
	const err = new Error(detail || code);
	err.code = code;
	return err;
}

// 主入口。cfg: { startDate,startTime,endDate,endTime };geoParams: { zone,lon,lat,gpsLon,gpsLat,ad,gender };
// options: 盘面 22 参数;tree: compileQimenTree 产物;onProgress({done,total,hits,partial});signal: AbortSignal;
// limits.maxHits 仅供测试注入,生产恒默认 QIMEN_MAX_TOTAL_HITS。
export async function scanQimen({ cfg, geoParams, options, tree, onProgress, signal, limits }){
	const offsetMin = qimenZoneOffsetMinutes(geoParams && geoParams.zone);
	const t0 = wallToMs(cfg && cfg.startDate, (cfg && cfg.startTime) || '00:00', offsetMin);
	const t1 = wallToMs(cfg && cfg.endDate, (cfg && cfg.endTime) || '23:59', offsetMin);
	if(!Number.isFinite(t0) || !Number.isFinite(t1) || !(t1 > t0)){
		throw rangeError('invalid_range', '时间范围无效:结束须晚于起始');
	}
	const spanDays = (t1 - t0) / 86400e3;
	if(spanDays > QIMEN_MAX_SPAN_DAYS_TOTAL){
		throw rangeError('span_too_large', `跨度 ${Math.ceil(spanDays)} 天超上限 ${QIMEN_MAX_SPAN_DAYS_TOTAL} 天`);
	}
	const w0 = msToWall(t0, offsetMin);
	const w1 = msToWall(t1, offsetMin);
	const seeds = buildQimenScanSeeds(w0.y, w1.y, geoParams && geoParams.zone);
	const maxHits = (limits && Number(limits.maxHits) > 0) ? Number(limits.maxHits) : QIMEN_MAX_TOTAL_HITS;
	// 采样点:t0 起逐小时,尾段不足一小时时恒补 t1 终点样本(把最后一段也钉到分钟语义)。
	const alignedCount = Math.floor((t1 - t0) / STEP_MS) + 1;
	const lastAligned = t0 + (alignedCount - 1) * STEP_MS;
	const total = alignedCount + (lastAligned < t1 ? 1 : 0);
	let evalCount = 0;

	const recAt = (ms)=>{
		const w = msToWall(ms, offsetMin);
		const pan = computeQimenScanPan(geoParams, options, seeds, wallDateStr(w), wallTimeStr(w));
		evalCount++;
		if(!pan){
			return { pass: false, plateKey: '', juText: '' };
		}
		const verdict = evaluateQimenTree(tree, pan, null, false);
		return { pass: !!verdict.pass, plateKey: plateKeyOf(pan), juText: pan.juText || '' };
	};
	const sameRec = (a, b)=>a.pass === b.pass && a.plateKey === b.plateKey;
	// 把状态不同的相邻样本 (tA,tB] 递归切成分钟级恒定段边界(升序 push 进 out):
	// 中点与两端都不同 = 第三盘在场(至界翻局+时辰边界同小时),两半各自递归。
	const resolveTransition = (tA, recA, tB, recB, out)=>{
		if(sameRec(recA, recB)){
			return;
		}
		if(tB - tA <= MINUTE_MS){
			out.push({ ms: tB, rec: recB });
			return;
		}
		const mid = tA + Math.floor((tB - tA) / 2 / MINUTE_MS) * MINUTE_MS;
		if(mid <= tA || mid >= tB){
			out.push({ ms: tB, rec: recB });
			return;
		}
		const recM = recAt(mid);
		resolveTransition(tA, recA, mid, recM, out);
		resolveTransition(mid, recM, tB, recB, out);
	};

	const rows = [];
	let truncated = false;
	let cur = null;
	const makeRow = (startMs, endMsRaw, juText)=>{
		const endMs = Math.min(endMsRaw, t1);
		const sw = msToWall(startMs, offsetMin);
		const ew = msToWall(endMs, offsetMin);
		// 起盘安全时刻:两端各向内缩 1 分钟(天星 ε 同理)。边界分钟是本引擎判定的翻转瞬间,
		// 而主盘显示管线的真太阳时实现与本地 EoT 存在亚分钟差 —— 恰在边界分钟起盘可能落
		// 界外侧出上一时辰盘(真机实抓:03:09 边界 pick 被显示管线判成 02:59 丑时)。
		const pickMs = Math.min(startMs + MINUTE_MS, Math.max(startMs, endMs - MINUTE_MS));
		const pickW = msToWall(pickMs, offsetMin);
		const pickEndMs = Math.max(endMs - 2 * MINUTE_MS, startMs);
		const pw = msToWall(pickEndMs, offsetMin);
		return {
			start: wallText(sw),
			end: wallText(ew),
			pick: `${wallDateStr(pickW)} ${wallTimeStr(pickW)}`,
			pickEnd: `${wallDateStr(pw)} ${wallTimeStr(pw)}`,
			startMs,
			endMs,
			durationMin: Math.round((endMs - startMs) / MINUTE_MS),
			juText,
		};
	};
	const closeAt = (ms)=>{
		if(!cur){
			return;
		}
		if(ms > cur.startMs){
			rows.push(makeRow(cur.startMs, ms, cur.juText));
		}
		cur = null;
	};
	// 流式喂入分钟级状态段:同盘连续命中并行,变盘/失配即在边界分钟切行。
	const feed = (ms, rec)=>{
		if(rec.pass){
			if(!cur || cur.plateKey !== rec.plateKey){
				closeAt(ms);
				cur = { startMs: ms, plateKey: rec.plateKey, juText: rec.juText };
			}
		}else{
			closeAt(ms);
		}
	};

	let done = 0;
	const report = ()=>{
		if(typeof onProgress === 'function'){
			try{
				onProgress({ done, total, hits: rows.length, partial: rows.slice() });
			}catch(e){
				// 进度回调异常不阻断扫描
			}
		}
	};
	let prevMs = null;
	let prevRec = null;
	for(let i = 0; i < total; i++){
		if(signal && signal.aborted){
			throw abortError();
		}
		const ms = i < alignedCount ? t0 + i * STEP_MS : t1;
		const rec = recAt(ms);
		if(!prevRec){
			feed(ms, rec);
		}else if(!sameRec(prevRec, rec)){
			const boundaries = [];
			resolveTransition(prevMs, prevRec, ms, rec, boundaries);
			for(let b = 0; b < boundaries.length; b++){
				feed(boundaries[b].ms, boundaries[b].rec);
			}
		}
		prevMs = ms;
		prevRec = rec;
		if(rows.length >= maxHits){
			truncated = true;
			cur = null;
			break;
		}
		done = i + 1;
		if((i + 1) % CHUNK_SAMPLES === 0){
			report();
			// 让出主线程,保持 UI 可交互/可取消
			await new Promise((resolve)=>setTimeout(resolve, 0));
		}
	}
	closeAt(t1);
	if(rows.length > maxHits){
		rows.length = maxHits;
		truncated = true;
	}
	done = total;
	report();
	return {
		intervals: rows,
		truncated,
		stats: { samples: total, evalCount, spanDays: Math.round(spanDays * 100) / 100 },
	};
}

// 单时刻判读(工作台结果行「详情」):t = 'YYYY-MM-DD HH:mm(:ss)' 墙钟文本(找局快照口径)。
export function explainQimenAt({ geoParams, options, tree, t, jieqiYearSeeds }){
	const text = `${t || ''}`.trim().replace('T', ' ');
	const m = /^(\d{1,4})-(\d{2})-(\d{2})[ ](\d{2}):(\d{2})/.exec(text);
	if(!m){
		return { t: text, tree: null, err: 'invalid_time' };
	}
	const dateStr = `${m[1]}-${m[2]}-${m[3]}`;
	const timeStr = `${m[4]}:${m[5]}:00`;
	const year = Number(m[1]);
	const seeds = jieqiYearSeeds || buildQimenScanSeeds(year, year, geoParams && geoParams.zone);
	const pan = computeQimenScanPan(geoParams, options, seeds, dateStr, timeStr);
	if(!pan){
		return { t: text, tree: null, err: 'no_pan' };
	}
	return { t: text, tree: evaluateQimenTree(tree, pan, null, true), juText: pan.juText || '' };
}
