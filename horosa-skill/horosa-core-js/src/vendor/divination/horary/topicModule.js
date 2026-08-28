// divination/horary/topicModule.js
// 主题深化：按问题类别给「征象星对照」式专题判读（诉讼胜负 / 买房四角 / 怀孕）。
// 纯派生自 facts（宫主 + 单星状态），不改动通用完成法/裁决；供右栏「裁决」专题卡 + AI 快照。
import { PLANETS } from '../data/planets.js';
import { SIGNS } from '../data/signs.js';
import { aspectBetween } from '../engine/aspectsEngine.js';
import { mutualReceptionBetween } from '../engine/reception.js';
import { DIR_BY_ELEMENT } from '../data/directions.js';
import { signOfLon } from '../data/signs.js';
import { lotDispositor } from '../data/lots.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || '—'; }
const ANG_BONUS = { angular: 2, succedent: 0, cadent: -1.5 };

// 综合力量：庙旺尊贵分 + 角宫加成 − 逆行/燃烧减损。用于「谁更强」对照。
function strengthOf(facts, key){
	const p = key && facts.planets[key];
	if(!p) return null;
	let s = (typeof p.dignityScore === 'number') ? p.dignityScore : 0;
	s += (ANG_BONUS[p.angularity] || 0);
	if(p.retro) s -= 1.5;
	if(p.combustion === 'combust') s -= 3;
	else if(p.combustion === 'cazimi') s += 3;
	return s;
}
function lordOf(facts, house){ return facts.houses[house] && facts.houses[house].ruler; }
function stateWord(facts, key){
	const p = key && facts.planets[key];
	if(!p) return '不明';
	const bits = [];
	if(p.dignityScore >= 4) bits.push('有力'); else if(p.dignityScore <= -4) bits.push('失势'); else bits.push('中平');
	if(p.angularity === 'angular') bits.push('角宫'); else if(p.angularity === 'cadent') bits.push('果宫');
	if(p.retro) bits.push('逆行');
	if(p.combustion === 'combust') bits.push('燃烧');
	return bits.join('·');
}
function cmpLine(facts, aKey, aLabel, bKey, bLabel){
	const sa = strengthOf(facts, aKey);
	const sb = strengthOf(facts, bKey);
	if(sa === null || sb === null) return { polarity: 'neutral', text: `${aLabel}/${bLabel} 征象星不全，无法直接对照强弱。` };
	const diff = sa - sb;
	const who = Math.abs(diff) < 1.5 ? '双方旗鼓相当' : (diff > 0 ? `${aLabel}占优` : `${bLabel}占优`);
	const pol = Math.abs(diff) < 1.5 ? 'neutral' : (diff > 0 ? 'positive' : 'negative');
	return { polarity: pol, text: `${aLabel}（${cn(aKey)}·${stateWord(facts, aKey)}） 对 ${bLabel}（${cn(bKey)}·${stateWord(facts, bKey)}） → ${who}。` };
}

