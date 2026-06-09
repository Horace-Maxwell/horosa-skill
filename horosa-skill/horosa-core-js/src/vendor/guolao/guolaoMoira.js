// 七政四余 政余格局（Moira DSL，星阙 v2.6.x；verbatim 抽取自 GuoLaoChartMain.js）。
// buildLocalMoiraPatterns(chartObj, fields, params, godRows) → [{name,level:'good'|'bad',detail,dsl},...]
// + buildGodRowsFromChart(chartObj, fields)。纯函数闭包(34 fns + consts)，零 React/this。
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';
import * as SZConst from '../suzhan/SZConst.js';

// 七政四余 命主取法 / 宿度制（上游 GuoLaoChartStyle.js，localStorage 偏好）。headless 无持久化 →
// getStored* 回退 星阙 缺省（命主=ASC 命度、宿度制=2 张果今制）；normalizeGuolaoLifeMode 平移原逻辑。
// 仅当 fields.guolaoLifeMode 显式传入时改用羽士/同度命主，否则全走缺省（与 星阙 无偏好态一致）。
const GUOLAO_LIFE_MODE_YUMAO = 'yumao';
const GUOLAO_LIFE_MODE_COTRANS = 'cotrans';
const GUOLAO_LIFE_MODE_ASC = 'asc';
function normalizeGuolaoLifeMode(val) {
  if (val === GUOLAO_LIFE_MODE_YUMAO) return GUOLAO_LIFE_MODE_YUMAO;
  if (val === GUOLAO_LIFE_MODE_COTRANS) return GUOLAO_LIFE_MODE_COTRANS;
  return GUOLAO_LIFE_MODE_ASC;
}
const getStoredGuolaoLifeMode = () => GUOLAO_LIFE_MODE_ASC;
const getStoredGuolaoSu28Mode = () => 2;

const SIMPLE_TOKEN_MAP = {
	A: '日',
	B: '月',
	C: '水',
	D: '金',
	E: '火',
	F: '木',
	G: '土',
	H: '天王',
	I: '海王',
	J: '冥王',
	K: '北交',
	L: '南交',
	p: '福点',
	v: '暗月',
	w: '紫气',
	y: '凯龙',
	z: '月亮朔望点',
	Y: '月亮平均远地点',
	$: '月亮平均近地点',
	a: '白羊',
	b: '金牛',
	c: '双子',
	d: '巨蟹',
	e: '狮子',
	f: '处女',
	g: '天秤',
	h: '天蝎',
	i: '射手',
	j: '摩羯',
	k: '水瓶',
	l: '双鱼',
	0: '上升',
	1: '天顶',
	2: '天底',
	3: '下降',
	4: '谷神星',
	5: '智神星',
	6: '婚神星',
	7: '灶神星',
	8: '人龙星',
};


const MOIRA_PLANET_ORDER = [
	{id: AstroConst.SUN, name: '日'},
	{id: AstroConst.MOON, name: '月'},
	{id: AstroConst.VENUS, name: '金'},
	{id: AstroConst.JUPITER, name: '木'},
	{id: AstroConst.MERCURY, name: '水'},
	{id: AstroConst.MARS, name: '火'},
	{id: AstroConst.SATURN, name: '土'},
	{id: AstroConst.SOUTH_NODE, name: '计'},
	{id: AstroConst.NORTH_NODE, name: '罗'},
	{id: AstroConst.PURPLE_CLOUDS, name: '炁'},
	{id: AstroConst.DARKMOON, name: '孛'},
];


const MOIRA_BIRTH_GOD_ORDER = ['劫杀', '文昌', '禄勋', '大耗', '月杀', '咸池', '唐符', '天厨', '伏尸', '三刑', '勾神', '蓦越', '黄幡', '的杀', '孤辰', '天喜', '注受', '剑锋', '飞廉', '病符', '紫微', '华盖', '天贵', '六害', '孤虚', '游奕', '年符', '死符', '地雌', '卷舌', '绞杀', '天德', '贯索', '亡神', '国印', '岁殿', '卦气', '空亡', '豹尾', '擎天', '天空', '大杀', '天厄', '月廉', '天雄', '天哭', '天狗', '地耗', '月符', '披头', '红鸾', '岁驾', '小耗', '寡宿', '飞刃', '天耗', '斗杓', '驿马', '阳刃', '阑干', '玉贵', '血刃', '浮沉', '解神'];

