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
import { CLASSICAL_PARAM_SPEC, specDefaults, specKeysByValueType } from './classicalParamSpec.js';
import { loadCustomTerms } from './customCalibreStores.js';

export const CLASSICAL_GLOBALS_STORAGE_KEY = 'horosa.chart.classicalGlobals.v1';
export const CLASSICAL_GLOBALS_EVENT = 'horosa:classical-globals-changed';

// [WP-1] 默认表/类型表由 classicalParamSpec 单源派生(此前七方手工登记漂移:viaCombustaVariant
// 漏播种、三开关漏 UI 皆实锤)。语义不变:默认值 = 现内建默认(fieldsToParams 条件透传的「不下发」侧)。
// 逐键注释(取值域/后端消费点)移居 spec 表本体;契约测试锁本表≡spec≡播种≡齿轮≡Java 白名单五方全等。
export const CLASSICAL_GLOBAL_DEFAULTS = specDefaults();

const INT_KEYS = specKeysByValueType('int');
const FLOAT_KEYS = specKeysByValueType('float');
const ALL_KEYS = Object.keys(CLASSICAL_GLOBAL_DEFAULTS);

// 存储迁移:此七键 2026-07 初版曾住 divinationJudgeGlobals 仓——normalize 时若新仓缺键而旧仓有值,
// 一次性并入(读侧自愈,旧仓残键由其白名单收缩自然失效)。
const MIGRATED_FROM_JUDGE = ['cazimiOrb', 'combustOrb', 'underBeamsOrb', 'vocMode', 'vocIncludeOuter', 'fixedStarOrb', 'fixedStarOrbMode'];
const LEGACY_JUDGE_STORAGE_KEY = 'horosa.chart.divinationJudgeGlobals.v1';

