// 印占的 Yoga 判定表、补充表、穿界时刻、八重合:界面文字、AI 快照正文与两张表的显示口径。算法在 astropy/astrostudy/india。
import * as AstroText from '../../constants/AstroText.js';
import { definePageSettings } from './pageSettingsStore.js';
import { INDIA_AYANAMSA_OPTIONS, INDIA_NAKSHATRA_COUNT_OPTIONS, INDIA_NAKSHATRA_COUNT_DEFAULT, INDIA_STAGE_MODE_OPTIONS, INDIA_STAGE_MODE_DEFAULT } from '../india/indiaConst.js';

export const YOGA_TABLE_VARIANTS = [{ value: 'improved', label: '改进' }, { value: 'classic', label: '经典' }];
export const YOGA_TABLE_SCOPES = [{ value: 'hit', label: '只看成立' }, { value: 'all', label: '全部 111 条' }];
export const YOGA_NATURE_LABELS = { good: '吉', bad: '凶', mixed: '中' };
export const DIRAH_VARIANTS = YOGA_TABLE_VARIANTS;

// 印占页显示口径跨会话保留:Yoga 判定表与补充表三项(只影响页面上看哪一列,快照两档都写,所以不进挂载齿轮),
// 外加左栏三个纯显示开关 —— 宿数口径(27 / 28 宿)、中栏盘面(本命盘 / SBC / 三旗)、盘面叠加(福德点)。
// 后三项都不进请求、不进缓存键(三旗盘的数据开关另有记录字段 indiaTripataki,页面构造时若上次停在三旗盘一并打开)。
// 读在印占页构造时,写在各控件的亲手改动里;载入命盘不回灌这六项。
// 岁差键 → 页面上显示的名字(穿界快照段头与页面同名)
const ayanamsaLabel = (key)=>{ const hit = INDIA_AYANAMSA_OPTIONS.find((item)=>item.value === key); return hit ? hit.label : key; };

