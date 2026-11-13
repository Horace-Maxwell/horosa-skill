// 变换盘与黄道制的共用件:选项清单、页面设置、AI 快照文字(页面与无头同一份)。
import { definePageSettings } from './pageSettingsStore.js';

export const TRANSFORM_GROUPS = [
	{ label: '旋转与翻转', kinds: [
		{ value: 'inverted', label: '倒置盘', desc: '星和宫头转 180°。改进档四轴一起转;经典档四轴留在本命。', options: ['variant'] },
		{ value: 'sunRise', label: '日升盘', desc: '星和宫头一起旋转「上升 − 太阳」的度数,太阳落到本命上升的黄经上。改进档四轴也转,星与四轴的相对位置不变;经典档四轴留在本命。', options: ['variant'] },
		{ value: 'superimposed', label: '叠置盘', desc: '全盘旋转,让所选星落到上升点;缺省宫位与四轴不动,可选宫位同转。', options: ['planet', 'shift'] },
		{ value: 'antiscia', label: '映点盘', desc: '各星取 180° − 黄经(至点轴的镜像),四轴不动。' },
		{ value: 'contraAntiscia', label: '反映点盘', desc: '各星取 360° − 黄经(分点轴的镜像),四轴不动。' },
	] },
	{ label: '分度重排', kinds: [
		{ value: 'decanate', label: '旬盘', desc: '每座分三旬,第 k 旬取本座后第 4k 座为头,旬内度放大三倍。四轴同样变换,宫头不动,所以上升可能不在一宫头上。' },
		{ value: 'novien', label: '九分盘', desc: '黄经 × 9 − 90°;一宫头取月亮的九分位置,等宫。改进档四轴落在新宫头上;经典档四轴留在本命。', options: ['variant'] },
		{ value: 'nodeHouses', label: '北交宫盘', desc: '星不动,一宫从北交点起逆着黄经走 30°,以下逐宫同向。改进档上升落北交点;经典档四轴留在本命。', options: ['variant'] },
		{ value: 'vertical', label: '垂直黄道盘', desc: '由赤纬反推黄经:赤纬相同的两个黄经按赤纬增减取其一;赤纬超过黄赤交角的星出黄道带。南交对冲北交,福点、小行星不动。' },
	] },
	{ label: '地方盘', kinds: [
		{ value: 'geodeticLong', label: '地理盘 · 经度作中天赤经', desc: '星不动。地理经度直接当中天赤经,由此算四轴与宫位。' },
		{ value: 'geodeticRa', label: '地理盘 · 经度作中天黄经', desc: '星不动。地理经度直接当中天黄经,由此反算四轴与宫位。' },
		{ value: 'localityArmc', label: '地方盘 · 中天赤经(经典)', desc: '传统写法:基值 = 固定点 + |太阳 − |地理经度||,当中天赤经。东经西经给出同一张盘、又依赖出生太阳,与「地方固定」的本意不合,仅作对照。' },
		{ value: 'localityMc', label: '地方盘 · 中天黄经(经典)', desc: '同上,基值当中天黄经。仅作对照。' },
	] },
	{ label: '换中心与换时刻', kinds: [
		{ value: 'planetCentered', label: '行星中心盘', desc: '以所选星为中心取十星的黄经;选太阳即日心盘。位置表不列中心星;盘上中心星、交点和小行星留在地心位置作参照。', options: ['planet'] },
		{ value: 'persona', label: '人格盘', desc: '出生后太阳首次走到所选星本命黄经的时刻,在出生地起盘。选太阳就是出生那一刻,与本命盘相同。', options: ['planet'] },
		{ value: 'epoch', label: '受孕盘', desc: '出生前约 270 日,找上升点等于本命月亮的时刻,月亮尽量靠近所选本命宫头。', options: ['house'] },
	] },
	{ label: '行星根数', kinds: [
		{ value: 'planetNodes', label: '行星升交点', desc: '十星的地心平均升交点。交点、凯龙、福点等留在本命位置。' },
		{ value: 'planetNodesSouth', label: '行星降交点', desc: '十星的地心平均降交点。交点、凯龙、福点等留在本命位置。' },
		{ value: 'perihelion', label: '近日点', desc: '十星的地心平均近日点;月亮取近地点,太阳取地球过近日点那一刻太阳的地心黄经(与地球近日点方向相反,当代约在摩羯 13°,随近日点进动缓慢前移)。交点、凯龙、福点等留在本命位置。' },
		{ value: 'aphelion', label: '远日点', desc: '十星的地心平均远日点;月亮取远地点,太阳取地球过远日点那一刻太阳的地心黄经(与地球远日点方向相反,当代约在巨蟹 13°,随远日点进动缓慢前移)。交点、凯龙、福点等留在本命位置。' },
		{ value: 'secondFocus', label: '第二焦点', desc: '十星椭圆轨道的第二焦点。交点、凯龙、福点等留在本命位置。' },
	] },
	{ label: '坐标类比', kinds: [
		{ value: 'analogLatitude', label: '黄纬类比', desc: '把黄纬当黄经画。四轴固定、宫头 30° 一格。' },
		{ value: 'analogRightAscension', label: '赤经类比', desc: '把赤经当黄经画。' },
		{ value: 'analogDeclination', label: '赤纬类比', desc: '把赤纬当黄经画。' },
		{ value: 'analogDeclinationFold', label: '赤纬折叠', desc: '按黄经所在象限的起点加 |赤纬|:象限起点依次是 0°、90°、180°、270°。' },
		{ value: 'analogDeclinationBack', label: '赤纬反折', desc: '按黄经所在象限的基底加 |赤纬|:基底依次是 180°、90°、360°、270°。' },
		{ value: 'analogAzimuth', label: '方位角类比', desc: '把方位角当黄经画。' },
		{ value: 'analogAzimuthLocal', label: '本地地平类比', desc: '取 90° − 方位角。' },
		{ value: 'analogAltitude', label: '高度类比', desc: '把地平高度当黄经画。' },
		{ value: 'housePlacidus', label: '宫位类比 · Placidus', desc: '30° × (宫位值 − 1)。' },
		{ value: 'houseRegiomontanus', label: '宫位类比 · Regiomontanus', desc: '30° × (宫位值 − 1)。' },
		{ value: 'houseCampanus', label: '宫位类比 · Campanus', desc: '30° × (宫位值 − 1)。' },
		{ value: 'houseTopocentric', label: '宫位类比 · Topocentric', desc: '30° × (宫位值 − 1)。' },
	] },
];

