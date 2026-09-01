







import * as AstroConst from '../astroextra/progConst.js';

import * as LRConst from '../liureng/LRConst.js';
import { ZSList, ZhangSheng, liurengWangXiang, judgeKongWang } from '../liureng/LRZhangSheng.js';
import { resolveLiuRengTwelvePanStyle } from '../liureng/LRPanStyle.js';
import { normalizeLiuRengJiangName } from '../liureng/LRShenJiangDoc.js';


import { computeFrontendShenSha, computeYearShenSha, computeMonthShenSha } from '../liureng/LRShenShaDoc.js';
import { detectJianChuan } from '../liureng/LRJianChuanDoc.js';
import { analyzeKongLocations, analyzeDunGan, analyzeNianMing } from '../liureng/LRKongDunNianDoc.js';
import { ZHANDUAN_CATEGORIES, ZHANDUAN_DOC, RELATED_BIFA } from '../liureng/LRZhanDuanDoc.js';
import { matchBiFa, BIFA_LIST } from '../liureng/LRBiFaDoc.js';












import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../bazi/dayBoundary.js';

// R4-B2(horosa_prefetch_registry_v1):/liureng/gods 步进预取登记 + 选步长武装(S3 收敛)。





// 签名数组逐元素严格相等(引用/值);用于 render 内派生缓存命中判定(只多算、绝不少算)。
function sameLRSigArr(a, b){
	if(!a || !b || a.length !== b.length){
		return false;
	}
	for(let i = 0; i < a.length; i++){
		if(a[i] !== b[i]){
			return false;
		}
	}
	return true;
}

function cloneDateTimeSafe(val, fallback){
	if(val && val instanceof DateTime){
		return val.clone();
	}
	if(fallback && fallback instanceof DateTime){
		return fallback.clone();
	}
	return new DateTime();
}

function readLiurengChartType(){
	if(typeof window === 'undefined' || typeof localStorage === 'undefined'){
		return LRConst.LRChart_Square;
	}
	const stored = parseInt(localStorage.getItem('liurengPanView'), 10);
	if(stored === LRConst.LRChart_Circle || stored === LRConst.LRChart_Square){
		return stored;
	}
	return LRConst.LRChart_Square;
}

function readLiurengFlag(key, def){
	if(typeof window === 'undefined' || typeof localStorage === 'undefined'){
		return def;
	}
	try{
		const v = localStorage.getItem(key);
		if(v === '1' || v === 'true'){ return true; }
		if(v === '0' || v === 'false'){ return false; }
	}catch(e){ /* localStorage 不可用则用默认 */ }
	return def;
}

function buildBirthFields(source, fallbackNow){
	const now = fallbackNow && fallbackNow instanceof DateTime ? fallbackNow : new DateTime();
	const src = source || {};
	const dateVal = src.date && src.date.value ? cloneDateTimeSafe(src.date.value, now.startOf('date')) : now.startOf('date');
	const timeVal = src.time && src.time.value ? cloneDateTimeSafe(src.time.value, now) : now.clone();
	return {
		date: { value: dateVal },
		time: { value: timeVal },
		ad: { value: src.ad && src.ad.value !== undefined ? src.ad.value : now.ad },
		zone: { value: src.zone && src.zone.value ? src.zone.value : now.zone },
		lat: { value: src.lat && src.lat.value ? src.lat.value : Constants.DefLat },
		lon: { value: src.lon && src.lon.value ? src.lon.value : Constants.DefLon },
		gpsLat: { value: src.gpsLat && src.gpsLat.value !== undefined ? src.gpsLat.value : Constants.DefGpsLat },
		gpsLon: { value: src.gpsLon && src.gpsLon.value !== undefined ? src.gpsLon.value : Constants.DefGpsLon },
		gender: { value: src.gender && src.gender.value !== undefined ? src.gender.value : 1 },
		after23NewDay: { value: src.after23NewDay && src.after23NewDay.value !== undefined ? src.after23NewDay.value : defaultAfter23NewDay() },
		lateZiHourUseNextDay: { value: src.lateZiHourUseNextDay && src.lateZiHourUseNextDay.value !== undefined ? src.lateZiHourUseNextDay.value : defaultLateZiHourUseNextDay() },
	};
}

function fmtValue(value){
	if(value === undefined || value === null || value === ''){
		return '无';
	}
	if(value instanceof Array){
		return value.join('、') || '无';
	}
	return `${value}`;
}

function cleanKey(key){
	const txt = `${key || ''}`;
	const idx = txt.indexOf('(');
	if(idx >= 0){
		return txt.substring(0, idx);
	}
	return txt;
}

// 神煞 6 段(旬日/旺衰/基础神煞/干煞/月煞/支煞)共用:段头=preset 键,段内 GFM 2 列表化(值零变化,
// 键仍过 cleanKey、值仍过 fmtValue——事实 token 与旧「键：值」行逐字同,证明测试 liurengSnapshotTables.test.js)。
export function appendMapSection(lines, title, obj){
	lines.push(`[${title}]`);
	if(!obj || typeof obj !== 'object'){
		lines.push('无');
		lines.push('');
		return;
	}
	const keys = Object.keys(obj);
	if(keys.length === 0){
		lines.push('无');
		lines.push('');
		return;
	}
	lines.push('| 神煞 | 值 |');
	lines.push('| --- | --- |');
	keys.forEach((key)=>{
		lines.push(`| ${cleanKey(key)} | ${fmtValue(obj[key])} |`);
	});
	lines.push('');
}

function extractGanZi(text){
	const raw = `${text || ''}`.trim();
	if(raw.length < 2){
		return '';
	}
	if(LRConst.GanList.indexOf(raw.substr(0, 1)) >= 0 && LRConst.ZiList.indexOf(raw.substr(1, 1)) >= 0){
		return raw.substr(0, 2);
	}
	for(let i=0; i<raw.length - 1; i++){
		const gan = raw.substr(i, 1);
		const zi = raw.substr(i + 1, 1);
		if(LRConst.GanList.indexOf(gan) >= 0 && LRConst.ZiList.indexOf(zi) >= 0){
			return gan + zi;
		}
	}
	return '';
}

function extractBranch(text){
	const raw = `${text || ''}`;
	const match = raw.match(/[子丑寅卯辰巳午未申酉戌亥]/);
	return match ? match[0] : '';
}

function resolveGuaYearGanZi(liureng){
	if(!liureng){
		return '';
	}
	const fourYear = liureng.fourColumns ? liureng.fourColumns.year : null;
	if(fourYear){
		if(typeof fourYear === 'string'){
			const got = extractGanZi(fourYear);
			if(got){
				return got;
			}
		}else if(fourYear.ganzi){
			const got = extractGanZi(fourYear.ganzi);
			if(got){
				return got;
			}
		}
	}
	const nongli = liureng.nongli ? liureng.nongli : {};
	const fallback = [
		nongli.yearGanZi,
		nongli.yearJieqi,
		nongli.year,
	];
	for(let i=0; i<fallback.length; i++){
		const got = extractGanZi(fallback[i]);
		if(got){
			return got;
		}
	}
	return '';
}

const JiaZiList = (()=>{
	const list = [];
	for(let i=0; i<60; i++){
		list.push(`${LRConst.GanList[i % 10]}${LRConst.ZiList[i % 12]}`);
	}
	return list;
})();

function buildRunYearList(startGanZi, delta){
	const list = [];
	let idx = JiaZiList.indexOf(startGanZi);
	if(idx < 0){
		return list;
	}
	for(let i=0; i<60; i++){
		list.push(JiaZiList[idx]);
		idx = (idx + delta + 60) % 60;
	}
	return list;
}

const MaleRunYearList = buildRunYearList('丙寅', 1);
const FemaleRunYearList = buildRunYearList('壬申', -1);

function resolveCycleYear(ganzi, approxYear){
	const idx = JiaZiList.indexOf(ganzi);
	if(idx < 0){
		return approxYear;
	}
	const base = 1984 + idx;
	const k = Math.floor((approxYear - base) / 60);
	const c1 = base + k * 60;
	const c2 = c1 + 60;
	return Math.abs(c2 - approxYear) < Math.abs(c1 - approxYear) ? c2 : c1;
}

function calcRunYearLocal(birthGanZi, guaGanZi, gender, birthYear, guaYear){
	const bIdx = JiaZiList.indexOf(extractGanZi(birthGanZi));
	const gIdx = JiaZiList.indexOf(extractGanZi(guaGanZi));
	if(bIdx < 0 || gIdx < 0){
		return null;
	}
	const ageCycle = (gIdx - bIdx + 60) % 60;
	let age = ageCycle;
	if(Number.isFinite(birthYear) && Number.isFinite(guaYear)){
		const bSolar = resolveCycleYear(JiaZiList[bIdx], birthYear);
		const gSolar = resolveCycleYear(JiaZiList[gIdx], guaYear);
		const diff = gSolar - bSolar;
		if(diff >= 0){
			age = diff;
		}
	}
	const male = `${gender}` !== '0';
	const yearList = male ? MaleRunYearList : FemaleRunYearList;
	return {
		age,
		ageCycle,
		year: yearList[ageCycle] || '',
	};
}

function getSolarYearFromField(field){
	if(!field || !field.value){
		return NaN;
	}
	const dt = field.value;
	const y = Number(dt.year);
	if(!Number.isFinite(y)){
		return NaN;
	}
	const ad = Number(dt.ad || 1);
	return ad >= 0 ? y : -y;
}

function buildFallbackRunYearByYearDiff(birth, guaFields){
	const birthYear = getSolarYearFromField(birth && birth.date ? birth.date : null);
	const guaYear = getSolarYearFromField(guaFields && guaFields.date ? guaFields.date : null);
	if(!Number.isFinite(birthYear) || !Number.isFinite(guaYear) || guaYear < birthYear){
		return null;
	}
	const genderVal = birth && birth.gender ? birth.gender.value : 1;
	const age = guaYear - birthYear;
	const ageCycle = ((age % 60) + 60) % 60;
	const yearList = `${genderVal}` === '0' ? FemaleRunYearList : MaleRunYearList;
	return {
		age: age,
		ageCycle: ageCycle,
		year: yearList[ageCycle] || '',
	};
}

// [issue#74] export 供金标直测:此函数是「页面显示对、AI 挂载错」的分水岭——render 侧一直
// 过它校正,快照侧曾裸拍。金标锚死其校正语义+快照侧收口在位,两路径同构不许再散。
export function resolveDisplayRunYear(runyear, birth, guaFields){
	const fallback = buildFallbackRunYearByYearDiff(birth, guaFields);
	if(!fallback){
		return runyear;
	}
	const currAge = runyear && runyear.age !== undefined && runyear.age !== null ? Number(runyear.age) : NaN;
	const currAgeCycle = runyear && runyear.ageCycle !== undefined && runyear.ageCycle !== null ? Number(runyear.ageCycle) : NaN;
	const currYear = runyear && runyear.year ? `${runyear.year}` : '';
	const ageDelta = Number.isFinite(currAge) ? Math.abs(currAge - fallback.age) : NaN;
	const cycleDelta = Number.isFinite(currAgeCycle)
		? Math.min(Math.abs(currAgeCycle - fallback.ageCycle), 60 - Math.abs(currAgeCycle - fallback.ageCycle))
		: NaN;
	const hardMismatch = (Number.isFinite(ageDelta) && ageDelta >= 2)
		|| (Number.isFinite(cycleDelta) && cycleDelta >= 2);
	const sameAgeYearMismatch = Number.isFinite(currAge)
		&& currAge === fallback.age
		&& currYear !== ''
		&& fallback.year !== ''
		&& currYear !== fallback.year;
	const useFallback = !runyear
		|| !Number.isFinite(currAge)
		|| (currAge === 0 && fallback.age > 0)
		|| currYear === ''
		|| (currYear === '丙寅' && fallback.age > 0)
		|| hardMismatch
		|| sameAgeYearMismatch;
	if(!useFallback){
		return runyear;
	}
	return {
		...(runyear || {}),
		...fallback,
	};
}

function buildMetaRows(obj){
	let res = [];
	if(!obj || typeof obj !== 'object'){
		return res;
	}
	for(let k in obj){
		let data = {
			key: k,
			value: obj[k],
		};
		let pidx = k.indexOf('(');
		if(pidx >= 0){
			data.key = k.substr(0, pidx);
		}
		if(data.value instanceof Array){
			data.value = data.value.join('');
		}
		res.push(data);
	}
	return res;
}

export const DA_GE_META = {
	yuanshou: {
		key: 'yuanshou',
		name: '元首',
		source: '元首课',
		highlight: '权威在上，先机在前',
		summary: '上克下之势明确，宜先发、主导、定规矩。',
		keywords: '权力、名望、先者、长辈',
	},
	chongshen: {
		key: 'chongshen',
		name: '重审',
		source: '重审课',
		highlight: '下凌上，逆势突起',
		summary: '局面带逆反与掣肘，宜反复核验，不可轻信表象。',
		keywords: '逆反、小人、后手、阴谋',
	},
	zhiyi: {
		key: 'zhiyi',
		name: '知一',
		source: '知一课/比用课',
		highlight: '多端并发，择一断轴',
		summary: '多方拉扯并行，先抓主线再决策，忌面面俱到。',
		keywords: '纷乱、僵持、疑虑、同类',
	},
	jianji: {
		key: 'jianji',
		name: '见机',
		source: '见机课/涉害课',
		highlight: '暗处寻机，细处破局',
		summary: '困难隐匿且牵连多，宜侦查细节、灵活机动。',
		keywords: '隐匿、探查、暗线、机变',
	},
	shishe: {
		key: 'shishe',
		name: '矢射',
		source: '蒿矢课/弹射课',
		highlight: '远力有克，实伤有限',
		summary: '多为远端牵制、口舌流言或轻微冲击，烈度有限。',
		keywords: '杳渺、虚惊、流言、小病',
	},
	hushi: {
		key: 'hushi',
		name: '虎视',
		source: '虎视课',
		highlight: '刚猛临门，进退皆险',
		summary: '刚烈强冲、监视对峙色彩重，宜慎冲突、稳节奏。',
		keywords: '刚猛、争斗、监察、远行',
	},
	wuyin: {
		key: 'wuyin',
		name: '芜淫',
		source: '别责课(刚日不备/柔日芜淫)',
		highlight: '阴阳失衡，欲争并起',
		summary: '结构有缺，易引发关系争夺与秩序失衡。',
		keywords: '残缺、匮乏、欲望、争夺',
	},
	weibu: {
		key: 'weibu',
		name: '帷簿',
		source: '八专课',
		highlight: '边界变薄，秩序混融',
		summary: '界限感减弱，私域外泄或关系混杂之象明显。',
		keywords: '融合、模糊、混乱、悖伦',
	},
	xinren: {
		key: 'xinren',
		name: '信任',
		source: '伏吟类课(不虞/自任/自信/杜传)',
		highlight: '粘连原位，难以分化',
		summary: '事项多回到起点或原地循环，信息闭塞、进展迟滞。',
		keywords: '原地、回轮、沉默、黏稠',
	},
	wuyi: {
		key: 'wuyi',
		name: '无依',
		source: '反吟类课',
		highlight: '冲动极盛，离散奔波',
		summary: '对冲变动强，结构易拆分，稳定性与归属感降低。',
		keywords: '对冲、变动、波折、分散',
	},
};

const COURSE_TO_DAGE_KEY = {
	'元首课': 'yuanshou',
	'重审课': 'chongshen',
	// 始入课=「九法变十法」开关下单一下贼上的单列名(ChuangChart.isJinKe0),大格判词同归重审;
	// 漏此键则该开关下断语参考整块静默消失(#46 全量巡查时补)。
	'始入课': 'chongshen',
	'比用课': 'zhiyi',
	'知一课': 'zhiyi',
	'涉害课': 'jianji',
	'见机课': 'jianji',
	'察微课': 'jianji',
	'缀瑕课': 'jianji',
	'蒿矢课': 'shishe',
	'弹射课': 'shishe',
	'虎视课': 'hushi',
	'掩目课': 'hushi',
	// 别责两名(2026-07-04 词汇增强:刚日不备/柔日芜淫,同归芜淫格)
	'芜淫课': 'wuyin',
	'不备课': 'wuyin',
	'八专课': 'weibu',
	// 伏吟四格(课经:有克不虞/刚日自任/柔日自信/初传自刑杜传,同归信任格)
	'不虞课': 'xinren',
	'自任课': 'xinren',
	'自信课': 'xinren',
	'杜传课': 'xinren',
	'无依课': 'wuyi',
	'无亲课': 'wuyi',
};

export const XIAO_JU_META = {
	yinv: {
		key: 'yinv',
		name: '泆女',
		categoryKey: 'yinyi',
		categoryName: '淫泆局',
		condition: '初传天后、末传六合',
		summary: '后合同传，情欲牵连与越界关系信号偏强。',
		priority: 98,
	},
	jiaotong: {
		key: 'jiaotong',
		name: '狡童',
		categoryKey: 'yinyi',
		categoryName: '淫泆局',
		condition: '初传六合、末传天后',
		summary: '后合同传且男象在先，多见引诱、私情、主动纠缠。',
		priority: 97,
	},
	yuantai: {
		key: 'yuantai',
		name: '元胎',
		categoryKey: 'xinyun',
		categoryName: '新孕局',
		condition: '三传俱孟（寅申巳亥）',
		summary: '孟地主新生，宜解作萌发、孕育、起新意。',
		priority: 88,
	},
	sanjiao: {
		key: 'sanjiao',
		name: '三交',
		categoryKey: 'yinni',
		categoryName: '隐匿局',
		condition: '四仲（子午卯酉）临日干/日支，三传皆仲，且三传并见太阴与六合',
		summary: '交缠与隐匿并见，关系线与暗线并行。',
		priority: 96,
	},
	zhanguan: {
		key: 'zhanguan',
		name: '斩关',
		categoryKey: 'yinni',
		categoryName: '隐匿局',
		condition: '辰戌临日干或日支',
		summary: '关隘压身，常见挣脱、越限、动荡突围之象。',
		priority: 90,
	},
	youzi: {
		key: 'youzi',
		name: '游子',
		categoryKey: 'yinni',
		categoryName: '隐匿局',
		condition: '三传皆季（辰戌丑未）且驿马、丁马同入课传',
		summary: '土墓见马，多应漂泊迁徙、离位奔波。',
		priority: 86,
	},
	bikou: {
		key: 'bikou',
		name: '闭口',
		categoryKey: 'yinni',
		categoryName: '隐匿局',
		condition: '旬首乘玄武、旬尾发用',
		summary: '封口藏机，信息不透，常见暗谋或缄默局面。',
		priority: 92,
	},
	jieli: {
		key: 'jieli',
		name: '解离',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '日干克日支上神，且日支克日干上神',
		summary: '主客分歧加剧，关系层面易冲突、解构、离散。',
		priority: 91,
	},
	luanshou: {
		key: 'luanshou',
		name: '乱首',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '日干临支受支克，或日支临日干寄宫并克日干',
		summary: '在上者受挟，主失控、背叛、暗箭之患。',
		priority: 95,
	},
	juesi: {
		key: 'juesi',
		name: '绝嗣',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '四课俱摄（上克下）',
		summary: '权势过强而下弱，常见秩序压制与后续乏力。',
		priority: 85,
	},
	wulu: {
		key: 'wulu',
		name: '无禄',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '四课俱贼（下克上）',
		summary: '下逆上之势全开，主反制、离散、结构失序。',
		priority: 85,
	},
	gugua: {
		key: 'gugua',
		name: '孤寡',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '孤辰与寡宿并现，且旬空同时入课传',
		summary: '孤离与空耗同现，事易虚化、聚合力偏弱。',
		priority: 82,
	},
	longzhan: {
		key: 'longzhan',
		name: '龙战',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '卯酉日；卯酉发用；行年卯酉',
		summary: '门户对冲，主激烈变动、进退拉扯与交战感。',
		priority: 84,
	},
	lide: {
		key: 'lide',
		name: '励德',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '贵人临卯或酉',
		summary: '贵人临门，秩序重排，常见升降与赏罚并发。',
		priority: 83,
	},
	zhuixu: {
		key: 'zhuixu',
		name: '赘婿',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '日干上神临日支，且日干克日支',
		summary: '内外依附明显，吉凶多从内里关系起伏而来。',
		priority: 80,
	},
	xingde: {
		key: 'xingde',
		name: '刑德',
		categoryKey: 'yinni',
		categoryName: '隐匿局',
		condition: '德神与刑神同见于课传',
		summary: '德刑并衡，利于判断好恶胜败与缉捕得失。',
		priority: 79,
	},
	wuqi: {
		key: 'wuqi',
		name: '物气',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '发用五行与日干同类',
		summary: '以日干与用神同类关系细分人物、物类与事类。',
		priority: 77,
	},
	xingu: {
		key: 'xingu',
		name: '新故',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '三传首末呈“孟/季”或“阳/阴”新旧转换',
		summary: '用于分辨新旧、少老与事态起终转换。',
		priority: 76,
	},
	tunfu: {
		key: 'tunfu',
		name: '迍福',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '发用同见多层凶象或福象',
		summary: '以迍福层数衡量艰难与顺畅的强弱。',
		priority: 76,
	},
	shizhong: {
		key: 'shizhong',
		name: '始终',
		categoryKey: 'guaibie',
		categoryName: '乖别局',
		condition: '初末传吉凶出现反转',
		summary: '重在初中末走势：先凶后吉或先吉后凶。',
		priority: 75,
	},
	jiuchou: {
		key: 'jiuchou',
		name: '九丑',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '九丑日且丑临日支',
		summary: '多主郁闷、臭名、灾阻与酒色牵连。',
		priority: 78,
	},
	tianwang: {
		key: 'tianwang',
		name: '天网',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '时支、初传共克日干',
		summary: '围攻成网，主埋伏、收束、难脱。',
		priority: 93,
	},
	feihun: {
		key: 'feihun',
		name: '飞魂',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '游魂临行年、日干或日支',
		summary: '失魂惊惧，易见鬼祟、恍惚与异感。',
		priority: 81,
	},
	sangmen: {
		key: 'sangmen',
		name: '丧门',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '丧门临行年、日干或日支',
		summary: '衰亡与丧气偏重，逢虎更速更烈。',
		priority: 82,
	},
	fuyang: {
		key: 'fuyang',
		name: '伏殃',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '天鬼临行年、日干或日支',
		summary: '灾殃偏扩散，常见疫病、兵伤与群体性不安。',
		priority: 83,
	},
	luowang: {
		key: 'luowang',
		name: '罗网',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '天罗或地网临行年、日干或日支',
		summary: '诉讼拘束、行动受限，易陷网罗。',
		priority: 84,
	},
	sanguang: {
		key: 'sanguang',
		name: '三光',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '日干、日支、初传皆旺相；三传皆乘吉神',
		summary: '光明开敞，纵见凶将也多可化解。',
		priority: 87,
	},
	sanyang: {
		key: 'sanyang',
		name: '三阳',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '贵人顺治且三传吉神偏多',
		summary: '朝阳之象，偏利驱邪、行旅与升迁。',
		priority: 86,
	},
	sanqi: {
		key: 'sanqi',
		name: '三奇',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '旬奇或干奇入课传',
		summary: '意外机缘与非常之象并见。',
		priority: 85,
	},
	liuyi: {
		key: 'liuyi',
		name: '六仪',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '旬仪或支仪入课传',
		summary: '重礼与秩序，规范性与领袖性增强。',
		priority: 84,
	},
	guanjue: {
		key: 'guanjue',
		name: '官爵',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '戌乘太常发用且驿马入课传',
		summary: '官位、任命与迁转信号增强。',
		priority: 88,
	},
	xuangai: {
		key: 'xuangai',
		name: '轩盖',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '子卯午在三传且时值正月或七月',
		summary: '名位、出游、华盖与仪仗之象。',
		priority: 83,
	},
	zhuolun: {
		key: 'zhuolun',
		name: '斫轮',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '卯临申',
		summary: '加工成器、制作雕凿、技艺显功。',
		priority: 82,
	},
	zhuyin: {
		key: 'zhuyin',
		name: '铸印',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '巳戌卯同见三传',
		summary: '掌权得位，最利官职前程。',
		priority: 89,
	},
	longde: {
		key: 'longde',
		name: '龙德',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '年支、月将共乘贵人且贵人发用',
		summary: '年月级别力量同振，格局量级偏大。',
		priority: 90,
	},
	lianzhu: {
		key: 'lianzhu',
		name: '连珠',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '三传依次相邻（进连珠或退连珠）',
		summary: '势能连绵，吉凶皆有持续效应。',
		priority: 81,
	},
	jianchuan: {
		key: 'jianchuan',
		name: '间传',
		categoryKey: 'keshi',
		categoryName: '课式局',
		condition: '三传等隔（隔一位，顺间传 / 逆间传，如寅辰午 / 午辰寅）',
		summary: '跳跃前行 / 后退，事非直线、有间隔阻滞，须越障而达。',
		priority: 78,
	},
	liuchun: {
		key: 'liuchun',
		name: '六纯',
		categoryKey: 'keshi',
		categoryName: '课式局',
		condition: '四课三传地支全阳（六阳）或全阴（六阴）',
		summary: '六阳气纯利公开、主动、显达；六阴气纯利私谋、隐晦、阴事。',
		priority: 77,
	},
	panzhu: {
		key: 'panzhu',
		name: '盘珠',
		categoryKey: 'keshi',
		categoryName: '课式局',
		condition: '三传尽入四课上神（三传皆为四课之神）',
		summary: '三传不出四课，事在目前、范围紧凑，无外溢之象。',
		priority: 76,
	},
	yanshang: {
		key: 'yanshang',
		name: '炎上',
		categoryKey: 'wuxingju',
		categoryName: '五行局',
		condition: '三传皆火（寅午戌）',
		summary: '火势上炎，急烈、躁进、冶炼之象。',
		priority: 74,
	},
	quzhi: {
		key: 'quzhi',
		name: '曲直',
		categoryKey: 'wuxingju',
		categoryName: '五行局',
		condition: '三传皆木（亥卯未）',
		summary: '木气伸展，成长、舟木、柔韧并见。',
		priority: 74,
	},
	jiase: {
		key: 'jiase',
		name: '稼穑',
		categoryKey: 'wuxingju',
		categoryName: '五行局',
		condition: '三传皆土（辰戌丑未）',
		summary: '土性沉稳，田宅、筑室、蓄藏之象。',
		priority: 74,
	},
	congge: {
		key: 'congge',
		name: '从革',
		categoryKey: 'wuxingju',
		categoryName: '五行局',
		condition: '三传皆金（巳酉丑）',
		summary: '金气决断，兵革、改制、锐进并行。',
		priority: 74,
	},
	runxia: {
		key: 'runxia',
		name: '润下',
		categoryKey: 'wuxingju',
		categoryName: '五行局',
		condition: '三传皆水（申子辰）',
		summary: '水势润下，流通、舟楫、渔网之象。',
		priority: 74,
	},
	wangyun: {
		key: 'wangyun',
		name: '旺孕',
		categoryKey: 'xinyun',
		categoryName: '新孕局',
		condition: '行年旺相，且三合胎育线成立',
		summary: '旺相与合局并见，主胎育、孕势偏强。',
		priority: 88,
	},
	deyun: {
		key: 'deyun',
		name: '德孕',
		categoryKey: 'xinyun',
		categoryName: '新孕局',
		condition: '行年天干互合',
		summary: '德合成孕，主关系黏合与胎息成象。',
		priority: 87,
	},
	erfan: {
		key: 'erfan',
		name: '二烦',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '宿盘太阳、月亮皆临四仲，且斗罡（辰）加临丑或未',
		summary: '天烦地烦并见，坎坷烦恼叠加。',
		priority: 88,
	},
	tianhuo: {
		key: 'tianhuo',
		name: '天祸',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '四立日且与昨日干支纠缠',
		summary: '节令交变中的尖锐两难与灾咎端口。',
		priority: 89,
	},
	tiankou: {
		key: 'tiankou',
		name: '天寇',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '分至日且月亮临昨日日支',
		summary: '旅路阴杀重，动中易遭劫扰。',
		priority: 89,
	},
	tianyu: {
		key: 'tianyu',
		name: '天狱',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '辰临日干长生且发用受困',
		summary: '根源受塞，虚弱拘束、近牢狱象。',
		priority: 90,
	},
	siqi: {
		key: 'siqi',
		name: '死奇',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '辰（斗）合日月死奇线',
		summary: '阴死之象增，病厄与应期并显。',
		priority: 85,
	},
	pohua: {
		key: 'pohua',
		name: '魄化',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '白虎携死神并临日辰行年',
		summary: '凶猛急烈，主重击与魂魄不宁。',
		priority: 92,
	},
	sanyin: {
		key: 'sanyin',
		name: '三阴',
		categoryKey: 'xiongfou',
		categoryName: '凶否局',
		condition: '贵人逆治且武虎先行，初末受困',
		summary: '秩序失调、驱策无力、时弃其人。',
		priority: 91,
	},
	fugui: {
		key: 'fugui',
		name: '富贵',
		categoryKey: 'jitai',
		categoryName: '吉泰局',
		condition: '贵人旺相并临日辰行年，三传生旺',
		summary: '荣耀富裕，贵位与资源同振。',
		priority: 90,
	},
	jiaji: {
		key: 'jiaji',
		name: '甲己',
		categoryKey: 'tianheju',
		categoryName: '天合局',
		condition: '课传天干甲己互合（同课上下 / 三传 / 日干与日支上神 / 日支与日干上神）',
		summary: '弱者求合、循环往复的甲己合象。',
		priority: 73,
	},
	yigeng: {
		key: 'yigeng',
		name: '乙庚',
		categoryKey: 'tianheju',
		categoryName: '天合局',
		condition: '课传天干乙庚互合（同课上下 / 三传 / 日干与日支上神 / 日支与日干上神）',
		summary: '乙庚合象，强弱博弈中的求和与反复。',
		priority: 73,
	},
	bingxin: {
		key: 'bingxin',
		name: '丙辛',
		categoryKey: 'tianheju',
		categoryName: '天合局',
		condition: '课传天干丙辛互合（同课上下 / 三传 / 日干与日支上神 / 日支与日干上神）',
		summary: '丙辛合象，冷热消长中的依附与回摆。',
		priority: 73,
	},
	dingren: {
		key: 'dingren',
		name: '丁壬',
		categoryKey: 'tianheju',
		categoryName: '天合局',
		condition: '课传天干丁壬互合（同课上下 / 三传 / 日干与日支上神 / 日支与日干上神）',
		summary: '丁壬合象，水火权衡中的求存与折返。',
		priority: 73,
	},
	wugui: {
		key: 'wugui',
		name: '戊癸',
		categoryKey: 'tianheju',
		categoryName: '天合局',
		condition: '课传天干戊癸互合（同课上下 / 三传 / 日干与日支上神 / 日支与日干上神）',
		summary: '戊癸合象，中央与北方力场的相就相离。',
		priority: 73,
	},
	jianggongshi: {
		key: 'jianggongshi',
		name: '绛宫时',
		categoryKey: 'gongshiju',
		categoryName: '宫时局',
		condition: '登明（亥）加四仲（子午卯酉）',
		summary: '天乙藏深宫之中，入游系宫，行于私宴。当此之时，不可出行，避罪逃亡者得。',
		priority: 72,
	},
	mingtangshi: {
		key: 'mingtangshi',
		name: '明堂时',
		categoryKey: 'gongshiju',
		categoryName: '宫时局',
		condition: '神后（子）加四仲（子午卯酉）',
		summary: '天乙出游四野八极，当此之时，举动百事皆吉，逃亡者难得，在内利主，在外利客。',
		priority: 72,
	},
	yutangshi: {
		key: 'yutangshi',
		name: '玉堂时',
		categoryKey: 'gongshiju',
		categoryName: '宫时局',
		condition: '大吉（丑）加四仲（子午卯酉）',
		summary: '天乙加门之中，天神在门方欲出行。当此之时，百事小不利，逃亡者可得也。',
		priority: 72,
	},
	doumeng: {
		key: 'doumeng',
		name: '斗孟',
		categoryKey: 'beidouju',
		categoryName: '北斗局',
		condition: '斗罡（辰）加孟',
		summary: '北斗加孟，主未发与远因之端。',
		priority: 71,
	},
	douzhong: {
		key: 'douzhong',
		name: '斗仲',
		categoryKey: 'beidouju',
		categoryName: '北斗局',
		condition: '斗罡（辰）加仲',
		summary: '北斗加仲，主当下留连与中段变化。',
		priority: 71,
	},
	douji: {
		key: 'douji',
		name: '斗季',
		categoryKey: 'beidouju',
		categoryName: '北斗局',
		condition: '斗罡（辰）加季',
		summary: '北斗加季，主结果端的收束与应验。',
		priority: 71,
	},
};

