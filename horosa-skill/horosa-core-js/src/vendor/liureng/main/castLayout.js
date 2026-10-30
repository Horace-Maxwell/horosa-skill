// 六壬页 · 起课与盘式:月将取法、起课方法表、页面设置、岁差、分昼夜、丑位、起课坐标、起课覆盖参数、盘式布局。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import { definePageSettings } from '../../utils/pageSettingsStore.js';
import * as AstroConst from '../../../constants/AstroConst.js';
import * as LRConst from '../../liureng/LRConst.js';
import { getPlanetObject } from './ganzhiHelpers.js';

function getChartYue(chartObj){
	if(!chartObj || !chartObj.objects){
		return '';
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj.id === AstroConst.SUN){
			return LRConst.getSignZi(obj.sign);
		}
	}
	return '';
}

// 起课法：正时正将(第一客) + 十二客②–⑫ + 加时四法(太岁/月建/行年/本命加时) + 次客·一/二/三筹 + 四柱对齐 + 选时 + 演数。
// 古法：每法＝一对「天盘起支 X 加于 地盘临位 Y」；天干用寄宫(GanJiZi)；对齐/本命/行年取对应地支。
// 次客(cikeN)：自月将本位起，阳支「后三前五」/阴支「前三后五」取「第 N 筹」天盘地支，再以该支「加时」(放占时)重排上下盘——与其它加时法同理(见 liurengChouBranch + computeQiXY)。
// 起课法 25 法（AI 挂载齿轮 schema 复用此常量映射，杜绝手写错值/漂移——见 techniqueMountSettings.LIURENG_FIELDS）。
export const QI_METHODS = [
	{ key: 'zheng', name: '正时正将' },
	{ key: 'bake2', name: '十二客·月建加太岁' },
	{ key: 'bake3', name: '十二客·太岁加月建' },
	{ key: 'bake4', name: '十二客·月建加日干' },
	{ key: 'bake5', name: '十二客·岁干加正时' },
	{ key: 'bake6', name: '十二客·月将加日干' },
	{ key: 'bake7', name: '十二客·月将加太岁' },
	{ key: 'bake8', name: '十二客·太岁加月将' },
	{ key: 'bake9', name: '十二客·月将加本命' },
	{ key: 'bake10', name: '十二客·月将加行年' },
	{ key: 'bake11', name: '十二客·太岁加本命' },
	{ key: 'bake12', name: '十二客·太岁加行年' },
	{ key: 'tsjs', name: '太岁加时' },
	{ key: 'yjjs', name: '月建加时' },
	{ key: 'xnjs', name: '行年加时' },
	{ key: 'bmjs', name: '本命加时' },
	{ key: 'cike1', name: '次客·一筹' },
	{ key: 'cike2', name: '次客·二筹' },
	{ key: 'cike3', name: '次客·三筹' },
	{ key: 'alnr', name: '年日对齐·陈旧事' },
	{ key: 'alns', name: '年时对齐·深远事' },
	{ key: 'alyr', name: '月日对齐·催迫事' },
	{ key: 'alys', name: '月时对齐·灵活事' },
	{ key: 'xuanshi', name: '选时·事发之时' },
	{ key: 'yanshu', name: '演数·随感之数(加时)' },
	{ key: 'baoshu', name: '报数/端法·活时(÷12定支)' },
];
export const YUE_JIANG_METHODS = [
	{ key: 'zhongqi', name: '中气过宫（默认）' },
	{ key: 'jieqi', name: '节气换将' },
	{ key: 'richan', name: '太阳过宫·日躔（含岁差）' },
];
export const FEN_ZHOU_YE_METHODS = [
	{ key: 'chenhun', name: '晨昏分昼夜（默认）' },
	{ key: 'maoyou', name: '卯酉分昼夜' },
	{ key: 'yinshen', name: '寅申分昼夜' },
];
// 排盘设置跨会话保留(用户实报:改了之后每次重开软件都要重设)。只收「口径」——
// 选时时辰 / 演数数字 / 占事类型是每一课的输入,十二长生五行缺省随日干(保留了就再也回不到「随日干」),都不进。
// 只在用户亲手改控件时落盘:载入事盘回灌、择日工作台下发口径(applyCastFields)都走 setState,不经落盘入口。
// 🔴 只有**独立六壬页**读写这份保存值;六壬择日里内嵌的那份既不读也不写(见 usesSavedSettings):
// 择日的扫描引擎把时基 / 起课法 / 分昼夜 / 涉害口径钉死在缺省档、工作台只下发贵人 / 月将 / 阴阳系三键,
// 内嵌盘若继承了独立页保存的别的口径,点选命中行看到的课就不是扫描判定的那一课(所见 ≠ 所判)。
// 起课法里「选时 / 演数 / 报数」三法离不开逐课输入(时辰 / 数字,不保留):只留法不留数,重开后数字是空的,
// 盘面按正时起、起课法一栏却写着演数 —— 所以这三法不进候选(选了照常用,只是不记;库里仍是上一次选的独立起课法)。
const QI_METHODS_NEEDING_INPUT = ['xuanshi', 'yanshu', 'baoshu'];
export const LIURENG_PAGE_SETTINGS = definePageSettings('horosa.liureng.settings.v1', {
	timeAlg: { def: 0, oneOf: [0, 1] },
	guireng: { def: 2, oneOf: [0, 1, 2, 3, 4] },
	castMethod: { def: 'zheng', oneOf: QI_METHODS.map((m)=>m.key).filter((k)=>QI_METHODS_NEEDING_INPUT.indexOf(k) < 0) },
	yueJiangMethod: { def: 'zhongqi', oneOf: YUE_JIANG_METHODS.map((m)=>m.key) },
	fenZhouYe: { def: 'chenhun', oneOf: FEN_ZHOU_YE_METHODS.map((m)=>m.key) },
	seHaiMethod: { def: 'app', oneOf: ['app', 'standard', 'mengzhongji'] },
	seHaiBoundary: { def: 'app', oneOf: ['app', 'both', 'neither'] },
	shiRuKe: { def: false },
	yearShenShaSort: { def: 'sanyuan', oneOf: ['sanyuan', 'suigui'] },
	yinyangSystem: { def: 'danmu', oneOf: ['danmu', 'yinyang'] },
	tuWangShuai: { def: 'siji', oneOf: ['siji', 'huotu'] },
});
const MAOYOU_DAY_BRANCHES = ['卯', '辰', '巳', '午', '未', '申'];
const YINSHEN_DAY_BRANCHES = ['寅', '卯', '辰', '巳', '午', '未'];

