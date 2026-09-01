// [奇门择日] 找局扫描引擎(纯前端,零 HTTP)。
// [Z0] 改为 hourlyScanEngine 通用外壳的**第一个实例**:外壳承载全部技法无关面(采样/递归
// 转变分解/行折叠/pick 内缩/CHUNK/Abort/上限防呆),本文件只留奇门四注入点+既有导出面
// (导出名与行为逐字节不变,由 qimenZeriStress 46 例+qimenScanEngine 10 例整套回归钉死)。
// 供数链与 dunjiaBackendParity.test.js 同范式:buildLocalNongliLite(轻量 nongli,跳过三推运
// ≈97% 成本) + calcDunJia(纯函数本地排盘;时家定局本地↔后端有 42,731 点 0 差 parity 锚背书)。
// 🔴 绝不解析式硬推时辰边界:真太阳时(timeAlg=0)时辰边界随经度/均时差漂移、晚子时
//   (after23NewDay=0)把子时截成两盘、置闰/拆补在至点时刻可在同一时辰内翻局
//   (2015-12-22 冬至 12:48 案例),采样+递归分解对这些天然正确(T2② 金标钉死)。
// 🔴 不做「按四柱 memo 求值」:同四柱不保证同盘(至界分钟级翻局),每样本直算
//   (lite+calc 约 2-4ms,月窗≈2s;上限窗见 QIMEN_MAX_SPAN_DAYS_TOTAL)。
import { calcDunJia } from '../../dunjia/DunJiaCalc.js';
import { buildLocalNongliLite } from '../../bazi/baziLunarLocal.js';
import { buildLocalJieqiYearSeed } from '../../../shared/localNongliAdapter.js';
import { QIMEN_CONDITION_TYPES, makeQimenEvalCtx } from './qimenConditionTypes.js';
import { makeHourlyScanEngine, zoneOffsetMinutes } from './hourlyScanEngine.js';

// 上限对齐天星(scanOrchestrator):命中 1000 条截断、总跨度 ≤1830 天(约 5 年)。
export const QIMEN_MAX_TOTAL_HITS = 1000;
export const QIMEN_MAX_SPAN_DAYS_TOTAL = 1830;

// zone 兼容(既有导出名保留;实现下沉外壳)。
export const qimenZoneOffsetMinutes = zoneOffsetMinutes;

// 盘面身份键:局 + 值符值使 + 九宫全要素(含特殊标记)= 基础位(全类恒吃)。同 plateKey ⇒
// 条件求值面完全同盘;行折叠按它切分 —— 时家逐时辰自然分行,日/月/年家在盘不变的连续
// 命中时辰自动并为一行。
// [十一轮实核] 旧注释「ganzhi 已在 plateKey」是错的(key 从未含四柱)——四柱派生面
// (xunShou/fuTou=日柱、allKong=各柱、anGan/anZhi=时柱干+时旬、wangShuai=月支五行、
// shenSha=四柱+昼夜)在日/月/年家盘「同 key 跨多时辰」时独立翻转=假合并实锤。修法=
// 依赖感知掩位(六壬同协议):树声明吃哪些柱位才把该柱入 key——默认树(不涉这些类)
// key 与旧全等=零回归,涉则按柱变分行=正确。可掩位:yearGz/monthGz/dayGz/timeGz/diurnal。
export const QIMEN_MASKABLE_KEY_BITS = ['yearGz', 'monthGz', 'dayGz', 'timeGz', 'diurnal'];
export function plateKeyOf(pan, mask){
	const cells = (pan && pan.cells ? pan.cells : []).map((c)=>[
		c.palaceNum, c.diGan || '', c.tianGan || '', c.door || '', c.tianXing || '', c.god || '',
		c.hasJiXing ? 1 : 0, c.hasRuMu ? 1 : 0, c.hasMenPo ? 1 : 0, c.hasKongWang ? 1 : 0,
		c.isYiMa ? 1 : 0, c.isZhiFu ? 1 : 0, c.isZhiShi ? 1 : 0,
	].join('')).join('|');
	const base = `${pan ? pan.juText : ''}#${pan ? pan.zhiFu : ''}#${pan ? pan.zhiShi : ''}#${cells}`;
	if(!mask){ return base; }
	const gz = (pan && pan.ganzhi) || {};
	const extra = [
		mask.yearGz ? (gz.year || '') : '',
		mask.monthGz ? (gz.month || '') : '',
		mask.dayGz ? (gz.day || '') : '',
		mask.timeGz ? (gz.time || '') : '',
		mask.diurnal ? (pan && pan.isDiurnal ? 'D' : 'N') : '',
	].join('#');
	return `${base}#${extra}`;
}