const DA_GE_REFERENCE_TEXT = {
	yuanshou: {
		poem: `四课一克下，元首是初神。
臣忠子孝顺，忧喜因男人。
论官先者胜，后到理不伸。`,
		note: `贼摄，只有一摄。
元首，即权威，对下行使权力。
上克下为摄。父教子、君控臣、男对女，皆是上摄下，先辈认为这理所当然，因此元首格备受尊崇。
我们不必在意陈旧伦理。`,
		yaodian: '权力、名望、长辈、先者。',
	},
	chongshen: {
		poem: `重审下凌上，子逆臣不恭。
事起女人忧，害主防妻从。
万般皆难顺，鬼病恐复重。
论讼伸理吉，虚张先诉凶。`,
		note: `贼摄，只有一贼。
重审，即谨慎，重新审视局面。
下克上为贼。子逆父、臣反君、女抗男，皆是下贼上，先辈认为这不合天理，因此才叫重审——“小心啊，再仔细看看，定有逆事贼人”。`,
		yaodian: '逆反、卑贱、小人、后者、阴谋、妖鬼。',
	},
	zhiyi: {
		poem: `知一卦何知，阴阳比日宜。
事因同灰起，婚嫁失和怡。
失物邻人取，逃亡不远离。
论讼和允好，为事尚狐疑。`,
		note: `比用。
知一，即果决，迅速权衡后当机立断。
比用有多处近克，说明此事必有多重矛盾，同时并发。择与日干阴阳相同者为用，即滤去末节、抓其主轴，于万军取上将首级。然而这只是理想，却非现实。知一格昭示的现实，往往多方势力僵持不下。若想从中渔利或抽身而退，则十分棘手。
此外，亦可取象为邻、兄、伙，类似他术“比劫”之意，同我者与我同欲，可分我财、夺我物。
疑虑万般，知一而择，这是此格在告诫；千丝万缕，欲解还缠，实乃此格之真相。`,
		yaodian: '纷乱、僵持、踌躇、疑虑、同类、邻居。',
	},
	jianji: {
		poem: `两比两不比，行事须见机。
涉深争发用，羁绊多迟疑。
忧患日难消，伤孕胎忌时。
盗贼邻里起，逃亡隐亲戚。`,
		note: `涉害。
见机，即冒险，寻找机会、灵活行事。
能到涉害这一步，事态已然混乱不堪，人力不能决疑，苦难不可解，甚至眼前一片空白，未见敌手、徒受其害。
必须从细处寻破绽，着眼于暗处，从忽视之处入手，找机会，抛开成见与惯性，见机行事。
此格与知一相似，多重困境，却更棘手——敌人无影，却如鲠在喉。`,
		yaodian: '沦陷、隐匿、侦查、探秘、细致、暗类。',
	},
	shishe: {
		poem: `蒿矢遥克日，射我当不畏。
弹射日克遥，侥中亦无力。
贵逆子不良，顺行臣不义。
宾来不可容，口舌西南至。`,
		note: `遥克。
矢射，即远力，路途杳渺而难至。

近克之力强，为手边之事；遥克之力弱，如天边之人。所谓只闻其信、未见其人，即矢射格。

分为两种，一为他神克日，名“蒿矢”，如别人用草作箭来射我，必无大碍；二为日克他神，名“弹射”，如我用玩具弹弓射人，徒留小伤。

由于克无力，只能用贵人顺逆来辅助取象，其实无论顺逆，都会有人对我不良不义，但皆是小动作、小算计，上不得台面，如同流言蜚语、造谣中伤。

无论远者克我，还是我克远者，我与远者终究有克，即隔阂。虽不至于摆明刀枪，但心有芥蒂，必难谐和。所以远来之宾难容。

至于口舌“西南至”，源于坤卦之辞——西南得朋、东北丧朋。由于远来之宾（朋）难容，得罪于朋友，自然口舌起于当初结识宾朋的西南。此句是对易经的引用，无伤大雅。`,
		yaodian: '杳渺、微弱、虚惊、流言、暗骂、小病。',
	},
	hushi: {
		poem: `昴星名虎视，秋酉知生死。
出入日月门，动留难进止。
刚徙身不归，柔匿忧祸起。
女淫问何因？出门难禁止。`,
		note: `昴星。
虎视，即凶猛，刚烈奋勇易履险。
前文已述，昴星在酉，酉为秋八月，金气极旺。而白虎（四象之一）恰在秋季。凡与金、秋、虎相关者，必凶险勇猛、不顾身家，如战场敢死之先锋，黄沙百战、万里不还。
此外，昴宿有“眼”之象。古人常抬头看昴，以测视力。易经之辟卦，酉（昴宿）亦对应观卦，所谓观我生进退、观国之光。观即看，引申为监视、巡查。所以此格称“虎视”，白虎监视或怒视。
一旦理解，其义自现。若成此格，事必乖张凶猛，难以招架。涉事之人也会有类似特征，比如女性刚强剽悍、剪碎束缚，逆乱寻淫。
“日月门”，指卯酉，为门户，引申为一切“可通”之义。家门可通，关系可通，女性私处亦可通。卯酉此义，诸书常见。`,
		yaodian: '刚猛、勇烈、争斗、监察、嗔怒、孤寡、远行。',
	},
	wuyin: {
		poem: `阴阳不备克，夫妇有外心。
争男阳不足，共女只单阴。
上克下夫过，反此妇不仁。
支干交互克，是乖失调琴。`,
		note: `别责。
芜淫，即缺憾，残缺失衡导致因欲斗争。
依拉康之说，人之欲望产生于残缺。某处有一空洞，欲望就会填满它，人即成为空虚且欲望的双重动物。欲望必然引发争吵，夫妻、父子、同事皆然。
此格还可看争夺，尤其“小三”。原理是，阳有两课、阴有两课，共四课，现在缺了一课，就只有一阳双阴、一阴双阳两种结果。如王弼所言，多阴单阳，如女争夫；多阳单阴，如男争妻。所以此格之象，二男争女、二女争男。
当然，残缺之处，即欲望源头，可依次寻因。不再赘述。`,
		yaodian: '残缺、匮乏、欲望、争夺、失和。',
	},
	weibu: {
		poem: `八专惟两课，阴阳杂不明。
家门无礼存，夫妇总不贞。
六合兼元武，叔嫂妹淫兄。
人伦真难测，玄女鉴留经。`,
		note: `八专。
帏薄，即混乱，欲要融合必消弭边界。
以人事为例，我国传统伦理，重视一衣带水的亲族，大家庭间少有隔阂、不讲原则、忽视个体界限，此即八专。而现代工业社会则强调个体边界，即便父母子女，也不可越矩，此即秩序井然。同样，我国古代君臣之间、男女之间，亦重秩序，所谓“礼”，与上述宗族之通融有别。
秩序井然变为界限不明，即此格之义。帷，是用以遮蔽隐私的帘幕，即个人私生活的界限，帷幕太薄，便会透光，被别人所窥，甚至自己掀开帘幕迎人进入，个体之防卫即告终结。所以可引申为偷窥、淫乱、悖伦。无非是界限虚化、秩序崩塌。
君臣本该尊卑有别，而今鱼水一家，现在我们称之“管理扁平化”，但封建的古代就以为大逆不道，立场不同罢了。
欲与子同袍，必共弃界限，如此矛盾，乃千古难题。`,
		yaodian: '融合、协力、混乱、模糊、悖伦、交媾、爱情。',
	},
	xinren: {
		poem: `信任伏吟神，行人立至门。
失物家内盗，逃者隐乡邻。
病合难言语，占胎聋哑人。
访人藏不出，行者却回轮。`,
		note: `伏吟。
信任，即粘连，难分化而无生机。
世间人事，必须先分化，再交互，才形成百态。而伏吟相反，未分化、无交互，所谓“鸡犬相闻，老死不往来”。人皆只在乎自己，事皆与外界相隔。如希腊的那喀索斯，忽视一切，只爱镜中的自己。用胶水把自己与自己粘合，即为伏吟。
所以失物在家里、逃者隐于原地。粘连原处，必难分开。而病难言语、生子聋哑，无非是双唇粘连、七窍不通之象。
此格之人事，皆会在它最初所在，会回溯至分化前，除此之外，大千静谧，难动难通。`,
		yaodian: '家乡、原地、起点、黏稠、死寂、沉默。',
	},
	wuyi: {
		poem: `无依是返吟，逃者远追寻。
合者应分散，安巢改别林。
守官须易位，结友也分襟。
臣子俱怀背，夫妻有外心。
所为多反复，占病两般侵。`,
		note: `反吟。
无依，即孤独，奔波而无枝可依。
伏吟到反吟，逐渐从极静变为极动。反吟已然是冲动的极点。无穷分化、无限交互，万物对冲演变，如高能粒子对撞。一梦千年。
简言之，此格即二元对立，相逆之物各据一方，相爱相杀。这对立纯粹，无关欲望、没有原由，它只是冲突着，如同含笑不语的大千。颠覆你，与你无干。
习惯却颠覆，珍爱遭抹除，古旧被革新，沧海已桑田。雨燕永飞，无处安停。`,
		yaodian: '二元、复数、对冲、变动、革新、波折、分散、天涯。',
	},
};