const MOIRA_TRANSIT_GOD_ORDER = ['岁驾', '天空', '地雌', '贯索', '五鬼', '死符', '大耗', '天厄', '天雄', '大杀', '卷舌', '天德', '天狗', '蓦越', '亡神', '天喜', '披头', '血刃', '解神', '天哭', '地解', '劫杀', '的杀', '红鸾', '驿马', '游奕', '擎天', '黄幡', '豹尾', '天厨', '三刑', '六害', '咸池', '阳刃', '禄勋', '天贵'];

const MOIRA_PLANET_CN_TO_ID = {
	日: AstroConst.SUN,
	月: AstroConst.MOON,
	水: AstroConst.MERCURY,
	金: AstroConst.VENUS,
	火: AstroConst.MARS,
	木: AstroConst.JUPITER,
	土: AstroConst.SATURN,
	罗: AstroConst.NORTH_NODE,
	计: AstroConst.SOUTH_NODE,
	炁: AstroConst.PURPLE_CLOUDS,
	孛: AstroConst.DARKMOON,
};

const MOIRA_RULER_BY_SIGN = {
	Aries: AstroConst.MARS,
	Taurus: AstroConst.VENUS,
	Gemini: AstroConst.MERCURY,
	Cancer: AstroConst.MOON,
	Leo: AstroConst.SUN,
	Virgo: AstroConst.MERCURY,
	Libra: AstroConst.VENUS,
	Scorpio: AstroConst.MARS,
	Sagittarius: AstroConst.JUPITER,
	Capricorn: AstroConst.SATURN,
	Aquarius: AstroConst.SATURN,
	Pisces: AstroConst.JUPITER,
};

const MOIRA_OVERCOMING = {
	日: '月',
	月: '日',
	金: '火',
	木: '金',
	水: '土',
	火: '水',
	土: '木',
	炁: '金',
	孛: '土',
	罗: '水',
	计: '木',
};


function addLocalMoiraPattern(list, name, level, score, detail, dsl){
	list.push({
		name,
		level,
		score,
		source: 'moira_s.prop-local',
		dsl,
		detail,
	});
}


function buildGodRowsFromChart(result, fields){
	const chart = getChart(result);
	const houses = safeList(chart.houses);
	const ziGods = getZiGods(result);
	const ascSignIndex = computeAscSignIndex(result, chart, fields);
	return houses.map((house, idx)=>{
		const sign = signFromLon(house && house.lon);
		const zi = sign ? SZConst.SignZi[sign] : '';
		const one = zi && ziGods ? safeMap(ziGods[zi]) : {};
		return {
			house: houseFullLabel(house, idx, ascSignIndex),
			zi,
			signName: sign ? msg(sign) : '',
			goodGods: orderGods(one.goodGods, MOIRA_BIRTH_GOD_ORDER),
			neutralGods: orderGods(one.neutralGods, MOIRA_BIRTH_GOD_ORDER),
			badGods: orderGods(one.badGods, MOIRA_BIRTH_GOD_ORDER),
			taisuiGods: orderGods(one.taisuiGods, MOIRA_TRANSIT_GOD_ORDER),
		};
	});
}