// 月将换将三派(§3.2):中气过宫(③默认=getChartYue,回归中气) / 节气换将(①立节古法,提前半月=黄经+15°取宫) /
// 太阳过宫·日躔(②含岁差,黄经−岁差后取宫,今约较中气晚一周)。岁差=Lahiri 线性近似(标准天文常数,非传本臆断;
// 仅用于定宫,精度足够;太阳黄经已由星历给出,无需后端)。
export function liurengAyanamsa(solarYear){
	const yr = (typeof solarYear === 'number' && isFinite(solarYear)) ? solarYear : 2024;
	return 23.853 + 0.0139644 * (yr - 2000); // 23°51′@2000 + 50.27″/yr
}
export function getYueJiangByMethod(chartObj, yueJiangMethod, solarYear){
	if(yueJiangMethod !== 'jieqi' && yueJiangMethod !== 'richan'){
		return getChartYue(chartObj);
	}
	const sun = getPlanetObject(chartObj, AstroConst.SUN);
	if(!sun || typeof sun.lon !== 'number' || !isFinite(sun.lon)){
		return getChartYue(chartObj);
	}
	const offset = yueJiangMethod === 'richan' ? -liurengAyanamsa(solarYear) : 15;
	const lon = (((sun.lon + offset) % 360) + 360) % 360;
	return LRConst.SignZiList[Math.floor(lon / 30) % 12] || getChartYue(chartObj);
}

