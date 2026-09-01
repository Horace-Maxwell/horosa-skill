// [Z1·黄历择日] AI 快照附加段 builder。三段头🔒与 aiExport `AI_EXPORT_PRESET_SECTIONS.huanglizeri`
// 的追加段逐字成对(preflight 对偶锁);基底=选中日黄历日课快照(HuangLiMain 同链),此处只拼择日态。
import { HUANGLI_CONDITION_TYPES, huangliLeafSummary } from './huangliZeriConditionTypes.js';
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
		out.push(`${indent}${joiner}${huangliLeafSummary(node)}`);
	}
	return out;
}

export function buildHuangliZeriSnapshotExtra({ cfg, tree, results, truncated }){
	const lines = [];
	lines.push('[择吉搜索配置]');
	lines.push(`时间范围:${(cfg && cfg.startDate) || '?'} ~ ${(cfg && cfg.endDate) || '?'}(日粒度;黄历日课与地点/时刻无关)`);
	lines.push('');
	lines.push('[择吉条件]');
	const hasTree = tree && Array.isArray(tree.children) && tree.children.length;
	if(hasTree){
		tree.children.forEach((c, i)=>treeLines(c, 0, i, lines));
	}else{
		lines.push('(未设条件)');
	}
	lines.push('');
	lines.push('[命中日段]');
	const rows = Array.isArray(results) ? results : [];
	if(rows.length){
		rows.slice(0, 60).forEach((r, i)=>{
			lines.push(`${i + 1}. ${r.start}${r.days > 1 ? ` ~ ${r.end}` : ''}(${r.days}天)${r.badge ? ` ${r.badge}` : ''}`);
		});
		if(rows.length > 60){
			lines.push(`…共 ${rows.length} 段(仅列前 60)`);
		}
		if(truncated){
			lines.push('(扫描达上限截断,清单不完整)');
		}
	}else{
		lines.push('(尚未择吉或无命中)');
	}
	return lines.join('\n');
}

// 供金标:条件类键集(注册表单源)。
export function huangliZeriConditionKeys(){
	return Object.keys(HUANGLI_CONDITION_TYPES);
}
