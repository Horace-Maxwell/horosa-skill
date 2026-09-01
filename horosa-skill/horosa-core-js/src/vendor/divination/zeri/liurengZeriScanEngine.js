// [Z5·六壬择日] 逐时辰扫描引擎(纯前端零 HTTP)——hourlyScanEngine 外壳第六实例。
// 供数链:buildLrChartLite(liurengLocal:四柱 lite+月将两档+日出方程昼夜+神煞机械同源表)
// +主六壬页同一排盘函数族(buildLiuRengLayout/buildKeData/buildSanChuanData——涉害
// byte-perfect 三传核 ChuangChart 在内;主排盘修正,择日自动跟,零第二实现)。
// 🔴 与主页供数的三个差异窗(帮助分册明示):①月将换将时刻(lunar-js 中气 vs 后端星历,
// 分钟级) ②昼夜界(几何日出方程 vs 星历地平判,折射 2-3 分钟窗) ③四柱=bazi golden 满防。
// 起课法:扫描恒正时正将(第一客);贵人流派 guirengType/昼夜法/阴阳系全参数可调。
// plateKey=判定输入元组(日柱|时支|月将|昼夜|贵人流派有效参),同元组⇒同盘。
import { buildLiuRengLayout, buildKeData, buildSanChuanData } from '../../liureng/LiuRengMain.js';
import { buildLrChartLite } from './liurengLocal.js';
import { LIURENG_CONDITION_TYPES, makeLiurengZeriEvalCtx } from './liurengZeriConditionTypes.js';
import { makeHourlyScanEngine } from './hourlyScanEngine.js';

export const LIURENG_MAX_TOTAL_HITS = 1000;
export const LIURENG_MAX_SPAN_DAYS_TOTAL = 1830;

// 单时刻起课:lite 供数→主页 layout/ke/三传 同函数(月将/昼夜经 castOverride 旁路注入)。
export function computeLiurengScanPan(geoParams, options, dateStr, timeStr){
	const o = options || {};
	const base = buildLrChartLite(geoParams, o, dateStr, timeStr);
	if(!base){ return null; }
	const guirengType = o.guirengType !== undefined ? Number(o.guirengType) : 0;
	const castOverride = {
		yue: base.yue,
		isDiurnal: base.diurnal,
		yinyangSystem: o.yinyangSystem || undefined,
		seHaiOpts: o.seHaiOpts || null,
	};
	const layout = buildLiuRengLayout(base.chartLite, guirengType, castOverride);
	if(!layout){ return null; }
	const ke = buildKeData(layout, base.chartLite);
	if(!ke || !ke.raw){ return null; }
	const sanChuan = buildSanChuanData(layout, ke.raw, base.chartLite, castOverride);
	if(!sanChuan){ return null; }
	return {
		layout, ke, sanChuan,
		lrGods: base.lrGods,
		xun: base.xun,
		fourColumns: base.fourColumns,
		yue: base.yue,
		diurnal: base.diurnal,
		// [W2 全谱轮] 小局/大格判定面装配材料:chartLite(nongli 载体;无星历 objects——
		// 涉日月宿位的少数局在扫描侧无供数不判,注册表 hint 明示)+castOverride+guirengType。
		chartLite: base.chartLite,
		castOverride,
		guirengType,
	};
}

export function evaluateLiurengTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeLiurengZeriEvalCtx(pan);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateLiurengTree(child, pan, evalCtx, explain));
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
	const spec = node ? LIURENG_CONDITION_TYPES[node.type] : null;
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