export function buildTopicDeepening(facts, category, opts){
	if(category === 'lawsuit'){
		const l1 = lordOf(facts, 1); const l7 = lordOf(facts, 7); const l10 = lordOf(facts, 10);
		const lines = [cmpLine(facts, l1, '本方（1宫）', l7, '对方（7宫）')];
		if(l10) lines.push({ polarity: 'neutral', text: `法官/裁决 = 10宫主 ${cn(l10)}（${stateWord(facts, l10)}）；其偏向哪方之征象星接纳，多主判向该方。` });
		return { title: '诉讼胜负（1宫本方 vs 7宫对方，10宫法官）', lines };
	}
	if(category === 'property'){
		// Sahl 四角：1宫买方 / 4宫标的(田宅) / 7宫卖方 / 10宫成交(价/结果)。
		const l1 = lordOf(facts, 1); const l4 = lordOf(facts, 4); const l7 = lordOf(facts, 7); const l10 = lordOf(facts, 10);
		const lines = [
			{ polarity: 'neutral', text: `买方＝1宫主 ${cn(l1)}（${stateWord(facts, l1)}）；卖方＝7宫主 ${cn(l7)}（${stateWord(facts, l7)}）。` },
			{ polarity: (strengthOf(facts, l4) >= 0 ? 'positive' : 'negative'), text: `标的（田宅）＝4宫主 ${cn(l4)}（${stateWord(facts, l4)}）→ ${strengthOf(facts, l4) >= 0 ? '房产/地块状况良好' : '房产/地块有瑕或不宜'}。` },
			{ polarity: (strengthOf(facts, l10) >= 0 ? 'positive' : 'negative'), text: `成交/价格＝10宫主 ${cn(l10)}（${stateWord(facts, l10)}）→ ${strengthOf(facts, l10) >= 0 ? '价钱/结果趋顺' : '价钱/结果多波折'}。` },
		];
		return { title: '买房四角（1买方·4标的·7卖方·10成交）', lines };
	}
	if(category === 'pregnancy'){
		const l5 = lordOf(facts, 5);
		const asc = facts.meta.ascSign;
		const ascGender = SIGNS[asc] ? SIGNS[asc].gender : null;  // masculine/feminine
		const benefic = ['jupiter', 'venus'].filter((k) => facts.planets[k] && facts.planets[k].dignityScore > -4);
		const lines = [
			{ polarity: (strengthOf(facts, l5) >= 0 ? 'positive' : 'negative'), text: `子嗣＝5宫主 ${cn(l5)}（${stateWord(facts, l5)}）＋月亮/木星/金星为自然征象。` },
			{ polarity: (benefic.length ? 'positive' : 'neutral'), text: benefic.length ? `吉星 ${benefic.map(cn).join('/')} 状态尚可 → 助孕育之象。` : '吉星（木星/金星）受损 → 孕育征象偏弱，宜谨慎。' },
		];
		if(ascGender) lines.push({ polarity: 'neutral', text: `性别参考（仅一征象，勿单凭）：上升座属${ascGender === 'masculine' ? '阳（偏男）' : '阴（偏女）'}，须合5宫主/月亮阴阳同断。` });
		return { title: '怀孕（5宫子嗣 + 月木金自然征象）', lines };
	}
	// ── B1–B12 专题扩充（2026-07 批2;既有三题在上方保持字节不变）──
	if(category === 'health'){
		return buildDecumbiture(facts);
	}
	if(category === 'wealth'){
		const l1 = lordOf(facts, 1); const l2 = lordOf(facts, 2);
		const lines = [
			{ polarity: (strengthOf(facts, l2) >= 0 ? 'positive' : 'negative'), text: `财帛＝2宫主 ${cn(l2)}（${stateWord(facts, l2)}）;福点亦作财之征。` },
			{ polarity: 'neutral', text: '取效方向：2宫主入相位1宫主 → 钱主动来;1宫主入相位2宫主 → 须主动求取。' },
			{ polarity: 'neutral', text: `讨债/借贷：债务人＝7宫主 ${cn(lordOf(facts, 7))}，其钱＝7之2＝本盘8宫主 ${cn(lordOf(facts, 8))}（转宫口径）。` },
		];
		return { title: '钱财能否得（2宫财帛·B2）', lines };
	}
	if(category === 'message'){
		const l3 = lordOf(facts, 3);
		const merc = facts.planets.mercury;
		const mercBad = merc && (merc.retro || merc.combustion === 'combust' || merc.dignityScore <= -4);
		const moonVoc = facts.planets.moon && facts.planets.moon.isVOC;
		const lines = [
			{ polarity: (strengthOf(facts, l3) >= 0 ? 'positive' : 'negative'), text: `消息＝3宫主 ${cn(l3)}（${stateWord(facts, l3)}）＋水星（信息自然象征）。` },
			{ polarity: mercBad ? 'negative' : 'positive', text: mercBad ? `水星受损（${stateWord(facts, 'mercury')}）→ 消息恐假/坏/迟。` : '水星状态尚可 → 消息偏真/可达。' },
		];
		if(moonVoc) lines.push({ polarity: 'negative', text: '月亮空亡 → 多主「无下文」。' });
		return { title: '消息真假·书信能否达（3宫·B3）', lines };
	}
	if(category === 'death'){
		const l8 = lordOf(facts, 8); const l1 = lordOf(facts, 1); const l2 = lordOf(facts, 2);
		const lines = [
			{ polarity: 'neutral', text: `遗产＝8宫主 ${cn(l8)}（${stateWord(facts, l8)}）;能否得看其与 1/2 宫主（${cn(l1)}/${cn(l2)}）的入相位与容纳。` },
			{ polarity: (strengthOf(facts, l8) >= 0 ? 'positive' : 'negative'), text: strengthOf(facts, l8) >= 0 ? '8宫主未受重克 → 承得之象偏顺。' : '8宫主受克/被阻 → 不得或缩水。' },
		];
		return { title: '遗产能否得（8宫·B8）', lines };
	}
	if(category === 'travel'){
		const l9 = lordOf(facts, 9); const l1 = lordOf(facts, 1);
		const moonOk = facts.planets.moon && facts.planets.moon.dignityScore > -4 && facts.planets.moon.combustion !== 'combust';
		const lines = [
			cmpLine(facts, l1, '行人（1宫）', l9, '旅程（9宫）'),
			{ polarity: moonOk ? 'positive' : 'negative', text: moonOk ? '月亮未受重克 → 途中偏顺。' : '月亮受克 → 途中多阻/险。' },
			{ polarity: 'neutral', text: '出国移居：1宫主与9宫主入相位、9宫主得位 → 可成且佳。' },
		];
		return { title: '旅行/出国顺否（9宫·B9）', lines };
	}
	if(category === 'career'){
		const l1 = lordOf(facts, 1); const l10 = lordOf(facts, 10);
		const lines = [
			cmpLine(facts, l1, '求职者（1宫）', l10, '职位/上司（10宫）'),
			{ polarity: 'neutral', text: '取效方向：10宫主入相位1宫主 → 职位主动来;1宫主入相位10宫主 → 须争取。受阻/撤回 → 落空。' },
			{ polarity: 'neutral', text: '选举/竞争：对手＝7宫主，比较双方尊贵，再看 10宫（权威/选民）容纳谁。' },
		];
		return { title: '求职升迁·选举竞争（10宫·B10）', lines };
	}
	if(category === 'hope'){
		const l1 = lordOf(facts, 1); const l11 = lordOf(facts, 11);
		return {
			title: '愿望能否实现（11宫·B11）',
			lines: [
				cmpLine(facts, l1, '问者（1宫）', l11, '所愿（11宫）'),
				{ polarity: 'neutral', text: '1宫主与11宫主（或所愿之事本宫主）入相位 → 如愿;月亮吉相有助。' },
			],
		};
	}
	if(category === 'enemy'){
		const l1 = lordOf(facts, 1); const l12 = lordOf(facts, 12);
		const l1p = facts.planets[l1];
		const trapped = l1p && l1p.house === 12;
		return {
			title: '暗敌·囚禁能否脱（12宫·B12）',
			lines: [
				cmpLine(facts, l1, '本人（1宫）', l12, '暗敌/禁锢（12宫）'),
				{ polarity: trapped ? 'negative' : 'neutral', text: trapped ? '1宫主落12宫 → 受困之象。' : '1宫主不居12宫 → 未成困局。' },
				{ polarity: 'neutral', text: '脱困之征：1宫主离开凶相、与吉星入相位、得位。' },
			],
		};
	}
	if(category === 'lost'){
		return buildLostObject(facts, opts);
	}
	// ── [H6] 三新专题:婚姻分科 / 走失活物 / 通用买卖 ──
	if(category === 'marriage'){
		return buildMarriageTopic(facts);
	}
	if(category === 'lost_animal'){
		return buildLostAnimal(facts);
	}
	if(category === 'trade'){
		const l1 = lordOf(facts, 1); const l7 = lordOf(facts, 7); const l10 = lordOf(facts, 10); const l4 = lordOf(facts, 4);
		const lines = [
			cmpLine(facts, l1, '买方（1宫）', l7, '卖方（7宫）'),
			{ polarity: (strengthOf(facts, l4) >= 0 ? 'positive' : 'negative'), text: `货物/标的＝4宫主 ${cn(l4)}（${stateWord(facts, l4)}）→ ${strengthOf(facts, l4) >= 0 ? '货物品质尚可' : '货物有瑕/名不副实'}。` },
			{ polarity: (strengthOf(facts, l10) >= 0 ? 'positive' : 'negative'), text: `价格/成交＝10宫主 ${cn(l10)}（${stateWord(facts, l10)}）→ ${strengthOf(facts, l10) >= 0 ? '价钱公道、成交趋顺' : '价钱纠葛、成交多波折'}。` },
			{ polarity: 'neutral', text: '成交之征：1宫主与7宫主入相位（尤有接纳/传递）;两主刑冲无接纳/被阻 → 谈不拢。' },
		];
		return { title: '通用买卖四角（1买·7卖·4货·10价）', lines };
	}
	return null;
}

