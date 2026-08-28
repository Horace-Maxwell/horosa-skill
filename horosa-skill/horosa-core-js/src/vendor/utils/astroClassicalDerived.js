// 古典 tab「衍化」四组件(派生宫转宫/七气候带/显赫计分/世界范式盘)的计算纯函数 + 快照行构建 —— 单一真值源。
// 🔴 零组件依赖轻文件:astroAiSnapshot(AI 快照链)与四个 astro 组件都要消费;AI 核 import 组件文件会把
// 组件树吃进自己的 chunk(46/47 回灌案),故计算层全部住这里,组件只 import 计算函数回去(只移不改)。
// 🔴 快照 opt-in 铁律:四段仅在 buildAstroSnapshotContent 收到 options.classicalDerived 才产出——
// 本命 astro 快照路径与挂载 astrochart 分支显式开;germany/mundane/indiachart/jieqi/relative 等嵌套
// 消费方缺省 falsy=零输出零字节(嵌套段头爆炸半径钉死,per-key 负向锁看死)。
import * as AstroConst from '../../constants/AstroConst.js';
import { SIGNS } from '../divination/data/signs.js';
import { houseNum as dcHouseNum, signOf as dcSignOf } from './dispositorChain.js';
import { KLIMATA, SIGN_CN, PLANET_CN, THEMA_MUNDI, parseSignDegree } from '../divination/data/hellenisticData.js';
import { termRulerForVariant } from '../divination/engine/almuten.js';

// ─────────────────────────── 通用小工具 ───────────────────────────

const planetCn = (id)=>PLANET_CN[id] || id || '-';
const signCnOf = (s)=>(s && SIGNS[String(s).toLowerCase()] && SIGNS[String(s).toLowerCase()].cn) || s || '-';

// ─────────────────────────── G19 派生宫 · 转宫(自 AstroDerivedHouses 抽出,只移不改) ───────────────────────────

// 十二宫话题(自命宫起)。
export const DERIVED_HOUSE_TOPICS = ['命宫·自我', '财帛', '兄弟·近邻', '田宅·父母', '子女·创造', '奴仆·疾厄', '夫妻·伴侣', '疾厄·死亡', '迁移·信仰', '官禄·事业', '福德·友群', '玄秘·隐患'];

// 以第 base 宫为第 1 宫派生十二宫。返回 { rows: [{k, origin, sign, planets, ruler, topic}], isWhole }。
export function deriveDerivedHouseRows(chartObj, base){
	const houses = (chartObj && chartObj.chart && chartObj.chart.houses) || [];
	const objects = (chartObj && chartObj.chart && chartObj.chart.objects) || [];
	const hsys = chartObj && chartObj.params && chartObj.params.hsys;
	// 整宫家族 = 0(整宫制)与 24(福点整宫制);8 是「天顶为10宫中点等宫制」,与整宫无关。
	const isWhole = String(hsys) === '0' || String(hsys) === '24' || String(hsys) === 'whole' || String(hsys).toLowerCase() === 'w';
	// 原宫号 → {sign, planets[]}。
	const byHouse = {};
	houses.forEach((h)=>{
		if(!h){ return; }
		const hn = dcHouseNum(h.id);
		if(!hn){ return; }
		const csign = h.sign ? String(h.sign).toLowerCase() : (h.lon != null ? dcSignOf(h.lon) : null);
		byHouse[hn] = { sign: csign, planets: [] };
	});
	objects.forEach((o)=>{
		// objects[].house 是字符串 'House4' → 必走 houseNum(Number() 恒 NaN 教训)。
		const hn = dcHouseNum(o.house);
		if(byHouse[hn]){ byHouse[hn].planets.push(o.id); }
	});
	const rows = [];
	for(let k = 1; k <= 12; k++){
		const origin = ((base - 1) + (k - 1)) % 12 + 1;
		const cell = byHouse[origin] || { sign: null, planets: [] };
		const ruler = cell.sign ? (SIGNS[cell.sign] || {}).domicile || null : null;
		rows.push({ k, origin, sign: cell.sign, planets: cell.planets, ruler, topic: DERIVED_HOUSE_TOPICS[k - 1] });
	}
	return { rows, isWhole };
}

// ─────────────────────────── G7 七气候带 Klimata(自 AstroKlimata 抽出,只移不改) ───────────────────────────

export const OBLIQUITY = 23.44; // 当世黄赤交角约值(度)。
const DEG = Math.PI / 180;

