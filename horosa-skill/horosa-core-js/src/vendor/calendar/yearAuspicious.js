// yearAuspicious.js — 年度黄道吉日榜引擎（纯前端）。
//
// 复用：日课 buildHuangliDay（含 lunar 通书宜忌 + 内部建除/黄黑道/28宿）；事项分类 EVENT_CATEGORIES。
// 设计要点：以 lunar「宜」为权威闸门（lunar 宜忌本身已神煞择净），命中事项宜方入榜；
// 建除吉位/黄道/吉神/值宿吉 为排名加分，关键大凶（四废/五墓/受死）为硬红线覆盖宜。
import { buildHuangliDay } from './huangliDay.js';
import { EVENT_CATEGORIES, EVENT_KEY_TO_CATEGORY, KEY_JI_SHEN } from './tongshuData.js';
import { Solar } from 'lunar-javascript';

// 真大凶「百事不宜」——即便 lunar 列宜亦淘汰（名取 lunar 实际凶煞词表）。
// 🔴 '受死' 不在 lunar 神煞词表(表内实名为「致死」sn.zhiSi)→ 该条曾恒不触发,
// 注释自称「名取 lunar 实际凶煞词表」与事实相反。
const HARD_EXCLUDE = ['四废', '五墓', '致死', '阴阳击冲'];
// 软凶煞——入榜但扣分（排名靠后）。
const SOFT_XIONG = ['往亡', '月厌', '大耗', '天贼', '天火', '归忌', '月煞', '死神', '月刑', '大煞', '月虚', '死气'];
// 建除吉位加分（破日不硬排除：破屋/破土宜破日，由 lunar 宜把关）。
const GOOD_JIANCHU = { 定: 2, 成: 2, 开: 2, 危: 1, 执: 1 };

// 内存缓存：跨调用复用整年 day 对象（一年一填，切年份自然新键）。
const dayCache = new Map();
function cachedDay(y, m, d) {
	const key = `${y}-${m}-${d}`;
	if (!dayCache.has(key)) { dayCache.set(key, buildHuangliDay(y, m, d)); }
	return dayCache.get(key);
}

// 单日对某事项类别评分；非该事项宜日 / 逢硬红线 → 返回 null（不入榜）。
export function scoreDayForEvent(day, cat) {
	const yiSet = new Set(day.yi || []);
	const yiHits = (cat.yiKeys || []).filter((k)=> yiSet.has(k));
	if (!yiHits.length) { return null; }

	const xs = new Set([...(day.xiongsha || []), ...(day.ji || [])]);
	if (HARD_EXCLUDE.some((k)=> xs.has(k))) { return null; }

	const reasons = [];
	let score = 3;
	reasons.push({ t: 'good', text: `宜${yiHits.join('、')}` });

	if (GOOD_JIANCHU[day.jianchu.name]) {
		score += GOOD_JIANCHU[day.jianchu.name];
		reasons.push({ t: 'good', text: `${day.jianchu.name}日` });
	} else {
		reasons.push({ t: 'muted', text: `${day.jianchu.name}日` });
	}

	if (day.tianshen.type === '黄道') { score += 2; reasons.push({ t: 'good', text: `${day.tianshen.name}·黄道` }); }
	else { score -= 1; reasons.push({ t: 'bad', text: `${day.tianshen.name}·黑道` }); }

	if (day.xiu.jx === 'good') { score += 1; reasons.push({ t: 'good', text: `${day.xiu.name}宿吉` }); }
	else if (day.xiu.jx === 'bad') { score -= 1; reasons.push({ t: 'bad', text: `${day.xiu.name}宿凶` }); }

	const jsHit = (day.jishen || []).filter((k)=> KEY_JI_SHEN.includes(k));
	if (jsHit.length) { score += Math.min(3, jsHit.length); reasons.push({ t: 'good', text: `吉神：${jsHit.join('、')}` }); }

	const softHit = SOFT_XIONG.filter((k)=> xs.has(k));
	if (softHit.length) { score -= 2 * softHit.length; reasons.push({ t: 'bad', text: `凶煞：${softHit.join('、')}` }); }

	return { score, reasons, yiHits };
}

// 结果 memo：同 (年 · 事项集 · topN) 恒同结果，全年扫描（365 天 × 日课）重且同步阻塞主线程，
// 老黄历年度吉日榜与日子馆逐次重算常复用同年同事项 → 缓存令二次起近乎瞬时（返回只读，消费方不改）。
const _yearAusCache = new Map();

// 扫全年 → { [catKey]: { label, list:[{ymd,week,lunar,ganzhi,jianchu,xiu,huangdao,score,reasons}] } }（每类分降序 Top N）。
export function buildYearAuspicious(year, opts = {}) {
	const eventKeys = (opts.events && opts.events.length)
		? opts.events
		: EVENT_CATEGORIES.filter((c)=> !c.sensitive).map((c)=> c.key);
	const topN = opts.topN || 12;
	const cacheKey = `${year}|${[...eventKeys].sort().join(',')}|${topN}`;
	const cached = _yearAusCache.get(cacheKey);
	if (cached) { return cached; }
	const cats = eventKeys.map((k)=> EVENT_KEY_TO_CATEGORY[k]).filter(Boolean);
	const out = {};
	cats.forEach((c)=>{ out[c.key] = { label: c.label, list: [] }; });

	let cur = Solar.fromYmd(year, 1, 1);
	while (cur.getYear() === year) {
		const day = cachedDay(cur.getYear(), cur.getMonth(), cur.getDay());
		cats.forEach((cat)=>{
			const sc = scoreDayForEvent(day, cat);
			if (sc) {
				out[cat.key].list.push({
					ymd: day.solar.ymd,
					week: day.solar.week,
					lunar: `${day.lunar.monthCn}月${day.lunar.dayCn}`,
					ganzhi: day.lunar.dayGZ,
					jianchu: day.jianchu.name,
					xiu: day.xiu.name,
					huangdao: day.tianshen.type,
					score: sc.score,
					reasons: sc.reasons,
				});
			}
		});
		cur = cur.next(1);
	}
	Object.keys(out).forEach((k)=>{
		out[k].list.sort((a, b)=> (b.score - a.score) || (a.ymd < b.ymd ? -1 : 1));
		out[k].list = out[k].list.slice(0, topN);
	});
	if (_yearAusCache.size > 48) { _yearAusCache.clear(); }   // 防无限增长（跨多年/多事项集）
	_yearAusCache.set(cacheKey, out);
	return out;
}

export default buildYearAuspicious;
