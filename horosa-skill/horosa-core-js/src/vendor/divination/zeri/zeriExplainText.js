// [Q-452/Q-453 裁决 2026-09-18] 择日快照「命中清单」共用尾巴:上限可配 + 前 N 行附判读树。
// 判读树 = 工作台「详情▼」同一棵编译形 explain 树(group{op,pass,children} / leaf{type,actual,pass}),
// 「设定」文本按 UI 树叶 DFS 序配对(compile 不增删叶,先序一致——与各工作台 renderExplainNode 同律)。
// 九宿主 builder + 天星 builder 都走 appendZeriHitRows:行格式 / 尾句 / 截断句各自保留(字节不变),只把
// 硬编码 60 换成可配上限,并在前 N 行下缩进附判读行。
import { readGlobalZeriSnapshotMaxRows, readGlobalZeriSnapshotExplainRows, normalizeZeriSnapshotMaxRows, normalizeZeriSnapshotExplainRows } from '../../utils/zeriSnapshotPrefs.js';

export const ZERI_GATE_CN = { all: '且(全部满足)', any: '或(任一满足)', xor: '异或(奇数满足)', not: '非(取反)' };

export function collectZeriUiLeaves(node, out){
	const acc = out || [];
	if(!node){ return acc; }
	if(node.kind === 'leaf'){ acc.push(node); return acc; }
	(node.children || []).forEach((c)=>collectZeriUiLeaves(c, acc));
	return acc;
}

function passMark(ok){
	return ok ? '✓' : '✗';
}

function explainNodeLines(node, uiLeaves, counter, depth, out, leafSummary, indent){
	if(!node){ return out; }
	const pad = `${indent}${'  '.repeat(depth)}`;
	if(node.kind === 'group'){
		out.push(`${pad}${ZERI_GATE_CN[node.op] || node.op || '分组'} ${passMark(node.pass)}`);
		(node.children || []).forEach((c)=>explainNodeLines(c, uiLeaves, counter, depth + 1, out, leafSummary, indent));
		return out;
	}
	const ui = uiLeaves[counter.i];
	counter.i += 1;
	let setting = '';
	try{ setting = ui && typeof leafSummary === 'function' ? `${leafSummary(ui) || ''}` : ''; }catch(e){ setting = ''; }
	if(!setting){ setting = `${node.type || '(条件)'}`; }
	const negate = ui && ui.negate ? '(取反)' : '';
	const actual = node.actual === undefined || node.actual === null || `${node.actual}` === '' ? '—' : `${node.actual}`;
	out.push(`${pad}· 设定 ${setting}${negate} → 实际 ${actual} ${passMark(node.pass)}`);
	return out;
}

// 单行判读文本:explainResult = { tree, err? }(同步引擎直返 / 异步预取缓存);uiTree = 冻结 UI 树。
export function buildZeriRowExplainLines(explainResult, uiTree, leafSummary, indent){
	const pad = indent || '   ';
	if(!explainResult){ return []; }
	if(!explainResult.tree){
		return explainResult.err ? [`${pad}判读:(不可得 ${explainResult.err})`] : [];
	}
	const uiLeaves = collectZeriUiLeaves(uiTree, []);
	const out = [`${pad}判读:`];
	explainNodeLines(explainResult.tree, uiLeaves, { i: 0 }, 1, out, leafSummary, pad);
	return out;
}

// 行时长(分):优先取 row.durationMin;缺则由 start/end('YYYY-MM-DD HH:mm[:ss]' 墙钟文本)相减(奇门行此前无时长)。
export function zeriRowDurationMin(row){
	if(row && Number.isFinite(Number(row.durationMin)) && `${row.durationMin}` !== ''){ return Math.round(Number(row.durationMin)); }
	const parse = (s)=>{
		const m = /^(-?\d{1,4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(`${s || ''}`.trim());
		if(!m){ return NaN; }
		return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]));
	};
	const a = parse(row && row.start);
	const b = parse(row && row.end);
	if(!Number.isFinite(a) || !Number.isFinite(b) || b < a){ return null; }
	return Math.round((b - a) / 60000);
}

// lines 追加命中清单:
//   opts.formatRow(row, i) → 行文本(各 builder 自有格式,字节不变)
//   opts.tail(total, cap) → 超上限尾句(null=不加);opts.truncated + opts.truncatedText → 扫描截断句
//   opts.maxRows / opts.explainRows:显式覆盖;缺省读全局设置(60 / 3)
//   opts.explainAt(row, i) → { tree, err? } | null(同步引擎直算 / 异步预取缓存);opts.uiTree + opts.leafSummary 给「设定」文本
export function appendZeriHitRows(lines, rows, opts){
	const o = opts || {};
	const list = Array.isArray(rows) ? rows : [];
	const cap = o.maxRows === undefined ? readGlobalZeriSnapshotMaxRows() : normalizeZeriSnapshotMaxRows(o.maxRows);
	const n = o.explainRows === undefined ? readGlobalZeriSnapshotExplainRows() : normalizeZeriSnapshotExplainRows(o.explainRows);
	list.slice(0, cap).forEach((r, i)=>{
		lines.push(o.formatRow ? o.formatRow(r, i) : `${i + 1}. ${r && r.start} ~ ${r && r.end}`);
		if(i < n && typeof o.explainAt === 'function'){
			let res = null;
			try{ res = o.explainAt(r, i); }catch(e){ res = null; }
			if(res && typeof res.then === 'function'){ res = null; }   // 异步结果不等(宿主应预取后再传缓存)
			buildZeriRowExplainLines(res, o.uiTree, o.leafSummary, '   ').forEach((l)=>lines.push(l));
		}
	});
	if(list.length > cap && typeof o.tail === 'function'){
		const t = o.tail(list.length, cap);
		if(t){ lines.push(t); }
	}
	if(o.truncated && o.truncatedText){
		lines.push(o.truncatedText);
	}
	return lines;
}