const XIAO_JU_REFERENCE_TEXT = {
	yinv: {
		poem: `天后厌翳神，六合是私门。
二将淫泆女，夫妻异情恩。
欲知谁淫荡，传中辨将论。
六合男诱女，元武携男奔。`,
		note: `天后与六合，同现三传，必男女情欲。
初传天后，末传六合，成局。女性淫荡，称“泆女”。
初传六合，末传天后，成局。男性狂荡、引诱女性，称“狡童”。
天后为女、六合为男。三传有先后，在先者为因，所以天后在先（初传）即女为因，六合在先（初传）即男为因。
二者统称“后合”，有一名言“后合占婚岂用媒”，即指——后合同现则男女必已生情纵欲，不须家长费心包办。若后合再携卯酉（门户可通），必成交媾，或已私奔。`,
	},
	jiaotong: {
		poem: `初传六合，末传天后。
男象在先，女象在后。`,
		note: `天后与六合，同现三传，必男女情欲。
初传六合，末传天后，成局。男性狂荡、引诱女性，称“狡童”。
天后为女、六合为男。三传有先后，在先者为因，所以天后在先（初传）即女为因，六合在先（初传）即男为因。
二者统称“后合”，有一名言“后合占婚岂用媒”，即指——后合同现则男女必已生情纵欲，不须家长费心包办。若后合再携卯酉（门户可通），必成交媾，或已私奔。`,
	},
	yuantai: {
		poem: `三传何俱孟？生地主婴孩。
百事皆新意，怀胎结偶来。`,
		note: `元胎，三传皆孟（寅申巳亥），孟为变动、新生，因此有孕育、革新之义。`,
	},
	sanjiao: {
		poem: `昴房加日辰，阴合又骈臻。
今又逢子午，三传四仲因。
家匿奸私客，自逃或避迍。
蛇火勾陈斗，武盗虎杀人。`,
		jushi: '仲（子午卯酉）临日干、日支；且三传皆仲；又有太阴、六合在三传。',
		juyi: '交合、纠缠、不明、隐藏、欺瞒、淫秽、人情。',
		juzhu: '昴，为星宿，在酉；房，为星宿，在卯。昴房指代卯酉。子午卯酉，四仲之地，为沐浴所在，常与裸露、男女色情有关，因此常称“咸池”，俗称“桃花”。犹如人成熟而多欲。',
	},
	zhanguan: {
		poem: `魁罡临日辰，卦名是斩关。
神光参玉女，功曹太阴间。
更有龙与合，勿令捕此奸。`,
		jushi: '辰或戌临日干或日支。',
		juyi: '超越、挣脱、自由、动乱。',
		juzhu: `斩关，即斩开关隘、得以脱逃。辰戌皆有牢狱之义，囚禁而限制人，引申为“困难”。二者加临日干或日支，犹如泰山压顶，亦如雄关在前，人难以逾越，因此必须战胜它。追求自由的主体，与限制自由的关隘，形成二元对立。

增注： 若课传有龙合寅卯六甲，或携丁马、贵阴，则关隘难挡，动而难捕，可脱困而自由。原理是，辰戌关隘之五行为土，欲破此关必用木，因此龙合寅卯六甲（皆属木）有益脱困；而丁马主变动、贵人为庇护、太阴是暗匿，亦可自由。`,
	},
	youzi: {
		poem: `三传皆四季，旬丁天马并。
占身出游子，天涯地角寻。
传出阳远行，传入阴伏匿。
墓神并杀害，冤家刑迫逼。`,
		jushi: '三传皆季（辰戌丑未）；丁马、天马入课传。',
		juyi: '漂泊、流离。',
		juzhu: `四季之地，辰戌丑未，皆是土，且为墓库，其义为终结、沉淀。若只是三传皆季，则称“稼穑”局，即土局，万事静滞、杂融而难动。惟有在此基础上，课传现丁马或天马，才成“游子”局。土局有马，即马踏四方大地，流浪之象。

增注： 三传先阴后阳，则由静变动，离家外出之象；三传先阳后阴，则由动化静，天涯躲藏之象。由于土神皆墓，晦暗复杂，一旦辰戌丑未携带恶煞，必遇怨仇。`,
	},
	bikou: {
		poem: `阳神作元武，度四是终阴。
此名闭口卦，逃者远追寻。
亡人随武匿，盗贼往终擒。
顺行阳数起，逆行阴所临。
婢走求阳处，奴逃须责阴。`,
		jushi: '旬首乘元武；旬尾临旬首；旬尾发用。',
		juyi: '闭嘴、哑巴、城府、阴谋、封锁、苦闷、难言。',
		juzhu: `一旬之首，如人之口。元武黯然，旬尾塞口。假设今天是庚午日，即在甲子旬中， 子为旬首，酉是旬尾。

增注： 此局可用于捉贼、寻失。女婢或阴物，在旬首下神方向；男奴或阳物，在旬尾下神方向。`,
	},
	jieli: {
		poem: `解离视行年，察地后观天。
夫妻互冲克，地天两相煎。
金盆将覆水，玉轸音悲怜。`,
		jushi: '二人的行年上神相冲且克相。',
		juyi: '冲突、解散、矛盾、离异。',
		juzhu: `用于判断人际关系，尤其婚恋之事。

增注： 《心镜》是以行年代指人。若只有两人，亦可以日干、日支代指主客双方，若日干克日支日支上神、且日支克日干上神，则也可称为“解离”，与上文同论。`,
	},
	luanshou: {
		poem: `日往辰被克，发用为乱首。
臣欺君害父，妻背夫犯兄。
奴婢不从主，将军愤其兵。
日尊辰卑小，犯上忌此刑。`,
		jushi: '日干临日支，被日支克。',
		juyi: '失控、谋逆、背叛、暗箭。',
		juzhu: `日干是主、为尊者，握有权力；日支是臣，承担责任。如今日干加临日支，犹如君主巡阅军队，或视察地方各省。此时日干被日支所克，即遭其背叛与挟持。由于已然临支，出行在外，君主落入圈套便插翅难逃。君主被劫，即称“乱首”。

增注： 另有一法。日支临日干，克日干，亦称“乱首”。此象是臣民主动背叛、攻陷君主之殿，然后劫持。两种乱首，一者是君主自招其祸，一者是臣下蓄谋主动，意义有别。`,
	},
	juesi: {
		poem: `四课俱克下，律法威严论。
臣子忧殃起，无禄何以尊？
孤老谁扶持？空室无人存。
官门小抵罪，论讼理不伸。`,
		jushi: '四课的每一课皆摄（上克下）。',
		juyi: '威权、秩序、严苛、酷政、欺压、绝后。',
		juzhu: `在上者为尊，是老，亦夺先机；在下者为卑，是少，亦步后尘。四课皆摄，朱门酒肉臭、路有冻死骨，卑者、少者、后者必惨败。

增注： 若遇此局，勿与尊者、权威相争。凡与法律擦边的灰色地带，勿持侥幸，必速败亡。若占生育，或求子嗣，则镜花水月，恐有绝后之患。少者飘零，老者无养。`,
	},
	wulu: {
		poem: `四课俱贼上，如何保双亲？
妻背夫背主，子弑父弑君。
占孕忧害子，孤茕失业人。
论讼忌先起，必定雪难伸。`,
		jushi: '四课的每一课皆贼（下克上）。',
		juyi: '叛逆、混乱、孤冷、反制。',
		juzhu: `禄为官职俸禄，无禄即丟官，此局四课皆贼，官作为在上者被逼而亡，所以称“无禄”。无禄局与绝嗣局相对。前者皆贼，逼死在上者；后者皆摄，压迫在下者。

增注： 古代由于封建道德，认为在下者反叛则必遭镇压而断子绝孙，在上者严刑峻法则必定导致人心离散而无民可治，因此历代古籍中四课皆贼称“绝嗣”、四课皆摄称“无禄”。此言不妥。把道德观念视为准则，必会让学者步入歧途，为假象所惑。因此，编者反转两局名称，以合局义。`,
	},
	gugua: {
		poem: `天寡地孤神，空用六甲旬。
孤独离桑梓，财无伴不亲。
官位宜改动，行访无亲人。
百事皆非实，讼病不害身。`,
		jushi: '孤辰、寡宿、旬空，皆在课传。',
		juyi: '孤独、虚无、不聚、出世。',
		juzhu: '孤辰与寡宿，合称“孤寡”。旬空有空而不实之义，可引申为脱离世俗，与日常家庭生活相悖。',
		basis: `孤辰： 春巳、夏申、秋亥、冬寅。
寡宿： 春丑、夏辰、秋未、冬戌。`,
	},
	longzhan: {
		poem: `龙战二八门，春生秋杀分。
燕来燕去兆，雷收雷发震。
卯酉日占事，年用又斯神。
刑德俱合此，出南入北迍。
行人疑进退，弟乖妻不亲。`,
		jushi: '卯酉日；卯酉发用；行年卯酉。',
		juyi: '激烈、战争、动荡。',
		juzhu: `二八门，即卯酉。宏观上，卯为二月春分，酉为八月秋分，前者万物并生、后者大千肃杀，一者生、一者死，所以卯酉一旦叠现，必阴阳交战。微观上，卯为清晨太阳初升之时、酉是黄昏太阳沉落之刻。空间上，卯为东方，日月从此升；酉是西方，日月从此没。因此，卯酉又是“门户”，取象为出入。阴阳生死交战、出入门户，即此局所象。

增注： 二月，燕来、雷发；八月，燕去、雷收。至于“刑德”，则二月春分是德、八月秋分为刑，一如《马王堆帛书》所述东为德、西为刑。所以卯酉共现，即“刑德俱合”。`,
	},
	lide: {
		poem: `世以何励德，卯酉日月门。
天乙既上立，贵贱位各分。
阴前阳处后，尊升卑吏迍。
庶身宅移动，魂梦难安神。`,
		jushi: '贵人临卯或酉，不必在课传。',
		juyi: '变迁、升降、赏罚。',
		juzhu: `卯酉取象出入门户，贵人本该安坐庙堂，如今却临门动摇。十二神皆围绕贵人，所以也随贵人之动而动。秩序跌宕。一课上神、三课上神皆阳，阳宜显贵，若一三上神在贵人之后，则其所指代之人必晋升，其事必显扬；二课上神、四课上神皆阴，阴应匿藏，若二四上神在贵人之前，即为僭越，其所指代之人必遭跌罚，其事遗臭或退藏。

增注：此局以贵人为中心，由贵人临变引申出秩序将变，再从诸神在贵人之前后，判定晋升或贬谪、升降与赏罚。握此主脉即可运用自如。`,
	},
	zhuixu: {
		poem: `日干往克辰，辰来日制身。
婿寄妻家住，嫁携男就人。
灾庆皆主内，天官决事因。`,
		jushi: '日干临日支，克日支。',
		juyi: '控制、揩油、入赘、入主。',
		juzhu: `与“乱首”局相对。皆是日干临日支，乱首是日干被克，所以被叛；赘婿则日干克支，所以入主其家。如男子一无所有，却入赘女家，成其家主，因此称“赘婿”。乱首日干被克，日干之象皆不吉，矛盾激化于日干，日干主外，所以事起于外；赘婿日支被克，日支之象皆不利，矛盾激化于日支，日支主内，所以事起于内。

增注： 另有一法。日支临日干，被日支克，亦属“赘婿”。但意义已变，不再是男子入主女家，而是女子追求男子、依存男子，女入男家而受制。经常是女子已有身孕，欲寻人接盘。`,
	},
	xingde: {
		poem: `刑德好恶分，德刑在日辰。
阴德从阳合，阳德自处尊。
寅午戌刑火，申子辰木林。
巳酉丑指西，亥卯未北归。
德刑同一位，良贱皆隐身。
德胜刑易获，刑胜德无因。`,
		note: `刑德，即研究刑与德的胜败关系。
刑。日支是寅午戌，刑为火；是申子辰，刑为木；是巳酉丑，刑为金；是亥卯未，刑是水。
德。日干是甲己，德为木；是乙庚，德为金；是丙辛，德为火；是丁壬，德为水；是戊癸，德为土。
二者五行属性，因而有胜败：克者胜、被生者胜；被克者败、生者败。假设刑为金，德为木，金克木，则刑胜德。
~~邢~~「刑」之义为叛逆、破坏，象征贼匪；德之义为良德、秩序，象征警察。因此，捉贼、寻失时，若德胜刑，则易获；若刑胜德，则难获。
而德与刑五行相同，警与匪的二元对立消失，或者二者身份模糊不清（无间道），或者贼匪早已远走他乡、隐形更名，警察亦无心缉拿。

增注：
刑，其实是术数常用的“三刑”；德，其实是术数常用的“天干五合”，每一对天干五合中，其德皆在阳干。
由于上文只须衡量五行的胜败，因此并未展开。详见下文。

刑，
· 寅刑巳，戌刑未，午自刑。皆是南方火。
· 申刑寅，子刑卯，辰自刑。皆在东方木。
· 巳刑申，酉自刑，丑刑戌。皆在西方金。
· 亥自刑，子刑卯，未刑丑。皆在北方水。

德，
· 甲德在甲，己德亦在甲；
· 庚德在庚，乙德亦在庚；
· 丙德在丙，辛德亦在丙；
· 壬德在壬，丁德亦在壬；
· 戊德在戊，癸德亦在戊；`,
	},
	wuqi: {
		poem: `用神与日类，物气辨否臧。
木用水为气，当忧父母亡。
见木称兄弟，同类事可量。
小吉知何类？妻奴及酒羊。
亥猪辰龙蛟，旺生墓已凉。`,
		note: `即通过诸神与日干的五行关系，判断其神的类象。
木日，水神为父母，因水生木；金日，火神是丈夫，因火克金……
十二神亦各自有其象，如未可取象为家庭、田宅、酒宴、羊。依前文《神》章所述。`,
	},
	xingu: {
		poem: `新故不易分，刚柔辨斯文。
刚用阳神气，物成不染尘。
柔求德临日，乙庚土作因，
丑临干死旧，辰加日生新。`,
		note: `用于判断物的新旧、人的老少、事的初终。
长生、旺相、孟、阳、德，为物之新、人之少、事之初；
墓库、休囚、季、阴、邢，为物之旧、人之老、事之终。`,
	},
	tunfu: {
		poem: `迍福详凶吉，意推无定神。
刑冲克墓死，恶将叠几迍？
旺生吉神将，福海几何恩？
多福灾渐退，病愈冤得伸。`,
		note: `计算某神同一时间遭遇几层凶象。迍，苦难。
八迍——遭刑、遇冲、受克、失助、被墓、休囚、凶将、恶煞。
五福——得助、长生、旺相、吉将、良煞。
所遇迍数越多，此神之象越凄惨；所遇福数越多，此神之象越舒畅。

当然，这计数只是姑且之言，并非必须集齐八迍才现凶、集齐五福才转吉。实践中，只有要两迍、三迍，就已然是凶。而且，八迍、五福，也绝非一加一等于二，而是各有其意指，如刑为焦灼、冲为对立、克为打压……须诸君细分。`,
	},
	shizhong: {
		poem: `始终在临时，神将重传思。
后吉终成美，先凶只源夭。`,
		note: `初传是“始”，末传为“终”。
若初传不良，则此事初期多舛；若末传凶恶，则此事后期惊险。
初传凶而终传吉，事态转危为安；初传吉而终传凶，事态从安变危。
总之，此局之义，是从三传变化推导事态发展，初期、中期、末期分别对应初传、中传、末传，以定情势。`,
	},
	jiuchou: {
		poem: `乙戊己辛壬，下领四仲神。
大吉临支辰，凶灾将及人。
大小二时会，刚男迍柔阴。
重阳妨害父，重阴母失温。
莫纳妻嫁女，忌游行出军。`,
		jushi: '九丑日；丑临日支。',
		juyi: '丑恶、臭名、郁闷、酒色、灾难。',
		juzhu: `（五暗干）乙、戊、己、辛、壬，与（四仲）子、午、卯、酉搭配，共有十日——乙卯、己卯、辛卯、乙酉、己酉、辛酉、戊子、壬子、戊午、壬午。此十日，称“九丑日”。
四仲，前文已述，为淫荡交合之象，亦是二分二至所在，因此又可取象为阴阳变迁（子午）及交战（卯酉）。总之是出入交媾。而“五暗干”，据《订讹》所说——乙者，雷始震之日；戊己，北辰下降之日；辛者，万物断绝之日；壬者，三光不照之日。所以其象皆黑暗。依注者之见，五暗干亦与卦位有关——此五干之寄宫为辰、巳、未、戌、亥。辰巳是巽（风）、戌亥为乾（天），无论是天风之姤卦，抑或风天之小畜卦，皆是蓄闷不正之象。至于未，则是坤卦之阴（坤阳在申），又有酒宴之象。所以此五干昏闷，与四仲合象，自然腐败而蓄郁。正如《壶中子》所言，“老醉秦楼十二，直缘重犯八专；少亡楚甸八千，应是迭逢九丑”。九丑可致愤懑无志、借色消愁。九丑日不利兵战、嫁娶、旅行，在黄道择日之术中颇为重要。

增注： 原文提及一法。一旦大时（桃花）临小时（月建），或小时临大时，若当日是阳日且日干上神、日支上神皆在贵人之前，则男性、父亲必凶，称为“重阳”；若当日是阴日且日干上神、日支上神皆在贵人之后，则女性、母亲必凶，称为“重阴”。

大时，正月在卯逆行四仲。小时，正月在寅顺行十二宫，即月建。`,
	},
	tianwang: {
		poem: `时用同克日，天网四张临。
忧事缘何发，天将断客心。`,
		jushi: '时支、初传共克日干。',
		juyi: '埋伏、收网、捕获。',
		juzhu: `初传是六壬中力量最强之处，既主导事态，又是事态之因；时支是最敏锐易动之处，诞生多样与可能，因此月将加时，奠定六壬之根基。一旦二者共克某神，其神必败。在劫难逃。占卜时，日干往往是卜者自己，或所卜之人事的主体。所以，若日干被时支、初传围攻，则“天网四张、万物尽伤”，陷于十面埋伏，唯听四面楚歌。卜者自己，或所卜之人事，极易落网。或是被捕，或是被伏。遇此残局，切莫乖张，必致速祸。`,
	},
	feihun: {
		poem: `游魂临年日，用兼恶将并。
飞魂魂不定，逢鬼祟又惊。
煞居何处所？正月顺登明。`,
		jushi: '游魂临行年、日干、日支。',
		juyi: '失魂、惊魂、鬼魂。',
		juzhu: '游魂，乃神煞。月建之后第四位。正月亥、二月子、三月丑……游魂临行年，其人被鬼魂纠缠，或自身已然失魂；临日干亦同；临日支，宅有鬼，或多惊异离奇。发用更甚。',
	},
	sangmen: {
		poem: `丧门正月未，四季游逆推。
用年日辰上，病死健人衰。
白虎凶转恶，言之事莫疑。`,
		jushi: '丧门临行年、日干、日支。',
		juyi: '丧事、衰亡。',
		juzhu: '丧门，乃神煞。正月在未，逆行四季之地。二月在辰、三月在丑、四月在戌、五月在未、六月在辰……若丧门乘白虎，则死丧之事出人意料且极速。发用更甚。',
	},
	fuyang: {
		poem: `天鬼依四仲，寅建酉逆寻。
年日上逢此，殃伏乱杀人。`,
		jushi: '天鬼临行年、日干、日支。',
		juyi: '瘟疫、扩散、灾殃、兵伤。',
		juzhu: '天鬼，乃神煞。正月在酉，逆行四仲之地。二月在午、三月在卯、四月在子、五月在酉、六月在午……其特殊在于，凶险可能传播扩散，无论鬼祟或疾病，皆为恶广泛，并非针对个体。发用更甚。',
	},
	luowang: {
		poem: `日前天罗杀，对冲地网神。
用年支干上，官灾病厄迍。
雀火白虎病，蛇怪梦惊人。`,
		jushi: '天罗或地网临行年、日干、日支。',
		juyi: '诉讼，局限。',
		juzhu: `天罗、地网，乃神煞。天罗，即日干前方一神；地网，即天罗对冲之神。比如，甲日，甲寄于寅，则寅前一神为卯，卯即天罗；卯冲酉，酉即地网。此局所用天罗地网，是从日干而来，犹如日干所撒渔网，或专门捉捕日干、限制日干的网。与辰戌牢狱有别。作用对象、捉捕范围皆有差异。`,
	},
	sanguang: {
		poem: `日辰用俱旺，传复有吉神。
三光无相克，多欢病者轻。
纵尔逢凶将，灾患事不忧。`,
		jushi: '日干、日支、初传皆旺相；三传乘吉神。',
		juyi: '光明、开敞、热闹。',
		juzhu: '旺相则有力，如人壮年，事业鼎盛。三处皆旺相，犹日朗晴空，恣意且舒远，难被束缚。只要三传之神不违日辰行年，即便乘凶将亦无大碍。',
	},
	sanyang: {
		poem: `天乙方顺行，日辰气居前。
用神兼旺相，三阳保庆安。
相生神将吉，旅利职高迁。
病解讼伸雪，凶将亦无愆。`,
		jushi: '贵人顺治；日干、日支皆在贵人之前；日干、日支、初传皆旺相。',
		juyi: '驱邪、祛病、朝阳、明媚。',
		juzhu: '与“三阴”局相对，意义与类象皆相反。诸君参酌二者，以衔其髓。',
	},
	sanqi: {
		poem: `三奇用旬行，两处共一名。
午申旬神后，寅辰旬登明，
子戌旬大吉，不忌杀与刑。
甲午乙日巳，支逆己丑停，
庚始顺在未，癸戌总有灵。
值两奇皆喜，传将更要精。`,
		jushi: '旬奇或干奇在课传。',
		juyi: '奇遇、意外。',
		juzhu: `旬奇、干奇皆神煞。旬奇在课传，即便被刑或带煞亦无妨，干奇则易受挫。何故？因为在时间层面，旬大于日，当日之刑难刑上级之旬。而干奇，由当日日干而来，所以必受刑害。

旬奇。甲午旬、甲申旬，在子；甲寅旬、甲辰旬，在亥；甲子旬、甲戌旬，在丑。
干奇。甲日在午、乙日在巳、丙日在辰、丁日在卯、戊日在寅、己日在丑、庚日在未、辛日在申、壬日在酉、癸日在戌。

增注：旬奇要么是亥，要么是子，要么是丑。所以，一旦亥、子、丑皆在三传，即称“三奇连珠”，所遇之事必超于常理，神秘莫测，与计划相悖。若课传再有良好格局，则一日九迁、平步青云，意外之大喜。`,
	},
	liuyi: {
		poem: `六仪居旬首，甲子旬神后。
支仪子配午，配逆逐辰移。
用仪名善卦，须末有吉随。`,
		jushi: '旬仪或支仪在课传。',
		juyi: '仪式、肃穆、礼节、领袖。',
		juzhu: `旬仪、支仪，皆神煞。旬仪又名六仪，因它是每旬首日的地支，共有六旬，每旬有一个旬仪，所以旬仪有六，称为六仪。六仪局与三奇局相对，六仪为规范，三奇是意外。一者庄重肃穆，一者神奇神奇难测。

旬仪，即旬首之地支。甲子旬，在子；甲寅旬，在寅……
支仪。子日在午，逐支逆推。丑日在巳、寅日在辰、卯日在卯、辰日在寅、巳日在丑……`,
	},
	guanjue: {
		poem: `印绶两俱用，四驿马逢传。
值此名官爵，终吉道途通。`,
		jushi: '戌乘太常发用；驿马在课传。',
		juyi: '官职、上任、升迁。',
		juzhu: `戌为印，太常是绶，合称“印绶”，官位职权之象。至于驿马，亦是骑乘而变动之象。我国常用马指代官员的升降，如“上马”、“落马”。能否乘马，是古代社会的身份象征。所以，印绶、驿马在传，取象官爵。

增注：此局所谓“四驿马”，是指年支、月支、日支、行年各有其驿马。四种驿马，皆可助成此局。但其他格局一般只用日支驿马，不采其他。`,
	},
	xuangai: {
		poem: `华盖居神后，天驷房太冲。
胜光正月马，六阳顺申同。
高盖乘轩马，龙常禄位丰。`,
		jushi: '子、卯、午皆在三传；时值正月、七月。',
		juyi: '华丽、名位、出游、遮盖。',
		juzhu: `午，如生肖所言，象为马；卯，林木舟车，有车之象；子，其中之虚宿，像马车上的华盖，用于遮风挡雨、亦彰显身份。三者合象，即奢华马车，正是此局之义。至于必须时值一月、七月，乃是由于此两月天马在午、天车在卯，煞（天马、天车）与神（午、卯）叠象之故。

增注： 若此局再遇驿马、青龙、太常，其人必升迁。但此局不利占病，如绝命之车，载赴黄泉。`,
	},
	zhuolun: {
		poem: `庚辛为金斧，卯木作车轮。
太冲来金上，斫轮衣紫朱。
传内太常绶，龙合登高舆。`,
		jushi: '卯临申。',
		juyi: '成器、雕刻、制作、加工、劈砍。',
		juzhu: `申，阳金，刀斧之象。卯，林木，木料之象。卯临申，如用利器雕凿原木。而“斫轮”即加工木料、制成车轮，遂有此名。

增注： 有书认为，卯临庚或辛，亦是斫轮。如甲子旬中，庚在午，此时卯临午（午中有庚），成斫轮局。`,
	},
	zhuyin: {
		poem: `戌印何为铸？临巳得冶炉。
末有卯车在，铸印车爵成。
传有气疾速，又兼驿马并。
太阴私事立，贵顺君令明。`,
		jushi: '巳、戌、卯皆在三传。',
		juyi: '掌权、得位。',
		juzhu: `戌临巳，则丙（巳中）辛（戌中）相合，巳是火、戌为印，炉冶锻造之象，锻出戌印，遂称“铸印”。卯之象为车。所以三传巳戌卯，乃铸印、取印、登车之义，全称“铸印乘轩”，必主权柄，最利官职前程。

增注： 若三传生旺，则格局极高；若驿马是巳，则掌权迅速。`,
	},
	longde: {
		poem: `太岁作贵人，发用兼月将。
龙德官禄位，恩赐贺圣君。`,
		jushi: '年支、月将共乘贵人；贵人发用。',
		juyi: '无双、惊天、如龙。',
		juzhu: `年月日时，等级有别——年为国；月为省；日为城；时为街。其所代表的权力、资源、量级皆大不相同。一旦涉及年月，必惊动“天庭”，这在古代牵涉君臣将相，在现代牵涉社会巨头。所谓“龙德”，磅礴而出，烈震而游，雄浑而没，指能量极大。若卜大事，前途若龙；若卜小事，常人难受。

增注： 此局罕见。有志者遇之，跃飞九天；无志者遇之，必被震慑。市井纠纷遇龙德，恐演变为惊天丑闻。`,
	},
	lianzhu: {
		poem: `孟仲季古传，尊卑位不偏。
或是岁月日，累累月相连。
皆曰连珠卦，事绪百盈千。
凶则灾不已，吉则庆缠绵。
三传同一处，谋干利成全。
岁月日时建，顺带逆迟延。`,
		jushi: '三传之神依次相邻。',
		juyi: '连绵，顺势。',
		juzhu: `有两种连珠——进连珠，三传递进；退连珠，三传递退。如三传卯辰巳，递进，为进连珠；三传未午巳，递退，为退连珠。无论进退，连珠皆有连绵不绝之象，只是方向不同。进连珠向前、向外、向新绵延；退连珠向后、向内、向旧绵延。若占旧病，退连珠，则病必难治；若占职位，进连珠，则稳步而前。

增注： 连珠局有时可“会”五行局。如寅卯辰，进连珠三传会东方木局；戌酉申，退连珠三传会西方金局。形成会局，三传一气，其气荟萃集中，必有所验之象。须诸君留意。`,
	},
	yanshang: {
		poem: `寅午戌炎上，三传俱火名。
日君人性急，釜鸣炉冶晴。`,
		note: `三传皆为同一五行，即成五行局。名称随五行而各异。
三传皆火，称“炎上”。如火焰跃动闪烁，华丽却燥热。
三传皆木，称“曲直”。如林木柔韧参天，强直又密盛。
三传皆土，称“稼穑”。如沃土依规耕种，沉稳而井然。
三传皆金，称“从革”。如锐刃锋芒刺破，刚硬反易折。
三传皆水，称“润下”。如流水善下不争，融容乃消弭。

若成五行局，只须依照五行而取其对应意义、类象即可。比如，水局可取江海之象、沟壑之象；火局可取炉灶之象、冶炼之象、晴空之象。不一而足，诸君须持一化万千。`,
	},
	quzhi: {
		poem: `曲直东方木，传亥卯未并。
占者筏及木，病者风致萦。`,
		note: `三传皆为同一五行，即成五行局。名称随五行而各异。
三传皆火，称“炎上”。如火焰跃动闪烁，华丽却燥热。
三传皆木，称“曲直”。如林木柔韧参天，强直又密盛。
三传皆土，称“稼穑”。如沃土依规耕种，沉稳而井然。
三传皆金，称“从革”。如锐刃锋芒刺破，刚硬反易折。
三传皆水，称“润下”。如流水善下不争，融容乃消弭。

若成五行局，只须依照五行而取其对应意义、类象即可。比如，水局可取江海之象、沟壑之象；火局可取炉灶之象、冶炼之象、晴空之象。不一而足，诸君须持一化万千。`,
	},
	jiase: {
		poem: `戊己占用土，四季合斯名。
稼穑缘从土，筑室田宅墓。`,
		note: `三传皆为同一五行，即成五行局。名称随五行而各异。
三传皆火，称“炎上”。如火焰跃动闪烁，华丽却燥热。
三传皆木，称“曲直”。如林木柔韧参天，强直又密盛。
三传皆土，称“稼穑”。如沃土依规耕种，沉稳而井然。
三传皆金，称“从革”。如锐刃锋芒刺破，刚硬反易折。
三传皆水，称“润下”。如流水善下不争，融容乃消弭。

若成五行局，只须依照五行而取其对应意义、类象即可。比如，水局可取江海之象、沟壑之象；火局可取炉灶之象、冶炼之象、晴空之象。不一而足，诸君须持一化万千。`,
	},
	congge: {
		poem: `巳酉丑从革，兵革持属金。
改新多别业，病伤肺骨筋。`,
		note: `三传皆为同一五行，即成五行局。名称随五行而各异。
三传皆火，称“炎上”。如火焰跃动闪烁，华丽却燥热。
三传皆木，称“曲直”。如林木柔韧参天，强直又密盛。
三传皆土，称“稼穑”。如沃土依规耕种，沉稳而井然。
三传皆金，称“从革”。如锐刃锋芒刺破，刚硬反易折。
三传皆水，称“润下”。如流水善下不争，融容乃消弭。

若成五行局，只须依照五行而取其对应意义、类象即可。比如，水局可取江海之象、沟壑之象；火局可取炉灶之象、冶炼之象、晴空之象。不一而足，诸君须持一化万千。`,
	},
	runxia: {
		poem: `用传申子辰，润下水之因。
占者因沟涧，舟楫网鱼鳞。`,
		note: `三传皆为同一五行，即成五行局。名称随五行而各异。
三传皆火，称“炎上”。如火焰跃动闪烁，华丽却燥热。
三传皆木，称“曲直”。如林木柔韧参天，强直又密盛。
三传皆土，称“稼穑”。如沃土依规耕种，沉稳而井然。
三传皆金，称“从革”。如锐刃锋芒刺破，刚硬反易折。
三传皆水，称“润下”。如流水善下不争，融容乃消弭。

若成五行局，只须依照五行而取其对应意义、类象即可。比如，水局可取江海之象、沟壑之象；火局可取炉灶之象、冶炼之象、晴空之象。不一而足，诸君须持一化万千。`,
	},
	wangyun: {
		poem: `行年旺相神，夫妇三合群。
春妻午夫寅，秋妻子夫申。`,
		note: `旺孕，夫妇的行年皆旺相，甚至二人的行年地支三合，则胎儿强旺。例如，丈夫行年地支为申，妻子行年地支为子，申子三合，又恰逢秋季金旺水相，导致二人行年地支皆旺相。`,
	},
	deyun: {
		poem: `行年课十干，甲己例同攒。
夫甲妻居己，孕安贵灵胎。`,
		note: `德孕，夫妇二人的行年天干相合。如丈夫行年天干为甲，妻子行年天干是己，甲己相合。`,
	},
	erfan: {
		poem: `日月临四仲，各为天地烦。
斗罡加丑未，兼称名杜传。
男年日女月，灾殃为汝言。
祸散欢复怒，仇解又成冤。
朔望天烦合，男犯刑伤官。
四仲地烦会，女主血光邅。`,
		jushi: '太阳临四仲；月亮临四仲；辰临丑未。',
		juyi: '坎坷、磨难、烦恼、无路。',
		juzhu: `此局需天文测算。古人算法粗略不精。诸君使用星阙即可测得。
太阳所在星宿，若临四仲，则称“天烦”；月亮所在星宿，若临四仲，则称“地烦”。天烦且地烦，并称“二烦”。此局是六壬的天文实践，需要实测日月的黄道位置、星宿位置。可于星阙“宿占盘”测得——我们数月前已复原中国古代的星宿占卜法。

增注： 原文提及一法，源于月相——朔（初一）、弦（初八）、望（十五）、晦（廿三），此四日尤为敏感。在此四日占，若男子行年临太阳所在（神），则男子定遭大灾；若女子行年临月亮所在（神），则女子必有血光。日主男、月主女之故。

子中星宿。女、虚、危。
午中星宿。柳、星、张。
卯中星宿。氐、房、心。
酉中星宿。胃、昴、毕。`,
	},
	tianhuo: {
		poem: `四立占百事，切忌遇绝神。
此名为天祸，灾咎四五旬。
立春当乙酉，冬穷是甲申。
乙酉戌时课，干临申害人。
祸患缘何起？以将决事因：
虎死元武盗，官追雀斗勾。
天空多欺诈，依天将邅迍。`,
		jushi: '四立日；今天与昨天的日干日支有临。',
		juyi: '敏感、尖锐、两难。',
		juzhu: `立春、立夏、立秋、立冬，即四立日，为五行交变之要节。比如立春时，水已至极、已然衰落，木渐得气、迅速崛起，因此立春之实质是水趋于绝而木趋于旺，暗含质变。因此立春日的昨日，称为“绝神”，意寓老旧之气将绝，趋势不可扭转。若立春的日辰，与其昨日的日辰纠缠不清，则必进退维谷，前后两难。其他立日相似，举一反三即可。当然，四立日各有其五行绝旺，因此有所差异。

增注： 具体事端，依将而定。应期在四十五天内。`,
	},
	tiankou: {
		poem: `生杀言分至，昨日是离神。
月宿居离上，多少悉殃人。
月积阴杀气，离逢天寇迍。
行人去遭劫，经营害及身。`,
		jushi: '分至日；月亮临昨天的日支。',
		juyi: '变动、旅祸、阴杀。',
		juzhu: `春分、夏至、秋分、冬至，即分至日。前文天祸局是四立日，五行嬗变之节，敏而易感；此处天寇局为分至日，出入交战之所，动即惊雷。另，天祸局注重日干日支的纠缠，天寇局则看太阴月亮之旅途。月亮纠缠昨日，更增阴杀怨战，尤防旅路凶险、途遇劫持。易有杀身之祸。`,
	},
	tianyu: {
		poem: `用神当死囚，仰丘俯见仇。
斗罡加日本，四凶天狱由。
塞生父母忧，火木忌逢秋。
临仲身兄患，加季妻儿愁。
行人不可出，能知则免忧。`,
		jushi: '辰临日干之长生；初传或休囚，或被墓覆，或被下神所克。',
		juyi: '牢狱、虚弱、萎靡、根断源消。',
		juzhu: `辰，天罡之名源于北斗七星之柄。斗柄所指，执衡监律，既是公义、亦无人情。因此，辰可用于定盘，或“塞位”。如“罡塞鬼户”之说，即辰临寅，天罡堵塞鬼户，便无妖异，又损魂胎。须知天罡双刃，镇邪压人，皆系于辰。天狱局“罡加日本”，即辰临日干长生，塞其长生，镇压日干命源。若日干为卜者，则其长生为父母之象，所以长生被塞则父母有忧。长生已塞，初传再弱，此人犹入囚牢，与亲人隔绝，亦无力逃脱。`,
	},
	siqi: {
		poem: `三奇日月星，日福德月刑。
星死奇为斗，加临各有灵：
加孟忧父母，临仲身及兄。
季上系妻儿，看其臧否并。
塞日旬中应，塞辰月内行。
塞年月日者，各以其期鸣。
星月临主死，日照免灾倾。`,
		note: `太阳主福德、月亮主刑伤、北斗主死丧。合称“三奇”。
此局名“死奇”，即指死丧之主——北斗七星。六壬中，北斗即天罡，亦即辰。 如前文所言，辰可定盘、亦可塞位，所以辰临何神非常重要。以孟仲季而言，孟是初生，所以取象父母；仲是成熟，所以取象平辈兄弟；季是结果，所以取象妻儿。若被辰临，则其象有忧。
北斗与月亮皆阴死之象，所以占病尤忌。但若太阳临日干、日支、年支，则可驱散阴死，不惧星月。
另有一法，用辰所临神判断应期。辰临日干，旬中（十天内）应验；辰临日支，月内应验；若临时支，即刻应验；若临年支，年内应验。举一反三。`,
	},
	pohua: {
		poem: `白虎本西金，性煞忌加临。
与死神相会，日辰年上吟。
即为魂魄化，无病也昏沉。
贼上应内事，阳男女为阴。
年遇魁罡立，害身祸相侵。`,
		jushi: '白虎携死神；白虎临日干、日支、行年。',
		juyi: '杀戮、丧命、亡魂、猛击。',
		juzhu: `白虎至凶，金气极烈，若携死神，必为杀伐之饿虎。此虎临日辰或行年，所临者必受重创。若在发用，其是势滔天，万军难阻。白虎烈且急，凶验大而速。除非所卜之事本就契合白虎之性，如战争、捕猎、竞技，白虎可助其临，否则判以大凶。

死神，月建前方第四位。正月巳，二月午，三月未，四月申，五月酉……`,
	},
	sanyin: {
		poem: `天乙方逆行，元白居日前。
用终囚死克，时贼凶行年。
三阴任尔作，精神入墓间。
事悖家业散，登科位不迁。`,
		jushi: '贵人逆治，元武、白虎皆在日干前；初传、末传皆休囚；时支克行年。',
		juyi: '阴弱、受骗、不振、颓唐、女主。',
		juzhu: '贵人逆治，失序；武虎先于日干，阴谋歹意先行而待，“一阴”；初末皆休囚，驱策无力，“二阴”；时支克行年，卜者被天时所弃，“三阴”。所以，既背天时，又难撑局面，还秩序尽失，后是泥潭、前有凶险，唯余哀叹。',
	},
	fugui: {
		poem: `天乙乘旺相，临在年日辰。
发用传有气，即是富贵人。
中遇凶神近，但看青龙珍。`,
		jushi: '贵人所乘之神旺相；贵人临日干、日支、行年；三传生旺。',
		juyi: '荣耀、富裕。',
		juzhu: '贵人旺相且临日辰行年，再遇三传生旺，全局皆贵而自由。',
	},
	jiaji: {
		poem: `戊己避木刑，己妻甲欢情。
六月妊归戊，果实熟带青。`,
		note: `课传若有互合之天干，即成天合局。名称随天干而各异。
课中神、传中神，皆会携一天干。若不携天干，则称“空亡”。此现象的实质是，每一旬皆会把十天干依次配给十二地支，所以每一神皆会携一天干（或空亡）。
两神所携天干互合，就会形成意义、显现类象。
甲与己合、乙与庚合、丙与辛合、丁与壬合、戊与癸合。

以甲己之合为例——戊己属土，惧怕木克，所以需要与木“和亲”，把女土（己）嫁给男木（甲），方可求得安宁。所以甲与己合，己为甲之妻。春天木旺，甲权势滔天，妻子己被其占有、束缚；直到六月，秋天将至，金旺木衰，并且木在未月（六月）入墓而丧权失力，此时，己妻便挣脱甲夫的管束，逃回家乡。但毕竟相处半年，己已怀孕。怕甲恨甲、却有了甲的骨肉。上述过程便凝结成意义，土中遗木，六月果实（土）成熟却仍然遗留青色（木），正是此意义的具象。第二年春，木再次得势，又会把妻子掳回，循环往复。

其余四合，逻辑一致，皆似上述——弱者惧强，奉献女性以求苟且，此女趁丈夫虚弱而逃回，却发现已怀身孕，木已成舟，第二年再次被丈夫掳回，循环不已。

这既是古代男女关系的悲哀，亦是传统婚恋观的实质。传统家庭女性，皆幻想夫君至强至性。她们的爱情，多半是对权力的臣服，是弱者对强者的依赖甚至寄生。传统女性对丈夫，既爱且恨，恨其强大难制、爱其甘心护己。这矛盾一旦难以调和，结局必是相爱相杀。求仁得仁而已。当代社会，这种例子依然屡见不鲜，如凤凰男女，乡土和亲烙印。
天合局之精髓，即弱而求合、外合实弱。一旦求合之人掌握力量，此合必破；一旦求和之人失去力量，此姻又复。
所以，此局用处有三。一者，判断强弱；二者，确定应期；三者，寻找周期。诸君只须研读原文，按图索骥，即可彻解。

增注：
依注者经验，合在三处，象最明显——一者，同课上下相合；二者，三传有合；三者，日干与日支上神有合，或日支与日干上神有合。
另，上述所说天干，皆旬中天干。至于“十干寄宫”之天干，能否形成天合局？暂时存疑。如甲寄于寅、己寄于未，寅临未，是否可成天合局？从理论来说，亦应成立。诸君可自行验证。`,
	},
	yigeng: {
		poem: `木畏庚与辛，乙妹合庚金。
春时乙归本，琼花开绿林。`,
		note: `课传若有互合之天干，即成天合局。名称随天干而各异。
课中神、传中神，皆会携一天干。若不携天干，则称“空亡”。此现象的实质是，每一旬皆会把十天干依次配给十二地支，所以每一神皆会携一天干（或空亡）。
两神所携天干互合，就会形成意义、显现类象。
甲与己合、乙与庚合、丙与辛合、丁与壬合、戊与癸合。

天合局之精髓，即弱而求合、外合实弱。一旦求合之人掌握力量，此合必破；一旦求和之人失去力量，此姻又复。
所以，此局用处有三。一者，判断强弱；二者，确定应期；三者，寻找周期。诸君只须研读原文，按图索骥，即可彻解。

增注：
依注者经验，合在三处，象最明显——一者，同课上下相合；二者，三传有合；三者，日干与日支上神有合，或日支与日干上神有合。
另，上述所说天干，皆旬中天干。至于“十干寄宫”之天干，能否形成天合局？暂时存疑。如甲寄于寅、己寄于未，寅临未，是否可成天合局？从理论来说，亦应成立。诸君可自行验证。`,
	},
	bingxin: {
		poem: `庚辛怯南火，辛便合丙同。
秋冷金归去，霜凝叶落红。`,
		note: `课传若有互合之天干，即成天合局。名称随天干而各异。
课中神、传中神，皆会携一天干。若不携天干，则称“空亡”。此现象的实质是，每一旬皆会把十天干依次配给十二地支，所以每一神皆会携一天干（或空亡）。
两神所携天干互合，就会形成意义、显现类象。
甲与己合、乙与庚合、丙与辛合、丁与壬合、戊与癸合。

天合局之精髓，即弱而求合、外合实弱。一旦求合之人掌握力量，此合必破；一旦求和之人失去力量，此姻又复。
所以，此局用处有三。一者，判断强弱；二者，确定应期；三者，寻找周期。诸君只须研读原文，按图索骥，即可彻解。

增注：
依注者经验，合在三处，象最明显——一者，同课上下相合；二者，三传有合；三者，日干与日支上神有合，或日支与日干上神有合。
另，上述所说天干，皆旬中天干。至于“十干寄宫”之天干，能否形成天合局？暂时存疑。如甲寄于寅、己寄于未，寅临未，是否可成天合局？从理论来说，亦应成立。诸君可自行验证。`,
	},
	dingren: {
		poem: `火畏北方水，丁妹配于壬。
夏旺丁归丙，桑椹熟紫青。`,
		note: `课传若有互合之天干，即成天合局。名称随天干而各异。
课中神、传中神，皆会携一天干。若不携天干，则称“空亡”。此现象的实质是，每一旬皆会把十天干依次配给十二地支，所以每一神皆会携一天干（或空亡）。
两神所携天干互合，就会形成意义、显现类象。
甲与己合、乙与庚合、丙与辛合、丁与壬合、戊与癸合。

天合局之精髓，即弱而求合、外合实弱。一旦求合之人掌握力量，此合必破；一旦求和之人失去力量，此姻又复。
所以，此局用处有三。一者，判断强弱；二者，确定应期；三者，寻找周期。诸君只须研读原文，按图索骥，即可彻解。

增注：
依注者经验，合在三处，象最明显——一者，同课上下相合；二者，三传有合；三者，日干与日支上神有合，或日支与日干上神有合。
另，上述所说天干，皆旬中天干。至于“十干寄宫”之天干，能否形成天合局？暂时存疑。如甲寄于寅、己寄于未，寅临未，是否可成天合局？从理论来说，亦应成立。诸君可自行验证。`,
	},
	wugui: {
		poem: `水怯中央土，癸戊偶室房。
立冬还盛癸，和凝杀草黄。`,
		note: `课传若有互合之天干，即成天合局。名称随天干而各异。
课中神、传中神，皆会携一天干。若不携天干，则称“空亡”。此现象的实质是，每一旬皆会把十天干依次配给十二地支，所以每一神皆会携一天干（或空亡）。
两神所携天干互合，就会形成意义、显现类象。
甲与己合、乙与庚合、丙与辛合、丁与壬合、戊与癸合。

天合局之精髓，即弱而求合、外合实弱。一旦求合之人掌握力量，此合必破；一旦求和之人失去力量，此姻又复。
所以，此局用处有三。一者，判断强弱；二者，确定应期；三者，寻找周期。诸君只须研读原文，按图索骥，即可彻解。

增注：
依注者经验，合在三处，象最明显——一者，同课上下相合；二者，三传有合；三者，日干与日支上神有合，或日支与日干上神有合。
另，上述所说天干，皆旬中天干。至于“十干寄宫”之天干，能否形成天合局？暂时存疑。如甲寄于寅、己寄于未，寅临未，是否可成天合局？从理论来说，亦应成立。诸君可自行验证。`,
	},
	jianggongshi: {
		poem: `三神临仲是三宫，此法元微捷径踪。
绛宫时值登明入，六神相扶有顺从。
天魁是德未生气，辰午酉申宜见逢。
功曹正合为华盖，犹恐须居不避凶。
魁罡加孟女为杀，行人不至过江风。
占贼不来亡叛获，囚病人加罪皆轻。
人情不实行宜止，睡若逢歧左道通。
见怪身当殃不出，孕生男子卜财丰。`,
		note: `所谓宫时，即以天地两盘中孟仲季的叠合来定局。
若把十二神皆划归为四孟、四仲、四季这三大类，则天地两盘叠合后，孟仲季必有一定之规。
比如，亥为四孟，若（天盘）亥临（地盘）仲，则（天盘）四孟皆临（地盘）四仲、（天盘）四仲皆临（地盘）四季、（天盘）四季皆临（地盘）四孟。
由于孟仲季各有其意义与类象，研究孟仲季叠合的规律就势在必行。`,
		jushi: '登明加四仲，名绛宫时。',
		juyi: '天乙藏深宫之中，入游系宫，行于私宴。当此之时，不可出行，避罪逃亡者得。',
		juzhu: '四孟临四仲。即四仲临四季、四季临四孟。',
	},
	mingtangshi: {
		poem: `神后明堂入仲时，从魁合德未申随。
功曹别处而生气，丑居华盖避凶危。
斗罡加季登明杀，囚人将出病难医。
看人不见上书吉，占贼即来通启宜。
逃亡不获行人到，纳财权止情须追。`,
		jushi: '神后加四仲，名明堂时。',
		juyi: '天乙出游四野八极，当此之时，举动百事皆吉，逃亡者难得，在内利主，在外利客。',
		juzhu: '四仲临四仲。即四孟临四孟、四季临四季。',
	},
	yutangshi: {
		poem: `大吉居仲是玉堂，太乙生气得功曹。
申酉即为侍从者，神后合为华盖方。
天罡加仲杀居亥，贼来中咱战须伤。
上书遭执追逃获，天气无风可渡江。
谒人相见胎生女，若问人归中路傍。`,
		jushi: '大吉加四仲，名玉堂时。',
		juyi: '天乙加门之中，天神在门方欲出行。当此之时，百事小不利，逃亡者可得也。',
		juzhu: '四季临四仲。即四孟临四季，四仲临四孟。',
	},
	doumeng: {
		poem: `孟则占行人未发，若觅家中因病人。
官事罪重奴婢吉，忧不忧兮凶讼论。
商贾所求还自得，讨猎求鱼怪临身。
书为不通因待慢，胜于捕贼不行军。
逆战可经军不罢，天罡三首后来分。`,
		note: `北斗为纲纪，六壬中以天盘的天罡（辰）代表北斗所指。所以辰临何处，可用于定盘与定局。
唐代古法，先看北斗，其次三传。与宋后之法有所差异。以注者之见，应遵唐规——重北斗、摄大局。
孟仲季与初中末三传实为两面一体，二者皆可象征开始、过程、终局，或源头、凝定、结果。但二者也有天壤之别，初中末三传由人为规定的“机制”建构而来，孟仲季则纯粹天然、无人为筛选。以此而言，孟仲季才是客观存在（本质），三传只是主观现象（表象）罢了。当然，二者绝无优劣之别，只应有先后之分。孟仲季优先，三传于后。

辰临孟。
寅申巳亥，四马之地，变动不拘，开端。
占星术中，此四地力量极弱，心神难安，爱多而杂，丧其专一。`,
	},
	douzhong: {
		poem: `仲因官事解留连，病不成兮忧不至。
觅人不出行人发，渔猎所求半得钱。
灾怪家中奴婢病，上书且未讼能方。
捕贼两专宽有语，半兵相虞用军员。
侵围妨害何曾罢？病人已瘥必安然。`,
		note: `辰临仲。
子午卯酉，四正之地，固执稳定，中途。
占星术中，此四地力量强且凝，如刃出窍，锋锐不散。`,
	},
	douji: {
		poem: `病人忧死行人至，官事不成忧必忧。
觅人远出言词告，奴婢逃捕贼可求。
商贾不成渔猎得，怪在比邻急速游。
书却以通军必出，勿战军围去不留。
斗人已死军须罢，不然三合报人雠。`,
		note: `辰临季。
辰戌丑未，四墓之地，蓄积郁结，结果。
占星术中，此四地力量强而隐，庞阔能容，犹如江海，亦如土墓。`,
	},
};

