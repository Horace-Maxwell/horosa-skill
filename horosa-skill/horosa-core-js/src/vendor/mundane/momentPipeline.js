// divination/mundane/momentPipeline.js
// 世俗「精确时刻 → 排盘」复用基座。一处实现，两处用：
//   (1) 世俗盘：新月/满月/日食/月食事件扫描 + 选中后按精确时刻起盘（走 DivinationChartShell 的 setTime）。
//   (2) 择日盘「时势合参」：前一次新/满月、前一次日/月食、当年入宫盘 等单独排盘（chartAtMoment 不动主盘）。
// 后端复用既有 /astroextra/ephemeris（已返回 lunarPhases / eclipses / ingresses / stations，无需新端点）。




import { SIGNS } from '../divination/data/signs.js';

const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];

// 由黄经直接定座（最稳，避免依赖后端 sign 字段大小写/语言）。
export function signKeyFromLon(lon){
	const n = Number(lon);
	if(!Number.isFinite(n)){ return null; }
	const norm = ((n % 360) + 360) % 360;
	return SIGN_KEYS[Math.floor(norm / 30)] || null;
}

// 事件本地时刻：后端 date_time_from_jd 给 datetime（'YYYY-MM-DD HH:mm:ss'，已按 zone 折算）。
function localTimeOf(ev){
	if(!ev){ return ''; }
	if(ev.datetime){ return ev.datetime; }
	if(ev.date && ev.time){ return `${ev.date} ${ev.time}`; }
	return ev.date || '';
}

// 离最近交点（升/降）的角距，用于食强度（~18° 内方成食）。
export function nodeDistance(lon, nodeLon){
	const a = Number(lon); const b = Number(nodeLon);
	if(!Number.isFinite(a) || !Number.isFinite(b)){ return null; }
	const norm = (x) => ((x % 360) + 360) % 360;
	const sep = (x, y) => { const d = Math.abs(norm(x - y)); return Math.min(d, 360 - d); };
	return Math.min(sep(a, b), sep(a, b + 180));
}

// 入宫盘掌管时长（经典定则）：上升基本座→3 月、变动座→6 月、固定座→12 月。
export function ingressDurationMonths(ascSignKey){
	const sign = ascSignKey ? SIGNS[ascSignKey] : null;
	const mod = sign && sign.modality;
	if(mod === 'fixed'){ return 12; }
	if(mod === 'mutable'){ return 6; }
	return 3; // cardinal 或缺省
}

// 入境主管(§8.3):按规则集 + 白羊入境盘四轴(ASC)座模式判定主管时长与须补起的季盘。
// quarterly(Ptolemaic/Medieval):四轴基本→只首季(3月,须夏至/秋分/冬至)、变动→半年(6月,须秋分天秤)、固定→整年。
// aries_annual(现代默认):白羊全年。capricorn_year(摩羯优先派):冬至为年首、全年。
// [Q-150/T-60] 主管说明恒以「白羊盘」立论(摩羯优先档为冬至盘),但左栏可选夏至/秋分/冬至节气起盘 ——
// 此前照样把「白羊盘主管整年」套在当前盘上,读的人会以为手里这张夏至盘管一年。
// termName = 当前入宫节气(左栏 extra.ingressTerm);不传 = 年首盘,说明逐字不变(零回归)。
const INGRESS_YEAR_HEAD_TERM = { quarterly: '春分', aries_annual: '春分', capricorn_year: '冬至' };
function ingressTermSuffix(rule, termName){
	const head = INGRESS_YEAR_HEAD_TERM[rule] || '春分';
	if(!termName || termName === head){ return ''; }
	return `;本盘是${termName}入境盘 —— 主管年度的是${head}入境盘,本盘按该档只作分季/阶段补充`;
}

export function ingressGovernance(ascSignKey, ingressRule, termName){
	const rule = ingressRule || 'aries_annual';
	const sign = ascSignKey ? SIGNS[ascSignKey] : null;
	const mod = (sign && sign.modality) || null;
	const sfx = ingressTermSuffix(rule, termName);
	if(rule === 'quarterly'){
		if(mod === 'fixed'){ return { rule, modality: 'fixed', spanMonths: 12, needSeasonal: [], note: '四轴固定座 → 白羊盘主管整年' + sfx }; }
		if(mod === 'mutable'){ return { rule, modality: 'mutable', spanMonths: 6, needSeasonal: ['libra'], note: '四轴变动座 → 白羊盘主管半年,须再起秋分(天秤)入境' + sfx }; }
		return { rule, modality: 'cardinal', spanMonths: 3, needSeasonal: ['cancer', 'libra', 'capricorn'], note: '四轴基本座 → 白羊盘只管首季,须再起夏至/秋分/冬至三盘' + sfx };
	}
	if(rule === 'capricorn_year'){
		return { rule, modality: mod, spanMonths: 12, needSeasonal: [], note: '摩羯入境(冬至)为政治/财政年首,主管全年' + sfx };
	}
	return { rule, modality: mod, spanMonths: 12, needSeasonal: [], note: '白羊入境盘主管全年(其余三盘作分季补充,非必需)' + sfx };
}
