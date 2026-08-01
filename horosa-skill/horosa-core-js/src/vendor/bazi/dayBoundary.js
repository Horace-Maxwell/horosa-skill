// 日界点全局偏好的取值与映射。
// 用户语义（拍板，字面直觉版，配套自检 27日23:30）：
//   'after23'（默认）「23点算第二天」= 23点起日柱进位次日(壬寅)
//   'after24'           「24点算第二天」= 23点仍守今、24点才换日柱(辛丑)
// 时柱跨日永远按"次日日干"起子时(=庚子,与 lunar.js Exact 一致)。
export const DAY_BOUNDARY_AFTER23 = 'after23';
export const DAY_BOUNDARY_AFTER24 = 'after24';

export function normalizeDayBoundary(value){
	return value === DAY_BOUNDARY_AFTER24 ? DAY_BOUNDARY_AFTER24 : DAY_BOUNDARY_AFTER23;
}

// 映射到既有的 after23NewDay 开关：
//   1 = 「23点算第二天」= 日柱进位次日(壬寅)
//   0 = 「24点算第二天」= 日柱守今(辛丑)
export function dayBoundaryToAfter23NewDay(boundary){
	return normalizeDayBoundary(boundary) === DAY_BOUNDARY_AFTER24 ? 0 : 1;
}

// 全局默认的 after23NewDay 值（供各技法在「未显式设置」时回退使用）。
export function globalDefaultAfter23NewDay(app){
	return dayBoundaryToAfter23NewDay(app && app.dayBoundary);
}

// 直接从持久化的全局偏好读取日界点（不依赖 React/dva，可在模块常量、astro model、纯工具里调用）。
// key 'globalSetup' 同 constants.GlobalSetupKey。
export function readGlobalDayBoundary(){
	try{
		if(typeof localStorage !== 'undefined'){
			const raw = localStorage.getItem('globalSetup');
			if(raw){
				const obj = JSON.parse(raw);
				return normalizeDayBoundary(obj && obj.dayBoundary);
			}
		}
	}catch(e){
		// 读取/解析失败时回退默认（23点后次日）。
	}
	return DAY_BOUNDARY_AFTER23;
}

// 各技法「未单独覆盖」时使用的 after23NewDay 默认值——实时取自全局设置。
export function defaultAfter23NewDay(){
	return dayBoundaryToAfter23NewDay(readGlobalDayBoundary());
}

// ============================================================================
// v3 第二个独立全局开关·晚子时·时柱起干模式 (与日柱开关 after23NewDay 完全独立)
// 用户拍板(配套自检 27日23:30 直接时间):
//   'nextDay'(默认): 时干用次日日干起子时
//     - after23=1 (日柱壬寅) + lateZi=1 → 壬寅 庚子
//     - after23=0 (日柱辛丑) + lateZi=1 → 辛丑 庚子 (按 28日壬干起子时)
//   'today': 时干用今日日干起子时
//     - after23=1 (日柱壬寅) + lateZi=0 → 壬寅 庚子 (日柱已次日, 当日干即次日, 等价)
//     - after23=0 (日柱辛丑) + lateZi=0 → 辛丑 戊子 (按 27日辛干起子时, 新行为)
// 时柱开关只在 hour∈[23:00,24:00) 时影响时干; 其他时辰无差别。
export const LATE_ZI_HOUR_NEXT_DAY = 'nextDay';
export const LATE_ZI_HOUR_TODAY = 'today';

export function normalizeLateZiHourMode(value){
	return value === LATE_ZI_HOUR_TODAY ? LATE_ZI_HOUR_TODAY : LATE_ZI_HOUR_NEXT_DAY;
}

// 映射到后端开关 lateZiHourUseNextDay:
//   1 = 'nextDay' = 时干用次日日干起子时 (默认)
//   0 = 'today'   = 时干用今日日干起子时
export function lateZiHourModeToBit(mode){
	return normalizeLateZiHourMode(mode) === LATE_ZI_HOUR_TODAY ? 0 : 1;
}

export function globalDefaultLateZiHourUseNextDay(app){
	return lateZiHourModeToBit(app && app.lateZiHourMode);
}

export function readGlobalLateZiHourMode(){
	try{
		if(typeof localStorage !== 'undefined'){
			const raw = localStorage.getItem('globalSetup');
			if(raw){
				const obj = JSON.parse(raw);
				return normalizeLateZiHourMode(obj && obj.lateZiHourMode);
			}
		}
	}catch(e){
		// fallback: nextDay
	}
	return LATE_ZI_HOUR_NEXT_DAY;
}

export function defaultLateZiHourUseNextDay(){
	return lateZiHourModeToBit(readGlobalLateZiHourMode());
}
