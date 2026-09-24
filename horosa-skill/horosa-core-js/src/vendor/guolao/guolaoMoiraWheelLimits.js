// 七政四余「命度 → 百六大限」算法闭包 —— 自上游 components/guolao/GuoLaoMoiraWheel.js **逐字**抽出
// （bespoke，derived_from + derived_sha256 看守：上游 GuoLaoMoiraWheel.js 一动即红，复核本文件后 --restamp）。
// 上游该文件是 2485 行的 SVG 轮盘 React 组件，纯算法（buildGuolaoLimitTable / birthYearBasis / currentLimitIndex /
// lifeDegree 及其依赖）与 JSX 同居，整份 vendor 不可行。消费方：guolaoInfoFacts.js（[三主与化曜]/[限法实算] 事实层）
// 与 guolaoSnapshotSections.js（[大限] 段）—— 与上游 GuoLaoMoiraPanel / GuoLaoChartMain 的 import 同源。
// 下方 GUOLAO_LIFE_MODE_* / GUOLAO_DIZHI / normalizeGuolaoLifeMode 逐字取自上游 GuoLaoChartStyle.js；
// getStoredGuolaoLifeMode 是 headless 缺省（上游读 localStorage 偏好，缺省 = 占星上升 asc）。
import * as AstroConst from '../../constants/AstroConst.js';
import { childYearsSpan } from './guolaoMoiraTables.js';
import { buildLocalJieqiYearSeed } from '../../shared/localNongliAdapter.js';

export const GUOLAO_LIFE_MODE_ASC = 'asc';
export const GUOLAO_LIFE_MODE_YUMAO = 'yumao';       // 日出安命(实际日出)
export const GUOLAO_LIFE_MODE_COTRANS = 'cotrans';
export const GUOLAO_LIFE_MODE_GUMAO = 'gumao';       // 遇卯安命(古法时加太阳顺数至卯)
export const GUOLAO_DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export function normalizeGuolaoLifeMode(val){
	if(val === GUOLAO_LIFE_MODE_YUMAO){
		return GUOLAO_LIFE_MODE_YUMAO;
	}
	if(val === GUOLAO_LIFE_MODE_COTRANS){
		return GUOLAO_LIFE_MODE_COTRANS;
	}
	if(val === GUOLAO_LIFE_MODE_GUMAO){
		return GUOLAO_LIFE_MODE_GUMAO;
	}
	// R2 自定命宫:命度法值=地支(子~亥)即手动命宫,后端按地支当 custom 算。
	if(GUOLAO_DIZHI.indexOf(val) >= 0){
		return val;
	}
	return GUOLAO_LIFE_MODE_ASC;
}
// headless：无 localStorage 偏好 → 上游缺省（GuoLaoChartStyle.getStoredGuolaoLifeMode 读不到键时同此）。
const getStoredGuolaoLifeMode = ()=>GUOLAO_LIFE_MODE_ASC;

const LIMIT_SEQ = [11.0, 10.0, 11.0, 15.0, 8.0, 7.0, 11.0, 4.5, 4.5, 4.5, 5.0, 5.0];

const HOUSE_BRANCH = ['命宫', '财帛', '兄弟', '田宅', '男女', '奴仆', '夫妻', '疾厄', '迁移', '官禄', '福德', '相貌'];

function norm(deg){
	let val = Number(deg);
	if(!Number.isFinite(val)){
		return 0;
	}
	val %= 360;
	if(val < 0){
		val += 360;
	}
	return val;
}

function objectRa(obj, preferLon = false){
	const num = Number(obj && (preferLon && obj.lon !== undefined ? obj.lon : (obj.ra !== undefined ? obj.ra : obj.lon)));
	return Number.isFinite(num) ? num : null;
}

function isZhengSiderealChart(chart){
	const params = chart && chart.params ? chart.params : {};
	return Number(params.doubingSu28) === 4 || Number(params.guolaoZhengSidereal) === 1;
}

