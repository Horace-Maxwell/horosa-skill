// 择日内嵌技法页「左栏口径 × 扫描」的单一登记处(纯数据,宿主 / 扫描引擎 / 概览浮窗 / 内嵌页都从这里取)。
//
// 择日宿主内嵌的是完整技法页,左栏的起课 / 起局口径用户照样能改。每个会改变判定的口径只能是三种之一:
//   · 页面 → 扫描(*_PAGE_SCAN_KEYS):开始择时那一刻从内嵌页取当前值,冻结进扫描口径;点结果行时按冻结值回写内嵌页;
//   · 工作台 → 扫描(*_WORKBENCH_TO_PAGE):工作台上调,扫描照用,点结果行时按页面键名回写;
//   · 锁定(*_ZERI_LOCKED):扫描只支持一种口径,内嵌页里该控件置灰并写明,点结果行时回写锁定值。
// 否则点开的盘就不是扫描判定的那一盘(所见 ≠ 所判)。合同测试 zeriTechniqueParity 对四个内嵌页的全部可改键逐键核对。

// ── 六壬(独立六壬择日;三式择日的六壬家同用) ──
// 分昼夜 / 涉害取舍 / 涉害起讫 / 始入课:扫描起课同读(liurengZeriScanEngine.computeLiurengScanPan)
export const LIURENG_PAGE_SCAN_KEYS = ['fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe'];
// 起课法:扫描只按正时正将起课(选时 / 演数 / 报数离不开逐课输入,扫描无从枚举)
export const LIURENG_ZERI_LOCKED = {
	castMethod: { value: 'zheng', label: '正时正将', hint: '择日按正时正将扫描;点选结果行时内嵌盘随扫描口径' },
};
// 工作台三键 → 六壬页键名(贵人体系 / 月将换法 / 昼夜阳阴归属)
export function liurengWorkbenchToPage(o){
	const opts = o || {};
	const partial = {};
	if(opts.guirengType !== undefined && opts.guirengType !== null && `${opts.guirengType}` !== ''){ partial.guireng = Number(opts.guirengType); }
	if(opts.yueMode !== undefined){ partial.yueJiangMethod = opts.yueMode === 'jieqi' ? 'jieqi' : 'zhongqi'; }
	if(opts.yinyangSystem !== undefined && opts.yinyangSystem !== null && `${opts.yinyangSystem}` !== ''){ partial.yinyangSystem = opts.yinyangSystem; }
	return partial;
}

// ── 太乙(太乙择日;三式择日的太乙家同口径,键名按三式页改名) ──
// 流派六轴:扫描照用页面当前值(applyTaiyiSchool)
export const TAIYI_PAGE_SCAN_KEYS = ['school'];
// 太乙已剔除的两个死键(十精 / 转盘:后端全仓零读取、前端零消费者)。此前登记在页面口径键里,旧方案 / 历史 / 存案里带着它们 ——
// 载入时一律剔除(withoutKeys),不再写进内嵌太乙页、随存案落盘
export const TAIYI_RETIRED_OPTION_KEYS = Object.freeze(['tenching', 'rotation']);
// 盘式恒时计、时间基准恒钟表时、博弈恒关(computeTaiyiScanPan 钉死)
export const TAIYI_ZERI_LOCKED = {
	style: { value: 3, label: '时计', hint: '择日按时计太乙扫描' },
	timeBasis: { value: 'direct', label: '钟表时', hint: '择日按钟表时扫描' },
	gameTheory: { value: 0, label: '博弈关闭', hint: '择日扫描不用博弈盘' },
};

// ── 三式合一(三式择日) ──
// 六壬家:同独立六壬择日;太乙家:流派表(三式页键名 taiyiSchool);奇门家:见 sanshiOptionSplit.QM_SEED_KEYS(由页面播种)
export const SANSHI_LR_PAGE_SCAN_KEYS = LIURENG_PAGE_SCAN_KEYS;
export const SANSHI_TY_PAGE_SCAN_KEYS = ['taiyiSchool'];
export const SANSHI_ZERI_LOCKED = {
	taiyiStyle: { value: 3, label: '时计', hint: '择日按时计太乙扫描' },
	taiyiTimeBasis: { value: 'direct', label: '钟表时', hint: '择日按钟表时扫描' },
	gameTheory: { value: 0, label: '博弈关闭', hint: '择日扫描不用博弈盘' },
};

