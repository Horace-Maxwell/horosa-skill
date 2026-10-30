// 日界 / 晚子时两键的取值单源:各技法页面、引擎、择日扫描与浮窗、截盘挂载在「选项里缺键」时一律经这里取全局现值,
// 不各写各的写死回落(此前同一技法内有回落 0、回落 1、回落全局三种口径,全局改成「24 点换日」后缺键处仍按 23 点算)。
//   值形:1 / '1' / true → 1;0 / '0' / false → 0;缺键(undefined / null / '' / 其他)→ 全局现值。
//   全局为出厂缺省(23 点换日、晚子时用次日干)时,所有缺键结果与旧写死 1 逐字节相同。
// 判据合同:utils/__tests__/dayBoundaryFallbackContract.test.js(全 src 不许再出现写死的缺键回落)。
import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../bazi/dayBoundary.js';

const isOn = (v)=>v === 1 || v === '1' || v === true;
const isOff = (v)=>v === 0 || v === '0' || v === false;

export function resolveAfter23NewDay(v){
	if(isOn(v)){ return 1; }
	if(isOff(v)){ return 0; }
	return defaultAfter23NewDay();
}

export function resolveLateZiHourUseNextDay(v){
	if(isOn(v)){ return 1; }
	if(isOff(v)){ return 0; }
	return defaultLateZiHourUseNextDay();
}

// 选项对象 → 两键(缺键取全局现值);用于构请求体与引擎入口归一
export function resolveDayBoundaryOptions(options){
	const o = options || {};
	return {
		after23NewDay: resolveAfter23NewDay(o.after23NewDay),
		lateZiHourUseNextDay: resolveLateZiHourUseNextDay(o.lateZiHourUseNextDay),
	};
}

// 本盘(表单 fields)→ 两键:本盘有值用本盘,没有才用全局现值。命类各页面(八字 / 七政 / 正传 / kinastro 系 / 参评 / 河洛 / 一掌经)
// 与 AI 无头重算一律经这里取,同一张盘页面与挂载同口径(此前 kinastro 系页面只读全局、无头读本盘 → 23 点档两套四柱)。
//   fields:{ after23NewDay: { value }, lateZiHourUseNextDay: { value }, … };缺键 / 空值 / 非 0·1 形 → 全局现值。
export function chartDayBoundary(fields){
	const fv = (k)=>{ const x = fields && fields[k]; return (x && typeof x === 'object') ? x.value : undefined; };
	return {
		after23NewDay: resolveAfter23NewDay(fv('after23NewDay')),
		lateZiHourUseNextDay: resolveLateZiHourUseNextDay(fv('lateZiHourUseNextDay')),
	};
}
