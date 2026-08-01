// riziEngine.js — 日子馆个性化择日引擎（纯前端）。
// 在通书基线（年度吉日榜·事项宜日）之上，叠加各命主八字（复用 baziLunarLocal）冲煞/用神生扶，
// 多命主取交集（冲任一人本命年支即淘汰），综合评分排序。跨人合婚 hehunPair 纯查表零外部依赖。
import { buildLocalBaziResult } from '../bazi/baziLunarLocal.js';
import { ZHI_CHONG, ZHI_SANHE_JU, NAYIN_60 } from '../fengshui/fengshuiData.js';
import { buildYearAuspicious } from './yearAuspicious.js';
import { EVENT_KEY_TO_CATEGORY } from './tongshuData.js';
import { buildHuangliDay } from './huangliDay.js';

const ZHI_SHENGXIAO = { 子: '鼠', 丑: '牛', 寅: '虎', 卯: '兔', 辰: '龙', 巳: '蛇', 午: '马', 未: '羊', 申: '猴', 酉: '鸡', 戌: '狗', 亥: '猪' };
const GAN_WX = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };
const ZHI_WX = { 子: '水', 亥: '水', 寅: '木', 卯: '木', 巳: '火', 午: '火', 申: '金', 酉: '金', 辰: '土', 戌: '土', 丑: '土', 未: '土' };
// 地支六合。
const ZHI_HE6 = { 子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯', 辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午' };
// 地支相刑（三刑 + 自刑）：无恩寅巳申·持势丑戌未·无礼子卯·自刑辰午酉亥。
const ZHI_XING = { 寅: '巳', 巳: '申', 申: '寅', 丑: '戌', 戌: '未', 未: '丑', 子: '卯', 卯: '子', 辰: '辰', 午: '午', 酉: '酉', 亥: '亥' };
// 五行生克（纳音年命合婚用）。生：木→火→土→金→水→木；克：木克土·土克水·水克火·火克金·金克木。
const WX_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
const WX_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };

// 从生辰参数抽取择日所需八字要素（复用本地八字引擎，取年命/日主/用神喜忌）。
export function personBazi(params) {
	const r = buildLocalBaziResult(params);
	const fc = r.bazi.fourColumns;
	const ys = (r.bazi.gejuYongShen || {}).yongshen || {};
	const yearGZ = fc.year.ganZhi;
	const yearZhi = fc.year.branch.cell;
	const dayGan = fc.day.stem.cell;
	const dayZhi = fc.day.branch.cell;
	return {
		yearGZ, yearZhi, shengxiao: ZHI_SHENGXIAO[yearZhi],
		dayGZ: fc.day.ganZhi, dayGan, dayZhi, dayGanWx: GAN_WX[dayGan],
		xi: Array.isArray(ys.xi) ? ys.xi : [],
		ji: Array.isArray(ys.ji) ? ys.ji : [],
		verdict: ys.verdict || '',
		nayinYear: (NAYIN_60[yearGZ] || {}).name || '',
		nayinYearWx: (NAYIN_60[yearGZ] || {}).wuxing || '',
	};
}

// 跨人合婚：年命相冲 / 三合 / 六合 / 纳音生克（纯查表）。
export function hehunPair(a, b) {
	if (!a || !b || !a.yearZhi || !b.yearZhi) { return null; }
	const chong = ZHI_CHONG[a.yearZhi] === b.yearZhi;
	// 三合加 ZHI_SANHE_JU[a] 真值守卫：否则两个非地支串 undefined===undefined 误报三合（与 scoreDayForPerson 对齐）。
	const sanhe = !chong && a.yearZhi !== b.yearZhi && !!ZHI_SANHE_JU[a.yearZhi] && ZHI_SANHE_JU[a.yearZhi] === ZHI_SANHE_JU[b.yearZhi];
	const liuhe = ZHI_HE6[a.yearZhi] === b.yearZhi;
	// 纳音年命五行生克：相生最吉 / 比和次吉 / 相克凶。旧代码把「同五行」误标「相生」，且不识真相生/相克。
	const wa = a.nayinYearWx; const wb = b.nayinYearWx;
	const nayinBihe = !!wa && wa === wb;
	const nayinSheng = !!wa && !!wb && !nayinBihe && (WX_SHENG[wa] === wb || WX_SHENG[wb] === wa);
	const nayinKe = !!wa && !!wb && !nayinBihe && (WX_KE[wa] === wb || WX_KE[wb] === wa);
	let verdict = '平';
	let jx = 'neutral';
	if (chong) { verdict = '年命六冲（相冲）'; jx = 'bad'; }
	else if (sanhe) { verdict = '年命三合'; jx = 'good'; }
	else if (liuhe) { verdict = '年命六合'; jx = 'good'; }
	else if (nayinSheng) { verdict = '纳音相生'; jx = 'good'; }
	else if (nayinBihe) { verdict = '纳音比和（同五行）'; jx = 'good'; }
	else if (nayinKe) { verdict = '纳音相克'; jx = 'bad'; }
	return { chong, sanhe, liuhe, nayinHe: nayinBihe, nayinSheng, nayinKe, verdict, jx, nayinA: a.nayinYear, nayinB: b.nayinYear };
}

