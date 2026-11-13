// 东亚诸术:藏历(浦派时轮历)与藏占(八卦 Parkha / 九宫 Mewa / 魂命煞)、蒙古 Zurkhai、日本算命学、九星气学、
// 洛书流年、易卦星盘。全部是纯算术,只读出生资料(易卦星盘另读本命盘的星位与宫位)。
//
// 藏历:Phugpa 派,1927 历元。平日 / 平太阳 / 月异常三条线性式,月差表 8 格、日差表 4 格对称插值;
// 真月序 n = ⌊(67·M* + 72) / 65⌋,M* = 12(Y − 1927) + M − 3。闰月指数 ix = (2·M* + 55) mod 65,
// ix 为 48 或 49 的月前面置一个同名闰月(闰月在前)。n 用 72 而不是 55:两式真月序只差月份标号,
// 用 55 时闰月会落到 ix 为 0、1 的月前,与闰月规则错开一档(245 个藏历日逐日对照,72 全对)。
// 一个民用日收两个太阴日时跳号(本日标前一个号,后一个号跳过),一个太阴日跨整日时重号(前一日标「重日」)。
// 民用日从当地平太阳时 5 点起算:日序 = ⌊JD(UT) + 0.5 + 东经/360 − 5/24⌋。
import { computeFenYe } from '../bazi/baziFenYe.js';
import { eastAsiaPillarFacts, xunKongOf, pairBranchRelations } from '../bazi/baziLunarLocal.js';
import { zibaiYearCenter } from '../fengshui/liqiCore.js';
import { monthCenter, dayCenter } from '../fengshui/zibai.js';
import { ZIBAI_STAR } from '../fengshui/fengshuiData.js';
import { Gua64 } from '../gua/GuaConst.js';

// ─────────────────────────── 藏历 ───────────────────────────
const M1 = 167025 / 5656;
const M2 = 11135 / 11312;
const M0 = 2424972 + 5457 / 5656;
const S1 = 65 / 804;
const S2 = 13 / 4824;
const S0 = 749 / 804;
const A1 = 253 / 3528;
const A2 = 1 / 28;
const A0 = 1741 / 3528;
const MOON_TABLE = [0, 5, 10, 15, 19, 22, 24, 25];
const SUN_TABLE = [0, 6, 10, 11];

const frac = (x)=>x - Math.floor(x);

function tableValue(x, table, per){
	const span = per * 4;
	const base = (i)=>{
		const k = ((i % span) + span) % span;
		if(k <= per){ return table[k]; }
		if(k <= 2 * per){ return table[2 * per - k]; }
		if(k <= 3 * per){ return -table[k - 2 * per]; }
		return -table[4 * per - k];
	};
	const v = ((x % span) + span) % span;
	const f = Math.floor(v);
	const r = v - f;
	return base(f) + (base(f + 1) - base(f)) * r;
}

function meanSun(day, n){ return n * S1 + day * S2 + S0; }

function sunEquation(day, n){ return tableValue(frac(meanSun(day, n) - 0.25) * 12, SUN_TABLE, 3); }

// 第 n 个真月第 day 个太阴日结束的时刻:整数部分 = 那个民用日的日序,小数 = 从当地 5 点起的日分
export function tibetanTrueDate(day, n){
	const meanDate = n * M1 + day * M2 + M0;
	const anomaly = n * A1 + day * A2 + A0;
	return meanDate + tableValue(frac(anomaly) * 28, MOON_TABLE, 7) / 60 - sunEquation(day, n) / 60;
}

// 真太阳黄经(度):平太阳减日差
export function tibetanTrueSun(day, n){
	return frac(meanSun(day, n) - sunEquation(day, n) / (27 * 60)) * 360;
}

const monthIndexOf = (ms)=>Math.floor((67 * ms + 72) / 65);

export function tibetanMonthLabel(n){
	let ms = Math.floor((65 * n - 72) / 67) - 2;
	while(monthIndexOf(ms) < n){ ms += 1; }
	return {
		year: 1927 + Math.floor((ms + 2) / 12),
		month: ((ms + 2) % 12 + 12) % 12 + 1,
		leap: monthIndexOf(ms) !== n,
		intercalation: ((2 * ms + 55) % 65 + 65) % 65,
	};
}