const XIAO_JU_REFERENCE_TAB_KEYS = new Set([
	'shizhong',
	'tunfu',
	'xingde',
	'wuqi',
	'xingu',
	'wangyun',
	'deyun',
]);

const XIAO_JU_ALWAYS_REFERENCE_KEYS = [
	'wuqi',
	'xingu',
	'tunfu',
	'shizhong',
	'xingde',
	'wangyun',
	'deyun',
];

function buildReferenceDocumentText(item, type){
	if(!item){
		return '';
	}
	const dict = type === 'dage' ? DA_GE_REFERENCE_TEXT : (type === 'xiaoju' ? XIAO_JU_REFERENCE_TEXT : null);
	const detail = dict && item.key ? dict[item.key] : null;
	const parts = [];
	if(detail && detail.poem){
		parts.push(`${detail.poem}`.trim());
	}
	const xunzhuLines = [];
	if(detail && detail.note){
		xunzhuLines.push(`${detail.note}`.trim());
	}
	if(detail && detail.jushi){
		xunzhuLines.push(`局式： ${detail.jushi}`);
	}
	if(detail && detail.juyi){
		xunzhuLines.push(`局义： ${detail.juyi}`);
	}
	if(detail && detail.juzhu){
		xunzhuLines.push(`局注： ${detail.juzhu}`);
	}
	if(xunzhuLines.length){
		parts.push(`荀注：\n${xunzhuLines.join('\n')}`.trim());
	}
	if(detail && detail.basis){
		parts.push(`依据：\n${detail.basis}`.trim());
	}
	if(parts.length){
		return parts.join('\n\n').trim();
	}
	const fallback = [];
	if(item.condition){
		fallback.push(`局式： ${item.condition}`);
	}
	if(item.summary){
		fallback.push(`局义： ${item.summary}`);
	}
	return fallback.join('\n');
}

const GU_CHEN_GUA_SU_BY_SEASON = {
	spring: { guchen: '巳', guasu: '丑' },
	summer: { guchen: '申', guasu: '辰' },
	autumn: { guchen: '亥', guasu: '未' },
	winter: { guchen: '寅', guasu: '戌' },
};

const SEASON_BRANCH_GROUP = {
	spring: ['寅', '卯', '辰'],
	summer: ['巳', '午', '未'],
	autumn: ['申', '酉', '戌'],
	winter: ['亥', '子', '丑'],
};

const TIANJIANG_JI = ['贵人', '六合', '青龙', '太常', '太阴', '天后'];
const TIANJIANG_XIONG = ['螣蛇', '朱雀', '勾陈', '天空', '白虎', '玄武'];
const FOUR_SEASON_BRANCHES = ['辰', '戌', '丑', '未'];
const ZHUQUE_KAIKOU_MONTH_BRANCH = ['巳', '辰', '午', '未', '卯', '寅', '申', '酉', '丑', '子', '戌', '亥'];
const ZHUQUE_XIANWU_MONTH_BRANCH = ['酉', '巳', '丑', '子', '申', '辰', '卯', '亥', '未', '午', '寅', '戌'];
const GOUCHEN_BAJIAN_MONTH_BRANCH = ['巳', '辰', '卯', '寅', '丑', '子', '亥', '戌', '酉', '申', '未', '午'];

function normalizeOverviewGodName(name){
	const raw = `${name || ''}`.trim();
	if(!raw){
		return '';
	}
	return normalizeLiuRengJiangName(raw);
}

function getMonthIndexByBranch(branch){
	const idx = MONTH_BRANCH_SEQUENCE.indexOf(branch);
	return idx >= 0 ? idx + 1 : -1;
}

function isBranchSetIncludes(target, arr){
	if(!target || !arr || !arr.length){
		return false;
	}
	return arr.indexOf(target) >= 0;
}

function buildOverviewReferenceText(item){
	if(!item){
		return '';
	}
	const parts = [];
	if(item.verse){
		parts.push(`${item.verse}`.trim());
	}
	if(item.note){
		parts.push(`荀注：${item.note}`.trim());
	}
	return parts.join('\n\n').trim();
}

function mergeOverviewRefsByName(items){
	if(!Array.isArray(items) || items.length === 0){
		return [];
	}
	const merged = [];
	const mergeMap = {};
	const mergeText = (a, b, sep = '\n')=>{
		const parts = uniqueStrings([a, b].filter(Boolean).map((item)=>`${item}`.trim())).filter(Boolean);
		return parts.join(sep);
	};
	items.forEach((item)=>{
		if(!item){
			return;
		}
		const mergeKey = `${item.group || ''}_${item.name || ''}`;
		if(!mergeKey.trim()){
			merged.push(item);
			return;
		}
		const existed = mergeMap[mergeKey];
		if(!existed){
			const one = {
				...item,
				evidence: uniqueStrings(item.evidence || []),
			};
			mergeMap[mergeKey] = one;
			merged.push(one);
			return;
		}
		existed.evidence = uniqueStrings([...(existed.evidence || []), ...((item && item.evidence) || [])]);
		existed.verse = mergeText(existed.verse, item.verse, '\n');
		existed.note = mergeText(existed.note, item.note, '；');
		existed.summary = mergeText(existed.summary, item.summary, '；');
		existed.key = mergeText(existed.key, item.key, '__');
	});
	return merged;
}

