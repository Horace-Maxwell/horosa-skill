// divination/data/egyptianSchools.js
// 埃及占星「流派切换」单一真值源:七轴口径 → 一个纯函数 deriveEgyptView(chartObj, school)。
//
// 设计铁律：
//   ① 默认档 = 现行行为逐字节零回归(EGYPT_SCHOOL_DEFAULT 各轴默认值即页面改造前的固定口径);
//   ② 纯函数、零副作用、零 React、零请求 —— 组件与 AI 段共用同一份派生结果,不各自算;
//   ③ 拿不到可采信底本的轴,只给「可算且已标注性质」的选项,绝不伪造古代数值。
//
// 七轴：旬主星制 / 旬序锚定 / 旬名录传统 / 星钟法 / 历法锚点 / Petosiris 模数 / 众神版本。
// (原拟「旬星家族」一轴因缺可采信的墓本家族底本,改以「旬名录传统」代之 —— 三套名本页内已有实数据,
//  切换只改主显名与副名次序,不臆造任何名。星钟家族差异则由「星钟法」承担。)

import {
	EGYPT_DECANS, greekDecan,
	EGYPT_DECAN_RULER_SYSTEMS, EGYPT_DECAN_RULER_DEFAULT, decanRulerAt,
	EGYPT_DECAN_ANCHORS, EGYPT_DECAN_ANCHOR_DEFAULT, decanNumberAt, decansOrderedBy,
	EGYPT_STAR_CLOCKS, EGYPT_STAR_CLOCK_DEFAULT,
	EGYPT_CALENDAR_ANCHORS, EGYPT_CALENDAR_ANCHOR_DEFAULT, egyptAnchor,
	egyptCivilFromJD, sothicPosition, jdFromGregorianYMD, gregorianFromJD,
	talismanByDecan, norm360,
} from './egyptianData.js';
import { EGYPT_GOD_EDITIONS, EGYPT_GOD_EDITION_DEFAULT, egyptianGodSign, EGYPT_GOD_BY_KEY } from './egyptianGods.js';
import { safeLocalStorageGet, safeLocalStorageSet } from '../../gua/safeStorage.js';

/* ============================================================
 * 轴定义(供设置条渲染;label/note 即界面文案的单一来源)
 * ============================================================ */

export const EGYPT_DECAN_NAMINGS = {
	egypt: { key: 'egypt', label: '埃及本名', field: 'egyptName', note: '以象形文字转写的旬名为主显名 —— 最接近古代星表原貌。' },
	coptic: { key: 'coptic', label: '科普特-希腊名', field: 'copticGreek', note: '以希腊化时期星表沿用的名形为主显名 —— 与希腊化占星文献对读最便。' },
	hermes: { key: 'hermes', label: '赫尔墨斯名', field: 'hermesName', note: '以护符文献所用的秘名系统为主显名 —— 与护符择时一节同名。' },
};
export const EGYPT_DECAN_NAMING_DEFAULT = 'egypt';

export const EGYPT_PETOSIRIS_MODS = {
	29: { key: 29, label: '29 分区', note: '以太阴月 29 日为模;残缺抄本多见此式。' },
	30: { key: 30, label: '30 分区', note: '以整 30 日为模;与民用历整月同步的一式。' },
};
export const EGYPT_PETOSIRIS_MOD_DEFAULT = 29;