// ── 紫微(紫微择日) ──
// 排盘口径一律取内嵌紫微页(紫微页的排盘设置是全局单例,内嵌页与紫微页同读):开始择时那一刻冻结进扫描口径,
// 工作台只留性别 / 时间算法。扫描引擎消费的引擎键(定年界线 / 晚子时 / 三盘 / 引擎转发键);安星农历由晚子时推得
// (与页面同一规则:跟随全局 = 日历日,否则随日柱进位)。页面全缺省时 = Java 兼容口径,与旧扫描逐盘相同。
// 点结果行不回写(回写 = 改你的紫微全局设置);扫描之后在紫微页改了口径,「结果已过期」照亮(指纹含这些键)。
export const ZIWEI_PAGE_SCAN_KEYS = ['yearBoundary', 'lateZi', 'sanPan', 'daxianSpan', 'tianmaBasis', 'starSet', 'shangShi', 'leapMonth',
	'huoling', 'kongNaming', 'lifeMasterBy', 'changshengStart', 'changshengDirection', 'kuiYue', 'kongwangStyle', 'xiaoxianMode'];
// 紫微页这些键的出厂值(= 紫微设置单例的出厂值;扫描引擎对缺键就按它起盘)。只用于「结果已过期」指纹把缺席的页面键补成出厂值:
// 页面口径进扫描之前存的存案 / 方案不带这些键,当时就是按出厂口径扫的 —— 不补,设置是出厂值时也会误亮过期
export const ZIWEI_PAGE_FACTORY = Object.freeze({
	yearBoundary: 'lunar_1_1', lateZi: 'global', sanPan: 'tian', daxianSpan: 10, tianmaBasis: 'month', starSet: 'full', shangShi: 'fixed',
	leapMonth: 'mid_split', huoling: 'sanhe', kongNaming: 'modern', lifeMasterBy: 'year_branch', changshengStart: 'shui_tu',
	changshengDirection: 'yinyang', kuiYue: 'jia_wu_geng', kongwangStyle: 'double', xiaoxianMode: '0',
});

// ── 印度(印度择日) ──
// 岁差制 / 交点 = 工作台参数(扫描后端只收这两项):点结果行按工作台值回写内嵌印度页(左栏亲手改过的覆盖掉);
// 分宫制在择日里锁定整宫(扫描「自 Lagna 落宫」按整宫数)
export function indiaWorkbenchToPage(o){
	const opts = o || {};
	return { indiaAyanamsa: opts.ayanamsa || 'lahiri', indiaNodeType: opts.nodeType === 'true' ? 'true' : 'mean' };
}
export const INDIA_ZERI_LOCKED = {
	indiaHsys: { value: 0, label: '整宫制', hint: '择日按整宫扫描(自 Lagna 数宫);点选结果行时内嵌盘回到整宫' },
};

// ── 七政(七政择日) ──
// 排盘引擎在择日里锁定星阙七政引擎(扫描与之同一套黄经 / 宿界 / 命宫);「坚七政」是另一套引擎,择日里不可选
export const QIZHENG_ZERI_LOCKED = {
	engineMode: { value: 'horosa', label: '星阙七政引擎', hint: '择日按星阙七政引擎扫描;「坚七政」盘式在择日里不可用' },
};

// ── 八字(八字择日) ──
// 南半球月令 / 命宫起法:扫描起盘照用内嵌八字页当前值(baziScanParams → buildLocalNongliLite),
// 开始择时那一刻冻结,点结果行时按冻结值回写;旧方案没带 → 出厂值(none / tongxing)
export const BAZI_PAGE_SCAN_KEYS = ['southMonth', 'minggongMethod'];
export const BAZI_PAGE_FACTORY = Object.freeze({ southMonth: 'none', minggongMethod: 'tongxing' });