// ── [H6] 婚姻分科:两主接通 + 金星(婚姻自然征象) + 日月配合(男女光体) + 7 宫互容专查。──
function buildMarriageTopic(facts){
	const l1 = lordOf(facts, 1); const l7 = lordOf(facts, 7);
	const lines = [cmpLine(facts, l1, '问者（1宫）', l7, '对象（7宫）')];
	const venus = facts.planets.venus;
	const venusBad = venus && (venus.retro || venus.combustion === 'combust' || venus.dignityScore <= -4);
	lines.push({ polarity: venusBad ? 'negative' : 'positive', text: venusBad ? `金星（婚姻自然征象）受损（${stateWord(facts, 'venus')}）→ 情缘之象偏弱。` : `金星（婚姻自然征象）状态尚可（${stateWord(facts, 'venus')}）→ 有利情缘。` });
	// 日月配合:传统以日=男方光体、月=女方光体,两光吉相=阴阳相谐。
	const sm = aspectBetween(facts, 'sun', 'moon');
	if(sm && [0, 60, 120].indexOf(sm.angle) >= 0){
		lines.push({ polarity: 'positive', text: `日月${sm.angle === 0 ? '合相' : (sm.angle === 60 ? '六合' : '三合')}（男女光体相谐）→ 阴阳相合,婚象得助。` });
	}else if(sm && [90, 180].indexOf(sm.angle) >= 0){
		lines.push({ polarity: 'negative', text: `日月${sm.angle === 90 ? '四分' : '对分'}（男女光体相违）→ 两家/两人之间多扞格。` });
	}else{
		lines.push({ polarity: 'neutral', text: '日月无主相位 → 光体配合中平,以两主接通为断。' });
	}
	// 7 宫互容专查(契约层 mutualPairsOf;两主互容=婚成有力之征)。
	if(l1 && l7 && l1 !== l7){
		const mu = mutualReceptionBetween(facts, l1, l7);
		if(mu){
			const strong = mu.some((x) => x.strong);
			lines.push({ polarity: 'positive', text: `两主互容（${strong ? '庙旺级·有力' : '次尊贵级'}）→ 彼此接纳,婚象大利${strong ? ',几可独立成事' : ''}。` });
		}
	}
	return { title: '婚姻分科（两主接通·金星·日月配合·互容）', lines };
}