function matchLiuRengOverviewReferences(context){
	if(!context){
		return [];
	}
	const refs = [];
	const refMap = {};
	const push = (group, key, title, verse, summary, evidence, note = '')=>{
		const uniqEvidence = uniqueStrings(evidence || []);
		if(uniqEvidence.length === 0){
			return;
		}
		const uniqKey = `${group}_${key}`;
		const existed = refMap[uniqKey];
		if(existed){
			existed.evidence = uniqueStrings([...(existed.evidence || []), ...uniqEvidence]);
			if(!existed.note && note){
				existed.note = note;
			}
			if(!existed.summary && summary){
				existed.summary = summary;
			}
			if(!existed.verse && verse){
				existed.verse = verse;
			}
			return;
		}
		const one = {
			group,
			key: `${group}_${key}`,
			name: title,
			verse,
			note,
			summary,
			evidence: uniqEvidence,
		};
		refMap[uniqKey] = one;
		refs.push(one);
	};
	const firstRole = {
		role: '发用',
		god: normalizeOverviewGodName(context.firstGod),
		branch: context.firstBranch,
		gan: context.firstGan,
	};
	const dayRole = {
		role: '日干上神',
		god: normalizeOverviewGodName(context.branchGodMap ? context.branchGodMap[context.ke1Up] : ''),
		branch: context.ke1Up,
		gan: context.ke1UpGan,
	};
	const roles = [firstRole, dayRole];
	const monthBranch = context.monthBranch;
	const monthIndex = getMonthIndexByBranch(monthBranch);
	const dayHeGan = context.dayGan ? LRConst.GanHe[context.dayGan] : '';
	const hasMonthTianDe = !!(
		context.dayGodMap
		&& context.dayGodMap.base
		&& (context.dayGodMap.base['月德'] || context.dayGodMap.base['天德'])
	);
	roles.forEach((roleObj)=>{
		const roleName = roleObj.role;
		const god = roleObj.god;
		const branch = roleObj.branch;
		const gan = roleObj.gan;
		if(!god || !branch){
			return;
		}
		if(god === '天乙' && isBranchSetIncludes(branch, ['丑', '未'])){
			push(
				'laiyi',
				'tianyi',
				'天乙决',
				'贵人丑未下，定危问小儿。',
				'贵人加丑未，多主择日、急务或小儿相关之问。',
				[`${roleName}见天乙临${branch}`],
			);
		}
		if(god === '六合' && (branch === context.dayGanBranch || (context.horseBranches || []).indexOf(branch) >= 0)){
			push(
				'laiyi',
				'liuhe_luma',
				'六合决',
				'六合加禄马，行职最宜鞍。',
				'六合临禄马，多主行职、差遣、出行、赴任之问。',
				[
					`${roleName}见六合临${branch}`,
					branch === context.dayGanBranch ? `临禄位（${context.dayGanBranch}）` : '',
					(context.horseBranches || []).indexOf(branch) >= 0 ? `临驿马（${branch}）` : '',
				],
			);
		}
		if(god === '螣蛇' && isBranchSetIncludes(branch, ['巳', '午', '卯'])){
			push(
				'laiyi',
				'tengshe',
				'螣蛇决',
				'螣蛇巳午卯，梦寝虚惊怪。若非戾财失，即是众悖乖。',
				'螣蛇临巳午卯，多见虚惊怪梦、财失或人事乖悖。',
				[`${roleName}见螣蛇临${branch}`],
			);
		}
		if(god === '朱雀'){
			push(
				'laiyi',
				'zhuque',
				'朱雀决',
				'朱雀信息来，杀神应官灾。遇月天两德，呼为炉冶财。',
				'朱雀主信息文书；并杀气则偏官灾，得月德天德可转炉冶财利。',
				[
					`${roleName}见朱雀临${branch}`,
					hasMonthTianDe ? '盘中见月德/天德' : '',
				],
			);
		}
		if(god === '六合' && isBranchSetIncludes(branch, ['卯', '酉'])){
			push(
				'laiyi',
				'liuhe_maoyou',
				'六合决',
				'六合乘卯酉，婚孕事分明。若临日辰上，唇舌钱立生。',
				'六合临卯酉偏婚孕与合议；并临日辰，口舌财事并发。',
				[
					`${roleName}见六合临${branch}`,
					(branch === context.dayGanBranch || branch === context.dayZhi) ? '并临日辰位' : '',
				],
			);
		}
		if(god === '勾陈' && (context.season === 'spring' || isBranchSetIncludes(branch, ['卯', '酉']))){
			push(
				'laiyi',
				'gouchen',
				'勾陈决',
				'勾陈春二八，官讼要争论。阳绝并阴绝，病者连绵昏。',
				'勾陈见春或卯酉，多主官讼争执，病事则绵延不解。',
				[
					`${roleName}见勾陈临${branch}`,
					context.season === 'spring' ? '时在春令' : '',
				],
				'春为寅卯，二八为卯酉。',
			);
		}
		if(god === '青龙' && (gan === dayHeGan || branch === context.dayGanBranch)){
			push(
				'laiyi',
				'qinglong',
				'青龙诀',
				'青龙当干合，财隆百事安。求官并借职，书信往来传。',
				'青龙得干合/禄位，多主财禄与求官、往来文书之利。',
				[
					`${roleName}见青龙临${branch}`,
					gan && dayHeGan && gan === dayHeGan ? `与日干成合（${context.dayGan}↔${gan}）` : '',
					branch === context.dayGanBranch ? `临日干禄位（${context.dayGanBranch}）` : '',
				],
			);
		}
		if(god === '天空'){
			push(
				'laiyi',
				'tiankong',
				'天空决',
				'天空有失亡，魁罡仆不良。若临干旺相，营作运行商。',
				'天空主失亡虚耗；逢魁罡偏仆役不良，旺相可转营作与行商。',
				[
					`${roleName}见天空临${branch}`,
					isBranchSetIncludes(branch, ['辰', '戌']) ? '临魁罡位' : '',
					isWangXiangState(getSeasonStateForBranch(context.seasonMap, branch)) ? '临旺相地' : '',
				],
			);
		}
		if(god === '白虎'){
			push(
				'laiyi',
				'baihu',
				'白虎决',
				'白虎临门叹，病侵老幼俩。午未兼申酉，殴斗事起他。',
				'白虎多主病灾惊惧；临午未申酉，斗殴冲突之象更显。',
				[
					`${roleName}见白虎临${branch}`,
					isBranchSetIncludes(branch, ['午', '未', '申', '酉']) ? '临午未申酉位' : '',
				],
			);
		}
		if(god === '太常'){
			push(
				'laiyi',
				'taichang',
				'太常决',
				'太常旺今朝，衣裳财文章。禄上加合上，筵开亲戚招。',
				'太常偏衣食筵会与财文；得旺、禄、合时更主亲友宴集。',
				[
					`${roleName}见太常临${branch}`,
					isWangXiangState(getSeasonStateForBranch(context.seasonMap, branch)) ? '太常临旺相' : '',
				],
			);
		}
		if(god === '元武' && isBranchSetIncludes(branch, ['亥', '子', '辰'])){
			push(
				'laiyi',
				'yuanwu',
				'元武决',
				'元武亥子辰，临卯酉盗伤。加午未迁官，推详莫妄陈。',
				'元武临亥子辰偏盗失暗伤；兼卯酉午未时需细辨迁官与是非。',
				[`${roleName}见元武临${branch}`],
			);
		}
		if(god === '太阴' && isBranchSetIncludes(branch, ['巳', '午'])){
			push(
				'laiyi',
				'taiyin',
				'太阴决',
				'太阴巳午焚，结聚起异心。欺瞒官长上，口舌到知音。',
				'太阴临巳午，主隐私聚结、异心欺瞒与口舌暗耗。',
				[`${roleName}见太阴临${branch}`],
			);
		}
		if(god === '天后'){
			push(
				'laiyi',
				'tianhou',
				'天后决',
				'天后因女子，土旺彩衣嫔。午未兼壬癸，万事无一真。',
				'天后主女子私情；若并午未壬癸，虚饰失真之象更显。',
				[
					`${roleName}见天后临${branch}`,
					isBranchSetIncludes(branch, ['午', '未']) ? '并午未位' : '',
					isBranchSetIncludes(context.dayGan, ['壬', '癸']) ? `日干为${context.dayGan}` : '',
				],
			);
		}
		if(god === '螣蛇' && (safeRestrain(branch, context.midBranch) || safeRestrain(context.midBranch, branch))){
			push(
				'zazhu',
				'tengshe_dazhan',
				'螣蛇大战',
				'螣蛇大战，毒气相凌。',
				'往来上下相克，惊疑与冲突烈度上升。',
				[
					`${roleName}见螣蛇临${branch}`,
					`与中传${context.midBranch || '—'}互克`,
				],
				'大战，往来上下相克也。',
			);
		}
		if(god === '螣蛇' && isBranchSetIncludes(branch, ['子', '午', '卯', '酉'])){
			push(
				'zazhu',
				'tengshe_danglu',
				'螣蛇当路',
				'螣蛇当路，鬼怪殃藏。',
				'螣蛇居四仲，怪异与暗殃信息上浮。',
				[`${roleName}见螣蛇临${branch}`],
				'当路，子午卯酉也。',
			);
		}
		if(god === '六合' && isBranchSetIncludes(branch, ['酉', '卯', '午'])){
			push(
				'zazhu',
				'liuhe_buhe',
				'六合不合',
				'六合不合，阴私相坏。',
				'六合落酉卯午，和合反折，私线易坏。',
				[`${roleName}见六合临${branch}`],
			);
		}
		if(god === '太常'){
			const taichangCond = (context.season === 'spring' && branch === '辰')
				|| (context.season === 'autumn' && branch === '卯')
				|| (context.season === 'summer' && branch === '酉')
				|| (context.season === 'winter' && branch === '巳');
			if(taichangCond){
				push(
					'zazhu',
					'taichang_bobo',
					'太常被剥',
					'太常被剥，官事消铄。',
					'太常遇季节剥位，官事华饰与体面受损。',
					[`${roleName}见太常临${branch}`],
					'春辰、秋卯、夏酉、冬巳。',
				);
			}
		}
		if(god === '朱雀' && monthIndex > 0 && ZHUQUE_KAIKOU_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'zhuque_kaikou',
				'朱雀开口',
				'朱雀开口，发主喧斗。',
				'朱雀值月开口位，喧争口舌与争辩信息增强。',
				[`${roleName}见朱雀临${branch}；月建序=${monthIndex}`],
			);
		}
		if(god === '青龙' && isBranchSetIncludes(branch, ['寅', '酉', '戌'])){
			push(
				'zazhu',
				'qinglong_kaiyan',
				'青龙开眼',
				'青龙开眼，万事无灾。',
				'青龙得开眼位，行事顺畅度提升。',
				[`${roleName}见青龙临${branch}`],
				'孟寅，仲酉，季戌。',
			);
		}
		if(god === '青龙' && branch === '巳'){
			push(
				'zazhu',
				'qinglong_wobing',
				'青龙卧病',
				'青龙卧病，财散人灾。',
				'青龙陷巳，财气易散且伴人事耗损。',
				[`${roleName}见青龙临巳`],
			);
		}
		if(god === '天空' && isBranchSetIncludes(gan, ['壬', '癸']) && isBranchSetIncludes(context.dayGan, ['壬', '癸'])){
			push(
				'zazhu',
				'tiankong_luolei',
				'天空落泪',
				'天空落泪，哀声聒耳。',
				'天空与壬癸同会，哀戚与失落情绪放大。',
				[`${roleName}见天空临${branch}；所携天干=${gan}`],
				'六甲旬中居壬癸地，见壬癸。',
			);
		}
		if(god === '天乙' && isBranchSetIncludes(branch, ['辰', '戌'])){
			push(
				'zazhu',
				'tianyi_yugyu',
				'天乙归狱',
				'天乙归狱，诸事不治。',
				'贵人陷辰戌狱地，主事阻滞。',
				[`${roleName}见天乙临${branch}`],
			);
		}
		if(god === '勾陈' && monthIndex > 0 && GOUCHEN_BAJIAN_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'gouchen_bajian',
				'勾陈拔剑',
				'勾陈拔剑，病患相伤。',
				'勾陈值月拔剑位，病患与冲突风险上扬。',
				[`${roleName}见勾陈临${branch}；月建序=${monthIndex}`],
				'正月起巳，逆行十二辰。',
			);
		}
		if(god === '勾陈' && isBranchSetIncludes(branch, ['辰', '戌', '丑', '未'])){
			push(
				'zazhu',
				'gouchen_xianghui',
				'勾陈相会',
				'勾陈相会，连绵祸深。',
				'勾陈临四季土，祸患拖延不散（辰戌重、丑未轻）。',
				[`${roleName}见勾陈临${branch}`],
				'辰戌大凶，丑未小凶。',
			);
		}
		if(god === '天后' && isBranchSetIncludes(branch, ['申', '酉'])){
			push(
				'zazhu',
				'tianhou_yinsi',
				'天后阴私',
				'天后阴私，申阳酉阴。',
				'天后居申酉，私隐议题更重。',
				[`${roleName}见天后临${branch}`],
			);
		}
		if(god === '朱雀' && monthIndex > 0 && ZHUQUE_XIANWU_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'zhuque_xianwu',
				'朱雀衔物',
				'朱雀衔物，婚姻和合。',
				'朱雀值月衔物位，婚姻与和合议题突出。',
				[`${roleName}见朱雀临${branch}；月建序=${monthIndex}`],
			);
		}
		if(god === '太阴' && isBranchSetIncludes(branch, ['申', '酉'])){
			push(
				'zazhu',
				'taiyin_bajian',
				'太阴拔剑',
				'太阴拔剑，阴谋相害。',
				'太阴居申酉，暗谋与相害风险偏高。',
				[`${roleName}见太阴临${branch}`],
			);
		}
		if(god === '元武' && isBranchSetIncludes(monthBranch, FOUR_SEASON_BRANCHES)){
			push(
				'zazhu',
				'yuanwu_hengjie',
				'元武横截',
				'元武横截，盗贼兵发。',
				'四季土月见元武，盗兵、截阻与暗线风险增。',
				[`${roleName}见元武临${branch}；月建=${monthBranch}`],
				'四季。',
			);
		}
		if(god === '白虎' && isBranchSetIncludes(branch, ['巳', '午'])){
			push(
				'zazhu',
				'baihu_zaoqin',
				'白虎遭擒',
				'白虎遭擒，已免灾咎。',
				'白虎落巳午，凶力受制，灾咎可缓。',
				[`${roleName}见白虎临${branch}`],
			);
		}
		if(god === '白虎' && isBranchSetIncludes(monthBranch, FOUR_SEASON_BRANCHES)){
			push(
				'zazhu',
				'baihu_yangshi',
				'白虎仰视',
				'白虎仰视，凶恶之甚。',
				'四季土月遇白虎，凶烈度显著上扬。',
				[`${roleName}见白虎临${branch}；月建=${monthBranch}`],
				'四季。',
			);
		}
	});
	const mergedRefs = mergeOverviewRefsByName(refs);
	return mergedRefs.sort((a, b)=>{
		const ga = a.group === 'laiyi' ? 0 : 1;
		const gb = b.group === 'laiyi' ? 0 : 1;
		if(ga !== gb){
			return ga - gb;
		}
		return a.name.localeCompare(b.name, 'zh-Hans-CN');
	});
}

const MONTH_BRANCH_SEQUENCE = ['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'];
const JIU_CHOU_DAYS = ['乙卯', '己卯', '辛卯', '乙酉', '己酉', '辛酉', '戊子', '壬子', '戊午', '壬午'];
const GAN_DE_GAN = {
	'甲': '甲',
	'乙': '庚',
	'丙': '丙',
	'丁': '壬',
	'戊': '戊',
	'己': '甲',
	'庚': '庚',
	'辛': '丙',
	'壬': '壬',
	'癸': '戊',
};
const GAN_QI_BRANCH = {
	'甲': '午',
	'乙': '巳',
	'丙': '辰',
	'丁': '卯',
	'戊': '寅',
	'己': '丑',
	'庚': '未',
	'辛': '申',
	'壬': '酉',
	'癸': '戌',
};
const XUN_QI_BY_XUN_HEAD = {
	'甲午': '子',
	'甲申': '子',
	'甲寅': '亥',
	'甲辰': '亥',
	'甲子': '丑',
	'甲戌': '丑',
};
const TIANHE_PAIR_RULES = [
	{ key: 'jiaji', a: '甲', b: '己', label: '甲己' },
	{ key: 'yigeng', a: '乙', b: '庚', label: '乙庚' },
	{ key: 'bingxin', a: '丙', b: '辛', label: '丙辛' },
	{ key: 'dingren', a: '丁', b: '壬', label: '丁壬' },
	{ key: 'wugui', a: '戊', b: '癸', label: '戊癸' },
];

function normalizeTianJiangName(name){
	const txt = `${name || ''}`.replace(/\s+/g, '');
	if(!txt){
		return '';
	}
	if(txt === '腾蛇'){
		return '螣蛇';
	}
	return txt;
}

function uniqueStrings(values){
	const out = [];
	const seen = {};
	(values || []).forEach((item)=>{
		const txt = `${item || ''}`.trim();
		if(!txt || seen[txt]){
			return;
		}
		seen[txt] = true;
		out.push(txt);
	});
	return out;
}

function extractSingleBranch(raw){
	const txt = `${raw || ''}`;
	for(let i=txt.length - 1; i>=0; i--){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}

function extractSingleGan(raw){
	const txt = `${raw || ''}`;
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(LRConst.GanList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}

function extractBranches(raw){
	if(raw === undefined || raw === null){
		return [];
	}
	if(raw instanceof Array){
		let arr = [];
		raw.forEach((item)=>{
			arr = arr.concat(extractBranches(item));
		});
		return uniqueStrings(arr);
	}
	const txt = `${raw}`;
	const arr = [];
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			arr.push(ch);
		}
	}
	return uniqueStrings(arr);
}

const ERFAN_SU_TO_BRANCH = {
	'女': '子',
	'虚': '子',
	'危': '子',
	'柳': '午',
	'星': '午',
	'张': '午',
	'氐': '卯',
	'房': '卯',
	'心': '卯',
	'胃': '酉',
	'昴': '酉',
	'毕': '酉',
};

function getPlanetObject(chartObj, planetId){
	if(!chartObj || !chartObj.objects || !planetId){
		return null;
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj && obj.id === planetId){
			return obj;
		}
	}
	return null;
}

function getPlanetBranch(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return LRConst.getSignZi(obj.sign) || '';
}

const QIZHENG_DEFS = [
	{ id: AstroConst.SUN, name: '日' },
	{ id: AstroConst.MOON, name: '月' },
	{ id: AstroConst.MERCURY, name: '水' },
	{ id: AstroConst.VENUS, name: '金' },
	{ id: AstroConst.MARS, name: '火' },
	{ id: AstroConst.JUPITER, name: '木' },
	{ id: AstroConst.SATURN, name: '土' },
];

// 七政星曜色（自带 fallback，不依赖外部样式表）。
const QIZHENG_PLANET_COLOR = {
	'日': '#e0a93b',
	'月': '#cfd2d6',
	'水': '#5fb3c9',
	'金': '#d98fb0',
	'火': '#c9483e',
	'木': '#73b36b',
	'土': '#c19a57',
};

// 五行语义色：与六壬盘面 RengChart.getBranchColor 同口径（CSS 变量 + hex fallback）。
const QIZHENG_WUXING_COLOR = {
	'木': 'var(--horosa-liureng-stem-wood, #73b36b)',
	'火': 'var(--horosa-liureng-stem-fire, #c9483e)',
	'土': 'var(--horosa-liureng-stem-earth, #c19a57)',
	'金': 'var(--horosa-liureng-stem-metal, #d8d2c7)',
	'水': 'var(--horosa-liureng-stem-water, #8f9694)',
};

// 七政：复用现成 getPlanetObject + getSignZi；顺逆按 lonspeed<0（与主星盘一致，见 AstroHelper）。
function buildQiZhengItems(chartObj){
	if(!chartObj || !chartObj.objects){
		return [];
	}
	const sunBranch = getPlanetBranch(chartObj, AstroConst.SUN);
	const items = [];
	for(let i=0; i<QIZHENG_DEFS.length; i++){
		const def = QIZHENG_DEFS[i];
		const obj = getPlanetObject(chartObj, def.id);
		if(!obj){
			continue;
		}
		const branch = LRConst.getSignZi(obj.sign) || '';
		let deg = null;
		if(typeof obj.lon === 'number' && isFinite(obj.lon)){
			deg = ((obj.lon % 30) + 30) % 30;
		}
		items.push({
			key: def.id,
			name: def.name,
			branch,
			wx: branch ? (LRConst.GanZiWuXing[branch] || '') : '',
			deg,
			retro: typeof obj.lonspeed === 'number' && obj.lonspeed < 0,
			isYue: !!branch && branch === sunBranch,
		});
	}
	return items;
}

function extractSuName(raw){
	const txt = `${raw || ''}`;
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(ERFAN_SU_TO_BRANCH[ch]){
			return ch;
		}
	}
	return '';
}

function getPlanetSuName(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return extractSuName(obj.su28 || '');
}

function getPlanetErfanBranch(chartObj, planetId){
	const suName = getPlanetSuName(chartObj, planetId);
	if(suName && ERFAN_SU_TO_BRANCH[suName]){
		return ERFAN_SU_TO_BRANCH[suName];
	}
	return '';
}

function safeRestrain(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiRestrain[a];
	return !!(list && list.indexOf(b) >= 0);
}

function safeOppose(a, b){
	if(!a || !b){
		return false;
	}
	return LRConst.ZiCong[a] === b || LRConst.ZiCong[b] === a;
}

function safeBrother(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiBrother[a];
	return !!(list && list.indexOf(b) >= 0);
}

function safeAccrue(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiAccrue[a];
	return !!(list && list.indexOf(b) >= 0);
}

function getBranchIndex(branch){
	return branch ? LRConst.ZiList.indexOf(branch) : -1;
}

function shiftBranch(branch, delta){
	const idx = getBranchIndex(branch);
	if(idx < 0){
		return '';
	}
	return LRConst.ZiList[(idx + delta + 1200) % 12];
}

function getPrevJiaZi(ganzi){
	const idx = JiaZiList.indexOf(extractGanZi(ganzi));
	if(idx < 0){
		return '';
	}
	return JiaZiList[(idx + 59) % 60];
}

function matchMapValueByKey(obj, key){
	if(!obj || !key){
		return null;
	}
	if(obj[key] !== undefined){
		return obj[key];
	}
	const target = cleanKey(key);
	const keys = Object.keys(obj);
	for(let i=0; i<keys.length; i++){
		const k = keys[i];
		if(cleanKey(k) === target){
			return obj[k];
		}
	}
	return null;
}

function hasAny(values, targets){
	if(!values || !targets || !values.length || !targets.length){
		return false;
	}
	return values.some((item)=>targets.indexOf(item) >= 0);
}

function resolveSeasonByMonthBranch(branch){
	if(SEASON_BRANCH_GROUP.spring.indexOf(branch) >= 0){
		return 'spring';
	}
	if(SEASON_BRANCH_GROUP.summer.indexOf(branch) >= 0){
		return 'summer';
	}
	if(SEASON_BRANCH_GROUP.autumn.indexOf(branch) >= 0){
		return 'autumn';
	}
	if(SEASON_BRANCH_GROUP.winter.indexOf(branch) >= 0){
		return 'winter';
	}
	return '';
}

function getSeasonStateForBranch(seasonMap, branch){
	if(!seasonMap || !branch){
		return '';
	}
	const elem = LRConst.GanZiWuXing[branch];
	if(!elem){
		return '';
	}
	const state = matchMapValueByKey(seasonMap, elem);
	return `${state || ''}`;
}

function isWangXiangState(state){
	const txt = `${state || ''}`;
	if(!txt){
		return false;
	}
	return txt.indexOf('王') >= 0 || txt.indexOf('旺') >= 0 || txt.indexOf('相') >= 0;
}

function isXiuQiuState(state){
	const txt = `${state || ''}`;
	if(!txt){
		return false;
	}
	return txt.indexOf('休') >= 0 || txt.indexOf('囚') >= 0 || txt.indexOf('死') >= 0;
}

function getMengZhongJiType(branch){
	if(LRConst.ZiMeng.indexOf(branch) >= 0){
		return 'meng';
	}
	if(LRConst.ZiZong.indexOf(branch) >= 0){
		return 'zhong';
	}
	if(LRConst.ZiJi.indexOf(branch) >= 0){
		return 'ji';
	}
	return '';
}

function buildXunGanMap(dayGan, dayZhi){
	const map = {};
	if(!dayGan || !dayZhi){
		return map;
	}
	const xun = LRConst.getXun(dayGan, dayZhi);
	for(let i=0; i<xun.length && i<LRConst.GanList.length; i++){
		map[xun[i]] = LRConst.GanList[i];
	}
	return map;
}

function containsJieQi(jieqi, names){
	const txt = `${jieqi || ''}`.trim();
	if(!txt || !names || !names.length){
		return false;
	}
	return names.some((name)=>txt.indexOf(name) >= 0);
}

function createReferenceItem(meta, evidence, extra){
	return {
		...(meta || {}),
		evidence: uniqueStrings(evidence || []),
		...(extra || {}),
	};
}

function isMatchedTianHePair(g1, g2, a, b){
	if(!g1 || !g2 || !a || !b){
		return false;
	}
	return (g1 === a && g2 === b) || (g1 === b && g2 === a);
}