// 7 气候带固定表:带号 / 城(英·中)/ 纬度(度分串·十进制)/ 最长昼(小时)/ Valens 半圆累计级数。
const VALENS_SERIES = [210, 214, 218, 222, 226, 230, 234]; // 每带 +4,半圆(180°方向)上升时度累计级数。
const BANDS_BASE = [
	{ n: 1, cityEn: 'Meroe', cityCn: '麦罗埃', latStr: '16°27′', lat: 16.45, longestDay: 13 },
	{ n: 2, cityEn: 'Syene', cityCn: '塞伊尼(阿斯旺)', latStr: '23°51′', lat: 23.85, longestDay: 13.5 },
	{ n: 3, cityEn: 'Alexandria', cityCn: '亚历山大(下埃及)', latStr: '30°22′', lat: 30.37, longestDay: 14 },
	{ n: 4, cityEn: 'Rhodes', cityCn: '罗德岛', latStr: '36°00′', lat: 36, longestDay: 14.5 },
	{ n: 5, cityEn: 'Hellespont', cityCn: '赫勒斯滂', latStr: '40°56′', lat: 40.93, longestDay: 15 },
	{ n: 6, cityEn: 'Borysthenes', cityCn: '博里斯提尼斯(中本都)', latStr: '45°01′', lat: 45.02, longestDay: 15.5 },
	{ n: 7, cityEn: 'Mouth of Borysthenes', cityCn: '博里斯提尼斯河口', latStr: '48°32′', lat: 48.53, longestDay: 16 },
];

// 数据底座 KLIMATA 与常量按带号对齐:十进制纬度/最长昼以底座为准(若结构齐全),其余字段用本表补。
export function buildBands(){
	const data = Array.isArray(KLIMATA) ? KLIMATA : [];
	return BANDS_BASE.map((b, i)=>{
		const d = data[i] || {};
		return {
			...b,
			lat: (typeof d.lat === 'number') ? d.lat : b.lat,
			longestDay: (typeof d.longest_day_h === 'number') ? d.longest_day_h : b.longestDay,
			valens: VALENS_SERIES[i],
		};
	});
}

// "26n04" / "26s04" / "31.5" → 十进制纬度(北正南负);无法解析返回 null。
export function parseLat(raw){
	if(raw === undefined || raw === null){ return null; }
	const s = String(raw).trim();
	if(!s){ return null; }
	const m = s.toLowerCase().match(/^(\d+(?:\.\d+)?)([ns])(\d+(?:\.\d+)?)?$/);
	if(m){
		const deg = parseFloat(m[1]);
		const min = m[3] ? parseFloat(m[3]) : 0;
		const v = deg + min / 60;
		return m[2] === 's' ? -v : v;
	}
	const num = parseFloat(s);
	return Number.isFinite(num) ? num : null;
}

// 从 chartObj 取出生纬度十进制。优先 params.lat,退而 fields.lat.value。
export function readLatDeg(chartObj, fields){
	const params = (chartObj && chartObj.params) || {};
	let v = parseLat(params.lat);
	if(v === null && fields && fields.lat){
		v = parseLat(fields.lat.value !== undefined ? fields.lat.value : fields.lat);
	}
	return v;
}

// 当前纬度落在哪个气候带:取纬度绝对值最接近的带(超界则贴最近端带)。
export function currentBandIndex(bands, latDeg){
	if(latDeg === null || !bands.length){ return -1; }
	const abs = Math.abs(latDeg);
	let best = 0;
	let bestDiff = Infinity;
	bands.forEach((b, i)=>{
		const diff = Math.abs(abs - b.lat);
		if(diff < bestDiff){ bestDiff = diff; best = i; }
	});
	return best;
}

// 斜升时度闭式:δ=asin(sinε·sinλ)/α=atan2(cosε·sinλ,cosλ)/AD=asin(tanδ·tanφ)/OA=α−AD。
// 单座上升时度 = OA(座末)−OA(座首);12 座和=360。返回各座度数数组(长度 12)。
export function obliqueAscensions(latDeg){
	const phi = latDeg * DEG;
	const eps = OBLIQUITY * DEG;
	const tanPhi = Math.tan(phi);
	// 黄经 λ → OA(0..360 连续展开)。
	const oa = (lamDeg)=>{
		const lam = lamDeg * DEG;
		const sinDelta = Math.sin(eps) * Math.sin(lam);
		const delta = Math.asin(Math.max(-1, Math.min(1, sinDelta)));
		const alpha = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam)); // -π..π
		let ad = Math.asin(Math.max(-1, Math.min(1, Math.tan(delta) * tanPhi)));
		if(!Number.isFinite(ad)){ ad = 0; } // 极区超界保护(asin 域外)。
		let oaDeg = (alpha - ad) / DEG;
		return oaDeg;
	};
	// 以 RA 为骨:取每座首末 OA,差值规整到 (0,360)→各座度数,再缩放到精确 360 总和(消浮点漂移)。
	const raw = [];
	for(let i = 0; i < 12; i++){
		let span = oa((i + 1) * 30) - oa(i * 30);
		span = ((span % 360) + 360) % 360;
		raw.push(span);
	}
	const sum = raw.reduce((a, b)=>a + b, 0) || 360;
	return raw.map((v)=>v * 360 / sum);
}

