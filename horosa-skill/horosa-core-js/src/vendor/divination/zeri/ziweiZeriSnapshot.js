// AI 快照附加段 builder。三段头🔒与 AI_EXPORT_PRESET_SECTIONS.ziweizeri
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

import { ZWEngineOptions, ZIWEI_ZERI_SCAN_FIELDS, LATE_ZI_OPTIONS } from '../../ziwei/ziweiOptions.js';

// 紫微 14 个排盘引擎键是全局可变单例(ZWEngineOptions,主页/择日显示盘同读);工作台扫描口径独立冻结,
// 不回写全局(回写=悄悄改用户全局紫微设置)→ 改在快照配置段明标「扫描口径 vs 显示盘口径」,消除
// 「母全文(显示盘口径)+命中时段(工作台口径)且不标口径」。只比对工作台显式设过的键(未动的键=与显示盘同档)。
// 字段名与档名取工作台同一份(ZIWEI_ZERI_SCAN_FIELDS),性别 / 时间算法不是排盘引擎键,不比
const ZW_CALIBRE_FIELDS = ZIWEI_ZERI_SCAN_FIELDS.filter((f)=>f.key !== 'gender' && f.key !== 'timeAlg');
const zwOptionLabel = (f, v)=>{
	// 晚子时:显示盘可能是「双盘」(工作台不列这一档),档名查未过滤的全表,不露内部键名
	const opts = f.key === 'lateZi' ? LATE_ZI_OPTIONS : (f.options || []);
	const hit = opts.find((o)=>`${o.value}` === `${v}`);
	return hit ? hit.label : `${v}`;
};
// 显示盘实际所用的值:安星农历没设时按引擎规则(ZiweiCalc:晚子时跟随全局 = 日历日,否则随日柱进位),其余没设 = 默认档
const zwDisplayValue = (f, g)=>{
	const v = g[f.key];
	if(v !== undefined && v !== null){ return v; }
	if(f.key === 'ziweiLunarBasis'){ return (!g.lateZi || g.lateZi === 'global') ? 'calendar' : 'ziwei'; }
	return f.dv;
};
export function ziweiZeriCalibreLine(options, engine){
	const o = options && typeof options === 'object' ? options : {};
	const g = engine && typeof engine === 'object' ? engine : ZWEngineOptions;
	const diffs = [];
	ZW_CALIBRE_FIELDS.forEach((f)=>{
		const k = f.key;
		if(o[k] === undefined || o[k] === null || `${o[k]}` === ''){ return; }
		// 显示盘全局设置里没有的键 = 显示盘按该项实际规则排(安星农历随晚子时定);按它比,不误报也不漏报
		const gv = zwDisplayValue(f, g);
		if(`${gv}` !== `${o[k]}`){ diffs.push(`${f.label}=${zwOptionLabel(f, o[k])}(工作台)≠${zwOptionLabel(f, gv)}(显示盘)`); }
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
		// 清单上限全局可配(设置弹窗,缺省 60)+ 前 N 行附判读树(设定 vs 实际)——共用 appendZeriHitRows,
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
