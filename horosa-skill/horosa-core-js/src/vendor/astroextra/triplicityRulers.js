import moment from 'moment';
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';
import { TRIPLICITY } from '../divination/data/hellenisticData.js';
// [YB] 三段补厚共享 helper(起盘信息/当前时点/方法说明;astroAiSnapshot 不回引本文件,无环)。
// namespace import + typeof 守卫:测试环境可能部分 mock astroAiSnapshot(只留 buildAstroSnapshotContent 等),
// 缺函数时回 [] 保底 → 输出与补厚前逐字节一致,不炸挂载。
// headless stub：上游 [YB] 三段补厚用它产 [起盘信息]/[当前时点]/[方法说明]，但 skill 的 Python 层
// 已经产这三段（契约 v10 的 _predictive_setup_section_text / _predictive_common_sections_text），
// 再让 JS 产一遍会重段。上游每个调用点都写了 typeof …==='function' 守卫，缺失即回退 []，故空对象即正解。
const astroAiSnapshot = {};
const birthHeaderLines = (c) => (typeof astroAiSnapshot.buildPredictiveBirthHeaderLines === 'function' ? astroAiSnapshot.buildPredictiveBirthHeaderLines(c) : []);
const currentMomentLines = (c, x) => (typeof astroAiSnapshot.buildCurrentMomentLines === 'function' ? astroAiSnapshot.buildCurrentMomentLines(c, x) : []);
const methodNoteLines = (k) => (typeof astroAiSnapshot.buildMethodNoteLines === 'function' ? astroAiSnapshot.buildMethodNoteLines(k) : []);

// 三分主星推运（Triplicity-Ruler Periods）。纯前端：仅重新切分本命盘。
//  ① 区间光体：昼生看太阳所在座、夜生看月亮所在座。
//  ② 该座元素的三颗三分主星（昼/夜/协作），按昼夜换序：
//       ruler1 = 昼盘取 Trip[0] / 夜盘取 Trip[1]（主）；ruler2 反之（次）；ruler3 = Trip[2]（协作，贯穿）。
//  ③ 划分：三分（默认 0–25/25–50/50–75）或两分（上/下半生 + 协作贯穿）。
//  ④ 各段品质 = 该主星落宫（角=旺/续=中/果=衰）+ 庙旺/逆行。
//  ⑤ 换段计时参考行星期（日19/月25/水20/金8/火15/木12/土30）。
// 三分主星表直接读 AstroConst.SignsProp[sign].Trip，不重复编码。

export const TRIPLICITY_LIFESPAN_DEFAULT = 75;

export const PLANETARY_PERIOD_YEARS = {
	[AstroConst.SUN]: 19,
	[AstroConst.MOON]: 25,
	[AstroConst.MERCURY]: 20,
	[AstroConst.VENUS]: 8,
	[AstroConst.MARS]: 15,
	[AstroConst.JUPITER]: 12,
	[AstroConst.SATURN]: 30,
};

export const TRIPLICITY_DIVISIONS = {
	thirds: '三分（0–25 / 25–50 / 50–75）',
	halves: '两分（上半生 / 下半生 + 协作贯穿）',
};

// 三分体系（同一元素三分主星的取法分歧；默认多罗特三主＝现状）。
//  Dorothean  ：昼/夜/共同 三主（与本盘 SignsProp.Trip 一致）。
//  Ptolemaic  ：昼/夜 两主（无共同主星）；水象座特别取两/三主变体。
//  PtolemaicWaterVariant：托勒密两主，但水象座改用另一套水象三主。
export const TRIPLICITY_SYSTEMS = {
	Dorothean: '多罗特三主（昼/夜/共同）',
	Ptolemaic: '托勒密二主（昼/夜）',
	PtolemaicWaterVariant: '托勒密·水象变体',
};

export const TRIPLICITY_SYSTEM_DEFAULT = 'Dorothean';

