// 推运图族四子页:演进推运(Néroman)/ 推运图(Bezza)/ 周日小限(Jay)/ 双黄道(Michon)。
// 计算在后端 /astroextra/<接口>(astrostudy/directed_figures.py);口径、名称与 AI 快照正文单源在 utils/directedFigures。
// 版式与主限法盘同一个(progPageLayout):左边整列是盘(双黄道是回归 / 恒星双环图),右栏固定头(标题行 →「时间选择」紧凑时间块 →「设置」)
// + 只在卡内滚动的表格卡片。
// 改任何设置自动重算,旧结果留着(角标「更新中…」);取不到结果时盘位显示原因,并每隔十几秒自动重试。







// headless stub：AstroExtraCommon 是页面公共件；纯逻辑段只在请求型包装 fetchDirectedFigure 里用 unwrapResult / chartParams。
// skill 的请求在 Python 侧发（AGENTS §4.2：JS 层不发 HTTP），这条路径不可达——调到即抛明确错误，不留空 stub。
const headlessUnreachable = (name) => () => { throw new Error(`headless: AstroExtraCommon.${name} 不可达（请求在 Python 侧发，见 service/runners/predictive.py）`); };
const unwrapResult = headlessUnreachable('unwrapResult');
const chartParams = headlessUnreachable('chartParams');



// headless stub：today / chartZone 只服务 buildDirectedFigureSnapshotText 的「目标时刻缺省 = 本盘时区今日」——skill 由
// Python 侧按同一口径（_today_for_chart(zone)）先定好 targetDate 再发请求，这条路径不可达。
const headlessUnreachableProg = (name) => () => { throw new Error(`headless: astroProgSnapshot.${name} 不可达（目标时刻在 Python 侧定）`); };
const today = headlessUnreachableProg('today');
const chartZone = headlessUnreachableProg('chartZone');

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
// headless stub：星阙页面保存值（localStorage）在 headless 下不存在 = 全新安装：load() 返回空记录，各口径回落
// directedFigures.js 的 *_DEFAULTS（directedFigureRequestFields 的 num(…, DEFAULTS) 兜底），与页面首装同值。
const DIRECTION_PAGE_SETTINGS = { load: () => ({}) };

import {
	DIRECTED_FIGURES, NEROMAN_EQUATOR_OPTIONS, BEZZA_KIND_LABELS, BEZZA_MUNDANE_ASPECTS, ZODIAC_ASPECT_LABELS, MICHON_FAMILY_LABELS,
	directedFigureRequestFields, buildDirectedFigureText, pointName, fmtLon, fmtN,
} from '../utils/directedFigures.js';


const safeHelperLines = (fn, ...args)=>(typeof fn === 'function' ? fn(...args) : []);

// 页面保存值 → 各技法设置(挂载齿轮同名字段,见 techniqueMountSettings)
export function directedFigureOptsFromSettings(key, sv){
	const s = sv || DIRECTION_PAGE_SETTINGS.load();
	if(key === 'neroman'){ return { k: s.nerK, t0: s.nerT0, keepDec: s.nerKeepDec, orb: s.nerOrb }; }
	if(key === 'bezzafigure'){ return { orb: s.bezzaOrb }; }
	if(key === 'jayprofection'){ return { from: s.jayFrom }; }
	if(key === 'michon'){ return { orb: s.michonOrb, swap: s.michonSwap, equal: s.michonEqual }; }
	return {};
}

// 返回 null = 网络层失败(request 吞错时 resolve undefined),调用方保留旧结果
async function fetchDirectedFigure(key, chartObj, targetDate, targetTime, opts, silent){
	const def = DIRECTED_FIGURES[key];
	const data = await request(`${Constants.ServerRoot}${def.endpoint}`, {
		body: JSON.stringify({ ...chartParams(chartObj), targetDate, targetTime, ...directedFigureRequestFields(key, opts) }),
		timeoutMs: 45000,
		...(silent ? { silent: true } : null),
	});
	return data ? (unwrapResult(data) || {}) : null;
}

export function snapshotText(key, chartObj, result){
	const body = buildDirectedFigureText(key, result);
	if(!body){ return ''; }
	const lines = [];
	lines.push(...safeHelperLines(astroAiSnapshot.buildPredictiveBirthHeaderLines, chartObj));
	lines.push(body);
	lines.push('');
	lines.push(...safeHelperLines(astroAiSnapshot.buildCurrentMomentLines, chartObj));
	lines.push(...safeHelperLines(astroAiSnapshot.buildMethodNoteLines, key));
	while(lines.length && lines[lines.length - 1] === ''){ lines.pop(); }
	return lines.join('\n');
}

// AI 快照(无头):挂载重算 / 导出用。opts = 挂载齿轮设置(缺省 = 页面保存值);targetDate / targetTime 缺省 = 本盘时区今日 12:00。
export async function buildDirectedFigureSnapshotText(key, chartObj, opts){
	if(!chartObj || !DIRECTED_FIGURES[key]){ return ''; }
	const o = opts && typeof opts === 'object' ? opts : {};
	const base = directedFigureOptsFromSettings(key);
	const merged = { ...base };
	Object.keys(o).forEach((k)=>{ if(o[k] !== undefined && o[k] !== null && o[k] !== ''){ merged[k] = o[k]; } });
	const targetDate = `${o.targetDate || ''}`.trim() || today(chartZone(chartObj));
	const targetTime = `${o.targetTime || ''}`.trim() || '12:00:00';
	try{
		const result = await fetchDirectedFigure(key, chartObj, targetDate, targetTime, merged);
		return snapshotText(key, chartObj, result);
	}catch(e){
		return '';
	}
}