// 分昼夜 → isDiurnal 覆盖；晨昏(默认)返回 undefined（沿用星历 isDiurnal）。
// (单一来源:六壬页、三式合一页、六壬 / 三式择日扫描都经它,勿另写一份)
export function liurengFenZhouYeDiurnal(fenZhouYe, chartObj){
	if(fenZhouYe !== 'maoyou' && fenZhouYe !== 'yinshen'){
		return undefined;
	}
	const tb = chartObj && chartObj.nongli && chartObj.nongli.time ? chartObj.nongli.time.substr(1) : '';
	const set = fenZhouYe === 'maoyou' ? MAOYOU_DAY_BRANCHES : YINSHEN_DAY_BRANCHES;
	return set.indexOf(tb) >= 0;
}

// 次客 第 N 筹的天盘地支:自月将本位起,阳支「后三前五」、阴支「前三后五」。
//   一筹=月将本位;二筹=阳后三(逆3)/阴前三(顺3);三筹=阳前五(二筹顺5)/阴后五(二筹逆5)。
//   例:月将申(阳)→申/巳/戌;月将戌(阳)→戌/未/子;月将亥(阴)→亥/寅/酉。取得后用作「该支加时」重排上下盘。
export function liurengChouBranch(yueEff, chou){
	const i = LRConst.ZiList.indexOf(yueEff);
	if(i < 0){
		return '';
	}
	const yang = (i % 2 === 0); // 子寅辰午申戌 为阳(偶位索引)
	if(chou === 1){
		return LRConst.ZiList[i];
	}
	const er = yang ? ((i - 3 + 12) % 12) : ((i + 3) % 12);
	if(chou === 2){
		return LRConst.ZiList[er];
	}
	const san = yang ? ((er + 5) % 12) : ((er - 5 + 12) % 12);
	return LRConst.ZiList[san];
}

