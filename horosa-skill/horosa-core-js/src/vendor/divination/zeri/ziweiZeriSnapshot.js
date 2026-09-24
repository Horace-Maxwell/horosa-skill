// [Z4·紫微择日] AI 快照附加段 builder。三段头🔒与 AI_EXPORT_PRESET_SECTIONS.ziweizeri
// 追加段逐字成对(preflight 对偶锁);基底=紫微全文快照(ZiWeiMain 同链),此处只拼择时态。
import { ziweiLeafSummary } from './ziweiZeriConditionTypes.js';
import { JOINER_CN } from './conditionTypes.js';
import { appendZeriHitRows } from './zeriExplainText.js';

function treeLines(node, depth, index, out){
	if(!node){
		return out;
	}
	const indent = '  '.repeat(depth);
	const joiner = index > 0 ? `${JOINER_CN[node.joiner || 'all']} ` : '';
	if(node.kind === 'group' || Array.isArray(node.children)){
		out.push(`${indent}${joiner}${node.negate ? '非·' : ''}分组:`);
		(node.children || []).forEach((c, i)=>treeLines(c, depth + 1, i, out));
	}else{
		out.push(`${indent}${joiner}${ziweiLeafSummary(node)}`);
	}
	return out;
}

import { ZWEngineOptions } from '../../ziwei/ziweiOptions.js';

// [挂载自检 F-37] 紫微 14 个排盘引擎键是全局可变单例(ZWEngineOptions,主页/择日显示盘同读);工作台扫描口径独立冻结,
// 不回写全局(回写=悄悄改用户全局紫微设置)→ 改在快照配置段明标「扫描口径 vs 显示盘口径」,消除
// 「母全文(显示盘口径)+命中时段(工作台口径)且不标口径」。只比对工作台显式设过的键(未动的键=与显示盘同档)。
const ZW_CALIBRE_LABELS = {
	yearBoundary: '年界', ziweiLunarBasis: '安星农历', lateZi: '晚子时', leapMonth: '闰月', tianmaBasis: '天马', huoling: '火铃',
	kuiYue: '魁钺', kongwangStyle: '空亡', changshengStart: '长生起', changshengDirection: '长生序', shangShi: '天伤使',
	kongNaming: '空劫名', starSet: '星集', lifeMasterBy: '命主取法',
};
export function ziweiZeriCalibreLine(options, engine){
	const o = options && typeof options === 'object' ? options : {};
	const g = engine && typeof engine === 'object' ? engine : ZWEngineOptions;
	const diffs = [];
	Object.keys(ZW_CALIBRE_LABELS).forEach((k)=>{
		if(o[k] === undefined || o[k] === null || `${o[k]}` === ''){ return; }
		const gv = g[k];
		if(`${gv}` !== `${o[k]}`){ diffs.push(`${ZW_CALIBRE_LABELS[k]}=${o[k]}(工作台)≠${gv === undefined ? '默认' : gv}(显示盘)`); }
	});
	return diffs.length
		? `扫描口径:${diffs.join('、')} —— 命中时段按工作台口径判定,显示盘/紫微段按全局紫微设置排盘`
		: '扫描口径:与显示盘(全局紫微设置)一致';
}

export function buildZiweiZeriSnapshotExtra({ cfg, geo, natal, tree, results, truncated, options, explainAt, maxRows, explainRows }){
	const lines = [];
	lines.push('[择时搜索配置]');
	lines.push(`时间范围:${(cfg && cfg.startDate) || '?'} ${(cfg && cfg.startTime) || ''} ~ ${(cfg && cfg.endDate) || '?'} ${(cfg && cfg.endTime) || ''}`);
	lines.push(`地点:${(geo && geo.pos) || '(未名)'} 时区 ${(geo && geo.zone) || '?'}`);
	lines.push(`用事人本命:${natal && natal.label ? natal.label : '(未设)'}`);
	lines.push(ziweiZeriCalibreLine(options));
	lines.push('');
	lines.push('[择时条件]');
	const hasTree = tree && Array.isArray(tree.children) && tree.children.length;
	if(hasTree){
		tree.children.forEach((c, i)=>treeLines(c, 0, i, lines));
	}else{
		lines.push('(未设条件)');
	}
	lines.push('');
	lines.push('[命中时段]');
	const rows = Array.isArray(results) ? results : [];
	if(rows.length){
		// [Q-452 裁决 A / Q-453 裁决 2026-09-18] 清单上限全局可配(设置弹窗,缺省 60)+ 前 N 行附判读树(设定 vs 实际)——共用 appendZeriHitRows,
		// 行格式 / 尾句 / 截断句字节不变;explainAt 由宿主传入(同步引擎直算 / 异步预取缓存),缺则只列清单。
		appendZeriHitRows(lines, rows, {
			formatRow: (r, i)=>`${i + 1}. ${r.start} ~ ${r.end}(${r.durationMin}分)${r.mingText ? ` ${r.mingText}` : ''}${r.juText ? `·${r.juText}` : ''}`,
			tail: (total, cap)=>`…共 ${total} 段(仅列前 ${cap})`,
			truncated, truncatedText: '(扫描达上限截断,清单不完整)',
			maxRows, explainRows, explainAt, uiTree: tree, leafSummary: ziweiLeafSummary,
		});
	}else{
		lines.push('(尚未择时或无命中)');
	}
	return lines.join('\n');
}
