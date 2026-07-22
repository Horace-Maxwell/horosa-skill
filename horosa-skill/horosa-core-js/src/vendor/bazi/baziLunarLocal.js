import { Solar, LunarUtil } from 'lunar-javascript';
import { isLunarJsYearReliable, lunarDomainNotice } from './lunarDomainGuard.js';
import { NaYin, SixtyJiaZi } from './ZWConst.js';
import { calcFourPillarShenSha } from './baziShenShaLocal.js';
import { computeWuxingStrength } from './baziWuxing.js';
import { computeFenYe } from './baziFenYe.js';
import { computeGejuYongShen } from './baziGejuYongShen.js';
import { computeMangPai } from './baziMangPai.js';
import { parseDateParts } from './dateStrSafe.js';

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHIS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

// 纳音长生：纳音五行在各地支的十二长生（子→亥序），供旧版柱细览（Zhu/FourZhu）显示「纳音·长生」。
// 与后端 wuxingphase.json「纳音{五行}_{支}」逐项一致（土从水土同长生）。纳音末字即其五行（如「天河水」→水）。
// 注：细盘「星运」= 日干十二长生、「自坐」= 本柱干自坐长生，均走 getSelfZuo，与此纳音长生无关。
const NAYIN_PHASE = {
	木: ['沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养', '长生'],
	火: ['胎', '养', '长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝'],
	土: ['帝旺', '衰', '病', '死', '墓', '绝', '胎', '养', '长生', '沐浴', '冠带', '临官'],
	金: ['死', '墓', '绝', '胎', '养', '长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病'],
	水: ['帝旺', '衰', '病', '死', '墓', '绝', '胎', '养', '长生', '沐浴', '冠带', '临官'],
};
function naYinPhase(naying, zhi){
	if(!naying || !zhi){ return ''; }
	const el = naying.charAt(naying.length - 1);
	const zi = ZHIS.indexOf(zhi);
	const row = NAYIN_PHASE[el];
	return (row && zi >= 0) ? row[zi] : '';
}

// 天干在地支的十二长生（阳干顺行、阴干逆行，
// offset 取 lunar CHANG_SHENG_OFFSET）。星运=日干vs各支；自坐=本柱干vs本柱支。
export function getSelfZuo(gan, zhi){
	if(!gan || !zhi){ return ''; }
	const sv = GANS.indexOf(gan) + 1; // 甲=1…癸=10
	const bv = ZHIS.indexOf(zhi) + 1; // 子=1…亥=12
	const off = LunarUtil.CHANG_SHENG_OFFSET && LunarUtil.CHANG_SHENG_OFFSET[gan];
	if(sv < 1 || bv < 1 || off === undefined){ return ''; }
	let i = off + (((sv - 1) % 2 === 0) ? (bv - 1) : -(bv - 1));
	i = ((i % 12) + 12) % 12;
	return (LunarUtil.CHANG_SHENG && LunarUtil.CHANG_SHENG[i]) || '';
}

// 死选项接线·phaseType（长生派别）覆盖四柱「星运」（日元十二长生 diShi）的起点。
//   现状（fallback）= lunar.js eightChar.getXxxDiShi()，其对戊=寅顺、己=酉逆（= Java「阳顺阴逆 yingyang」语义）。
//   据 Java 权威 wuxingphase.json 三派对照（HuoTu0/ShuiTu1/YingYang2）：
//     · phaseType=2 阳顺阴逆：戊寅顺/己酉逆 == lunar 现状 → 不覆盖（byte-perfect）。
//     · phaseType=0 火土同  ：本实现以 lunar 现状为 0 档基线（任务钉死「phaseType=0 不覆盖」，与 golden 锚定）→ 不覆盖。
//     · phaseType=1 水土同  ：土寄水，戊/己 长生同在「申」且顺行（off=4）→ 仅此档覆盖土日元四柱 diShi。
//   非土日元（非戊/己）任何档均不覆盖。覆盖时复刻 lunar.js _getDiShi 的 index 公式：index = off + (顺?+zhiIdx:-zhiIdx)。
const CHANG_SHENG_SEQ = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
// 水土同：戊/己 长生在申（zhiIdx 8）且顺行 → off=4（验证 申=(4+8)%12=0=长生）。复刻整列与 wuxingphase.json suitutong 戊/己 逐项一致。
const SHUITU_EARTH_OFFSET = 4;
export function resolveDiShiByPhaseType(dayGan, zhi, phaseType, fallback){
	// 仅水土同(1) + 土日元(戊/己) 覆盖；其余一律返回现状 fallback（byte-perfect）。
	if(Number(phaseType) !== 1 || (dayGan !== '戊' && dayGan !== '己')){
		return fallback;
	}
	const bv = ZHIS.indexOf(zhi);
	if(bv < 0){
		return fallback;
	}
	// 戊/己 在水土同均顺行（土寄水、阴阳同生），故恒用 +bv（不按干阴阳镜像）。
	const idx = ((SHUITU_EARTH_OFFSET + bv) % 12 + 12) % 12;
	return CHANG_SHENG_SEQ[idx] || fallback;
}

