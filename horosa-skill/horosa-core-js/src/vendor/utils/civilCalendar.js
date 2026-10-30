// 民用历法口径单一来源(前端):儒略日 ⇄ 日期,与计算服务的 astrostudy/civil_calendar.py 逐位同口径。
//
// 全站约定:
// - 1582-10-15 起用格里历,此前一律儒略历(1582-10-04 的次日是 10-15);
// - 年份对外一律「历史纪年」:没有公元 0 年,公元前 1 年写 -1(天文年 0),公元前 300 年写 -300(天文年 -299);
// - 日期串与 formatSignedDate 同形:负年前导负号,年不足 4 位补零,5 位原样('-0300-04-09'、'0999-01-01')。
//
// JS 的 Date 恒按外推格里历 + 天文年拆日期(年份 0–99 还会被 Date.UTC 当成 1900–1999):拿它从儒略日反推
// 出生日、或拿 Date.UTC 当「当地墙钟」轴,1582 年以前差 10 天起、公元前再差一年。凡「儒略日 → 民用日期」
// 「民用日期 → 时间轴」一律经本模块。julday / revjul 是计算服务所用 Swiss Ephemeris 同名函数的逐式移植
// (同一组浮点运算),1582-10-15 以后与格里历结果逐位相同。用例表 __tests__/fixtures/civilCalendarCases.json
// 由前后端两侧的测试同读。

export const GREG_START_JD = 2299160.5;
const GREG_START_YMD = [1582, 10, 15];
// 1970-01-01 00:00 的儒略日(Unix 纪元)。
const UNIX_EPOCH_JDN = 2440588;
const MS_PER_DAY = 86400000;

export function astroYear(displayYear){
	const y = Math.trunc(Number(displayYear));
	return y < 0 ? y + 1 : y;
}

export function displayYear(astroY){
	const y = Math.trunc(Number(astroY));
	return y <= 0 ? y - 1 : y;
}

// Swiss Ephemeris swe_julday 逐式移植。greg=true 按格里历,false 按儒略历;年份为天文年。
export function julday(year, month, day, hour, greg){
	let u = Number(year);
	if(month < 3){ u -= 1; }
	const u0 = u + 4712.0;
	let u1 = Number(month) + 1.0;
	if(u1 < 4){ u1 += 12.0; }
	let jd = Math.floor(u0 * 365.25)
		+ Math.floor(30.6 * u1 + 0.000001)
		+ Number(day) + Number(hour || 0) / 24.0 - 63.5;
	if(greg){
		let u2 = Math.floor(Math.abs(u) / 100) - Math.floor(Math.abs(u) / 400);
		if(u < 0.0){ u2 = -u2; }
		jd = jd - u2 + 2;
		if((u < 0.0) && (u / 100 === Math.floor(u / 100)) && (u / 400 !== Math.floor(u / 400))){
			jd -= 1;
		}
	}
	return jd;
}

// Swiss Ephemeris swe_revjul 逐式移植 → [天文年, 月, 日, 小时浮点]。
export function revjul(jd, greg){
	let u0 = Number(jd) + 32082.5;
	if(greg){
		let u1 = u0 + Math.floor(u0 / 36525.0) - Math.floor(u0 / 146100.0) - 38.0;
		if(jd >= 1830691.5){ u1 += 1; }
		u0 = u0 + Math.floor(u1 / 36525.0) - Math.floor(u1 / 146100.0) - 38.0;
	}
	const u2 = Math.floor(u0 + 123.0);
	const u3 = Math.floor((u2 - 122.2) / 365.25);
	const u4 = Math.floor((u2 - Math.floor(365.25 * u3)) / 30.6001);
	let mon = Math.trunc(u4 - 1.0);
	if(mon > 12){ mon -= 12; }
	const day = Math.trunc(u2 - Math.floor(365.25 * u3) - Math.floor(30.6001 * u4));
	const year = Math.trunc(u3 + Math.floor((u4 - 2.0) / 12.0) - 4800);
	const ut = (jd - Math.floor(jd + 0.5) + 0.5) * 24.0;
	return [year, mon, day, ut];
}

function isGregorianYmd(astroY, month, day){
	const a = [Math.trunc(astroY), Math.trunc(month), Math.trunc(day)];
	for(let i = 0; i < 3; i++){
		if(a[i] !== GREG_START_YMD[i]){ return a[i] > GREG_START_YMD[i]; }
	}
	return true;
}

// 民用日期(天文年)+ 小时 → 儒略日。
export function civilJulday(astroY, month, day, hour){
	const y = Math.trunc(astroY); const m = Math.trunc(month); const d = Math.trunc(day);
	return julday(y, m, d, Number(hour || 0), isGregorianYmd(y, m, d));
}

