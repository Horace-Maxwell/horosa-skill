import { Solar, LunarUtil } from 'lunar-javascript';
import { NaYin, SixtyJiaZi } from './ZWConst.js';
import { calcFourPillarShenSha } from './baziShenShaLocal.js';

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHIS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

const GAN_ELEMENT = {
	甲: 'Wood', 乙: 'Wood',
	丙: 'Fire', 丁: 'Fire',
	戊: 'Earth', 己: 'Earth',
	庚: 'Metal', 辛: 'Metal',
	壬: 'Water', 癸: 'Water',
};

const ZHI_ELEMENT = {
	寅: 'Wood', 卯: 'Wood',
	巳: 'Fire', 午: 'Fire',
	辰: 'Earth', 戌: 'Earth', 丑: 'Earth', 未: 'Earth',
	申: 'Metal', 酉: 'Metal',
	亥: 'Water', 子: 'Water',
};

const SHI_SHEN_SHORT = {
	比肩: '比',
	劫财: '劫',
	食神: '食',
	伤官: '伤',
	偏财: '才',
	正财: '财',
	七杀: '杀',
	正官: '官',
	偏印: '枭',
	正印: '印',
	日主: '日元',
};

const GAN_HE_RULES = [
	{ key: '甲己合土', cells: ['甲', '己'] },
	{ key: '乙庚合金', cells: ['乙', '庚'] },
	{ key: '丙辛合水', cells: ['丙', '辛'] },
	{ key: '丁壬合木', cells: ['丁', '壬'] },
	{ key: '戊癸合火', cells: ['戊', '癸'] },
];

const GAN_CONG_RULES = [
	{ key: '甲庚冲', cells: ['甲', '庚'] },
	{ key: '乙辛冲', cells: ['乙', '辛'] },
	{ key: '丙壬冲', cells: ['丙', '壬'] },
	{ key: '丁癸冲', cells: ['丁', '癸'] },
];

const ZHI_HE6_RULES = [
	{ key: '子丑合土', cells: ['子', '丑'] },
	{ key: '寅亥合木', cells: ['寅', '亥'] },
	{ key: '卯戌合火', cells: ['卯', '戌'] },
	{ key: '辰酉合金', cells: ['辰', '酉'] },
	{ key: '巳申合水', cells: ['巳', '申'] },
	{ key: '午未合土', cells: ['午', '未'] },
];

const ZHI_HE3_RULES = [
	{ key: '申子辰合水', cells: ['申', '子', '辰'] },
	{ key: '亥卯未合木', cells: ['亥', '卯', '未'] },
	{ key: '寅午戌合火', cells: ['寅', '午', '戌'] },
	{ key: '巳酉丑合金', cells: ['巳', '酉', '丑'] },
];

const ZHI_HUI_RULES = [
	{ key: '寅卯辰会木', cells: ['寅', '卯', '辰'] },
	{ key: '巳午未会火', cells: ['巳', '午', '未'] },
	{ key: '申酉戌会金', cells: ['申', '酉', '戌'] },
	{ key: '亥子丑会水', cells: ['亥', '子', '丑'] },
];

const ZHI_CONG_RULES = [
	{ key: '子午冲', cells: ['子', '午'] },
	{ key: '丑未冲', cells: ['丑', '未'] },
	{ key: '寅申冲', cells: ['寅', '申'] },
	{ key: '卯酉冲', cells: ['卯', '酉'] },
	{ key: '辰戌冲', cells: ['辰', '戌'] },
	{ key: '巳亥冲', cells: ['巳', '亥'] },
];

const ZHI_XING_RULES = [
	{ key: '寅巳申三刑', cells: ['寅', '巳', '申'] },
	{ key: '丑戌未三刑', cells: ['丑', '戌', '未'] },
	{ key: '子卯刑', cells: ['子', '卯'] },
	{ key: '辰辰自刑', cells: ['辰', '辰'] },
	{ key: '午午自刑', cells: ['午', '午'] },
	{ key: '酉酉自刑', cells: ['酉', '酉'] },
	{ key: '亥亥自刑', cells: ['亥', '亥'] },
];

const ZHI_CUAN_RULES = [
	{ key: '子未穿', cells: ['子', '未'] },
	{ key: '丑午穿', cells: ['丑', '午'] },
	{ key: '寅巳穿', cells: ['寅', '巳'] },
	{ key: '卯辰穿', cells: ['卯', '辰'] },
	{ key: '申亥穿', cells: ['申', '亥'] },
	{ key: '酉戌穿', cells: ['酉', '戌'] },
];