// 地支藏干 + 相对日干十神（供流年/大运列就地补算，与四柱同口径）。
export function hiddenStemsOf(zhi, dayGan){
	const list = (LunarUtil.ZHI_HIDE_GAN && LunarUtil.ZHI_HIDE_GAN[zhi]) || [];
	return list.map((g)=>({ cell: g, relative: shortShiShen(LunarUtil.SHI_SHEN[`${dayGan}${g}`]) }));
}
// 旬空（空亡）：按干支所在旬。
export function xunKongOf(ganzi){
	return (ganzi && LunarUtil.getXunKong ? LunarUtil.getXunKong(ganzi) : '') || '';
}

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
	const _dp = parseDateParts(`${params.date || ''}`) || {};
	const year = _dp.year, month = _dp.month, day = _dp.day;
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
	// timeAlg=0 真太阳时（经度差 + 均时差 EoT）；timeAlg=3 平太阳时（仅经度差，去 EoT）；其余不调整。
	const alg = Number(params.timeAlg);
	if(alg !== 0 && alg !== 3){
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
	const eotSeconds = alg === 0 ? equationOfTime(dayOfYearUTC(utcForEot)) * 60 : 0;
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

// 脱句柄版：按 (年, 出生月, 出生日) 安全取该公历年的 Solar（逐字等价 safeSolarAtYear）。
function safeSolarAtYearMD(year, birthMonth, birthDay){
	const month = Number.isFinite(birthMonth) ? birthMonth : 7;
	const day = Number.isFinite(birthDay) ? birthDay : 1;
	for(let d = day; d >= 1; d--){
		try{
			return Solar.fromYmd(year, month, d);
		}catch(e){
			// Try the previous day for leap-day and month-edge cases.
		}
	}
	return Solar.fromYmd(year, 7, 1);
}

function safeSolarAtYear(year, baseSolar){
	const month = baseSolar && baseSolar.getMonth ? baseSolar.getMonth() : 7;
	const day = baseSolar && baseSolar.getDay ? baseSolar.getDay() : 1;
	return safeSolarAtYearMD(year, month, day);
}

// 脱句柄版：按公历年补算「值年星宿」（28 宿），与 buildDirection/buildSmallDirection 内
// makeStarChargerFromSolar(safeSolarAtYear(year, birthSolar)) 逐字等价。供 starCharger 惰性化后
// legacy 消费端（MainDirection/SmallDirection/MDSYear）在 null 时按公历年 on-demand 补算。
export function buildStarChargerForYear(year, birthMonth, birthDay){
	if(!Number.isFinite(year)){
		return null;
	}
	return makeStarChargerFromSolar(safeSolarAtYearMD(year, birthMonth, birthDay));
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
		nayingPhase: naYinPhase(data.nayin || NaYin[ganzi], zhi),
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

// 用户拍板·v3 第二开关:
// 算「按今日干起子时」的 timeGan/timeZhi 返回; 如 lateZi=1 (默认 = lunar.js 现行) 或非晚子时 (hour!=23),
// 返回 null 让上游用 lunar.js 原始 eightChar.getTime()。
function computeOverrideTimeGan(eightChar, lateZiHourUseNextDay){
	if(lateZiHourUseNextDay !== 0 && lateZiHourUseNextDay !== '0' && lateZiHourUseNextDay !== false){
		return null; // 默认: 按 lunar.js Exact 行为(用次日干起), 不覆盖
	}
	try{
		const lunar = eightChar._p && eightChar._p.lunar;
		if(!lunar){
			return null;
		}
		const hour = lunar.getHour ? lunar.getHour() : null;
		if(hour !== 23){
			return null; // 仅在 hour∈[23,24) 即晚子时,时干起算才在两派间分歧
		}
		const timeZhiIdx = lunar.getTimeZhiIndex();
		const dayGanIdxToday = lunar.getDayGanIndexExact2(); // 今日干 idx (不进位)
		const timeGanIdx = (dayGanIdxToday % 5 * 2 + timeZhiIdx) % 10;
		return {
			gan: GANS[timeGanIdx],
			zhi: ZHIS[timeZhiIdx],
		};
	}catch(e){
		return null;
	}
}

// 命宫/身宫「子平数法」(对照表法, 八字大全 §4.4/§4.6, 与 bazi.py 逐字一致):
//   月序 m: 寅=1…丑=12(节气月); 时序 h: 子=1…亥=12; 命宫数=26−(m+h)(>12 则−12), 身宫基数=32。
//   命宫支/身宫支 = 数→地支; 天干 = 年干五虎遁推到该支当月取干。
//   与 lunar.js getMingGong/getShenGong(时支从寅起的「通行版」)并列为可选流派, 默认本法。
function computeMingShenShuFa(eightChar){
	const monthZhi = eightChar.getMonthZhi();
	const timeZhi = eightChar.getTimeZhi();
	const yearGan = eightChar.getYearGan();
	const mbi = ZHIS.indexOf(monthZhi);   // 子=0…亥=11
	const hbi = ZHIS.indexOf(timeZhi);
	const ystem = GANS.indexOf(yearGan);
	if(mbi < 0 || hbi < 0 || ystem < 0){
		return { ming: eightChar.getMingGong(), shen: eightChar.getShenGong() };
	}
	const yinStem = ((ystem % 5) * 2 + 2) % 10;       // 五虎遁: 寅月干
	const mNum = ((mbi - 2 + 12) % 12) + 1;           // 寅=1…丑=12
	const hNum = hbi + 1;                             // 子=1…亥=12
	let mg = 26 - (mNum + hNum);
	if(mg > 12){ mg -= 12; }
	const mgBranch = (mg + 1) % 12;
	const mgStem = (yinStem + ((mgBranch - 2 + 12) % 12)) % 10;
	let sg = 32 - (mNum + hNum);
	while(sg > 12){ sg -= 12; }
	while(sg < 1){ sg += 12; }
	const sgBranch = (sg + 1) % 12;
	const sgStem = (yinStem + ((sgBranch - 2 + 12) % 12)) % 10;
	return {
		ming: GANS[mgStem] + ZHIS[mgBranch],
		shen: GANS[sgStem] + ZHIS[sgBranch],
	};
}

function buildFourColumns(eightChar, opts){
	const dayGan = eightChar.getDayGan();
	// 用户拍板·v3 第二开关「晚子时·时柱起干模式」(独立于 after23NewDay 日柱开关):
	//   opts.lateZiHourUseNextDay=1 (默认, = lunar.js Exact 现行行为): 时干用次日日干起子时
	//   opts.lateZiHourUseNextDay=0: 时干用今日日干起子时 (hour==23 子时跨日,但起干用今日)
	// lunar.js EightChar.getTimeGan() 硬编码用 dayGanIndexExact(进位日干),
	// 所以 lateZi=0 时,我们必须自己算 time.gan 并重算下游 hideGan/shishen/nayin。
	let timeGanZhi = eightChar.getTime();
	let timeShiShenGan = eightChar.getTimeShiShenGan();
	let timeShiShenZhi = eightChar.getTimeShiShenZhi();
	let timeHideGan = eightChar.getTimeHideGan();
	let timeNaYin = eightChar.getTimeNaYin();
	let timeDiShi = eightChar.getTimeDiShi();
	let timeXunKong = eightChar.getTimeXunKong();
	const lateZiHourUseNextDay = opts && opts.lateZiHourUseNextDay !== undefined ? opts.lateZiHourUseNextDay : 1;
	const overrideTimeGan = computeOverrideTimeGan(eightChar, lateZiHourUseNextDay);
	if(overrideTimeGan){
		// 替换 time ganzi 的天干,zhi 保持(子时跨日,zhi 永远是子);
		// 重算 nayin / shishen(都是基于 timeGan + timeZhi 的纯函数计算)
		const newGanZhi = overrideTimeGan.gan + overrideTimeGan.zhi;
		timeGanZhi = newGanZhi;
		const newShiShenGanRaw = LunarUtil.SHI_SHEN && LunarUtil.SHI_SHEN[`${dayGan}${overrideTimeGan.gan}`];
		if(newShiShenGanRaw){
			timeShiShenGan = newShiShenGanRaw;
		}
		const newNaYin = (LunarUtil.NAYIN && LunarUtil.NAYIN[newGanZhi]) || (NaYin && NaYin[newGanZhi]);
		if(newNaYin){
			timeNaYin = newNaYin;
		}
		// hideGan/shishenZhi 仅由 zhi 决定(zhi 没变), diShi/xunKong 由 dayGan+zhi 决定(均不变), 故保持
	}
	// 命宫/身宫流派: 默认「通行版」(lunar.js 现行算法，与原星阙零回归); opts.minggongMethod==='shufa' 走子平数法对照表。
	const minggongMethod = (opts && opts.minggongMethod === 'shufa') ? 'shufa' : 'tongxing';
	let mingGanZhi = eightChar.getMingGong();
	let shenGanZhi = eightChar.getShenGong();
	if(minggongMethod === 'shufa'){
		const ms = computeMingShenShuFa(eightChar);
		mingGanZhi = ms.ming;
		shenGanZhi = ms.shen;
	}
	// 死选项接线·phaseType：四柱「星运」diShi（日元十二长生）经 resolveDiShiByPhaseType 覆盖。
	// 默认 0 / 非土日元 → 恒返回 lunar 原值（byte-perfect）；仅 phaseType=1 土日元（戊/己）改起点。
	const phaseType = opts && opts.phaseType !== undefined ? opts.phaseType : 0;
	const resolveDiShi = (zhi, fallback)=>resolveDiShiByPhaseType(dayGan, zhi, phaseType, fallback);
	const four = {
		year: makePillar('年', eightChar.getYear(), {
			stemRel: eightChar.getYearShiShenGan(),
			hideGan: eightChar.getYearHideGan(),
			hideRel: eightChar.getYearShiShenZhi(),
			nayin: eightChar.getYearNaYin(),
			diShi: resolveDiShi(`${eightChar.getYear() || ''}`.charAt(1), eightChar.getYearDiShi()),
			xunKong: eightChar.getYearXunKong(),
		}),
		month: makePillar('月', eightChar.getMonth(), {
			stemRel: eightChar.getMonthShiShenGan(),
			hideGan: eightChar.getMonthHideGan(),
			hideRel: eightChar.getMonthShiShenZhi(),
			nayin: eightChar.getMonthNaYin(),
			diShi: resolveDiShi(`${eightChar.getMonth() || ''}`.charAt(1), eightChar.getMonthDiShi()),
			xunKong: eightChar.getMonthXunKong(),
		}),
		day: makePillar('日', eightChar.getDay(), {
			stemRel: '日主',
			hideGan: eightChar.getDayHideGan(),
			hideRel: eightChar.getDayShiShenZhi(),
			nayin: eightChar.getDayNaYin(),
			diShi: resolveDiShi(`${eightChar.getDay() || ''}`.charAt(1), eightChar.getDayDiShi()),
			xunKong: eightChar.getDayXunKong(),
		}),
		time: makePillar('时', timeGanZhi, {
			stemRel: timeShiShenGan,
			hideGan: timeHideGan,
			hideRel: timeShiShenZhi,
			nayin: timeNaYin,
			diShi: resolveDiShi(`${timeGanZhi || ''}`.charAt(1), timeDiShi),
			xunKong: timeXunKong,
		}),
		tai: pillarFromGanzi('胎', eightChar.getTaiYuan(), dayGan),
		ming: pillarFromGanzi('命', mingGanZhi, dayGan),
		shen: pillarFromGanzi('身', shenGanZhi, dayGan),
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
	// 死选项接线·godKeyPos（神煞主位 年/日/年日）：默认 '年'。透传给逐柱神煞查法。
	const godKeyPos = (opts && (opts.godKeyPos === '日' || opts.godKeyPos === '年日')) ? opts.godKeyPos : '年';
	const shenSha = calcFourPillarShenSha(four, godKeyPos);
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

// 流日（批A）：枚举某公历 year-month 的全部日，逐日干支用 lunar.js 原生 getDayInGanZhi，
// 十神/纳音/空亡复用 pillarFromGanzi（与四柱同口径）。坏月/越界静默跳过，绝不抛。
function buildFlowDays(year, month, dayGan){
	if(!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12){
		return [];
	}
	// lunar.js Solar.fromYmd 不校验越界日（31 号也照存），故用公历 JS Date 取该月实际天数。
	const daysInMonth = new Date(year, month, 0).getDate();
	if(!Number.isFinite(daysInMonth) || daysInMonth < 1){
		return [];
	}
	const out = [];
	for(let d = 1; d <= daysInMonth; d++){
		let solar = null;
		try{
			solar = Solar.fromYmd(year, month, d);
		}catch(e){
			continue;
		}
		if(!solar){
			continue;
		}
		const ganzi = solar.getLunar().getDayInGanZhi();
		out.push({
			year,
			month,
			day: d,
			date: solar.toYmd(),
			ganzi,
			ganzhi: ganzi,
			...pillarFromGanzi('日', ganzi, dayGan),
		});
	}
	return out;
}

// 流时（批A）：枚举某公历 year-month-day 的 12 时辰（子起，0–11），时干支用 lunar.js 原生 getTimeInGanZhi。
// 每个时辰取该时辰中点小时（子=0,丑=2,…亥=22）；十神/纳音/空亡复用 pillarFromGanzi。
function buildFlowHours(year, month, day, dayGan){
	if(!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)){
		return [];
	}
	const out = [];
	for(let h = 0; h < 12; h++){
		const hour = (h * 2) % 24; // 子=0,丑=2,…,亥=22
		let solar = null;
		try{
			solar = Solar.fromYmdHms(year, month, day, hour, 0, 0);
		}catch(e){
			break;
		}
		if(!solar){
			break;
		}
		const ganzi = solar.getLunar().getTimeInGanZhi();
		out.push({
			year,
			month,
			day,
			hourIdx: h,
			hour,
			ganzi,
			ganzhi: ganzi,
			...pillarFromGanzi('时', ganzi, dayGan),
		});
	}
	return out;
}

// 脱离 liuNian 句柄、纯按公历年算某流年的流月列表（与 buildFlowMonths 逐字等价）。
// 依据：lunar.js LiuNian.getLiuYue() 恒返回 i=0..11 共 12 项、getIndex()===i，且整段逻辑只用
// liuNian.getYear()（=公历年）与 month.getIndex()（=0..11）；故用 0..11 直接替代即可逐字复刻。
// 供「惰性化后非当前大运流年 flowMonths=null」的消费端按公历年 on-demand 补算。
export function buildFlowMonthsByYear(year, birthSolar, dayGan){
	if(!Number.isFinite(year)){
		return [];
	}
	let monthIdxs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
	if(birthSolar && year === birthSolar.getYear()){
		monthIdxs = monthIdxs.filter((mi)=>mi + 1 >= birthSolar.getMonth());
	}
	const seen = {};
	const result = [];
	monthIdxs.forEach((monthIdx, idx)=>{
		const seed = Solar.fromYmd(year, monthIdx + 1, 1);
		const jie = seed.getLunar().getNextJie(true);
		const term = jie.getName();
		if(monthIdx === 0 && term === '小寒'){
			return;
		}
		if(!seen[term]){
			seen[term] = true;
			result.push(flowMonthFromSolar(year, term, jie.getSolar(), dayGan));
		}
		if(idx === monthIdxs.length - 1 && term === '大雪'){
			const nextSeed = Solar.fromYmd(year + 1, 1, 1);
			const nextJie = nextSeed.getLunar().getNextJie(true);
			result.push(flowMonthFromSolar(year + 1, nextJie.getName(), nextJie.getSolar(), dayGan));
		}
	});
	return result;
}

function buildFlowMonths(liuNian, birthSolar, dayGan){
	return buildFlowMonthsByYear(liuNian.getYear(), birthSolar, dayGan);
}

// perf：daYunList 由上层 buildLocalBaziResult 算一次（yun.getDaYun(10)）后传入三个 builder，
// 避免每个 builder 各自重复调 getDaYun(10)（之前 3 次，每次都重算大运表，是热路径冗余）。逐字等价。
//
// perf · flowMonths/starCharger 惰性化：旧版对每个大运的每个流年都 eager 算 buildFlowMonths（节气查找）
// 与 makeStarChargerFromSolar（getXiu 28 宿天文计算 ~1.6ms），合计上百次重活；而现代默认 UI 只有
// 「当前公历年所在大运」会被展开看流月、且现代 UI 不读 starCharger（仅 legacy MainDirection/SmallDirection/
// MDSYear 读）。改为只对「当前公历年所在大运」eager 算，其余大运的流年 flowMonths=null / starCharger=null；
// 消费端 null 时按公历年 on-demand 补算（buildFlowMonthsByYear / buildStarChargerForYear，逐字等价）。
function buildDirection(daYunList, dayGan, birthSolar){
	const currentYear = new Date().getFullYear();
	return daYunList.slice(1).map((item)=>{
		const mainDirect = pillarFromGanzi('运', item.getGanZhi(), dayGan);
		const startYear = item.getStartYear();
		const endYear = item.getEndYear();
		// 当前公历年是否落在该大运区间内（含端点）→ 该大运的流年 eager 算 flowMonths/starCharger，其余惰性。
		const isCurrentDaYun = Number.isFinite(startYear) && Number.isFinite(endYear)
			&& currentYear >= startYear && currentYear <= endYear;
		return {
			age: item.getStartAge(),
			startYear,
			endYear,
			mainDirect,
			subDirect: item.getLiuNian().map((year)=>({
				year: year.getYear(),
				age: year.getAge(),
				index: year.getIndex(),
				flowMonths: isCurrentDaYun ? buildFlowMonths(year, birthSolar, dayGan) : null,
				starCharger: isCurrentDaYun ? makeStarChargerFromSolar(safeSolarAtYear(year.getYear(), birthSolar)) : null,
				...pillarFromGanzi('年', year.getGanZhi(), dayGan),
			})),
		};
	});
}

function buildMainDirection(daYunList, dayGan){
	return daYunList.map((item, idx)=>{
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

function buildSmallDirection(daYunList, dayGan, birthSolar){
	const currentYear = new Date().getFullYear();
	return daYunList.flatMap((dayun)=>dayun.getXiaoYun()).map((item)=>{
		const year = item.getYear();
		const yearSolar = safeSolarAtYear(year, birthSolar);
		const yearLunar = yearSolar.getLunar();
		const yearGanzi = yearLunar.getYearInGanZhiByLiChun ? yearLunar.getYearInGanZhiByLiChun() : yearLunar.getYearInGanZhi();
		const direct = pillarFromGanzi('小', item.getGanZhi(), dayGan);
		// starCharger 惰性化：现代默认 UI 不读小运 starCharger（仅 legacy SmallDirection 读），
		// 仅当前公历年那条 eager 算，其余 null；legacy 消费端 null 时按公历年补算 buildStarChargerForYear。
		const liunian = {
			year,
			age: item.getAge(),
			starCharger: year === currentYear ? makeStarChargerFromSolar(yearSolar) : null,
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

function formatStartLuck(yun, precision){
	const y = yun.getStartYear();
	const mo = yun.getStartMonth();
	const d = yun.getStartDay();
	const h = yun.getStartHour ? yun.getStartHour() : 0;
	if(precision === 'integer'){
		// 起运整数：按 3 天折 1 岁的余日就近进位为整岁（通行口径）。
		const rounded = Math.max(1, Math.round(y + mo / 12 + d / 365));
		return `出生后约${rounded}年起运`;
	}
	return `出生后${y}年${mo}个月${d}天${h}小时起运`;
}

// 晚子时·紫微所用农历(月/日/闰)。after23NewDay=1 且本命落 23 点子时段时,日柱已进位次日,
// 但 lunar.getDay() 仍是当日历日 → 紫微/命宫/农历日须随日柱同步进位(否则 zi_chu/midnight_split/
// zi_zheng 三方案紫微落宫完全相同=死)。这里照日柱口径(_computeDay:hm∈[23:00,23:59] 才进位)用次日
// 历日重算一个 lunar,正确处理月/年/闰跨界;非进位场景退回当日 lunar(零回归)。
// 仅紫微读 ziweiMonthNum/ziweiDayNum/ziweiLeap;八字 fourColumns 与展示用 monthNum/dayNum 不变。
function ziweiLunarFor(lunar, solar, dayPillarShift, apparentHour){
	const shifted = dayPillarShift && Number(apparentHour) === 23;
	if(!shifted || !solar || !solar.next){ return lunar; }
	try{
		const nextLunar = solar.next(1).getLunar();
		return nextLunar || lunar;
	}catch(e){
		return lunar; // 跨界容错:取不到次日 lunar 时退回当日,不阻断排盘
	}
}

function buildNongli(lunar, solar, apparentSolar, ziweiLunar){
	const prev = lunar.getPrevJieQi ? lunar.getPrevJieQi(false) : lunar.getPrevJie(false);
	const prevSolar = prev && prev.getSolar ? prev.getSolar() : null;
	let dayDiff = '';
	if(prevSolar && solar.subtract){
		dayDiff = `${prev.getName()}后第${Math.max(1, solar.subtract(prevSolar) + 1)}天`;
	}
	const zwLunar = ziweiLunar || lunar;
	return {
		year: lunar.getYearInChinese(),
		month: `${lunar.getMonthInChinese()}月`,
		day: lunar.getDayInChinese(),
		leap: lunar.getMonth ? lunar.getMonth() < 0 : false,
		// 数字农历(紫微排盘等需要):monthNum=农历月1-12(闰月取绝对值)、dayNum=农历日1-30。
		monthNum: lunar.getMonth ? Math.abs(lunar.getMonth()) : null,
		dayNum: lunar.getDay ? lunar.getDay() : null,
		// 晚子时·紫微专用农历(随日柱进位口径;默认=与 monthNum/dayNum/leap 同值,仅 after23 子时段次日不同)。
		ziweiMonthNum: zwLunar.getMonth ? Math.abs(zwLunar.getMonth()) : (lunar.getMonth ? Math.abs(lunar.getMonth()) : null),
		ziweiDayNum: zwLunar.getDay ? zwLunar.getDay() : (lunar.getDay ? lunar.getDay() : null),
		ziweiLeap: zwLunar.getMonth ? zwLunar.getMonth() < 0 : (lunar.getMonth ? lunar.getMonth() < 0 : false),
		// 正月初一口径年干支(紫微「定年界线=初一」用;纯新增字段,八字/奇门等不读→零影响。八字 fourColumns.year 仍走立春不变)。
		yearGZByLunar: lunar.getYearInGanZhi ? lunar.getYearInGanZhi() : null,
		// 生肖两口径(立春=与年柱一致默认 / 正月初一=民俗);纯展示,年柱永按立春不变。
		shengXiaoLichun: lunar.getYearShengXiaoByLiChun ? lunar.getYearShengXiaoByLiChun() : (lunar.getYearShengXiao ? lunar.getYearShengXiao() : ''),
		shengXiaoLunar: lunar.getYearShengXiao ? lunar.getYearShengXiao() : '',
		birth: apparentSolar.toYmdHms(),
		jieqi: prev && prev.getName ? prev.getName() : '',
		jiedelta: dayDiff,
		chef: '',
	};
}

// [A3·核心层 memo] 时空核心(solar/lunar/eightChar/yun/大运/紫微农历)只依赖下列键;
// 五个派生开关(minggongMethod/phaseType/godKeyPos/fenyeVersion/cangVersion)与 lateZiHourUseNextDay/
// dayunPrecision 均在核心之外 —— 用户在选项轴来回拨时核心层零重算(实测核心占大头)。
// 状态安全:唯一 setter eightChar.setSect 由 after23NewDay 驱动且 after23 在核心键内 → 每个缓存桶
// 构造时定终身,复用零漂移;daYunList 消费者全只读(map/slice/flatMap)。开关 horosa.perf.baziCoreMemo
// (localStorage 置 '0' 关=旧行为逐次全算);字节等价由全部八字 golden/压测(同日期×选项笛卡尔)裁决。
const BAZI_CORE_KEYS = ['date', 'time', 'zone', 'ad', 'lon', 'lat', 'gpsLon', 'gpsLat', 'timeAlg', 'after23NewDay', 'gender'];
const baziCoreMemo = new Map();   // key -> bundle(插入序 LRU,8 桶)
const BAZI_CORE_MEMO_MAX = 8;
function baziCoreMemoEnabled(){
	try{
		if(typeof localStorage === 'undefined'){ return true; }
		return localStorage.getItem('horosa.perf.baziCoreMemo') !== '0';
	}catch(e){ return true; }
}
function buildBaziCore(params){
	const rawParts = parseDateTime(params);
	if(!Number.isFinite(rawParts.year) || !Number.isFinite(rawParts.month) || !Number.isFinite(rawParts.day)){
		throw new Error('invalid bazi date');
	}
	// lunar-javascript 可靠域 AD1~9999:域外(公元前/万年后)其节气静默错位 → 月柱错干支,
	// 比报错更危险。此处硬挡,域外历法走后端星历实算路径(错误信息供上层提示)。
	if(!isLunarJsYearReliable(rawParts.year)){
		throw new Error(lunarDomainNotice(rawParts.year));
	}
	const apparentParts = applyApparentSolarTime(rawParts, params || {});
	const solar = solarFromParts(apparentParts);
	const lunar = solar.getLunar();
	const eightChar = lunar.getEightChar();
	// 用户语义（拍板，字面直觉版）:
	//   after23NewDay=1「23点算第二天」= 23点起日柱进位次日 → setSect(1)=Exact 进位
	//   after23NewDay=0「24点算第二天」= 23点仍属今日、24点才换日柱 → setSect(2)=Exact2 不进位
	// 对应 lunar.js: setSect(1)在 hour∈[23,24) 时 dayGan+1；setSect(2) 不进位。
	const dayPillarShift = params && (params.after23NewDay === 1 || params.after23NewDay === '1' || params.after23NewDay === true);
	eightChar.setSect(dayPillarShift ? 1 : 2);
	const gender = Number(params.gender) === 0 ? 0 : 1;
	const yun = eightChar.getYun(gender);
	// perf · A1：大运表算一次，喂给三个推运 builder（旧版三 builder 各自调 yun.getDaYun(10)，3 次重活）。
	const daYunList = yun.getDaYun(10);
	// 晚子时·紫微所用农历:after23NewDay=1 且本命落 23 点子时段 → 日柱已进位次日,紫微随之取次日历日。
	const ziweiLunar = ziweiLunarFor(lunar, solar, dayPillarShift, apparentParts.hour);
	// [A3·profile 定谳] 三推运 builder(流年/主运/小运,lunar.js 逐年重演)≈ 全函数 97% 耗时,
	// 且只依赖核心键参数 → 随核心一并缓存;消费侧以 slice() 发新数组防外部 push/splice 互染。
	const dayGan = eightChar.getDayGan();
	const direction = buildDirection(daYunList, dayGan, solar);
	const mainDirection = buildMainDirection(daYunList, dayGan);
	const smallDirection = buildSmallDirection(daYunList, dayGan, solar);
	return { rawParts, apparentParts, solar, lunar, eightChar, dayPillarShift, gender, yun, daYunList, ziweiLunar, direction, mainDirection, smallDirection };
}
function getBaziCore(params){
	if(!baziCoreMemoEnabled()){
		return buildBaziCore(params);
	}
	const key = BAZI_CORE_KEYS.map((k)=>`${params && params[k] !== undefined && params[k] !== null ? params[k] : ''}`).join('|');
	const hit = baziCoreMemo.get(key);
	if(hit){
		// 访问提升(Map 重插=LRU 触底保护)
		baziCoreMemo.delete(key);
		baziCoreMemo.set(key, hit);
		return hit;
	}
	const bundle = buildBaziCore(params);
	baziCoreMemo.set(key, bundle);
	while(baziCoreMemo.size > BAZI_CORE_MEMO_MAX){
		const first = baziCoreMemo.keys().next().value;
		baziCoreMemo.delete(first);
	}
	return bundle;
}

export function buildLocalBaziResult(params){
	const core = getBaziCore(params);
	const { rawParts, apparentParts, solar, lunar, eightChar, dayPillarShift, gender, yun, daYunList, ziweiLunar } = core;
	const dayGan = eightChar.getDayGan();
	// v3 第二开关 lateZiHourUseNextDay: 默认 1 (跟现有 lunar.js Exact 行为一致, 时干用次日干起子时)。
	const lateZiHourUseNextDay = (params && (params.lateZiHourUseNextDay === 0 || params.lateZiHourUseNextDay === '0' || params.lateZiHourUseNextDay === false)) ? 0 : 1;
	const minggongMethod = (params && params.minggongMethod === 'shufa') ? 'shufa' : 'tongxing';
	// 死选项接线·phaseType（长生派别 0火土同/1水土同/2阳顺阴逆）：默认 0 = lunar.js 现状（byte-perfect）。
	// 仅在 phaseType=1 且日元为土（戊/己）时覆盖四柱 diShi；其余档/非土日元 → 不覆盖（详见 resolveDiShiByPhaseType）。
	const phaseType = (params && (params.phaseType === 1 || params.phaseType === '1' || params.phaseType === 2 || params.phaseType === '2'))
		? Number(params.phaseType) : 0;
	// 死选项接线·godKeyPos（神煞主位 年/日/年日）：默认 '年'（与 Java GodsHelper/BaZiDirect 一致；
	// 旧本地实现恒并年+日是 bug）。月柱基组恒含；按年/日/年日切年柱与日柱基组（见 calcFourPillarShenSha）。
	const godKeyPos = (params && (params.godKeyPos === '日' || params.godKeyPos === '年日')) ? params.godKeyPos : '年';
	const fourColumns = buildFourColumns(eightChar, { lateZiHourUseNextDay, minggongMethod, phaseType, godKeyPos });
	// 月律分野（人元司令）：节后天数 → 司令藏干（版本可切，纯展示派生）
	let fenYe = null;
	try{
		const prevJie = lunar.getPrevJie();
		const daysAfterJie = solar.getJulianDay() - prevJie.getSolar().getJulianDay();
		const fenyeVersion = (params && params.fenyeVersion === 'fajue') ? 'fajue' : 'common';
		fenYe = computeFenYe(eightChar.getMonthZhi(), daysAfterJie, fenyeVersion);
	}catch(e){ /* 节气边缘容错，分野缺省不阻断排盘 */ }
	// 五行力量·藏干版本：cangVersion='fenye'（分野加权）→ 月柱仅当令司令之干吃 monthMult，其余月支藏干不加月乘。
	// 默认 'common'（通行版）与历史口径字节一致（零回归）。司令干取 fenYe.ruler.gan（按 fenyeVersion 表轮值）。
	const cangVersion = (params && params.cangVersion === 'fenye') ? 'fenye' : 'common';
	const wuxingStat = computeWuxingStrength(fourColumns, {
		cangVersion,
		siLingGan: (fenYe && fenYe.ruler) ? fenYe.ruler.gan : '',
	});
	const gejuYongShen = computeGejuYongShen(fourColumns, wuxingStat);
	const mangpai = computeMangPai(fourColumns);
	// (daYunList/ziweiLunar 已随核心层缓存,见 buildBaziCore)
	const bazi = {
		gender: gender === 1 ? 'Male' : 'Female',
		nongli: buildNongli(lunar, solar, solar, ziweiLunar),
		fourColumns,
			wuxingStat,
			gejuYongShen,
			mangpai,
			fenYe,
			gong12God: {},
			direction: core.direction.slice(),
			mainDirection: core.mainDirection.slice(),
			smallDirection: core.smallDirection.slice(),
		directTime: yun.getStartSolar().toYmdHms(),
		directInfo: formatStartLuck(yun, params && params.dayunPrecision),
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

// 批A：供 AI 挂载多运限按所选流日/流时无头复算（与四柱同口径，纯 lunar.js）。
export { buildFlowDays, buildFlowHours };

export default buildLocalBaziResult;