// ── [H6] 走失活物:小活物(猫犬禽)＝6 宫;大牲畜(马牛等驮畜)＝12 宫——两宫对照并给方位。──
function buildLostAnimal(facts){
	const l6 = lordOf(facts, 6); const l12 = lordOf(facts, 12);
	const dirLine = (key, label) => {
		const pp = key && facts.planets[key];
		const el = pp && SIGNS[pp.sign] ? SIGNS[pp.sign].element : null;
		const d = el && DIR_BY_ELEMENT[el];
		return d ? `${label}征象星落${el === 'fire' ? '火' : (el === 'earth' ? '土' : (el === 'air' ? '风' : '水'))}象 → 方位偏${d.dir}（${d.terrain}）` : null;
	};
	const lines = [
		{ polarity: 'neutral', text: `小活物（猫犬禽类）＝6宫主 ${cn(l6)}（${stateWord(facts, l6)}）;大牲畜（马牛驮畜）＝12宫主 ${cn(l12)}（${stateWord(facts, l12)}）。` },
		{ polarity: 'neutral', text: '寻回之征：该征象星与 1宫主/月亮入相位（尤有容纳）;征象星落角宫 → 未走远。' },
	];
	const d6 = dirLine(l6, '小活物'); if(d6){ lines.push({ polarity: 'neutral', text: d6 + '。' }); }
	const d12 = dirLine(l12, '大牲畜'); if(d12){ lines.push({ polarity: 'neutral', text: d12 + '。' }); }
	const p6 = l6 && facts.planets[l6];
	if(p6 && (p6.house === 8 || p6.house === 12)){ lines.push({ polarity: 'negative', text: '小活物征象星落 8/12 宫 → 有失亡/被困之虞。' }); }
	return { title: '走失活物（6宫小活物·12宫大牲畜）', lines };
}