// 时度 → 恒星小时(15 时度 = 1 小时)。
export function toSiderealHour(asc){ return asc / 15; }

// ─────────────────────────── G18 显赫计分 Eminence(自 AstroEminence 抽出,只移不改) ───────────────────────────

const MUTED = 'var(--horosa-muted, #999)';
const GOLD = 'var(--horosa-gold, #b8860b)';
const JADE = 'var(--horosa-jade, #3a9a6a)';
const DANGER = 'var(--horosa-danger, #cf1322)';

// 「有用宫」(尊贵宫/可见且与上升成相位之宫):命1·官10·福11·夫7·田4·迁9·子5。
const USEFUL_HOUSES = [1, 10, 11, 7, 4, 9, 5];
const ANGULAR_HOUSES = [1, 4, 7, 10];
const BENEFICS = [AstroConst.VENUS, AstroConst.JUPITER];
const LIGHTS = [AstroConst.SUN, AstroConst.MOON];

// chart.objects 取星(按 id)。
function findObj(chart, id){
	const objs = (chart && chart.objects) || [];
	return objs.find((x) => x && x.id === id) || null;
}

// 宫号:o.house 形如 'House5' 或数字。
function emHouseNum(h){
	if(h == null){ return null; }
	if(typeof h === 'number'){ return h; }
	const m = String(h).match(/(\d+)/);
	return m ? Number(m[1]) : null;
}

