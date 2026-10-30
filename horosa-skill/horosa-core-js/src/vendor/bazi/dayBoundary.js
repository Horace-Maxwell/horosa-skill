// 日界点全局偏好的取值与映射。
// 用户语义（拍板，字面直觉版，配套自检 27日23:30）：
//   'after23'（默认）「23点算第二天」= 23点起日柱进位次日(壬寅)
//   'after24'           「24点算第二天」= 23点仍守今、24点才换日柱(辛丑)
// 时柱跨日永远按"次日日干"起子时(=庚子,与 lunar.js Exact 一致)。
import { readGlobalSetupField } from '../utils/globalSetupStore.js';
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

// 读全局偏好的日界点（不依赖 React/dva，可在模块常量、astro model、纯工具里调用）。
// 经全局设置单源的内存镜像(globalSetupStore.readGlobalSetupField):跨窗口跟随、全量恢复冻结期间与界面一致。
export function readGlobalDayBoundary(){
	try{
		return normalizeDayBoundary(readGlobalSetupField('dayBoundary'));
	}catch(e){
		// 读取失败时回退默认（23点后次日）。
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
//     - after23=1 (日柱壬寅) + lateZi=0 → 壬寅 戊子 (日柱进位、时干仍按钟面当天辛干起;两开关完全独立 —— 用户拍板,
//       jest baziLunarLocal.dayBoundary 矩阵 + Java BaZiHelper + 七路 Python 权威 2026-09-18 已对齐同一口径)
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

export function readGlobalLateZiHourMode(){
	try{
		return normalizeLateZiHourMode(readGlobalSetupField('lateZiHourMode'));
	}catch(e){
		// fallback: nextDay
	}
	return LATE_ZI_HOUR_NEXT_DAY;
}

export function defaultLateZiHourUseNextDay(){
	return lateZiHourModeToBit(readGlobalLateZiHourMode());
}

// ============================================================================
// 日界 / 晚子时改了之后的同步通道(单源):各技法页与 astro 共享口径靠这两条窗口事件跟着换并重算。
// 凡「本窗口的日界 / 晚子时变了」—— 页头设置菜单、AI 设置工具(含撤销回灌)、别的窗口改了全局设置后的跟随 —— 一律经这里派发,
// 不各自手写 CustomEvent(此前跟随入口漏了派发:菜单显示新值,共享口径与当前盘停在旧值)。
// 只派发本窗口事件、不写存储,所以跟随别的窗口时不会反过来再触发别的窗口。
export const DAY_BOUNDARY_CHANGED_EVENT = 'horosa:day-boundary-changed';
export const LATE_ZI_HOUR_MODE_CHANGED_EVENT = 'horosa:late-zi-hour-mode-changed';
function dispatchWindowEvent(name, detail){
	try{
		if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof CustomEvent === 'function'){
			window.dispatchEvent(new CustomEvent(name, { detail }));
		}
	}catch(e){
		// 广播失败不影响设置本身
	}
}
export function announceDayBoundaryChange(value){
	const dayBoundary = normalizeDayBoundary(value);
	dispatchWindowEvent(DAY_BOUNDARY_CHANGED_EVENT, { dayBoundary, after23NewDay: dayBoundaryToAfter23NewDay(dayBoundary) });
}
export function announceLateZiHourChange(value){
	const lateZiHourMode = normalizeLateZiHourMode(value);
	dispatchWindowEvent(LATE_ZI_HOUR_MODE_CHANGED_EVENT, { lateZiHourMode, lateZiHourUseNextDay: lateZiHourModeToBit(lateZiHourMode) });
}

// 全局设置字段 → 变了之后要走的副作用通道。其余全局字段都是「状态驱动」(组件按 props / 镜像重读),没有单独通道;
// 新增全局字段若另有通道(窗口事件 / 重算),必须登记在这里 —— 写入口与跟随入口共用 announceGlobalSetupChanges。
export const GLOBAL_SETUP_CHANNELS = Object.freeze({
	dayBoundary: announceDayBoundaryChange,
	lateZiHourMode: announceLateZiHourChange,
});
// values:这次变了的全局字段(只看自有键;未登记通道的字段忽略)
export function announceGlobalSetupChanges(values){
	if(!values || typeof values !== 'object'){ return; }
	Object.keys(GLOBAL_SETUP_CHANNELS).forEach((k)=>{
		if(Object.prototype.hasOwnProperty.call(values, k) && values[k] !== undefined){ GLOBAL_SETUP_CHANNELS[k](values[k]); }
	});
}

// ============================================================================
// 日界口径的农历月 / 日 / 闰(单一入口)。
// after23NewDay=1(23 点算第二天)且本命落 23 点子时段时,日柱已进位次日,baziLunarLocal.buildNongli
// 同步给出进位后的农历(ziweiMonthNum / ziweiDayNum / ziweiLeap,紫微首用);而 monthNum / dayNum
// 恒为钟面历日的农历。凡按「农历月 / 日」起数的技法(一掌经四宫、参评起运、正传铁板月命数等)
// 一律经此取值,与日柱、紫微同一口径;此前四页直读 dayNum → 同一屏上日柱已是次日、农历日仍是当日,
// 且日界开关对这些页面是死开关(三方案结果完全相同)。
// 不进位场景 / 远程农历桥(无 ziwei* 键)逐字回退 monthNum / dayNum / leap → 缺省与非 23 点档零回归。
export function lunarByDayBoundary(nl){
	const n = nl || {};
	const rolled = n.ziweiDayNum != null && n.ziweiMonthNum != null;
	const civilMonth = Number(n.monthNum || n.month) || 0;
	const civilDay = Number(n.dayNum || n.day) || 0;
	const monthNum = rolled ? (Number(n.ziweiMonthNum) || civilMonth) : civilMonth;
	const dayNum = rolled ? (Number(n.ziweiDayNum) || civilDay) : civilDay;
	const leap = rolled ? !!n.ziweiLeap : !!(n.isLeap || n.leap);
	return { monthNum, dayNum, leap, shifted: rolled && (monthNum !== civilMonth || dayNum !== civilDay) };
}