let cache = null;   // 模块级缓存;写侧失效。localStorage 只读一次,热路径零 IO。
// [SURF-R5c] 读侧自愈:全量备份「恢复」直写 localStorage 不经 setClassicalChartGlobal,
// 热 cache 恒返回旧值;更重的次生病=恢复后改任一档,set 以旧 cache 为基整包回写,把刚恢复
// 的其它键永久覆盖(重启不救)。照 customCalibreStores rawStr 比对范式:get 时原串不同即重建
// +广播;1s 节流防构参热路径(逐键 classicalGlobalValue)IO 放大——恢复场景秒级足够。
let cacheRawStr = null;
let lastRawCheckAt = 0;
function rawSelfHealCheck(){
	if(!cache){ return; }
	const now = Date.now();
	if(now - lastRawCheckAt < 1000){ return; }
	lastRawCheckAt = now;
	let rawStr = null;
	try{ rawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(CLASSICAL_GLOBALS_STORAGE_KEY) : null; }catch(e){ return; }
	if(rawStr === cacheRawStr){ return; }
	cache = null;   // 外部直写(备份恢复等):失效重建,读侧下一行重建后广播
	getClassicalChartGlobals();
	if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function'){
		try{ window.dispatchEvent(new CustomEvent(CLASSICAL_GLOBALS_EVENT, { detail: { key: '*', value: null } })); }catch(e){ /* ignore */ }
	}
}

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
	rawSelfHealCheck();
	if(!cache){
		let _rawStr = null;
		try{ _rawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(CLASSICAL_GLOBALS_STORAGE_KEY) : null; }catch(e){ _rawStr = null; }
		cacheRawStr = _rawStr;
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
			try{ cacheRawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(CLASSICAL_GLOBALS_STORAGE_KEY) : cacheRawStr; }catch(e){ /* keep */ }
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
	try{ cacheRawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(CLASSICAL_GLOBALS_STORAGE_KEY) : cacheRawStr; }catch(e){ /* keep */ }
	lastRawCheckAt = Date.now();   // 写侧刚同步,节流窗口内免重比
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

// [WP-1] spec 驱动版:逐键手写段收编为 CLASSICAL_PARAM_SPEC 循环——新键在 spec 登记
// (send:'nonDefault')即自动进本单源,不再逐键手补。判据语义与手写版逐字节等价
// (mountRequestDiff/chartGlobalsStores/natalClassicalParams 三组契约全绿自证):
// - float 键:与默认差 >1e-9 才发(数值净化 Number);
// - int 键:强转后 ≠ 默认才发(0/1 开关天然涵盖「=1 才发」);
// - str 键:字符串化 ≠ 默认(defaultAliases 同义词也算默认,vocMode 的 lilly/backend);
// - 值域校验:有 options 的键,值不在档内不发(脏值防线,较手写版更严);
// - 键名映射:spec.backendKey(fixedStarOrb→starOrb);
// - 伴发特例:vocIncludeOuter 仅随非默认 vocMode 下发(lilly 口径后端忽略之,单独发白扰缓存键);
// - partileDef 等 send:'never' 纯前端键恒不发。
export function classicalBackendOverrides(getVal){
	const out = {};
	CLASSICAL_PARAM_SPEC.forEach((s) => {
		if(s.send !== 'nonDefault'){ return; }
		let raw;
		try{ raw = getVal(s.key); }catch(e){ return; }   // [R4-P3] 单键取值炸不拖垮整包(forEach 回调里 return=跳过本键)
		// [SURF-R2b] 改名键双名回退:后端回显/params 派生链按 backendKey 存(starOrb/starOrbMode),
		// 只按前端名取=fixedStarOrb 两键在「回显形 plain 再派生」(FromPlain(chartObj.params)/
		// chartRequestKey/natalClassicalParams)恒 undefined——字符串键名双轨族第五处。前端名优先,
		// 对既有正确调用零语义变化。
		if((raw === undefined || raw === null || raw === '') && s.backendKey && s.backendKey !== s.key){
			try{ raw = getVal(s.backendKey); }catch(e){ return; }
		}
		if(raw === undefined || raw === null || raw === ''){ return; }
		let val;
		if(s.valueType === 'float'){
			val = Number(raw);
			if(!Number.isFinite(val) || !_neqNum(val, s.default)){ return; }
		}else if(s.valueType === 'int'){
			// boolean 归一(true→1/false→0):旧手写版接受 x===true,divinationJudgeGlobals 迁移值
			// 与部分 record 还原值为 bool 形态——parseInt('true')=NaN 会静默丢开。
			val = raw === true ? 1 : (raw === false ? 0 : parseInt(raw + '', 10));
			if(!Number.isFinite(val) || val === s.default){ return; }
		}else{
			val = raw + '';
			if(val === s.default){ return; }
			if(Array.isArray(s.defaultAliases) && s.defaultAliases.indexOf(val) >= 0){ return; }
		}
		if(s.options && !s.options.some((o) => o.value === val)){ return; }   // 值域外脏值不发
		out[s.backendKey || s.key] = val;
	});
	// 伴发规则:vocIncludeOuter 仅随非默认 vocMode(后端 classic/lilly 口径忽略它)。
	if(out.vocIncludeOuter !== undefined && out.vocMode === undefined){ delete out.vocIncludeOuter; }
	// [WP-7] 自定义界表附表体:termsVariant=4 时随请求带 customTermsDay/Night(后端强校验+回落埃及);
	// 本地无合法表 → 降级不发 4(等效埃及,防「选了自定义却无表」的静默怪盘)。
	if(out.termsVariant === 4){
		try{
			// [F14] 随盘表体优先(record 载入场景 getVal 能取到 customTermsDay)——换机/清仓后
			// 旧盘不再静默变埃及;无随盘表才回落本机编辑器仓;两处都无 → 降级不发 4。
			const recDay = getVal('customTermsDay');
			const recNight = getVal('customTermsNight');
			if(Array.isArray(recDay) && recDay.length === 12){
				out.customTermsDay = recDay;
				if(Array.isArray(recNight) && recNight.length === 12){ out.customTermsNight = recNight; }
			}else{
				const tbl = loadCustomTerms();
				if(tbl && tbl.day){
					out.customTermsDay = tbl.day;
					if(tbl.night){ out.customTermsNight = tbl.night; }
				}else{
					delete out.termsVariant;
				}
			}
		}catch(e){ delete out.termsVariant; }
	}
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

// [SURF-T1] 推运组件 hook 增量 merge({...state.params, ...fresh})的粘滞剔除:
// send:nonDefault 键改回默认后 fresh 不再携带,但旧 state 里的非默认值会被 merge 永久保留
// → 请求持续发已废档(返照法拨回「精确回归」后仍按希腊式取盘,真机 fiber 三证)。
// 修法=以 fresh 为「当前应发全集」,spec 键(backendKey 与 key 双名)fresh 缺席则从 merge 结果删除。
// ⚠ 入参 merged 必须是新建对象(调用点恒 {...state.params, ...fresh} 字面量)——本函数就地
// delete,直传 this.state.params 会静默突变 React state。
export function pruneStaleClassicalParams(merged, fresh){
	if(!merged){ return merged; }
	const f = fresh || {};
	CLASSICAL_PARAM_SPEC.forEach((s) => {
		[s.backendKey || s.key, s.key].forEach((name) => {
			if(f[name] === undefined && merged[name] !== undefined){
				delete merged[name];
			}
		});
	});
	// [SURF-R3p] 伴生附表键不在 spec:termsVariant 拨离自定义(4)后 fresh 无此二键,
	// 12 座死表会随每次推运请求(后端 tv≠4 门控不消费=不错盘,但请求膨胀+缓存键碎片)。
	['customTermsDay', 'customTermsNight'].forEach((name) => {
		if(f[name] === undefined && merged[name] !== undefined){ delete merged[name]; }
	});
	return merged;
}

// 测试用：清缓存（storage 由测试自理）。
export function __resetClassicalGlobalsCacheForTest(){
	cache = null;
	cacheRawStr = null;
	lastRawCheckAt = 0;
}

// [F11] 快照敏感 never 键:不进请求体(纯前端消费)但改变 AI 快照内容(显赫段/相位正列)——
// 改动必须失效旧快照,否则 AI 挂旧口径文本。签名层专用(两侧同构拼进 classicalOv JSON),
// 与请求体 overrides 严格分离(never 键恒不下发)。
const SNAPSHOT_SENSITIVE_NEVER_KEYS = ['busyPlaces', 'dynamicalDivisions', 'domicileMasterMethod', 'rayWeighting', 'partileDef'];
export function classicalSnapshotNeverSig(getVal){
	const out = {};
	SNAPSHOT_SENSITIVE_NEVER_KEYS.forEach((k) => {
		let v;
		try{ v = getVal(k); }catch(e){ return; }   // [R4-P3] 同上
		const d = CLASSICAL_GLOBAL_DEFAULTS[k];
		if(v !== undefined && v !== null && `${v}` !== `${d}`){
			out[`~${k}`] = `${v}`;   // ~ 前缀:与请求体键名空间隔离,自证不可能混进 body
		}
	});
	return out;
}

