// utils/classicalChartGlobals.js
// /chart 级古典排盘参数的全局真值仓（「设置 → 星盘设置」唯一写入口）。
//
// 为什么需要它：termsVariant / westNodeType / sectBuffer / leoBoundFirst / triplicity /
// lotReversal / geminiBoundEmended 此前只活在 astro model fields 与 app 会话态里——
// globalSetup 不持久化它们，重启即回默认；辅盘（卜卦/择日）、合盘等独立构参页面
// 也各自为政。本仓以 safeStorage 持久化一份用户全局偏好，作为各处 fields 的
// 「缺省种子」（models/astro.js getFields 播种；DivinationChartShell 监听事件热同步）。
//
// 优先级铁律（用户拍板）：页面显式字段（含卜卦流派预设 patch 的键）> 本仓全局值 > 内建默认。
// 本仓默认值 == 各内建默认 —— 用户从未改过设置时，一切请求体逐字节零变（零回归锚）。
import { safeJsonParseFromStorage, safeJsonStringifyToStorage } from '../gua/safeStorage.js';

export const CLASSICAL_GLOBALS_STORAGE_KEY = 'horosa.chart.classicalGlobals.v1';
export const CLASSICAL_GLOBALS_EVENT = 'horosa:classical-globals-changed';

// 默认值 = 现内建默认（fieldsToParams 条件透传的「不下发」侧）。
export const CLASSICAL_GLOBAL_DEFAULTS = {
	termsVariant: 0,          // 0=埃及 1=托勒密·校勘本 2=托勒密·经典传本 3=迦勒底(推演)
	geminiBoundEmended: 0,    // 仅 termsVariant==2 生效:1=双子末两界校勘对调
	westNodeType: 'mean',     // 'mean' | 'true'
	sectBuffer: 'geo',        // 'geo' | 'ptolemy5'
	leoBoundFirst: 0,         // 仅 termsVariant==1 生效:1=狮子首界主木→土
	triplicity: 'Dorothean',  // 'Dorothean' | 'Ptolemaic' | 'PtolemaicWaterVariant'
	lotReversal: 1,           // 1=福点按昼夜反转(默认) 0=恒昼式
	// ── 2026-07 二批:落宫/三态/空亡/恒星/映点升排盘级(后端 perchart 参数化;默认=后端现硬编码值)──
	houseCuspAdvance: 5,      // 落宫宫头前移(5°律):5 默认/3/1/0=纯宫界;整宫制天然豁免
	cazimiOrb: 17 / 60,       // 日心(度):传键时后端 sunPos/phase 两套统一;缺省各保现值(17′/16′)
	combustOrb: 8.5,          // 燃烧上界(度):同上(8.5/8)
	underBeamsOrb: 17,        // 日光束外界(度):sunPos 用;phase 束级恒逐星 arcus visionis
	vocMode: 'classic',       // 空亡口径:classic(=后端 lilly「无入相即空」1647)/by_orb/by_sign_perfect/by_sign_orb/kenodromia/exempt4
	vocIncludeOuter: 0,       // 1=空亡目标星集含三王星(仅非 classic 口径)
	fixedStarOrb: 1,          // 恒星合相平轨(度):后端 chart.stars 现值 1°(卜卦判读层由流派绑定,不受此默认影响)
	fixedStarOrbMode: 'school',   // 'school'=平轨 | 'byMagnitude'=按星等表(1等7.5°…)
	antisciaOrb: 1,           // 映点接触容许度(度,同座 signlon 差)
	viaCombustaVariant: 'standard',   // 燃烧之路边界:standard=195–225 传统(2026-07 由旧窄口径归正)/narrow=208–217 旧值/scorpioFull/bothFull
	partileDef: 'same_degree',        // 正相位(partile)判据:同整数度(1647)/le3/le1——主盘相位表标记列+卜卦尊贵计分共用(纯前端,不进排盘请求)
};