// 轴清单:key = school 字段名;options 顺序即控件顺序;第一项恒为默认档。
export const EGYPT_SCHOOL_AXES = [
	{
		key: 'decanRuler', label: '旬主星制', width: 168,
		note: '三十六旬各由一星主之,主星怎么派有两制。',
		options: Object.keys(EGYPT_DECAN_RULER_SYSTEMS).map((k) => ({
			value: k, label: EGYPT_DECAN_RULER_SYSTEMS[k].label, note: EGYPT_DECAN_RULER_SYSTEMS[k].note,
		})),
	},
	{
		key: 'decanAnchor', label: '旬序锚定', width: 168,
		note: '「第几旬」从哪一旬起数 —— 黄道序自白羊起,恒星序自天狼所主之旬起。',
		options: Object.keys(EGYPT_DECAN_ANCHORS).map((k) => ({
			value: k, label: EGYPT_DECAN_ANCHORS[k].label, note: EGYPT_DECAN_ANCHORS[k].note,
		})),
	},
	{
		key: 'decanNaming', label: '旬名录传统', width: 168,
		note: '同一旬在三套名本中各有其名;此轴只决定主显名,另两名恒作副名并列,不改任何计算。',
		options: Object.keys(EGYPT_DECAN_NAMINGS).map((k) => ({
			value: k, label: EGYPT_DECAN_NAMINGS[k].label, note: EGYPT_DECAN_NAMINGS[k].note,
		})),
	},
	{
		key: 'starClock', label: '星钟法', width: 176,
		note: '夜十二时以星授时,记「升起」抑或记「上中天」,两法网格互异。',
		options: Object.keys(EGYPT_STAR_CLOCKS).map((k) => ({
			value: k, label: EGYPT_STAR_CLOCKS[k].label, note: EGYPT_STAR_CLOCKS[k].note,
		})),
	},
	{
		key: 'calendarAnchor', label: '历法锚点', width: 184,
		note: '民用历游移无闰,绝对日期全看纪元锚点;换锚点则同一日的埃及年月日随之改变。',
		options: Object.keys(EGYPT_CALENDAR_ANCHORS).map((k) => ({
			value: k, label: EGYPT_CALENDAR_ANCHORS[k].label, note: EGYPT_CALENDAR_ANCHORS[k].note,
		})),
	},
	{
		key: 'petosirisMod', label: 'Petosiris 模数', width: 160,
		note: '数字占取余的模数;两式并存。',
		options: [29, 30].map((k) => ({ value: k, label: EGYPT_PETOSIRIS_MODS[k].label, note: EGYPT_PETOSIRIS_MODS[k].note })),
	},
	{
		key: 'godEdition', label: '众神版本', width: 168,
		note: '现代通俗「埃及众神星座」的日期分段,各读物略有出入。',
		options: Object.keys(EGYPT_GOD_EDITIONS).map((k) => ({
			value: k, label: EGYPT_GOD_EDITIONS[k].label, note: EGYPT_GOD_EDITIONS[k].note,
		})),
	},
];

// 默认档 —— 逐值即页面改造前的固定口径,故默认档输出与旧版完全一致。
export const EGYPT_SCHOOL_DEFAULT = {
	decanRuler: EGYPT_DECAN_RULER_DEFAULT,          // 'chaldean' —— 等同 EGYPT_DECANS[].face
	decanAnchor: EGYPT_DECAN_ANCHOR_DEFAULT,        // 'greek'    —— 等同 EGYPT_DECANS[].greek
	decanNaming: EGYPT_DECAN_NAMING_DEFAULT,        // 'egypt'    —— 名录主显名原为埃及本名
	starClock: EGYPT_STAR_CLOCK_DEFAULT,            // 'diagonal' —— 原对角星钟表
	calendarAnchor: EGYPT_CALENDAR_ANCHOR_DEFAULT,  // 'ce139'
	petosirisMod: EGYPT_PETOSIRIS_MOD_DEFAULT,      // 29        —— 原 state.petosirisMod 初值
	godEdition: EGYPT_GOD_EDITION_DEFAULT,          // 'seamless'
};

const AXIS_VALUES = EGYPT_SCHOOL_AXES.reduce((acc, ax) => {
	acc[ax.key] = ax.options.map((o) => o.value);
	return acc;
}, {});

