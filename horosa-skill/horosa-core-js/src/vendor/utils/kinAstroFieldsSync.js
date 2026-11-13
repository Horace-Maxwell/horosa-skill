// KinAstroMain（数算/其他 11 技法宿主）fields→state 同步层。
//
// 背景：宿主在 didMount 把 props.fields 的性别与农历锚点拷进 state（性别下拉兼作「技法内临时切换」
// 控件、锚点供 演禽/南极/蠢子 编辑），但载入命例使 fields 变化时 didUpdate 原先只重取盘、不重同步
// 这些拷贝 → 一掌经/策天等载入命例后性别/锚点停留旧值（透传断链 L2）。
// 🔴 值变化检测必须基于「上次同步来源标记 prevSyncSrc」，不能用 prevProps —— dva saga 历史上就地改
// 共享 entry（prevProps.fields.gender 与 props.fields.gender 同对象），prevProps 值比对天然失明；
// 标记式对任何来源（命盘载入/事盘还原/表单编辑）一律成立。

// 性别归一：命类技法只用二元性别（男/女）；载入的命盘可能带未知性别（-1 等），而性别下拉只有
// 男/女两项 → antd 会把无匹配原始值「-1」直接显示出来。一律归「女=0，其余（含未知/-1/缺失)=男=1」，
// 与算法引擎口径一致（未知作男），杜绝显示层出现「-1」。
import { parseDateParts } from '../bazi/dateStrSafe.js';
import { Solar } from 'lunar-javascript';
import { isLunarJsYearReliable } from '../bazi/lunarDomainGuard.js';

// 公历 → 农历 {year, month(1..12,闰月按本月序), day(1..30)};域外或异常返 null(调用方退公历)。
export function solarToLunarYmd(year, month, day){
	try{
		if(!isLunarJsYearReliable(year)){ return null; }
		const lunar = Solar.fromYmd(year, month, day).getLunar();
		const m = Math.abs(lunar.getMonth());
		const d = lunar.getDay();
		if(!(m >= 1 && m <= 12) || !(d >= 1 && d <= 30)){ return null; }
		return { year: lunar.getYear(), month: m, day: d };
	}catch(_e){ return null; }
}

// 钟点 → 时支(23–1 子 … 21–23 亥)。
const HOUR_BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export function hourBranchOf(hour){
	const h = Number(hour);
	if(!Number.isFinite(h)){ return '子'; }
	return HOUR_BRANCHES[Math.floor((((h % 24) + 24) % 24 + 1) / 2) % 12];
}

// 公历时刻 → 节气月序(寅 1 … 丑 12;lunar-javascript getMonthZhiExact 按节气,含时刻);域外/异常返 null。
const JIE_MONTH_BRANCHES = ['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'];
export function solarToJieMonthIndex(year, month, day, hour, minute){
	try{
		if(!isLunarJsYearReliable(year)){ return null; }
		const h = Number.isFinite(Number(hour)) ? Number(hour) : 12;
		const mi = Number.isFinite(Number(minute)) ? Number(minute) : 0;
		const lunar = Solar.fromYmdHms(year, month, day, h, mi, 0).getLunar();
		const zhi = typeof lunar.getMonthZhiExact === 'function' ? lunar.getMonthZhiExact() : lunar.getMonthZhi();
		const idx = JIE_MONTH_BRANCHES.indexOf(zhi);
		return idx >= 0 ? idx + 1 : null;
	}catch(_e){ return null; }
}

export function normBinaryGender(g){
	const s = `${g === undefined || g === null ? '' : g}`.trim();
	return (s === '0' || s === '女' || s === 'Female' || s === 'female' || s === 'F') ? '0' : '1';
}