// plateKey=起课输入元组:日柱+时支+月将(基础三位,全类恒吃)+可掩四位(昼夜/年支/月支/
// 候选公历年)。[十一轮] 依赖感知掩码:mask 存在时可掩位只保留树声明位——树不涉贵人则
// key 略 diurnal 位,日出日落不再假劈行(用户实报 1.6h/24分 非整行根修);涉则保留,
// 按昼夜盘分行=语义正确。mask 缺省(null)=全位(三式旧调用/压测 kit/兜底零回归)。
// 🔴 年支/月支必须可入 key:taisui_god_at 吃年支环、天德/月德/月破吃月支——立春/各节
// 翻转分钟若 key 不变,外壳 sameRec 恒真不做递归分解,一行折叠横跨节气(审查实抓)。
// 🔴 candY=候选公历年(bm 两类行年 ctx.xingnian 的输入,1/1 00:00 子时中段翻)——
// 十一轮补的历史漏位(此前跨年扫描 bm 行年翻转不分行)。
export const LIURENG_MASKABLE_KEY_BITS = ['diurnal', 'yearZhi', 'monthZhi', 'candY'];
export function plateKeyOf(pan, mask){
	const fc = pan.fourColumns || {};
	const day = (fc.day || {}).ganzi || (fc.day || {}).ganZhi || '';
	const time = (fc.time || {}).ganzi || (fc.time || {}).ganZhi || '';
	const on = (bit)=>!mask || !!mask[bit];
	const yearZhi = on('yearZhi') ? ((fc.year || {}).ganzi || (fc.year || {}).ganZhi || '').charAt(1) : '';
	const monthZhi = on('monthZhi') ? ((fc.month || {}).ganzi || (fc.month || {}).ganZhi || '').charAt(1) : '';
	const diurnal = on('diurnal') ? (pan.diurnal ? 'D' : 'N') : '';
	const candY = on('candY') ? `${pan._candY || ''}` : '';
	return [day, time.charAt(1), pan.yue, diurnal, yearZhi, monthZhi, candY].join('#');
}

// 树 → 掩码:DFS 收集叶类型的 keyDeps ∪;未知类型(已删类兜底)=全位(保守)。
export function liurengKeyMaskOf(tree){
	const mask = { diurnal: false, yearZhi: false, monthZhi: false, candY: false };
	const allOn = ()=>{ LIURENG_MASKABLE_KEY_BITS.forEach((b)=>{ mask[b] = true; }); };
	const walk = (node)=>{
		if(!node){ return; }
		if(Array.isArray(node.conditions)){ node.conditions.forEach(walk); return; }
		const spec = LIURENG_CONDITION_TYPES[node.type];
		if(!spec || !Array.isArray(spec.keyDeps)){ allOn(); return; }
		spec.keyDeps.forEach((b)=>{ if(b in mask){ mask[b] = true; } });
	};
	walk(tree);
	return mask;
}
function rowExtras(pan){
	const c = (pan.sanChuan && pan.sanChuan.cuang) || [];
	return {
		keText: (pan.sanChuan && pan.sanChuan.name) || '',
		chuanText: c.join('→'),
	};
}

const engine = makeHourlyScanEngine({
	name: 'liureng',
	makeScanCtx: (args)=>{
		const natal = args && args.options && args.options._natal;
		return { natal: natal || null };
	},
	computePanAt: (scanCtx, geoParams, options, dateStr, timeStr)=>{
		const o = { ...(options || {}) };
		delete o._natal;
		const pan = computeLiurengScanPan(geoParams, o, dateStr, timeStr);
		if(pan && scanCtx && scanCtx.natal){ pan._natal = scanCtx.natal; }
		// 候选公历年:行年支按候选年现算的输入(ctx.xingnian();系统年冻结=跨年错位实抓)
		if(pan){ pan._candY = Number(`${dateStr}`.slice(0, 4)); }
		return pan;
	},
	plateKeyOf,
	keyMaskOf: ({ tree })=>liurengKeyMaskOf(tree),
	evaluateTree: (tree, pan, explain)=>evaluateLiurengTree(tree, pan, null, explain),
	rowExtras,
	maxHits: LIURENG_MAX_TOTAL_HITS,
	maxSpanDays: LIURENG_MAX_SPAN_DAYS_TOTAL,
});

export function scanLiureng(args){
	return engine.scan(args);
}
export function explainLiurengAt({ geoParams, options, tree, t }){
	return engine.explainAt({ geoParams, options, tree, t });
}

// [Z6] 三式合一拼接 plateKey 消费(同源别名;三家同名 plateKeyOf 避免 import 冲突)。
export { plateKeyOf as liurengPlateKeyOf };