// 锁定表 → 回写值 { key: value }
export function lockedValuesOf(table){
	const out = {};
	Object.keys(table || {}).forEach((k)=>{ out[k] = table[k].value; });
	return out;
}
// 页面口径键补出厂值:值缺席(undefined / null / 空串)的页面键换成出厂值,其余原样(引擎对缺键就按出厂口径起盘,两者是同一个口径)
export function withPageFactory(options, keys, factory){
	const out = { ...(options && typeof options === 'object' ? options : {}) };
	(keys || []).forEach((k)=>{
		const v = out[k];
		if((v === undefined || v === null || v === '') && factory && factory[k] !== undefined){ out[k] = factory[k]; }
	});
	return out;
}
// 去掉给定键(浅拷贝;不是对象 → 原样返回)
export function withoutKeys(obj, keys){
	if(!obj || typeof obj !== 'object' || Array.isArray(obj)){ return obj; }
	const out = { ...obj };
	(keys || []).forEach((k)=>{ delete out[k]; });
	return out;
}
// 从对象里只取给定键(undefined 不取)
export function pickKeys(src, keys){
	const out = {};
	if(!src || typeof src !== 'object'){ return out; }
	(keys || []).forEach((k)=>{
		if(src[k] !== undefined && src[k] !== null){ out[k] = (typeof src[k] === 'object') ? JSON.parse(JSON.stringify(src[k])) : src[k]; }
	});
	return out;
}
// 内嵌页渲染控件时用:该键在择日里锁定 → { disabled, title }。第三参 = 控件当前值(必传),第四参 = 显式存案标记(必传;
// 本页 / 宿主载入存案时记下:zeriRestoredLockMarks,没载入过 = null)。
//   · 当前值 = 锁定值 → 锁定;
//   · 当前值 ≠ 锁定值、且这一项确是载入存案复原来的(标记在)→ 不锁,悬停写明:载入的是锁定之前存的存案,盘由存档复原、
//     起法不是扫描口径;控件若一直灰着就改不回扫描口径;
//   · 当前值 ≠ 锁定值、却没有存案标记 = 有入口绕过了锁定把值改掉(该修的是那个入口):照样锁定,开发态告警。
// 此前没有第四参、按「值不等」推定来自存案:流派预设之类改掉锁定项,控件就跟着解锁,还挂「由存案复原」的假提示
export const ZERI_LOCK_RESTORED_HINT = '这张盘由存案复原,此项不是择日扫描的口径(扫描只按「%s」);可以改,点结果行会回到扫描口径';
export function zeriLockProps(locked, key, currentValue, restoredMarks){
	const e = locked && locked[key];
	if(!e){ return {}; }
	const differs = currentValue !== undefined && currentValue !== null && `${currentValue}` !== `${e.value}`;
	if(differs && restoredMarks && restoredMarks[key]){
		return { disabled: false, title: ZERI_LOCK_RESTORED_HINT.replace('%s', e.label || `${e.value}`), restoredMismatch: true };
	}
	if(differs && typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development' && typeof console !== 'undefined'){
		console.warn(`[zeri] 锁定项 ${key} 的当前值不是锁定值,也不是由存案复原的:有入口绕过了锁定`);
	}
	return { disabled: true, title: e.hint };
}
// 载入存案时记下:哪些锁定项的复原值不是锁定值(显式存案标记,zeriLockProps 第四参)。values = 复原后的 { 键: 值 };一项都没有 → null
export function zeriRestoredLockMarks(locked, values){
	const out = {};
	Object.keys(locked || {}).forEach((k)=>{
		const v = values ? values[k] : undefined;
		if(v !== undefined && v !== null && `${v}` !== `${locked[k].value}`){ out[k] = true; }
	});
	return Object.keys(out).length ? out : null;
}
// 宿主回写了这些键(点结果行按扫描口径回写锁定值等):它们不再是「由存案复原」的,标记去掉;剩不下 → null
export function clearZeriLockMarks(marks, written){
	if(!marks){ return null; }
	const out = { ...marks };
	Object.keys(written && typeof written === 'object' ? written : {}).forEach((k)=>{ delete out[k]; });
	return Object.keys(out).length ? out : null;
}

// 页面口径键随方案 / 历史存取:存 = 工作台参数 ∪ 宿主给出的页面键(getSchemeOptions);载入 = 宿主把其中的页面键回写内嵌页、
// 其余进工作台(splitPageKeys)。页面键不住在工作台参数里(住了会压住内嵌页左栏当前值)。
export function schemeOptionsOf(getSchemeOptions, options){
	let o = null;
	try{ o = typeof getSchemeOptions === 'function' ? getSchemeOptions() : null; }catch(e){ o = null; }
	return o && typeof o === 'object' ? o : options;
}
export function splitPageKeys(options, keys){
	const page = pickKeys(options, keys);
	const rest = {};
	Object.keys(options || {}).forEach((k)=>{ if((keys || []).indexOf(k) < 0){ rest[k] = options[k]; } });
	return { page, rest };
}
