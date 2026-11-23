// 盘壳(DivinationChartShell)宿主页的排盘设置 · 共用件。
//
// 卜卦盘 / 择日盘 / 世俗盘 / 天星择日共用一个盘壳:页面专属选项收在壳的 extra 里,盘面字段(黄道 / 宫制)收在壳的
// fields 里。壳只在**构造时**读 defaults / initialExtra 两个 prop —— 所以「跨会话保留」对这几页的做法一致:
//   · 构造时用保存值播种 defaults / initialExtra(没存过 = 原来的出厂值,逐字相同);
//   · 用户亲手改 extra 里的设置项 → 页面落盘;用户亲手改壳左栏的黄道 / 宫制 → 壳回调 onUserFieldChange → 页面落盘。
// 载入事盘回灌、换流派联动、全局古典参数热同步都走壳的 patchFields / setExtra,不经落盘入口。
import { HOUSE_SYSTEM_OPTIONS } from '../../constants/AstroConst.js';
import { INDIA_AYANAMSA_OPTIONS } from '../india/indiaConst.js';

// 盘面字段三键的 schema 片段(各页 definePageSettings 时展开进去;hsysDef = 该页出厂宫制)。
export function shellFieldSchema(hsysDef){
	return {
		zodiacal: { def: 0, oneOf: [0, 1] },
		siderealAyanamsa: { def: '', oneOf: ['', 'user'].concat(INDIA_AYANAMSA_OPTIONS.map((o)=>o.value)) },   // 壳左栏黄道下拉(buildZodiacOptions)的全量候选:'' = 回归黄道、'user' = 自定义历元槽位;库里的值会进起盘请求,不收候选外的串
		hsys: { def: hsysDef, oneOf: HOUSE_SYSTEM_OPTIONS.map((o)=>o.value) },
	};
}

// 由保存值播种壳的两个 prop。baseDefaults / baseExtra = 该页出厂值;extraKeys = 该页 extra 里要保留的设置键。
// 只并入**保存过**的键:没存过的键保持出厂值(包括「出厂值另有来源」的,如随流派联动的宫制)。
// factoryDefaults(可选)= 盘面字段的**出厂**值。baseDefaults 本身随保存值变的页要单独给
// (卜卦盘的后端字段随保存的流派联动:baseDefaults 是「保存流派」那一档,出厂是经典主流那一档)。
// 第三个返回值 restoreBaseline = 载入事盘时的还原基线:事盘里没有的键回**出厂值**,而不是本机保存的偏好 ——
// 一份按出厂口径存下的旧案,不能因为你后来把缺省改成了别的流派,打开时就被按新流派改判。
export function seedShellFromSaved(store, baseDefaults, baseExtra, extraKeys, factoryDefaults){
	const sv = store.loadSaved();
	const defaults = { ...(baseDefaults || {}) };
	if(sv.zodiacal !== undefined){
		defaults.zodiacal = sv.zodiacal;
		defaults.siderealAyanamsa = sv.zodiacal === 1 ? (sv.siderealAyanamsa || 'lahiri') : '';
	}
	if(sv.hsys !== undefined){ defaults.hsys = sv.hsys; }
	const initialExtra = { ...(baseExtra || {}) };
	(extraKeys || []).forEach((k)=>{
		if(sv[k] === undefined){ return; }
		// 稀疏覆盖层存的是空对象时不必播种(等价于没有)
		if(sv[k] && typeof sv[k] === 'object' && !Array.isArray(sv[k]) && !Object.keys(sv[k]).length){ return; }
		initialExtra[k] = sv[k];
	});
	const fac = factoryDefaults || baseDefaults || {};
	const baselineFields = factoryDefaults ? { ...factoryDefaults } : {};
	['zodiacal', 'siderealAyanamsa', 'hsys'].forEach((k)=>{
		if(baselineFields[k] === undefined){ baselineFields[k] = fac[k] !== undefined ? fac[k] : (k === 'siderealAyanamsa' ? '' : 0); }
	});
	const baselineExtra = {};
	(extraKeys || []).forEach((k)=>{ baselineExtra[k] = (baseExtra || {})[k]; });   // 出厂时不存在的键 = undefined(显式清掉)
	return { defaults, initialExtra, restoreBaseline: { fields: baselineFields, extra: baselineExtra } };
}
