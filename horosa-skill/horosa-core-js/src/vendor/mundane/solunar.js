// 恒星派世运 Solunars(古籍恒星派篇)。整套体系:恒星黄道(Fagan/Bradley 差值)+
// Campanus 量角化(mundoscope)+角化压倒宫义+休眠盘判定。
// 求根用 chartAtMoment 牛顿迭代(恒星盘直读恒星黄经,差值交后端零近似);
// 角化在 Campanus 宫框上按宫内比例插值成 mundo 度(宫头=卯酉圈等分,忠实量角化口径)。


const norm360 = (x) => (((x % 360) + 360) % 360);
const fwd = (from, to) => norm360(to - from);                  // 前向弧
const angDist = (a, b) => { const d = Math.abs(norm360(a) - norm360(b)); return Math.min(d, 360 - d); };

// 8 盘种:太阳/月亮 各入恒星 摩羯/白羊/巨蟹/天秤。approxMonthDay=迭代初值(恒星入境
// 比回归晚约 24–25 日,取古籍常值近似作种子;收敛由迭代保证,种子仅省步数)。
export const SOLUNAR_TYPES = [
	{ key: 'capsolar', cn: 'Capsolar（太阳入恒星摩羯）', body: 'sun', target: 270, approx: '01-14', span: '年主盘 · 强 12 个月(首季最强)', weightIdx: 0 },
	{ key: 'arisolar', cn: 'Arisolar（太阳入恒星白羊）', body: 'sun', target: 0, approx: '04-14', span: '其后约 3 个月(收束/定时器)', weightIdx: 1 },
	{ key: 'cansolar', cn: 'Cansolar（太阳入恒星巨蟹）', body: 'sun', target: 90, approx: '07-16', span: '次强(约 ¾ 力),前 3 个月', weightIdx: 2 },
	{ key: 'libsolar', cn: 'Libsolar（太阳入恒星天秤）', body: 'sun', target: 180, approx: '10-17', span: '其后约 3 个月(收束/定时器)', weightIdx: 3 },
	{ key: 'caplunar', cn: 'Caplunar（月入恒星摩羯）', body: 'moon', target: 270, approx: null, span: '月主盘 · 4 周(首周最强)', weightIdx: 0 },
	{ key: 'arilunar', cn: 'Arilunar（月入恒星白羊）', body: 'moon', target: 0, approx: null, span: '实务约 1 周', weightIdx: 1 },
	{ key: 'canlunar', cn: 'Canlunar（月入恒星巨蟹）', body: 'moon', target: 90, approx: null, span: '实务约 1 周', weightIdx: 2 },
	{ key: 'liblunar', cn: 'Liblunar（月入恒星天秤）', body: 'moon', target: 180, approx: null, span: '实务约 1 周', weightIdx: 3 },
];

// 相对强度两口径(摩羯–白羊–巨蟹–天秤序;分歧→选项):
export const SOLUNAR_WEIGHTS = {
	scheme_a: { cn: '4-1-3-1（太阳）/ 4-1-1-1（月亮）', sun: [4, 1, 3, 1], moon: [4, 1, 1, 1] },
	scheme_b: { cn: '4-1-2-1（原始口径）', sun: [4, 1, 2, 1], moon: [4, 1, 2, 1] },
};

// 角化容许度三档(角 3° 内事件多发,<1° 尤强;流年盘 2°;背景 10°)。
export const ANGULARITY_ORBS = [
	{ key: 'ingress', cn: '入境盘 3°', orb: 3 },
	{ key: 'transit', cn: '流年盘 2°', orb: 2 },
	{ key: 'background', cn: '背景 10°', orb: 10 },
];

// 行星临角断语(古籍口径逐条,零人名)。
export const PLANET_ANGULAR_OMEN = {
	saturn: { tone: 'malefic', text: '重大伤亡、哀悼、艰难与紧缩' },
	mars: { tone: 'malefic', text: '火灾、暴力、毁灭性冲突' },
	venus: { tone: 'benefic', text: '和好、庆典、愉悦之事' },
	jupiter: { tone: 'benefic', text: '扩张顺遂;并且唯一对暴雨洪水有主导性' },
	uranus: { tone: 'upheaval', text: '剧变、颠覆、灾难性突发' },
	pluto: { tone: 'upheaval', text: '剧变、颠覆、深层重构' },
	neptune: { tone: 'confusion', text: '群体混乱、恐慌、迷雾' },
	sun: { tone: 'neutral', text: '元首/权力焦点(与土星皆在角且互无相位=元首之死复合判据)' },
	moon: { tone: 'neutral', text: '民情波动焦点' },
	mercury: { tone: 'neutral', text: '消息、交通、舆论焦点' },
};
export const OMEN_COMBOS = [
	'金星与土星（或冥王）同时临角 → 爱与死并见、巨大丧失',
	'土星与太阳皆在角且彼此无相位 → 元首之死的复合判据',
];