const ZHI_PO_RULES = [
	{ key: '子酉破', cells: ['子', '酉'] },
	{ key: '丑辰破', cells: ['丑', '辰'] },
	{ key: '寅亥破', cells: ['寅', '亥'] },
	{ key: '卯午破', cells: ['卯', '午'] },
	{ key: '巳申破', cells: ['巳', '申'] },
	{ key: '未戌破', cells: ['未', '戌'] },
];

const TRIGRAMS = {
	乾: { name: '乾', yao: [1, 1, 1] },
	兑: { name: '兑', yao: [1, 1, 0] },
	离: { name: '离', yao: [1, 0, 1] },
	震: { name: '震', yao: [1, 0, 0] },
	巽: { name: '巽', yao: [0, 1, 1] },
	坎: { name: '坎', yao: [0, 1, 0] },
	艮: { name: '艮', yao: [0, 0, 1] },
	坤: { name: '坤', yao: [0, 0, 0] },
};

const GAN_GUA = {
	甲: TRIGRAMS.乾, 乙: TRIGRAMS.坤, 丙: TRIGRAMS.离, 丁: TRIGRAMS.兑, 戊: TRIGRAMS.坎,
	己: TRIGRAMS.艮, 庚: TRIGRAMS.震, 辛: TRIGRAMS.巽, 壬: TRIGRAMS.乾, 癸: TRIGRAMS.坤,
};

const ZHI_GUA = {
	子: TRIGRAMS.坎, 丑: TRIGRAMS.艮, 寅: TRIGRAMS.震, 卯: TRIGRAMS.震, 辰: TRIGRAMS.巽, 巳: TRIGRAMS.离,
	午: TRIGRAMS.离, 未: TRIGRAMS.坤, 申: TRIGRAMS.兑, 酉: TRIGRAMS.兑, 戌: TRIGRAMS.乾, 亥: TRIGRAMS.坎,
};

function mod(num, base){
	return ((num % base) + base) % base;
}

function parseZoneHours(zone){
	if(zone === undefined || zone === null || zone === ''){
		return 8;
	}
	if(typeof zone === 'number'){
		return zone;
	}
	const text = `${zone}`;
	const match = text.match(/^([+-]?)(\d{1,2})(?::?(\d{2}))?/);
	if(match){
		const sign = match[1] === '-' ? -1 : 1;
		const hour = Number(match[2]);
		const minute = Number(match[3] || 0);
		return sign * (hour + minute / 60);
	}
	const n = Number(text);
	return Number.isFinite(n) ? n : 8;
}

function parseGeoDegrees(value, limit){
	if(value === undefined || value === null || value === ''){
		return null;
	}
	if(typeof value === 'number'){
		return Math.abs(value) <= limit ? value : null;
	}
	const text = `${value}`.trim().toLowerCase();
	const compass = text.match(/^(\d+(?:\.\d+)?)([ewns])(?:(\d+(?:\.\d+)?))?$/);
	if(compass){
		const deg = Number(compass[1]);
		const min = Number(compass[3] || 0);
		if(!Number.isFinite(deg) || !Number.isFinite(min)){
			return null;
		}
		const sign = compass[2] === 'w' || compass[2] === 's' ? -1 : 1;
		const result = sign * (deg + min / 60);
		return Math.abs(result) <= limit ? result : null;
	}
	const n = Number(text);
	return Number.isFinite(n) && Math.abs(n) <= limit ? n : null;
}

function parseDateTime(params){
	const [year, month, day] = `${params.date || ''}`.split('-').map((item)=>Number(item));
	const [hour, minute, second] = `${params.time || '00:00:00'}`.split(':').map((item)=>Number(item));
	return {
		year,
		month,
		day,
		hour: Number.isFinite(hour) ? hour : 0,
		minute: Number.isFinite(minute) ? minute : 0,
		second: Number.isFinite(second) ? second : 0,
	};
}

function dayOfYearUTC(date){
	const start = Date.UTC(date.getUTCFullYear(), 0, 1);
	return Math.floor((date.getTime() - start) / 86400000) + 1;
}

function equationOfTime(dayOfYear){
	const b = (360 / 365) * (dayOfYear - 81) * Math.PI / 180;
	return 9.87 * Math.sin(2 * b) - 7.53 * Math.cos(b) - 1.5 * Math.sin(b);
}