// 起课法 → 天盘起支 X 与 地盘临位 Y（yueEff＝换将后月将）。
export function computeQiXY(castMethod, chartObj, yueEff, opts){
	opts = opts || {};
	const nongli = chartObj.nongli || {};
	const timeBranch = nongli.time ? nongli.time.substr(1) : '';
	const dayBranch = nongli.dayGanZi ? nongli.dayGanZi.substr(1) : '';
	const monthBranch = nongli.monthGanZi ? nongli.monthGanZi.substr(1) : '';
	const yearGz = nongli.yearGanZi || nongli.yearJieqi || '';
	const yearBranch = yearGz ? yearGz.substr(1) : '';
	const yearGan = yearGz ? yearGz.substr(0, 1) : '';
	const dayGan = nongli.dayGanZi ? nongli.dayGanZi.substr(0, 1) : '';
	const jiDayGan = LRConst.GanJiZi[dayGan] || '';
	const jiYearGan = LRConst.GanJiZi[yearGan] || '';
	// 本命支(命主出生年支) / 行年支:由调用方(渲染/快照)经 opts 传入;缺省时退回默认起法(零回归)。
	const benmingBranch = (opts.benmingZhi && LRConst.ZiList.indexOf(opts.benmingZhi) >= 0) ? opts.benmingZhi : '';
	const xingnianBranch = (opts.xingnianZhi && LRConst.ZiList.indexOf(opts.xingnianZhi) >= 0) ? opts.xingnianZhi : '';
	let X = yueEff;
	let Y = timeBranch;
	switch(castMethod){
		case 'bake2': X = monthBranch; Y = yearBranch; break;
		case 'bake3': X = yearBranch; Y = monthBranch; break;
		case 'bake4': X = monthBranch; Y = jiDayGan; break;
		case 'bake5': X = jiYearGan; Y = timeBranch; break;
		case 'bake6': X = yueEff; Y = jiDayGan; break;
		case 'bake7': X = yueEff; Y = yearBranch; break;
		case 'bake8': X = yearBranch; Y = yueEff; break;
		case 'bake9': X = yueEff; Y = benmingBranch; break;       // 第九客 月将加本命
		case 'bake10': X = yueEff; Y = xingnianBranch; break;     // 第十客 月将加行年
		case 'bake11': X = yearBranch; Y = benmingBranch; break;  // 十一客 太岁加本命
		case 'bake12': X = yearBranch; Y = xingnianBranch; break; // 十二客 太岁加行年
		case 'tsjs': X = yearBranch; Y = timeBranch; break;       // 太岁加时
		case 'yjjs': X = monthBranch; Y = timeBranch; break;      // 月建加时
		case 'xnjs': X = xingnianBranch; Y = timeBranch; break;   // 行年加时
		case 'bmjs': X = benmingBranch; Y = timeBranch; break;    // 本命加时
		case 'cike1': X = liurengChouBranch(yueEff, 1) || yueEff; Y = timeBranch; break; // 次客·一筹(月将本位)加时
		case 'cike2': X = liurengChouBranch(yueEff, 2) || yueEff; Y = timeBranch; break; // 次客·二筹 加时
		case 'cike3': X = liurengChouBranch(yueEff, 3) || yueEff; Y = timeBranch; break; // 次客·三筹 加时
		case 'alnr': X = yearBranch; Y = dayBranch; break;   // 年日对齐
		case 'alns': X = yearBranch; Y = timeBranch; break;  // 年时对齐
		case 'alyr': X = monthBranch; Y = dayBranch; break;  // 月日对齐
		case 'alys': X = monthBranch; Y = timeBranch; break; // 月时对齐
		case 'xuanshi': X = yueEff; Y = (opts.xuanShiZhi && LRConst.ZiList.indexOf(opts.xuanShiZhi) >= 0) ? opts.xuanShiZhi : timeBranch; break;
		case 'yanshu': {
			X = yueEff;
			const ti = LRConst.ZiList.indexOf(timeBranch);
			const N = parseInt(opts.yanShuNum, 10);
			if(ti < 0 || !isFinite(N)){ Y = timeBranch; break; }
			const step = ((N % 12) + 12) % 12;
			const forward = LRConst.YangGan.indexOf(dayGan) >= 0; // 阳日顺、阴日逆
			Y = LRConst.ZiList[forward ? (ti + step) % 12 : (ti - step + 12) % 12];
			break;
		}
		case 'baoshu': {
			// 活时/端法:报数(或字数/笔画/声数)÷12 直接折占时支(子1…亥12,余0=亥12),月将加之(§4.2/§5.8)
			X = yueEff;
			const N = parseInt(opts.yanShuNum, 10);
			if(!isFinite(N)){ Y = timeBranch; break; }
			let r = ((N % 12) + 12) % 12;
			Y = LRConst.ZiList[r === 0 ? 11 : r - 1];
			break;
		}
		default: break; // zheng / 未知 → X=月将, Y=正时
	}
	return { X, Y };
}

// 涉害三键(取舍 / 起讫 / 始入课)→ 三传核的 seHaiOpts(单一来源:页面起课与择日扫描同用)
export function liurengSeHaiOptsOf(opts){
	const o = opts || {};
	return {
		method: o.seHaiMethod || 'app',
		boundary: o.seHaiBoundary || 'app',
		shiRuKe: !!o.shiRuKe,
	};
}