// 黄仪/赤仪显示口径(单一真值源=chart.displayCoord,python 按宿度制 byLon/byRA 分派宣告):
// 黄仪(回归今宿/开禧/恒星制/授时历古法)→全黄经显示;赤仪(荀爽/斗柄/赤道恒星/赤道回归)→全赤经。
// 旧 chart 无该字段时回退旧判据(仅恒星制郑式=黄经),平滑兼容。
function isEclipticDisplayChart(chart){
	const coord = chart && chart.displayCoord;
	if(coord === 'ecliptic'){ return true; }
	if(coord === 'equatorial'){ return false; }
	return isZhengSiderealChart(chart);
}

function findObject(chart, id){
	const objects = chart && chart.objects ? chart.objects : [];
	return objects.find((obj)=>obj.id === id);
}

function lifeModeFromFields(fields){
	if(fields && fields.guolaoLifeMode && fields.guolaoLifeMode.value !== undefined && fields.guolaoLifeMode.value !== null){
		return normalizeGuolaoLifeMode(fields.guolaoLifeMode.value);
	}
	return getStoredGuolaoLifeMode();
}

function lifeDegree(chart, fields, forceLon){
	const life = findObject(chart, AstroConst.LIFEMASTERDEG74);
	const asc = findObject(chart, AstroConst.ASC);
	const sun = findObject(chart, AstroConst.SUN);
	const lifeMode = lifeModeFromFields(fields);
	// R: 除「占星上升」外(asc 直接用上升点),日出/赤黄/古法遇卯/自定命宫(地支)均以 BaZi 算出的 LifeMasterDeg74 为命度起宫。
	const useLifeMaster = lifeMode !== GUOLAO_LIFE_MODE_ASC;
	// forceLon=true:恒取黄经命度(供 12 宫/地支/小限飞限用,宫位系黄道划分,不随宿度制显示坐标变)。
	const preferLon = forceLon === true ? true : isEclipticDisplayChart(chart);
	const primary = useLifeMaster ? objectRa(life, preferLon) : objectRa(asc, preferLon);
	const secondary = useLifeMaster ? objectRa(asc, preferLon) : objectRa(life, preferLon);
	const val = primary !== null ? primary : (secondary !== null ? secondary : objectRa(sun, preferLon));
	return val === null ? 0 : val;
}

// 限度逐宫年数:首宫=童限(不四舍,base 由定童限 9/10),其余=limit_seq[1..11](照 Moira addChildYearToBirthDate / limit_seq[i])。
function limitSegments(life, childBase){
	return [childYearsSpan(life, childBase)].concat(LIMIT_SEQ.slice(1));
}