/** 任意输入 → 合法 school 对象(非法/缺失值一律回落默认档;绝不抛)。 */
export function normalizeEgyptSchool(raw){
	const src = raw && typeof raw === 'object' ? raw : {};
	const out = {};
	Object.keys(EGYPT_SCHOOL_DEFAULT).forEach((k) => {
		const allowed = AXIS_VALUES[k] || [];
		// petosirisMod 允许字符串数字(来自 localStorage / 控件)
		const v = k === 'petosirisMod' ? Number(src[k]) : src[k];
		out[k] = allowed.indexOf(v) >= 0 ? v : EGYPT_SCHOOL_DEFAULT[k];
	});
	return out;
}

/** 是否默认档(用于「零回归」自证与 AI 段的「非默认才标注」)。 */
export function isDefaultEgyptSchool(school){
	const s = normalizeEgyptSchool(school);
	return Object.keys(EGYPT_SCHOOL_DEFAULT).every((k) => s[k] === EGYPT_SCHOOL_DEFAULT[k]);
}

/** 非默认轴清单(用于界面/AI 段标注实际所用口径)。 */
export function egyptSchoolDiff(school){
	const s = normalizeEgyptSchool(school);
	const out = [];
	EGYPT_SCHOOL_AXES.forEach((ax) => {
		if(s[ax.key] === EGYPT_SCHOOL_DEFAULT[ax.key]){ return; }
		const opt = ax.options.find((o) => o.value === s[ax.key]);
		out.push({ key: ax.key, label: ax.label, value: s[ax.key], valueLabel: opt ? opt.label : `${s[ax.key]}` });
	});
	return out;
}

/* ============================================================
 * 盘面取值:从 chartObj 抽出派生所需的最小面
 * ============================================================ */

const POINT_IDS = ['Asc', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'MC'];

export function egyptPointsFrom(chartObj){
	const byId = {};
	if(chartObj && chartObj.chart){
		(chartObj.chart.objects || []).forEach((o) => { if(o && o.id){ byId[o.id] = o; } });
		(chartObj.chart.angles || []).forEach((a) => { if(a && a.id){ byId[a.id] = a; } });
	}
	const out = [];
	POINT_IDS.forEach((id) => {
		const o = byId[id];
		if(o && o.lon != null){ out.push({ id, lon: norm360(o.lon) }); }
	});
	return out;
}

/**
 * 出生日 → 本地民用日的 JD(该日 0h),外加公历年月日。拿不到返回 null(界面显示「—」,不猜)。
 *
 * 真实盘的日期面是 chart.date = { date:{jdn}, time:{value}, utcoffset:{value}, jd }，
 * 其中 jd 为世界时儒略日。埃及民用日按**当地**日界切分,故先加时区偏移再取整日。
 * 兼容面:老/异构调用方传 {year,month,day} 或日期串时仍走格里历换算。
 */
export function egyptBirthJD(chartObj){
	const cd = (chartObj && chartObj.chart && chartObj.chart.date) || null;
	// ① 首选:世界时 JD + 时区偏移 → 当地日 0h(与排盘同一时刻源,无二次换算误差)
	if(cd && Number.isFinite(Number(cd.jd))){
		const off = cd.utcoffset && Number.isFinite(Number(cd.utcoffset.value)) ? Number(cd.utcoffset.value) : 0;
		const localJD = Number(cd.jd) + off / 24;
		const jd = Math.floor(localJD + 0.5) - 0.5;      // 当地民用日 0h
		const g = gregorianFromJD(jd);
		return g ? { jd, year: g.year, month: g.month, day: g.day } : null;
	}
	// ② 次选:后端已给的当地民用日 JDN
	if(cd && cd.date && Number.isFinite(Number(cd.date.jdn))){
		const jd = Number(cd.date.jdn) - 0.5;
		const g = gregorianFromJD(jd);
		return g ? { jd, year: g.year, month: g.month, day: g.day } : null;
	}
	// ③ 兼容:{year,month,day} 或日期串
	const d = (chartObj && chartObj.date) || null;
	let y; let m; let dd;
	if(d && typeof d === 'object'){
		y = Number(d.year); m = Number(d.month); dd = Number(d.day);
	}
	if(!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(dd)){
		const s = (chartObj && (chartObj.dateText || chartObj.birthDate)) || '';
		const mm = `${s}`.match(/(-?\d{1,6})[-/](\d{1,2})[-/](\d{1,2})/);
		if(mm){ y = Number(mm[1]); m = Number(mm[2]); dd = Number(mm[3]); }
	}
	if(!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(dd)){ return null; }
	if(m < 1 || m > 12 || dd < 1 || dd > 31){ return null; }
	return { jd: jdFromGregorianYMD(y, m, dd), year: y, month: m, day: dd };
}

