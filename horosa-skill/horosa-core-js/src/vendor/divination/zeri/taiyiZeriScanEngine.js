// [Z3·太乙择日] 逐时辰扫描引擎(纯前端零 HTTP)——hourlyScanEngine 外壳第三实例。
// 供数链:buildLocalNongliLite + liteToTaiyiNongli 适配(lite 的 nongli 键形与生产
// fetchPreciseNongli 不同构:year=中文年非干支、无 monthGanZi/dayGanZi——parity 首跑实抓
// 计神合神恒空+阴阳遁误判,适配后五锚判定面对齐) + calcTaiyi(太乙页同一本地引擎,
// TaiYiCore 706 行纯 JS;与后端 kentang 的 parity 由 taiyiLocalParity 五锚金标看守)。
// 🔴 style 恒 3(时计太乙):命法档(5)按生辰非候选时刻,不是择日扫描对象(定谳);
//   tn(古法公式)/tenching/rotation/晚子时档全参数可调(与太乙页同枚举)。
// plateKey=白名单(Z0 裁定:applyNongliDisplay 挂 clockTime/realSunTime 逐分钟回显字段,
// hash 整 pan=逐分钟成行爆炸)——只取 16 宫布局+局+三算+诸神落宫。
import { buildLocalNongliLite } from '../../bazi/baziLunarLocal.js';
import { calcTaiyi } from '../../taiyi/TaiYiCalc.js';
import { buildPalaceMarks } from '../../taiyi/core/TaiYiCore.js';
import { applyTaiyiSchool } from '../../taiyi/core/taiyiSchool.js';
import { TAIYI_CONDITION_TYPES, makeTaiyiZeriEvalCtx } from './taiyiZeriConditionTypes.js';
import { makeHourlyScanEngine } from './hourlyScanEngine.js';

export const TAIYI_MAX_TOTAL_HITS = 1000;
export const TAIYI_MAX_SPAN_DAYS_TOTAL = 1830;

// lite → 太乙引擎 nongli 形(生产 fetchPreciseNongli 同构面;键谱=TaiYiCore buildGanZhi/
// getAccNum/extractCurrentJieqi 的消费集)。
export function liteToTaiyiNongli(lite){
	if(!lite || !lite.bazi){
		return null;
	}
	const fc = lite.bazi.fourColumns || {};
	const nl = lite.bazi.nongli || {};
	const gz = (k)=>(fc[k] && (fc[k].ganzi || fc[k].ganZhi)) || '';
	return {
		year: gz('year'),
		yearJieqi: gz('year'),	// 四柱年柱=立春界干支(太岁/计神链)
		monthGanZi: gz('month'),
		dayGanZi: gz('day'),
		time: gz('time'),
		monthInt: nl.monthNum,
		dayInt: nl.dayNum,
		jieqi: nl.jieqi,
		jiedelta: nl.jiedelta,	// 阴阳遁按节气切(冬夏至界)——lunar-js 全 24 气在此
		birth: nl.birth || '',
	};
}

