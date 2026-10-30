// components/astro/AstroAgePoint.js
// 年龄推进点（Age Point）：年龄点自上升点起逐宫顺行，每宫 6 年、72 年一周。
// 推进方式(Koch 宫 / 等速 5°/年)、事件(全部点 × 五相位 / 只报合七星)、年长、年限四项口径见 utils/agePointOptions(各处共用同一份)。
// 报每岁落座 / 落宫与事件精确岁数。后端 /predict/agepoint。
import { civilInstantMsOfStr } from '../bazi/dateStrSafe.js';




// headless stub：AstroExtraCommon 是页面公共件（antd 表格 / 卡片样式 / 请求键 / 加载停车位），纯逻辑段只在
// 「请求型」包装（buildXxxSnapshotText 内 fetch 后端、xxxRequestBody 拼请求体）里用到 unwrapResult / chartParams。
// skill 的请求在 Python 侧发（AGENTS §4.2：JS 层不发 HTTP），这两条路径不可达——调到即抛明确错误，不留空 stub。
const headlessUnreachable = (name) => () => { throw new Error(`headless: AstroExtraCommon.${name} 不可达（请求在 Python 侧发，见 service/runners/predictive.py）`); };
const unwrapResult = headlessUnreachable('unwrapResult');
const chartParams = headlessUnreachable('chartParams');
import * as AstroText from '../../constants/AstroText.js';



import { AP_METHODS, AP_EVENTS, AP_YEARS, AP_SPANS, normalizeApSettings, apRequestParams, apSettingsLine, apAspectText } from '../utils/agePointOptions.js';
// [YB] 三段补厚共享 helper(起盘信息/当前时点/方法说明)。namespace import + typeof 守卫:
// 测试环境可能部分 mock astroAiSnapshot(只留 buildAstroSnapshotContent 等),缺函数时回 [] 保底。
// headless stub：上游 [YB] 三段补厚用它产 [起盘信息]/[当前时点]/[方法说明]，但 skill 的 Python 层
// 已经产这三段（_predictive_setup_section_text / _predictive_common_sections_text），再让 JS 产一遍会重段。
// 上游每个调用点都写了 typeof …==='function' 守卫：未定义的 helper 回退 []（不产段）。唯一例外是
// buildCurrentMomentLines——它收下 builder 自算的 [当前时点] 定位行（extraLines，如「当前主限」），交给
// tools/progextra.js 回传 Python 追加进 [当前时点]（= 上游 buildCurrentMomentLines(chartObj, extraLines)），自身仍返 []。
const astroAiSnapshot = {
	buildCurrentMomentLines: (chartObj, extraLines) => {
		globalThis.__horosaProgMomentLines = Array.isArray(extraLines) ? extraLines.filter(Boolean).map((l) => `${l}`) : [];
		return [];
	},
};


const birthHeaderLines = (c) => (typeof astroAiSnapshot.buildPredictiveBirthHeaderLines === 'function' ? astroAiSnapshot.buildPredictiveBirthHeaderLines(c) : []);
const currentMomentLines = (c, x) => (typeof astroAiSnapshot.buildCurrentMomentLines === 'function' ? astroAiSnapshot.buildCurrentMomentLines(c, x) : []);
const methodNoteLines = (k) => (typeof astroAiSnapshot.buildMethodNoteLines === 'function' ? astroAiSnapshot.buildMethodNoteLines(k) : []);

// AI 快照用中文名(astroSymbol 字形在纯文本里不可读)。
function apName(id){
	if(id === undefined || id === null || id === ''){ return '-'; }
	return AstroText.AstroTxtMsg[id] || `${id}`;
}

// 一行内多个事件:后端 points[i].aspects=[{aspectTo,aspectAge,aspectType,side}](精确穿越岁数);旧字段 aspectTo 仅首个 → 兼容回退。
function rowAspects(p){
	if(!p){ return []; }
	if(Array.isArray(p.aspects) && p.aspects.length){ return p.aspects; }
	return p.aspectTo ? [{ aspectTo: p.aspectTo, aspectAge: p.aspectAge, aspectType: 0, side: '' }] : [];
}

// 事件全集:后端 crossings(按岁升序,精确岁数);旧后端无此字段 → 由 points 行的 aspects 拼出。
function keyCrossings(ap, points){
	if(ap && Array.isArray(ap.crossings) && ap.crossings.length){ return ap.crossings; }
	const out = [];
	(points || []).forEach((p)=>{ rowAspects(p).forEach((a)=>out.push({ age: Number.isFinite(Number(a.aspectAge)) ? Number(a.aspectAge) : p.age, aspectTo: a.aspectTo, aspect: a.aspectType || 0, side: a.side || '' })); });
	return out;
}

