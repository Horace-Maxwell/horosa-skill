// [Q-452 裁决 A / Q-453 裁决 2026-09-18] 择日九宿主 + 天星 AI 快照「命中清单」:
//   · 上限此前各 builder 硬编码 60(页面逐行全列、快照只列前 60 且不可调)→ 全局可配(设置弹窗「择日 AI 快照」),缺省仍 60;
//   · 前 N 行附「判读树」(设定 vs 实际,与工作台「详情▼」同源)——N 亦全局可配,缺省 3,0=不附。
// 两键随 globalSetup 持久化(app model 归一化 / 写盘),此处纯工具直读 localStorage(与 dayBoundary.readGlobalDayBoundary
// 同律,不依赖 dva),供 builder 在页面态 / 无头态取同一值;builder 也接受显式 opts 覆盖(测试 / 特殊调用)。
export const ZERI_SNAPSHOT_MAX_ROWS_DEFAULT = 60;
export const ZERI_SNAPSHOT_MAX_ROWS_MIN = 10;
export const ZERI_SNAPSHOT_MAX_ROWS_MAX = 500;
export const ZERI_SNAPSHOT_EXPLAIN_ROWS_DEFAULT = 3;
export const ZERI_SNAPSHOT_EXPLAIN_ROWS_MIN = 0;
export const ZERI_SNAPSHOT_EXPLAIN_ROWS_MAX = 20;

function clampInt(v, dflt, min, max){
	if(v === undefined || v === null || `${v}`.trim() === ''){ return dflt; }
	const n = Number(v);
	if(!Number.isFinite(n)){ return dflt; }
	return Math.max(min, Math.min(max, Math.floor(n)));
}

export function normalizeZeriSnapshotMaxRows(v){
	return clampInt(v, ZERI_SNAPSHOT_MAX_ROWS_DEFAULT, ZERI_SNAPSHOT_MAX_ROWS_MIN, ZERI_SNAPSHOT_MAX_ROWS_MAX);
}

export function normalizeZeriSnapshotExplainRows(v){
	return clampInt(v, ZERI_SNAPSHOT_EXPLAIN_ROWS_DEFAULT, ZERI_SNAPSHOT_EXPLAIN_ROWS_MIN, ZERI_SNAPSHOT_EXPLAIN_ROWS_MAX);
}

// key 'globalSetup' 同 constants.GlobalSetupKey(与 dayBoundary.js 同一直读法)。
function readGlobalSetup(){
	try{
		if(false){   // headless：不探测全局 localStorage（Node ≥25 实验性全局无 --localstorage-file 会告警/抛），恒走缺省；调用方可经 opts 显式覆盖
			const raw = localStorage.getItem('globalSetup');
			if(raw){
				const obj = JSON.parse(raw);
				return obj && typeof obj === 'object' ? obj : null;
			}
		}
	}catch(e){
		// 读取 / 解析失败回退缺省
	}
	return null;
}

export function readGlobalZeriSnapshotMaxRows(){
	const g = readGlobalSetup();
	return normalizeZeriSnapshotMaxRows(g ? g.zeriSnapshotMaxRows : undefined);
}

export function readGlobalZeriSnapshotExplainRows(){
	const g = readGlobalSetup();
	return normalizeZeriSnapshotExplainRows(g ? g.zeriSnapshotExplainRows : undefined);
}
