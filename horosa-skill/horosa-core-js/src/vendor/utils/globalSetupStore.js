// 全局设置(存储键 globalSetup)的落盘单源:app 模型的 save reducer 只经这里写。
//
// 写法与页面排盘设置(pageSettingsStore.save)同一范式:**只写这一次真改了的设置字段,以存储里现有的那份为底合并**,
// 不按内存里的整份状态拼一份写回。此前 save 每次调用(哪怕只改了 refresh / loading 这类非设置字段)都把内存态整份写回:
//   · 全量恢复写进去的全局设置,在刷新页面之前被任何一次 app/save(排盘请求结束、切外观……)用恢复前的内存态整份盖回去;
//   · 同一本机存储的两个窗口:A 改了外观,B 随后改日界 —— B 用自己内存里的旧外观整份写回,A 的改动就没了。
// 冻结:全量恢复执行期间、以及恢复的记录只在内存(页面不刷新)之后,内存态与存储已经对不上 —— 冻结期间一律不写(界面照常用内存态,
// 恢复写进去的设置重启后生效)。
import { safeLocalStorageGet, safeLocalStorageSet } from '../gua/safeStorage.js';

export const GLOBAL_SETUP_STORAGE_KEY = 'globalSetup';   // 与 utils/constants GlobalSetupKey 同名(此处不引 constants,免循环)

// 落盘的设置字段(与 app 模型 state 里的同名字段一一对应;非设置字段 refresh / loading / 窗口高度等永不落盘)
export const GLOBAL_SETUP_FIELDS = [
	'chartDisplay',
	'chartStyle',
	'wheelArt',
	'planetListStyle',
	'indiaChartStyle',
	'planetDisplay',
	'lotsDisplay',
	'colorTheme',
	'appearanceMode',
	'showPdBounds',
	'pdMethod',
	'pdTimeKey',
	'showPlanetHouseInfo',
	'showAstroMeaning',
	'showOnlyRulExaltReception',
	'voidClassical',
	'schoolPreset',
	'tripSystem',
	'dayBoundary',
	'lateZiHourMode',
	'zeriSnapshotMaxRows',
	'zeriSnapshotExplainRows',
	'chartDisplayDefaultsVersion',
	'planetDisplayDefaultsVersion',
];

let frozenReason = null;

// 内存镜像:全站读全局设置(日界 / 晚子时 / 择日快照行数 / 显示开关……)一律读它,不各自直读存储。
//   · 没冻结:每次读比对存储原串,变了(别的窗口写了 / 外部直写)就重建 —— 跨窗口跟随,且同串零解析;
//   · 冻结期间(全量恢复执行中 / 恢复的记录只在内存、页面不刷新):不跟存储(恢复直写进去的值重启后才生效),
//     本窗口 save 照样更新镜像 —— 界面上改的值本次运行照样生效,与界面显示一致(此前冻结只拦写、不管读:
//     界面显示新日界,八字 / 紫微 / 六壬 / 择日仍按存储里的旧值起盘)。
let mirror = null;
let mirrorRaw;   // 镜像对应的存储原串(undefined = 还没读过)
function parseSetup(raw){
	if(!raw){ return {}; }
	try{
		const o = JSON.parse(raw);
		return o && typeof o === 'object' && !Array.isArray(o) ? o : {};
	}catch(e){
		return {};
	}
}
function syncMirrorFromStorage(){
	const raw = safeLocalStorageGet(GLOBAL_SETUP_STORAGE_KEY);
	if(mirror !== null && raw === mirrorRaw){ return false; }
	mirrorRaw = raw;
	mirror = parseSetup(raw);
	return true;
}

// 当前生效的全局设置(对象,只读;没有 → 空对象)。永不抛
export function currentGlobalSetup(){
	if(mirror === null || frozenReason === null){ syncMirrorFromStorage(); }
	return mirror;
}
// 单字段便捷读(缺 → undefined)
export function readGlobalSetupField(key){
	const g = currentGlobalSetup();
	return g ? g[key] : undefined;
}