/* ============================================================
 * 单一真值源:deriveEgyptView(chartObj, school)
 * ------------------------------------------------------------
 * 组件各 tab 与 AI 段一律从这里取值,不再各自算。
 * ============================================================ */

export function deriveEgyptView(chartObj, school){
	const s = normalizeEgyptSchool(school);
	const namingField = (EGYPT_DECAN_NAMINGS[s.decanNaming] || EGYPT_DECAN_NAMINGS[EGYPT_DECAN_NAMING_DEFAULT]).field;

	// —— 旬表(按锚定排序 + 按流派派主星 + 按名录传统定主显名)
	const decans = decansOrderedBy(s.decanAnchor).map((d) => ({
		...d,
		number: decanNumberAt(d, s.decanAnchor),           // 该锚定下的「第几旬」
		ruler: decanRulerAt(d, s.decanRuler),              // 该制下的旬主星
		primaryName: d[namingField] || d.egyptName,        // 主显名
		altNames: ['egyptName', 'copticGreek', 'hermesName']
			.filter((f) => f !== namingField).map((f) => d[f]).filter(Boolean),
	}));
	const byGreek = {};
	decans.forEach((d) => { byGreek[d.greek] = d; });

	// —— 本盘各点落旬
	const points = egyptPointsFrom(chartObj).map((p) => {
		const d = byGreek[greekDecan(p.lon)] || null;
		return { ...p, decan: d };
	});
	const asc = points.find((p) => p.id === 'Asc') || null;
	const ascDecan = asc ? asc.decan : null;
	const ascTalisman = ascDecan ? talismanByDecan(ascDecan.greek) : null;

	// —— 民用历 / Sothic
	const anchor = egyptAnchor(s.calendarAnchor);
	const birth = egyptBirthJD(chartObj);
	const civil = birth ? egyptCivilFromJD(birth.jd, anchor.jd) : null;
	const sothic = birth ? sothicPosition(birth.jd, anchor.jd) : null;

	// —— 天狼偕日升(Python 已算,此处只回显与对差,不自算)
	const eg = (chartObj && chartObj.egyptianCalendar) || null;
	const siriusRising = eg && eg.siriusRising ? `${eg.siriusRising}` : '';
	let siriusDeltaDays = null;
	if(birth && siriusRising){
		const mm = siriusRising.match(/(-?\d{1,6})-(\d{1,2})-(\d{1,2})/);
		if(mm){
			const sjd = jdFromGregorianYMD(Number(mm[1]), Number(mm[2]), Number(mm[3]));
			siriusDeltaDays = Math.round(birth.jd - sjd);
		}
	}

	// —— 众神(现代体系;取出生公历月日)
	const godKey = birth ? egyptianGodSign(birth.month, birth.day, s.godEdition) : '';
	const god = godKey ? EGYPT_GOD_BY_KEY[godKey] || null : null;

	return {
		school: s,
		isDefault: isDefaultEgyptSchool(s),
		diff: egyptSchoolDiff(s),
		decans, byGreek, namingField,
		points, asc, ascDecan, ascTalisman,
		anchor, birth, civil, sothic,
		sirius: { date: siriusRising, deltaDays: siriusDeltaDays },
		god, godKey,
		starClock: EGYPT_STAR_CLOCKS[s.starClock] || EGYPT_STAR_CLOCKS[EGYPT_STAR_CLOCK_DEFAULT],
		petosirisMod: s.petosirisMod,
	};
}