export function tibetanCivilDayNumber(jdUt, lonEast){
	return Math.floor(Number(jdUt) + 0.5 + (Number(lonEast) || 0) / 360 - 5 / 24);
}

export function tibetanDateOfDayNumber(dayNumber){
	let n = Math.floor((dayNumber - M0) / M1);
	while(Math.floor(tibetanTrueDate(30, n)) < dayNumber){ n += 1; }
	while(Math.floor(tibetanTrueDate(30, n - 1)) >= dayNumber){ n -= 1; }
	let day = 1;
	for(; day <= 30; day += 1){
		if(Math.floor(tibetanTrueDate(day, n)) >= dayNumber){ break; }
	}
	const end = tibetanTrueDate(day, n);
	// 后一个太阴日也在今天结束:今天标前一个号,后一个号跳过(第 30 日看下月初一)
	const nextEnd = day < 30 ? tibetanTrueDate(day + 1, n) : tibetanTrueDate(1, n + 1);
	const skipped = Math.floor(end) === dayNumber && Math.floor(nextEnd) === dayNumber;
	return {
		...tibetanMonthLabel(n),
		day,
		extra: Math.floor(end) > dayNumber,            // 这一天没有太阴日结束:与次日同号,本日是「重日」
		skippedDay: skipped ? (day < 30 ? day + 1 : 1) : null,   // 这一天收了两个太阴日:后一个号跳过
		trueMonth: n,
		lunarDayEnds: Math.floor(end) === dayNumber ? frac(end) : null,
		trueSun: tibetanTrueSun(day, n),
	};
}

const STEMS = '甲乙丙丁戊己庚辛壬癸';
const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';
const ANIMALS = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'];
const TIB_ELEMENTS = ['木', '火', '土', '铁', '水'];
export const WEEKDAY_PLANETS = ['日', '月', '火', '水', '木', '金', '土'];

export function tibetanYearInfo(year){
	const s = ((year - 4) % 10 + 10) % 10;
	const b = ((year - 4) % 12 + 12) % 12;
	return {
		year,
		stem: STEMS[s],
		branch: BRANCHES[b],
		animal: ANIMALS[b],
		animalIndex: b,
		element: TIB_ELEMENTS[Math.floor(s / 2)],
		male: s % 2 === 0,
		rabjung: Math.floor((year - 1027) / 60) + 1,          // 第一胜生周始于 1027 火阴兔年
		rabjungYear: ((year - 1027) % 60 + 60) % 60 + 1,
	};
}

// 胜生周文字:1027 年以前没有胜生周纪年,如实写明,不出「第 -8 胜生周」
export function rabjungText(info){
	if(!info){ return ''; }
	if(info.rabjung < 1){ return `早于胜生周纪年(第一胜生周始于 1027 年),六十年周期中第 ${info.rabjungYear} 年`; }
	return `第 ${info.rabjung} 胜生周第 ${info.rabjungYear} 年`;
}

// ─────────────────────────── 八卦 Parkha ───────────────────────────
// 后天八卦方位顺时针:离 S · 坤 SW · 兑 W · 乾 NW · 坎 N · 艮 NE · 震 E · 巽 SE。
export const PARKHA = [
	{ key: 'li', gua: '离', tib: 'Li', dir: '南', element: '火' },
	{ key: 'khon', gua: '坤', tib: 'Khon', dir: '西南', element: '土' },
	{ key: 'dwa', gua: '兑', tib: 'Dwa', dir: '西', element: '铁' },
	{ key: 'khen', gua: '乾', tib: 'Khen', dir: '西北', element: '天(铁)' },
	{ key: 'kham', gua: '坎', tib: 'Kham', dir: '北', element: '水' },
	{ key: 'gin', gua: '艮', tib: 'Gin', dir: '东北', element: '山(土)' },
	{ key: 'zin', gua: '震', tib: 'Zin', dir: '东', element: '木' },
	{ key: 'zon', gua: '巽', tib: 'Zon', dir: '东南', element: '风(木)' },
];
const PARKHA_INDEX = { li: 0, kham: 4 };