function applyApparentSolarTime(parts, params){
	if(Number(params.timeAlg) !== 0){
		return parts;
	}
	const lon = parseGeoDegrees(params.lon, 180);
	if(!Number.isFinite(lon)){
		return parts;
	}
	const zoneHours = parseZoneHours(params.zone);
	const wall = new Date(Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second));
	const utcForEot = new Date(wall.getTime() - zoneHours * 3600000);
	const ltcSeconds = (lon - zoneHours * 15) * 4 * 60;
	const eotSeconds = equationOfTime(dayOfYearUTC(utcForEot)) * 60;
	const adjusted = new Date(wall.getTime() + Math.round(ltcSeconds + eotSeconds) * 1000);
	return {
		year: adjusted.getUTCFullYear(),
		month: adjusted.getUTCMonth() + 1,
		day: adjusted.getUTCDate(),
		hour: adjusted.getUTCHours(),
		minute: adjusted.getUTCMinutes(),
		second: adjusted.getUTCSeconds(),
	};
}

function solarFromParts(parts){
	return Solar.fromYmdHms(parts.year, parts.month, parts.day, parts.hour, parts.minute, parts.second);
}

function shortShiShen(label){
	return SHI_SHEN_SHORT[label] || label || '';
}

function polarFromGan(gan){
	const idx = GANS.indexOf(gan);
	return idx >= 0 && idx % 2 === 0 ? 'Positive' : 'Negative';
}

function polarFromZhi(zhi){
	const idx = ZHIS.indexOf(zhi);
	return idx >= 0 && idx % 2 === 0 ? 'Positive' : 'Negative';
}

function emptyGods(){
	return {
		goodGods: [],
		neutralGods: [],
		badGods: [],
		taisuiGods: [],
	};
}

function makeStem(gan, relative){
	return {
		...emptyGods(),
		cell: gan || '',
		element: GAN_ELEMENT[gan] || '',
		polar: polarFromGan(gan),
		relative: shortShiShen(relative),
		gua: GAN_GUA[gan] || TRIGRAMS.乾,
	};
}

function makeBranch(zhi, relative){
	return {
		...emptyGods(),
		cell: zhi || '',
		element: ZHI_ELEMENT[zhi] || '',
		polar: polarFromZhi(zhi),
		relative: shortShiShen(relative),
		gua: ZHI_GUA[zhi] || TRIGRAMS.坤,
	};
}

function makeGua(gan, zhi){
	const up = GAN_GUA[gan] || TRIGRAMS.乾;
	const down = ZHI_GUA[zhi] || TRIGRAMS.坤;
	const yao = [...down.yao, ...up.yao];
	const name = `${up.name}${down.name}`;
	return {
		name,
		abrname: name,
		desc: '本地排盘',
		url: '#',
		yao,
	};
}

function makeStarChargerFromSolar(solar){
	if(!solar || !solar.getLunar){
		return null;
	}
	try{
		const lunar = solar.getLunar();
		const name = lunar && lunar.getXiu ? lunar.getXiu() : '';
		if(!name){
			return null;
		}
		const luck = lunar.getXiuLuck ? lunar.getXiuLuck() : '';
		const song = lunar.getXiuSong ? lunar.getXiuSong() : '';
		return {
			name,
			luck,
			event: [luck ? `${luck}宿` : '', song].filter(Boolean).join('。'),
		};
	}catch(e){
		return null;
	}
}

function safeSolarAtYear(year, baseSolar){
	const month = baseSolar && baseSolar.getMonth ? baseSolar.getMonth() : 7;
	const day = baseSolar && baseSolar.getDay ? baseSolar.getDay() : 1;
	for(let d = day; d >= 1; d--){
		try{
			return Solar.fromYmd(year, month, d);
		}catch(e){
			// Try the previous day for leap-day and month-edge cases.
		}
	}
	return Solar.fromYmd(year, 7, 1);
}

function makeRelationItem(pillar, zhu){
	const source = pillar || {};
	return {
		cell: source.cell || '',
		zhu: zhu || source.zhu || '',
		polar: source.polar,
		element: source.element,
		relative: source.relative,
	};
}

function collectRelationSources(four, part){
	const keys = [
		['year', '年'],
		['month', '月'],
		['day', '日'],
		['time', '时'],
		['tai', '胎'],
		['ming', '命'],
		['shen', '身'],
	];
	return keys.map(([key, label])=>{
		const item = four && four[key] ? four[key] : {};
		const node = part === 'stem' ? item.stem : item.branch;
		return makeRelationItem(node, label);
	}).filter((item)=>item.cell);
}