/* ============================================================
 * 持久化(safeStorage;缺失/损坏一律回默认档)
 * ============================================================ */

export const EGYPT_SCHOOL_STORAGE_KEY = 'horosa.egypt.school.v1';

export function readEgyptSchool(storage){
	try{
		const raw = storage && storage.getItem ? storage.getItem(EGYPT_SCHOOL_STORAGE_KEY) : null;
		return normalizeEgyptSchool(raw ? JSON.parse(raw) : null);
	}catch(e){
		return normalizeEgyptSchool(null);
	}
}

export function writeEgyptSchool(storage, school){
	try{
		if(storage && storage.setItem){
			storage.setItem(EGYPT_SCHOOL_STORAGE_KEY, JSON.stringify(normalizeEgyptSchool(school)));
		}
	}catch(e){ /* 配额/隐私模式:静默 */ }
	return normalizeEgyptSchool(school);
}

/* ============================================================
 * 命盘随盘保真(record 面):七轴以 egypt_<axis> 七键落库/回放。
 * ------------------------------------------------------------
 * 目的:同一命例两次打开,【埃及历】段口径不随「当前全局设置」漂移 ——
 * 与其余古典键(termsVariant 等)「随盘保真」同口径。
 *  · 存盘:全局非默认的轴才落键(默认档不落 = 旧记录语义不变,零回归);
 *  · 回放:七键进 fields;快照链(AI 导出/挂载/报告)优先读 fields,缺键回落全局;
 *  · 页面(AstroEgypt)仍吃全局显示偏好,不受单条记录钳制。
 * ============================================================ */
export const EGYPT_RECORD_KEY_PREFIX = 'egypt_';
export const EGYPT_RECORD_KEYS = Object.keys(EGYPT_SCHOOL_DEFAULT).map((k) => EGYPT_RECORD_KEY_PREFIX + k);

/** 存盘捕获:返回 {egypt_<axis>: value} —— 仅含与默认档不同的轴;全默认返回 {}。 */
export function egyptSchoolToRecordValues(school){
	const s = normalizeEgyptSchool(school);
	const out = {};
	Object.keys(EGYPT_SCHOOL_DEFAULT).forEach((k) => {
		if(s[k] !== EGYPT_SCHOOL_DEFAULT[k]){ out[EGYPT_RECORD_KEY_PREFIX + k] = s[k]; }
	});
	return out;
}

/** 回放读取:fields 里任一 egypt_* 键在 → 组出该记录的流派(缺轴回默认);一个都不在 → null(调用方回落全局)。 */
export function egyptSchoolFromFields(fields){
	if(!fields){ return null; }
	let any = false;
	const raw = {};
	Object.keys(EGYPT_SCHOOL_DEFAULT).forEach((k) => {
		const f = fields[EGYPT_RECORD_KEY_PREFIX + k];
		const v = f && f.value !== undefined && f.value !== null && f.value !== '' ? f.value : undefined;
		if(v !== undefined){ any = true; raw[k] = v; }
	});
	return any ? normalizeEgyptSchool(raw) : null;
}

// 走 safeStorage 的默认通道(配额/隐私模式静默降级);组件与 AI 快照共用同一份口径。
export const EGYPT_SCHOOL_STORE = {
	getItem: (k) => safeLocalStorageGet(k),
	setItem: (k, v) => safeLocalStorageSet(k, v),
};
export function currentEgyptSchool(){ return readEgyptSchool(EGYPT_SCHOOL_STORE); }
export function persistEgyptSchool(school){ return writeEgyptSchool(EGYPT_SCHOOL_STORE, school); }