function fmtAge(v){
	const n = Number(v);
	if(!Number.isFinite(n)){ return `${v}`; }
	return Number.isInteger(n) ? `${n}` : n.toFixed(2).replace(/\.?0+$/, '');
}
const eventTxt = (c) => `${apAspectText(c.aspect !== undefined ? c.aspect : c.aspectType, c.side)}${apName(c.aspectTo)}`;

// 请求体 = 本盘排盘参数 + 与出厂值不同的年龄推进点口径(出厂值不带,请求与旧版逐字节相同)
export function agePointRequestBody(chartObj, opts){
	return { ...chartParams(chartObj), ...apRequestParams(opts) };
}

// 年龄推进点 AI 快照(无头):内部 fetch /predict/agepoint,与组件同口径。aiAnalysisContext 复算用。
export async function buildAgePointSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	let r = {};
	try{
		const data = await request(`${Constants.ServerRoot}/predict/agepoint`, {
			body: JSON.stringify(agePointRequestBody(chartObj, opts)),
			timeoutMs: 60000,
		});
		r = unwrapResult(data) || {};
	}catch(e){
		return '';
	}
	return buildAgePointSnapshotFromResult(chartObj, r, opts);
}

export function buildAgePointSnapshotFromResult(chartObj, r, opts){
	const ap = (r && r.agepoint) || {};
	const points = ap.points || [];
	if(!points.length){ return ''; }  // 无年龄推进点数据=该技法在本盘缺失,挂载显示「缺失」而非空表头。
	const crossings = keyCrossings(ap, points);
	const st = normalizeApSettings({ ...(opts || {}), ...(ap.settings || {}) });
	const lines = [];
	// [YB] 头部盘主生辰([起盘信息];无数据 helper 自返 [],不产空段头)。
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[年龄推进点（Age Point / Huber）]');
	lines.push(`年龄点自上升点起逐宫顺行，每宫 6 年、72 年回到上升。${apSettingsLine(st)}。年龄点经过本命点或其相位点的岁数为人生关键节点。`);
	if(crossings.length){
		lines.push('');
		lines.push('关键岁数（精确穿越岁数）：' + crossings.map((c) => `${fmtAge(c.age)}岁${eventTxt(c)}${c.date ? `(${c.date})` : ''}`).join('；'));
	}
	lines.push('');
	lines.push('| 年龄 | 日期 | 落座 | 宫 | 事件（穿越岁数） |');
	lines.push('| --- | --- | --- | --- | --- |');
	points.forEach((p)=>{
		const sign = `${apName(p.sign)}${(p.signlon !== undefined && p.signlon !== null) ? ' ' + p.signlon + '°' : ''}`;
		const asp = rowAspects(p).map((a) => `${eventTxt(a)}${Number.isFinite(Number(a.aspectAge)) ? `(${fmtAge(a.aspectAge)}岁)` : ''}`).join('、');
		lines.push(`| ${p.age}岁 | ${p.date || '-'} | ${sign} | ${p.house}宫 | ${asp || '—'} |`);
	});
	// [YB] 尾部 [当前时点]+[方法说明];定位行=当前年龄对应的年龄点行(取 age≤当前年龄的最大行)。
	const extraLines = [];
	const birthRaw = (chartObj && chartObj.params && chartObj.params.birth) ? `${chartObj.params.birth}`.trim() : '';
	const birthMs = birthRaw ? civilInstantMsOfStr(birthRaw.replace(/\//g, '-').replace(' ', 'T')) : NaN;   // 民用历真实时刻(1582 以前 / 公元前)
	if(Number.isFinite(birthMs)){
		const curAge = (Date.now() - birthMs) / (365.2425 * 24 * 3600 * 1000);
		let curPoint = null;
		points.forEach((p)=>{
			if(Number(p.age) <= curAge && (!curPoint || Number(p.age) > Number(curPoint.age))){ curPoint = p; }
		});
		if(curPoint){
			const curSign = `${apName(curPoint.sign)}${(curPoint.signlon !== undefined && curPoint.signlon !== null) ? ' ' + curPoint.signlon + '°' : ''}`;
			const curAsp = rowAspects(curPoint).map((a) => `${eventTxt(a)}${Number.isFinite(Number(a.aspectAge)) ? `(${fmtAge(a.aspectAge)}岁)` : ''}`).join('、');
			extraLines.push(`当前年龄点：${curPoint.age}岁 落${curSign}，第${curPoint.house}宫${curAsp ? `，${curAsp}` : ''}`);
		}
		const next = crossings.find((c) => Number(c.age) > curAge);
		if(next){ extraLines.push(`下一事件：${fmtAge(next.age)}岁${eventTxt(next)}${next.date ? `（${next.date}）` : ''}`); }
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('agepoint')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}
