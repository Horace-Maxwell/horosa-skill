// huangliDay.js — 老黄历日课聚合器（纯前端 · 零后端往返 · 零新增外部依赖）。
//
// 内部复用优先（决策5）：
//   · 建除十二神 / 黄黑道十二神 / 二十八宿值日 → fengshui/zeri.dayCourse（与 lunar 交叉校验）。
//   · 年家凶煞（太岁/岁破/三煞/五黄/十二岁君神）→ fengshui/zeri.yearGods。
//   · 纯通书日课（宜忌/彭祖/胎神/冲煞/吉神凶煞/五方位/时辰宜忌/物候/六曜/数九三伏/日禄/九星）
//     → 既有依赖 lunar-javascript（已被 baziLunarLocal/河洛/一掌经 import；非新增 GitHub 库）。
//
// 入参 (y,m,d,hour?) 皆公历；返回规范化 day 对象，供老黄历卡片 / 吉日榜 / 日子馆 / AI 快照复用。
import { Solar } from 'lunar-javascript';
import { dayCourse, yearGods } from '../fengshui/zeri.js';

// lunar 各 get*() 有的返回单值、有的返回数组、偶有空串 —— 统一成干净数组。
function asArr(v) {
	if (Array.isArray(v)) { return v.filter((x)=> x != null && x !== ''); }
	if (v == null || v === '') { return []; }
	return [v];
}
function safe(fn, fallback = null) {
	try { const v = fn(); return v == null ? fallback : v; } catch (e) { return fallback; }
}

// 九星值日：lunar getDayNineStar() 返回对象（getNumber/getColor/getWuXing/getPosition）。
function normalizeNineStar(ns) {
	if (!ns) { return null; }
	const number = safe(()=> ns.getNumber(), '');
	const color = safe(()=> ns.getColor(), '');
	const wuxing = safe(()=> ns.getWuXing(), '');
	const position = safe(()=> ns.getPosition(), '');
	return { number, color, wuxing, position, name: `${number}${color}${wuxing}`.trim() };
}

// 时辰宜忌：getTimes() 返回 13 段（早/晚子时分列），每段自带干支/黄黑道值神/宜忌/冲煞。
function normalizeTimes(lunar) {
	const times = safe(()=> lunar.getTimes(), []) || [];
	return times.map((t)=>({
		ganzhi: safe(()=> t.getGanZhi(), ''),
		range: `${safe(()=> t.getMinHm(), '')}-${safe(()=> t.getMaxHm(), '')}`,
		tianshen: safe(()=> t.getTianShen(), ''),          // 时家黄黑道值神
		luck: safe(()=> t.getTianShenLuck(), ''),          // 吉 / 凶
		yi: asArr(safe(()=> t.getYi(), [])),
		ji: asArr(safe(()=> t.getJi(), [])),
		chong: safe(()=> t.getChong(), ''),
		sha: safe(()=> t.getSha(), ''),
	}));
}

// 全局 memo（buildHuangliDay 为纯函数·同日恒同结果）：网格逐格/吉日榜全年扫描/日子馆逐候选
// 常对同一日反复调用，每次 2 次 getLunar（重）。memo 令跨模块复用，显著降本；返回值只读不改。
const _dayMemo = new Map();

// 聚合一日全通书日课。hour 影响时辰高亮聚焦（默认午时 12 时，日级字段与 hour 无关）。
export function buildHuangliDay(y, m, d, hour = 12) {
	const key = `${y}-${m}-${d}-${hour}`;
	const cached = _dayMemo.get(key);
	if (cached) { return cached; }
	const result = computeHuangliDay(y, m, d, hour);
	if (_dayMemo.size > 6000) { _dayMemo.clear(); }   // 防无限增长（跨多年扫描）
	_dayMemo.set(key, result);
	return result;
}

