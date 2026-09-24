// [Z8·印度择日] AI 快照附加段 builder。三段头🔒与 AI_EXPORT_PRESET_SECTIONS.indiazeri
// 追加段逐字成对(preflight 对偶锁);挂载=三段自足(印度页 A 类星盘系无 module 槽;印度盘全文见主印度页),此处只拼择时态。
import { indiaLeafSummary } from './indiaZeriConditionTypes.js';
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
		out.push(`${indent}${joiner}${indiaLeafSummary(node)}`);
	}
	return out;
}

export function buildIndiaZeriSnapshotExtra({ cfg, geo, tree, results, truncated, explainAt, maxRows, explainRows }){
	const lines = [];
	lines.push('[择时搜索配置]');
	lines.push(`时间范围:${(cfg && cfg.startDate) || '?'} ${(cfg && cfg.startTime) || ''} ~ ${(cfg && cfg.endDate) || '?'} ${(cfg && cfg.endTime) || ''}`);
	lines.push(`地点:${(geo && geo.pos) || '(未名)'} 时区 ${(geo && geo.zone) || '?'}`);
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
			formatRow: (r, i)=>`${i + 1}. ${r.start} ~ ${r.end}(${r.durationMin}分)`,
			tail: (total, cap)=>`…共 ${total} 段(仅列前 ${cap})`,
			truncated, truncatedText: '(扫描达上限截断,清单不完整)',
			maxRows, explainRows, explainAt, uiTree: tree, leafSummary: indiaLeafSummary,
		});
	}else{
		lines.push('(尚未择时或无命中)');
	}
	return lines.join('\n');
}