// 单时刻起盘:pan=calcTaiyi 产物(applyTaiyiSchool 过流派六轴——与太乙页同链)。
export function computeTaiyiScanPan(geoParams, options, dateStr, timeStr){
	const o = options || {};
	const lite = buildLocalNongliLite({
		...geoParams,
		date: dateStr,
		time: timeStr,
		gender: 1,
		timeAlg: 1,	// 太乙时基:direct=钟表时(trueSolar 档见下 timeBasis 说明)。[十三轮跨链核]后端 kentang 太乙同为钟表口径——taiyiLocalParity 六锚「判定面逐键==后端」恒绿即制度证据(口径若分叉,任意锚时刻必红);两链无 EoT 面,无骑线窗。
		after23NewDay: o.after23NewDay !== undefined ? o.after23NewDay : 0,
		lateZiHourUseNextDay: o.lateZiHourUseNextDay !== undefined ? o.lateZiHourUseNextDay : 1,
	});
	const nongli = liteToTaiyiNongli(lite);
	if(!nongli){
		return null;
	}
	const fields = {
		date: { value: { format: ()=>dateStr } },
		time: { value: { format: ()=>timeStr } },
		zone: { value: (geoParams && geoParams.zone) || '+08:00' },
	};
	const pan = calcTaiyi(fields, nongli, {
		style: 3,	// 恒时计(定谳)
		tn: o.tn !== undefined ? o.tn : 0,
		sex: '男',
		tenching: o.tenching !== undefined ? o.tenching : 0,
		rotation: o.rotation || '固定',
		timeBasis: 'direct',	// 扫描恒钟表时(真太阳时档=后端星历,本地无;pick 起盘后页面按其设置显示)
		after23NewDay: o.after23NewDay !== undefined ? o.after23NewDay : 0,
		lateZiHourUseNextDay: o.lateZiHourUseNextDay !== undefined ? o.lateZiHourUseNextDay : 1,
		gameTheory: 0,
	});
	if(!pan){
		return null;
	}
	// applyTaiyiSchool 返回 {pan, overrides, geoSuan} 包(非裸 pan——首跑实抓 {} 空盘);
	// 默认流派原样透传。
	let out = pan;
	try{
		const applied = applyTaiyiSchool(pan, o.school || {});
		out = (applied && applied.pan) ? applied.pan : pan;
	}catch(e){
		out = pan;
	}
	// 🔴 阴遁太乙落宫「后端对齐补丁」(parity 三锚实抓):本地 TaiYiCore num2gong 为「秘书归正」
	// 版(阴阳同映射),后端 kentang 沿旧表(阴遁=归正版**对宫**,三阴遁锚 2↔午/子、8↔子/午 全证)。
	// 用户 pick 后太乙页显示走后端 → 扫描判定必须与用户所见一致,故此处按后端口径覆写;
	// 「归正是否同步后端」待用户拍板,拍板归正后删本补丁(taiyiLocalParity 锚会咬住)。
	try{
		const yy = out.kook && (out.kook.yinYang || ((out.kook.text || '').indexOf('阴') >= 0 || (out.kook.text || '').indexOf('陰') >= 0 ? '阴' : '阳'));
		if(yy === '阴' && out.taiyiPalace){
			const GONG16_RING = ['子', '丑', '艮', '寅', '卯', '辰', '巽', '巳', '午', '未', '坤', '申', '酉', '戌', '乾', '亥'];
			const i = GONG16_RING.indexOf(out.taiyiPalace);
			if(i >= 0){
				out = { ...out, taiyiPalace: GONG16_RING[(i + 8) % 16] };
				// 🔴 翻宫后必须重建布神三表(buildPalaceMarks 同源重跑,键名照 TaiYiCore 挂法):
				// 曾只翻 taiyiPalace 一键,布神表仍标旧宫 → gong16_has「午含太乙」与
				// taiyi_gong「太乙落午」同引擎互斥,且与 pick 后太乙页所见相反(审查实抓)。
				const mk = buildPalaceMarks(out);
				out = { ...out, palaceMarks: mk.marks, palace16: mk.palace16, branch12: mk.branch12 };
			}
		}
	}catch(e){ /* 补丁失败保原盘 */ }
	return out;
}

export function evaluateTaiyiTree(node, pan, ctx, explain){
	const evalCtx = ctx || makeTaiyiZeriEvalCtx(pan);
	if(node && Array.isArray(node.conditions)){
		const children = node.conditions.map((child)=>evaluateTaiyiTree(child, pan, evalCtx, explain));
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
	const spec = node ? TAIYI_CONDITION_TYPES[node.type] : null;
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

// plateKey 白名单:局+太乙落宫+文昌始击+三算+大小将+计合神+16 宫序列(诸神布点)。
// 🔴 绝不 hash 整 pan(clockTime/realSunTime 逐分钟变=行爆炸,Z0 裁定)。
export function plateKeyOf(pan){
	const p16 = (pan.palace16 || pan.palaces || []).map((c)=>`${c.palace || ''}:${(c.items || []).map((it)=>it.name || it).join(',')}`).join('|');
	return [
		pan.kook && pan.kook.text,
		pan.taiyiPalace, pan.taiyiNum, pan.skyeyes, pan.sf,
		pan.homeCal, pan.awayCal, pan.setCal,
		pan.homeGeneral, pan.awayGeneral, pan.jigod, pan.hegod, pan.wufuNum,
		// W0 预审补键:youshen_gong 读 bigyoNum/smyoNum 而 key 原缺(仅靠 p16 布神串间接盖,
		// 36h 窗内恰不翻转即漏分行);W1 新类判定面(将/参将/诸算派生)同批显式入 key。
		pan.bigyoNum, pan.smyoNum, pan.setGeneral, pan.homeVGen, pan.awayVGen, pan.setVGen,
		p16,
	].join('#');
}
function rowExtras(pan){
	return { juText: (pan.kook && pan.kook.text) || '', taiyiText: `太乙${pan.taiyiPalace || '?'}宫` };
}

const engine = makeHourlyScanEngine({
	name: 'taiyi',
	makeScanCtx: ()=>null,
	computePanAt: (scanCtx, geoParams, options, dateStr, timeStr)=>computeTaiyiScanPan(geoParams, options, dateStr, timeStr),
	plateKeyOf,
	evaluateTree: (tree, pan, explain)=>evaluateTaiyiTree(tree, pan, null, explain),
	rowExtras,
	maxHits: TAIYI_MAX_TOTAL_HITS,
	maxSpanDays: TAIYI_MAX_SPAN_DAYS_TOTAL,
});

export function scanTaiyi(args){
	return engine.scan(args);
}
export function explainTaiyiAt({ geoParams, options, tree, t }){
	return engine.explainAt({ geoParams, options, tree, t });
}

// [Z6] 三式合一拼接 plateKey 消费(同源别名;三家同名 plateKeyOf 避免 import 冲突)。
export { plateKeyOf as taiyiPlateKeyOf };