function buildLocalMoiraPatterns(chartObj, fields, params, godRows){
	const chart = getChart(chartObj);
	const lifeObj = localLifeObject(chart, fields);
	const lifeLon = objectLon(lifeObj);
	const lifeSignIndex = localLifeSignIndex(chart, fields);
	const selfSignIndex = objectSignIndex(chart, AstroConst.MOON);
	const godSigns = localMoiraGodSigns(godRows);
	const signOf = (name)=>localSignOfCn(chart, name, lifeSignIndex, selfSignIndex, godSigns);
	const same = (a, b)=>a >= 0 && b >= 0 && a === b;
	const rel = (base, offset)=>(base + offset + 12) % 12;
	const sun = signOf('日');
	const moon = signOf('月');
	const venus = signOf('金');
	const mercury = signOf('水');
	const darkMoon = signOf('孛');
	const northNode = signOf('罗');
	const guan = signOf('官');
	const fu = signOf('福');
	const patterns = [];
	const isDay = localMoiraIsDay(params);
	const lifeZi = lifeSignIndex >= 0 ? localSignZi(lifeSignIndex) : '';

	if(lifeSignIndex >= 0 && lifeZi && ('戌亥'.indexOf(lifeZi) >= 0)){
		const diseaseRulerCn = localPlanetCnById(MOIRA_RULER_BY_SIGN[AstroConst.LIST_SIGNS[signOf('疾')]]);
		if(same(signOf(diseaseRulerCn), lifeSignIndex)){
			addLocalMoiraPattern(patterns, '八杀朝天', 'good', '3.2.0', '政余喜格：疾厄宫主入命，且命临戌亥。', '@{@{疾厄}[1]}=@命');
		}
	}
	const moonSign = moon;
	if(moonSign >= 0){
		const sameMoonSignCount = MOIRA_PLANET_ORDER
			.map((item)=>objectSignIndex(chart, item.id))
			.filter((idx)=>idx === moonSign).length;
		if(!isDay && sameMoonSignCount === 1){
			addLocalMoiraPattern(patterns, '孤月独明', 'good', '2.3.0', '政余喜格：夜生月曜独居一方。', '?{孤月} & ?夜');
		}
	}
	if(same(sun, rel(guan, 4)) && same(moon, rel(guan, -4)) || same(sun, rel(guan, -4)) && same(moon, rel(guan, 4))){
		addLocalMoiraPattern(patterns, '日月拱官', 'good', '2.3.0', '政余喜格：日月分拱官禄。', '@日=@官禄+4 & @月=@官禄-4');
	}
	if(same(venus, mercury) && !localMoiraIsWinter(params)){
		addLocalMoiraPattern(patterns, '金水相涵', 'good', '2.3.0', '政余喜格：金水同宫，且不以冬令破格。', '?{金水会} & !?冬');
	}
	const noble = signOf(isDay ? '天贵' : '玉贵');
	if(same(sun, rel(noble, 4)) && same(moon, rel(noble, -4)) || same(sun, rel(noble, -4)) && same(moon, rel(noble, 4))){
		addLocalMoiraPattern(patterns, '日月拱贵人', 'good', '2.2.0', `政余喜格：${isDay ? '昼取天贵' : '夜取玉贵'}，日月分拱。`, '?昼/夜 & 日月拱贵人');
	}
	if(same(lifeSignIndex, signOf('岁驾'))){
		addLocalMoiraPattern(patterns, '命登岁驾', 'good', '2.0.3', '政余喜格：命度临岁驾。', '@命=@{岁驾}');
	}
	if(sun >= 0 && moon >= 0){
		const sunZi = localSignZi(sun);
		const moonZi = localSignZi(moon);
		if(('申酉戌亥子丑'.indexOf(sunZi) >= 0) && ('寅卯辰巳午未'.indexOf(moonZi) >= 0)){
			addLocalMoiraPattern(patterns, '日月失所', 'bad', '2.3.0', '政余忌格：日居西北、月居东南。', '(?{日西}|?{日北}) & (?{月东}|?{月南})');
		}
	}
	if(localMoiraLostRulership(chart, '官', lifeSignIndex, selfSignIndex, godSigns) && localMoiraLostRulership(chart, '福', lifeSignIndex, selfSignIndex, godSigns)){
		addLocalMoiraPattern(patterns, '官福失垣', 'bad', '2.2.0', '政余忌格：官禄、福德主失垣。', '?{官失垣} & ?{福失垣}');
	}
	if(same(darkMoon, sun)){
		addLocalMoiraPattern(patterns, '孛犯太阳', 'bad', '2.2.0', '政余忌格：孛与太阳同宫。', '?{日孛遇}');
	}
	if(same(northNode, sun)){
		addLocalMoiraPattern(patterns, '罗犯太阳', 'bad', '2.2.0', '政余忌格：罗与太阳同宫。', '?{日罗遇}');
	}
	if(same(northNode, darkMoon)){
		addLocalMoiraPattern(patterns, '孛罗交战', 'bad', '2.2.0', '政余忌格：罗孛同宫。', '?{罗孛遇}');
	}
	if(localMoiraNearSignBoundary(lifeLon) || localMoiraNearSuBoundary(chart, lifeLon)){
		addLocalMoiraPattern(patterns, '命坐两歧', 'bad', '2.0.4', '政余忌格：命度近宫界或宿界。', '?{命宫歧} | ?{命宿歧}');
	}
	return patterns.sort((a, b)=>{
		const la = a.level === 'good' ? 0 : (a.level === 'bad' ? 1 : 2);
		const lb = b.level === 'good' ? 0 : (b.level === 'bad' ? 1 : 2);
		return la - lb;
	});
}


