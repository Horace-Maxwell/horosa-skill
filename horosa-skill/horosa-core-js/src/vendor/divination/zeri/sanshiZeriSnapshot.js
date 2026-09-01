// [Z6·三式择日] AI 快照附加段 builder。三段头🔒与 AI_EXPORT_PRESET_SECTIONS.sanshizeri
// 追加段逐字成对(preflight 对偶锁);基底=三式合一全文快照(SanShiUnitedMain 同链),此处只拼择时态。
import { sanshiLeafSummary } from './sanshiZeriConditionTypes.js';
import { JOINER_CN } from './conditionTypes.js';

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
		out.push(`${indent}${joiner}${sanshiLeafSummary(node)}`);
	}
	return out;
}

export function buildSanshiZeriSnapshotExtra({ cfg, geo, natal, tree, results, truncated }){
	const lines = [];
	lines.push('[择时搜索配置]');
	lines.push(`时间范围:${(cfg && cfg.startDate) || '?'} ${(cfg && cfg.startTime) || ''} ~ ${(cfg && cfg.endDate) || '?'} ${(cfg && cfg.endTime) || ''}`);
	lines.push(`地点:${(geo && geo.pos) || '(未名)'} 时区 ${(geo && geo.zone) || '?'}`);
	lines.push(`用事人本命:${natal && natal.label ? natal.label : '(未设)'}`);
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
		rows.slice(0, 60).forEach((r, i)=>{
			lines.push(`${i + 1}. ${r.start} ~ ${r.end}(${r.durationMin}分)${r.sanshiText ? ` ${r.sanshiText}` : ''}`);
		});
		if(rows.length > 60){
			lines.push(`…共 ${rows.length} 段(仅列前 60)`);
		}
		if(truncated){
			lines.push('(扫描达上限截断,清单不完整)');
		}
	}else{
		lines.push('(尚未择时或无命中)');
	}
	return lines.join('\n');
}
