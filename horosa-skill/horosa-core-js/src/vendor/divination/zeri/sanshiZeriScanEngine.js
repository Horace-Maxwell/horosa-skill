// [Z6·三式择日] 逐时辰扫描引擎(纯前端零 HTTP)——hourlyScanEngine 外壳第七实例。
// 每样本起三盘(定案2):六壬(Z5 本地链)+奇门(Z0 外壳第一实例同函数)+太乙(Z3 本地链),
// 判定单源全数继承三家(零第二实现);options=merged 平铺形经 splitSanshiOptions 单源拆分。
// 某家起盘失败:样本不弃,该家条件全部判否+actual 注记(定案:勿静默吞);plateKey=三家
// 拼接 `L#..‖Q#..‖T#..`(任一家变盘即分行;失败家段为 FAIL 常量,保折叠正确性)。
import { computeLiurengScanPan, liurengPlateKeyOf, liurengKeyMaskOf } from './liurengZeriScanEngine.js';
import { computeQimenScanPan, qimenPlateKeyOf, qimenKeyMaskOf, buildQimenScanSeeds } from './qimenScanEngine.js';
import { computeTaiyiScanPan, taiyiPlateKeyOf } from './taiyiZeriScanEngine.js';
import { SANSHI_CONDITION_TYPES, makeSanshiZeriEvalCtx } from './sanshiZeriConditionTypes.js';
import { splitSanshiOptions } from './sanshiOptionSplit.js';
import { makeHourlyScanEngine } from './hourlyScanEngine.js';

export const SANSHI_MAX_TOTAL_HITS = 1000;
export const SANSHI_MAX_SPAN_DAYS_TOTAL = 1830;

// 单时刻三家起盘。scanCtx={seeds(奇门节气种子), natal(六壬本命)}。
export function computeSanshiScanPan(scanCtx, geoParams, options, dateStr, timeStr){
	const split = splitSanshiOptions(options);
	const out = { liureng: null, qimen: null, taiyi: null, _famFail: {} };
	try{
		out.liureng = computeLiurengScanPan(geoParams, split.liureng, dateStr, timeStr);
		if(!out.liureng){ out._famFail.liureng = '供数/排盘返回空'; }
	}catch(e){
		out._famFail.liureng = (e && e.message) || '异常';
	}
	try{
		out.qimen = computeQimenScanPan(geoParams, split.qimen, scanCtx && scanCtx.seeds, dateStr, timeStr);
		if(!out.qimen){ out._famFail.qimen = '供数/排盘返回空'; }
	}catch(e){
		out._famFail.qimen = (e && e.message) || '异常';
	}
	try{
		out.taiyi = computeTaiyiScanPan(geoParams, split.taiyi, dateStr, timeStr);
		if(!out.taiyi){ out._famFail.taiyi = '供数/排盘返回空'; }
	}catch(e){
		out._famFail.taiyi = (e && e.message) || '异常';
	}
	if(!out.liureng && !out.qimen && !out.taiyi){
		return null;	// 三家全失败=样本跳过(外壳契约)
	}
	if(scanCtx && scanCtx.natal && out.liureng){ out.liureng._natal = scanCtx.natal; }
	// 候选公历年:六壬家行年支按候选年现算(ctx.xingnian();独立六壬择日同修)
	if(out.liureng){ out.liureng._candY = Number(`${dateStr}`.slice(0, 4)); }
	return out;
}

export function evaluateSanshiTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeSanshiZeriEvalCtx(pan);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateSanshiTree(child, pan, evalCtx, explain));
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
	const spec = node ? SANSHI_CONDITION_TYPES[node.type] : null;
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

