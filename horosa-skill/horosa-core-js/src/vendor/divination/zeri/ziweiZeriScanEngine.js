// 逐时辰扫描引擎(纯前端零 HTTP)——hourlyScanEngine 外壳第四实例。
// 供数链:calcZiweiFromLite(与主紫微页 calcZiwei 同一 buildChartFromBazi 组装体——
// 全量核 91ms/盘重头在百年大运推演,lite 0.13ms/盘实测,判定面 20 时刻 deep-equal 全等)。
// 🔴 口径三键默认=Java 兼容档(yearBoundary:lunar_1_1/ziweiLunarBasis:calendar/
// lifeMasterBy:year_branch,ZIWEI_JAVA_COMPAT 同源常量):主紫微页默认档显示 Java 盘即此
// 口径,pick 后所见=扫描所判;用户在主页拨引擎键后主页走本地(lichun 界),届时工作台
// 同枚举可调对齐(帮助分册明示)。
// plateKey=输入元组(年干支|紫微月|闰|紫微日|时支|三盘锚):安星 13 步由此完全决定
// (Z0 裁定;「同 key⇒chart deep-equal」不变量由金标钉)。
import { calcZiweiFromLite, deriveSanPan } from '../../ziwei/ZiweiCalc.js';
import { ZIWEI_PAGE_SCAN_KEYS } from './zeriPageCalibre.js';
import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../../bazi/dayBoundary.js';
import { ZIWEI_CONDITION_TYPES, makeZiweiZeriEvalCtx } from './ziweiZeriConditionTypes.js';
import { makeHourlyScanEngine } from './hourlyScanEngine.js';

export const ZIWEI_MAX_TOTAL_HITS = 1000;
export const ZIWEI_MAX_SPAN_DAYS_TOTAL = 1830;

// Java 兼容口径三键(与 ziweiLocalParity.ZIWEI_JAVA_COMPAT_OPTS 语义同——那边在测试文件,
// 生产侧此处为单源;金标断言两处逐键相等防漂移)。
export const ZIWEI_ZERI_DEFAULT_COMPAT = Object.freeze({
	yearBoundary: 'lunar_1_1',
	ziweiLunarBasis: 'calendar',
	lifeMasterBy: 'year_branch',
});

// 扫描起盘参数(单一来源):扫描判定(calcZiweiFromLite)与概览浮窗显示(calcZiwei 全量)都经它构参,
// 两边同一张盘(浮窗不许另拼一份 calcZiwei 参数 —— 曾在浮窗写死「子初换日」,全局 24 点换日时 23 点那行浮窗与扫描不同盘)。
export function ziweiScanCalcArgs(geoParams, options, dateStr, timeStr){
	const o = options || {};
	const birth = {
		date: dateStr, time: timeStr,
		zone: (geoParams && geoParams.zone) || '+08:00',
		// lon 回落 gpsLon:applyApparentSolarTime 只认 lon 键,缺失=真太阳时静默不生效(金标实抓)
		lon: geoParams && (geoParams.lon !== undefined ? geoParams.lon : geoParams.gpsLon),
		lat: geoParams && (geoParams.lat !== undefined ? geoParams.lat : geoParams.gpsLat),
		gpsLon: geoParams && geoParams.gpsLon, gpsLat: geoParams && geoParams.gpsLat,
		ad: 1,
		gender: o.gender !== undefined ? o.gender : 1,
	};
	const opts = {
		...ZIWEI_ZERI_DEFAULT_COMPAT,
		timeAlg: o.timeAlg !== undefined ? o.timeAlg : 1,	// 扫描默认钟表时(候选时刻域)
		// 晚子时缺省「跟随全局」(= 主紫微页缺省):日界 / 晚子时两键显式取全局现值 —— 不给就吃 undefined
		// (after23=不进位≈子正换日,与工作台显示漂移,自查实抓)。全局为出厂值时与旧缺省「子初换日」逐盘相同
		lateZi: o.lateZi !== undefined ? o.lateZi : 'global',
		...o,
	};
	delete opts.gender;
	if(opts.lateZi === 'dual'){ opts.lateZi = 'global'; }	// 双盘=本命人工比对场景,扫描恒单方案
	if(opts.lateZi === 'global'){
		if(opts.after23NewDay === undefined){ opts.after23NewDay = defaultAfter23NewDay(); }
		if(opts.lateZiHourUseNextDay === undefined){ opts.lateZiHourUseNextDay = defaultLateZiHourUseNextDay(); }
	}
	return { birth, opts };
}

// 内嵌紫微页当前的排盘口径(扫描读页面):引擎键照页面;安星农历按页面同一规则由晚子时推得(页面不单设这一项)
export function ziweiPageScanOptions(engine){
	const g = engine && typeof engine === 'object' ? engine : {};
	const out = {};
	ZIWEI_PAGE_SCAN_KEYS.forEach((k)=>{ if(g[k] !== undefined && g[k] !== null && `${g[k]}` !== ''){ out[k] = Array.isArray(g[k]) ? [...g[k]] : g[k]; } });
	out.ziweiLunarBasis = (!out.lateZi || out.lateZi === 'global') ? 'calendar' : 'ziwei';
	return out;
}

// 紫微设置(本机偏好全键,utils/ziweiRecordSettings.currentZiweiSettings 的形状)→ 引擎单例同形(小限顺逆的偏好键名不同)。
// 无头 / AI 择日没有内嵌页可读单例时,经它取「你的紫微设置」,与紫微页读偏好同源
export function ziweiEngineFromSettings(settings){
	const s = settings && typeof settings === 'object' ? settings : {};
	return { ...s, xiaoxianMode: s.ziweiXiaoxianYinyang !== undefined ? s.ziweiXiaoxianYinyang : s.xiaoxianMode };
}