function collectTianHeEvidence(context, a, b){
	const evidence = [];
	const kePairs = context && context.kePairGanTuples ? context.kePairGanTuples : [];
	kePairs.forEach((item)=>{
		if(isMatchedTianHePair(item.upGan, item.downGan, a, b)){
			evidence.push(`同课上下相合：第${item.index}课 ${item.upBranch || '—'}(${item.upGan || '空'}) ↔ ${item.downBranch || '—'}(${item.downGan || '空'})`);
		}
	});
	const sanChuanItems = [
		{ name: '初传', branch: context ? context.firstBranch : '', gan: context ? context.firstGan : '' },
		{ name: '中传', branch: context ? context.midBranch : '', gan: context ? context.midGan : '' },
		{ name: '末传', branch: context ? context.lastBranch : '', gan: context ? context.lastGan : '' },
	];
	for(let i=0; i<sanChuanItems.length; i++){
		for(let j=i + 1; j<sanChuanItems.length; j++){
			const left = sanChuanItems[i];
			const right = sanChuanItems[j];
			if(isMatchedTianHePair(left.gan, right.gan, a, b)){
				evidence.push(`三传有合：${left.name}${left.branch || '—'}(${left.gan || '空'}) ↔ ${right.name}${right.branch || '—'}(${right.gan || '空'})`);
			}
		}
	}
	if(isMatchedTianHePair(context ? context.dayGan : '', context ? context.ke3UpGan : '', a, b)){
		evidence.push(`日干与日支上神有合：日干${context ? context.dayGan || '—' : '—'} ↔ 日支上神天干${context ? context.ke3UpGan || '—' : '—'}（${context ? context.ke3Up || '—' : '—'}）`);
	}
	if(isMatchedTianHePair(context ? context.dayZhiGan : '', context ? context.ke1UpGan : '', a, b)){
		evidence.push(`日支与日干上神有合：日支天干${context ? context.dayZhiGan || '—' : '—'}（${context ? context.dayZhi || '—' : '—'}） ↔ 日干上神天干${context ? context.ke1UpGan || '—' : '—'}（${context ? context.ke1Up || '—' : '—'}）`);
	}
	return uniqueStrings(evidence);
}

export function buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride, extraOpts){
	// [W2 择日全谱轮] extraOpts.prebuilt={layout,keData,sanChuan}:扫描侧已用同函数起过课,
	// 直供跳过重算(不传=原路径,主页零波及)。
	const pb = extraOpts && extraOpts.prebuilt ? extraOpts.prebuilt : null;
	const layout = pb && pb.layout ? pb.layout : buildLiuRengLayout(chartObj, guirengType, castOverride);
	const keData = pb && pb.keData ? pb.keData : buildKeData(layout, chartObj);
	const sanChuan = pb && pb.sanChuan ? pb.sanChuan : buildSanChuanData(layout, keData.raw, chartObj, castOverride);
	const nongli = chartObj && chartObj.nongli ? chartObj.nongli : {};
	const dayGanZi = nongli && nongli.dayGanZi ? nongli.dayGanZi : '';
	const dayGan = dayGanZi.substr(0, 1);
	const dayZhi = dayGanZi.substr(1, 1);
	const dayGanBranch = LRConst.GanJiZi[dayGan] ? LRConst.GanJiZi[dayGan] : '';
	const prevDayGanZi = getPrevJiaZi(dayGanZi);
	const prevDayGan = extractSingleGan(prevDayGanZi);
	const prevDayZhi = extractSingleBranch(prevDayGanZi);
	const prevDayGanBranch = prevDayGan ? (LRConst.GanJiZi[prevDayGan] || '') : '';
	const monthGanZi = nongli && nongli.monthGanZi ? nongli.monthGanZi : '';
	const monthBranch = extractSingleBranch(monthGanZi);
	const jieqi = nongli && nongli.jieqi ? `${nongli.jieqi}` : '';
	const fourColumns = liureng && liureng.fourColumns ? liureng.fourColumns : {};
	const yearBranch = extractSingleBranch(fourColumns && fourColumns.year ? (fourColumns.year.ganzi || (fourColumns.year.branch ? fourColumns.year.branch.cell : '')) : '');
	const timeBranch = extractSingleBranch(fourColumns && fourColumns.time ? (fourColumns.time.ganzi || (fourColumns.time.branch ? fourColumns.time.branch.cell : '')) : '');
	// 月将高亮/盘式以「真实月将」为准(layout.actualYue);layout.yue 是起课法的天盘起支(仅用于上下盘对齐),非起课法下二者相等。
	const yueGeneralBranch = layout ? (layout.actualYue || layout.yue) : '';
	const occupyTimeBranch = timeBranch || (layout ? layout.timezi : '');
	const panStyle = resolveLiuRengTwelvePanStyle(yueGeneralBranch, occupyTimeBranch);
	const runYearGanZi = runyear && runyear.year ? extractGanZi(runyear.year) : '';
	const runYearGan = extractSingleGan(runYearGanZi);
	const runYearBranch = extractSingleBranch(runYearGanZi || (runyear && runyear.year ? runyear.year : ''));
	const season = resolveSeasonByMonthBranch(monthBranch);
	const guChenGuaSu = season ? GU_CHEN_GUA_SU_BY_SEASON[season] : null;
	const seasonMap = liureng && liureng.season ? liureng.season : {};
	const keRaw = keData && keData.raw ? keData.raw : [];
	const sanChuanGz = sanChuan && sanChuan.cuang ? sanChuan.cuang : [];
	const sanChuanGans = sanChuanGz.map((item)=>extractSingleGan(item)).filter(Boolean);
	const sanChuanBranches = sanChuanGz.map((item)=>extractSingleBranch(item)).filter(Boolean);
		// 🔴 上面 filter(Boolean) 会在某传无遁干时删掉空位，使 gans 整体上移、与 branches 错位 —— 右栏取象 mini 与
		// 初/中/末 gan 因而把「辛」错配给戌、「癸」错配给未（与中盘真三传天干不符）。故按支位「保位重建」（不 filter）
		// 供所有「按位取用」者；上面带 filter 的版本仍留给下方神煞/格局「合干池」（那里要干清单、空位本就该剔）。
		const sanChuanGansAligned = sanChuanGz.map((item)=>extractSingleGan(item));
		const sanChuanBranchesAligned = sanChuanGz.map((item)=>extractSingleBranch(item));
	const sanChuanGods = (sanChuan && sanChuan.tianJiang ? sanChuan.tianJiang : []).map((item)=>normalizeTianJiangName(item));
	const keUp = keRaw.map((item)=>extractSingleBranch(item[1])).filter(Boolean);
	// 🔴 保位重建(勿 filter):第一课的「下」是**日干**不是地支,extractSingleBranch 判空后
	// 被 filter 剔掉 → 整条数组前移一位,取象角色标注把二课下标成「1课下」…「4课下」恒不出现
	// (与上方 sanChuanGansAligned 刚修的同型漂移,当时漏了这行)。首位取日干寄宫。
	const keDown = keRaw.map((item, i)=>(i === 0
		? (extractSingleBranch(item[2]) || dayGanBranch)
		: extractSingleBranch(item[2])));
	const branchGodMap = {};
	const branchUpMap = {};
	const upDownMap = {};
	if(layout && layout.downZi){
		layout.downZi.forEach((branch, idx)=>{
			const up = layout.upZi && layout.upZi[idx] ? layout.upZi[idx] : '';
			branchGodMap[branch] = normalizeTianJiangName(layout.houseTianJiang && layout.houseTianJiang[idx] ? layout.houseTianJiang[idx] : '');
			branchUpMap[branch] = up;
			if(up && !upDownMap[up]){
				upDownMap[up] = branch;
			}
		});
	}
	const xun = liureng && liureng.xun ? liureng.xun : {};
	const xunHeadGanZi = xun['旬首'] ? `${xun['旬首']}` : '';
	const xunHeadBranch = extractSingleBranch(xun['旬首']);
	const xunTailBranch = extractSingleBranch(xun['旬尾']);
	const xunKongBranches = extractBranches(xun['旬空']);
	const yiMaBranches = uniqueStrings(extractBranches(liureng && liureng.gods ? liureng.gods['驿马'] : null));
	const dingHorseBranches = uniqueStrings([
		...extractBranches(xun['遁丁']),
		...extractBranches(xun['旬丁']),
	]);
	const horseBranches = uniqueStrings([
		...yiMaBranches,
		...dingHorseBranches,
	]);
	const xunGanMap = buildXunGanMap(dayGan, dayZhi);
	const ke1UpGan = xunGanMap[keUp[0]] || '';
	const ke3UpGan = xunGanMap[keUp[2]] || '';
	const dayZhiGan = xunGanMap[dayZhi] || '';
	const kePairGanTuples = keRaw.map((item, idx)=>{
		const upBranch = extractSingleBranch(item[1]);
		const downBranch = extractSingleBranch(item[2]);
		return {
			index: idx + 1,
			upBranch,
			downBranch,
			upGan: upBranch ? (xunGanMap[upBranch] || '') : '',
			downGan: downBranch ? (xunGanMap[downBranch] || '') : '',
		};
	});
	const tianHeGanPool = uniqueStrings([
		dayGan,
		dayZhiGan,
		ke1UpGan,
		ke3UpGan,
		...kePairGanTuples.map((item)=>item.upGan),
		...kePairGanTuples.map((item)=>item.downGan),
		...sanChuanGans,
	]);
	const courseGans = uniqueStrings([
		dayGan,
		ke1UpGan,
		ke3UpGan,
		...sanChuanGans,
	]);
	const courseBranches = uniqueStrings([
		...sanChuanBranches,
		...keUp,
		...keDown,
	]);
	const sunBranch = getPlanetBranch(chartObj, AstroConst.SUN);
	const moonBranch = getPlanetBranch(chartObj, AstroConst.MOON);
	const sunSuName = getPlanetSuName(chartObj, AstroConst.SUN);
	const moonSuName = getPlanetSuName(chartObj, AstroConst.MOON);
	const sunErfanBranch = getPlanetErfanBranch(chartObj, AstroConst.SUN);
	const moonErfanBranch = getPlanetErfanBranch(chartObj, AstroConst.MOON);
	const allKeShe = keRaw.length === 4 && keRaw.every((item)=>safeRestrain(item[1], item[2]));
	const allKeZei = keRaw.length === 4 && keRaw.every((item)=>safeRestrain(item[2], item[1]));
	const dayGodMap = {
		base: liureng && liureng.gods ? liureng.gods : {},
		gan: liureng && liureng.godsGan ? liureng.godsGan : {},
		month: liureng && liureng.godsMonth ? liureng.godsMonth : {},
		zi: liureng && liureng.godsZi ? liureng.godsZi : {},
		year: liureng && liureng.godsYear && liureng.godsYear.taisui1 ? liureng.godsYear.taisui1 : {},
	};
	// 昼/夜两贵的地盘位 + 当前用昼或夜（供毕法贵人类法 3/45/46/49/50）。
	const guiObj = LRConst.GuiRengs[guirengType] || LRConst.GuiRengs[2];
	const dayGuiBranch = guiObj && guiObj.day ? (guiObj.day[dayGan] || '') : '';
	const nightGuiBranch = guiObj && guiObj.night ? (guiObj.night[dayGan] || '') : '';
	const dayNight = (layout && layout.guizi === dayGuiBranch) ? '昼' : '夜';
	return {
		layout,
		keData,
		sanChuan,
		courseName: sanChuan && sanChuan.name ? `${sanChuan.name}` : '',
		dayGanZi,
		dayGan,
		dayZhi,
		dayGanBranch,
		yearBranch,
		timeBranch: occupyTimeBranch,
		runYearGanZi,
		runYearGan,
		runYearBranch,
		// 本命支:空亡/年命上神两处早已按 benMingBranch 取用,此前 context 从不产出 → 「本命上神」一位恒不触发。
		benMingBranch: (extraOpts && extraOpts.benMingBranch && LRConst.ZiList.indexOf(extraOpts.benMingBranch) >= 0) ? extraOpts.benMingBranch : '',
		monthBranch,
		season,
		jieqi,
		sunBranch,
		moonBranch,
		sunSuName,
		moonSuName,
		sunErfanBranch,
		moonErfanBranch,
		prevDayGanZi,
		prevDayGan,
		prevDayZhi,
		prevDayGanBranch,
		guChenBranch: guChenGuaSu ? guChenGuaSu.guchen : '',
		guaSuBranch: guChenGuaSu ? guChenGuaSu.guasu : '',
		keRaw,
		keUpBranches: keUp,
		keDownBranches: keDown,
		ke1UpGan,
		ke3UpGan,
		dayZhiGan,
		kePairGanTuples,
		tianHeGanPool,
		ke1Up: keUp[0] || '',
		ke3Up: keUp[2] || '',
		courseGans,
		sanChuanBranches: sanChuanBranchesAligned,
		sanChuanGans: sanChuanGansAligned,
		sanChuanGods,
		firstBranch: sanChuanBranchesAligned[0] || '',
		midBranch: sanChuanBranchesAligned[1] || '',
		lastBranch: sanChuanBranchesAligned[2] || '',
		firstGan: sanChuanGansAligned[0] || '',
		midGan: sanChuanGansAligned[1] || '',
		lastGan: sanChuanGansAligned[2] || '',
		firstGod: sanChuanGods[0] || '',
		midGod: sanChuanGods[1] || '',
		lastGod: sanChuanGods[2] || '',
		branchGodMap,
		branchUpMap,
		upDownMap,
		xunGanMap,
		guirenForward: !!(layout && layout.guirenForward),
		yueGeneralBranch,
		panStyle,
		xunHeadBranch,
		xunHeadGanZi,
		xunTailBranch,
		xunKongBranches,
		yiMaBranches,
		dingHorseBranches,
		horseBranches,
		courseBranches,
		allKeShe,
		allKeZei,
		dayGodMap,
		seasonMap,
		dayGanWuXing: LRConst.GanZiWuXing[dayGan] || '',
		dayZhiWuXing: LRConst.GanZiWuXing[dayZhi] || '',
		sanChuanText: sanChuanGz.length ? sanChuanGz.join(' / ') : '',
		sanChuanBranchText: sanChuanBranches.length ? sanChuanBranches.join('→') : '',
		sanChuanGodText: sanChuanGods.length ? sanChuanGods.join('→') : '',
		guizi: layout && layout.guizi ? layout.guizi : '',
		dayGuiBranch,
		nightGuiBranch,
		dayNight,
	};
}

export function matchDaGeReferences(context){
	if(!context){
		return [];
	}
	let key = context.courseName ? COURSE_TO_DAGE_KEY[context.courseName] : '';
	if(!key){
		if(context.allKeShe){
			key = 'yuanshou';
		}else if(context.allKeZei){
			key = 'chongshen';
		}
	}
	if(!key || !DA_GE_META[key]){
		return [];
	}
	const meta = DA_GE_META[key];
	return [createReferenceItem(meta, [
		context.courseName ? `当前课式：${context.courseName}` : '',
		context.sanChuanText ? `三传：${context.sanChuanText}` : '',
		context.dayGanZi ? `日干支：${context.dayGanZi}` : '',
	])];
}

