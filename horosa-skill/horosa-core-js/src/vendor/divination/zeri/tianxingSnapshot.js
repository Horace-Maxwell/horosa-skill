// 天星择日·AI 快照 builder(纯函数,零 React)。
// 🔒 段头与 aiExport.js AI_EXPORT_PRESET_SECTIONS.tianxing 逐字成对(改一处必同步另一处,
//    否则该段在「AI导出设置」永远选不到——四同步铁律)。
import { conditionSummaryText } from './conditionGlyph.js';
import { JOINER_CN } from './conditionTypes.js';
import { HOUSE_SYSTEM_OPTIONS } from '../../../constants/AstroConst.js';

// 经纬度显示格式:度分制+大写方向字母(用户规格,如 119°19′E, 26°05′N;拒绝裸十进制)。
export function formatGpsDms(lon, lat){
	const part = (v, pos, neg) => {
		const n = Number(v);
		if(!isFinite(n)){ return ''; }
		const av = Math.abs(n);
		let d = Math.floor(av);
		let m = Math.round((av - d) * 60);
		if(m === 60){ d += 1; m = 0; }
		return `${d}°${String(m).padStart(2, '0')}′${n >= 0 ? pos : neg}`;
	};
	const lo = part(lon, 'E', 'W');
	const la = part(lat, 'N', 'S');
	return [lo, la].filter(Boolean).join(', ');
}

function fv(fields, key){
	return fields && fields[key] ? fields[key].value : undefined;
}

// UI 树=链式模型:组节点无 op,兄弟第 2 个起各带 joiner(all/any/xor)——
// 文本渲染与工作台行首徽标/详情判读树同构(且/或/异或前缀),勿按 op 键读(恒 undefined)。
function describeTreeLines(node, depth, out, idx){
	if(!node){ return out; }
	const indent = '  '.repeat(depth);
	const prefix = idx > 0 ? `${JOINER_CN[node.joiner] || JOINER_CN.all} ` : '';
	if(node.children){
		out.push(`${indent}${prefix}${node.negate ? '非 ' : ''}【分组】`);
		node.children.forEach((c, i) => describeTreeLines(c, depth + 1, out, i));
		return out;
	}
	out.push(`${indent}${prefix}${node.negate ? '非 ' : ''}${conditionSummaryText(node)}`);
	return out;
}

/**
 * buildTianxingSnapshot(chart, fields, extra, ctx)
 *  ctx = { cfg, tree, results, truncated }(TianxingElectionMain state 快照)。
 * 返回格式化快照文本;完全无内容时返回 ''(挂载契约:空=missing,勿硬凑表头)。
 */
export function buildTianxingSnapshot(chart, fields, extra, ctx){
	const cfg = (ctx && ctx.cfg) || {};
	const tree = (ctx && ctx.tree) || null;
	const results = (ctx && ctx.results) || null;
	if(!chart && !tree){
		return '';
	}
	const lines = [];
	lines.push('[起盘信息]');
	const date = fv(fields, 'date');
	const time = fv(fields, 'time');
	const dateText = date && date.format ? date.format('YYYY-MM-DD') : `${date || ''}`;
	const timeText = time && time.format ? time.format('HH:mm:ss') : `${time || ''}`;
	lines.push(`时间：${dateText} ${timeText}`.trim());
	lines.push(`地点：${fv(fields, 'pos') || ''} ${fv(fields, 'lon') || ''} ${fv(fields, 'lat') || ''}`.trim());
	lines.push(`时区：${fv(fields, 'zone') || ''}`);
	lines.push(`黄道：${Number(fv(fields, 'zodiacal') || 0) === 1 ? `恒星黄道(${fv(fields, 'siderealAyanamsa') || 'lahiri'})` : '回归黄道'}`);
	lines.push('');
	lines.push('[征象搜索配置]');
	if(cfg.startDate){
		lines.push(`时间段：${cfg.startDate} ${cfg.startTime || ''} → ${cfg.endDate} ${cfg.endTime || ''}`.trim());
		lines.push(`搜索地点：${cfg.pos || formatGpsDms(cfg.gpsLon, cfg.gpsLat)}`);
		const hsysOpt = HOUSE_SYSTEM_OPTIONS.find((o) => Number(o.value) === Number(cfg.hsys || 0));
		lines.push(`搜索盘面：${Number(cfg.zodiacal || 0) === 1 ? `恒星黄道(${cfg.siderealAyanamsa || 'lahiri'})` : '回归黄道'} · 宫制：${hsysOpt ? hsysOpt.label : Number(cfg.hsys || 0)}`);
	}else{
		lines.push('(未配置搜索)');
	}
	lines.push('');
	lines.push('[征象条件]');
	if(tree && tree.children && tree.children.length){
		// 根组=隐式容器不出头行,children 平铺(与工作台已选征象列表同构)。
		tree.children.forEach((c, i) => describeTreeLines(c, 0, lines, i));
	}else{
		lines.push('(未设置条件)');
	}
	lines.push('');
	lines.push('[命中区间]');
	if(results && results.length){
		lines.push(`共 ${results.length} 个区间${ctx && ctx.truncated ? '(已达上限截断)' : ''}：`);
		results.slice(0, 60).forEach((row, i) => {
			lines.push(`${i + 1}. ${row.start} ~ ${row.end}（${row.durationMin >= 90 ? `${(row.durationMin / 60).toFixed(1)}小时` : `${Math.round(row.durationMin)}分`}）`);
		});
		if(results.length > 60){
			lines.push(`……(其余 ${results.length - 60} 条略)`);
		}
	}else{
		lines.push(results ? '时间段内无满足全部条件的时刻。' : '(尚未执行搜索)');
	}
	return lines.join('\n');
}