// 候选日对单命主评分。冲本命年支 → 硬淘汰。opts={event,gender}：婚嫁重女命，性别据此生效。
function scoreDayForPerson(day, p, opts = {}) {
	const dayGZ = day.lunar.dayGZ;
	const dayZhi = dayGZ[1];
	const reasons = [];
	let score = 0;
	let hardBlock = false;
	if (ZHI_CHONG[dayZhi] === p.yearZhi) { hardBlock = true; reasons.push({ t: 'bad', text: `日冲${p.shengxiao}·犯本命年` }); }
	else if (ZHI_CHONG[dayZhi] === p.dayZhi) { score -= 3; reasons.push({ t: 'bad', text: '日支冲日柱' }); }
	const dayWx = [GAN_WX[dayGZ[0]], ZHI_WX[dayZhi]];
	const seen = new Set();
	dayWx.forEach((w)=>{
		if (seen.has(w)) { return; }
		seen.add(w);
		if (p.xi.includes(w)) { score += 2; reasons.push({ t: 'good', text: `日${w}生扶用神` }); }
		else if (p.ji.includes(w)) { score -= 1; reasons.push({ t: 'bad', text: `日${w}属忌神` }); }
	});
	// 婚嫁重女命（通书「嫁娶以女命为主」）：日支与命主年支三合/六合为上吉、刑害值岁为忌；
	// 女命(gender 0)权重从重、男命(gender 1)从轻 —— 性别据此真实改变婚课排名。
	const g = Number(opts.gender);
	if (opts.event === 'marriage' && (g === 0 || g === 1)) {
		const female = g === 0;
		const w = female ? 2 : 1;
		const role = female ? '新娘' : '新郎';
		const sanhe = dayZhi !== p.yearZhi && ZHI_SANHE_JU[dayZhi] && ZHI_SANHE_JU[dayZhi] === ZHI_SANHE_JU[p.yearZhi];
		const liuhe = ZHI_HE6[dayZhi] === p.yearZhi;
		if (sanhe) { score += w; reasons.push({ t: 'good', text: `日${dayZhi}三合${role}本命·嫁娶重女命` }); }
		else if (liuhe) { score += w; reasons.push({ t: 'good', text: `日${dayZhi}六合${role}本命` }); }
		if (female) {
			if (ZHI_XING[dayZhi] === p.yearZhi && dayZhi !== p.yearZhi) { score -= 2; reasons.push({ t: 'bad', text: `日刑新娘本命` }); }
			if (dayZhi === p.yearZhi) { score -= 1; reasons.push({ t: 'bad', text: `值新娘本命年(太岁)` }); }
		}
	}
	return { score, reasons, hardBlock };
}

// 折线曲线专用薄包装(P1):单日 × 单命主评分——组装 buildHuangliDay 的 day 结构后
// 直转 scoreDayForPerson;不改任何既有逻辑,只暴露新入口(共享引擎「只 import 不改」的加法豁免)。
export function scoreDateForPersonExport(dateStr, person, opts = {}) {
	const parts = String(dateStr || '').split(/[-/]/).map(Number);
	if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) { return null; }
	const day = buildHuangliDay(parts[0], parts[1], parts[2]);
	if (!day || !day.lunar) { return null; }
	return scoreDayForPerson(day, person, opts);
}

// 个性化吉日：通书基线 × 各命主八字，交集评分排序。
// persons=[{role, name, bazi:personBazi(...)}]；缺 bazi 的命主跳过评分（不阻断）。
export function buildPersonalizedDates({ event = 'marriage', persons = [], year, topN = 15, strongOnly = false }) {
	const cat = EVENT_KEY_TO_CATEGORY[event] || { label: event };
	const base = buildYearAuspicious(year, { events: [event], topN: 366 });
	const baseList = (base[event] && base[event].list) || [];
	const validPersons = persons.filter((p)=> p && p.bazi);

	const out = [];
	baseList.forEach((b)=>{
		const [y, m, d] = b.ymd.split('-').map((n)=> parseInt(n, 10));
		const day = buildHuangliDay(y, m, d);
		let total = b.score;
		let blocked = false;
		const perPerson = [];
		validPersons.forEach((p)=>{
			const sc = scoreDayForPerson(day, p.bazi, { event, gender: p.gender });
			if (sc.hardBlock) { blocked = true; }
			total += sc.score;
			perPerson.push({ role: p.role, name: p.name, shengxiao: p.bazi.shengxiao, gender: p.gender, ...sc });
		});
		if (blocked) { return; }   // 冲任一命主本命年 → 淘汰
		out.push({
			ymd: b.ymd, week: b.week, lunar: b.lunar, ganzhi: b.ganzhi, jianchu: b.jianchu, huangdao: b.huangdao,
			tongshuScore: b.score, score: total, tongshuReasons: b.reasons, perPerson,
		});
	});
	out.sort((a, b2)=> (b2.score - a.score) || (a.ymd < b2.ymd ? -1 : 1));
	const filtered = strongOnly ? out.filter((x)=> x.score >= 8) : out;
	return { event, label: cat.label, count: out.length, list: filtered.slice(0, topN) };
}

export default buildPersonalizedDates;