// 同上,年份按历史纪年给(用户输入、日期串里的年)。
export function civilJuldayDisplay(displayY, month, day, hour){
	return civilJulday(astroYear(displayY), month, day, hour);
}

// 儒略日 → [天文年, 月, 日, 小时浮点]。
export function civilRevjul(localJd){
	return revjul(Number(localJd), Number(localJd) >= GREG_START_JD);
}

export function formatCivilDate(astroY, month, day, sep){
	const s = sep === undefined ? '-' : sep;
	const y = displayYear(astroY);
	const ys = (y < 0 ? '-' : '') + `${Math.abs(y)}`.padStart(4, '0');
	return `${ys}${s}${`${Math.trunc(month)}`.padStart(2, '0')}${s}${`${Math.trunc(day)}`.padStart(2, '0')}`;
}

// 与 Python round() 同:恰在 .5 时取偶数。
function roundHalfEven(x){
	const f = Math.floor(x);
	const diff = x - f;
	if(diff > 0.5){ return f + 1; }
	if(diff < 0.5){ return f; }
	return f % 2 === 0 ? f : f + 1;
}

// 小时浮点 → [时, 分, 秒, 进位天数];秒四舍五入,60 秒 / 60 分逐级进位,满 24 时进位到下一天。
export function splitHms(hourFloat){
	let hour = Math.trunc(hourFloat);
	const minuteFloat = (hourFloat - hour) * 60.0;
	let minute = Math.trunc(minuteFloat);
	let second = roundHalfEven((minuteFloat - minute) * 60.0);
	if(second >= 60){ second -= 60; minute += 1; }
	if(minute >= 60){ minute -= 60; hour += 1; }
	let carry = 0;
	if(hour >= 24){ carry = Math.floor(hour / 24); hour -= 24 * carry; }
	return [hour, minute, second, carry];
}

// 当地民用时刻儒略日 → { astroYear, year(历史纪年), month, day, hour, minute, second, date, time }。
export function civilPartsFromJd(localJd){
	let [y, m, d, hourFloat] = civilRevjul(localJd);
	const [hh, mi, ss, carry] = splitHms(hourFloat);
	if(carry){
		[y, m, d] = civilRevjul(Math.floor(Number(localJd) + 0.5) + carry);
	}
	const pad = (v)=>`${v}`.padStart(2, '0');
	return {
		astroYear: y,
		year: displayYear(y),
		month: m,
		day: d,
		hour: hh,
		minute: mi,
		second: ss,
		date: formatCivilDate(y, m, d),
		time: `${pad(hh)}:${pad(mi)}:${pad(ss)}`,
	};
}

// 民用日期时刻(历史纪年)→ 「墙钟毫秒」:与 Unix 毫秒同一条线性时间轴(1970-01-01 00:00 = 0),
// 所以两个墙钟毫秒相减就是真实间隔。1582-10-15 以后与 Date.UTC(年, 月 − 1, 日, 时, 分, 秒) 逐位相同;
// 此前按儒略历、公元前按历史纪年,年份 0–99 也不会被当成 1900 年代。整数天 × 86400000 + 整数毫秒,无浮点误差。
export function civilWallMs(displayY, month, day, hour, minute, second){
	const jdn = civilJuldayDisplay(displayY, month, day, 0) + 0.5;
	const tod = ((Number(hour || 0) * 60 + Number(minute || 0)) * 60 + Number(second || 0)) * 1000;
	return (jdn - UNIX_EPOCH_JDN) * MS_PER_DAY + tod;
}

// ── 整数日序(JDN,当日正午的儒略日;与 DateTime.getOnlyDateNum 同口径)──
// 「两个日期隔几天 / 某日往后数 N 天是哪天」一律在这条轴上算,不经 JS Date / moment(二者恒按外推格里历 + 天文年)。

/** 天文年(公元前 1 年 = 0)外推格里历年月日 → JDN。 */
export function gregJdnOfYmd(astroY, month, day){
	return julday(Math.trunc(astroY), Math.trunc(month), Math.trunc(day), 12, true);
}

/** JDN → 外推格里历 { astroYear, month, day }(给 JS Date / moment 构造用)。 */
export function gregYmdOfJdn(jdn){
	const [astroY, month, day] = revjul(Math.floor(Number(jdn)), true);
	return { astroYear: astroY, month, day };
}

/** 民用日期(年份按历史纪年,无 0 年)→ JDN;年为 0 / 不是数 → NaN。 */
export function civilJdnOfYmd(year, month, day){
	const y = Number(year);
	const mo = Number(month);
	const d = Number(day);
	if(!Number.isFinite(y) || y === 0 || !Number.isFinite(mo) || !Number.isFinite(d)){ return NaN; }
	return civilJuldayDisplay(y, mo, d, 12);
}