function relationMapByRules(items, rules, minUniqueCount){
	const result = {};
	rules.forEach((rule)=>{
		const matched = [];
		const requiredCount = {};
		rule.cells.forEach((cell)=>{
			requiredCount[cell] = (requiredCount[cell] || 0) + 1;
		});
		Object.keys(requiredCount).forEach((cell)=>{
			const found = items.filter((item)=>item.cell === cell);
			if(found.length >= requiredCount[cell]){
				matched.push(...found);
			}
		});
		const need = minUniqueCount || rule.cells.length;
		const matchedUniqueCount = Array.from(new Set(matched.map((item)=>item.cell))).length;
		const selfRule = Object.keys(requiredCount).length === 1 && rule.cells.length > 1;
		if((selfRule && matched.length >= rule.cells.length) || (!selfRule && matchedUniqueCount >= need)){
			result[rule.key] = matched;
		}
	});
	return result;
}

function buildStemBranchRelations(four){
	const stems = collectRelationSources(four, 'stem');
	const branches = collectRelationSources(four, 'branch');
	return {
		ganHe: relationMapByRules(stems, GAN_HE_RULES),
		ganCong: relationMapByRules(stems, GAN_CONG_RULES),
		ziHe6: relationMapByRules(branches, ZHI_HE6_RULES),
		ziHe3: relationMapByRules(branches, ZHI_HE3_RULES, 2),
		ziHui: relationMapByRules(branches, ZHI_HUI_RULES),
		ziXing: relationMapByRules(branches, ZHI_XING_RULES),
		ziCong: relationMapByRules(branches, ZHI_CONG_RULES),
		ziCuan: relationMapByRules(branches, ZHI_CUAN_RULES),
		ziPo: relationMapByRules(branches, ZHI_PO_RULES),
	};
}

function makePillar(label, ganzi, data){
	const gan = `${ganzi || ''}`.charAt(0);
	const zhi = `${ganzi || ''}`.charAt(1);
	const hidden = data.hideGan || [];
	const hiddenRel = data.hideRel || [];
	const gua64 = makeGua(gan, zhi);
	const huGua = makeGua(gan, zhi);
	return {
		...emptyGods(),
		zhu: label,
		ganzi,
		ganZhi: ganzi,
		stem: makeStem(gan, data.stemRel),
		branch: makeBranch(zhi, hiddenRel[0] || data.branchRel),
		stemInBranch: hidden.map((item, idx)=>makeStem(item, hiddenRel[idx])),
		naying: data.nayin || NaYin[ganzi] || '',
		nayingPhase: '',
		ganziPhase: data.diShi || '',
		xunEmpty: data.xunKong || '',
		zhiStarGod: { gua: '' },
		gua64,
		huGua,
		tongGua: makeGua(gan, zhi),
		huGuaUp: GAN_GUA[gan] || TRIGRAMS.乾,
		huGuaDown: ZHI_GUA[zhi] || TRIGRAMS.坤,
	};
}

function ganziAt(ganzi, delta){
	const idx = SixtyJiaZi.indexOf(ganzi);
	return SixtyJiaZi[mod((idx >= 0 ? idx : 0) + delta, 60)];
}

function pillarFromGanzi(label, ganzi, dayGan){
	const gan = `${ganzi || ''}`.charAt(0);
	const zhi = `${ganzi || ''}`.charAt(1);
	const hideGan = (LunarUtil.ZHI_HIDE_GAN && LunarUtil.ZHI_HIDE_GAN[zhi]) || [];
	const hideRel = hideGan.map((item)=>shortShiShen(LunarUtil.SHI_SHEN[`${dayGan}${item}`]));
	return makePillar(label, ganzi, {
		stemRel: shortShiShen(LunarUtil.SHI_SHEN[`${dayGan}${gan}`]),
		hideGan,
		hideRel,
		nayin: LunarUtil.NAYIN && LunarUtil.NAYIN[ganzi] ? LunarUtil.NAYIN[ganzi] : NaYin[ganzi],
		xunKong: LunarUtil.getXunKong ? LunarUtil.getXunKong(ganzi) : '',
	});
}

