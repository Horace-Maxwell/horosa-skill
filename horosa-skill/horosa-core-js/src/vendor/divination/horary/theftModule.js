// divination/horary/theftModule.js
// 盗窃 / 失物 / 走失 复合判断（构建清单 §3.4 十一步 + Sahl §7.10–7.22）。
// 失主=上升/命主+月亮；盗贼=7宫主；赃物=2宫主；藏匿地=4宫。每步独立可显示。
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { termRulerAt } from '../data/dignities.js';
import { decanImageAt } from '../data/decanImages.js';
import { DIR_BY_ELEMENT, dirByMoonQuadrant } from '../data/directions.js';
import { THIEF_BY_PLANET } from './describe.js';
import { signsBetween, isEven } from '../engine/utils.js';
import { aspectBetween, applyingAspects } from '../engine/aspectsEngine.js';
import { isViaCombusta } from '../engine/moon.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || '—'; }

const MATERIAL_BY_TERM = {
	saturn: '旧物 / 农具 / 建材 / 廉价之物', jupiter: '金银 / 锦缎 / 财宝', mars: '铁器 / 锻造物 / 染色物',
	venus: '珠宝 / 女性饰品 / 香水', mercury: '书册 / 账本 / 钱币',
};
const HANDS_BY_PLANET = {
	jupiter: '落入贵族 / 体面之人手中', mars: '落入奴仆 / 自由人 / 鲁莽者手中', saturn: '落入老者 / 下层人手中',
	venus: '落入女性手中（前段贵妇、后段婢女）', mercury: '落入年轻商人 / 文书之手', sun: '落入有权位者手中', moon: '落入平民 / 妇人手中',
};
const PLACE_BY_HOUSEPLANET = {
	saturn: '阴暗、潮湿、肮脏或高处', jupiter: '祈祷室 / 体面整洁处', mars: '厨房 / 炉灶 / 铁器火源处',
	sun: '主人房 / 封闭显眼处', venus: '女人房 / 妆奁处', mercury: '书房 / 粮仓 / 装饰处', moon: '井 / 蓄水池 / 近水处',
};
const RESULT_BY_MOON_APPLY = {
	mars: '月入相火星 → 盗贼被抓且受刑 / 见血', saturn: '月入相土星 → 自杀 / 丢弃赃物 / 被捕',
	jupiter: '月入相木星 → 安全寻回 / 和平归还', venus: '月入相金星 → 安全逃脱 / 和平归还',
};