function computeAscSignIndex(result, chart, fields){
	const objects = chart && chart.objects ? chart.objects : [];
	const asc = objects.find((obj)=>obj.id === AstroConst.ASC);
	const sun = objects.find((obj)=>obj.id === AstroConst.SUN);
	if(!asc){
		return -1;
	}
	const ascIdx = Math.floor(Number(asc.ra) / 30);
	const mode = resolveHouseStartMode(fields);
	if(mode === SZConst.SZHouseStart_ASC){
		return ascIdx;
	}
	const bazi = (chart && chart.nongli && chart.nongli.bazi)
		|| (result && result.nongli && result.nongli.bazi);
	if(!bazi || !sun){
		return ascIdx;
	}
	const timezi = bazi.time && bazi.time.branch ? bazi.time.branch.cell : null;
	const timesig = timezi ? SZConst.ZiSign[timezi] : null;
	const tmsigidx = timesig ? AstroConst.LIST_SIGNS.indexOf(timesig) : -1;
	if(tmsigidx < 0){
		return ascIdx;
	}
	const sunidx = Math.floor(Number(sun.ra) / 30);
	return (sunidx - tmsigidx - 5 + 24) % 12;
}


function findChartObject(chart, id){
	return safeList(chart.objects).find((obj)=>obj && obj.id === id);
}


function formatGodName(name){
	let val = `${name || ''}`.replace(/\s+/g, '');
	if(!val){
		return '';
	}
	val = val.split(/[\/／]/)[0];
	const aliases = {
		天乙贵人: '天贵',
		玉堂贵人: '玉贵',
	};
	return aliases[val] || val;
}


function getChart(result){
	const root = getChartRoot(result);
	return root.chart || {};
}


function getChartRoot(result){
	return result || {};
}


function getZiGods(result){
	const root = getChartRoot(result);
	const chart = getChart(root);
	const rootGods = root.nongli && root.nongli.bazi && root.nongli.bazi.guolaoGods
		? root.nongli.bazi.guolaoGods.ziGods : null;
	const chartGods = chart.nongli && chart.nongli.bazi && chart.nongli.bazi.guolaoGods
		? chart.nongli.bazi.guolaoGods.ziGods : null;
	return chartGods || rootGods || {};
}


function guolaoLifeModeFromFields(fields){
	if(fields && fields.guolaoLifeMode && fields.guolaoLifeMode.value !== undefined && fields.guolaoLifeMode.value !== null){
		return normalizeGuolaoLifeMode(fields.guolaoLifeMode.value);
	}
	return getStoredGuolaoLifeMode();
}

// 七政宿度制(su28Mode 0-4)：优先 fields.doubingSu28（页面选/存盘值，数据丢失修复后保真），
// 缺省回退 getStoredGuolaoSu28Mode（AI 挂载抽屉「宿度制」/全局默认 2）。与 命度/罗计 同口径。

function houseFullLabel(house, idx, ascSignIndex){
	let houseName = msg(house && house.id ? house.id : null) || `第${idx + 1}宫`;
	const sign = signFromLon(house ? house.lon : null);
	if(!sign){
		return houseName;
	}
	const signIdx = AstroConst.LIST_SIGNS.indexOf(sign);
	if(signIdx >= 0 && ascSignIndex >= 0){
		const hnum = (signIdx - ascSignIndex + 12) % 12 + 1;
		houseName = `第${hnum}宫`;
	}
	const zi = SZConst.SignZi[sign] || '';
	const area = (SZConst.SZSigns[signIdx] && SZConst.SZSigns[signIdx].length >= 2)
		? `${SZConst.SZSigns[signIdx][0]}${SZConst.SZSigns[signIdx][1]}`
		: '';
	const signName = AstroText.AstroMsgCN[sign] || msg(sign);
	return `${zi}—${area}—${signName}座—${houseName}`;
}


function isEncodedToken(text){
	return /^[A-Za-z0-9${}]$/.test((text || '').trim());
}


function localLifeObject(chart, fields){
	const mode = guolaoLifeModeFromFields(fields);
	const life = findChartObject(chart, AstroConst.LIFEMASTERDEG74);
	const asc = findChartObject(chart, AstroConst.ASC);
	const sun = findChartObject(chart, AstroConst.SUN);
	if(mode === GUOLAO_LIFE_MODE_YUMAO || mode === GUOLAO_LIFE_MODE_COTRANS){
		return life || asc || sun || null;
	}
	return asc || life || sun || null;
}