// 流年八卦:男命一岁起离顺行,女命一岁起坎逆行,每岁一宫(岁数按藏历,生年为一岁)。
// 流年早于出生(岁数 < 1)没有流年八卦,返回 null,由调用方写明「早于出生」(不悄悄按一岁算)。
export function yearParkha(age, male){
	const a = Math.floor(Number(age));
	if(!Number.isFinite(a) || a < 1){ return null; }
	const start = male ? PARKHA_INDEX.li : PARKHA_INDEX.kham;
	const step = male ? 1 : -1;
	return PARKHA[(((start + step * (a - 1)) % 8) + 8) % 8];
}

// 日八卦:正月初一起坎,逐日顺行;每月 30 日,所以下月初一比本月初一退两宫(30 ≡ 6 ≡ −2 mod 8)
export function dayParkha(month, day){
	const steps = (Number(month) - 1) * 30 + (Number(day) - 1);
	return PARKHA[((PARKHA_INDEX.kham + steps) % 8 + 8) % 8];
}

// ─────────────────────────── 九宫 Mewa ───────────────────────────
export const MEWA_COLOR = { 1: '白', 2: '黑', 3: '蓝', 4: '绿', 5: '黄', 6: '白', 7: '红', 8: '白', 9: '红' };
const nine = (v)=>((Math.round(v) % 9) + 9) % 9 || 9;

export function birthMewa(year){ return nine(1 - (year - 1963)); }

export function mewaSet(birthYear, currentYear){
	const b = birthMewa(birthYear);
	return {
		birth: b,
		year: birthMewa(currentYear),
		vitality: nine(b - 3),
		power: nine(b + 3),
		// 下降九宫:阴年(奇数年)同本命;阳年按 1946 起逆数
		descending: birthYear % 2 !== 0 ? b : nine(birthYear - 1946),
	};
}

export function lunarDayMewa(month, day){ return nine(Number(day) + 3 * (Number(month) + 1)); }
export function calendarDayMewa(dayNumber){ return nine(-dayNumber); }

// ─────────────────────────── 魂命煞(按生肖) ───────────────────────────
// 前三项是星曜(星期),后六项是二十七宿序号(0 起,0 = 娄宿 Aśvinī)。
export const FORCE_LABELS = ['魂曜', '命曜', '煞曜', '魂宿', '命宿', '力宿', '凶宿', '魔宿', '煞宿'];
const FORCE_PLANETS = ['日', '月', '水', '金', '火', '木', '土'];
const FORCE_TABLE = [
	[2, 4, 6, 19, 5, 2, 25, 9, 22], [6, 2, 5, 16, 13, 11, 1, 7, 4], [5, 6, 3, 4, 26, 8, 13, 11, 1],
	[5, 6, 3, 10, 26, 11, 25, 24, 17], [0, 2, 5, 2, 23, 16, 7, 8, 10], [4, 3, 2, 12, 11, 5, 7, 8, 5],
	[4, 3, 2, 16, 11, 5, 14, 4, 26], [3, 1, 5, 7, 0, 1, 14, 4, 26], [3, 5, 4, 7, 0, 1, 8, 4, 16],
	[3, 5, 4, 13, 6, 24, 2, 10, 23], [1, 2, 5, 8, 26, 4, 10, 2, 11], [2, 4, 6, 1, 7, 10, 15, 2, 11],
];
// 二十七宿(梵名);序号 0 起(0 = 娄 Aśvinī)
export const TIB_MANSIONS = ['娄 Aśvinī', '胃 Bharaṇī', '昴 Kṛttikā', '毕 Rohiṇī', '觜 Mṛgaśira', '参 Ārdrā', '井 Punarvasu',
	'鬼 Puṣya', '柳 Āśleṣā', '星 Maghā', '张 Pūrvaphalgunī', '翼 Uttaraphalgunī', '轸 Hasta', '角 Citrā', '亢 Svātī',
	'氐 Viśākhā', '房 Anurādhā', '心 Jyeṣṭhā', '尾 Mūla', '箕 Pūrvāṣāḍhā', '斗 Uttarāṣāḍhā', '女 Śravaṇa', '虚 Dhaniṣṭhā',
	'危 Śatabhiṣaj', '室 Pūrvabhādrapadā', '壁 Uttarabhādrapadā', '奎 Revatī'];