function buildFourColumns(eightChar){
	const dayGan = eightChar.getDayGan();
	const four = {
		year: makePillar('年', eightChar.getYear(), {
			stemRel: eightChar.getYearShiShenGan(),
			hideGan: eightChar.getYearHideGan(),
			hideRel: eightChar.getYearShiShenZhi(),
			nayin: eightChar.getYearNaYin(),
			diShi: eightChar.getYearDiShi(),
			xunKong: eightChar.getYearXunKong(),
		}),
		month: makePillar('月', eightChar.getMonth(), {
			stemRel: eightChar.getMonthShiShenGan(),
			hideGan: eightChar.getMonthHideGan(),
			hideRel: eightChar.getMonthShiShenZhi(),
			nayin: eightChar.getMonthNaYin(),
			diShi: eightChar.getMonthDiShi(),
			xunKong: eightChar.getMonthXunKong(),
		}),
		day: makePillar('日', eightChar.getDay(), {
			stemRel: '日主',
			hideGan: eightChar.getDayHideGan(),
			hideRel: eightChar.getDayShiShenZhi(),
			nayin: eightChar.getDayNaYin(),
			diShi: eightChar.getDayDiShi(),
			xunKong: eightChar.getDayXunKong(),
		}),
		time: makePillar('时', eightChar.getTime(), {
			stemRel: eightChar.getTimeShiShenGan(),
			hideGan: eightChar.getTimeHideGan(),
			hideRel: eightChar.getTimeShiShenZhi(),
			nayin: eightChar.getTimeNaYin(),
			diShi: eightChar.getTimeDiShi(),
			xunKong: eightChar.getTimeXunKong(),
		}),
		tai: pillarFromGanzi('胎', eightChar.getTaiYuan(), dayGan),
		ming: pillarFromGanzi('命', eightChar.getMingGong(), dayGan),
		shen: pillarFromGanzi('身', eightChar.getShenGong(), dayGan),
		ganHe: {},
		ganCong: {},
		ziHe6: {},
		ziHe3: {},
		ziHui: {},
		ziXing: {},
		ziCong: {},
		ziCuan: {},
		ziPo: {},
	};
	four.ming12 = {
		zhi: four.ming.branch.cell,
	};
	const shenSha = calcFourPillarShenSha(four);
		['year', 'month', 'day', 'time'].forEach((key)=>{
			if(four[key]){
				four[key].shenSha = shenSha[key] || [];
				four[key].neutralGods = four[key].shenSha;
			}
		});
		Object.assign(four, buildStemBranchRelations(four));
		return four;
	}

function flowMonthFromSolar(year, term, solar, dayGan){
	const lunar = solar.getLunar();
	const ganzi = lunar.getMonthInGanZhi();
	return {
		year,
		month: solar.getMonth(),
		day: solar.getDay(),
		term,
		date: solar.toYmd(),
		ganzi,
		ganzhi: ganzi,
		...pillarFromGanzi('月', ganzi, dayGan),
	};
}

function buildFlowMonths(liuNian, birthSolar, dayGan){
	const year = liuNian.getYear();
	let months = liuNian.getLiuYue();
	if(birthSolar && year === birthSolar.getYear()){
		months = months.filter((item)=>item.getIndex() + 1 >= birthSolar.getMonth());
	}
	const seen = {};
	const result = [];
	months.forEach((month, idx)=>{
		const seed = Solar.fromYmd(year, month.getIndex() + 1, 1);
		const jie = seed.getLunar().getNextJie(true);
		const term = jie.getName();
		if(month.getIndex() === 0 && term === '小寒'){
			return;
		}
		if(!seen[term]){
			seen[term] = true;
			result.push(flowMonthFromSolar(year, term, jie.getSolar(), dayGan));
		}
		if(idx === months.length - 1 && term === '大雪'){
			const nextSeed = Solar.fromYmd(year + 1, 1, 1);
			const nextJie = nextSeed.getLunar().getNextJie(true);
			result.push(flowMonthFromSolar(year + 1, nextJie.getName(), nextJie.getSolar(), dayGan));
		}
	});
	return result;
}

function buildDirection(yun, dayGan, birthSolar){
	return yun.getDaYun(10).slice(1).map((item)=>{
		const mainDirect = pillarFromGanzi('运', item.getGanZhi(), dayGan);
		return {
			age: item.getStartAge(),
			startYear: item.getStartYear(),
			endYear: item.getEndYear(),
			mainDirect,
			subDirect: item.getLiuNian().map((year)=>({
				year: year.getYear(),
				age: year.getAge(),
				index: year.getIndex(),
				flowMonths: buildFlowMonths(year, birthSolar, dayGan),
				starCharger: makeStarChargerFromSolar(safeSolarAtYear(year.getYear(), birthSolar)),
				...pillarFromGanzi('年', year.getGanZhi(), dayGan),
			})),
		};
	});
}