// 汇总：起课法 + 换将 + 分昼夜 → castOverride {yue,timeZhi,isDiurnal}；全默认返回 null（零回归）。
// (export 供择日概览浮窗同源构造——概览盘口径必须=主页盘口径,勿另写平行实现)
export function buildLiuRengCastOverride(chartObj, opts){
	opts = opts || {};
	if(!chartObj || !chartObj.nongli){
		return null;
	}
	const castMethod = opts.castMethod || 'zheng';
	const yueJiangMethod = opts.yueJiangMethod || 'zhongqi';
	const fenZhouYe = opts.fenZhouYe || 'chenhun';
	const isDiurnal = liurengFenZhouYeDiurnal(fenZhouYe, chartObj);
	// 涉害取舍流派(默认全 app=仅下贼上,零回归);非默认时即便其余皆默认也须产出 override 携 seHaiOpts。
	const seHaiOpts = liurengSeHaiOptsOf(opts);
	const seHaiDefault = seHaiOpts.method === 'app' && seHaiOpts.boundary === 'app' && !seHaiOpts.shiRuKe;
	// 昼夜阳阴归属(§6.3④):danmu=旦暮系(默认)/yinyang=星历考原阳阴系。
	const yinyangSystem = opts.yinyangSystem === 'yinyang' ? 'yinyang' : 'danmu';
	const allDefault = castMethod === 'zheng' && yueJiangMethod !== 'jieqi' && yueJiangMethod !== 'richan' && isDiurnal === undefined && seHaiDefault && yinyangSystem === 'danmu';
	if(allDefault){
		return null;
	}
	const solarYear = Number(opts.solarYear);
	const yueEff = getYueJiangByMethod(chartObj, yueJiangMethod, solarYear);
	const xy = computeQiXY(castMethod, chartObj, yueEff, opts);
	const tFallback = chartObj.nongli.time ? chartObj.nongli.time.substr(1) : '';
	const X = (xy.X && LRConst.ZiList.indexOf(xy.X) >= 0) ? xy.X : (yueEff || getChartYue(chartObj));
	const Y = (xy.Y && LRConst.ZiList.indexOf(xy.Y) >= 0) ? xy.Y : tFallback;
	if(!X || !Y){
		return null;
	}
	// actualYue=真实月将(yueEff):起课法只改 X(天盘起支)用于上下盘对齐;月将/时辰高亮与盘式仍以真实月将+真实占时为准。
	return { yue: X, timeZhi: Y, isDiurnal, actualYue: yueEff, seHaiOpts, yinyangSystem };
}

export function buildLiuRengLayout(chartObj, guirengType, castOverride){
	if(!chartObj || !chartObj.nongli || !chartObj.nongli.time){
		return null;
	}
	// 起课法/换将：月将(yue=天盘起支) 与 临位(timezi=地盘临位) 可被 castOverride 覆盖；缺省=正时正将(现状)。
	const yue = (castOverride && castOverride.yue) || getChartYue(chartObj);
	if(!yue){
		return null;
	}
	const downZi = LRConst.ZiList.slice(0);
	const upZi = LRConst.ZiList.slice(0);
	const yueIndexs = [];
	const timezi = (castOverride && castOverride.timeZhi) || chartObj.nongli.time.substr(1);
	const yueIdx = LRConst.ZiList.indexOf(yue);
	const tmIdx = LRConst.ZiList.indexOf(timezi);
	if(yueIdx < 0 || tmIdx < 0){
		return null;
	}
	const delta = yueIdx - tmIdx;
	for(let i=0; i<12; i++){
		const idx = (i + delta + 12) % 12;
		yueIndexs[i] = idx;
		upZi[i] = LRConst.ZiList[idx];
	}

	const houseTianJiang = LRConst.TianJiang.slice(0);
	const guizi = LRConst.getGuiZi(chartObj, guirengType, castOverride ? castOverride.isDiurnal : undefined, castOverride ? castOverride.yinyangSystem : undefined);
	// 🔴 贵人未命中曾静默落 houseidx=0(子位),十二天将整环随之偏移且无任何提示;
	// getGuiZi 在流派表缺键时确会返 undefined → 该路径可达。未命中即判失败(与本函数
	// 其余失败分支同口径),宁可不出盘也不出错盘。
	let houseidx = -1;
	for(let i=0; i<12; i++){
		const zi = LRConst.ZiList[yueIndexs[i]];
		if(zi === guizi){
			houseidx = i;
			break;
		}
	}
	if(houseidx < 0){
		return null;
	}
	const housezi = LRConst.ZiList[houseidx];
	const guirenForward = LRConst.SummerZiList.indexOf(housezi) < 0;
	if(!guirenForward){
		for(let i=0; i<12; i++){
			const idx = (houseidx - i + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}else{
		for(let i=0; i<12; i++){
			const idx = (i - houseidx + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}

	return {
		yue,
		timezi,
		guizi,
		guirenForward,
		downZi,
		upZi,
		houseTianJiang,
		actualYue: (castOverride && castOverride.actualYue) || yue, // 真实月将(高亮/盘式用);yue 仅作上下盘对齐的天盘起支
	};
}