export const INDIA_TABLE_SETTINGS = definePageSettings('horosa.india.tables.settings.v1', {
	yogaTableVariant: { label: 'Yoga 判定表口径', def: 'improved', oneOf: YOGA_TABLE_VARIANTS.map((item)=>item.value) },
	yogaTableScope: { label: 'Yoga 判定表显示', def: 'hit', oneOf: YOGA_TABLE_SCOPES.map((item)=>item.value) },
	dirahVariant: { label: 'Dirah 口径', def: 'improved', oneOf: DIRAH_VARIANTS.map((item)=>item.value) },
	indiaNakshatraCount: { label: '宿数口径', def: INDIA_NAKSHATRA_COUNT_DEFAULT, oneOf: INDIA_NAKSHATRA_COUNT_OPTIONS.map((item)=>item.value) },
	indiaStageMode: { label: '中栏盘面', def: INDIA_STAGE_MODE_DEFAULT, oneOf: INDIA_STAGE_MODE_OPTIONS.map((item)=>item.value) },
	indiaOverlayBB: { label: '盘面叠加福德点', def: false },
	// 穿界表三项(行运页):重开软件、备份恢复都带回;无头复算缺省也取这里
	transitPlanet: { label: '穿界表·星', def: 'all', oneOf: ['all', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'] },
	transitKind: { label: '穿界表·事件', def: 'sign', oneOf: ['sign', 'nakshatra', 'pada', 'kakshya'] },
	transitDays: { label: '穿界表·范围', def: 90, oneOf: [30, 90, 180, 366] },
});

// 穿界表当前所选:页面保存值(读不到 / 非法回缺省)
export function savedTransitSelection(){
	const saved = INDIA_TABLE_SETTINGS.load() || {};
	return { transitPlanet: saved.transitPlanet, transitKind: saved.transitKind, transitDays: saved.transitDays };
}

const SIGNS = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
const POINT_NAMES = { 'North Node': '罗睺', 'South Node': '计都', Asc: '上升', MC: '天顶' };
const KOOTA_LABELS = {
	Varna: '种姓', Vashya: '相制', Tara: '星宿吉凶', Yoni: '生类', 'Graha Maitri': '星主友谊', Gana: '性情组', Bhakoot: '星座距', Nadi: '脉',
};
const SPHUTA_LABELS = {
	Trisphuta: '三合点', Chatusphuta: '四合点', Panchasphuta: '五合点', Prana: '命息点', Deha: '身点', Mrityu: '死点', Sookshma: '细点',
};

export const TRANSIT_KIND_OPTIONS = [
	{ value: 'sign', label: '入星座' }, { value: 'nakshatra', label: '入星宿' }, { value: 'pada', label: '入足' }, { value: 'kakshya', label: '入 Kakshya' },
];
export const TRANSIT_DAY_OPTIONS = [{ value: 30, label: '30 天' }, { value: 90, label: '90 天' }, { value: 180, label: '180 天' }, { value: 366, label: '一年' }];
export const TRANSIT_PLANET_OPTIONS = [
	{ value: 'all', label: '七星' }, { value: 'Sun', label: '太阳' }, { value: 'Moon', label: '月亮' }, { value: 'Mercury', label: '水星' },
	{ value: 'Venus', label: '金星' }, { value: 'Mars', label: '火星' }, { value: 'Jupiter', label: '木星' }, { value: 'Saturn', label: '土星' },
];
export const TRANSIT_DEFAULT_SELECTION = { transitPlanet: 'all', transitKind: 'sign', transitDays: 90 };
// 快照最多收这么多行(一年 · 七星 · 入足可到 600 行,全塞进去会挤掉别的段)
export const TRANSIT_SNAPSHOT_MAX_ROWS = 200;
export const DIRAH_WESTERN_TYPES = { 1: '本座', 2: '擢升', 3: '落', 4: '陷', 5: '八十二宫', 6: '同序宫', 7: '相位多', 8: '与木星成相', 10: '逆行' };
const RELATION_LABELS = { own: '自座', friend: '友', neutral: '中', enemy: '敌' };

export const extraPointName = (id)=>POINT_NAMES[id] || (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || `${id}`;
export const kootaLabel = (name)=>KOOTA_LABELS[name] || name;
export const sphutaLabel = (name)=>SPHUTA_LABELS[name] || name;

export function extraLon(lon){
	const value = ((Number(lon) || 0) % 360 + 360) % 360;
	return `${SIGNS[Math.floor(value / 30)]} ${(value % 30).toFixed(2)}°`;
}

export function transitEventText(row){
	const back = row.retrograde ? '(逆)' : '';
	if(row.kind === 'sign'){ return `${SIGNS[row.sign]}${back}`; }
	if(row.kind === 'nakshatra'){ return `第 ${row.number} 宿${back}`; }
	if(row.kind === 'pada'){ return `第 ${row.number} 足${back}`; }
	return `${SIGNS[row.sign]}第 ${row.number} 段 · ${row.lord === 'Asc' ? '上升' : extraPointName(row.lord)}${back}`;
}

export const transitRelationText = (relation)=>RELATION_LABELS[relation] || relation;

const optionLabel = (options, value)=>{
	const hit = options.find((item)=>`${item.value}` === `${value}`);
	return hit ? hit.label : `${value}`;
};

// 穿界表认盘只看出生时空:时刻由起始日决定,不随别的选项变
export function indiaTransitBirthSig(params){
	if(!params){ return ''; }
	return ['date', 'time', 'zone', 'lat', 'lon'].map((key)=>`${params[key] === undefined || params[key] === null ? '' : params[key]}`).join('|');
}

// 页面上的穿界表(所选的星、事件、范围与结果),按出生时空分槽:印占页与择日内嵌的印占盘各有一张,互不顶掉
// (此前只有一个槽,择日页一算就把印占页那张换成择日盘的,印占快照随即丢了这一段)。印占快照按出生时空认领,
// 认不上就不写;重算期间清掉这张盘的槽,旧表不留给 AI。
const TRANSIT_SNAPSHOT_SLOTS_MAX = 6;
const transitSnapshotSlots = new Map();
// entry 有效 → 写它那张盘的槽;entry 为空 → 清 birthSig 那张盘的槽(不给 birthSig = 全清)
export function setIndiaTransitSnapshot(entry, birthSig){
	if(entry && entry.birthSig && entry.result && Array.isArray(entry.result.rows)){
		transitSnapshotSlots.delete(entry.birthSig);
		transitSnapshotSlots.set(entry.birthSig, { ...entry });
		while(transitSnapshotSlots.size > TRANSIT_SNAPSHOT_SLOTS_MAX){
			transitSnapshotSlots.delete(transitSnapshotSlots.keys().next().value);
		}
		return;
	}
	const sig = entry && entry.birthSig ? entry.birthSig : birthSig;
	if(sig){ transitSnapshotSlots.delete(sig); }else{ transitSnapshotSlots.clear(); }
}
export function indiaTransitSnapshotFor(birthSig){
	return birthSig && transitSnapshotSlots.has(birthSig) ? transitSnapshotSlots.get(birthSig) : null;
}
export function __resetIndiaTransitSnapshotForTests(){ transitSnapshotSlots.clear(); }

// entry = { start, transitPlanet, transitKind, transitDays, ayanamsa, result }
export function buildTransitEventLines(entry){
	if(!entry || !entry.result || !Array.isArray(entry.result.rows)){ return []; }
	const rows = entry.result.rows;
	const total = Number.isFinite(Number(entry.result.total)) ? Number(entry.result.total) : rows.length;
	const head = `起始 ${entry.start || '-'},范围 ${optionLabel(TRANSIT_DAY_OPTIONS, entry.transitDays)},星 ${optionLabel(TRANSIT_PLANET_OPTIONS, entry.transitPlanet)},事件 ${optionLabel(TRANSIT_KIND_OPTIONS, entry.transitKind)};共 ${total} 条,时刻按本盘时区,恒星黄道${entry.ayanamsa ? `(岁差 ${ayanamsaLabel(entry.ayanamsa)})` : ''}`;
	if(!rows.length){ return [head, '这段时间里没有所选的穿界事件']; }
	const shown = rows.slice(0, TRANSIT_SNAPSHOT_MAX_ROWS);
	const lines = [head, ...table(['时刻', '星', '进入', '座主'], shown.map((row)=>[
		`${row.date} ${`${row.time || ''}`.slice(0, 5)}`.trim(), extraPointName(row.planet), transitEventText(row), transitRelationText(row.relation) || '',
	]))];
	if(shown.length < total){ lines.push(`只列前 ${shown.length} 条(共 ${total} 条),要看全部请到印占「行运」页缩短范围或只看一颗星`); }
	return lines;
}

const isFemale = (g)=>['0', '女', 'Female', 'female', 'F', 'f'].includes(`${g}`);
const isMale = (g)=>['1', '男', 'Male', 'male', 'M', 'm'].includes(`${g}`);

// 记录里的性别定男方;都不明或同性时默认星盘 A
export function maleSideOf(genderA, genderB){
	if(isFemale(genderA) && !isFemale(genderB)){ return 'outer'; }
	if(isMale(genderB) && !isMale(genderA)){ return 'outer'; }
	return 'inner';
}

// 八重合男方:页内亲手改过的,本次运行里这一对都按所改的算(页面与 AI 双盘挂载同一口径);重开软件回到按性别。
// 男方和性别一样是这一对人的输入,不跨会话保留。
const ASHTAKOOTA_MALE_PICKS = new Map();
const ASHTAKOOTA_MALE_PICKS_MAX = 32;
const pairSideKey = (p)=>indiaTransitBirthSig(p);
export function rememberAshtakootaMaleSide(inner, outer, side, defaultSide){
	const key = `${pairSideKey(inner)}#${pairSideKey(outer)}`;
	ASHTAKOOTA_MALE_PICKS.delete(`${pairSideKey(outer)}#${pairSideKey(inner)}`);
	if(!side || side === defaultSide){
		ASHTAKOOTA_MALE_PICKS.delete(key);
		return;
	}
	ASHTAKOOTA_MALE_PICKS.delete(key);
	ASHTAKOOTA_MALE_PICKS.set(key, side);
	while(ASHTAKOOTA_MALE_PICKS.size > ASHTAKOOTA_MALE_PICKS_MAX){ ASHTAKOOTA_MALE_PICKS.delete(ASHTAKOOTA_MALE_PICKS.keys().next().value); }
}
// 两盘对调(挂载时本人是页面上的星盘 B)也认得,男方跟着对调
export function pickedAshtakootaMaleSide(inner, outer){
	const a = pairSideKey(inner);
	const b = pairSideKey(outer);
	if(ASHTAKOOTA_MALE_PICKS.has(`${a}#${b}`)){ return ASHTAKOOTA_MALE_PICKS.get(`${a}#${b}`); }
	if(ASHTAKOOTA_MALE_PICKS.has(`${b}#${a}`)){ return ASHTAKOOTA_MALE_PICKS.get(`${b}#${a}`) === 'inner' ? 'outer' : 'inner'; }
	return null;
}
export function __resetAshtakootaMalePicksForTests(){ ASHTAKOOTA_MALE_PICKS.clear(); }

// Nadi、Bhakoot 落 0 分 = 有 Dosha;后端只标满足了哪些常见化解条件,不改分
const DOSHA_KOOTAS = { Nadi: 'Nadi Dosha(脉)', Bhakoot: 'Bhakoot Dosha(星座距)' };
const DOSHA_CANCEL_LABELS = {
	sameSignDifferentNakshatra: '两人月亮同座不同宿',
	sameNakshatraDifferentSign: '两人月亮同宿不同座',
	sameNakshatraDifferentPada: '两人月亮同宿不同足',
	sameSignLord: '两人月亮所在座的座主是同一颗星',
	friendlySignLords: '两人月亮所在座的座主互为天然之友',
};
export const doshaCancelLabel = (key)=>DOSHA_CANCEL_LABELS[key] || key;
export function ashtakootaDoshas(result){
	if(!result || !Array.isArray(result.doshas)){ return []; }
	return result.doshas.filter((item)=>item && item.present && DOSHA_KOOTAS[item.koota]).map((item)=>({
		koota: item.koota,
		label: DOSHA_KOOTAS[item.koota],
		cancels: (Array.isArray(item.cancel) ? item.cancel : []).map(doshaCancelLabel),
	}));
}
export function doshaCancelText(item){
	return item.cancels.length ? `满足化解条件:${item.cancels.join('、')}` : '没有满足本页列出的化解条件';
}

export const yogaRowHit = (row, variant)=>(variant === 'classic' ? !!row.classicHit : !!row.hit);
export const yogaRowCond = (row, variant)=>(variant === 'classic' && row.classicCond ? row.classicCond : row.cond);

export function dirahColumns(rows, types){
	const used = new Set();
	(rows || []).forEach((row)=>Object.keys(row.scores || {}).forEach((key)=>used.add(key)));
	return Object.keys(types || {}).filter((key)=>used.has(key)).sort((a, b)=>Number(a) - Number(b));
}

const scoreText = (value)=>(value === undefined || value === null ? '' : `${value > 0 ? '+' : ''}${value}`);
export const dirahScore = scoreText;

function table(heads, rows){
	return [`| ${heads.join(' | ')} |`, `| ${heads.map(()=>'---').join(' | ')} |`, ...rows.map((row)=>`| ${row.join(' | ')} |`)];
}

export function buildYogaTableLines(data){
	if(!data || data.available === false || !Array.isArray(data.rows)){ return []; }
	const hits = data.rows.filter((row)=>row.hit || row.classicHit);
	const lines = [`111 条里成立 ${data.hits} 条(经典写法 ${data.classicHits} 条),按上升星座起整宫,计数只算七曜`];
	if(!hits.length){ return lines; }
	return lines.concat(table(['组合', '类', '性质', '改进', '经典', '条件'], hits.map((row)=>[
		`${row.zh}(${row.name})`, row.group, YOGA_NATURE_LABELS[row.nature] || '中', row.hit ? '成立' : '不成立', row.classicHit ? '成立' : '不成立', row.hit ? row.cond : yogaRowCond(row, 'classic'),
	])));
}

export function buildExtraTableLines(data){
	if(!data || data.available === false){ return []; }
	const lines = [];
	if(Array.isArray(data.samaya) && data.samaya.length){
		lines.push('Graha Samaya(0–26,经验式)');
		lines.push(...table(['星', '值'], data.samaya.map((row)=>[extraPointName(row.planet), row.value])));
	}
	if(Array.isArray(data.dirah) && data.dirah.length){
		const keys = dirahColumns(data.dirah, data.dirahTypes);
		lines.push('Dirah Bala');
		lines.push(...table(['星', ...keys.map((key)=>data.dirahTypes[key]), '合计'], data.dirah.map((row)=>[
			extraPointName(row.planet), ...keys.map((key)=>scoreText(row.scores[key])), scoreText(row.sum),
		])));
	}
	if(Array.isArray(data.dirahClassic) && data.dirahClassic.length){
		lines.push('Dirah Bala 合计(经典口径)');
		lines.push(...table(['星', '合计'], data.dirahClassic.map((row)=>[extraPointName(row.planet), scoreText(row.sum)])));
	}
	if(Array.isArray(data.dirahWestern) && data.dirahWestern.length){
		const keys = dirahColumns(data.dirahWestern, DIRAH_WESTERN_TYPES);
		lines.push('Dirah 西占版');
		lines.push(...table(['星', ...keys.map((key)=>DIRAH_WESTERN_TYPES[key])], data.dirahWestern.map((row)=>[
			extraPointName(row.planet), ...keys.map((key)=>scoreText(row.scores[key])),
		])));
	}
	// 经典档与改进档只差天王星守水瓶一项:只写与改进档不同的星,全同就写一句
	if(Array.isArray(data.dirahWesternClassic) && data.dirahWesternClassic.length){
		const improved = {};
		(data.dirahWestern || []).forEach((row)=>{ improved[row.planet] = JSON.stringify(row.scores || {}); });
		const diff = data.dirahWesternClassic.filter((row)=>improved[row.planet] !== JSON.stringify(row.scores || {}));
		if(!diff.length){
			lines.push('Dirah 西占版(经典口径):与上表逐项相同');
		}else{
			// 列取这几颗星两档用到过的项:经典档少掉的那一项也要露出来(空着)
			const pair = diff.concat((data.dirahWestern || []).filter((row)=>diff.some((d)=>d.planet === row.planet)));
			const keys = dirahColumns(pair, DIRAH_WESTERN_TYPES);
			lines.push('Dirah 西占版(经典口径,水瓶不算天王星的本座;只列与上表不同的星)');
			lines.push(...table(['星', ...keys.map((key)=>DIRAH_WESTERN_TYPES[key])], diff.map((row)=>[
				extraPointName(row.planet), ...keys.map((key)=>scoreText(row.scores[key])),
			])));
		}
	}
	if(data.polar){ lines.push('本盘在极圈内,Dirah 的宫位分按 Porphyry 宫算'); }
	if(Array.isArray(data.sphuta) && data.sphuta.length){
		lines.push('Sphuta');
		lines.push(...table(['点', '位置'], data.sphuta.map((row)=>[`${sphutaLabel(row.name)}(${row.name})`, extraLon(row.lon)])));
	}
	return lines;
}

export function buildAshtakootaLines(result){
	if(!result || !Array.isArray(result.rows)){ return []; }
	return [
		`合计 ${result.total} / ${result.max}(另一套传统表 ${result.classicTotal}),岁差 ${result.ayanamsa || 'Lahiri'}`,
		`男方:${result.maleSide === 'outer' ? '星盘 B' : '星盘 A'},月亮 ${SIGNS[result.groomSign]} 第 ${result.groomNakshatra} 宿;女方:月亮 ${SIGNS[result.brideSign]} 第 ${result.brideNakshatra} 宿`,
		...table(['项', '满分', '通行表', '传统表'], result.rows.map((row)=>[`${kootaLabel(row.name)}(${row.name})`, row.max, row.score, row.classic])),
		...ashtakootaDoshaLines(result),
	];
}

function ashtakootaDoshaLines(result){
	if(!result || !Array.isArray(result.doshas)){ return []; }
	const items = ashtakootaDoshas(result);
	if(!items.length){ return ['Dosha:脉、星座距两项都不是 0 分,没有 Nadi / Bhakoot Dosha']; }
	return [
		...items.map((item)=>`有 ${item.label}(该项 0 分);${doshaCancelText(item)}`),
		'化解条件只作标注,分数照原样;各家认不认、认哪几条说法不一',
	];
}
