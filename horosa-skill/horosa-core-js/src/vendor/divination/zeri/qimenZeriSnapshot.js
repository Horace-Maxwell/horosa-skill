// [奇门择日] AI 快照附加段 builder(拼接在 DunJiaMain 奇门全文快照之后)。
// 🔒 三个段头「择日搜索配置/择日条件/命中时辰」与 aiExport.AI_EXPORT_PRESET_SECTIONS.qimenzeri
// 的追加段逐字成对(四同步纪律),改任一侧必同改另一侧(qimenZeriFourLedger.test.js 钉死)。
import { JOINER_CN } from './conditionTypes.js';
import { qimenLeafSummary } from './qimenConditionTypes.js';
import {
	PAIPAN_OPTIONS, QIJU_METHOD_OPTIONS, SCHOOL_OPTIONS,
	KONG_MODE_OPTIONS, MA_MODE_OPTIONS, TIME_ALG_OPTIONS, DAY_SWITCH_OPTIONS, ZHIRUN_LEAP_OPTIONS,
} from '../../dunjia/DunJiaCalc.js';

function labelOf(options, value){
	const hit = (options || []).find((o)=>`${o.value}` === `${value}`);
	return hit ? hit.label : `${value === undefined || value === null ? '' : value}`;
}

// 链式 joiner 树文本(组无 op;兄弟第 2 起带 且/或/异或 前缀)——勿按 op 键读(恒 undefined)。
export function describeQimenTreeLines(node, depth, index, out){
	const lines = out || [];
	if(!node){
		return lines;
	}
	const pad = '  '.repeat(depth);
	const gate = index > 0 ? `${JOINER_CN[node.joiner || 'all']} ` : '';
	if(node.kind === 'group' || Array.isArray(node.children)){
		lines.push(`${pad}${gate}${node.negate ? '非·' : ''}分组(${(node.children || []).length} 条):`);
		(node.children || []).forEach((c, i)=>describeQimenTreeLines(c, depth + 1, i, lines));
		return lines;
	}
	lines.push(`${pad}${gate}${qimenLeafSummary(node)}`);
	return lines;
}

export function buildQimenZeriSnapshotExtra({ cfg, geo, options, tree, results, truncated }){
	const lines = [];
	lines.push('[择日搜索配置]');
	lines.push(`时间段：${cfg ? `${cfg.startDate} ${cfg.startTime} → ${cfg.endDate} ${cfg.endTime}` : '未设'}`);
	const geoText = geo
		? (geo.pos || (geo.gpsLon !== undefined && geo.gpsLon !== null ? `${geo.gpsLon},${geo.gpsLat}` : '未设'))
		: '未设';
	lines.push(`地点：${geoText}　时区：${geo && geo.zone !== undefined && geo.zone !== null ? geo.zone : '—'}`);
	if(options){
		const segs = [
			labelOf(PAIPAN_OPTIONS, options.paiPanType),
			labelOf(QIJU_METHOD_OPTIONS, options.qijuMethod),
			labelOf(SCHOOL_OPTIONS, options.school),
			`空亡${labelOf(KONG_MODE_OPTIONS, options.kongMode)}`,
			`驿马${labelOf(MA_MODE_OPTIONS, options.yimaMode)}`,
			labelOf(TIME_ALG_OPTIONS, options.timeAlg),
			labelOf(DAY_SWITCH_OPTIONS, options.after23NewDay),
		];
		if(options.qijuMethod === 'zhirun'){
			segs.push(labelOf(ZHIRUN_LEAP_OPTIONS, options.zhirunLeapDays));
		}
		if(options.qijuMethod === 'shuzi' && options.shuziReportNumber){
			segs.push(`报数${options.shuziReportNumber}`);
		}
		lines.push(`参数：${segs.join('·')}`);
	}
	lines.push('');
	lines.push('[择日条件]');
	const treeLines = [];
	(tree && tree.children ? tree.children : []).forEach((c, i)=>describeQimenTreeLines(c, 0, i, treeLines));
	if(treeLines.length){
		lines.push(...treeLines);
	}else{
		lines.push('(未设条件)');
	}
	lines.push('');
	lines.push('[命中时辰]');
	const rows = Array.isArray(results) ? results : null;
	if(!rows){
		lines.push('尚未找局。');
	}else if(!rows.length){
		lines.push('时间段内无满足条件的时辰。');
	}else{
		const MAX_ROWS = 60;
		rows.slice(0, MAX_ROWS).forEach((row, i)=>{
			lines.push(`${i + 1}. ${row.start} ~ ${row.end}　${row.juText || ''}`);
		});
		if(rows.length > MAX_ROWS){
			lines.push(`(其余 ${rows.length - MAX_ROWS} 条略)`);
		}
		if(truncated){
			lines.push('(已达命中上限截断,请缩小时间段)');
		}
	}
	return lines.join('\n');
}