export function forcesOf(animalIndex){
	const row = FORCE_TABLE[animalIndex];
	if(!row){ return []; }
	return row.map((value, i)=>({
		label: FORCE_LABELS[i],
		value: i < 3 ? `${FORCE_PLANETS[value]}曜(星期${['日', '一', '三', '五', '二', '四', '六'][value]})` : (TIB_MANSIONS[value] || String(value)),
	}));
}

// ─────────────────────────── 蒙古 Zurkhai ───────────────────────────
export const ZURKHAI_RELATION = { 0: '同支', 2: '相邻', 3: '隔一支', 4: '隔二支', 5: '隔三支(三合位)', 6: '隔四支', 7: '对冲' };
export function zurkhaiAspect(yearZhi, monthZhi){
	const a = BRANCHES.indexOf(yearZhi);
	const b = BRANCHES.indexOf(monthZhi);
	if(a < 0 || b < 0){ return null; }
	if(a === b){ return 0; }
	const d = Math.abs(a - b);
	return Math.min(d, 12 - d) + 1;
}

// ─────────────────────────── 洛书流年 ───────────────────────────
const LOSHU_V = { 2: 2, 3: 9, 4: 4, 5: 3, 6: 8, 7: 1, 0: 6, 1: 7 };
const LOSHU_C = { 2: 1, 3: 7, 4: 3, 5: 2, 6: 6, 7: 9, 0: 4, 1: 5 };
export const LOSHU_CELLS = [
	{ key: 'head', label: '头', offset: 7 }, { key: 'leftShoulder', label: '左肩', offset: 2 }, { key: 'rightShoulder', label: '右肩', offset: 8 },
	{ key: 'chest', label: '胸', offset: 5 }, { key: 'leftHand', label: '左手', offset: 6 }, { key: 'rightHand', label: '右手', offset: 4 },
	{ key: 'belly', label: '腹', offset: 0 }, { key: 'leftFoot', label: '左脚', offset: 3 }, { key: 'rightFoot', label: '右脚', offset: 1 },
];
export function loshuTransit(birthYear, flowYear){
	const age = Number(flowYear) - Number(birthYear);
	// 流年早于出生:不排九格,标 beforeBirth 由调用方写明
	if(age < 0){ return { year: Number(flowYear), age, beforeBirth: true, center: null, active: null, cells: [] }; }
	const k = ((age % 8) + 8) % 8;
	const center = LOSHU_C[k];
	const active = LOSHU_V[k];
	const cells = LOSHU_CELLS.map((cell)=>{
		let v = center + cell.offset;
		if(v > 9){ v -= 9; }                  // 一律减 9(有的传本部分格减 10,会出重复数和 0)
		return { ...cell, value: v, active: v === active };
	});
	return { year: Number(flowYear), age, center, active, cells };
}

// ─────────────────────────── 九星气学 ───────────────────────────
export function nineStarKi(facts){
	if(!facts){ return null; }
	const year = facts.lichunYear;
	const monthIdx = (BRANCHES.indexOf(facts.month.zhi) - 2 + 12) % 12 + 1;     // 寅月为 1
	const honmei = zibaiYearCenter(year);
	const getsumei = monthCenter(year, monthIdx);
	let nichimei = null;
	let nichimeiDun = null;
	try{
		const dc = dayCenter(facts.civil.year, facts.civil.month, facts.civil.day);
		nichimei = dc ? dc.center : null;
		nichimeiDun = dc ? `${dc.yang ? '阳遁' : '阴遁'}${dc.yuanName || ''}` : null;
	}catch(e){ nichimei = null; }
	return {
		year, monthIndex: monthIdx,
		honmei, honmeiName: ZIBAI_STAR[honmei],
		getsumei, getsumeiName: ZIBAI_STAR[getsumei],
		nichimei, nichimeiName: nichimei ? ZIBAI_STAR[nichimei] : null, nichimeiDun,
	};
}

