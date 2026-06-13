import moment from 'moment';
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';

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

export const TRIPLICITY_DEFAULT_OPTS = { division: 'thirds', lifespan: TRIPLICITY_LIFESPAN_DEFAULT };

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
	if(!sp || !Array.isArray(sp.Trip)){ return { isDiurnal, sectLight, sign, signCn: sign ? SIGN_CN[sign] : '', periods: [], lifespan: o.lifespan, division: o.division }; }
	const trip = sp.Trip;
	const r1 = isDiurnal ? trip[0] : trip[1];
	const r2 = isDiurnal ? trip[1] : trip[0];
	const r3 = trip[2];
	const L = o.lifespan;
	const birth = parseBirth(chartObj);
	const dateAt = (age) => (birth ? moment(birth).add(Math.round(age * 365.2422), 'days').format('YYYY-MM-DD') : '');
	let periods;
	if(o.division === 'halves'){
		periods = [
			{ ruler: r1, role: '主三分主星（上半生）', fromAge: 0, toAge: L / 2 },
			{ ruler: r2, role: '次三分主星（下半生）', fromAge: L / 2, toAge: L },
			{ ruler: r3, role: '协作主星（贯穿）', fromAge: 0, toAge: L },
		];
	}else{
		periods = [
			{ ruler: r1, role: '主三分主星', fromAge: 0, toAge: L / 3 },
			{ ruler: r2, role: '次三分主星', fromAge: L / 3, toAge: (2 * L) / 3 },
			{ ruler: r3, role: '协作主星', fromAge: (2 * L) / 3, toAge: L },
		];
	}
	periods.forEach((p) => {
		p.fromDate = dateAt(p.fromAge);
		p.toDate = dateAt(p.toAge);
		p.quality = rulerQuality(chartObj, p.ruler);
		p.period = PLANETARY_PERIOD_YEARS[p.ruler];
		p.rulerCn = planetTxt(p.ruler);
	});
	return { isDiurnal, sectLight, sectLightCn: planetTxt(sectLight), sign, signCn: sign ? SIGN_CN[sign] : '', periods, lifespan: L, division: o.division };
}

// AI 快照。section 头 [三分主星推运] 与 aiExport preset 对齐。
export function buildTriplicityRulersSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const r = buildTriplicityPeriods(chartObj, opts);
	if(!r || !r.periods || !r.periods.length){ return ''; }
	const lines = ['[三分主星推运]'];
	lines.push(`${r.isDiurnal ? '昼' : '夜'}生盘，区间光体=${r.sectLightCn}（${r.signCn}），三分主星依其落宫与状态主导人生各阶段（${TRIPLICITY_DIVISIONS[r.division]}）。`);
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
	return lines.join('\n');
}

export default { buildTriplicityPeriods, buildTriplicityRulersSnapshotText, TRIPLICITY_DIVISIONS, TRIPLICITY_HOUSE_SIGS, TRIPLICITY_DEFAULT_OPTS, PLANETARY_PERIOD_YEARS };