// 三盘(地盘 / 人盘)与页面同一后处理(deriveSanPan):扫描判定、概览浮窗、点开的盘同一张
export function ziweiScanChartOf(chart, opts){
	const o = opts || {};
	return (chart && o.sanPan && o.sanPan !== 'tian') ? deriveSanPan(chart, o.sanPan) : chart;
}

export function computeZiweiScanPan(geoParams, options, dateStr, timeStr){
	const { birth, opts } = ziweiScanCalcArgs(geoParams, options, dateStr, timeStr);
	try{
		return ziweiScanChartOf(calcZiweiFromLite(birth, opts), opts);
	}catch(e){
		return null;	// lunar 域外等:该样本判否(hourlyScanEngine 对 null 盘跳过)
	}
}

export function evaluateZiweiTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeZiweiZeriEvalCtx(pan, (pan && pan._natal) || null);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateZiweiTree(child, pan, evalCtx, explain));
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
	const spec = node ? ZIWEI_CONDITION_TYPES[node.type] : null;
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

// plateKey=安星输入元组(同元组⇒同盘,金标不变量钉):年干支+紫微口径农历月/闰/日+时支。
// 🔴 勿 hash 整 chart(nongli.clockTime 等逐分钟字段;houses 大对象串接浪费)。
// 位级掩码:六位全可掩——年干四化树(sihua_star)→ key 仅 yearGan,行=整年粒度。
export const ZIWEI_KEY_BITS = ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'];
export function plateKeyOf(pan, mask){
	// 🔴 用安星实际锚 anchorMD(buildChartFromBazi 挂):直读 nl.ziweiDayNum 在 calendar
	// 基准+晚子时窗与判定面不同构(23 点段错误折叠,行内同盘探针实抓)。
	const a = pan.anchorMD || {};
	const on = (bit)=>!mask || !!mask[bit];
	return [
		on('yearGan') ? pan.yearGan : '',
		on('yearZi') ? pan.yearZi : '',
		on('anchorM') ? a.m : '',
		on('anchorLeap') ? (a.leap ? 1 : 0) : '',
		on('anchorD') ? a.d : '',
		on('timeZi') ? pan.timeZi : '',
	].join('#');
}

export function ziweiKeyMaskOf(tree){
	const mask = { yearGan: false, yearZi: false, anchorM: false, anchorLeap: false, anchorD: false, timeZi: false };
	const allOn = ()=>{ ZIWEI_KEY_BITS.forEach((b)=>{ mask[b] = true; }); };
	const walk = (node)=>{
		if(!node){ return; }
		if(Array.isArray(node.conditions)){ node.conditions.forEach(walk); return; }
		const spec = ZIWEI_CONDITION_TYPES[node.type];
		if(!spec || !Array.isArray(spec.keyDeps)){ allOn(); return; }
		spec.keyDeps.forEach((b)=>{ if(b in mask){ mask[b] = true; } });
	};
	walk(tree);
	return mask;
}
// 徽章面 ⊆ 掩码后 key 面:年干四化树(无 timeZi 位)行跨时辰,命宫/局在行内变
// → 徽章改显年干四化(行内恒定);全位树徽章不变。
function rowExtras(pan, mask){
	const ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
	if(mask && !mask.timeZi && !mask.anchorD){
		const sh = pan.birthSihua || {};
		const sihuaText = ['禄', '权', '科', '忌'].map((k)=>`${k}${(sh[k] && sh[k].star) || sh[k] || '?'}`).join(' ');
		return { mingText: `${pan.yearGan || '?'}年四化`, juText: sihuaText };
	}
	const mains = ((pan.houses && pan.houses[pan.lifeHouseIndex]) || {}).starsMain || [];
	return {
		mingText: `命宫${ZHI12[pan.lifeHouseIndex] || '?'}·${mains.length ? mains.map((s)=>s.name).join('') : '空宫'}`,
		juText: pan.wuxingJuText || '',
	};
}

const engine = makeHourlyScanEngine({
	name: 'ziwei',
	makeScanCtx: (args)=>{
		const natal = args && args.options && args.options._natal;
		return { natal: natal || null };
	},
	computePanAt: (scanCtx, geoParams, options, dateStr, timeStr)=>{
		const o = { ...(options || {}) };
		delete o._natal;
		const pan = computeZiweiScanPan(geoParams, o, dateStr, timeStr);
		if(pan && scanCtx && scanCtx.natal){ pan._natal = scanCtx.natal; }
		return pan;
	},
	plateKeyOf,
	keyMaskOf: ({ tree })=>ziweiKeyMaskOf(tree),
	evaluateTree: (tree, pan, explain)=>evaluateZiweiTree(tree, pan, null, explain),
	rowExtras,
	maxHits: ZIWEI_MAX_TOTAL_HITS,
	maxSpanDays: ZIWEI_MAX_SPAN_DAYS_TOTAL,
});

export function scanZiwei(args){
	return engine.scan(args);
}
export function explainZiweiAt({ geoParams, options, tree, t }){
	return engine.explainAt({ geoParams, options, tree, t });
}

// [压测] 行内同盘探针消费(zeriStressKit;别名防跨技法 import 冲突)。
export { plateKeyOf as ziweiPlateKeyOf };