// ── Campanus mundoscope 角化 ──
// 盘按 Campanus(hsys=10)排;宫头即卯酉圈十二等分 → mundo 位置 = (宫序−1)×30 +
// 宫内黄经比例×30;四轴 mundo = 0(ASC)/90(IC)/180(DSC)/270(MC)。角距=到四轴 mundo 最小距。
const AXIS_MUNDO = [
	{ key: 'asc', cn: '上升', pos: 0 },
	{ key: 'ic', cn: '天底', pos: 90 },
	{ key: 'dsc', cn: '下降', pos: 180 },
	{ key: 'mc', cn: '天顶', pos: 270 },
];

export function mundoPositionOf(planet, houses){
	if(!planet || planet.lon == null || !planet.house || !houses){ return null; }
	const h = houses[planet.house];
	const hn = houses[(planet.house % 12) + 1];
	if(!h || h.lon == null || !hn || hn.lon == null){ return null; }
	const width = fwd(h.lon, hn.lon) || 30;
	const frac = Math.min(Math.max(fwd(h.lon, planet.lon) / width, 0), 1);
	return norm360((planet.house - 1) * 30 + frac * 30);
}

const ANGULARITY_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'];

export function computeAngularity(facts, orb){
	if(!facts || !facts.planets || !facts.houses){ return null; }
	const useOrb = orb || 3;
	const rows = [];
	ANGULARITY_KEYS.forEach((k) => {
		const p = facts.planets[k];
		const mundo = mundoPositionOf(p, facts.houses);
		if(mundo == null){ return; }
		let best = null;
		AXIS_MUNDO.forEach((ax) => {
			const d = angDist(mundo, ax.pos);
			if(!best || d < best.dist){ best = { axis: ax.key, axisCn: ax.cn, dist: d }; }
		});
		rows.push({
			planet: k, mundo, axis: best.axis, axisCn: best.axisCn, dist: best.dist,
			foreground: best.dist <= useOrb, strong: best.dist <= 1,
			omen: PLANET_ANGULAR_OMEN[k] || null,
		});
	});
	rows.sort((a, b) => a.dist - b.dist);
	return { rows, orb: useOrb };
}

// 休眠盘:无星在角(orb 内)→ 无信息,可略过(可计算判定)。
export function isDormantChart(facts, orb){
	const a = computeAngularity(facts, orb || 3);
	if(!a){ return null; }
	return !a.rows.some((r) => r.foreground);
}

// 元首之死复合判据:土与日皆角化(≤orb)且彼此无主相位(0/60/90/120/180 ±3° 外)。
export function rulerDeathSignature(facts, orb){
	const a = computeAngularity(facts, orb || 3);
	if(!a){ return false; }
	const sun = a.rows.find((r) => r.planet === 'sun');
	const sat = a.rows.find((r) => r.planet === 'saturn');
	if(!sun || !sat || !sun.foreground || !sat.foreground){ return false; }
	const ps = facts.planets.sun; const pt = facts.planets.saturn;
	if(!ps || !pt || ps.lon == null || pt.lon == null){ return false; }
	const d = angDist(ps.lon, pt.lon);
	const inAspect = [0, 60, 90, 120, 180].some((ang) => Math.abs(d - ang) <= 3);
	return !inAspect;
}

// ── 恒星入境求根(牛顿迭代;盘=恒星黄道 fagan_bradley,直读恒星黄经零差值近似)──
const MEAN_SPEED = { sun: 0.98565, moon: 13.17640 };
const CHART_ID = { sun: 'Sun', moon: 'Moon' };

function lonOf(chart, body){
	const objs = (chart && chart.chart && chart.chart.objects) || [];
	const o = objs.find((x) => x.id === CHART_ID[body]);
	return o && o.lon != null ? o.lon : null;
}

function shiftMoment(momentStr, days){
	const ms = new Date(String(momentStr).replace(/-/g, '/')).getTime() + days * 86400000;
	const d = new Date(ms);
	const pad = (n) => (n < 10 ? '0' + n : '' + n);
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// 求 year 年(或 seedMoment 起)body 入恒星 target 的精确时刻;返回 {moment, chart} 或 null。
// fieldsLike 应含地点;本函数强制 zodiacal=1 + fagan_bradley + hsys=Campanus(10)。
export function describeSolunar(typeKey, weightScheme){
	const t = SOLUNAR_TYPES.find((x) => x.key === typeKey);
	if(!t){ return null; }
	const w = SOLUNAR_WEIGHTS[weightScheme] || SOLUNAR_WEIGHTS.scheme_a;
	const weights = t.body === 'sun' ? w.sun : w.moon;
	return { ...t, weight: weights[t.weightIdx], weightsCn: w.cn };
}

export default { SOLUNAR_TYPES, SOLUNAR_WEIGHTS, ANGULARITY_ORBS, PLANET_ANGULAR_OMEN, computeAngularity, isDormantChart, rulerDeathSignature, describeSolunar, mundoPositionOf };