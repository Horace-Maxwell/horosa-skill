// [Z2·八字择日] 逐时辰扫描引擎(纯前端零 HTTP)——hourlyScanEngine 通用外壳**第二实例**
// (抽壳正确性的活体验证)。供数链与奇门同范式:buildLocalNongliLite(轻量四柱,跳三推运
// ≈97% 成本,微秒-低毫秒/样)——与八字主盘同一引擎同一口径(timeAlg 真太阳时/晚子时三方案/
// 节气换月全由它内部处理,主算法修正择日自动跟)。
// 翻盘输入(时辰/日界/节气月/立春年)全部单调不回头 → 递归转变分解安全(Z0 论证迁移)。
// plateKey=四柱串(条件可见判定面=四柱纯函数:神煞/长生/旬空/纳音全由四柱查表派生,
// 键含四柱即完备;phaseType/godKeyPos 等口径参数不随时刻变,不入 key)。
import { buildLocalNongliLite } from '../../bazi/baziLunarLocal.js';
import { BAZI_CONDITION_TYPES, makeBaziZeriEvalCtx } from './baziZeriConditionTypes.js';
import { makeHourlyScanEngine } from './hourlyScanEngine.js';

export const BAZI_MAX_TOTAL_HITS = 1000;
export const BAZI_MAX_SPAN_DAYS_TOTAL = 1830;

function normalizeGodKeyPos(v){
	if(v === '年' || v === '日' || v === '年日'){ return v; }
	if(v === 0 || v === '0'){ return '年日'; }
	if(v === 2 || v === '2'){ return '日'; }
	return '年';
}

// 单时刻起盘:pan={four,nongli,godKeyPos,phaseType}(条件 evaluate 的唯一输入面)。
export function computeBaziScanPan(geoParams, options, dateStr, timeStr){
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
	if(!lite || !lite.bazi || !lite.bazi.fourColumns){
		return null;
	}
	return {
		four: lite.bazi.fourColumns,
		nongli: lite.bazi.nongli,
		// 归一垫片:旧存方案曾存数值 0/1/2(死开关期),映射回 allowedBases 认的字符串档;
		// 0→'年日'(年日互查) 1→'年' 2→'日';缺省='年'(与 allowedBases 默认分支同义,零回归)。
		godKeyPos: normalizeGodKeyPos(options && options.godKeyPos),
		phaseType: options && options.phaseType,
	};
}

export function evaluateBaziTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeBaziZeriEvalCtx(pan, null);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateBaziTree(child, pan, evalCtx, explain));
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
	const spec = node ? BAZI_CONDITION_TYPES[node.type] : null;
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

// [十一轮实核锚] 四柱串盖全部条件判定面:jie_delta 翻转=节气瞬间=月柱同刻;农历日=日界
// =日柱同刻(00:00 档;23 点档朔窗 1h 知情例外见 conditionTypes lunar_date 注)。
// [十四轮] 位级掩码:四位全可掩——树只涉日柱(如「日柱=甲子」)→ key 仅 dayGz 位,
// 行=整日粒度而非被时柱劈成 12×2h(用户「树不涉之面不劈行」标准全家补全)。
export const BAZI_KEY_BITS = ['yearGz', 'monthGz', 'dayGz', 'timeGz'];
export function plateKeyOf(pan, mask){
	const g = (k)=>{
		const c = pan.four && pan.four[k];
		return (c && (c.ganzi || c.ganZhi)) || '?';
	};
	const on = (bit)=>!mask || !!mask[bit];
	return [
		on('yearGz') ? g('year') : '',
		on('monthGz') ? g('month') : '',
		on('dayGz') ? g('day') : '',
		on('timeGz') ? g('time') : '',
	].join('|');
}

// 树 → 位掩码:叶 keyDeps(数组或 (params)=>数组)∪;未知类型/异常=全位保守。
export function baziKeyMaskOf(tree){
	const mask = { yearGz: false, monthGz: false, dayGz: false, timeGz: false };
	const allOn = ()=>{ BAZI_KEY_BITS.forEach((b)=>{ mask[b] = true; }); };
	const walk = (node)=>{
		if(!node){ return; }
		if(Array.isArray(node.conditions)){ node.conditions.forEach(walk); return; }
		const spec = BAZI_CONDITION_TYPES[node.type];
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
// [十四轮] 徽章面 ⊆ 掩码后 key 面:只显涉及柱(树只涉日柱=合并行跨时辰,钉时柱=误导)。
function rowExtras(pan, mask){
	const g = (k)=>{
		const c = pan.four && pan.four[k];
		return (c && (c.ganzi || c.ganZhi)) || '';
	};
	const isFull = !mask || (mask.yearGz && mask.monthGz && mask.dayGz && mask.timeGz);
	if(isFull){
		return { pillarText: `${g('day')}日${g('time')}时` };	// 全位/无掩码=旧形态(视觉零回归)
	}
	const parts = [];
	if(mask.yearGz){ parts.push(`${g('year')}年`); }
	if(mask.monthGz){ parts.push(`${g('month')}月`); }
	if(mask.dayGz){ parts.push(`${g('day')}日`); }
	if(mask.timeGz){ parts.push(`${g('time')}时`); }
	return { pillarText: parts.join('') || `${g('day')}日${g('time')}时` };
}

// natal 经 makeScanCtx 冻结进扫描上下文(evaluate 经 ctx.natal 读;工作台侧算好传入)。
function makeEngine(){
	let natalRef = null;
	const engine = makeHourlyScanEngine({
		name: 'bazi',
		makeScanCtx: ({ options })=>{
			natalRef = options && options._natal ? options._natal : null;
			return { natal: natalRef };
		},
		computePanAt: (scanCtx, geoParams, options, dateStr, timeStr)=>computeBaziScanPan(geoParams, options, dateStr, timeStr),
		plateKeyOf,
		keyMaskOf: ({ tree })=>baziKeyMaskOf(tree),
		evaluateTree: (tree, pan, explain)=>evaluateBaziTree(tree, pan, makeBaziZeriEvalCtx(pan, natalRef), explain),
		rowExtras,
		maxHits: BAZI_MAX_TOTAL_HITS,
		maxSpanDays: BAZI_MAX_SPAN_DAYS_TOTAL,
	});
	return engine;
}
const engine = makeEngine();

// 主入口。cfg:{startDate,startTime,endDate,endTime};geoParams:{zone,lon,lat,gpsLon,gpsLat,ad};
// options:{timeAlg,after23NewDay,lateZiHourUseNextDay,godKeyPos,phaseType,_natal};tree:compile 产物。
export function scanBazi(args){
	return engine.scan(args);
}

export function explainBaziAt({ geoParams, options, tree, t }){
	return engine.explainAt({ geoParams, options, tree, t });
}

// [压测] 行内同盘探针消费(zeriStressKit;别名防跨技法 import 冲突)。
export { plateKeyOf as baziPlateKeyOf };
