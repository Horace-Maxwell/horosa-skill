// divination/engine/resultShapes.js
// 后端 /chart 响应形状的**唯一契约读法层**(卜卦改进战役 H0)。
//
// 立层缘由(三死链定谳):引擎里散落的裸 result 读取猜错了三处形状,使映点成事/互容/被围
// 三条判读路径**恒不触发**——①antiscionBetween 读 `result.antiscias`(扁平数组),真形状是
// `result.chart.antiscias.{antiscia,cantiscia}`;②mutualReceptionBetween 读 `it.mutual/it.pair`,
// 真形状是 `{planetA:{id,rulerShip},planetB:{...}}`;③isBesieged 期待 `surround.attacks` 为数组,
// 真形状是按行星分桶的 dict。测试 fixture 恰好模拟了同款错误形状=掩盖共犯。
// 此后任何对后端响应新字段的消费**必须**经本层加读法函数,并由 resultShapes.contract.test.js
// 的「:8899 在线形状哨兵」与真形 fixture 双向看守——形状再漂移时哨兵先红,不再静默死链。
//
// ⚠️ 语义陷阱(围攻):`surround.attacks[planet]` 按型分桶——**只有 MarsSaturn 桶是凶围(围攻)**;
// VenusJupiter=围荣(吉)、SunMoon=围耀(贵)、MinDelta=最近邻记录。朴素地「attacks 非空即被围」
// 会把吉围判凶=比恒 false 更糟的反向错判。凶围判定必须走 marsSaturnAttacksOf。
//
// 全部函数:纯读、零副作用、对缺失字段返回空集合(绝不抛)——调用方零判空负担。

// ── 映点/对映点 ──
// 真形状:result.chart.antiscias = { antiscia: [[idA, idB, orb]...], cantiscia: [[idA, idB, orb]...] }
// 统一输出:[{ a, b, orb, kind: 'antiscia' | 'cantiscia' }](id 保持后端 chartId 原文,如 'Sun')
export function antisciaPairsOf(result){
	const box = result && result.chart && result.chart.antiscias;
	if(!box || typeof box !== 'object'){ return []; }
	const out = [];
	['antiscia', 'cantiscia'].forEach((kind) => {
		const rows = Array.isArray(box[kind]) ? box[kind] : [];
		rows.forEach((r) => {
			if(Array.isArray(r) && r.length >= 2){
				out.push({ a: r[0], b: r[1], orb: Number(r[2]) || 0, kind });
			}
		});
	});
	return out;
}

// ── 互容 ──
// 真形状:result.mutuals = { normal: [{planetA:{id,rulerShip[]},planetB:{id,rulerShip[]}}...], abnormal: [...] }
// 统一输出:[{ a, b, shipA[], shipB[], level: 'strong'|'weak'|'mixed', abnormal }]
//  层级口径(1647 传统):domicile(ruler)/exalt 任一侧命中主尊贵=该侧 strong;双侧 strong=strong 互容,
//  双侧皆仅次尊贵(trip/term/face)=weak,一强一弱=mixed。
const STRONG_SHIPS = ['ruler', 'exalt'];
function shipLevel(ships){
	const arr = Array.isArray(ships) ? ships : [];
	return arr.some((s) => STRONG_SHIPS.indexOf(`${s}`.toLowerCase()) >= 0 || `${s}`.toLowerCase() === 'domicile') ? 'strong' : (arr.length ? 'weak' : 'none');
}
export function mutualPairsOf(result){
	const box = result && result.mutuals;
	if(!box || typeof box !== 'object'){ return []; }
	const out = [];
	[['normal', false], ['abnormal', true]].forEach(([bucket, abnormal]) => {
		const rows = Array.isArray(box[bucket]) ? box[bucket] : [];
		rows.forEach((it) => {
			const pa = it && it.planetA;
			const pb = it && it.planetB;
			if(!pa || !pb || !pa.id || !pb.id){ return; }
			const la = shipLevel(pa.rulerShip);
			const lb = shipLevel(pb.rulerShip);
			const level = (la === 'strong' && lb === 'strong') ? 'strong'
				: ((la === 'none' || lb === 'none') ? 'weak' : (la === lb ? la : 'mixed'));
			out.push({ a: pa.id, b: pb.id, shipA: pa.rulerShip || [], shipB: pb.rulerShip || [], level, abnormal });
		});
	});
	return out;
}