// 三分体系名 → 顶部说明。
export const TRIPLICITY_SYSTEM_HINTS = {
	Dorothean: '多罗特体系：每元素三颗三分主星（昼主／夜主／共同主），按昼夜换序分掌人生各阶段，共同主星贯穿。',
	Ptolemaic: '托勒密体系：每元素仅昼、夜两颗主星，无共同主星，按昼夜分掌上下半生。',
	PtolemaicWaterVariant: '托勒密体系（水象变体）：火/土/风三象同托勒密二主；唯水象座改取另一套水象主星（昼火金、夜火月）。',
};

export const TRIPLICITY_DEFAULT_OPTS = { division: 'thirds', lifespan: TRIPLICITY_LIFESPAN_DEFAULT, system: TRIPLICITY_SYSTEM_DEFAULT };

// 星座英文名 → 元素键（Fire/Earth/Air/Water），用于在希腊化三分表中取对应元素行。
const SIGN_ELEMENT = {
	Aries: 'Fire', Leo: 'Fire', Sagittarius: 'Fire',
	Taurus: 'Earth', Virgo: 'Earth', Capricorn: 'Earth',
	Gemini: 'Air', Libra: 'Air', Aquarius: 'Air',
	Cancer: 'Water', Scorpio: 'Water', Pisces: 'Water',
};

// 取某星座在指定体系下、依当前昼夜已排好序的三分主星列表 [主, 次?]。
//  Dorothean   → 复用 SignsProp.Trip（[昼,夜,共同]），按昼夜换序为 [主,次,共同]（与现状一致）。
//  Ptolemaic   → 元素行 {day, night} 视为 {昼主,夜主}，按昼夜取 [本派主, 另一]；水象退化为单主（火）。
//  水象变体     → 火/土/风同托勒密；水象改取 text_variant[昼/夜] 已序列表（昼[火,金]/夜[火,月]）。
// 返回的数组首元＝当前昼夜的「主」三分主星，次元（若有）＝「次」。下游不再换序。
export function resolveTripletForSign(sign, system, isDiurnal){
	const sp = sign ? AstroConst.SignsProp[sign] : null;
	const trip = (sp && Array.isArray(sp.Trip)) ? sp.Trip : null;
	const dorotheanOrdered = trip ? [isDiurnal ? trip[0] : trip[1], isDiurnal ? trip[1] : trip[0], trip[2]] : [];
	if(system !== 'Ptolemaic' && system !== 'PtolemaicWaterVariant'){
		return dorotheanOrdered; // 多罗特（默认）：三主，已按昼夜换序。
	}
	const elem = SIGN_ELEMENT[sign];
	const tab = (TRIPLICITY && TRIPLICITY.Ptolemaic) ? TRIPLICITY.Ptolemaic[elem] : null;
	if(!tab){ return dorotheanOrdered; }
	if(elem === 'Water'){
		const variant = tab.text_variant;
		if(system === 'PtolemaicWaterVariant' && variant){
			const seq = isDiurnal ? variant.day : variant.night; // 昼[火,金] / 夜[火,月]，已序。
			if(Array.isArray(seq)){ return seq.slice(); }
		}
		return [tab.day].filter(Boolean); // 标准托勒密水象：昼夜同主（火），单主。
	}
	// 火/土/风：元素行 {昼主, 夜主}，按昼夜取 [本派主, 另一]。
	return [isDiurnal ? tab.day : tab.night, isDiurnal ? tab.night : tab.day].filter(Boolean);
}

const SIGN_CN = {
	Aries: '白羊', Taurus: '金牛', Gemini: '双子', Cancer: '巨蟹', Leo: '狮子', Virgo: '处女',
	Libra: '天秤', Scorpio: '天蝎', Sagittarius: '射手', Capricorn: '摩羯', Aquarius: '水瓶', Pisces: '双鱼',
};

const ANGULARITY_CN = { angular: '角宫·旺', succedent: '续宫·中', cadent: '果宫·衰' };