function computeHuangliDay(y, m, d, hour = 12) {
	const solar = Solar.fromYmdHms(y, m, d, Number.isFinite(hour) ? hour : 12, 0, 0);
	const lunar = solar.getLunar();
	const course = dayCourse(y, m, d);   // 内部：建除/黄黑道/28宿
	const yg = safe(()=> yearGods(y), null);   // 内部：年神方位

	const shujiu = safe(()=> lunar.getShuJiu(), null);
	const fu = safe(()=> lunar.getFu(), null);

	// 值宿吉凶单一真值 = lunar getXiuLuck()（与 AI 快照/卡片/吉日榜同源）。旧 jx 取 zeri XIU_28 表，
	// 与 lunar 有 1 硬反转（奎）+9 软差 → 曾致卡片标「吉」而 AI 标「凶」自相矛盾、吉日榜误加/漏扣分。
	const xiuLuck = safe(()=> lunar.getXiuLuck(), '');       // 吉 / 凶
	const xiuJx = xiuLuck === '吉' ? 'good' : (xiuLuck === '凶' ? 'bad' : 'neutral');
	// 当日恰逢节气时取精确交节时刻（时分秒）：老黄历卡纯前端此前只取节气名、缺时刻（农历 tab 走后端已有）。
	const jieqiName = safe(()=> lunar.getJieQi(), '');
	const jieqiTime = jieqiName
		? safe(()=> { const t = lunar.getJieQiTable()[jieqiName]; return t ? t.toYmdHms() : ''; }, '')
		: '';

	return {
		input: { y, m, d, hour },
		solar: {
			ymd: solar.toYmd(),
			week: safe(()=> solar.getWeekInChinese(), ''),
			festivals: asArr(safe(()=> solar.getFestivals(), [])),
		},
		lunar: {
			text: lunar.toString(),                                  // 二〇二四年五月初五
			monthCn: safe(()=> lunar.getMonthInChinese(), ''),
			dayCn: safe(()=> lunar.getDayInChinese(), ''),
			yearGZ: safe(()=> lunar.getYearInGanZhiByLiChun(), safe(()=> lunar.getYearInGanZhi(), '')),
			monthGZ: safe(()=> lunar.getMonthInGanZhi(), ''),
			dayGZ: safe(()=> lunar.getDayInGanZhi(), ''),
			shengxiao: safe(()=> lunar.getYearShengXiaoByLiChun(), safe(()=> lunar.getYearShengXiao(), '')),
			jieqi: jieqiName,                                        // 当日恰逢节气名（否则空）
			jieqiTime,                                               // 精确交节时刻 YYYY-MM-DD HH:mm:ss（无节气则空）
		},
		// —— 用事宜忌（纯通书，lunar 全列表）——
		yi: asArr(safe(()=> lunar.getDayYi(), [])),
		ji: asArr(safe(()=> lunar.getDayJi(), [])),
		// —— 建除 / 黄黑道值神 / 值宿（内部 zeri，与 lunar 交叉见 crossCheck）——
		jianchu: course.jianChu,                                    // { name, jx }
		huanghei: course.huangHei,                                  // { shen, dao, jx }（内部值神）
		tianshen: {                                                 // lunar 黄黑道（另一口径，供交叉/时辰对齐）
			name: safe(()=> lunar.getDayTianShen(), ''),
			type: safe(()=> lunar.getDayTianShenType(), ''),        // 黄道 / 黑道
			luck: safe(()=> lunar.getDayTianShenLuck(), ''),        // 吉 / 凶
		},
		xiu: {
			name: course.xiu.name,
			xiang: course.xiu.xiang,                                // 四象（东青龙…）
			zheng: safe(()=> lunar.getZheng(), ''),                 // 七政（日月火水木金土）
			animal: safe(()=> lunar.getAnimal(), ''),               // 禽兽
			luck: xiuLuck,                                          // 吉 / 凶（lunar 权威）
			jx: xiuJx,                                              // good/bad/neutral，由 lunar luck 派生（单一真值）
		},
		// —— 彭祖百忌 ——
		pengzu: { gan: safe(()=> lunar.getPengZuGan(), ''), zhi: safe(()=> lunar.getPengZuZhi(), '') },
		// —— 每日吉神宜趋 / 凶煞宜忌 ——
		jishen: asArr(safe(()=> lunar.getDayJiShen(), [])),
		xiongsha: asArr(safe(()=> lunar.getDayXiongSha(), [])),
		// —— 冲煞 ——
		chong: {
			desc: safe(()=> lunar.getDayChongDesc(), ''),           // (己亥)猪
			shengxiao: safe(()=> lunar.getDayChongShengXiao(), ''), // 猪
			sha: safe(()=> lunar.getDaySha(), ''),                  // 煞方
		},
		// —— 胎神占方 ——
		tai: safe(()=> lunar.getDayPositionTai(), ''),
		// —— 吉神方位（喜/福/财/阳贵/阴贵）——
		positions: {
			xi: safe(()=> lunar.getDayPositionXiDesc(), ''),
			fu: safe(()=> lunar.getDayPositionFuDesc(), ''),
			cai: safe(()=> lunar.getDayPositionCaiDesc(), ''),
			yangGui: safe(()=> lunar.getDayPositionYangGuiDesc(), ''),
			yinGui: safe(()=> lunar.getDayPositionYinGuiDesc(), ''),
		},
		// —— 纳音 / 日禄 / 九星 ——
		nayin: safe(()=> lunar.getDayNaYin(), ''),
		lu: safe(()=> lunar.getDayLu(), ''),
		nineStar: normalizeNineStar(safe(()=> lunar.getDayNineStar(), null)),
		// —— 物候 / 六曜 / 月相 / 数九 / 三伏 ——
		hou: safe(()=> lunar.getHou(), ''),
		liuyao: safe(()=> lunar.getLiuYao(), ''),
		yuexiang: safe(()=> lunar.getYueXiang(), ''),
		shujiu: shujiu ? safe(()=> shujiu.toString(), null) : null,
		fu: fu ? safe(()=> fu.toString(), null) : null,
		// —— 时辰吉凶（12/13 时辰宜忌）——
		times: normalizeTimes(lunar),
		// —— 年神方位（内部 zeri）——
		yearGods: yg,
	};
}

// 建除 / 28 宿 两口径交叉校验（zeri 内部算法 vs lunar）——golden 用，保两源一致。
export function crossCheckDay(y, m, d) {
	const solar = Solar.fromYmd(y, m, d);
	const lunar = solar.getLunar();
	const course = dayCourse(y, m, d);
	return {
		date: `${y}-${m}-${d}`,
		jianchu: { zeri: course.jianChu.name, lunar: safe(()=> lunar.getZhiXing(), '') },
		xiu: { zeri: course.xiu.name, lunar: safe(()=> lunar.getXiu(), '') },
	};
}

export default buildHuangliDay;