const INT_KEYS = ['termsVariant', 'geminiBoundEmended', 'leoBoundFirst', 'lotReversal', 'houseCuspAdvance', 'vocIncludeOuter'];
const FLOAT_KEYS = ['cazimiOrb', 'combustOrb', 'underBeamsOrb', 'fixedStarOrb', 'antisciaOrb'];
const ALL_KEYS = Object.keys(CLASSICAL_GLOBAL_DEFAULTS);

// 存储迁移:此七键 2026-07 初版曾住 divinationJudgeGlobals 仓——normalize 时若新仓缺键而旧仓有值,
// 一次性并入(读侧自愈,旧仓残键由其白名单收缩自然失效)。
const MIGRATED_FROM_JUDGE = ['cazimiOrb', 'combustOrb', 'underBeamsOrb', 'vocMode', 'vocIncludeOuter', 'fixedStarOrb', 'fixedStarOrbMode'];
const LEGACY_JUDGE_STORAGE_KEY = 'horosa.chart.divinationJudgeGlobals.v1';

let cache = null;   // 模块级缓存;写侧失效。localStorage 只读一次,热路径零 IO。

function normalize(raw){
	const out = { ...CLASSICAL_GLOBAL_DEFAULTS };
	if(!raw || typeof raw !== 'object'){ return out; }
	ALL_KEYS.forEach((k) => {
		if(raw[k] === undefined || raw[k] === null){ return; }
		if(INT_KEYS.indexOf(k) >= 0){
			const n = parseInt(raw[k] + '', 10);
			if(Number.isFinite(n)){ out[k] = n; }
		}else if(FLOAT_KEYS.indexOf(k) >= 0){
			const f = Number(raw[k]);
			if(Number.isFinite(f)){ out[k] = f; }
		}else{
			out[k] = raw[k] + '';
		}
	});
	return out;
}

// 全量读取（默认 ∪ 已存偏好）。返回新对象，调用方可安全解构。
export function getClassicalChartGlobals(){
	if(!cache){
		const raw = safeJsonParseFromStorage(CLASSICAL_GLOBALS_STORAGE_KEY) || {};
		// 一次性并入旧 judge 仓的七个迁移键(新仓缺键才并;并入后立即固化,后续读零成本)。
		const legacy = safeJsonParseFromStorage(LEGACY_JUDGE_STORAGE_KEY);
		let migrated = false;
		if(legacy && typeof legacy === 'object'){
			MIGRATED_FROM_JUDGE.forEach((k) => {
				if((raw[k] === undefined || raw[k] === null) && legacy[k] !== undefined && legacy[k] !== null){
					// 旧仓 bool 形态(vocIncludeOuter true/false) → 新仓 int 0/1(INT_KEYS 口径)。
					raw[k] = legacy[k] === true ? 1 : (legacy[k] === false ? 0 : legacy[k]);
					migrated = true;
				}
			});
		}
		cache = normalize(raw);
		if(migrated){
			safeJsonStringifyToStorage(CLASSICAL_GLOBALS_STORAGE_KEY, cache);
		}
	}
	return { ...cache };
}

// 只取「用户改过（≠默认）」的键 —— 条件透传/请求体合并用，默认态恒返回 {}（零回归自证面）。
export function classicalGlobalOverrides(){
	const g = getClassicalChartGlobals();
	const out = {};
	ALL_KEYS.forEach((k) => {
		if(g[k] !== CLASSICAL_GLOBAL_DEFAULTS[k]){ out[k] = g[k]; }
	});
	return out;
}

// 单键便捷读（getFields 播种用）。
export function classicalGlobalValue(key){
	const g = getClassicalChartGlobals();
	return g[key] !== undefined ? g[key] : CLASSICAL_GLOBAL_DEFAULTS[key];
}

// 写一键并广播（ChartDisplaySelector 专用写入口）。
export function setClassicalChartGlobal(key, value){
	if(ALL_KEYS.indexOf(key) < 0){ return; }
	const next = normalize({ ...getClassicalChartGlobals(), [key]: value });
	cache = next;
	safeJsonStringifyToStorage(CLASSICAL_GLOBALS_STORAGE_KEY, next);
	if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function'){
		try{
			window.dispatchEvent(new CustomEvent(CLASSICAL_GLOBALS_EVENT, { detail: { key, value: next[key] } }));
		}catch(e){ /* 老 WebView 无 CustomEvent 构造器时静默(下次构参仍会读到新值) */ }
	}
}

