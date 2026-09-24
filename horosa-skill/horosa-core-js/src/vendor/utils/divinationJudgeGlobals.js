// utils/divinationJudgeGlobals.js
// 纯判读级参数的全局真值仓（「设置 → 星盘设置 → 卜卦·择日判读」写入口）。
//
// 2026-07 二批收缩：太阳三态阈值/空亡口径/恒星轨等七键已升排盘级、迁入 classicalChartGlobals
// （后端 perchart 参数化,全站显示随动）;本仓只剩**不进排盘请求**的两个纯判读键。
// 旧存储里的迁移键由 classicalChartGlobals 读侧一次性并入（本仓白名单收缩后自然失效）。
//
// 判读消费方请统一走 utils/judgeLayerOverrides.judgeLayerOverrides()（= classical 仓判读相关
// 七键 ∪ 本仓两键,只含用户改过的键）——保持 horaryJudgeOpts 四层优先级语义不变。
import { safeJsonParseFromStorage, safeJsonStringifyToStorage } from '../gua/safeStorage.js';

export const DIVINATION_JUDGE_STORAGE_KEY = 'horosa.chart.divinationJudgeGlobals.v1';
export const DIVINATION_JUDGE_EVENT = 'horosa:divination-judge-globals-changed';

// 默认值 = HORARY_PARAM_SPEC 各键的 classical 零回归值。
export const DIVINATION_JUDGE_DEFAULTS = {
	combustMitigateSameSign: false,   // 燃烧限同座（异座不判燃烧;判读层专属,后端 sunPos/phase 不看同座）[Q-144 裁决 2026-09-18] 全局缺省改关=与择日引擎缺省(chartFacts 门 === true)一致,拨开即真下发;卜卦按流派(classical 档学理绑定 true 不受此影响)
	antiscia: true,                   // 映点参与判读（隐合/隐冲;显示层映点恒开,后端 antisciaOrb 另管）
};

const BOOL_KEYS = ['combustMitigateSameSign', 'antiscia'];
const ALL_KEYS = Object.keys(DIVINATION_JUDGE_DEFAULTS);

let cache = null;
// [SURF-R5c] 读侧自愈(照 classicalChartGlobals 同款):备份恢复直写本仓 raw 键不经 set,
// 热 cache 恒旧值+恢复后改一档=旧 cache 整包回写覆盖恢复值。rawStr 比对+1s 节流。
let cacheRawStr = null;
let lastRawCheckAt = 0;
function rawSelfHealCheck(){
	if(!cache){ return; }
	const now = Date.now();
	if(now - lastRawCheckAt < 1000){ return; }
	lastRawCheckAt = now;
	let rawStr = null;
	try{ rawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(DIVINATION_JUDGE_STORAGE_KEY) : null; }catch(e){ return; }
	if(rawStr === cacheRawStr){ return; }
	cache = null;
	getDivinationJudgeGlobals();
	if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function'){
		try{ window.dispatchEvent(new CustomEvent(DIVINATION_JUDGE_EVENT, { detail: { key: '*', value: null } })); }catch(e){ /* ignore */ }
	}
}

function normalize(raw){
	const out = { ...DIVINATION_JUDGE_DEFAULTS };
	if(!raw || typeof raw !== 'object'){ return out; }
	ALL_KEYS.forEach((k) => {
		if(raw[k] === undefined || raw[k] === null){ return; }
		if(BOOL_KEYS.indexOf(k) >= 0){
			out[k] = !!raw[k];
		}else{
			out[k] = raw[k] + '';
		}
	});
	return out;
}

export function getDivinationJudgeGlobals(){
	rawSelfHealCheck();
	if(!cache){
		try{ cacheRawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(DIVINATION_JUDGE_STORAGE_KEY) : null; }catch(e){ cacheRawStr = null; }
		cache = normalize(safeJsonParseFromStorage(DIVINATION_JUDGE_STORAGE_KEY));
	}
	return { ...cache };
}

// 只取「用户改过（≠默认）」的键;默认态恒 {}。
export function divinationJudgeOverrides(){
	const g = getDivinationJudgeGlobals();
	const out = {};
	ALL_KEYS.forEach((k) => {
		if(g[k] !== DIVINATION_JUDGE_DEFAULTS[k]){ out[k] = g[k]; }
	});
	return out;
}

export function setDivinationJudgeGlobal(key, value){
	if(ALL_KEYS.indexOf(key) < 0){ return; }
	const next = normalize({ ...getDivinationJudgeGlobals(), [key]: value });
	cache = next;
	safeJsonStringifyToStorage(DIVINATION_JUDGE_STORAGE_KEY, next);
	try{ cacheRawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(DIVINATION_JUDGE_STORAGE_KEY) : cacheRawStr; }catch(e){ /* keep */ }
	lastRawCheckAt = Date.now();
	if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function'){
		try{
			window.dispatchEvent(new CustomEvent(DIVINATION_JUDGE_EVENT, { detail: { key, value: next[key] } }));
		}catch(e){ /* 静默 */ }
	}
}

export function __resetDivinationJudgeCacheForTest(){
	cache = null;
	cacheRawStr = null;
	lastRawCheckAt = 0;
}