// 逐宫三分主星象征（古典逐宫应用，供右栏次表展示）。
export const TRIPLICITY_HOUSE_SIGS = {
	1: { first: '欲求/喜好·前1/3生', second: '生命/健康/力量·中1/3生', third: '后1/3生（兼前二者义）' },
	2: { first: '人生三阶段财务（视三主星状态优劣）', second: '—', third: '—' },
	3: { first: '年幼手足', second: '居中排行手足', third: '年长手足' },
	4: { first: '父亲', second: '城邑与田产', third: '事物终结与监牢' },
	5: { first: '子女及其生活', second: '性方面喜好', third: '使节/外交任务者' },
	6: { first: '身体疾病与复原', second: '仆役', third: '走兽四足（兼牢狱拘留）' },
	7: { first: '女性/异性', second: '竞争或诉讼', third: '联合/合伙' },
	8: { first: '死亡', second: '古旧之物', third: '遗产/因死所遗' },
	9: { first: '长途旅行', second: '信仰/宗教', third: '智慧/梦境/星占/征兆' },
	10: { first: '权位尊贵与高升', second: '指挥胆识', third: '持久与稳定' },
	11: { first: '信念', second: '朋友', third: '此类事之效用与成功' },
	12: { first: '敌人', second: '劳作/分娩', third: '走兽（皆兼牢狱囚徒义）' },
};

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