const KIND_LIST = TRANSFORM_GROUPS.reduce((all, group)=>all.concat(group.kinds), []);
export const TRANSFORM_KINDS = KIND_LIST.map((item)=>item.value);
export function transformKindDef(kind){
	return KIND_LIST.find((item)=>item.value === kind) || KIND_LIST[0];
}
export const TRANSFORM_PLANETS = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'];
export const TRANSFORM_HOUSES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

export const TRANSFORM_PAGE_SETTINGS = definePageSettings('horosa.transform.settings.v1', {
	kind: { label: '变换', def: 'inverted', oneOf: TRANSFORM_KINDS },
	planet: { label: '基准星', def: 'Moon', oneOf: TRANSFORM_PLANETS },
	shift: { label: '宫位同转', def: false, type: 'boolean' },
	house: { label: '对应宫头', def: 1, oneOf: TRANSFORM_HOUSES },
	variant: { label: '口径', def: 'improved', oneOf: ['improved', 'classic'] },
	view: { label: '当前表', def: 'positions', oneOf: ['positions', 'rulers', 'golden', 'vertical'] },
});

export const ZODIAC_VERSIONS = [
	{ value: 'z13a', label: '十三星座 · 甲本' }, { value: 'z13iau', label: '十三星座 · 官方边界' }, { value: 'z13true', label: '十三星座 · 官方边界实测' },
	{ value: 'z13b', label: '十三星座 · 乙本' }, { value: 'z13c', label: '十三星座 · 丙本' }, { value: 'z13ab', label: '十三星座 · 甲乙均值' },
	{ value: 'z13ac', label: '十三星座 · 甲丙均值' }, { value: 'z13bc', label: '十三星座 · 乙丙均值' }, { value: 'z13cancer', label: '十三星座 · 巨蟹零度起' }, { value: 'z13cancerClassic', label: '十三星座 · 巨蟹零度起(旧排法)' },
	{ value: 'z13mid', label: '十三星座 · 中点' }, { value: 'z14', label: '十四星座 · 等分' },
	{ value: 'z12a', label: '十二段 · 甲本' }, { value: 'z12b', label: '十二段 · 乙本' }, { value: 'z12c', label: '十二段 · 丙本' }, { value: 'z12d', label: '十二段 · 丁本' },
	{ value: 'z12e', label: '十二段 · 戊本' }, { value: 'z12f', label: '十二段 · 综合本' }, { value: 'z12g', label: '十二段 · 己本' },
];
export const ZODIAC_VIEWS = ['rows', 'houses13', 'around', 'year'];
export const ZODIAC_PAGE_SETTINGS = definePageSettings('horosa.zodiacsystems.settings.v1', {
	version: { label: '黄道版本', def: 'z13a', oneOf: ZODIAC_VERSIONS.map((item)=>item.value) },
	view: { label: '当前表', def: 'rows', oneOf: ZODIAC_VIEWS },
});

export function zodiacVersionLabel(key){
	const hit = ZODIAC_VERSIONS.find((item)=>item.value === key);
	return hit ? hit.label : '';
}

const num = (v, d)=>{
	const n = Number(v);
	return Number.isFinite(n) ? n.toFixed(d) : '-';
};