// ── B6 疾病 decumbiture + 危象日（月亮自本位每 45° 一站;90°/180° 为最凶险节点）。
// 天数按本盘月亮真实日速折算（≈45°/13.2°日≈3.4天;90° 危象≈6.8–7 天与古法「约七日一危」相合）。──
function buildDecumbiture(facts){
	const l1 = lordOf(facts, 1); const l6 = lordOf(facts, 6);
	const moon = facts.planets.moon;
	const lines = [
		{ polarity: (strengthOf(facts, l1) >= 0 ? 'positive' : 'negative'), text: `患者＝1宫主 ${cn(l1)}（${stateWord(facts, l1)}）＋月亮;疾病＝6宫主 ${cn(l6)}（${stateWord(facts, l6)}）。` },
		{ polarity: 'neutral', text: `医者＝7宫主 ${cn(lordOf(facts, 7))};疗法＝10宫主 ${cn(lordOf(facts, 10))};结局看 4宫与月亮末相位;凶征＝入相位 6/8 宫主或凶星。` },
	];
	let criticalDays = null;
	if(moon && moon.speed){
		const v = Math.abs(moon.speed) || 13.1767;
		const stations = [
			{ arc: 45, kind: '判断日' }, { arc: 90, kind: '危象日(刑·最凶险)' }, { arc: 120, kind: '判断日(拱)' },
			{ arc: 135, kind: '判断日' }, { arc: 180, kind: '危象日(冲·最凶险)' }, { arc: 225, kind: '判断日' },
			{ arc: 270, kind: '危象日(刑·再临)' }, { arc: 315, kind: '判断日' },
		];
		criticalDays = stations.map((st) => ({ ...st, days: Math.round((st.arc / v) * 10) / 10 }));
		lines.push({ polarity: 'neutral', text: `危象日程（自起病盘月亮本位起算）：${criticalDays.map((c) => `${c.arc}°≈第${c.days}天(${c.kind})`).join('；')}。危象日月亮所遇吉/凶相预示该日转折。` });
	}
	return { title: '疾病 decumbiture + 危象日（6宫·B6）', lines, criticalDays };
}

// ── 失物（非盗窃）专题：象征星元素 → 场所类型;宫位 → 方位/家中;月亮指线索。──
const LOST_PLACE_BY_ELEMENT = {
	fire: '近火/炉灶/高处/南向之所',
	earth: '地面/田野/地板下/泥土附近',
	air: '高处/空中/墙上/窗架通风处',
	water: '近水/低湿处/水管盥洗/北向之所',
};
function buildLostObject(facts, opts){
	const l2 = lordOf(facts, 2);
	const p2 = l2 && facts.planets[l2];
	const el = p2 && SIGNS[p2.sign] ? SIGNS[p2.sign].element : null;
	const near = p2 && p2.angularity === 'angular';
	const lines = [
		{ polarity: 'neutral', text: `失物＝2宫主 ${cn(l2)}（${stateWord(facts, l2)}）;以最能描述该物之星为准（活物另按「走失活物」类）。` },
		{ polarity: near ? 'positive' : 'neutral', text: near ? '失物象征星落角宫 → 在近处/易得。' : (p2 && p2.angularity === 'cadent' ? '失物象征星落果宫 → 远/难寻或被移动。' : '失物象征星落续宫 → 不远不近。') },
	];
	if(el) lines.push({ polarity: 'neutral', text: `场所类型（象征星元素=${el}）：${LOST_PLACE_BY_ELEMENT[el]}。` });
	if(p2 && (p2.house === 8 || p2.house === 12)) lines.push({ polarity: 'negative', text: '象征星落 8/12 宫 → 难寻或被藏匿。' });
	// [H6] 福点=失物之所在(传统失物三征之一):按 pofReversal 口径算落座+定位星。
	const asc = facts.meta.ascLon; const sun = facts.planets.sun && facts.planets.sun.lon; const moon = facts.planets.moon && facts.planets.moon.lon;
	if(asc != null && sun != null && moon != null){
		const useNight = !!(opts && opts.pofReversal) && !facts.meta.isDiurnal;
		const pofLon = (((useNight ? (asc + sun - moon) : (asc + moon - sun)) % 360) + 360) % 360;
		const pofSign = SIGNS[signOfLon(pofLon)];
		const disp = lotDispositor(pofLon);
		const pofEl = pofSign && pofSign.element;
		lines.push({ polarity: 'neutral', text: `福点（失物之所）落${pofSign ? pofSign.cn : '—'}座 ${(pofLon % 30).toFixed(1)}°${disp ? '·定位星' + cn(disp) : ''}${pofEl ? '（' + LOST_PLACE_BY_ELEMENT[pofEl] + '）' : ''}。` });
	}
	// [H6] 月亮方位(线索之向):月亮所落元素定方向。
	const pm = facts.planets.moon;
	if(pm && SIGNS[pm.sign]){
		const d = DIR_BY_ELEMENT[SIGNS[pm.sign].element];
		if(d){ lines.push({ polarity: 'neutral', text: `月亮（线索）方位：偏${d.dir}（${d.terrain}）。` }); }
	}
	lines.push({ polarity: 'neutral', text: '寻回之征：失物象征星与 1宫主/月亮入相位（尤有容纳）;月亮入相位失物星 → 有线索。' });
	return { title: '失物寻回（非盗窃·2宫动产）', lines };
}

export default buildTopicDeepening;