export function runTheft(facts){
	const steps = [];
	const add = (label, text, polarity) => steps.push({ label, text, polarity: polarity || 'neutral' });

	const moon = facts.planets.moon;
	const lord1 = facts.meta.ascSign && SIGNS[facts.meta.ascSign] ? SIGNS[facts.meta.ascSign].domicile : null;
	const thief = facts.houses[7] && facts.houses[7].ruler;        // 7宫主=盗贼
	const obj = facts.houses[2] && facts.houses[2].ruler;          // 2宫主=赃物
	const h4 = facts.houses[4];                                    // 4宫=藏匿地
	const h4planets = (h4 && h4.planets) || [];

	// 1) 能否找回
	let recover = '证据不足，难以确断；参考裁决页倾向。';
	let recoverPol = 'neutral';
	if(lord1 && thief){
		const a = aspectBetween(facts, lord1, thief);
		if(a && a.applying){ recover = `命主 ${cn(lord1)} 与盗贼星 ${cn(thief)} 入相位 → 能追到盗贼 / 失物可寻。`; recoverPol = 'positive'; }
	}
	if(moon){
		if([7, 8].indexOf(moon.house) >= 0 || isViaCombusta(moon.lon)){ recover = '月落 7/8 宫或燃烧之路 → 多半找不回。'; recoverPol = 'negative'; }
		else if([1, 10].indexOf(moon.house) >= 0){ recover = '月落 1/10 宫 → 较有望寻回。'; recoverPol = 'positive'; }
	}
	add('① 能否找回', recover, recoverPol);

	// 2) 失物 / 藏匿地点（4宫星座元素 + 宫内星）
	const h4sign = h4 && h4.sign;
	const el = h4sign && SIGNS[h4sign] ? SIGNS[h4sign].element : null;
	let placeText = el ? `大环境：${(DIR_BY_ELEMENT[el] || {}).terrain || '—'}` : '4宫信息不足。';
	const placePlanet = h4planets.find((k) => PLACE_BY_HOUSEPLANET[k]);
	if(placePlanet) placeText += `；屋内：${PLACE_BY_HOUSEPLANET[placePlanet]}（4宫 ${cn(placePlanet)}）`;
	add('② 失物地点', placeText);

	// 3) 落入何人手（4宫星体）
	const handPlanet = h4planets.find((k) => HANDS_BY_PLANET[k]) || thief;
	add('③ 落入谁手', handPlanet ? HANDS_BY_PLANET[handPlanet] || `与 ${cn(handPlanet)} 相关之人` : '难定。');

	// 4) 失物材质（月亮界主星）
	if(moon){
		const term = termRulerAt(moon.lon);
		add('④ 失物材质', `月亮界主星 ${cn(term)} → ${MATERIAL_BY_TERM[term] || '杂物'}`);
	}

	// 5) 盗贼外貌（上升所落面 + 7宫主行星外貌）
	let look = '';
	if(facts.meta.ascSign && facts.meta.ascDegree !== null){
		const img = decanImageAt(facts.meta.ascSign, facts.meta.ascDegree);
		if(img) look += `上升所落面象：${img}`;
	}
	if(thief && THIEF_BY_PLANET[thief]) look += `${look ? '；' : ''}盗贼星 ${cn(thief)}：${THIEF_BY_PLANET[thief]}`;
	add('⑤ 盗贼外貌', look || '信息不足。');

	// 6) 年龄 / 性别（东出西入 + 行星阴阳）
	if(thief && facts.planets[thief]){
		const tp = facts.planets[thief];
		const age = tp.orientality === 'oriental' ? '偏年轻' : (tp.orientality === 'occidental' ? '偏年长' : '中年');
		const gender = (PLANETS[thief] || {}).gender === 'feminine' ? '女性倾向' : ((PLANETS[thief] || {}).gender === 'masculine' ? '男性倾向' : '不定');
		add('⑥ 年龄性别', `${age}；${gender}${tp.retro ? '（逆行/停滞 → 偏年长）' : ''}`);
	}

	// 7) 是否多人（月→水星 星座数奇偶；盗贼在双体座）
	if(moon && facts.planets.mercury){
		const n = signsBetween(moon.lon, facts.planets.mercury.lon);
		const multi = isEven(n);
		let t = `月亮→水星 星座数 ${n}（${multi ? '偶=多件/多人' : '奇=单件/单人'}）`;
		if(thief && facts.planets[thief] && SIGNS[facts.planets[thief].sign] && SIGNS[facts.planets[thief].sign].bicorporeal) t += '；盗贼星落双体座 → 偏多人';
		add('⑦ 是否多人', t);
	}

	// 8) 陌生或熟人（日月注视1宫 / 盗贼在1宫 / 自然征象身份）
	let familiar = '偏陌生人。';
	if(thief && facts.planets[thief]){
		if(facts.planets[thief].house === 1) familiar = '盗贼星落 1 宫 → 家中人 / 亲近者。';
		const natural = (PLANETS[thief] || {}).natural_sig;
		if(natural && natural.length) familiar += `（${cn(thief)} 自然代表：${natural.join('/')}）`;
	}
	add('⑧ 生人熟人', familiar);

	// 9) 方向（月亮四轴 + 元素）
	if(moon){
		const dq = dirByMoonQuadrant(moon.house);
		const de = el ? (DIR_BY_ELEMENT[el] || {}).dir : null;
		add('⑨ 方向', `月亮象限方位：${dq}${de ? `；元素方位：${de}` : ''}`);
	}

	// 10) 逃跑 / 找回结果（月入相 火/土/吉）
	if(moon){
		const ma = applyingAspects(facts, 'moon');
		const hit = ['mars', 'saturn', 'jupiter', 'venus'].find((k) => ma.some((a) => a.other === k));
		add('⑩ 结果', hit ? RESULT_BY_MOON_APPLY[hit] : '月无明显入相 → 结果不定；月减光易抓、增光难抓。', hit === 'mars' || hit === 'saturn' ? 'negative' : (hit ? 'positive' : 'neutral'));
	}

	// 11) 时间见「应期」。
	add('⑪ 时间', '见右栏「时间方位」页的应期推算。');

	return { steps, thief, obj };
}

export default runTheft;