function parseBirth(chartObj){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim();
	if(!birth){ return null; }
	const m = moment(birth.replace(/\//g, '-'), ['YYYY-MM-DD HH:mm:ss', 'YYYY-MM-DD HH:mm', 'YYYY-MM-DD']);
	return m.isValid() ? m : null;
}

function findObj(chartObj, id){
	const objs = (chartObj && chartObj.chart && chartObj.chart.objects) || [];
	return objs.find((x) => x.id === id) || null;
}

function natalLon(chartObj, id){
	const o = findObj(chartObj, id);
	if(!o){ return null; }
	if(o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
	if(idx >= 0 && o.signlon !== undefined && o.signlon !== null){ return idx * 30 + Number(o.signlon); }
	return null;
}

function natalSign(chartObj, id){
	const o = findObj(chartObj, id);
	if(o && o.sign){ return o.sign; }
	const lon = natalLon(chartObj, id);
	if(lon == null){ return null; }
	return AstroConst.LIST_SIGNS[Math.floor(norm360(lon) / 30)] || null;
}

function houseNum(h){
	if(h == null){ return null; }
	if(typeof h === 'number'){ return h; }
	const m = String(h).match(/(\d+)/);
	return m ? Number(m[1]) : null;
}

function angularityOf(h){
	if([1, 4, 7, 10].indexOf(h) >= 0){ return 'angular'; }
	if([2, 5, 8, 11].indexOf(h) >= 0){ return 'succedent'; }
	return 'cadent';
}

function rulerQuality(chartObj, planet){
	const o = findObj(chartObj, planet);
	const h = o ? houseNum(o.house) : null;
	const ang = h ? angularityOf(h) : null;
	const retro = !!(o && o.movedir === 'Retrograde');
	const sign = natalSign(chartObj, planet);
	let dignity = null;
	if(sign){
		const sp = AstroConst.SignsProp[sign];
		if(sp){
			if(sp.Ruler === planet){ dignity = '入庙'; }
			else if(sp.Exalt === planet){ dignity = '入旺'; }
			else if(sp.Exile === planet){ dignity = '陷'; }
			else if(sp.Fall === planet){ dignity = '落'; }
		}
	}
	return { house: h, angularity: ang, retro, dignity, sign };
}

function planetTxt(id){
	if(id === undefined || id === null || id === ''){ return '-'; }
	return AstroText.AstroTxtMsg[id] || `${id}`;
}

function resolveOpts(opts){
	const o = { ...TRIPLICITY_DEFAULT_OPTS, ...(opts || {}) };
	if(!TRIPLICITY_DIVISIONS[o.division]){ o.division = 'thirds'; }
	if(!TRIPLICITY_SYSTEMS[o.system]){ o.system = TRIPLICITY_SYSTEM_DEFAULT; }
	o.lifespan = Number(o.lifespan) > 0 ? Number(o.lifespan) : TRIPLICITY_LIFESPAN_DEFAULT;
	return o;
}

// 主输出：区间光体的三分主星 → 人生各阶段。
export function buildTriplicityPeriods(chartObj, opts){
	const o = resolveOpts(opts);
	const chart = chartObj && chartObj.chart;
	if(!chart){ return null; }
	const isDiurnal = !!chart.isDiurnal;
	const sectLight = isDiurnal ? AstroConst.SUN : AstroConst.MOON;
	const sign = natalSign(chartObj, sectLight);
	const sp = sign ? AstroConst.SignsProp[sign] : null;
	if(!sp || !Array.isArray(sp.Trip)){ return { isDiurnal, sectLight, sign, signCn: sign ? SIGN_CN[sign] : '', periods: [], lifespan: o.lifespan, division: o.division, system: o.system }; }
	const L = o.lifespan;
	const birth = parseBirth(chartObj);
	const dateAt = (age) => (birth ? moment(birth).add(Math.round(age * 365.2422), 'days').format('YYYY-MM-DD') : '');
	const periods = buildRawPeriods(sign, isDiurnal, o.system, o.division, L);
	periods.forEach((p) => {
		p.fromDate = dateAt(p.fromAge);
		p.toDate = dateAt(p.toAge);
		p.quality = rulerQuality(chartObj, p.ruler);
		p.period = PLANETARY_PERIOD_YEARS[p.ruler];
		p.rulerCn = planetTxt(p.ruler);
	});
	return { isDiurnal, sectLight, sectLightCn: planetTxt(sectLight), sign, signCn: sign ? SIGN_CN[sign] : '', periods, lifespan: L, division: o.division, system: o.system };
}

// 按体系与划分法生成原始阶段（仅 ruler/role/年龄段）。
//  Dorothean（默认）严格保持现状逻辑：从 SignsProp.Trip 取 [昼,夜,共同]，三段。
//  Ptolemaic/水象变体：二主 → 主/次两段；退化单主 → 仅一段（贯穿全程）。
function buildRawPeriods(sign, isDiurnal, system, division, L){
	const sp = AstroConst.SignsProp[sign];
	if(system === 'Dorothean'){
		const trip = sp.Trip;
		const r1 = isDiurnal ? trip[0] : trip[1];
		const r2 = isDiurnal ? trip[1] : trip[0];
		const r3 = trip[2];
		if(division === 'halves'){
			return [
				{ ruler: r1, role: '主三分主星（上半生）', fromAge: 0, toAge: L / 2 },
				{ ruler: r2, role: '次三分主星（下半生）', fromAge: L / 2, toAge: L },
				{ ruler: r3, role: '协作主星（贯穿）', fromAge: 0, toAge: L },
			];
		}
		return [
			{ ruler: r1, role: '主三分主星', fromAge: 0, toAge: L / 3 },
			{ ruler: r2, role: '次三分主星', fromAge: L / 3, toAge: (2 * L) / 3 },
			{ ruler: r3, role: '协作主星', fromAge: (2 * L) / 3, toAge: L },
		];
	}
	// 托勒密体系（含水象变体）：resolveTripletForSign 已按昼夜排好序 [主, 次?]。
	const seq = resolveTripletForSign(sign, system, isDiurnal);
	const r1 = seq[0];
	const r2 = seq.length > 1 ? seq[1] : seq[0];
	if(seq.length <= 1 || r1 === r2){
		// 单主（标准托勒密水象，昼夜同主）：全程一段。
		return [{ ruler: r1, role: '三分主星（贯穿）', fromAge: 0, toAge: L }];
	}
	if(division === 'halves'){
		return [
			{ ruler: r1, role: '主三分主星（上半生）', fromAge: 0, toAge: L / 2 },
			{ ruler: r2, role: '次三分主星（下半生）', fromAge: L / 2, toAge: L },
		];
	}
	return [
		{ ruler: r1, role: '主三分主星', fromAge: 0, toAge: L / 2 },
		{ ruler: r2, role: '次三分主星', fromAge: L / 2, toAge: L },
	];
}

// AI 快照。section 头 [三分主星推运] 与 aiExport preset 对齐。
export function buildTriplicityRulersSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const r = buildTriplicityPeriods(chartObj, opts);
	if(!r || !r.periods || !r.periods.length){ return ''; }
	const lines = [];
	// [YB] 头部盘主生辰([起盘信息];无数据 helper 自返 [],不产空段头)。
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[三分主星推运]');
	lines.push(`${r.isDiurnal ? '昼' : '夜'}生盘，区间光体=${r.sectLightCn}（${r.signCn}），三分体系＝${TRIPLICITY_SYSTEMS[r.system] || TRIPLICITY_SYSTEMS[TRIPLICITY_SYSTEM_DEFAULT]}，三分主星依其落宫与状态主导人生各阶段（${TRIPLICITY_DIVISIONS[r.division]}）。`);
	lines.push('');
	lines.push('| 阶段 | 主星 | 年龄段 | 日期段 | 落宫 | 状态 |');
	lines.push('| --- | --- | --- | --- | --- | --- |');
	r.periods.forEach((p) => {
		const q = p.quality || {};
		const place = q.house ? `第${q.house}宫·${ANGULARITY_CN[q.angularity] || ''}` : '-';
		const state = [q.dignity, q.retro ? '逆行' : ''].filter(Boolean).join('/') || '平';
		lines.push(`| ${p.role} | ${p.rulerCn} | ${p.fromAge.toFixed(0)}–${p.toAge.toFixed(0)}岁 | ${p.fromDate || '-'}~${p.toDate || '-'} | ${place} | ${state} |`);
	});
	lines.push('');
	lines.push('注：行星落角宫主该阶段鼎盛、续宫居中、果宫衰减；再结合入庙旺/受剋与定位星综合论断。');
	// bug 修:UI 的 12 宫逐宫三分主星象征块(AstroTriplicityRulers 用 TRIPLICITY_HOUSE_SIGS 渲染)此前整块缺;
	// 值/拼接口径同 UI(一主必出,二主/三主为「—」时省略),并入本段尾 ◆ 子块。
	lines.push('');
	lines.push('◆ 十二宫三分主星象征');
	Object.keys(TRIPLICITY_HOUSE_SIGS).forEach((h) => {
		const s = TRIPLICITY_HOUSE_SIGS[h];
		const second = (s.second && s.second !== '—') ? `；二主：${s.second}` : '';
		const third = (s.third && s.third !== '—') ? `；三主：${s.third}` : '';
		lines.push(`${h}宫：一主：${s.first}${second}${third}`);
	});
	// [YB] 尾部 [当前时点]+[方法说明];定位行=当前年龄所处阶段(halves 划分下协作主星贯穿,可多段并列)。
	const extraLines = [];
	const birth = parseBirth(chartObj);
	if(birth){
		const curAge = moment().diff(birth, 'years', true);
		const curPeriods = r.periods.filter((p) => curAge >= p.fromAge && curAge < p.toAge);
		if(curPeriods.length){
			extraLines.push(`当前所处阶段：${curPeriods.map((p) => `${p.role}·${p.rulerCn}（${p.fromAge.toFixed(0)}–${p.toAge.toFixed(0)}岁）`).join('；')}`);
		}
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('triplicityrulers')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}

export default { buildTriplicityPeriods, buildTriplicityRulersSnapshotText, resolveTripletForSign, TRIPLICITY_DIVISIONS, TRIPLICITY_SYSTEMS, TRIPLICITY_SYSTEM_HINTS, TRIPLICITY_SYSTEM_DEFAULT, TRIPLICITY_HOUSE_SIGS, TRIPLICITY_DEFAULT_OPTS, PLANETARY_PERIOD_YEARS };