function buildMainDirection(yun, dayGan){
	return yun.getDaYun(10).map((item, idx)=>{
		const ganzi = item.getGanZhi();
		return {
			age: item.getStartAge(),
			startYear: item.getStartYear(),
			year: item.getStartYear(),
			ganzi,
			ganzhi: ganzi,
			index: idx,
			...(ganzi ? pillarFromGanzi('运', ganzi, dayGan) : {}),
		};
	});
}

function buildSmallDirection(yun, dayGan, birthSolar){
	return yun.getDaYun(10).flatMap((dayun)=>dayun.getXiaoYun()).map((item)=>{
		const year = item.getYear();
		const yearSolar = safeSolarAtYear(year, birthSolar);
		const yearLunar = yearSolar.getLunar();
		const yearGanzi = yearLunar.getYearInGanZhiByLiChun ? yearLunar.getYearInGanZhiByLiChun() : yearLunar.getYearInGanZhi();
		const direct = pillarFromGanzi('小', item.getGanZhi(), dayGan);
		const liunian = {
			year,
			age: item.getAge(),
			starCharger: makeStarChargerFromSolar(yearSolar),
			...pillarFromGanzi('年', yearGanzi, dayGan),
		};
		return {
			year,
			age: item.getAge(),
			ganzi: item.getGanZhi(),
			ganzhi: item.getGanZhi(),
			direct,
			yearGanzi: liunian,
			...direct,
		};
	});
}

function formatStartLuck(yun){
	return `出生后${yun.getStartYear()}年${yun.getStartMonth()}个月${yun.getStartDay()}天${yun.getStartHour ? yun.getStartHour() : 0}小时起运`;
}

function buildNongli(lunar, solar, apparentSolar){
	const prev = lunar.getPrevJieQi ? lunar.getPrevJieQi(false) : lunar.getPrevJie(false);
	const prevSolar = prev && prev.getSolar ? prev.getSolar() : null;
	let dayDiff = '';
	if(prevSolar && solar.subtract){
		dayDiff = `${prev.getName()}后第${Math.max(1, solar.subtract(prevSolar) + 1)}天`;
	}
	return {
		year: lunar.getYearInChinese(),
		month: `${lunar.getMonthInChinese()}月`,
		day: lunar.getDayInChinese(),
		leap: lunar.getMonth ? lunar.getMonth() < 0 : false,
		birth: apparentSolar.toYmdHms(),
		jieqi: prev && prev.getName ? prev.getName() : '',
		jiedelta: dayDiff,
		chef: '',
	};
}

export function buildLocalBaziResult(params){
	const rawParts = parseDateTime(params);
	if(!Number.isFinite(rawParts.year) || !Number.isFinite(rawParts.month) || !Number.isFinite(rawParts.day)){
		throw new Error('invalid bazi date');
	}
	const apparentParts = applyApparentSolarTime(rawParts, params || {});
	const solar = solarFromParts(apparentParts);
	const lunar = solar.getLunar();
	const eightChar = lunar.getEightChar();
	eightChar.setSect(1);
	const gender = Number(params.gender) === 0 ? 0 : 1;
	const yun = eightChar.getYun(gender);
	const dayGan = eightChar.getDayGan();
	const fourColumns = buildFourColumns(eightChar);
	const bazi = {
		gender: gender === 1 ? 'Male' : 'Female',
		nongli: buildNongli(lunar, solar, solar),
		fourColumns,
			gong12God: {},
			direction: buildDirection(yun, dayGan, solar),
			mainDirection: buildMainDirection(yun, dayGan),
			smallDirection: buildSmallDirection(yun, dayGan, solar),
		directTime: yun.getStartSolar().toYmdHms(),
		directInfo: formatStartLuck(yun),
		tiaohou: [],
		source: 'lunar-local',
	};
	// Always expose both the clock/direct input time and the true solar time,
	// independent of the selected timeAlg, so the UI can show both without the
	// displayed value jumping when the user toggles the algorithm (the pillar
	// calc above still follows timeAlg). Mirrors the Java backend (BaZi.java).
	if(bazi.nongli){
		try{
			bazi.nongli.clockTime = solarFromParts(rawParts).toYmdHms();
			bazi.nongli.solarTime = solarFromParts(applyApparentSolarTime(rawParts, { ...(params || {}), timeAlg: 0 })).toYmdHms();
		}catch(e){
			// keep going even if either time cannot be formatted for an edge-case date
		}
	}
	return {
		bazi,
		gender: bazi.gender,
		local: true,
	};
}

export default buildLocalBaziResult;