// ── 排盘请求条件透传 helper（2026-07 二批九键;六个独立构参点共用,单一真值防六处漂移）──
// 语义:仅「非默认」才产出请求键（默认不下发=请求体/缓存键零回归,后端 data.get 缺省走现硬编码值）。
// 键名映射:前端 fixedStarOrb/fixedStarOrbMode → 后端 starOrb/starOrbMode(getStars 消费名)。
// vocIncludeOuter 仅随非默认 vocMode 下发(lilly 口径后端忽略之,单独发只会白扰缓存键)。
function _neqNum(a, b){
	const n = Number(a);
	return !Number.isFinite(n) ? false : Math.abs(n - b) > 1e-9;
}

export function classicalBackendOverrides(getVal){
	const out = {};
	const v = (k) => {
		const x = getVal(k);
		return (x === undefined || x === null || x === '') ? undefined : x;
	};
	const hca = v('houseCuspAdvance');
	if(hca !== undefined){
		const n = parseInt(hca + '', 10);
		if([0, 1, 3].indexOf(n) >= 0){ out.houseCuspAdvance = n; }   // 5=默认不发
	}
	const cz = v('cazimiOrb');
	if(cz !== undefined && _neqNum(cz, 17 / 60)){ out.cazimiOrb = Number(cz); }
	const cb = v('combustOrb');
	if(cb !== undefined && _neqNum(cb, 8.5)){ out.combustOrb = Number(cb); }
	const ub = v('underBeamsOrb');
	if(ub !== undefined && _neqNum(ub, 17)){ out.underBeamsOrb = Number(ub); }
	const vm = v('vocMode');
	if(vm !== undefined && ['classic', 'lilly', 'backend'].indexOf(vm + '') < 0){
		out.vocMode = vm + '';
		const vo = v('vocIncludeOuter');
		if(vo === 1 || vo === '1' || vo === true){ out.vocIncludeOuter = 1; }
	}
	const fo = v('fixedStarOrb');
	if(fo !== undefined && _neqNum(fo, 1)){ out.starOrb = Number(fo); }
	if(v('fixedStarOrbMode') === 'byMagnitude'){ out.starOrbMode = 'byMagnitude'; }
	const ao = v('antisciaOrb');
	if(ao !== undefined && _neqNum(ao, 1)){ out.antisciaOrb = Number(ao); }
	const vcv = v('viaCombustaVariant');
	if(vcv !== undefined && vcv !== 'standard'){ out.viaCombustaVariant = vcv + ''; }
	// 三个 0/1 流派开关(默认 0 不发):点公式文档序反转 / 交点入旺 / 土星旺 20°。
	// 必须走本单源:六个构参点(主盘/13宫/12分盘/合盘/节气/卜卦)自动同步,
	// 后端 /chart、/chart13、/chart12 已按 push_request_lots_doc_reverse /
	// push_request_exalt_variants 令牌纪律接好,只等键到。
	['lotsDocReverse', 'nodeExaltation', 'saturnExalt20'].forEach((k) => {
		const x = v(k);
		if(x === 1 || x === '1' || x === true){ out[k] = 1; }
	});
	// partileDef 为纯前端键(主盘相位标记+判读计分),不进排盘请求。
	return out;
}

// fields(wrapper 形 {key:{value}}) 版:主盘 fieldsToParams / 卜卦择日壳 / 合盘 / 13宫 用。
export function classicalBackendOverridesFromFields(fields){
	return classicalBackendOverrides((k) => (fields && fields[k] && fields[k].value !== undefined ? fields[k].value : undefined));
}

// 平面对象版:节气盘 st / AstroExtraCommon params 等已拍平的参数包用。
export function classicalBackendOverridesFromPlain(plain){
	return classicalBackendOverrides((k) => (plain ? plain[k] : undefined));
}

// 测试用：清缓存（storage 由测试自理）。
export function __resetClassicalGlobalsCacheForTest(){
	cache = null;
}
