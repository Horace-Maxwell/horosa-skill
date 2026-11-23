// 辅盘七张派生盘(十三分 / 十二分 / 调波 / 龙盘 / 重置盘 / 变换盘 / 黄道制)的无头复算:辅盘页没对这张盘出过图时
// (或出的是别的命主、或出图时的参数与此刻要的不同),AI 挂载 / 外部智能体直接请求后端,正文与页面出盘即存的快照同一份构建函数。
// 参数:调波数 / 龙盘宫位口径 / 重置地点取挂载设置(记录上的同名键),没设 = 页面缺省(调波 9、龙盘宫位口径取辅盘页保存值、重置地点 = 出生地);
// 变换盘 / 黄道制取辅盘页保存的设置。页面侧模块按需动态载入:不把辅盘页的依赖拉进 AI 上下文的静态链。




import { clampHarmonic, HARMONIC_DEFAULT, DRACONIC_HOUSE_MODES, harmonicSnapshotLines, draconicSnapshotLines, relocationSnapshotSpecialty, withNatalPlanetSign } from '../derivedAstroLabs.js';



export const DERIVED_LAB_HEADLESS_KEYS = ['hellenastro', 'dwadasamsa', 'harmonic', 'draconic', 'relocation', 'transformchart', 'zodiacsystems'];

// 这张派生盘「此刻要按什么参数出」(只列带参数的三张;其余回 null)。与页面出盘即存时记的 meta.derivedParams 同形,两边能直接比。
// 龙盘宫位口径没在记录上设 = 辅盘页保存值(读不到 = 整宫);重置地点没设或不成对 = null(按出生地出,与本命同)。
const finiteNum = (v)=>(v !== undefined && v !== null && `${v}` !== '' && Number.isFinite(Number(v)) ? Number(v) : null);
export function derivedParamsFor(key, record, draconicPageMode){
	const r = record || {};
	if(key === 'harmonic'){ return { harmonic: clampHarmonic(r.harmonic, HARMONIC_DEFAULT) }; }
	if(key === 'draconic'){
		const own = DRACONIC_HOUSE_MODES.indexOf(r.draconicHouses) >= 0 ? r.draconicHouses : '';
		return { draconicHouses: own || (DRACONIC_HOUSE_MODES.indexOf(draconicPageMode) >= 0 ? draconicPageMode : 'whole') };
	}
	if(key === 'relocation'){
		// 只给了一个:另一个取出生地(只换纬度 / 只换经度也是合法的问法)
		let lat = finiteNum(r.relocLat); let lon = finiteNum(r.relocLon);
		if(lat === null && lon !== null){ lat = finiteNum(r.gpsLat); }
		if(lon === null && lat !== null){ lon = finiteNum(r.gpsLon); }
		return lat !== null && lon !== null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { relocLat: Number(lat.toFixed(4)), relocLon: Number(lon.toFixed(4)) } : null;
	}
	return null;
}
// 变换盘 / 黄道制:记录上有生效的单次覆盖(与辅盘页保存值不同)时回一个「要现算」的标记;没有回 null(页面出过用页面的)
export function derivedOverrideFor(key, record){
	try{
		const tc = __req0;
		if(key === 'transformchart'){ const r = tc.transformSettingsFor(record, tc.TRANSFORM_PAGE_SETTINGS.load()); return r.overridden ? { override: JSON.stringify(r.settings) } : null; }
		if(key === 'zodiacsystems'){ const r = tc.zodiacSettingsFor(record, tc.ZODIAC_PAGE_SETTINGS.load()); return r.overridden ? { override: JSON.stringify(r.settings) } : null; }
	}catch(e){ /* 读不到页面设置:按没有覆盖 */ }
	return null;
}
// 记录上明写了这张盘的参数(挂载设置 / 外部智能体单次指定)
export function derivedParamsExplicit(key, record){
	const r = record || {};
	const has = (v)=>v !== undefined && v !== null && `${v}` !== '';
	if(key === 'harmonic'){ return has(r.harmonic); }
	if(key === 'draconic'){ return DRACONIC_HOUSE_MODES.indexOf(r.draconicHouses) >= 0; }
	if(key === 'relocation'){ return has(r.relocLat) || has(r.relocLon); }
	return false;
}
// 页面快照记的参数与此刻要的是否同一组(没有要比的 = 同;页面快照没记参数 = 不同,宁可现算)
export function sameDerivedParams(saved, wanted){
	if(!wanted){ return true; }
	if(!saved || typeof saved !== 'object'){ return false; }
	return Object.keys(wanted).every((k)=>`${saved[k]}` === `${wanted[k]}`);
}
// 取辅盘页保存的龙盘宫位口径(页面模块按需载入;读不到回 '')
export function draconicPageHouseMode(){
	return '';   // headless：没有「辅盘页已存的龙盘设置」（口径由调用方显式传）——即上游读不到时的回退值
}

// 变换盘只发这种变换真正用到的选项(与辅盘页 AstroTransformLab.requestOptions 同口径)
export function transformRequestOptions(settings, kindDef){
	const { kind, planet, shift, house, variant } = settings || {};
	const options = (kindDef && kindDef.options) || [];
	const out = { transformKind: kind };
	if(options.indexOf('planet') >= 0){ out.transformPlanet = planet; }
	if(options.indexOf('shift') >= 0){ out.transformShift = shift ? 1 : 0; }
	if(options.indexOf('house') >= 0){ out.transformHouse = house; }
	if(options.indexOf('variant') >= 0){ out.transformVariant = variant; }
	return out;
}
