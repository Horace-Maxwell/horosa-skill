// utils/customCalibreStores.js — [WP-7] 自定义界表 + 自定义恒星黄道槽位的持久化仓。
// 两键均已登记 storageKeyRegistry(settings/backup);safeStorage 读写,损坏自愈回默认。
import { safeJsonParseFromStorage, safeJsonStringifyToStorage } from '../gua/safeStorage.js';

export const CUSTOM_TERMS_STORAGE_KEY = 'horosa.astro.customTerms.v1';
export const CUSTOM_AYAN_STORAGE_KEY = 'horosa.astro.customAyanamsa.v1';

// ── 自定义界表:{ day: [[["jupiter",6],…]×12], night: 同形|null(null=夜同昼) } ──
export const TERMS_SIGNS_CN = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
export const TERMS_STARS = [
	{ value: 'saturn', label: '土' }, { value: 'jupiter', label: '木' }, { value: 'mars', label: '火' },
	{ value: 'venus', label: '金' }, { value: 'mercury', label: '水' },
];
// 起点模板=埃及界(与后端 EGYPTIAN_TERMS 同值;编辑器「从现档复制」的默认档)。
export const EGYPT_TEMPLATE = [
	[['jupiter', 6], ['venus', 6], ['mercury', 8], ['mars', 5], ['saturn', 5]],
	[['venus', 8], ['mercury', 6], ['jupiter', 8], ['saturn', 5], ['mars', 3]],
	[['mercury', 6], ['jupiter', 6], ['venus', 5], ['mars', 7], ['saturn', 6]],
	[['mars', 7], ['venus', 6], ['mercury', 6], ['jupiter', 7], ['saturn', 4]],
	[['jupiter', 6], ['venus', 5], ['saturn', 7], ['mercury', 6], ['mars', 6]],
	[['mercury', 7], ['venus', 10], ['jupiter', 4], ['mars', 7], ['saturn', 2]],
	[['saturn', 6], ['mercury', 8], ['jupiter', 7], ['venus', 7], ['mars', 2]],
	[['mars', 7], ['venus', 4], ['mercury', 8], ['jupiter', 5], ['saturn', 6]],
	[['jupiter', 12], ['venus', 5], ['mercury', 4], ['saturn', 5], ['mars', 4]],
	[['mercury', 7], ['jupiter', 7], ['venus', 8], ['saturn', 4], ['mars', 4]],
	[['mercury', 7], ['venus', 6], ['jupiter', 7], ['mars', 5], ['saturn', 5]],
	[['venus', 12], ['jupiter', 4], ['mercury', 3], ['mars', 9], ['saturn', 2]],
];

export function rowSum(row){
	return (row || []).reduce((s, cell) => s + (Number(cell && cell[1]) || 0), 0);
}

export function validateTermsTable(rows){
	if(!Array.isArray(rows) || rows.length !== 12){ return false; }
	return rows.every((row) => Array.isArray(row) && row.length === 5
		&& row.every((c) => Array.isArray(c) && TERMS_STARS.some((s) => s.value === c[0]) && Number(c[1]) > 0)
		&& Math.abs(rowSum(row) - 30) < 1e-9);
}

let _loadCache = null;   // { rawStr, value } —— [R2-8] 同串返回同引用,下游 memo(引用比较)才可能命中
export function loadCustomTerms(){
	let rawStr = null;
	try{ rawStr = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem(CUSTOM_TERMS_STORAGE_KEY) : null; }catch(e){ rawStr = null; }
	if(_loadCache && _loadCache.rawStr === rawStr){ return _loadCache.value; }
	const raw = safeJsonParseFromStorage(CUSTOM_TERMS_STORAGE_KEY);
	const value = (!raw || typeof raw !== 'object' || !validateTermsTable(raw.day))
		? null
		: { day: raw.day, night: validateTermsTable(raw.night) ? raw.night : null };
	_loadCache = { rawStr, value };
	return value;
}

export function saveCustomTerms(day, night){
	if(!validateTermsTable(day)){ return false; }
	safeJsonStringifyToStorage(CUSTOM_TERMS_STORAGE_KEY, {
		day, night: validateTermsTable(night) ? night : null,
	});
	return true;
}

// ── 自定义恒星黄道:{ slots: [{name, t0(JD), deg}×≤10], current: idx|null } ──
export const AYAN_MAX_SLOTS = 10;