// ─────────────────────────── 算命学 ───────────────────────────
const BRANCH_RELATION_CN = { ziCong: '冲', ziHe6: '六合', ziHe3: '三合', ziXing: '刑', ziCuan: '害' };
// 算命学的藏干三元叫法:分段表的余气 / 中气 / 本气 = 初元 / 中元 / 本元
const SANMEI_POS = { 余气: '初元', 中气: '中元', 本气: '本元' };
// 三柱:日、月、年(年按立春、月按节、日按 0 点)。藏干按节入日数分初元 / 中元 / 本元,三支用同一个节入日数;
// 天中杀 = 日柱所在旬的空亡两支。藏干表与八字页「月律分野」同一张(通行版 / 法诀版)。
export function sanmeigaku(facts, fenyeVersion){
	if(!facts){ return null; }
	const pillars = [['日', facts.day], ['月', facts.month], ['年', facts.year]];
	const days = facts.daysAfterJie;
	const hidden = pillars.map(([label, p])=>{
		const fy = Number.isFinite(days) ? computeFenYe(p.zhi, days, fenyeVersion) : null;
		const pos = fy && fy.ruler ? fy.ruler.pos : null;
		return { label, zhi: p.zhi, ruler: fy && fy.ruler ? fy.ruler.gan : null, rulerPos: pos ? (SANMEI_POS[pos] || pos) : null, segments: fy ? fy.segments : [] };
	});
	const voids = xunKongOf(facts.day.gz);
	const branches = pillars.map(([label, p])=>({ label, zhi: p.zhi }));
	const relations = [];
	for(let i = 0; i < branches.length; i += 1){
		for(let j = i + 1; j < branches.length; j += 1){
			const hits = pairBranchRelations(branches[i].zhi, branches[j].zhi) || [];
			hits.forEach((hit)=>relations.push({ a: branches[i].label, b: branches[j].label, kind: BRANCH_RELATION_CN[hit.kind] || hit.kind, text: hit.key }));
		}
	}
	return {
		pillars: pillars.map(([label, p])=>({ label, gan: p.gan, zhi: p.zhi, gz: p.gz })),
		daysAfterJie: Number.isFinite(days) ? Math.round(days * 10) / 10 : null,
		prevJie: facts.prevJieName,
		hidden,
		tenchusatsu: voids ? voids.split('') : [],
		relations,
	};
}

// 天中杀年:流年地支落在两支内的年份(未来 n 年)
export function tenchusatsuYears(voids, fromYear, count){
	const out = [];
	for(let y = fromYear; out.length < (count || 4) && y < fromYear + 40; y += 1){
		const zhi = BRANCHES[((y - 4) % 12 + 12) % 12];
		if(voids.indexOf(zhi) >= 0){ out.push({ year: y, zhi }); }
	}
	return out;
}

// ─────────────────────────── 易卦星盘 ───────────────────────────
// 黄经 0° 起每 5.625° 一卦,按先天六十四卦圆图:复起冬至(270°)顺行至乾止于夏至(90°),姤起夏至顺行至坤止于冬至,
// 乾坤正对。三爻记作 3 位掩码:最高位是初爻(下),最低位是上爻。
export const DEGREE_HEX_RING = [19, 41, 60, 61, 54, 38, 58, 10, 11, 26, 5, 9, 34, 14, 43, 1,
	44, 28, 50, 32, 57, 48, 18, 46, 6, 47, 64, 40, 59, 29, 4, 7, 33, 31, 56, 62, 53, 39, 52, 15, 12, 45, 35, 16, 20, 8, 23, 2,
	24, 27, 3, 42, 51, 21, 17, 25, 36, 22, 63, 37, 55, 30, 49, 13];
export const SIGN_HEX = [39, 53, 37, 44, 28, 43, 38, 54, 40, 24, 27, 23];
export const HOUSE_HEX = [11, 34, 43, 1, 44, 33, 12, 20, 23, 2, 24, 19];
export const PLANET_TRIGRAM = { Sun: 7, Moon: 6, Mercury: 5, Venus: 4, Mars: 3, Jupiter: 2, Saturn: 1 };
const TRIGRAM_NAME = { 7: '乾', 6: '兑', 5: '离', 4: '震', 3: '巽', 2: '坎', 1: '艮', 0: '坤' };
const TRI_ORDER = [7, 6, 5, 4, 3, 2, 1, 0];
const KING_WEN = [[1, 43, 14, 34, 9, 5, 26, 11], [10, 58, 38, 54, 61, 60, 41, 19], [13, 49, 30, 55, 37, 63, 22, 36], [25, 17, 21, 51, 42, 3, 27, 24],
	[44, 28, 50, 32, 57, 48, 18, 46], [6, 47, 64, 40, 59, 29, 4, 7], [33, 31, 56, 62, 53, 39, 52, 15], [12, 45, 35, 16, 20, 8, 23, 2]];