// ── 凶围(围攻,仅火土型) ──
// 真形状:result.surround.attacks = { [planetId]: { MarsSaturn: [{id,aspect,delta,...}], VenusJupiter: [...], SunMoon: [...], MinDelta: [...] } }
// 输出:凶围者数组(该行星被火土围的攻方记录);吉围(围荣/围耀)不在此函数——那是正面证词,走 benignSurroundsOf。
export function marsSaturnAttacksOf(result, planetChartId){
	const attacks = result && result.surround && result.surround.attacks;
	if(!attacks || typeof attacks !== 'object'){ return []; }
	const slot = attacks[planetChartId];
	const rows = slot && Array.isArray(slot.MarsSaturn) ? slot.MarsSaturn : [];
	return rows.filter((r) => r && r.id);
}

// 围荣(VenusJupiter)/围耀(SunMoon)正面记录——H4b/H7 证词池消费。
export function benignSurroundsOf(result, planetChartId){
	const attacks = result && result.surround && result.surround.attacks;
	if(!attacks || typeof attacks !== 'object'){ return { venusJupiter: [], sunMoon: [] }; }
	const slot = attacks[planetChartId] || {};
	return {
		venusJupiter: Array.isArray(slot.VenusJupiter) ? slot.VenusJupiter.filter((r) => r && r.id) : [],
		sunMoon: Array.isArray(slot.SunMoon) ? slot.SunMoon.filter((r) => r && r.id) : [],
	};
}

// ── 围攻十六式详断 ──
// 真形状:result.surround.besiegement = [{ target, type, kind, nature, severe?, targetRetro?,
//   besiegers: [{id,aspect,season,retro,delta,restrained[],counterBesieged}], defense?: [...] }]
export function besiegementOf(result){
	const rows = result && result.surround && result.surround.besiegement;
	return Array.isArray(rows) ? rows.filter((r) => r && r.target) : [];
}

// ── 即时相位(每星紧密相位表,按 orb 升序) ──
// 真形状:result.aspects.immediateAsp = { [planetId]: [{id, asp, orb}...] }
export function immediateAspOf(result, planetChartId){
	const box = result && result.aspects && result.aspects.immediateAsp;
	if(!box || typeof box !== 'object'){ return []; }
	const rows = box[planetChartId];
	return Array.isArray(rows) ? rows.filter((r) => r && r.id) : [];
}

// ── 后端恒星命中 ──
// 真形状:result.chart.stars = [{ id, stars: [[starName, sign, signlon, orb, cnName]...] }]
// 输出:{ [planetId]: [{ star, sign, signlon, orb, cn }] }
export function backendStarsOf(result){
	const rows = result && result.chart && result.chart.stars;
	if(!Array.isArray(rows)){ return {}; }
	const out = {};
	rows.forEach((it) => {
		if(!it || !it.id || !Array.isArray(it.stars)){ return; }
		out[it.id] = it.stars.filter((s) => Array.isArray(s) && s.length >= 2)
			.map((s) => ({ star: s[0], sign: s[1], signlon: Number(s[2]) || 0, orb: Number(s[3]) || 0, cn: s[4] || '' }));
	});
	return out;
}

// ── 后端阿拉伯点全套 ──
// 真形状:result.lots = [{ id, type, lon, sign, signlon, ... }](带 lotReversal 口径)
export function backendLotsOf(result){
	const rows = result && result.lots;
	return Array.isArray(rows) ? rows.filter((r) => r && r.id) : [];
}

export default {
	antisciaPairsOf, mutualPairsOf, marsSaturnAttacksOf, benignSurroundsOf,
	besiegementOf, immediateAspOf, backendStarsOf, backendLotsOf,
};