// 黄经:优先 o.lon,退而由 sign + signlon 推算。
function lonOf(o){
	if(!o){ return null; }
	if(o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
	if(idx >= 0 && o.signlon !== undefined && o.signlon !== null){ return idx * 30 + Number(o.signlon); }
	return null;
}

// 星座(SignsProp 键为首字母大写英文)。
function emSignOf(o){
	if(o && o.sign){ return o.sign; }
	const lon = lonOf(o);
	if(lon == null){ return null; }
	return AstroConst.LIST_SIGNS[Math.floor(((lon % 360) + 360) % 360 / 30)] || null;
}

// selfDignity 数组 → 是否有本垣/擢升级尊贵(强尊贵)。
function hasStrongDignity(o){
	const d = (o && o.selfDignity) || [];
	return d.indexOf('ruler') >= 0 || d.indexOf('exalt') >= 0;
}
// 任意尊贵(含界/面/三分)。
function hasAnyDignity(o){
	const d = (o && o.selfDignity) || [];
	return ['ruler', 'exalt', 'dayTrip', 'nightTrip', 'partTrip', 'term', 'face'].some((t) => d.indexOf(t) >= 0);
}
// 落陷/落弱(受损)。
function isDebilitated(o){
	const d = (o && o.selfDignity) || [];
	return d.indexOf('exile') >= 0 || d.indexOf('fall') >= 0;
}

// 某星座的庙主(本垣主星 id)。
function rulerOfSign(sign){
	const sp = sign ? AstroConst.SignsProp[sign] : null;
	return sp ? sp.Ruler : null;
}

// idA 是否被 idB 以相位照映(含合相):走现成 chart.aspects.normalAsp。
function isAspectedBy(chart, idA, idB){
	const na = chart && chart.aspects && chart.aspects.normalAsp;
	if(!na || !na[idA]){ return false; }
	const cats = ['Exact', 'Applicative', 'Separative', 'None'];
	return cats.some((c) => (na[idA][c] || []).some((x) => x && x.id === idB));
}
// 是否受任一吉星照映。
function aspectedByBenefic(chart, id){
	return BENEFICS.some((b) => isAspectedBy(chart, id, b));
}

// 度数围攻:同星座内左右最近的可见星皆为凶星(土/火),且本星夹其间。粗判:同宫有两凶星且本星黄经居中。
function isBesieged(chart, o){
	const lon = lonOf(o);
	if(lon == null){ return false; }
	const malefics = [AstroConst.MARS, AstroConst.SATURN]
		.map((id) => findObj(chart, id))
		.filter((m) => m && emHouseNum(m.house) === emHouseNum(o.house) && lonOf(m) != null);
	if(malefics.length < 2){ return false; }
	const lefts = malefics.filter((m) => lonOf(m) < lon);
	const rights = malefics.filter((m) => lonOf(m) > lon);
	return lefts.length >= 1 && rights.length >= 1;
}

// 持矛 doryphoria(护卫)派生:区间光体被同宗吉星(及尊贵星)在其前后随侍。
// 若 chartObj 已带分析数据(chart.analysis.doryphory),优先复用;否则自盘面轻量派生。
function deriveDoryphory(chart){
	// 优先复用现成派生(后端/分析挂载若已注入)。
	const fromAnalysis = chart && chart.analysis && chart.analysis.doryphory;
	if(Array.isArray(fromAnalysis) && fromAnalysis.length){
		return { has: true, count: fromAnalysis.length, source: 'analysis' };
	}
	const isDay = !!chart.isDiurnal;
	const lightId = isDay ? AstroConst.SUN : AstroConst.MOON;
	const light = findObj(chart, lightId);
	if(!light){ return { has: false, count: 0 }; }
	const lh = emHouseNum(light.house);
	// 随侍:同宗吉星 + 任意带强尊贵的可见星,落于光体所在宫或相邻宫(护卫语义之轻量近似)。
	const guards = [];
	const candidateIds = [AstroConst.VENUS, AstroConst.JUPITER, AstroConst.MERCURY, AstroConst.MARS, AstroConst.SATURN];
	candidateIds.forEach((id) => {
		const g = findObj(chart, id);
		if(!g){ return; }
		const sameSect = g.ofSect === true;
		const dignified = hasStrongDignity(g);
		if(!sameSect && !dignified){ return; }
		const gh = emHouseNum(g.house);
		if(lh != null && gh != null){
			// 宫位是环:12↔1 相邻(|12-1|=11 曾漏计,光体落 1/12 宫时邻宫吉星全丢)
			const dd = Math.abs(gh - lh);
			if(Math.min(dd, 12 - dd) <= 1){ guards.push(id); }
		}
	});
	return { has: guards.length > 0, count: guards.length, guards };
}

// 盘主(almuten)派生:复用现成 almuten(若已挂载),否则取上升星座庙主为近似盘主。
function deriveAlmuten(chart){
	const fromAnalysis = chart && chart.analysis && chart.analysis.almutem;
	if(fromAnalysis && fromAnalysis.winner){ return { id: fromAnalysis.winner, source: 'analysis' }; }
	const asc = findObj(chart, AstroConst.ASC);
	const ascSign = asc ? emSignOf(asc) : null;
	const ruler = ascSign ? rulerOfSign(ascSign) : null;
	return { id: ruler, source: 'ascRuler' };
}

// 显赫点对象:福点在 chart.objects,其余阿拉伯点在 Result.lots 独立数组。
// 🔴 曾只查 objects → 四点恒只命中福点一个,s5 上限从 2 分压到 0.5、显赫判级系统性下压。
function lotObj(chart, id, lots){
	const o = findObj(chart, id);
	if(o){ return o; }
	const list = Array.isArray(lots) ? lots : [];
	return list.find((x)=>x && x.id === id) || null;
}

// 核心:计五指标 + 总分 + 等级。返回 { ok, rows, total, level, levelColor, isDay, note }。
export function computeEminence(chartObj){
	const chart = chartObj && chartObj.chart;
	const lots = (chartObj && Array.isArray(chartObj.lots)) ? chartObj.lots : [];
	if(!chart || !Array.isArray(chart.objects) || !chart.objects.length){
		return { ok: false };
	}
	const isDay = !!chart.isDiurnal;
	const sun = findObj(chart, AstroConst.SUN);
	const moon = findObj(chart, AstroConst.MOON);
	if(!sun || !moon){ return { ok: false }; }

	const rows = [];

	// 指标 1 两光位置:日月各落「有用宫」给分,落角宫额外加权;被围攻则扣回。
	let s1 = 0;
	const lightDetail = [];
	LIGHTS.forEach((id) => {
		const o = id === AstroConst.SUN ? sun : moon;
		const h = emHouseNum(o.house);
		let pt = 0;
		if(h != null && USEFUL_HOUSES.indexOf(h) >= 0){ pt = ANGULAR_HOUSES.indexOf(h) >= 0 ? 1 : 0.5; }
		if(isBesieged(chart, o)){ pt = 0; }
		s1 += pt;
		lightDetail.push(`${id === AstroConst.SUN ? '日' : '月'}${h != null ? h + '宫' : '—'}${pt > 0 ? '✓' : ''}`);
	});
	s1 = Math.min(2, Math.round(s1 * 2) / 2);
	rows.push({
		key: 'lights', name: '两光位置', score: s1,
		factors: lightDetail.join(' / ') + '（有用宫·角宫加权·不被围攻）',
	});

	// 指标 2 福点及其主星:福点落角宫 +1;福点主星有尊贵或受吉星照 +1。缺福点降级。
	let s2 = 0;
	const fortune = lotObj(chart, AstroConst.PARS_FORTUNA, lots);
	let fortuneFactors;
	if(!fortune){
		fortuneFactors = '缺福点（降级）';
	}else{
		const fh = emHouseNum(fortune.house);
		const inAngle = fh != null && ANGULAR_HOUSES.indexOf(fh) >= 0;
		if(inAngle){ s2 += 1; }
		const fSign = emSignOf(fortune);
		const lordId = fSign ? rulerOfSign(fSign) : null;
		const lord = lordId ? findObj(chart, lordId) : null;
		const lordGood = lord && (hasAnyDignity(lord) || aspectedByBenefic(chart, lordId));
		if(lordGood){ s2 += 1; }
		fortuneFactors = `福点${fh != null ? fh + '宫' : '—'}${inAngle ? '·角宫✓' : ''}` +
			`　主星${lordId ? '' : '—'}${lordGood ? '·有力✓' : (lordId ? '·平' : '')}`;
	}
	s2 = Math.min(2, s2);
	rows.push({ key: 'fortune', name: '福点及主星', score: s2, factors: fortuneFactors });

	// 指标 3 持矛 doryphoria:复用现成护卫派生;有护卫给 1,护卫含强尊贵星给 2。
	let s3 = 0;
	const dory = deriveDoryphory(chart);
	if(dory.has){ s3 = dory.count >= 2 ? 2 : 1; }
	const doryFactors = dory.has
		? `区间光体受 ${dory.count} 星随侍${dory.source === 'analysis' ? '' : '（盘面派生）'}`
		: '无明显护卫';
	rows.push({ key: 'doryphory', name: '持矛护卫', score: s3, factors: doryFactors });

	// 指标 4 盘主有力:盘主落角宫 +1;盘主带尊贵 +1。
	let s4 = 0;
	const alm = deriveAlmuten(chart);
	let almFactors;
	if(!alm.id){
		almFactors = '盘主不可定';
	}else{
		const ao = findObj(chart, alm.id);
		const ah = ao ? emHouseNum(ao.house) : null;
		const inAngle = ah != null && ANGULAR_HOUSES.indexOf(ah) >= 0;
		if(inAngle){ s4 += 1; }
		const dignified = ao && hasStrongDignity(ao);
		if(dignified){ s4 += 1; }
		almFactors = `盘主${alm.source === 'ascRuler' ? '（上升主）' : ''} ${ah != null ? ah + '宫' : '—'}` +
			`${inAngle ? '·角宫✓' : ''}${dignified ? '·尊贵✓' : ''}`;
	}
	s4 = Math.min(2, s4);
	rows.push({ key: 'almuten', name: '盘主有力', score: s4, almuten: alm.id, factors: almFactors });

	// 指标 5 四显赫点:福点/精神点/根基点/擢升点 + 各点主星状态(受损扣分)。
	// 根基点 Basis、擢升点 Exaltation 若 chart.objects 未提供则跳过(优雅降级)。
	let s5 = 0;
	const EMINENCE_POINTS = [
		{ id: AstroConst.PARS_FORTUNA, cn: '福点' },
		{ id: AstroConst.PARS_SPIRIT, cn: '精神点' },
		{ id: 'Pars Basis', cn: '根基点' },
		{ id: 'Pars Exaltation', cn: '擢升点' },
	];
	const ptDetail = [];
	let present = 0;
	EMINENCE_POINTS.forEach((p) => {
		const o = lotObj(chart, p.id, lots);
		if(!o){ return; }
		present += 1;
		const h = emHouseNum(o.house);
		const inUseful = h != null && USEFUL_HOUSES.indexOf(h) >= 0;
		const lordId = rulerOfSign(emSignOf(o));
		const lord = lordId ? findObj(chart, lordId) : null;
		const lordOk = lord && !isDebilitated(lord);
		// 每点:落有用宫且主星不受损 → 0.5。
		if(inUseful && lordOk){ s5 += 0.5; }
		ptDetail.push(`${p.cn}${h != null ? h + '宫' : ''}${inUseful && lordOk ? '✓' : ''}`);
	});
	if(!present){ ptDetail.push('显赫点数据不足'); }
	s5 = Math.min(2, Math.round(s5 * 2) / 2);
	rows.push({ key: 'points', name: '四显赫点', score: s5, factors: ptDetail.join(' / ') });

	const total = Math.round((s1 + s2 + s3 + s4 + s5) * 2) / 2;
	let level;
	let levelColor;
	if(total >= 8){ level = '显赫'; levelColor = GOLD; }
	else if(total >= 6){ level = '显著'; levelColor = JADE; }
	else if(total >= 3){ level = '平凡'; levelColor = MUTED; }
	else { level = '暗晦'; levelColor = DANGER; }

	// 朔望(日月会合)边界:若日月同宫(新月)则两光合一,显赫判读降级提示。
	const sameSign = emSignOf(sun) && emSignOf(sun) === emSignOf(moon);
	const note = sameSign ? '日月同座(近朔)·两光合一,显赫判读宜降级看待。' : '';

	return { ok: true, rows, total, level, levelColor, isDay, note };
}

// ─────────────────────────── G5 世界范式盘 Thema Mundi(文案单源,自组件抽出) ───────────────────────────

// 七政范式位 → [{planetEn, signIndex, deg, lon}]。上升=15°巨蟹(lon 105)。
export function themaPositions(){
	const pos = THEMA_MUNDI.positions || {};
	const out = [];
	Object.keys(pos).forEach((p)=>{
		const sd = parseSignDegree(pos[p]);
		if(sd){ out.push({ planetEn: p, ...sd }); }
	});
	return out;
}

// 三条含义(第一性原理),组件 <li> 与快照同源。
export const THEMA_MUNDI_BULLETS = [
	'庙位由来:各星置于本垣(土摩羯/木射手/火天蝎/日狮/金天秤/水处女/月巨蟹),范式盘即「庙=第一性原理」之图解。',
	'相位语义:从巨蟹(上升)起整宫,与各星所成相位(三分/六分吉、四分/对分挑战)奠定相位本义。',
	'坏宫由来:自上升 2/6/8/12 宫(与上升不成主相位=背离)由范式盘几何推出,故为「衰宫」。',
];

// ─────────────────────────── 快照行构建(供 buildAstroSnapshotContent opt-in 消费) ───────────────────────────

// [古典·派生宫转宫]:本命基准(原 1 宫为命)十二宫 星座/落星/宫主 表 + 转宫法说明。
export function buildDerivedHousesSnapshotLines(chartObj){
	if(!chartObj || !chartObj.chart){ return []; }
	const { rows, isWhole } = deriveDerivedHouseRows(chartObj, 1);
	if(!rows.some((r)=>r.sign || (r.planets && r.planets.length))){ return []; }
	const lines = [];
	lines.push(`转宫法:以任一原宫作第 1 宫可派生十二宫话题(如以田宅 4 宫为命=父母之事盘)。下表为本命基准(原 1 宫为命)。${isWhole ? '' : '　※ 转宫为整宫制技法,当前非整宫制下仅作话题参考。'}`);
	lines.push('| 宫·话题 | 星座 | 落星 | 宫主 |');
	lines.push('| --- | --- | --- | --- |');
	rows.forEach((r)=>{
		const planets = r.planets && r.planets.length ? r.planets.map(planetCn).join('、') : '-';
		lines.push(`| ${r.k}·${r.topic} | ${signCnOf(r.sign)} | ${planets} | ${r.ruler ? planetCn(r.ruler) : '-'} |`);
	});
	return lines;
}

// [古典·气候带]:出生纬度归带行 + 十二座斜升时度表(随盘变的事实;七带常量表属固定教义不重复入快照)。
export function buildKlimataSnapshotLines(chartObj, fields){
	const latDeg = readLatDeg(chartObj, fields);
	if(latDeg === null){ return []; }
	const bands = buildBands();
	const curIdx = currentBandIndex(bands, latDeg);
	const band = bands[curIdx];
	const lines = [];
	if(band){
		lines.push(`出生纬度 ${Math.abs(latDeg).toFixed(2)}°${latDeg < 0 ? 'S' : 'N'},归入第 ${band.n} 气候带（${band.cityCn}·最长昼 ${band.longestDay}h·半圆级数 ${band.valens}）。`);
	}
	const ascs = obliqueAscensions(latDeg);
	lines.push('| 星座 | 上升时度 | 折恒星时 |');
	lines.push('| --- | --- | --- |');
	ascs.forEach((asc, i)=>{
		lines.push(`| ${SIGN_CN[i]} | ${asc.toFixed(2)}° | ${toSiderealHour(asc).toFixed(2)}h |`);
	});
	lines.push(`斜升时度按闭式(ε≈${OBLIQUITY}°)计,各座之和恒 360 时度,15 时度折 1 恒星小时。`);
	return lines;
}

// ─────────────── [WP-4] 主宰光体 predominator + 庙/界主两派(Valens 式三判据) ───────────────
// 判据:①落有利宫(chrematistikoi,busyPlaces 集合可配,默认 1/4/5/7/10/11) ②区分得体(sect light +1)
// ③近轴角(距 ASC/MC/DESC/IC 黄经 <10° +1)。dynamicalDivisions=1 时逐判据乘象限动力权
// (角宫 ×1.0 / 续宫 ×0.75 / 果宫 ×0.5)。两光加总取高者;平分取 sect light。
// domicileMasterMethod:'domicile'(庙主派 Porphyry·Antiochus,默认=寿命法现状)/'bound'(界主派 Valens·Rhetorius)。
const _PRED_ANGULAR = [1, 10, 7, 4];
const _PRED_SUCCEDENT = [2, 5, 8, 11];

export function computePredominator(chartObj, opts){
	const chart = chartObj && chartObj.chart;
	if(!chart || !Array.isArray(chart.objects)){ return { ok: false }; }
	const o = opts || {};
	const busy = Array.isArray(o.busyPlaces) && o.busyPlaces.length ? o.busyPlaces : [1, 4, 5, 7, 10, 11];
	const dyn = o.dynamicalDivisions === 1 || o.dynamicalDivisions === '1' || o.dynamicalDivisions === true;
	const isDay = !!chart.isDiurnal;
	const sun = findObj(chart, AstroConst.SUN);
	const moon = findObj(chart, AstroConst.MOON);
	if(!sun || !moon){ return { ok: false }; }
	const angles = Array.isArray(chart.angles) ? chart.angles : [];
	const angleLons = angles.map((a) => lonOf(a)).filter((x) => Number.isFinite(x));
	const quadWeight = (h) => {
		if(!dyn || h == null){ return 1.0; }
		if(_PRED_ANGULAR.indexOf(h) >= 0){ return 1.0; }
		if(_PRED_SUCCEDENT.indexOf(h) >= 0){ return 0.75; }
		return 0.5;
	};
	const judge = (obj, ofSect) => {
		const h = emHouseNum(obj.house);
		const w = quadWeight(h);
		const factors = [];
		let score = 0;
		if(h != null && busy.indexOf(h) >= 0){ score += 1 * w; factors.push(`有利宫(${h})`); }
		if(ofSect){ score += 1 * w; factors.push('区分得体'); }
		const lon = lonOf(obj);
		const nearAxis = Number.isFinite(lon) && angleLons.some((al) => {
			const d = Math.abs(((lon - al + 180) % 360) - 180);
			return d < 10;
		});
		if(nearAxis){ score += 1 * w; factors.push('近轴角'); }
		return { score: Math.round(score * 100) / 100, factors, house: h };
	};
	const sunJ = judge(sun, isDay);
	const moonJ = judge(moon, !isDay);
	let winnerId = sunJ.score > moonJ.score ? AstroConst.SUN : (moonJ.score > sunJ.score ? AstroConst.MOON : (isDay ? AstroConst.SUN : AstroConst.MOON));
	const winner = winnerId === AstroConst.SUN ? sun : moon;
	// 庙主/界主两派(termRulerAt 与后端界表同源四档)。
	const signKeyOf = (obj) => `${obj.sign || ''}`.toLowerCase();
	const domicileMaster = (SIGNS[signKeyOf(winner)] || SIGNS[winner.sign] || {}).domicile || null;
	let boundMaster = null;
	try{
		// [F6][R4-P2] 统一走 almuten.termRulerForVariant 单源:迦勒底昼夜/自定义表体/双子校勘全档齐
		// (termRulerAt 直调无 chaldean 分支,tv=3 恒埃及=同屏与行星表两结论)。
		boundMaster = termRulerForVariant(lonOf(winner), {
			termsVariant: o.termsVariant !== undefined ? Number(o.termsVariant) : 0,
			isDiurnal: isDay,
			geminiEmended: !!(o.geminiBoundEmended && Number(o.geminiBoundEmended) === 1),
			customTermsDay: o.customTermsDay, customTermsNight: o.customTermsNight,
		}) || null;
	}catch(e){ boundMaster = null; }
	const method = o.domicileMasterMethod === 'bound' ? 'bound' : 'domicile';
	return {
		ok: true, isDay, winner: winnerId,
		sunScore: sunJ.score, moonScore: moonJ.score,
		sunFactors: sunJ.factors, moonFactors: moonJ.factors,
		domicileMaster, boundMaster, method,
		master: method === 'bound' ? (boundMaster || domicileMaster) : domicileMaster,
		dynamical: dyn,
	};
}

// ─────────────── [WP-8] 七射线分布(灵学体系推算;默认 off 不算不显) ───────────────
// Bailey 体系公开映射:星座→射线 / 行星→射线;权重档 equal(每命中 1)/weighted(发光体×3/内行星×2/外行星×1)。
const RAY_OF_SIGN = { Aries: [1], Taurus: [4], Gemini: [2], Cancer: [3, 7], Leo: [1, 5], Virgo: [2, 6],
	Libra: [3], Scorpio: [4], Sagittarius: [4, 5, 6], Capricorn: [1, 3, 7], Aquarius: [5], Pisces: [2, 6] };
const RAY_OF_PLANET = { Sun: 1, Moon: 4, Mercury: 4, Venus: 5, Mars: 6, Jupiter: 2, Saturn: 3,
	Uranus: 7, Neptune: 6, Pluto: 1 };
const RAY_WEIGHT = { Sun: 3, Moon: 3, Mercury: 2, Venus: 2, Mars: 2, Jupiter: 1, Saturn: 1, Uranus: 1, Neptune: 1, Pluto: 1 };
export const RAY_NAMES_CN = ['意志', '爱智', '活性', '谐美', '实学', '虔诚', '仪轨'];

export function computeSevenRays(chartObj, weighting){
	const chart = chartObj && chartObj.chart;
	if(!chart || !Array.isArray(chart.objects)){ return null; }
	const totals = [0, 0, 0, 0, 0, 0, 0];
	chart.objects.forEach((o) => {
		const pr = RAY_OF_PLANET[o.id];
		if(pr === undefined){ return; }
		const w = weighting === 'weighted' ? (RAY_WEIGHT[o.id] || 1) : 1;
		totals[pr - 1] += w;
		(RAY_OF_SIGN[o.sign] || []).forEach((r) => { totals[r - 1] += w; });
	});
	const max = Math.max(...totals);
	return { totals, max, weighting: weighting === 'weighted' ? 'weighted' : 'equal' };
}

// [古典·显赫计分]:五指标计分表 + 总分等级(computeEminence 单源)。
export function buildEminenceSnapshotLines(chartObj, predOpts){
	const data = computeEminence(chartObj);
	if(!data.ok){ return []; }
	const lines = [];
	lines.push(`${data.isDay ? '昼生盘(区间光体=日)' : '夜生盘(区间光体=月)'}。五指标各 0-2 分(现代计分便于横向比较,非典籍原文权重)。`);
	lines.push('| 指标 | 满足要素 | 小分 |');
	lines.push('| --- | --- | --- |');
	data.rows.forEach((r)=>{
		lines.push(`| ${r.name}${r.almuten ? `(${planetCn(r.almuten)})` : ''} | ${r.factors} | ${r.score} |`);
	});
	lines.push(`总分 ${data.total} / 10 → ${data.level}（≥8 显赫 / 6-7 显著 / 3-5 平凡 / <3 暗晦）。`);
	if(data.note){ lines.push(data.note); }
	// [WP-4] 主宰光体行(段内增行不加段头):判定三判据+两派主星并列自陈。
	const pred = computePredominator(chartObj, predOpts);
	if(pred.ok){
		const fx = (pred.winner === AstroConst.SUN ? pred.sunFactors : pred.moonFactors).join('·') || '判据全空(按区分光体)';
		lines.push(`主宰光体(predominator):${pred.winner === AstroConst.SUN ? '太阳' : '月亮'}(日 ${pred.sunScore} 分 / 月 ${pred.moonScore} 分;${fx}${pred.dynamical ? ';动力学分区加权' : ''})。庙主=${planetCn(pred.domicileMaster) || '—'}${pred.boundMaster ? `,界主=${planetCn(pred.boundMaster)}` : ''};当前判法=${pred.method === 'bound' ? '界主派' : '庙主派'} → 主宰主星 ${planetCn(pred.master) || '—'}。`);
	}
	// [WP-8] 七射线分布(灵学推算;默认 off 零增行)+祝融星行(响应有 vulcan 字段才显)。
	const rw = predOpts && predOpts.rayWeighting;
	if(rw === 'equal' || rw === 'weighted'){
		const rays = computeSevenRays(chartObj, rw);
		if(rays){
			lines.push(`七射线分布(${rw === 'weighted' ? '加权' : '等权'} · 灵学体系推算):` +
				rays.totals.map((v, i) => `${i + 1}·${RAY_NAMES_CN[i]} ${v}`).join('／') + '。');
		}
	}
	if(chartObj && chartObj.vulcan){
		const v = chartObj.vulcan;
		const mtxt = (v.method === 'baker' || v.method === 'baker(fallback)') ? '水星系推算' : '轨道根数法';
		const SIGNS_EN = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
		const signCn = SIGN_CN[SIGNS_EN.indexOf(v.sign)] || v.sign;
		lines.push(`祝融星(推算行星·${mtxt}):${signCn} ${Math.round(v.signlon * 100) / 100}˚(距日 ${v.distToSun}˚)。`);
	}
	return lines;
}

// [古典·世界范式盘]:固定范式盘(恒定教义,默认关段)——七政范式位 + 三条第一性原理。
export function buildThemaMundiSnapshotLines(){
	const lines = [];
	lines.push('希腊化占星范式盘:上升 15°巨蟹,七政各居本垣中点 15°。非天文实算,示尊贵/相位/宫位语义之第一性原理。');
	const posText = themaPositions().map((p)=>`${planetCn(p.planetEn)}${SIGN_CN[p.signIndex]}${p.deg}°`).join('　');
	if(posText){ lines.push(`七政范式位:${posText}`); }
	THEMA_MUNDI_BULLETS.forEach((b)=>lines.push(`· ${b}`));
	return lines;
}