// 别的窗口改了全局设置(storage 事件,key 为 globalSetup 或清空存储时的 null):冻结期间不跟;
// 镜像变了才回调 fn(镜像)。返回解绑函数
export function subscribeGlobalSetupStorage(fn){
	if(typeof window === 'undefined' || typeof window.addEventListener !== 'function'){ return ()=>{}; }
	const h = (e)=>{
		const k = e ? e.key : null;
		if(k !== null && k !== GLOBAL_SETUP_STORAGE_KEY){ return; }
		if(frozenReason !== null){ return; }
		if(syncMirrorFromStorage() && typeof fn === 'function'){
			try{ fn(mirror); }catch(err){ /* 订阅方出错不影响镜像 */ }
		}
	};
	window.addEventListener('storage', h);
	return ()=>window.removeEventListener('storage', h);
}

// 冻结 / 解冻整份写回类写入口(全量恢复流程用)。reason 只用于诊断。冻结那一刻先把镜像对齐存储(恢复前的值)
export function freezeGlobalSetupWrites(reason){
	if(frozenReason === null){ syncMirrorFromStorage(); }
	frozenReason = `${reason || 'frozen'}`;
}
export function thawGlobalSetupWrites(){
	frozenReason = null;
}
export function globalSetupWritesFrozen(){
	return frozenReason !== null;
}

// 存储里现有的那份(对象);没有 / 解析不出 / 不是对象 → null。永不抛
export function readStoredGlobalSetup(){
	const raw = safeLocalStorageGet(GLOBAL_SETUP_STORAGE_KEY);
	if(!raw){ return null; }
	try{
		const o = JSON.parse(raw);
		return o && typeof o === 'object' && !Array.isArray(o) ? o : null;
	}catch(e){
		return null;
	}
}

// 从一次 save 的 payload 里挑出设置字段(只认 payload 自己带的键;值取 values —— 调用方已归一化过的那份)。
// 返回 { [field]: value };一个设置字段都没有 → 空对象(= 这次不写)
export function pickGlobalSetupPatch(payload, values){
	const out = {};
	if(!payload || typeof payload !== 'object'){ return out; }
	const src = values && typeof values === 'object' ? values : payload;
	GLOBAL_SETUP_FIELDS.forEach((f)=>{
		if(Object.prototype.hasOwnProperty.call(payload, f) && src[f] !== undefined){
			out[f] = src[f];
		}
	});
	return out;
}

// 合并写:以存储里现有的那份为底,只覆盖 patch 里的字段(存储里别的字段 —— 包括本机别的窗口刚写的 —— 原样保留)。
// 返回 { written:boolean, skipped?:'empty'|'frozen', ok?:boolean }。永不抛
export function mergeGlobalSetupWrite(patch){
	const keys = patch && typeof patch === 'object' ? Object.keys(patch).filter((k)=>GLOBAL_SETUP_FIELDS.indexOf(k) >= 0) : [];
	if(!keys.length){ return { written: false, skipped: 'empty' }; }
	if(globalSetupWritesFrozen()){
		// 不落盘,但镜像跟着改:本次运行里各处读到的与界面一致
		const cur = currentGlobalSetup();
		mirror = { ...cur };
		keys.forEach((k)=>{ mirror[k] = patch[k]; });
		return { written: false, skipped: 'frozen' };
	}
	const base = readStoredGlobalSetup() || {};
	const next = { ...base };
	keys.forEach((k)=>{ next[k] = patch[k]; });
	let ok = false;
	try{ ok = safeLocalStorageSet(GLOBAL_SETUP_STORAGE_KEY, JSON.stringify(next)); }catch(e){ ok = false; }
	// 镜像 = 这次合并后的值;原串记存储里实际那份(写不进时仍是旧串,下次读不会拿旧串把界面上的新值冲掉)
	mirror = next;
	mirrorRaw = safeLocalStorageGet(GLOBAL_SETUP_STORAGE_KEY);
	return { written: true, ok };
}

export function __resetGlobalSetupMirrorForTest(){
	mirror = null;
	mirrorRaw = undefined;
}
