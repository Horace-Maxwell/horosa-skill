



import '../utils/pageSettingsStore.js';




import '../liureng/LRPanStyle.js';
import '../liureng/LRShenJiangDoc.js';
import '../liureng/ChuangChart.js';

// headless stub：DateTime 只在 UI 草稿恢复链（deserializeBirthDraft → buildBirthFields → cloneDateTimeSafe）里用，
// 该链不被任何 headless 导出调用；真被调到时构造即抛明确错误，而不是被 try/catch 吞掉的 ReferenceError。
class DateTime { constructor(){ throw new Error('headless stub: components/comp/DateTime is not vendored'); } }

// R4-B2(horosa_prefetch_registry_v1):/liureng/gods 步进预取登记 + 选步长武装(S3 收敛)。

// 组件外的模块级助手(纯函数 / 常量 / 表 / 小组件)与组件方法(inputs · requests · caseState · inputPanel · rightTabs;类后 mixinMethods 挂回原型)按职责拆在 ./main/ 下;
// 构造、生命周期、render 与对外导出面仍在本文件。
import { sameLRSigArr, readLiurengChartType, readLiurengFlag, buildBirthFields, getSolarYearFromField, resolveDisplayRunYear } from './main/birthRunYear.js';
import { QIZHENG_PLANET_COLOR, QIZHENG_WUXING_COLOR, buildQiZhengItems } from './main/ganzhiHelpers.js';
import { LIURENG_PAGE_SETTINGS, liurengChouBranch, buildLiuRengCastOverride } from './main/castLayout.js';

import { XIAO_JU_REFERENCE_TAB_KEYS } from './main/referenceXiaoJu.js';
import { buildReferenceDocumentText, buildOverviewReferenceText } from './main/referenceOverview.js';
import { buildLiuRengReferenceBundle } from './main/referenceMatch.js';







// 对外导出面不变:搬进子模块的导出原样重导出
export { appendMapSection, resolveDisplayRunYear } from './main/birthRunYear.js';
export {
	QI_METHODS, LIURENG_PAGE_SETTINGS, liurengAyanamsa, getYueJiangByMethod, computeQiXY, buildLiuRengCastOverride,
	buildLiuRengLayout, liurengSeHaiOptsOf, liurengFenZhouYeDiurnal,
} from './main/castLayout.js';
export {
	liurengCaseGender, buildKeData, buildSanChuanData, buildLiuRengPanRows, buildLiuRengSanChuanRows,
	buildLiuRengSuiShaRows, buildLiuRengZhangShengRows,
} from './main/panData.js';
export { DA_GE_META } from './main/referenceDaGe.js';
export { XIAO_JU_META } from './main/referenceXiaoJu.js';
export { buildLiuRengReferenceContext, matchDaGeReferences, matchXiaoJuReferences } from './main/referenceMatch.js';
export { buildLiuRengSnapshotText } from './main/snapshot.js';


// 起课口径的 state 键(择日宿主经 hook.getCastOptions 取;变了经 onPageCalibreChange 告知宿主)
const LIURENG_CAST_STATE_KEYS = ['guireng', 'castMethod', 'yueJiangMethod', 'fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe', 'yearShenShaSort', 'yinyangSystem', 'tuWangShuai'];

export {
	buildLiuRengReferenceBundle,
	buildReferenceDocumentText,
	buildOverviewReferenceText,
	XIAO_JU_REFERENCE_TAB_KEYS,
	liurengChouBranch,
	buildQiZhengItems,
	QIZHENG_PLANET_COLOR,
	QIZHENG_WUXING_COLOR,
};