/** JDN → 民用日期 { year(历史纪年), month, day }。 */
export function civilYmdOfJdn(jdn){
	const [astroY, month, day] = civilRevjul(Math.floor(Number(jdn)));
	return { year: displayYear(astroY), month, day };
}


/** 民用日期是否真实存在(1582-10-05 … 10-14、平年 2 月 29 日、年 0 → false)。 */
export function civilYmdExists(year, month, day){
	const jdn = civilJdnOfYmd(year, month, day);
	if(!Number.isFinite(jdn)){ return false; }
	const p = civilYmdOfJdn(jdn);
	return p.year === Math.trunc(Number(year)) && p.month === Math.trunc(Number(month)) && p.day === Math.trunc(Number(day));
}

/** 显示年 year 的下一个显示年(公元前 1 年之后是公元 1 年)。 */
function nextDisplayYear(year){
	const y = Math.trunc(Number(year));
	return y === -1 ? 1 : y + 1;
}

/** 民用历某月真实存在的日号列表(1500-02 → 1…29;1582-10 → 1…4, 15…31)。月份越界 / 年为 0 → []。 */
export function civilMonthDays(year, month){
	const y = Math.trunc(Number(year));
	const m = Math.trunc(Number(month));
	if(!Number.isFinite(y) || y === 0 || !(m >= 1 && m <= 12)){ return []; }
	const a = civilJdnOfYmd(y, m, 1);
	const b = m === 12 ? civilJdnOfYmd(nextDisplayYear(y), 1, 1) : civilJdnOfYmd(y, m + 1, 1);
	const out = [];
	for(let j = a; j < b; j++){ out.push(civilYmdOfJdn(j).day); }
	return out;
}

/** 民用历某月的天数(1500-02 = 29,1582-10 = 21;替代 new Date(y, m, 0).getDate())。 */
export function civilDaysInMonth(year, month){
	return civilMonthDays(year, month).length;
}

/** 民用历某月最后一天的日号(1582-10 = 31;日期夹取用它,不用天数)。 */
export function civilLastDayOfMonth(year, month){
	const d = civilMonthDays(year, month);
	return d.length ? d[d.length - 1] : NaN;
}

/** civilWallMs 的反函数:墙钟毫秒 → { year(历史纪年), month, day, hour, minute, second, ms }。不是有限数 → null。 */
export function civilPartsFromWallMs(wallMs){
	const t = Number(wallMs);
	if(!Number.isFinite(t)){ return null; }
	const dayN = Math.floor(t / MS_PER_DAY);
	let rem = t - dayN * MS_PER_DAY;
	const p = civilYmdOfJdn(dayN + UNIX_EPOCH_JDN);
	const hour = Math.floor(rem / 3600000); rem -= hour * 3600000;
	const minute = Math.floor(rem / 60000); rem -= minute * 60000;
	const second = Math.floor(rem / 1000); rem -= second * 1000;
	return { year: p.year, month: p.month, day: p.day, hour, minute, second, ms: Math.round(rem) };
}

/** 民用历某年的天数(显示年;1500 = 366,1582 = 355)。 */
export function civilYearLength(year){
	const y = Math.trunc(Number(year));
	return civilJdnOfYmd(nextDisplayYear(y), 1, 1) - civilJdnOfYmd(y, 1, 1);
}

/** 民用日期 → 表示「真实那一天」本地 0 点的 JS Date(给只能吃 Date 的界面 / 与此刻比先后用;1582-10-15 以后与 new Date(年, 月 − 1, 日) 相同,
 *  公元 1–99 年不被当成 19xx)。读回标签必须经 civilYmdOfLocalDate,不要直接 getFullYear / getMonth / getDate。年为 0 / 不是数 → Invalid Date。 */
export function civilLocalDate(year, month, day){
	const jdn = civilJdnOfYmd(year, month, day);
	const d = new Date(0);
	if(!Number.isFinite(jdn)){ return new Date(NaN); }
	const g = gregYmdOfJdn(jdn);
	d.setFullYear(g.astroYear, g.month - 1, g.day);
	d.setHours(0, 0, 0, 0);
	return d;
}

/** civilLocalDate 的反函数:JS Date 所在的本地那一天 → 民用日期 { year(历史纪年), month, day }。 */
export function civilYmdOfLocalDate(date){
	return civilYmdOfJdn(gregJdnOfYmd(date.getFullYear(), date.getMonth() + 1, date.getDate()));
}