export function loadCustomAyanamsa(){
	const raw = safeJsonParseFromStorage(CUSTOM_AYAN_STORAGE_KEY);
	if(!raw || typeof raw !== 'object' || !Array.isArray(raw.slots)){ return { slots: [], current: null }; }
	// [N2] Number(null)=0 会把「清空的 deg」洗成合法 0° 静默排盘——空值保 null 存续(编辑中的槽
	// 不消失),消费闸(currentAyanSlot)按 isFinite(Number(null))=false 拦截。
	const numOrNull = (v) => (v === null || v === undefined || `${v}` === '' ? null : (Number.isFinite(Number(v)) ? Number(v) : null));
	const slots = raw.slots.slice(0, AYAN_MAX_SLOTS).filter((s) => s && typeof s === 'object')
		.map((s) => ({ name: `${s.name || '未命名'}`, t0: numOrNull(s.t0), deg: numOrNull(s.deg) }));
	const current = Number.isInteger(raw.current) && raw.current >= 0 && raw.current < slots.length ? raw.current : null;
	return { slots, current };
}

export function saveCustomAyanamsa(store){
	safeJsonStringifyToStorage(CUSTOM_AYAN_STORAGE_KEY, {
		slots: (store.slots || []).slice(0, AYAN_MAX_SLOTS),
		current: store.current,
	});
}

// 当前槽(选中且合法)→ {t0, deg} | null。黄道下拉选「自定义」时的下发参数源。
export function currentAyanSlot(){
	const st = loadCustomAyanamsa();
	if(st.current === null || !st.slots[st.current]){ return null; }
	const slot = st.slots[st.current];
	// [R2-17][N2] 历元两参必须为正有限数——注意 Number(null)=0 连 isFinite 闸都骗得过,
	// 必须先直判 null(load 层已把空值归一为 null);t0=0 是 JD 0=公元前 4713 年,必是清空事故。
	if(slot.t0 === null || slot.deg === null || !Number.isFinite(slot.t0) || slot.t0 <= 0 || !Number.isFinite(slot.deg)){ return null; }
	return slot;
}

// 近似换算:任意日期(JD)在该槽下的 ayanamsa ≈ deg + 岁差率 × 年差(50.29″/年;
// 排盘用 SE 精确模型,本值仅供槽位管理器参考显示)。
export function approxAyanAt(slot, jd){
	if(!slot){ return null; }
	// [R4-P3] t0/deg 为 null(编辑中清空)时不产垃圾度数(jd-null=jd-0 会算出 ≈93° 的假值)。
	if(!Number.isFinite(slot.t0) || !Number.isFinite(slot.deg)){ return null; }
	const years = (jd - slot.t0) / 365.25;
	return slot.deg + (50.290966 / 3600.0) * years;
}

// [WP-7] 'user' 档随行历元参数:fields/记录有值优先,缺则读当前槽;都缺={}(后端回落 Lahiri 不炸)。
export function userAyanParamsFrom(getVal){
	const t0 = Number(getVal('userAyanT0'));
	const deg = Number(getVal('userAyanDeg'));
	if(Number.isFinite(t0) && t0 > 0 && Number.isFinite(deg)){
		return { userAyanT0: t0, userAyanDeg: deg };
	}
	const slot = currentAyanSlot();
	return slot ? { userAyanT0: slot.t0, userAyanDeg: slot.deg } : {};
}

// ── [F5] 前端消费面转换器:自定义表 → 两套既有表结构(界环/行星表用大写;判读引擎用小写) ──
const SIGNS_UPPER = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
const cap = (s)=> s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
let _dispCache = null;   // { src, upper, lower }
function buildDisplayTables(table){
	const upper = {};
	const lower = {};
	for(let i = 0; i < 12; i++){
		const row = (table && table[i]) || [];
		let acc = 0;
		const up = [];
		const lo = [];
		for(let j = 0; j < row.length; j++){
			const star = `${row[j][0] || ''}`.toLowerCase();
			const w = Number(row[j][1]) || 0;
			up.push([cap(star), acc, acc + w]);
			lo.push([star, acc, acc + w]);
			acc += w;
		}
		upper[SIGNS_UPPER[i]] = up;
		lower[SIGNS_UPPER[i].toLowerCase()] = lo;
	}
	return { upper, lower };
}
// 当前自定义界表按昼/夜取显示表;无合法表返回 null(调用方回落埃及,与后端降级同语义)。
// [R2-3] bodyDay/bodyNight:随盘/回显表体优先(chartObj.params.customTermsDay,后端算的就是它)——
// 显示层必须与计算同表,只读本机仓会在「外机载入随盘表记录」场景同屏矛盾复发。
export function customTermsDisplayTables(isDiurnal, bodyDay, bodyNight){
	let table = null;
	if(Array.isArray(bodyDay) && validateTermsTable(bodyDay) === true){
		table = (!isDiurnal && Array.isArray(bodyNight) && validateTermsTable(bodyNight) === true) ? bodyNight : bodyDay;
	}else{
		const stored = loadCustomTerms();
		if(!stored){ return null; }
		table = (!isDiurnal && stored.night) ? stored.night : stored.day;
	}
	if(!table || validateTermsTable(table) !== true){ return null; }
	if(!_dispCache || _dispCache.src !== table){
		_dispCache = { src: table, ...buildDisplayTables(table) };
	}
	return { upper: _dispCache.upper, lower: _dispCache.lower };
}