export function matchXiaoJuReferences(context){
	if(!context){
		return [];
	}
	const refs = [];
	const added = {};
	const add = (key, evidence, extra = {})=>{
		if(!XIAO_JU_META[key]){
			return;
		}
		const uniqEvidence = uniqueStrings(evidence || []);
		if(added[key] !== undefined){
			const existed = refs[added[key]];
			if(!existed){
				return;
			}
			existed.evidence = uniqueStrings([...(existed.evidence || []), ...uniqEvidence]);
			Object.keys(extra || {}).forEach((k)=>{
				if(existed[k] === undefined || existed[k] === null || existed[k] === ''){
					existed[k] = extra[k];
				}
			});
			return;
		}
		const one = createReferenceItem(XIAO_JU_META[key], uniqEvidence, extra);
		refs.push(one);
		added[key] = refs.length - 1;
	};
	const findGodBranch = (godName)=>{
		if(!context.branchGodMap || !godName){
			return '';
		}
		const keys = Object.keys(context.branchGodMap);
		for(let i=0; i<keys.length; i++){
			const key = keys[i];
			if(context.branchGodMap[key] === godName){
				return key;
			}
		}
		return '';
	};
	const isBranchBeforeDayGan = (branch)=>{
		if(!branch || !context.dayGanBranch){
			return false;
		}
		const base = getBranchIndex(context.dayGanBranch);
		const idx = getBranchIndex(branch);
		if(base < 0 || idx < 0){
			return false;
		}
		const delta = (idx - base + 12) % 12;
		return delta > 0 && delta <= 5;
	};
	const isBranchBeforeGuiren = (branch)=>{
		if(!branch || !context.guizi || !context.guirenForward){
			return false;
		}
		const base = getBranchIndex(context.guizi);
		const idx = getBranchIndex(branch);
		if(base < 0 || idx < 0){
			return false;
		}
		const delta = (idx - base + 12) % 12;
		return delta > 0 && delta <= 5;
	};

	const hasPortalBranch = context.sanChuanBranches.some((item)=>item === '卯' || item === '酉');
	if(context.firstGod === '天后' && context.lastGod === '六合' && context.firstBranch && context.lastBranch){
		add('yinv', [
			`神将序列：${context.sanChuanGodText || '—'}`,
			context.sanChuanText ? `三传：${context.sanChuanText}` : '',
			hasPortalBranch ? '课传带卯酉门户' : '课传未见卯酉门户',
		]);
	}
	if(context.firstGod === '六合' && context.lastGod === '天后' && context.firstBranch && context.lastBranch){
		add('jiaotong', [
			`神将序列：${context.sanChuanGodText || '—'}`,
			context.sanChuanText ? `三传：${context.sanChuanText}` : '',
			hasPortalBranch ? '课传带卯酉门户' : '课传未见卯酉门户',
		]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>LRConst.ZiMeng.indexOf(item) >= 0)){
		add('yuantai', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
		]);
	}
	const dayTopAreZhong = LRConst.ZiZong.indexOf(context.ke1Up) >= 0
		&& LRConst.ZiZong.indexOf(context.ke3Up) >= 0;
	const sanjiaoCond = context.sanChuanBranches.length === 3
		&& context.sanChuanBranches.every((item)=>LRConst.ZiZong.indexOf(item) >= 0)
		&& dayTopAreZhong
		&& context.sanChuanGods.indexOf('太阴') >= 0
		&& context.sanChuanGods.indexOf('六合') >= 0;
	if(sanjiaoCond){
		add('sanjiao', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`三传神将：${context.sanChuanGodText || '—'}`,
			`日干/日支上神（四仲）：${context.ke1Up || '—'} / ${context.ke3Up || '—'}`,
		]);
	}
	if(['辰', '戌'].indexOf(context.ke1Up) >= 0 || ['辰', '戌'].indexOf(context.ke3Up) >= 0){
		add('zhanguan', [
			`日干上神：${context.ke1Up || '—'}；日支上神：${context.ke3Up || '—'}`,
		]);
	}
	const hasYiMaInCourse = context.yiMaBranches.length > 0
		&& context.yiMaBranches.some((item)=>context.courseBranches.indexOf(item) >= 0);
	const hasDingHorseInCourse = context.dingHorseBranches.length > 0
		&& context.dingHorseBranches.some((item)=>context.courseBranches.indexOf(item) >= 0);
	const allJi = context.sanChuanBranches.length === 3
		&& context.sanChuanBranches.every((item)=>LRConst.ZiJi.indexOf(item) >= 0);
	if(allJi && (hasYiMaInCourse || hasDingHorseInCourse)){
		add('youzi', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`驿马入课传：${hasYiMaInCourse ? '是' : '否'}（${context.yiMaBranches.join('、') || '—'}）`,
			`丁马入课传：${hasDingHorseInCourse ? '是' : '否'}（${context.dingHorseBranches.join('、') || '—'}）`,
		]);
	}
	const headGod = context.xunHeadBranch ? context.branchGodMap[context.xunHeadBranch] : '';
	const headUp = context.xunHeadBranch ? context.branchUpMap[context.xunHeadBranch] : '';
	if(context.xunHeadBranch && context.xunTailBranch
		&& headGod === '玄武'
		&& headUp === context.xunTailBranch
		&& context.firstBranch === context.xunTailBranch){
		add('bikou', [
			`旬首：${context.xunHeadBranch}（乘${headGod}）`,
			`旬尾：${context.xunTailBranch}（发用）`,
		]);
	}
	const jieliCore = safeRestrain(context.dayGan, context.ke3Up) && safeRestrain(context.dayZhi, context.ke1Up);
	const jieliOppose = safeOppose(context.ke1Up, context.ke3Up);
	if(jieliCore){
		add('jieli', [
			`日干克日支上神：${context.dayGan || '—'}克${context.ke3Up || '—'}`,
			`日支克日干上神：${context.dayZhi || '—'}克${context.ke1Up || '—'}`,
			jieliOppose ? `上神相冲：${context.ke1Up || '—'}↔${context.ke3Up || '—'}` : '上神未冲（按两人法仍可取解离）',
		]);
	}
	const luanshouA = context.ke1Up && context.ke1Up === context.dayZhi && safeRestrain(context.dayZhi, context.dayGan);
	const luanshouB = context.ke3Up && context.dayGanBranch && context.ke3Up === context.dayGanBranch && safeRestrain(context.dayZhi, context.dayGan);
	if(luanshouA){
		add('luanshou', [
			`法二：日支临日干（日干上神${context.ke1Up || '—'} = 日支${context.dayZhi || '—'}）`,
			`法二：日支克日干（${context.dayZhi || '—'}克${context.dayGan || '—'}）`,
		]);
	}
	if(luanshouB){
		add('luanshou', [
			`法一：日干临日支（日支上神${context.ke3Up || '—'} = 日干寄支${context.dayGanBranch || '—'}）`,
			`法一：日支克日干（${context.dayZhi || '—'}克${context.dayGan || '—'}）`,
		]);
	}
	if(context.allKeShe){
		add('juesi', [
			'四课皆上克下（摄）',
			context.courseName ? `当前课式：${context.courseName}` : '',
		]);
	}
	if(context.allKeZei){
		add('wulu', [
			'四课皆下克上（贼）',
			context.courseName ? `当前课式：${context.courseName}` : '',
		]);
	}
	const hasGuChen = context.guChenBranch && context.courseBranches.indexOf(context.guChenBranch) >= 0;
	const hasGuaSu = context.guaSuBranch && context.courseBranches.indexOf(context.guaSuBranch) >= 0;
	const hasXunKong = context.xunKongBranches.length > 0
		&& context.courseBranches.some((item)=>context.xunKongBranches.indexOf(item) >= 0);
	if(hasGuChen && hasGuaSu && hasXunKong){
		add('gugua', [
			`孤辰/寡宿：${context.guChenBranch || '—'} / ${context.guaSuBranch || '—'}`,
			`旬空：${context.xunKongBranches.join('、') || '—'}`,
		]);
	}
	const longzhanDay = context.dayZhi === '卯' || context.dayZhi === '酉';
	const longzhanYong = context.firstBranch === '卯' || context.firstBranch === '酉';
	const longzhanRunYear = context.runYearBranch === '卯' || context.runYearBranch === '酉';
	if(longzhanDay && longzhanYong && longzhanRunYear){
		add('longzhan', [
			`日支：${context.dayZhi || '—'}；发用：${context.firstBranch || '—'}；行年：${context.runYearBranch || '—'}`,
		]);
	}
	if(context.guizi === '卯' || context.guizi === '酉'){
		add('lide', [
			`贵人临门：${context.guizi}`,
		]);
	}
	const zhuixuCondA = context.ke1Up && context.ke1Up === context.dayZhi && safeRestrain(context.dayGan, context.dayZhi);
	const zhuixuCondB = context.ke3Up && context.dayGanBranch && context.ke3Up === context.dayGanBranch && safeRestrain(context.dayGan, context.dayZhi);
	if(zhuixuCondA){
		add('zhuixu', [
			`法二：日支临日干（日干上神${context.ke1Up || '—'} = 日支${context.dayZhi || '—'}）`,
			`法二：日干克日支（${context.dayGan || '—'}克${context.dayZhi || '—'}）`,
		]);
	}
	if(zhuixuCondB){
		add('zhuixu', [
			`法一：日干临日支（日支上神${context.ke3Up || '—'} = 日干寄支${context.dayGanBranch || '—'}）`,
			`法一：日干克日支（${context.dayGan || '—'}克${context.dayZhi || '—'}）`,
		]);
	}
	const deGan = context.dayGan ? GAN_DE_GAN[context.dayGan] : '';
	const deBranch = deGan ? (LRConst.GanJiZi[deGan] || '') : '';
	const deElemByDayGan = {
		'甲': '木', '己': '木',
		'乙': '金', '庚': '金',
		'丙': '火', '辛': '火',
		'丁': '水', '壬': '水',
		'戊': '土', '癸': '土',
	};
	const xingElemByDayZhi = {
		'寅': '火', '午': '火', '戌': '火',
		'申': '木', '子': '木', '辰': '木',
		'巳': '金', '酉': '金', '丑': '金',
		'亥': '水', '卯': '水', '未': '水',
	};
	const wuXingKe = {
		'木': '土',
		'火': '金',
		'土': '水',
		'金': '木',
		'水': '火',
	};
	const wuXingSheng = {
		'木': '火',
		'火': '土',
		'土': '金',
		'金': '水',
		'水': '木',
	};
	const deElem = deElemByDayGan[context.dayGan] || '';
	const xingElem = xingElemByDayZhi[context.dayZhi] || '';
	const xingdeResult = (()=> {
		if(!deElem || !xingElem){
			return '';
		}
		if(deElem === xingElem){
			return '德刑同位';
		}
		if(wuXingKe[xingElem] === deElem){
			return '刑胜德';
		}
		if(wuXingKe[deElem] === xingElem){
			return '德胜刑';
		}
		if(wuXingSheng[deElem] === xingElem){
			return '刑胜德（受生）';
		}
		if(wuXingSheng[xingElem] === deElem){
			return '德胜刑（受生）';
		}
		return '';
	})();
	let xingBranches = [];
	if(['寅', '午', '戌'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['寅', '午', '戌'];
	}else if(['申', '子', '辰'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['申', '子', '辰'];
	}else if(['巳', '酉', '丑'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['巳', '酉', '丑'];
	}else if(['亥', '卯', '未'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['亥', '卯', '未'];
	}
	if(deBranch && xingBranches.length && context.courseBranches.indexOf(deBranch) >= 0
		&& hasAny(context.courseBranches, xingBranches)){
		add('xingde', [
			`日干：${context.dayGan || '—'}；德干：${deGan || '—'}；德寄支：${deBranch || '—'}`,
			`日支：${context.dayZhi || '—'}；刑支系：${xingBranches.join('、')}`,
			xingdeResult ? `德刑五行：德${deElem || '—'} / 刑${xingElem || '—'}；${xingdeResult}` : '',
		]);
	}
	const firstWuXing = context.firstBranch ? (LRConst.GanZiWuXing[context.firstBranch] || '') : '';
	if(firstWuXing && context.dayGanWuXing && firstWuXing === context.dayGanWuXing){
		add('wuqi', [
			`发用：${context.firstBranch || '—'}（${firstWuXing}）`,
			`日干：${context.dayGan || '—'}（${context.dayGanWuXing || '—'}）`,
		]);
	}
	const firstIsNew = context.firstBranch && (LRConst.ZiMeng.indexOf(context.firstBranch) >= 0 || LRConst.YangZi.indexOf(context.firstBranch) >= 0);
	const firstIsOld = context.firstBranch && (LRConst.ZiJi.indexOf(context.firstBranch) >= 0 || LRConst.YingZi.indexOf(context.firstBranch) >= 0);
	const lastIsNew = context.lastBranch && (LRConst.ZiMeng.indexOf(context.lastBranch) >= 0 || LRConst.YangZi.indexOf(context.lastBranch) >= 0);
	const lastIsOld = context.lastBranch && (LRConst.ZiJi.indexOf(context.lastBranch) >= 0 || LRConst.YingZi.indexOf(context.lastBranch) >= 0);
	if((firstIsNew && lastIsOld) || (firstIsOld && lastIsNew)){
		add('xingu', [
			`初传：${context.firstBranch || '—'}；末传：${context.lastBranch || '—'}`,
			firstIsNew && lastIsOld ? '由新趋旧' : '由旧转新',
		]);
	}
	let tunCount = 0;
	let fuCount = 0;
	if(context.firstGod && TIANJIANG_XIONG.indexOf(context.firstGod) >= 0){
		tunCount += 1;
	}
	if(context.firstGod && TIANJIANG_JI.indexOf(context.firstGod) >= 0){
		fuCount += 1;
	}
	if(context.firstBranch && (safeRestrain(context.dayGan, context.firstBranch) || safeRestrain(context.dayZhi, context.firstBranch))){
		tunCount += 1;
	}
	if(context.firstBranch && (safeAccrue(context.dayGan, context.firstBranch) || safeBrother(context.dayGan, context.firstBranch))){
		fuCount += 1;
	}
	if(context.firstBranch && safeOppose(context.dayZhi, context.firstBranch)){
		tunCount += 1;
	}
	if(context.firstBranch && context.xunKongBranches.indexOf(context.firstBranch) >= 0){
		tunCount += 1;
	}
	if(tunCount >= 2 || fuCount >= 2){
		add('tunfu', [
			`发用：${context.firstBranch || '—'}；贵神：${context.firstGod || '—'}`,
			`迍数：${tunCount}；福数：${fuCount}`,
		]);
	}
	if(context.firstGod && context.lastGod){
		const firstGood = TIANJIANG_JI.indexOf(context.firstGod) >= 0;
		const lastGood = TIANJIANG_JI.indexOf(context.lastGod) >= 0;
		const firstBad = TIANJIANG_XIONG.indexOf(context.firstGod) >= 0;
		const lastBad = TIANJIANG_XIONG.indexOf(context.lastGod) >= 0;
		if((firstGood && lastBad) || (firstBad && lastGood)){
			add('shizhong', [
				`初传：${context.firstBranch || '—'}（${context.firstGod || '—'}）`,
				`末传：${context.lastBranch || '—'}（${context.lastGod || '—'}）`,
			]);
		}
	}
	if(JIU_CHOU_DAYS.indexOf(context.dayGanZi) >= 0 && context.ke3Up === '丑'){
		add('jiuchou', [
			`日干支：${context.dayGanZi || '—'}`,
			`日支上神：${context.ke3Up || '—'}`,
		]);
	}
	const erfanSunBranch = context.sunSuName && ERFAN_SU_TO_BRANCH[context.sunSuName]
		? ERFAN_SU_TO_BRANCH[context.sunSuName]
		: '';
	const erfanMoonBranch = context.moonSuName && ERFAN_SU_TO_BRANCH[context.moonSuName]
		? ERFAN_SU_TO_BRANCH[context.moonSuName]
		: '';
	const erfanSunZhong = erfanSunBranch && LRConst.ZiZong.indexOf(erfanSunBranch) >= 0;
	const erfanMoonZhong = erfanMoonBranch && LRConst.ZiZong.indexOf(erfanMoonBranch) >= 0;
	const douGangToChouWei = (context.branchUpMap && context.branchUpMap['丑'] === '辰')
		|| (context.branchUpMap && context.branchUpMap['未'] === '辰');
	if(erfanSunZhong && erfanMoonZhong && douGangToChouWei){
		add('erfan', [
			`宿盘日月临仲：太阳${context.sunSuName || '—'}→${erfanSunBranch || '—'}；太阴${context.moonSuName || '—'}→${erfanMoonBranch || '—'}`,
			`斗罡加丑未：${context.branchUpMap['丑'] === '辰' ? '丑' : ''}${context.branchUpMap['未'] === '辰' ? ' 未' : ''}`.trim() || '否',
		]);
	}
	const isSiLi = containsJieQi(context.jieqi, ['立春', '立夏', '立秋', '立冬']);
	const tianHuoLinkedToPrev = [context.ke1Up, context.ke3Up, context.firstBranch, context.lastBranch]
		.some((item)=>item && (item === context.prevDayGanBranch || item === context.prevDayZhi));
	if(isSiLi && tianHuoLinkedToPrev){
		add('tianhuo', [
			`节气：${context.jieqi || '—'}`,
			`昨日日辰：${context.prevDayGanZi || '—'}；课传临值：${context.prevDayGanBranch || '—'} / ${context.prevDayZhi || '—'}`,
		]);
	}
	const isFenZhi = containsJieQi(context.jieqi, ['春分', '夏至', '秋分', '冬至']);
	if(isFenZhi && context.moonBranch && context.prevDayZhi && context.moonBranch === context.prevDayZhi){
		add('tiankou', [
			`节气：${context.jieqi || '—'}`,
			`太阴临昨支：月支${context.moonBranch || '—'} = 昨日日支${context.prevDayZhi || '—'}`,
		]);
	}
	if(context.timeBranch && context.firstBranch && safeRestrain(context.timeBranch, context.dayGan) && safeRestrain(context.firstBranch, context.dayGan)){
		add('tianwang', [
			`时支：${context.timeBranch || '—'}克${context.dayGan || '—'}`,
			`初传：${context.firstBranch || '—'}克${context.dayGan || '—'}`,
		]);
	}
	const youHunBranch = shiftBranch(context.monthBranch, -3);
	const coreTargets = uniqueStrings([context.runYearBranch, context.dayGanBranch, context.dayZhi]);
	if(youHunBranch && coreTargets.indexOf(youHunBranch) >= 0){
		add('feihun', [
			`月建：${context.monthBranch || '—'}；游魂：${youHunBranch || '—'}`,
			`命中位：${coreTargets.join('、') || '—'}`,
		]);
	}
	const sangmenBranch = extractSingleBranch(matchMapValueByKey(context.dayGodMap.year, '丧门'));
	if(sangmenBranch && coreTargets.indexOf(sangmenBranch) >= 0){
		add('sangmen', [
			`丧门：${sangmenBranch || '—'}`,
			context.firstGod === '白虎' ? '发用乘白虎，凶势更急' : '',
		]);
	}
	const monthSeqIdx = MONTH_BRANCH_SEQUENCE.indexOf(context.monthBranch);
	const tianGuiBranch = monthSeqIdx >= 0 ? ['酉', '午', '卯', '子'][monthSeqIdx % 4] : '';
	if(tianGuiBranch && coreTargets.indexOf(tianGuiBranch) >= 0){
		add('fuyang', [
			`月建：${context.monthBranch || '—'}；天鬼：${tianGuiBranch || '—'}`,
			`命中位：${coreTargets.join('、') || '—'}`,
		]);
	}
	const tianLuoBranch = shiftBranch(context.dayGanBranch, 1);
	const diWangBranch = tianLuoBranch ? shiftBranch(tianLuoBranch, 6) : '';
	const runYearUp = context.runYearBranch && context.branchUpMap ? (context.branchUpMap[context.runYearBranch] || '') : '';
	const coreUpTargets = uniqueStrings([context.ke1Up, context.ke3Up, runYearUp]);
	const luoWangBranches = uniqueStrings([tianLuoBranch, diWangBranch]);
	const luoWangCoreHits = luoWangBranches.filter((item)=>item && coreTargets.indexOf(item) >= 0);
	const luoWangUpHits = luoWangBranches.filter((item)=>item && coreUpTargets.indexOf(item) >= 0);
	if(luoWangCoreHits.length > 0 || luoWangUpHits.length > 0){
		add('luowang', [
			`日干寄支：${context.dayGanBranch || '—'}；天罗：${tianLuoBranch || '—'}；地网：${diWangBranch || '—'}`,
			`命中地位：${luoWangCoreHits.join('、') || '无'}（行年/日干寄支/日支：${coreTargets.join('、') || '—'}）`,
			`命中上神：${luoWangUpHits.join('、') || '无'}（行年/日干/日支上神：${coreUpTargets.join('、') || '—'}）`,
		]);
	}
	const dayGanChangSheng = extractSingleBranch(matchMapValueByKey(context.dayGodMap.gan, '长生'));
	const douGangOnChangSheng = dayGanChangSheng && context.branchUpMap && context.branchUpMap[dayGanChangSheng] === '辰';
	const firstState = getSeasonStateForBranch(context.seasonMap, context.firstBranch);
	const firstDownBranch = context.upDownMap ? (context.upDownMap[context.firstBranch] || '') : '';
	const firstWeak = isXiuQiuState(firstState)
		|| LRConst.ZiJi.indexOf(context.firstBranch) >= 0
		|| (firstDownBranch && safeRestrain(firstDownBranch, context.firstBranch));
	if(douGangOnChangSheng && firstWeak){
		add('tianyu', [
			`日干长生：${dayGanChangSheng || '—'}；罡加长生：辰临${dayGanChangSheng || '—'}`,
			`初传：${context.firstBranch || '—'}（${firstState || '—'}）${firstDownBranch ? `；下神：${firstDownBranch}` : ''}`,
		]);
	}
	const siqiHasDou = [context.firstBranch, context.ke1Up, context.ke3Up].some((item)=>item === '辰');
	const siqiSunInCore = context.sunBranch
		&& [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.sunBranch) >= 0;
	const siqiMoonInCore = context.moonBranch
		&& [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.moonBranch) >= 0;
	if(siqiHasDou && (siqiSunInCore || siqiMoonInCore)){
		add('siqi', [
			`斗罡入局：${context.firstBranch === '辰' ? '发用' : `课位(${context.ke1Up === '辰' ? '日干上神' : '日支上神'})`}`,
			`日月入主位：太阳${context.sunBranch || '—'}；太阴${context.moonBranch || '—'}`,
		]);
	}
	const deadGodBranch = monthSeqIdx >= 0 ? shiftBranch('巳', monthSeqIdx) : '';
	const whiteTigerTargets = uniqueStrings([
		context.dayGanBranch,
		context.dayZhi,
		context.runYearBranch,
	]).filter((item)=>item && context.branchGodMap[item] === '白虎');
	const whiteTigerCarryDead = deadGodBranch && context.branchGodMap[deadGodBranch] === '白虎';
	if(whiteTigerCarryDead && whiteTigerTargets.length){
		add('pohua', [
			`死神：${deadGodBranch || '—'}；白虎同位：是`,
			`白虎临：${whiteTigerTargets.join('、') || '—'}${context.firstGod === '白虎' ? '；并见发用白虎' : ''}`,
		]);
	}
	const dayGanState = getSeasonStateForBranch(context.seasonMap, context.dayGan);
	const dayZhiState = getSeasonStateForBranch(context.seasonMap, context.dayZhi);
	const sanChuanAllJi = context.sanChuanGods.length === 3
		&& context.sanChuanGods.every((item)=>TIANJIANG_JI.indexOf(item) >= 0);
	const sanGuangWangXiang = !!(context.firstBranch
		&& isWangXiangState(dayGanState)
		&& isWangXiangState(dayZhiState)
		&& isWangXiangState(firstState));
	if(sanGuangWangXiang && sanChuanAllJi){
		add('sanguang', [
			`三传贵神：${context.sanChuanGodText || '—'}`,
			`旺相：日干${context.dayGan || '—'}(${dayGanState || '—'})、日支${context.dayZhi || '—'}(${dayZhiState || '—'})、初传${context.firstBranch || '—'}(${firstState || '—'})`,
			`吉神判定：${context.sanChuanGods.join('→') || '—'}（全为吉神）`,
		]);
	}
	const sanyangCore = context.guirenForward
		&& context.firstBranch
		&& isWangXiangState(dayGanState)
		&& isWangXiangState(dayZhiState)
		&& isWangXiangState(firstState)
		&& isBranchBeforeGuiren(context.dayGanBranch)
		&& isBranchBeforeGuiren(context.dayZhi);
	if(sanyangCore){
		add('sanyang', [
			`贵人顺治：是；贵人位：${context.guizi || '—'}`,
			`日干/日支在贵人之前：${context.dayGanBranch || '—'} / ${context.dayZhi || '—'}`,
			`旺相：日干${context.dayGan || '—'}(${dayGanState || '—'})、日支${context.dayZhi || '—'}(${dayZhiState || '—'})、初传${context.firstBranch || '—'}(${firstState || '—'})`,
		]);
	}
	const xuanwuBranch = findGodBranch('玄武');
	const baihuBranch = findGodBranch('白虎');
	const lastState = getSeasonStateForBranch(context.seasonMap, context.lastBranch);
	const sanYinCond = !context.guirenForward
		&& isBranchBeforeDayGan(xuanwuBranch)
		&& isBranchBeforeDayGan(baihuBranch)
		&& isXiuQiuState(firstState)
		&& isXiuQiuState(lastState)
		&& context.timeBranch
		&& context.runYearBranch
		&& safeRestrain(context.timeBranch, context.runYearBranch);
	if(sanYinCond){
		add('sanyin', [
			`贵人逆治：是；元武/白虎在日前：${xuanwuBranch || '—'} / ${baihuBranch || '—'}`,
			`初末休囚：${context.firstBranch || '—'}(${firstState || '—'})、${context.lastBranch || '—'}(${lastState || '—'})；时支克行年：${context.timeBranch}克${context.runYearBranch}`,
		]);
	}
	const guirenCarrier = context.guizi ? (context.branchUpMap[context.guizi] || '') : '';
	const guirenCarrierState = getSeasonStateForBranch(context.seasonMap, guirenCarrier);
	const guirenOnCore = [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.guizi) >= 0;
	const sanChuanStates = [context.firstBranch, context.midBranch, context.lastBranch].map((item)=>getSeasonStateForBranch(context.seasonMap, item));
	const sanChuanAllWang = sanChuanStates.length === 3 && sanChuanStates.every((item)=>isWangXiangState(item));
	if(isWangXiangState(guirenCarrierState) && guirenOnCore && sanChuanAllWang){
		add('fugui', [
			`贵人临：${context.guizi || '—'}（命中日辰行年）`,
			`贵人所乘：${guirenCarrier || '—'}（${guirenCarrierState || '—'}）；三传生旺：是`,
		]);
	}
	const xunQiBranch = XUN_QI_BY_XUN_HEAD[extractGanZi(context.xunHeadGanZi)] || '';
	const ganQiBranch = context.dayGan ? (GAN_QI_BRANCH[context.dayGan] || '') : '';
	if((xunQiBranch && context.courseBranches.indexOf(xunQiBranch) >= 0)
		|| (ganQiBranch && context.courseBranches.indexOf(ganQiBranch) >= 0)){
		add('sanqi', [
			`旬首：${context.xunHeadGanZi || '—'}；旬奇：${xunQiBranch || '—'}`,
			`日干：${context.dayGan || '—'}；干奇：${ganQiBranch || '—'}`,
		]);
	}
	const xunYiBranch = context.xunHeadBranch;
	const dayIdx = getBranchIndex(context.dayZhi);
	const zhiYiBranch = dayIdx >= 0 ? LRConst.ZiList[(6 - dayIdx + 12) % 12] : '';
	if((xunYiBranch && context.courseBranches.indexOf(xunYiBranch) >= 0)
		|| (zhiYiBranch && context.courseBranches.indexOf(zhiYiBranch) >= 0)){
		add('liuyi', [
			`旬仪：${xunYiBranch || '—'}`,
			`支仪：${zhiYiBranch || '—'}`,
		]);
	}
	if(context.firstBranch === '戌' && context.firstGod === '太常' && hasYiMaInCourse){
		add('guanjue', [
			`发用：${context.firstBranch || '—'}（${context.firstGod || '—'}）`,
			`驿马：${context.yiMaBranches.join('、') || '—'}`,
		]);
	}
	const hasZiMaoWu = ['子', '卯', '午'].every((item)=>context.sanChuanBranches.indexOf(item) >= 0);
	if(hasZiMaoWu && ['寅', '申'].indexOf(context.monthBranch) >= 0){
		add('xuangai', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`月建：${context.monthBranch || '—'}`,
		]);
	}
	if(context.branchUpMap && context.branchUpMap['申'] === '卯'){
		add('zhuolun', [
			`地盘申 -> 天盘${context.branchUpMap['申'] || '—'}`,
		]);
	}
	if(['巳', '戌', '卯'].every((item)=>context.sanChuanBranches.indexOf(item) >= 0)){
		add('zhuyin', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
		]);
	}
	const yearGod = context.yearBranch ? context.branchGodMap[context.yearBranch] : '';
	const yueGod = context.yueGeneralBranch ? context.branchGodMap[context.yueGeneralBranch] : '';
	if(yearGod === '贵人' && yueGod === '贵人' && context.firstGod === '贵人'){
		add('longde', [
			`年支：${context.yearBranch || '—'}乘${yearGod || '—'}`,
			`月将：${context.yueGeneralBranch || '—'}乘${yueGod || '—'}；发用：${context.firstBranch || '—'}乘${context.firstGod || '—'}`,
		]);
	}
	const scIdx = context.sanChuanBranches.map((item)=>getBranchIndex(item));
	if(scIdx.length === 3 && scIdx.every((idx)=>idx >= 0)){
		const forward = scIdx[1] === (scIdx[0] + 1) % 12 && scIdx[2] === (scIdx[1] + 1) % 12;
		const backward = scIdx[1] === (scIdx[0] + 11) % 12 && scIdx[2] === (scIdx[1] + 11) % 12;
		if(forward || backward){
			add('lianzhu', [
				`三传地支：${context.sanChuanBranchText || '—'}`,
				forward ? '进连珠' : '退连珠',
			]);
		}
		const jianForward = scIdx[1] === (scIdx[0] + 2) % 12 && scIdx[2] === (scIdx[1] + 2) % 12;
		const jianBackward = scIdx[1] === (scIdx[0] + 10) % 12 && scIdx[2] === (scIdx[1] + 10) % 12;
		if(jianForward || jianBackward){
			add('jianchuan', [
				`三传地支：${context.sanChuanBranchText || '—'}`,
				jianForward ? '顺间传，跳跃前行' : '逆间传，跳跃后退',
			]);
		}
	}
	const liuchunAllYang = context.courseBranches.length > 0 && context.courseBranches.every((item)=>LRConst.YangZi.indexOf(item) >= 0);
	const liuchunAllYin = context.courseBranches.length > 0 && context.courseBranches.every((item)=>LRConst.YingZi.indexOf(item) >= 0);
	if(liuchunAllYang || liuchunAllYin){
		add('liuchun', [liuchunAllYang ? '四课三传地支全阳（六阳），利公开主动' : '四课三传地支全阴（六阴），利私谋隐晦']);
	}
	if(context.sanChuanBranches.length === 3 && Array.isArray(context.keUpBranches) && context.sanChuanBranches.every((item)=>context.keUpBranches.indexOf(item) >= 0)){
		add('panzhu', [`三传${context.sanChuanBranchText || '—'}尽入四课上神，事在目前`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['寅', '午', '戌'].indexOf(item) >= 0)){
		add('yanshang', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['亥', '卯', '未'].indexOf(item) >= 0)){
		add('quzhi', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['辰', '戌', '丑', '未'].indexOf(item) >= 0)){
		add('jiase', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['巳', '酉', '丑'].indexOf(item) >= 0)){
		add('congge', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['申', '子', '辰'].indexOf(item) >= 0)){
		add('runxia', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	TIANHE_PAIR_RULES.forEach((rule)=>{
		const evidence = collectTianHeEvidence(context, rule.a, rule.b);
		if(evidence.length){
			add(rule.key, [
				`课传天干池：${(context.tianHeGanPool || []).join('、') || '—'}`,
				`命中天合：${rule.label}`,
				...evidence,
			]);
		}
	});
	const jianggongDown = context.upDownMap ? (context.upDownMap['亥'] || '') : '';
	const mingtangDown = context.upDownMap ? (context.upDownMap['子'] || '') : '';
	const yutangDown = context.upDownMap ? (context.upDownMap['丑'] || '') : '';
	const isJianggongshi = jianggongDown && LRConst.ZiZong.indexOf(jianggongDown) >= 0;
	const isMingtangshi = mingtangDown && LRConst.ZiZong.indexOf(mingtangDown) >= 0;
	const isYutangshi = yutangDown && LRConst.ZiZong.indexOf(yutangDown) >= 0;
	if(isJianggongshi){
		add('jianggongshi', [
			`天盘登明（亥）加临地盘：${jianggongDown || '—'}（四仲）`,
			'判定：登明（亥）加四仲（子午卯酉）',
		]);
	}
	if(isMingtangshi){
		add('mingtangshi', [
			`天盘神后（子）加临地盘：${mingtangDown || '—'}（四仲）`,
			'判定：神后（子）加四仲（子午卯酉）',
		]);
	}
	if(isYutangshi){
		add('yutangshi', [
			`天盘大吉（丑）加临地盘：${yutangDown || '—'}（四仲）`,
			'判定：大吉（丑）加四仲（子午卯酉）',
		]);
	}
	const douBaseBranch = context.upDownMap ? (context.upDownMap['辰'] || '') : '';
	const douBaseType = getMengZhongJiType(douBaseBranch);
	if(douBaseType === 'meng'){
		add('doumeng', [
			`斗罡加临：辰临${douBaseBranch || '—'}（孟）`,
		]);
	}
	if(douBaseType === 'zhong'){
		add('douzhong', [
			`斗罡加临：辰临${douBaseBranch || '—'}（仲）`,
		]);
	}
	if(douBaseType === 'ji'){
		add('douji', [
			`斗罡加临：辰临${douBaseBranch || '—'}（季）`,
		]);
	}
	XIAO_JU_ALWAYS_REFERENCE_KEYS.forEach((key)=>{
		if(!added[key]){
			add(key, [
				'参考常驻：此局按局义作长期参照，不以单一局式硬触发。',
			], {
				source: '参考常驻',
			});
		}
	});

	return refs.sort((a, b)=>{
		const pa = Number.isFinite(a.priority) ? a.priority : 0;
		const pb = Number.isFinite(b.priority) ? b.priority : 0;
		return pb - pa;
	});
}

function buildLiuRengReferenceBundle(liureng, chartObj, guirengType, runyear, castOverride, extraOpts){
	const context = buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride, extraOpts);
	const dage = matchDaGeReferences(context);
	const xiaoju = matchXiaoJuReferences(context);
	const overview = matchLiuRengOverviewReferences(context);
	return {
		context,
		layout: context.layout,
		keData: context.keData,
		sanChuan: context.sanChuan,
		dage,
		xiaoju,
		overview,
	};
}

function appendReferenceSnapshotSection(lines, title, refs, type = 'common'){
	lines.push(`[${title}]`);
	if(!refs || refs.length === 0){
		lines.push('无');
		lines.push('');
		return;
	}
	refs.forEach((item, idx)=>{
		lines.push(`${idx + 1}. ${item.name}`);
		const docText = buildReferenceDocumentText(item, type);
		if(docText){
			docText.split('\n').forEach((line)=>{
				lines.push(line);
			});
		}
		if(item.evidence && item.evidence.length){
			lines.push(`依据：${item.evidence.join('；')}`);
		}
		lines.push('');
	});
}

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
const YUE_JIANG_METHODS = [
	{ key: 'zhongqi', name: '中气过宫（默认）' },
	{ key: 'jieqi', name: '节气换将' },
	{ key: 'richan', name: '太阳过宫·日躔（含岁差）' },
];
const FEN_ZHOU_YE_METHODS = [
	{ key: 'chenhun', name: '晨昏分昼夜（默认）' },
	{ key: 'maoyou', name: '卯酉分昼夜' },
	{ key: 'yinshen', name: '寅申分昼夜' },
];
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
function computeFenZhouYe(fenZhouYe, chartObj){
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
function liurengChouBranch(yueEff, chou){
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
	const isDiurnal = computeFenZhouYe(fenZhouYe, chartObj);
	// 涉害取舍流派(默认全 app=仅下贼上,零回归);非默认时即便其余皆默认也须产出 override 携 seHaiOpts。
	const seHaiOpts = {
		method: opts.seHaiMethod || 'app',
		boundary: opts.seHaiBoundary || 'app',
		shiRuKe: !!opts.shiRuKe,
	};
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

function getAppliedBirth(state){
	if(state && state.calcBirth){
		return state.calcBirth;
	}
	return state ? state.birth : null;
}

// 六壬 本命支(命主出生年支,按公历年取年支) + 行年支 —— 第九~十二客 / 本命·行年加时 用;缺则空串(computeQiXY 退回默认)。
function liurengBenmingXingnian(birth, runyear){
	const by = getSolarYearFromField(birth && birth.date ? birth.date : null);
	const benmingZhi = Number.isFinite(by) ? (LRConst.ZiList[(((by - 4) % 12) + 12) % 12] || '') : '';
	const xingnianZhi = extractSingleBranch(runyear && runyear.year ? runyear.year : '');
	return { benmingZhi, xingnianZhi };
}

function clonePlain(obj){
	if(obj === undefined || obj === null){
		return obj;
	}
	try{
		return JSON.parse(JSON.stringify(obj));
	}catch(e){
		return obj;
	}
}

function buildCacheKey(obj){
	try{
		return JSON.stringify(obj || {});
	}catch(e){
		return '';
	}
}

function pushCache(map, key, val, max = 96){
	if(!map || !key || val === undefined || val === null){
		return;
	}
	if(map.has(key)){
		map.delete(key);
	}
	map.set(key, val);
	if(map.size > max){
		const first = map.keys().next().value;
		if(first){
			map.delete(first);
		}
	}
}

export function buildKeData(layout, chartObj){
	const result = {
		raw: [],
		lines: [],
	};
	if(!layout || !chartObj || !chartObj.nongli || !chartObj.nongli.dayGanZi){
		return result;
	}
	const dayGanZi = chartObj.nongli.dayGanZi;
	const daygan = dayGanZi.substr(0, 1);
	const dayzi = dayGanZi.substr(1, 1);

	const idx1 = layout.downZi.indexOf(LRConst.GanJiZi[daygan]);
	if(idx1 < 0){
		return result;
	}
	const ke1zi = layout.upZi[idx1];
	const ke1 = [layout.houseTianJiang[idx1], ke1zi, daygan];

	const idx2 = layout.downZi.indexOf(ke1zi);
	const ke2zi = idx2 >= 0 ? layout.upZi[idx2] : '';
	const ke2 = [idx2 >= 0 ? layout.houseTianJiang[idx2] : '', ke2zi, ke1zi];

	const idx3 = layout.downZi.indexOf(dayzi);
	const ke3zi = idx3 >= 0 ? layout.upZi[idx3] : '';
	const ke3 = [idx3 >= 0 ? layout.houseTianJiang[idx3] : '', ke3zi, dayzi];

	const idx4 = layout.downZi.indexOf(ke3zi);
	const ke4zi = idx4 >= 0 ? layout.upZi[idx4] : '';
	const ke4 = [idx4 >= 0 ? layout.houseTianJiang[idx4] : '', ke4zi, ke3zi];

	const all = [ke1, ke2, ke3, ke4];
	const names = ['一课', '二课', '三课', '四课'];
	all.forEach((item, idx)=>{
		result.lines.push(`${names[idx]}：地盘=${item[2]}，天盘=${item[1]}，贵神=${item[0]}`);
	});
	result.raw = all;
	return result;
}

export function buildSanChuanData(layout, keRaw, chartObj, castOverride){
	if(!layout || !keRaw || keRaw.length !== 4 || !chartObj || !chartObj.nongli){
		return null;
	}
	try{
		const helper = new ChuangChart({
			owner: null,
			chartObj: chartObj,
			nongli: chartObj.nongli,
			ke: keRaw,
			seHaiOpts: castOverride ? castOverride.seHaiOpts : null,
			liuRengChart: {
				upZi: layout.upZi,
				downZi: layout.downZi,
				houseTianJiang: layout.houseTianJiang,
			},
			x: 0,
			y: 0,
			width: 0,
			height: 0,
		});
		helper.genCuangs();
		return helper.cuangs || null;
	}catch(e){
		return null;
	}
}

// ---- AI 快照·段内容行 builder(纯函数,导出供证明测试)：段头 [X] 仍由 buildLiuRengSnapshotText 内联推入 ----
// GFM 表化(段内排版,值零变化):事实 token 与旧「行式」逐字同,仅列结构化,fact-multiset 证明见
// liurengSnapshotTables.test.js。空值 cell 统一 '—'(旧式无空值路径的沿用原字面,如 '无')。
// [十二地盘/十二天盘/十二贵神对应] 内容行 → | 序 | 地盘 | 天盘 | 贵神 |。
export function buildLiuRengPanRows(layout){
	const rows = [];
	rows.push('| 序 | 地盘 | 天盘 | 贵神 |');
	rows.push('| --- | --- | --- | --- |');
	for(let i=0; i<12; i++){
		rows.push(`| ${i + 1} | ${layout.downZi[i] || '—'} | ${layout.upZi[i] || '—'} | ${layout.houseTianJiang[i] || '—'} |`);
	}
	return rows;
}

// [三传] 三行内容(课式行不在此,仍内联)→ | 传 | 干支 | 六亲 | 贵神 |;缺项沿用旧字面 '无'。
export function buildLiuRengSanChuanRows(sanChuan){
	const rows = [];
	rows.push('| 传 | 干支 | 六亲 | 贵神 |');
	rows.push('| --- | --- | --- | --- |');
	const names = ['初传', '中传', '末传'];
	for(let i=0; i<3; i++){
		const gz = sanChuan.cuang && sanChuan.cuang[i] ? sanChuan.cuang[i] : '无';
		const lq = sanChuan.liuQin && sanChuan.liuQin[i] ? sanChuan.liuQin[i] : '无';
		const gs = sanChuan.tianJiang && sanChuan.tianJiang[i] ? sanChuan.tianJiang[i] : '无';
		rows.push(`| ${names[i]} | ${gz} | ${lq} | ${gs} |`);
	}
	return rows;
}

// [岁煞] 内容行(LRConst.TaiSui 七煞序)→ | 神煞 | 值 |;缺值 fmtValue 已产 '无'。
export function buildLiuRengSuiShaRows(yearGods){
	const rows = [];
	rows.push('| 神煞 | 值 |');
	rows.push('| --- | --- |');
	LRConst.TaiSui.forEach((name)=>{
		rows.push(`| ${name} | ${fmtValue(yearGods[name])} |`);
	});
	return rows;
}

// [十二长生] 内容行(所选五行 × 十二位)→ | 长生位 | 地支 |。
export function buildLiuRengZhangShengRows(zhangshengElem){
	const rows = [];
	rows.push('| 长生位 | 地支 |');
	rows.push('| --- | --- |');
	ZSList.forEach((item)=>{
		const key = `${zhangshengElem}_${item}`;
		rows.push(`| ${item} | ${fmtValue(ZhangSheng.wxphase[key])} |`);
	});
	return rows;
}

export function buildLiuRengSnapshotText(params, liureng, runyear, chartObj, guirengType, zhangshengElem, gender, castOpts){
	const lines = [];
	const _castOpts = castOpts || {};
	const nongli = liureng && liureng.nongli ? liureng.nongli : (chartObj && chartObj.nongli ? chartObj.nongli : {});
	const castOverride = buildLiuRengCastOverride(chartObj, _castOpts);
	const refs = buildLiuRengReferenceBundle(liureng, chartObj, guirengType, runyear, castOverride, { benMingBranch: _castOpts.benmingZhi });
	const layout = refs.layout;
	const panStyle = refs && refs.context ? refs.context.panStyle : null;
	const keData = refs.keData;
	const sanChuan = refs.sanChuan;
	const xingbie = `${gender}` === '1' ? '男' : '女';

	lines.push('[起盘信息]');
	if(params){
		lines.push(`日期：${params.date} ${params.time}`);
		lines.push(`时区：${params.zone}`);
		lines.push(`经纬度：${params.lon} ${params.lat}`);
	}
	if(nongli && nongli.birth){
		lines.push(`真太阳时：${nongli.birth}`);
	}
	if(liureng && liureng.fourColumns){
		const cols = liureng.fourColumns;
		lines.push(`四柱：${fmtValue(cols.year && cols.year.ganzi)}年 ${fmtValue(cols.month && cols.month.ganzi)}月 ${fmtValue(cols.day && cols.day.ganzi)}日 ${fmtValue(cols.time && cols.time.ganzi)}时`);
	}
	lines.push(`贵人体系：${['六壬法贵人', '遁甲法贵人', '星占法贵人', '甲戊兼牛羊', '干合阳阴贵'][guirengType] || '星占法贵人'}`);
	lines.push(`起课法：${(QI_METHODS.find((m)=>m.key === (_castOpts.castMethod || 'zheng')) || QI_METHODS[0]).name}`);
	if(_castOpts.castMethod === 'xuanshi' && _castOpts.xuanShiZhi){ lines.push(`选时：${_castOpts.xuanShiZhi}时`); }
	if((_castOpts.castMethod === 'yanshu' || _castOpts.castMethod === 'baoshu') && (_castOpts.yanShuNum || _castOpts.yanShuNum === 0)){ lines.push(`${_castOpts.castMethod === 'baoshu' ? '报数/端法(÷12定支)' : '演数'}：${_castOpts.yanShuNum}`); }
	lines.push(`换将：${(YUE_JIANG_METHODS.find((m)=>m.key === (_castOpts.yueJiangMethod || 'zhongqi')) || YUE_JIANG_METHODS[0]).name}`);
	lines.push(`分昼夜：${(FEN_ZHOU_YE_METHODS.find((m)=>m.key === (_castOpts.fenZhouYe || 'chenhun')) || FEN_ZHOU_YE_METHODS[0]).name}`);
	if((_castOpts.seHaiMethod && _castOpts.seHaiMethod !== 'app') || (_castOpts.seHaiBoundary && _castOpts.seHaiBoundary !== 'app') || _castOpts.shiRuKe){
		const _sm = { app: '仅下贼上(单向取)', standard: '标准深浅两向', mengzhongji: '直取孟仲季' }[_castOpts.seHaiMethod || 'app'];
		const _sb = { app: '计起点不计本家', both: '两端皆计', neither: '皆不计' }[_castOpts.seHaiBoundary || 'app'];
		lines.push(`涉害取舍：${_sm}·${_sb}${_castOpts.shiRuKe ? '·始入课单列(十法)' : ''}`);
	}
	lines.push(`十二长生五行：${fmtValue(zhangshengElem)}`);
	lines.push(`十二盘式：${fmtValue(panStyle && panStyle.name ? panStyle.name : '')}`);
	lines.push(`问测人性别：${xingbie}`);
	lines.push('');

	lines.push('[十二盘式]');
	if(panStyle && panStyle.name){
		lines.push(`盘式：${panStyle.name}`);
		lines.push(`月将：${fmtValue(panStyle.yueBranch)}；占时：${fmtValue(panStyle.timeBranch)}；位序：${fmtValue(panStyle.distanceLabel)}`);
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[十二地盘/十二天盘/十二贵神对应]');
	if(layout){
		buildLiuRengPanRows(layout).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[四课]');
	if(keData.lines.length){
		keData.lines.forEach((line)=>lines.push(line));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[三传]');
	if(sanChuan){
		lines.push(`课式：${fmtValue(sanChuan.name)}`);
		buildLiuRengSanChuanRows(sanChuan).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[行年]');
	if(runyear){
		lines.push(`行年干支：${fmtValue(runyear.year)}`);
		lines.push(`年龄：${fmtValue(runyear.age)}岁`);
		lines.push(`性别：${xingbie}`);
	}else{
		lines.push('无');
	}
	lines.push('');

	appendMapSection(lines, '旬日', liureng ? liureng.xun : null);
	appendMapSection(lines, '旺衰', liureng ? liureng.season : null);
	appendMapSection(lines, '基础神煞', liureng ? liureng.gods : null);
	appendMapSection(lines, '干煞', liureng ? liureng.godsGan : null);
	appendMapSection(lines, '月煞', liureng ? liureng.godsMonth : null);
	appendMapSection(lines, '支煞', liureng ? liureng.godsZi : null);

	lines.push('[岁煞]');
	const yearGods = liureng && liureng.godsYear ? liureng.godsYear.taisui1 : null;
	if(yearGods){
		buildLiuRengSuiShaRows(yearGods).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[十二长生]');
	if(zhangshengElem){
		buildLiuRengZhangShengRows(zhangshengElem).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	appendReferenceSnapshotSection(lines, '大格', refs.dage, 'dage');
	const xiaojuAllRefs = Array.isArray(refs.xiaoju) ? refs.xiaoju : [];
	const xiaojuMainRefs = xiaojuAllRefs.filter((item)=>!XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const xiaojuReferenceRefs = xiaojuAllRefs.filter((item)=>XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	appendReferenceSnapshotSection(lines, '小局', xiaojuMainRefs, 'xiaoju');
	appendReferenceSnapshotSection(lines, '参考', xiaojuReferenceRefs, 'xiaoju');
	lines.push('[概览]');
	const overviewRefs = Array.isArray(refs.overview) ? refs.overview : [];
	if(overviewRefs.length){
		overviewRefs.forEach((item, idx)=>{
			const groupName = item.group === 'laiyi' ? '天将发用来意诀' : '天将杂主吉凶';
			lines.push(`${idx + 1}. ${groupName} · ${item.name}`);
			const docText = buildOverviewReferenceText(item);
			if(docText){
				docText.split('\n').forEach((line)=>{
					lines.push(line);
				});
			}
			if(item.evidence && item.evidence.length){
				lines.push(`依据：${item.evidence.join('；')}`);
			}
			lines.push('');
		});
	}else{
		lines.push('无');
		lines.push('');
	}
	const _ctx = refs && refs.context ? refs.context : null;
	if(_ctx){
		const shenSha = computeFrontendShenSha(_ctx.dayGan, _ctx.dayZhi, _ctx.courseBranches);
		lines.push('[常用神煞]');
		if(shenSha.length){
			shenSha.forEach((s)=>lines.push(`${s.name}：${s.branch}${s.inCourse ? '（入课传）' : ''}（${s.brief}）`));
		}else{
			lines.push('无');
		}
		lines.push('');

		const yearSS = computeYearShenSha(_ctx.yearBranch, _castOpts.yearShenShaSort || 'sanyuan', _ctx.courseBranches);
		const monthSS = computeMonthShenSha(_ctx.monthBranch, _ctx.courseBranches);
		if(yearSS.length || monthSS.length){
			// 段头独占一行(段头卫生:parseSectionTitleLine 仅认整行 [X]);年神序说明移正文行,否则段头带正文 → 认不出 → 整段并入上一段、且导出设置勾不到。
			lines.push('[年月神煞]');
			lines.push(`（年神＝${(_castOpts.yearShenShaSort === 'suigui') ? '太岁排轮' : '四利三元序'}）`);
			yearSS.concat(monthSS).forEach((s)=>lines.push(`${s.name}：${s.branch}${s.inCourse ? '（入课传）' : ''}`));
			lines.push('');
		}
		const jcS = detectJianChuan(_ctx.sanChuanBranches);
		if(jcS){ lines.push('[课体结构]'); lines.push(`${jcS.name}（${jcS.kind}${jcS.wuxing ? '·' + jcS.wuxing : ''}${jcS.dir ? '·' + jcS.dir + '间' : ''}）：${jcS.text}`); lines.push(''); }
		const _ws = (_ctx.sanChuanBranches || []).map((z, i) => { const wx = LRConst.GanZiWuXing[`${z || ''}`.trim().substring(0,1)] || ''; const w = liurengWangXiang(wx, _ctx.monthBranch, _castOpts.tuWangShuai); return w ? `${['初','中','末'][i]}传${z}${wx}${w}` : ''; }).filter(Boolean);
		if(_ws.length){ lines.push('[三传旺衰]'); lines.push(`${_ws.join('、')}`); lines.push(''); }
		const _kw = (_ctx.xunKongBranches || []).map((z) => { const wx = LRConst.GanZiWuXing[`${z||''}`.trim().substring(0,1)] || ''; const j = judgeKongWang(wx, _ctx.monthBranch, _castOpts.tuWangShuai); return j ? `${z}${wx}${j.kind}(${j.ws})` : ''; }).filter(Boolean);
		if(_kw.length){ lines.push('[空亡真假]'); lines.push(`${_kw.join('、')}`); lines.push(''); }
		const _kloc = analyzeKongLocations(_ctx);
		if(_kloc.hits.length){ lines.push('[旬空落点]'); lines.push(`${_kloc.hits.map((h)=>`${h.pos}${h.branch}空（${h.note}）`).join('；')}${_kloc.allSanChuanKong ? '；三传全空，守干上旺禄勿动' : ''}`); lines.push(''); }
		if(_kloc.xianKong.length){ lines.push('[陷空]'); lines.push(`${_kloc.xianKong.map((x)=>`${x.god}临地盘${x.seat}`).join('、')}（落于空地、虚而不实）`); lines.push(''); }
		const _dun = analyzeDunGan(_ctx);
		if(_dun.length){ lines.push('[遁干特殊]'); lines.push(`${_dun.map((d)=>`${d.pos}${d.branch}${d.gan ? '遁' + d.gan : ''}${d.flags.length ? '（' + d.flags.join('、') + '）' : ''}：${d.note}`).join('；')}`); lines.push(''); }
		const _nm = analyzeNianMing(_ctx);
		if(_nm.length){ lines.push('[年命上神]'); lines.push(`${_nm.map((n)=>`${n.label}${n.branch}——${n.note}`).join('；')}`); lines.push(''); }
		const bifaHits = matchBiFa(_ctx);
		lines.push('[毕法（已命中）]');
		lines.push('（以下为机械命中之断诀，烈度须合时令旺衰、年命制化，非定数）');
		if(bifaHits.length){
			bifaHits.forEach((b)=>{
				lines.push(`${b.no}. ${b.name}：${b.verse}`);
				lines.push(`释：${b.explain}`);
				if(b.evidence && b.evidence.length){ lines.push(`依据：${b.evidence.join('；')}`); }
			});
		}else{
			lines.push('无（本盘未机械命中可判定之毕法）');
		}
		lines.push('');

		const zhanKey = _castOpts.zhanCategory || 'general';
		if(zhanKey && zhanKey !== 'general' && ZHANDUAN_DOC[zhanKey]){
			const zd = ZHANDUAN_DOC[zhanKey];
			lines.push('[占断向导]');
			lines.push(`占事：${zd.name}`);
			lines.push(`主用神：${(zd.mainYong || []).map((y)=>`${y.role}=${y.mean}`).join('；')}`);
			const yongLuo = [];
			if(_ctx.ke1Up){ yongLuo.push(`日干上神=${_ctx.ke1Up}`); }
			if(_ctx.ke3Up){ yongLuo.push(`日支上神=${_ctx.ke3Up}`); }
			if(_ctx.runYearBranch){ yongLuo.push(`年命上神位=${_ctx.runYearBranch}`); }
			if(yongLuo.length){ lines.push(`用神落点：${yongLuo.join('；')}`); }
			const godValues = _ctx.branchGodMap ? Object.keys(_ctx.branchGodMap).map((k)=>_ctx.branchGodMap[k]) : [];
			const present = (zd.keyJiang || []).filter((j)=>godValues.indexOf(j) >= 0);
			const absent = (zd.keyJiang || []).filter((j)=>present.indexOf(j) < 0);
			lines.push(`关键神将：现=${present.join('、') || '—'}；缺=${absent.join('、') || '—'}`);
			lines.push(`宜：${(zd.favor || []).join('；')}`);
			lines.push(`忌：${(zd.avoid || []).join('；')}`);
			lines.push(`三传提示：${zd.sanChuanTip || ''}`);
			lines.push('');
		}

		// [取象] doctrine 段(默认关段:builder 恒产,导出层按设置控)：与右栏「取象」卡同源 buildXiangContext,
		// 只导本盘四课三传在位地支的 类象/五行/方位/六亲/刑冲合害/长生旺衰 条目(非全库十二支),象意原文零改写。
		const xiangBranches = Array.isArray(_ctx.courseBranches) ? _ctx.courseBranches : [];
		const xiangLines = [];
		xiangBranches.forEach((z)=>{
			const cx = buildXiangContext(z, _ctx.dayGan, zhangshengElem);
			if(!cx){
				return;
			}
			// 在位标注(初/中/末传、N课上/下)——派生定位信息,便于 AI 对位取象。
			const roles = [];
			(_ctx.sanChuanBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${['初', '中', '末'][i] || ''}传`); } });
			(_ctx.keUpBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${i + 1}课上`); } });
			(_ctx.keDownBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${i + 1}课下`); } });
			xiangLines.push(`◆ ${cx.branch}${cx.shenName ? `（${cx.shenName}）` : ''}${roles.length ? `——${roles.join('、')}` : ''}`);
			const rowParts = [];
			if(cx.wuxing){ rowParts.push(`五行：${cx.wuxing}${cx.wuxingXiang ? `（${cx.wuxingXiang.keyword}）` : ''}`); }
			if(cx.direction){ rowParts.push(`方位：${cx.direction}`); }
			if(cx.liuqin){ rowParts.push(`六亲：${cx.liuqin}`); }
			if(cx.zhangsheng){ rowParts.push(`${cx.zhangshengElem}·长生：${cx.zhangsheng}`); }
			if(cx.yima){ rowParts.push(`驿马：${cx.yima}`); }
			if(rowParts.length){ xiangLines.push(rowParts.join('　')); }
			if(cx.symbol){ xiangLines.push(`类象：${cx.symbol}`); }
			if(cx.relations && cx.relations.length){ xiangLines.push(`刑冲合害：${cx.relations.join('　')}`); }
			if(cx.relationNotes && cx.relationNotes.length){ xiangLines.push(`断用：${cx.relationNotes.map((r)=>`${r.type}—${r.note}`).join('；')}`); }
			if(cx.wuxingXiang){ xiangLines.push(`五行取象：人物：${cx.wuxingXiang.person}；身体：${cx.wuxingXiang.body}；事：${cx.wuxingXiang.affair}`); }
		});
		if(xiangLines.length){
			lines.push('[取象]');
			lines.push('（本盘四课三传在位地支类象，供合盘断之）');
			xiangLines.forEach((l)=>lines.push(l));
			lines.push('');
		}
	}

	// [七政] 段(v44 硬缺修):七政 tab 整层此前显示了完全导不出——日月五星临宫/五行/度/逆行/月将
	// 是大六壬七政四余合参的独立断法层。值与 tab 网格同源(buildQiZhengItems);无星历数据不产段(零字节变化)。
	const qizhengItems = buildQiZhengItems(chartObj);
	if(qizhengItems.length){
		lines.push('[七政]');
		lines.push('| 七政 | 临支 | 五行 | 度数 | 逆行 | 备注 |');
		lines.push('| --- | --- | --- | --- | --- | --- |');
		qizhengItems.forEach((item)=>{
			const deg = item.deg != null ? `${item.deg.toFixed(0)}°` : '—';
			lines.push(`| ${item.name} | ${item.branch || '—'} | ${item.wx || '—'} | ${deg} | ${item.retro ? '逆' : '—'} | ${item.isYue ? '月将(太阳过宫)' : '—'} |`);
		});
		lines.push('');
	}

	return lines.join('\n').trim();
}