// [Q-188/T-125] 年界基准全量:{ frac 出生在年界内已历年分数, yearShift 岁次年号相对公历出生年的偏移 }。
// 立春界:立春前生人岁次属上一年(yearShift=-1);冬至界(天正建子):冬至后生人岁次属下一年(+1);公历元旦恒 0。
// 此前立春/冬至两档要 chart.nongli.jieqi 的 lichun/dongzhi 字段,后端恒 null → 静默回退元旦(死档);
// 现由本地节气表(lunar-javascript,AD1–9999)精算年界时刻,缺表仍回退元旦。
function birthYearBasis(chart, fields, mode){
	let Y; let Mo; let D; let h = 0; let mi = 0; let s = 0;
	const pd = chart && chart.params && chart.params.date;
	const pt = chart && chart.params && chart.params.time;
	if(pd){ const m = `${pd}`.match(/(-?\d+)\D+(\d+)\D+(\d+)/); if(m){ Y = +m[1]; Mo = +m[2]; D = +m[3]; } }
	if(pt){ const m = `${pt}`.match(/(\d+):(\d+)(?::(\d+))?/); if(m){ h = +m[1]; mi = +m[2]; s = +(m[3] || 0); } }
	if(!Number.isFinite(Y) && fields && fields.date && fields.date.value && typeof fields.date.value.year === 'function'){
		const dv = fields.date.value;
		Y = dv.year(); Mo = dv.month() + 1; D = dv.date();
		const tv = fields.time && fields.time.value;
		if(tv && typeof tv.hour === 'function'){ h = tv.hour(); mi = tv.minute(); s = tv.second(); }
	}
	// 🔴 第三来源(最可靠·后端排盘产出):chart.date = {jd, date:{jdn}, time:{value}, utcoffset:{value}}。
	// wheel 收到的 chart 常无 params(root.params 缺→graft 落空)、fields.date.value 也非 moment,
	// 前两路都取不到出生日 → birthFrac 静默算成 0 → 百六大限整体差 1 岁(寅卯宫界/环最大岁数)。
	// jd 为 UT 儒略日,+utcoffset 得当地墙钟毫秒(以 UTC 读取即当地历字段),照 Moira work_cal(当地时区)。
	if(!Number.isFinite(Y) && chart && chart.date && Number.isFinite(Number(chart.date.jd))){
		const jd = Number(chart.date.jd);
		const off = chart.date.utcoffset && Number.isFinite(Number(chart.date.utcoffset.value)) ? Number(chart.date.utcoffset.value) : 0;
		const localMs = (jd - 2440587.5) * 86400000 + off * 3600000;
		if(Number.isFinite(localMs)){
			const d = new Date(localMs);
			Y = d.getUTCFullYear(); Mo = d.getUTCMonth() + 1; D = d.getUTCDate();
			h = d.getUTCHours(); mi = d.getUTCMinutes(); s = d.getUTCSeconds();
		}
	}
	if(!Number.isFinite(Y) || !Number.isFinite(Mo) || !Number.isFinite(D)){ return { frac: 0, yearShift: 0 }; }
	const MS_YEAR = 365.25 * 24 * 60 * 60 * 1000;
	const birthMs = Date.UTC(Y, Mo - 1, D, h, mi, s);
	// 年界起点(默认公历元旦;立春/冬至由 solarTermBoundaryMs 提供,缺则元旦)。
	let boundaryMs = Date.UTC(Y, 0, 1, 0, 0, 0);
	let yearShift = 0;
	if(mode === 'lichun' || mode === 'dongzhi'){
		const b = solarTermBoundaryMs(chart, Y, birthMs, mode, chartZoneHours(chart, fields));
		if(Number.isFinite(b.ms)){ boundaryMs = b.ms; yearShift = b.yearShift; }
	}
	let frac = (birthMs - boundaryMs) / MS_YEAR;
	if(!Number.isFinite(frac)){ return { frac: 0, yearShift: 0 }; }
	// 归一到 [0,1)(立春/冬至基准时出生可能落在年界前)。
	frac = ((frac % 1) + 1) % 1;
	return { frac, yearShift };
}

// 盘时区(小时):params.zone '+08:00' → fields.zone/date.zone → chart.date.utcoffset;缺则 +8(本地节气表基准,零换算)。
function chartZoneHours(chart, fields){
	const parseZone = (z)=>{
		if(z == null || z === ''){ return NaN; }
		if(typeof z === 'number'){ return z; }
		const m = `${z}`.match(/^([+-])?(\d{1,2})(?::?(\d{2}))?$/);
		if(!m){ return NaN; }
		const v = Number(m[2]) + (m[3] ? Number(m[3]) / 60 : 0);
		return m[1] === '-' ? -v : v;
	};
	const cands = [
		chart && chart.params && chart.params.zone,
		fields && fields.zone && fields.zone.value,
		fields && fields.date && fields.date.value && fields.date.value.zone,
		chart && chart.date && chart.date.utcoffset && chart.date.utcoffset.value,
	];
	for(let i = 0; i < cands.length; i++){
		const v = parseZone(cands[i]);
		if(Number.isFinite(v)){ return v; }
	}
	return 8;
}

// [Q-188/T-125] 本地节气表取某公历年的立春/冬至时刻(表值为 +08:00 墙钟)→ 换到盘时区墙钟毫秒(与 birthMs 同域,UTC 读取)。
function localTermWallMs(year, term, zoneHours){
	// 本地表按「农历年」建表:键「冬至」= 该年之前一个冬至(Y−1 年 12 月),故取公历 Y 年 12 月冬至须查 Y+1 年表(实证 2005–2007 三年)。
	const seedYear = term === '冬至' ? year + 1 : year;
	let seed = null;
	try{ seed = buildLocalJieqiYearSeed(seedYear, null); }catch(e){ seed = null; }
	const t = seed && seed[term] && seed[term].time ? `${seed[term].time}` : '';
	const m = t.match(/(-?\d+)-(\d+)-(\d+)\D+(\d+):(\d+)(?::(\d+))?/);
	if(!m){ return NaN; }
	const cstMs = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
	return cstMs + (zoneHours - 8) * 3600000;
}

