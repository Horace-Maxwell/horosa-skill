// 本地历法引擎(lunar-javascript)可靠域守卫。
// 实测定界:AD 1 ~ AD 9999 内节气/干支/朔闰正确;域外(公元前、AD 10000+)不报错但
// 节气错位 → 月柱等静默算错(比崩溃更危险)。任何本地历法入口先过此守卫:
// 域内照常;域外返回 null 并由调用方给出明确提示,绝不吐出错误干支。
// 域外年份的历法计算走后端星历实算路径(/jieqi/nongli 系,BC12998~AD16798 可用)。

export const LUNAR_JS_MIN_YEAR = 1;
export const LUNAR_JS_MAX_YEAR = 9999;

export function isLunarJsYearReliable(year){
	const y = Number(year);
	return Number.isFinite(y) && y >= LUNAR_JS_MIN_YEAR && y <= LUNAR_JS_MAX_YEAR;
}

// 统一提示文案(UI 层直接展示)
export function lunarDomainNotice(year){
	return `公元 ${LUNAR_JS_MIN_YEAR}~${LUNAR_JS_MAX_YEAR} 年之外(输入 ${year} 年)的农历/干支需走星历实算路径,本地速算不适用`;
}

// 守卫包装:域外返回 null 并 console.warn(开发期可见),域内执行计算。
export function guardLunarYear(year, computeFn){
	if(!isLunarJsYearReliable(year)){
		if(typeof console !== 'undefined' && console.warn){
			console.warn('[lunarDomainGuard]', lunarDomainNotice(year));
		}
		return null;
	}
	return computeFn();
}