// plateKey=三家拼接(计划裁定;失败家=FAIL 段保折叠正确)。
// [十一轮] mask.lr/.qm=两家位级子掩码;[十四轮] mask.fams=家级掩码——树不涉之家整段
// 以 'SKIP' 占位不读盘(用户实报:六壬单叶树被太乙 19:00 钟表换局劈成 1.8h+15分,
// 徽章实证阴遁二十二→二十三局=真变盘但这棵树根本不判太乙)。未涉家不进判定,pass
// 边界不受影响;mask 缺省 null=三段全拼(压测 kit/旧调用零回归)。
export function plateKeyOf(pan, mask){
	const seg = (famPan, keyFn, m)=>(famPan ? keyFn(famPan, m) : 'FAIL');
	const m = mask || {};
	const fams = m.fams || { lr: true, qm: true, ty: true };
	const L = fams.lr ? seg(pan.liureng, liurengPlateKeyOf, m.lr || null) : 'SKIP';
	const Q = fams.qm ? seg(pan.qimen, qimenPlateKeyOf, m.qm || null) : 'SKIP';
	const T = fams.ty ? seg(pan.taiyi, taiyiPlateKeyOf) : 'SKIP';
	return `L${L}‖Q${Q}‖T${T}`;
}

// 三式树 → 家级+位级掩码:按前缀收集叶、剥前缀成各家树形喂同一 keyMaskOf(单源零第二
// 实现)。fams=树涉及哪些家(未知前缀/空树=三家全 true 保守兜底,与位级未知类型同律)。
export function sanshiKeyMaskOf(tree){
	const lrLeaves = [];
	const qmLeaves = [];
	let tyCount = 0;
	let unknown = 0;
	let leafCount = 0;
	const walk = (node)=>{
		if(!node){ return; }
		if(Array.isArray(node.conditions)){ node.conditions.forEach(walk); return; }
		leafCount++;
		const t = `${node.type || ''}`;
		if(t.indexOf('lr_') === 0){ lrLeaves.push({ type: t.slice(3), params: node.params }); }
		else if(t.indexOf('qm_') === 0){ qmLeaves.push({ type: t.slice(3), params: node.params }); }
		else if(t.indexOf('ty_') === 0){ tyCount++; }
		else{ unknown++; }
	};
	walk(tree);
	const allOn = unknown > 0 || leafCount === 0;
	return {
		lr: liurengKeyMaskOf({ type: 'all', conditions: lrLeaves }),
		qm: qimenKeyMaskOf({ type: 'all', conditions: qmLeaves }),
		fams: {
			lr: allOn || lrLeaves.length > 0,
			qm: allOn || qmLeaves.length > 0,
			ty: allOn || tyCount > 0,
		},
	};
}
// [十四轮] 徽章面 ⊆ 掩码后 key 面:未涉家不上徽章(合并行内该家值会变,钉行首=误导)。
function rowExtras(pan, mask){
	const fams = (mask && mask.fams) || { lr: true, qm: true, ty: true };
	const parts = [];
	if(fams.lr){ parts.push(pan.liureng && pan.liureng.sanChuan ? pan.liureng.sanChuan.name : '—'); }
	if(fams.qm){ parts.push(pan.qimen ? (pan.qimen.juText || '—') : '—'); }
	if(fams.ty){ parts.push(pan.taiyi && pan.taiyi.kook ? pan.taiyi.kook.text : '—'); }
	return { sanshiText: parts.join('·') };
}

const engine = makeHourlyScanEngine({
	name: 'sanshi',
	makeScanCtx: (args)=>{
		const { geoParams, w0, w1, options } = args || {};
		return {
			seeds: (w0 && w1) ? buildQimenScanSeeds(w0.y, w1.y, geoParams && geoParams.zone) : null,
			natal: (options && options._natal) || null,
		};
	},
	computePanAt: (scanCtx, geoParams, options, dateStr, timeStr)=>{
		const o = { ...(options || {}) };
		delete o._natal;
		return computeSanshiScanPan(scanCtx, geoParams, o, dateStr, timeStr);
	},
	plateKeyOf,
	keyMaskOf: ({ tree })=>sanshiKeyMaskOf(tree),
	evaluateTree: (tree, pan, explain)=>evaluateSanshiTree(tree, pan, null, explain),
	rowExtras,
	maxHits: SANSHI_MAX_TOTAL_HITS,
	maxSpanDays: SANSHI_MAX_SPAN_DAYS_TOTAL,
});

export function scanSanshi(args){
	return engine.scan(args);
}
export function explainSanshiAt({ geoParams, options, tree, t }){
	return engine.explainAt({ geoParams, options, tree, t });
}

// [压测] 行内同盘探针消费(zeriStressKit)。
export { plateKeyOf as sanshiPlateKeyOf };