// 树 → 掩码:叶 keyDeps(数组或 (params)=>数组)∪;未知类型=全位(保守兜底)。
export function qimenKeyMaskOf(tree){
	const mask = { yearGz: false, monthGz: false, dayGz: false, timeGz: false, diurnal: false };
	const allOn = ()=>{ QIMEN_MASKABLE_KEY_BITS.forEach((b)=>{ mask[b] = true; }); };
	const walk = (node)=>{
		if(!node){ return; }
		if(Array.isArray(node.conditions)){ node.conditions.forEach(walk); return; }
		const spec = QIMEN_CONDITION_TYPES[node.type];
		if(!spec || spec.keyDeps === undefined){ allOn(); return; }
		let deps = spec.keyDeps;
		if(typeof deps === 'function'){
			try{ deps = deps(node.params || {}); }catch(e){ deps = null; }
		}
		if(!Array.isArray(deps)){ allOn(); return; }
		deps.forEach((b)=>{ if(b in mask){ mask[b] = true; } });
	};
	walk(tree);
	return mask;
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
	// [W3] showAllKong 恒开:kong_all 条件的四柱空亡供数(主页默认关只是显示层减负;
	// 扫描判定面需要,纯附加键零回归——ganzhi 已在 plateKey,allKong 是其确定派生)。
	return calcDunJia(fields, nongli, { ...options, showAllKong: true }, { jieqiYearSeeds });
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

// ── 外壳实例(四注入点) ──
const engine = makeHourlyScanEngine({
	name: 'qimen',
	makeScanCtx: ({ geoParams, w0, w1 })=>buildQimenScanSeeds(w0.y, w1.y, geoParams && geoParams.zone),
	computePanAt: (seeds, geoParams, options, dateStr, timeStr)=>computeQimenScanPan(geoParams, options, seeds, dateStr, timeStr),
	plateKeyOf,
	keyMaskOf: ({ tree })=>qimenKeyMaskOf(tree),
	evaluateTree: (tree, pan, explain)=>evaluateQimenTree(tree, pan, null, explain),
	rowExtras: (pan)=>({ juText: (pan && pan.juText) || '' }),
	maxHits: QIMEN_MAX_TOTAL_HITS,
	maxSpanDays: QIMEN_MAX_SPAN_DAYS_TOTAL,
});

// 主入口。cfg: { startDate,startTime,endDate,endTime };geoParams: { zone,lon,lat,gpsLon,gpsLat,ad,gender };
// options: 盘面 22 参数;tree: compileQimenTree 产物;onProgress({done,total,hits,partial});signal: AbortSignal;
// limits.maxHits 仅供测试注入,生产恒默认 QIMEN_MAX_TOTAL_HITS。
export function scanQimen(args){
	return engine.scan(args);
}

// 单时刻判读(工作台结果行「详情」):t = 'YYYY-MM-DD HH:mm(:ss)' 墙钟文本(找局快照口径)。
// 返回形状兼容旧版:{ t, tree, juText }(juText 经 rowExtras 并入)。
export function explainQimenAt({ geoParams, options, tree, t, jieqiYearSeeds }){
	return engine.explainAt({ geoParams, options, tree, t, scanCtx: jieqiYearSeeds || null });
}

// [Z6] 三式合一拼接 plateKey 消费(同源别名;三家同名 plateKeyOf 避免 import 冲突)。
export { plateKeyOf as qimenPlateKeyOf };