// 立春/冬至 年界(增强项):chart.nongli 若给出 lichun/dongzhi 时刻优先;否则本地节气表精算;皆缺返回 NaN 让调用方回退公历元旦。
// 返回 { ms 年界墙钟毫秒, yearShift 岁次年号偏移 }:立春界取「≤出生」的最近一次立春(立春前生人=上一年立春,yearShift −1);
// 冬至界取「≤出生」的最近一次冬至(冬至后生人年界=本年冬至,天正岁次属下一年 +1;冬至前生人=上一年冬至,岁次=本年 0)。
function solarTermBoundaryMs(chart, year, birthMs, mode, zoneHours){
	const key = mode === 'dongzhi' ? 'dongzhi' : 'lichun';
	const term = mode === 'dongzhi' ? '冬至' : '立春';
	const jq = chart && chart.nongli && (chart.nongli.jieqi || chart.nongli.solarTerms);
	const parse = (v)=>{
		if(v == null){ return NaN; }
		if(typeof v === 'number'){ return v; }
		const m = `${v}`.match(/(-?\d+)\D+(\d+)\D+(\d+)(?:\D+(\d+)\D+(\d+))?/);
		return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0)) : NaN;
	};
	const zh = Number.isFinite(zoneHours) ? zoneHours : 8;
	// 本年该节气时刻:chart 显式字段优先,否则本地节气表。
	let cur = (jq && typeof jq === 'object') ? parse(jq[key]) : NaN;
	if(!Number.isFinite(cur)){ cur = localTermWallMs(year, term, zh); }
	if(!Number.isFinite(cur)){ return { ms: NaN, yearShift: 0 }; }
	if(cur <= birthMs){
		// 出生在本年节气之后:年界=本年节气。冬至界天正岁次属下一年。
		return { ms: cur, yearShift: mode === 'dongzhi' ? 1 : 0 };
	}
	// 出生在本年节气之前:年界=上一年节气(本地表精算;缺表回退 −365.25 日近似)。
	let prev = localTermWallMs(year - 1, term, zh);
	if(!Number.isFinite(prev)){ prev = cur - 365.25 * 24 * 60 * 60 * 1000; }
	return { ms: prev, yearShift: mode === 'lichun' ? -1 : 0 };
}

// 大限表（古度限度法，与年龄环同一套 limitSegments → 二者必然一致）：
// 自命宫起逐宫一段，每段年数取 limitSegments(life)，首段=命度入宫度推算。
// [Q-188/T-125] birthFrac(年界内已历年分数,照 Moira val=age−1−birthFrac)可选:与岁数带同口径;缺省 0 = 旧表逐字不变。
// birthYear 由调用方按年界基准传入岁次年号(公历年 + yearShift)。
function buildGuolaoLimitTable(life, birthYear, childBase, birthFrac){
	const segs = limitSegments(life, childBase);
	const rows = [];
	let age = 1 + (Number.isFinite(Number(birthFrac)) ? Number(birthFrac) : 0);
	for(let k = 0; k < 12; k++){
		const span = Math.max(0.5, segs[k] || 0);
		const fromAge = Math.round(age);
		const toAge = Math.round(age + span) - 1;
		rows.push({
			index: k + 1,
			palace: HOUSE_BRANCH[k],
			years: Math.round(span * 10) / 10,
			fromAge,
			toAge,
			fromYear: birthYear + fromAge - 1,
			toYear: birthYear + toAge - 1,
		});
		age += span;
	}
	return rows;
}

function currentLimitIndex(rows, age){
	if(!Array.isArray(rows) || !Number.isFinite(age)){
		return -1;
	}
	for(let i = 0; i < rows.length; i++){
		if(age >= rows[i].fromAge && age <= rows[i].toAge){
			return i;
		}
	}
	return -1;
}

export {
	buildGuolaoLimitTable as moiraBuildLimitTable,
	birthYearBasis as moiraBirthYearBasis,
	currentLimitIndex as moiraCurrentLimitIndex,
	lifeDegree as moiraLifeDegree,
};