function localLifeSignIndex(chart, fields){
	const life = localLifeObject(chart, fields);
	const lon = objectLon(life);
	return lon === null ? -1 : signIndexFromLon(lon);
}


function localMoiraGodSigns(godRows){
	const res = {};
	safeList(godRows).forEach((row)=>{
		const signIdx = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥'].indexOf(row.zi);
		if(signIdx < 0){
			return;
		}
		['goodGods', 'neutralGods', 'badGods', 'taisuiGods'].forEach((key)=>{
			safeList(row[key]).forEach((name)=>{
				const val = formatGodName(name);
				if(val && res[val] === undefined){
					res[val] = signIdx;
				}
			});
		});
	});
	return res;
}


function localMoiraHouseSign(lifeSignIndex, houseOffset){
	return lifeSignIndex < 0 ? -1 : (lifeSignIndex + houseOffset + 12) % 12;
}


function localMoiraIsDay(params){
	const hour = Number(`${params && params.time ? params.time : '12:00:00'}`.split(':')[0]);
	return Number.isFinite(hour) ? hour >= 6 && hour < 18 : true;
}


function localMoiraIsWinter(params){
	const raw = `${params && params.date ? params.date : ''}`.replace(/\//g, '-');
	const month = Number((raw.split('-')[1] || '').replace(/^0+/, ''));
	return month === 11 || month === 12 || month === 1;
}


function localMoiraLostRulership(chart, subject, lifeSignIndex, selfSignIndex, godSigns){
	const signIdx = localSignOfCn(chart, subject, lifeSignIndex, selfSignIndex, godSigns);
	if(signIdx < 0){
		return false;
	}
	const sign = AstroConst.LIST_SIGNS[signIdx];
	const rulerId = MOIRA_RULER_BY_SIGN[sign];
	const rulerCn = localPlanetCnById(rulerId);
	const rulerSign = objectSignIndex(chart, rulerId);
	if(rulerSign < 0){
		return false;
	}
	const rulerOfRulerSign = localPlanetCnById(MOIRA_RULER_BY_SIGN[AstroConst.LIST_SIGNS[rulerSign]]);
	return rulerOfRulerSign === MOIRA_OVERCOMING[rulerCn];
}


function localMoiraNearSignBoundary(lon){
	if(lon === null){
		return false;
	}
	const val = ((lon % 30) + 30) % 30;
	return val <= 1 || val >= 29;
}


function localMoiraNearSuBoundary(chart, lon){
	if(lon === null){
		return false;
	}
	return safeList(chart && chart.fixedStarSu28).some((item)=>{
		const ra = normDegree(item && item.ra);
		if(ra === null){
			return false;
		}
		const diff = Math.abs(normDegree(lon) - ra);
		return Math.min(diff, 360 - diff) <= 1;
	});
}


function localPlanetCnById(id){
	const row = MOIRA_PLANET_ORDER.find((item)=>item.id === id);
	return row ? row.name : msg(id);
}


function localSignOfCn(chart, name, lifeSignIndex, selfSignIndex, godSigns){
	const houseMap = {
		命: localMoiraHouseSign(lifeSignIndex, 0),
		命宫: localMoiraHouseSign(lifeSignIndex, 0),
		财: localMoiraHouseSign(lifeSignIndex, 1),
		财帛: localMoiraHouseSign(lifeSignIndex, 1),
		兄弟: localMoiraHouseSign(lifeSignIndex, 2),
		田: localMoiraHouseSign(lifeSignIndex, 3),
		田宅: localMoiraHouseSign(lifeSignIndex, 3),
		嗣: localMoiraHouseSign(lifeSignIndex, 4),
		男女: localMoiraHouseSign(lifeSignIndex, 4),
		奴: localMoiraHouseSign(lifeSignIndex, 5),
		奴仆: localMoiraHouseSign(lifeSignIndex, 5),
		妻: localMoiraHouseSign(lifeSignIndex, 6),
		夫妻: localMoiraHouseSign(lifeSignIndex, 6),
		疾: localMoiraHouseSign(lifeSignIndex, 7),
		疾厄: localMoiraHouseSign(lifeSignIndex, 7),
		迁: localMoiraHouseSign(lifeSignIndex, 8),
		迁移: localMoiraHouseSign(lifeSignIndex, 8),
		官: localMoiraHouseSign(lifeSignIndex, 9),
		官禄: localMoiraHouseSign(lifeSignIndex, 9),
		福: localMoiraHouseSign(lifeSignIndex, 10),
		福德: localMoiraHouseSign(lifeSignIndex, 10),
		相: localMoiraHouseSign(lifeSignIndex, 11),
		相貌: localMoiraHouseSign(lifeSignIndex, 11),
		身: selfSignIndex,
	};
	if(Object.prototype.hasOwnProperty.call(houseMap, name)){
		return houseMap[name];
	}
	if(godSigns && godSigns[name] !== undefined){
		return godSigns[name];
	}
	if(MOIRA_PLANET_CN_TO_ID[name]){
		return objectSignIndex(chart, MOIRA_PLANET_CN_TO_ID[name]);
	}
	const signs = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥'];
	const idx = signs.indexOf(name);
	return idx >= 0 ? idx : -1;
}


function localSignZi(signIdx){
	const sign = AstroConst.LIST_SIGNS[(signIdx + 12) % 12];
	return sign ? (SZConst.SignZi[sign] || '') : '';
}


function msg(id){
	if(id === undefined || id === null){
		return '';
	}
	if(AstroText.AstroTxtMsg[id]){
		return AstroText.AstroTxtMsg[id];
	}
	if(AstroText.AstroMsg[id]){
		const val = AstroText.AstroMsg[id];
		if(!isEncodedToken(val)){
			return `${val}`;
		}
	}
	const one = `${id}`.trim();
	if(one.length === 1 && SIMPLE_TOKEN_MAP[one]){
		return SIMPLE_TOKEN_MAP[one];
	}
	return `${id}`;
}


function normDegree(val){
	let deg = Number(val);
	if(!Number.isFinite(deg)){
		return null;
	}
	deg %= 360;
	if(deg < 0){
		deg += 360;
	}
	return deg;
}


function objectLon(obj){
	const raw = obj && (obj.ra !== undefined ? obj.ra : obj.lon);
	const lon = normDegree(raw);
	if(lon !== null){
		return lon;
	}
	const sign = obj && obj.sign ? AstroConst.LIST_SIGNS.indexOf(obj.sign) : -1;
	const signlon = Number(obj && obj.signlon);
	if(sign >= 0 && Number.isFinite(signlon)){
		return normDegree(sign * 30 + signlon);
	}
	return null;
}


function objectSignIndex(chart, id){
	const obj = findChartObject(chart, id);
	const lon = objectLon(obj);
	return lon === null ? -1 : signIndexFromLon(lon);
}


function orderGods(list, order){
	const priority = new Map(order.map((name, idx)=>[name, idx]));
	const seen = new Set();
	return safeList(list).map(formatGodName).filter((item)=>{
		if(!item || seen.has(item)){
			return false;
		}
		seen.add(item);
		return true;
	}).sort((a, b)=>{
		const ia = priority.has(a) ? priority.get(a) : 999;
		const ib = priority.has(b) ? priority.get(b) : 999;
		if(ia !== ib){
			return ia - ib;
		}
		return `${a}`.localeCompare(`${b}`, 'zh-Hans-CN');
	});
}


function resolveHouseStartMode(fields){
	if(fields && fields.houseStartMode && fields.houseStartMode.value !== undefined && fields.houseStartMode.value !== null){
		return parseInt(fields.houseStartMode.value, 10) === SZConst.SZHouseStart_ASC
			? SZConst.SZHouseStart_ASC : SZConst.SZHouseStart_Bazi;
	}
	return SZConst.SZHouseStart_Bazi;
}


function safeList(val){
	return Array.isArray(val) ? val : [];
}


function safeMap(val){
	return val && typeof val === 'object' ? val : {};
}


function signFromLon(lon){
	if(lon === undefined || lon === null || Number.isNaN(Number(lon))){
		return null;
	}
	let val = Number(lon) % 360;
	if(val < 0){
		val += 360;
	}
	const idx = Math.floor(val / 30) % 12;
	return AstroConst.LIST_SIGNS[idx];
}


function signIndexFromLon(lon){
	const sign = signFromLon(lon);
	return sign ? AstroConst.LIST_SIGNS.indexOf(sign) : -1;
}


export { buildLocalMoiraPatterns, buildGodRowsFromChart };
