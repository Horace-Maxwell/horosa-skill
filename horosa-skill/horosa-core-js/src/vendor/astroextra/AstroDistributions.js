// components/astro/AstroDistributions.js
// 界推运（Distributions）：发放点随周日运动顺黄道依次经过其后各界 → 分配星(界主)期 + 伙伴星期。后端 /predict/dist。
// 界表随「设置→星盘设置」的全局界系;发放点 / 时间算法 / 年长 / 年限四项口径见 utils/distributionsOptions(各处共用同一份)。
import { civilInstantMsOfStr } from '../bazi/dateStrSafe.js';




// headless stub：AstroExtraCommon 是页面公共件（antd 表格 / 卡片样式 / 请求键 / 加载停车位），纯逻辑段只在
// 「请求型」包装（buildXxxSnapshotText 内 fetch 后端、xxxRequestBody 拼请求体）里用到 unwrapResult / chartParams。
// skill 的请求在 Python 侧发（AGENTS §4.2：JS 层不发 HTTP），这两条路径不可达——调到即抛明确错误，不留空 stub。
const headlessUnreachable = (name) => () => { throw new Error(`headless: AstroExtraCommon.${name} 不可达（请求在 Python 侧发，见 service/runners/predictive.py）`); };
const unwrapResult = headlessUnreachable('unwrapResult');
const chartParams = headlessUnreachable('chartParams');
import * as AstroText from '../../constants/AstroText.js';



import {
	DIST_RELEASERS, DIST_METHODS, DIST_YEARS, DIST_SPANS,
	normalizeDistSettings, distRequestParams, distSettingsLine, distReleaserLabel, partnerAspectText,
} from '../utils/distributionsOptions.js';
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

import { silentTechniquePanelsEnabled } from '../utils/perfFlags.js';


const birthHeaderLines = (c) => (typeof astroAiSnapshot.buildPredictiveBirthHeaderLines === 'function' ? astroAiSnapshot.buildPredictiveBirthHeaderLines(c) : []);
const currentMomentLines = (c, x) => (typeof astroAiSnapshot.buildCurrentMomentLines === 'function' ? astroAiSnapshot.buildCurrentMomentLines(c, x) : []);
const methodNoteLines = (k) => (typeof astroAiSnapshot.buildMethodNoteLines === 'function' ? astroAiSnapshot.buildMethodNoteLines(k) : []);

// AI 快照用中文名(astroSymbol 的字形在纯文本里不可读)。
function distName(id){
	if(id === undefined || id === null || id === ''){ return '-'; }
	return AstroText.AstroTxtMsg[id] || `${id}`;
}
const fmtYears = (v) => (Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '-');
const partnerTxt = (p) => `${distName(p.planet)}${partnerAspectText(p.aspect, p.side)}`;

// 请求体 = 本盘排盘参数 + 与出厂值不同的界推运口径(出厂值不带,请求与旧版逐字节相同)
export function distributionsRequestBody(chartObj, opts){
	return { ...chartParams(chartObj), ...distRequestParams(opts) };
}

// 时刻落在哪一行:起止日期可解析且含该时刻才算(防日期格式变体误判)
function rowAt(rows, ms){
	return (rows || []).find((row)=>{
		const s = civilInstantMsOfStr(`${row.startDate || ''}`.replace(/\//g, '-'));
		const e = civilInstantMsOfStr(`${row.endDate || ''}`.replace(/\//g, '-'));
		return Number.isFinite(s) && Number.isFinite(e) && ms >= s && ms < e;
	});
}

// 界推运 AI 快照(无头):内部 fetch /predict/dist,与组件同口径。aiAnalysisContext 复算用。
export async function buildDistributionsSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	let r = {};
	try{
		// WP-C 极速化:无头快照复算也走 silent,不触发全局满屏 Spin 压暗(失败经外层 catch 回 '')。
		const data = await request(`${Constants.ServerRoot}/predict/dist`, {
			body: JSON.stringify(distributionsRequestBody(chartObj, opts)),
			timeoutMs: 60000,
			silent: silentTechniquePanelsEnabled(),
		});
		r = unwrapResult(data) || {};
	}catch(e){
		return '';
	}
	return buildDistributionsSnapshotFromResult(chartObj, r, opts);
}

// 由后端结果拼快照(页面已取到结果时直接用,不再请求)
export function buildDistributionsSnapshotFromResult(chartObj, r, opts){
	const rows = (r && r.dist) || [];
	if(!rows.length){ return ''; }  // 无界推运数据=该技法在本盘缺失,挂载显示「缺失」而非空表头。
	const partners = (r && r.distPartners) || [];
	const st = normalizeDistSettings({ ...(opts || {}), ...((r && r.distSettings) || {}) });
	const releaserLon = r && r.distSettings && Number.isFinite(Number(r.distSettings.releaserLon)) ? `（黄经 ${Number(r.distSettings.releaserLon).toFixed(2)}°）` : '';
	const lines = [];
	// [YB] 头部盘主生辰([起盘信息];无数据 helper 自返 [],不产空段头)。
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[界推运（分配法 / Distributions）]');
	lines.push(`发放点随周日运动顺黄道依次经过其后各界（界表用当前全局界系设置）。${distSettingsLine(st)}${releaserLon}。分配星 = 所在界的界主；伙伴星 = 发放点最近经过的行星本体或相位点（左右 60° / 90° / 120° 与 180°），各管到下一点为止。`);
	lines.push('');
	lines.push('| 分配星 | 界(座) | 起始岁 | 时长(年) | 起 | 止 | 期内伙伴星 |');
	lines.push('| --- | --- | --- | --- | --- | --- | --- |');
	rows.forEach((row)=>{
		const detail = Array.isArray(row.partnerDetail) && row.partnerDetail.length ? row.partnerDetail.map(partnerTxt).join('、')
			: ((row.participants && row.participants.length) ? row.participants.map(distName).join('、') : '—');
		lines.push(`| ${distName(row.distributor)} | ${distName(row.sign)} | ${fmtYears(row.startYears)} | ${fmtYears(row.years)} | ${row.startDate || '-'} | ${row.endDate || '-'} | ${detail} |`);
	});
	if(partners.length){
		lines.push('');
		lines.push('[伙伴星期]');
		lines.push('| 伙伴星 | 相位点 | 起始岁 | 时长(年) | 起 | 止 |');
		lines.push('| --- | --- | --- | --- | --- | --- |');
		partners.forEach((p)=>{
			lines.push(`| ${distName(p.planet)} | ${partnerAspectText(p.aspect, p.side)}（${Number(p.lon).toFixed(2)}°） | ${fmtYears(p.startYears)} | ${fmtYears(p.years)} | ${p.startDate || '-'} | ${p.endDate || '-'} |`);
		});
	}
	// [YB] 尾部 [当前时点]+[方法说明];定位行=今日所在分配期 / 伙伴期。
	const extraLines = [];
	const nowMs = Date.now();
	const curRow = rowAt(rows, nowMs);
	if(curRow){
		extraLines.push(`当前分配星：${distName(curRow.distributor)}（${distName(curRow.sign)} 界，${curRow.startDate || '-'} ~ ${curRow.endDate || '-'}）`);
	}
	const curP = rowAt(partners, nowMs);
	if(curP){
		extraLines.push(`当前伙伴星：${partnerTxt(curP)}（${curP.startDate || '-'} ~ ${curP.endDate || '-'}）`);
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('distributions')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}
