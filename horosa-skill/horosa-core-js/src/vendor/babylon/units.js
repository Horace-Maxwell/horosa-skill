// divination/babylon/units.js —— 巴比伦六十进制记号与单位系统(纯函数,零依赖)。
// 记号:分号 `;` 分隔整数与分数部,逗号 `,` 分隔各六十进制位;整数侧亦可多位
// (`2,17;4,48,53,20` = 2×60+17+4/60+… = 137.0802…)。
// 单位恒等式:1 日 = 360 UŠ = 12 bēru = 24h;1 bēru = 30 UŠ = 2h;1 UŠ = 1° = 4min = 60 NINDA;
// 1 large hour(大时) = 60 UŠ(1 日 = 6 大时);1 cubit = 24 finger(观测系 ≈2°–2.5°,图式系 = 2;30° = 180 še);
// 1 finger(食分系) = 月径 1/12 = 6 še;1 še = 0;0,50° = 50″。

// ── 六十进制解析/格式化 ──────────────────────────────────────────────
// sexParse('33;8,45') → 33.145833…;sexParse('2,17;4,48,53,20') → 137.08023…
// 容错:全整数('277' / '4,37')、负号、空白。
export function sexParse(str){
	if(typeof str === 'number'){ return str; }
	const s = String(str || '').trim();
	if(!s){ return NaN; }
	const neg = s[0] === '-' || s[0] === '−';
	const body = neg ? s.slice(1) : s;
	const parts = body.split(';');
	const intDigits = parts[0].split(',').map((x) => parseFloat(x || '0'));
	let v = 0;
	for(let i = 0; i < intDigits.length; i++){ v = v * 60 + intDigits[i]; }
	if(parts.length > 1 && parts[1] !== ''){
		const fracDigits = parts[1].split(',').map((x) => parseFloat(x || '0'));
		let scale = 1 / 60;
		for(let i = 0; i < fracDigits.length; i++){ v += fracDigits[i] * scale; scale /= 60; }
	}
	return neg ? -v : v;
}

// sexFormat(33.145833, {frac:2}) → '33;8,45';frac = 分数位数(默认 2,足以覆盖手册常数);
// intGroups=true 时整数部亦按 60 分组('137' → '2,17')。
export function sexFormat(value, opts){
	const o = opts || {};
	const frac = o.frac === undefined ? 2 : o.frac;
	const neg = value < 0;
	let v = Math.abs(value);
	// 四舍五入到最末分数位,避免 59,59,60 溢出
	const unit = Math.pow(60, -frac);
	v = Math.round(v / unit) * unit;
	let intPart = Math.floor(v + 1e-9);
	let rem = v - intPart;
	const fracDigits = [];
	for(let i = 0; i < frac; i++){
		rem *= 60;
		let d = Math.floor(rem + 1e-6);
		if(d > 59){ d = 59; }
		fracDigits.push(d);
		rem -= d;
	}
	// 去尾零
	while(fracDigits.length && fracDigits[fracDigits.length - 1] === 0){ fracDigits.pop(); }
	let intStr;
	if(o.intGroups){
		const groups = [];
		let ip = intPart;
		if(ip === 0){ groups.push(0); }
		while(ip > 0){ groups.unshift(ip % 60); ip = Math.floor(ip / 60); }
		intStr = groups.join(',');
	}else{
		intStr = String(intPart);
	}
	const out = fracDigits.length ? `${intStr};${fracDigits.join(',')}` : intStr;
	return (neg ? '−' : '') + out;
}

// ── 角度/时间单位换算 ────────────────────────────────────────────────
export const US_PER_DAY = 360;            // 1 日 = 360 UŠ
export const US_PER_BERU = 30;            // 1 bēru = 30 UŠ = 2h
export const NINDA_PER_US = 60;           // 1 UŠ = 60 NINDA
export const US_PER_LARGE_HOUR = 60;      // 1 大时 = 60 UŠ;1 日 = 6 大时
export const MINUTES_PER_US = 4;          // 1 UŠ = 4 分钟

export function usToHours(us){ return us * MINUTES_PER_US / 60; }
export function usToBeru(us){ return us / US_PER_BERU; }
export function beruToUs(beru){ return beru * US_PER_BERU; }
export function largeHoursToUs(lh){ return lh * US_PER_LARGE_HOUR; }
export function usToLargeHours(us){ return us / US_PER_LARGE_HOUR; }

// cubit(观测系):统计最佳 2.2(古代规范另有 2°/2.5° 两说);1 cubit = 24 finger。
export const CUBIT_DEFAULT = 2.2;
export function cubitToDeg(cubits, cubitDeg){ return cubits * (cubitDeg || CUBIT_DEFAULT); }
export function degToCubit(deg, cubitDeg){ return deg / (cubitDeg || CUBIT_DEFAULT); }
export function fingerToDeg(fingers, cubitDeg){ return fingers * (cubitDeg || CUBIT_DEFAULT) / 24; }

// 图式系(月亮列/微黄道):1 cubit = 2;30° = 180 še;1 še = 0;0,50°;食分 1 finger = 6 še(月径 1/12)。
export const SE_DEG = sexParse('0;0,50');            // 1 še = 50″
export const SCHEMATIC_CUBIT_DEG = 2.5;              // 图式 cubit = 2;30°
export function seToDeg(se){ return se * SE_DEG; }
export function eclipseFingerToSe(fingers){ return fingers * 6; }

// ── tithi 与年月常数 ────────────────────────────────────────────────
export const MEAN_SYNODIC_MONTH = sexParse('29;31,50,8,20');    // 29.530594… 日
export const YEAR_MONTHS_A = sexParse('12;22,8');               // 1 年(System A 截断)
export const YEAR_MONTHS_B = sexParse('12;22,8,53,20');         // 1 年(System B)
export const EPACT_TITHI = sexParse('11;4');                    // 岁余 = 371;4 − 360
export const SOLAR_RATE_TITHI_PER_DEG = sexParse('1;1,50,40');  // 太阳速率(tithi/度)
export const YEAR_TITHI = sexParse('6,11;4');                   // 371;4 tithi(30×12;22,8)

export function tithiToDays(tithi){ return tithi * MEAN_SYNODIC_MONTH / 30; }
export function daysToTithi(days){ return days * 30 / MEAN_SYNODIC_MONTH; }

// tithi 计数 →(整月, 余 tithi);monthBase = 整月基数(木/土/金 12、火 24、水 ≈3)
export function tithiToMonthsDays(totalTithi){
	const months = Math.floor(totalTithi / 30);
	const days = totalTithi - months * 30;
	return { months, tithi: days };
}

// 黄经辅助:位置 (宫1–12, 宫内度) ↔ 绝对黄经 L
export function signDegToLon(sign, deg){ return ((sign - 1) * 30 + deg) % 360; }
export function lonToSignDeg(lon){
	const L = ((lon % 360) + 360) % 360;
	return { sign: Math.floor(L / 30) + 1, deg: L % 30 };
}
export function norm360(x){ return ((x % 360) + 360) % 360; }