export function parseFieldsDateTime(fields){
	if(!fields || !fields.date || !fields.time || !fields.date.value || !fields.time.value){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	// 🔴 BC 串('-12026-07-19')裸 split('-') 会撕成 year=NaN/month=12026 —— NaN 还会让
	// resync 的相等检测(NaN!==NaN)永真,didUpdate→fetchPan 无限风暴;统一走带符号安全解析。
	const dp = parseDateParts(dateStr);
	const t = timeStr.split(':').map((item)=>parseInt(item, 10));
	if(!dp || !Number.isFinite(dp.year) || t.length < 2){
		return null;
	}
	return {
		year: dp.year,
		month: dp.month,
		day: dp.day,
		hour: t[0],
		minute: t[1],
		second: t[2] || 0,
		date: dateStr,
		time: timeStr,
		zone: fields.zone && fields.zone.value ? fields.zone.value : '',
		lat: fields.lat && fields.lat.value ? fields.lat.value : '',
		lon: fields.lon && fields.lon.value ? fields.lon.value : '',
		gender: fields.gender && fields.gender.value !== undefined ? fields.gender.value : 1,
		// 地名随载荷下发(策天 [起盘] 段「地点」行此前恒为后端占位串;缺名后端不出该行)
		pos: fields.pos && fields.pos.value ? `${fields.pos.value}` : '',
	};
}

// 计算 fields→state 重同步补丁。返回 null（无需变更）或 setState patch（恒含 fieldsSyncSrc 标记）：
// - 性别：仅当 fields 侧归一值相对上次同步真变了才覆盖 state.gender —— 技法内手动切换（只动 state、
//   不动 fields）不更新标记，因此无关的 fields 变化（时间微调等）绝不冲掉手动选择。
// - 农历锚点（演禽 lunar×3 / 南极 nanji×3 / 蠢子 chunzi×2）：仅生辰年月日变了才重排；钳位 30/31/30
//   与 didMount 原逻辑逐字一致。
// - prevSyncSrc=null（首次挂载）→ 全量同步，与原 didMount 手写块值等价。
export function computeKinFieldsResync(fields, prevSyncSrc){
	const dt = parseFieldsDateTime(fields);
	if(!dt){
		return null;
	}
	const src = { gender: normBinaryGender(dt.gender), year: dt.year, month: dt.month, day: dt.day, hour: dt.hour, minute: dt.minute };
	const genderChanged = !prevSyncSrc || prevSyncSrc.gender !== src.gender;
	const dateChanged = !prevSyncSrc || prevSyncSrc.year !== src.year || prevSyncSrc.month !== src.month || prevSyncSrc.day !== src.day;
	// 同一天只改时刻(步进小时、载入同日另一时辰的命例、交节当天跨过节气时刻):南极「手动古法」的时支与节月
	// 都随时刻定,此前只在日期变了才重填 → 时支停在旧值、盘按旧时支起。其余锚点只看日期,不动。
	const timeChanged = !prevSyncSrc || prevSyncSrc.hour !== src.hour || prevSyncSrc.minute !== src.minute;
	if(!genderChanged && !dateChanged && !timeChanged){
		return null;
	}
	const next = { fieldsSyncSrc: src };
	if(genderChanged){
		next.gender = src.gender;
	}
	if(dateChanged){
		// 农历锚点字段(演禽入式/蠢子数)此前直接灌**公历**年月日:蠢子数按「農曆月/日」匹配诗词、
		// 演禽手动农历也以此为初值 → 公历数字冒充农历。现真换算(lunar-javascript,闰月按本月序);域外(BC/万年后)才退公历。
		const lunar = solarToLunarYmd(src.year, src.month, src.day);
		next.lunarYear = lunar ? lunar.year : src.year;
		next.lunarMonth = lunar ? lunar.month : src.month;
		next.lunarDay = lunar ? lunar.day : Math.min(30, src.day);
		next.nanjiLunarYear = lunar ? lunar.year : src.year;
		// 南极「节月」= 节气月序(寅月=1 … 丑月=12,与帮助「节月即节气月序」一致),此前灌公历月 → 5 月 18 日月柱错一位(午,应巳)。
		const jieMonth = solarToJieMonthIndex(dt.year, dt.month, dt.day, dt.hour, dt.minute);
		next.nanjiSolarMonth = jieMonth || src.month;
		next.nanjiDay = Math.min(31, src.day);
		// 时支初值按出生时辰(此前恒「子」,与「空=自出」口径不符;页面恒显式下发,后端回落用不上)。
		if(Number.isFinite(Number(dt.hour))){ next.nanjiHourZhi = hourBranchOf(dt.hour); }
		next.chunziLunarMonth = lunar ? lunar.month : src.month;
		next.chunziLunarDay = lunar ? lunar.day : Math.min(30, src.day);
	}else if(timeChanged){
		const jieMonth = solarToJieMonthIndex(dt.year, dt.month, dt.day, dt.hour, dt.minute);
		next.nanjiSolarMonth = jieMonth || src.month;
		if(Number.isFinite(Number(dt.hour))){ next.nanjiHourZhi = hourBranchOf(dt.hour); }
	}
	return next;
}

export default { normBinaryGender, parseFieldsDateTime, computeKinFieldsResync };