// 变换盘的专属段(整张盘的星位另由派生快照带上)
export function transformSnapshotLines(result, settings, pointLabel){
	if(!result || !result.chart){ return []; }
	const def = transformKindDef(result.kind);
	const label = pointLabel || ((id)=>id);
	const out = ['[变换盘]', `变换:${def.label}。${def.desc}`];
	if((def.options || []).indexOf('planet') >= 0 && settings && settings.planet){ out.push(`基准星:${label(settings.planet)}`); }
	if((def.options || []).indexOf('shift') >= 0){ out.push(`宫位:${settings && settings.shift ? '随之旋转' : '不动'}`); }
	if((def.options || []).indexOf('house') >= 0 && settings){ out.push(`对应本命第 ${settings.house} 宫头`); }
	if((def.options || []).indexOf('variant') >= 0 && settings){ out.push(`口径:${settings.variant === 'classic' ? '经典(四轴留在本命;现代宫主表白羊主冥王、天蝎主火星)' : '改进'}`); }
	if(result.moment){ out.push(`起盘时刻:${result.moment}`); }
	if(result.coordinatesMoved === false){ out.push('这张盘的黄经是换算出来的量,赤经赤纬、方位高度、出界和赤纬平行仍按星体本来的位置。'); }
	if(result.natalHorizon === true){ out.push('地平上下和得时失时取出生时的值,不随变换改。'); }
	(result.positions || []).forEach((row)=>{
		out.push(`${label(row.id)}:本命黄经 ${num(row.natalLon, 2)}° → ${num(row.lon, 2)}°`);
	});
	const vertical = result.vertical || [];
	const outside = vertical.filter((row)=>row.outside);
	if(outside.length){ out.push(`出黄道带:${outside.map((row)=>label(row.id)).join('、')}`); }
	vertical.filter((row)=>!row.outside).forEach((row)=>{
		out.push(`${label(row.id)} 赤纬 ${num(row.declination, 2)}°:两解 ${num(row.first, 2)}° / ${num(row.second, 2)}°`);
	});
	const list = (ids)=>(ids || []).map(label).join('、');
	(result.rulers || []).forEach((row)=>{
		const withRetro = (id, retro)=>`${label(id)}${retro ? `/${label(retro)}逆` : ''}`;
		const parts = [`主星 ${withRetro(row.ruler, row.rulerRetro)}`, `共主 ${withRetro(row.coRuler, row.coRulerRetro)}`];
		if(row.nextRuler){ parts.push(`次共主 ${withRetro(row.nextRuler, row.nextRulerRetro)}`); }
		if((row.inside || []).length){ parts.push(`宫内 ${list(row.inside)}`); }
		if((row.nearCusp || []).length){ parts.push(`宫头前 3° ${list(row.nearCusp)}`); }
		out.push(`本命第 ${row.house} 宫现代宫主:${parts.join(',')}`);
	});
	(result.golden || []).filter((row)=>(row.near || []).length).forEach((row)=>{
		out.push(`黄金分割点 ${num(row.lon, 2)}°(比例 ${num(row.ratio, 3)}):${list(row.near)}`);
	});
	return out;
}

// 北交宫盘的宫是逆向走的:盘面用「段头」画,给 AI 的正文和宫主表要用真宫头(一宫从北交起)。
const SIGN_IDS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
export function transformSnapshotChart(result){
	const chartObj = result && result.chart;
	if(!chartObj || result.kind !== 'nodeHouses' || !chartObj.chart || !Array.isArray(chartObj.chart.houses)){ return chartObj; }
	const houses = chartObj.chart.houses.map((house)=>{
		const lon = (Number(house.lon) + 30) % 360;
		return { ...house, lon, sign: SIGN_IDS[Math.floor(lon / 30) % 12] };
	});
	return { ...chartObj, chart: { ...chartObj.chart, houses } };
}

export function zodiacSnapshotLines(result, pointLabel){
	if(!result || !Array.isArray(result.rows)){ return []; }
	const label = pointLabel || ((id)=>id);
	const out = ['[黄道制]', `黄道版本:${zodiacVersionLabel(result.version) || result.version}(黄经不变,只换分段)`, `银心回归黄经 ${num(result.galacticCenter, 2)}°`];
	result.rows.forEach((row)=>{
		const seg = row.versions && row.versions[result.version];
		const parts = [`回归黄经 ${num(row.lon, 2)}°`];
		if(seg){ parts.push(`${seg.sign} ${num(seg.deg, 2)}°`); }
		parts.push(`星座 ${row.conName}${row.onZodiac ? '' : '(黄道外)'}`);
		if(row.galactic){ parts.push(`银河黄道 ${row.galactic.sign} ${num(row.galactic.deg, 2)}°`); }
		out.push(`${label(row.id)}:${parts.join(' · ')}`);
	});
	// 上次与下次换星座(页面「上次与下次」表同一份数据,两头都写:AI 才看得出这颗星刚进来还是快要离开)
	(result.around || []).forEach((row)=>{
		if(row.last){ out.push(`${label(row.id)} 上次换星座:${row.last.date} 自${row.last.fromName}`); }
		if(row.next){ out.push(`${label(row.id)} 下次换星座:${row.next.date} 入${row.next.toName}`); }
	});
	const houses13 = result.rows.filter((row)=>row.houses13);
	if(houses13.length){
		out.push(`十三宫(上升起按十三星座各座长度排宫):${houses13.map((row)=>`${label(row.id)} ${row.houses13.house} 宫(宫内折 30° 为 ${num(row.houses13.fraction * 30, 1)}°)`).join('、')}`);
	}
	return out;
}