export function kingWen(upper, lower){ return KING_WEN[TRI_ORDER.indexOf(lower)][TRI_ORDER.indexOf(upper)]; }

const HEX_TRIGRAMS = {};
TRI_ORDER.forEach((u)=>TRI_ORDER.forEach((l)=>{ HEX_TRIGRAMS[kingWen(u, l)] = { upper: u, lower: l }; }));
export function hexTrigrams(num){ return HEX_TRIGRAMS[num] || null; }

const HEX_NAMES = {};
function bitsOf(mask){ return [(mask >> 2) & 1, (mask >> 1) & 1, mask & 1]; }
(Gua64 || []).forEach((g)=>{
	if(!g || !Array.isArray(g.value)){ return; }
	TRI_ORDER.forEach((u)=>TRI_ORDER.forEach((l)=>{
		const v = bitsOf(l).concat(bitsOf(u));
		if(v.every((b, i)=>b === g.value[i])){ HEX_NAMES[kingWen(u, l)] = g.name; }
	}));
});
export function hexName(num){ return HEX_NAMES[num] ? `${num} ${HEX_NAMES[num]}` : String(num); }
export function trigramName(mask){ return TRIGRAM_NAME[mask] || ''; }

export const ICHING_MERGE = ['horizon', 'upper', 'lower'];
// horizon:地平上(7~12 宫)合到上卦,地平下合到下卦(缺省);upper / lower 恒合上卦 / 下卦
export function mergeTrigram(num, mask, toUpper){
	const t = hexTrigrams(num);
	if(!t){ return null; }
	return toUpper ? kingWen(t.upper ^ mask, t.lower) : kingWen(t.upper, t.lower ^ mask);
}

export function degreeHexagram(lon){
	const v = ((Number(lon) % 360) + 360) % 360;
	return DEGREE_HEX_RING[Math.floor(v / 5.625) % 64];
}

export function ichingRows(planets, merge){
	const mode = ICHING_MERGE.indexOf(merge) >= 0 ? merge : 'horizon';
	return (planets || []).filter((p)=>PLANET_TRIGRAM[p.id] !== undefined && Number.isFinite(p.lon)).map((p)=>{
		const mask = PLANET_TRIGRAM[p.id];
		const sign = Math.floor((((p.lon % 360) + 360) % 360) / 30);
		const house = Number(p.house) || null;
		const toUpper = mode === 'upper' ? true : (mode === 'lower' ? false : (house ? house >= 7 : false));
		const deg = degreeHexagram(p.lon);
		const signHex = SIGN_HEX[sign];
		const houseHex = house ? HOUSE_HEX[house - 1] : null;
		return {
			id: p.id, lon: p.lon, sign, house, trigram: mask, toUpper,
			degree: deg, degreeMerged: mergeTrigram(deg, mask, toUpper),
			sign_: signHex, signMerged: mergeTrigram(signHex, mask, toUpper),
			house_: houseHex, houseMerged: houseHex ? mergeTrigram(houseHex, mask, toUpper) : null,
		};
	});
}

// 易卦推运:环位 = (出生起日数 + 62) mod 64,逐日前进一格
export function ichingProgression(daysSinceBirth){
	const pos = ((Math.floor(daysSinceBirth) + 62) % 64 + 64) % 64;
	return { position: pos, hexagram: DEGREE_HEX_RING[pos] };
}

// ─────────────────────────── 汇总 ───────────────────────────
export function eastAsiaFacts(params){
	try{ return eastAsiaPillarFacts(params); }catch(e){ return null; }
}

export { BRANCHES as EAST_ASIA_BRANCHES, ANIMALS as EAST_ASIA_ANIMALS };
